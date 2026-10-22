"""Unit tests verifying shared ML preprocessing, quality gate, OOD guard, and routing consistency."""

import io
import json
import pytest
import numpy as np
import torch
from PIL import Image

from casttrace_ml.preprocessing import (
    get_eval_transform,
    get_inference_transform,
    preprocess_pil,
    preprocess_image_bytes,
)
from casttrace_ml.quality_gate import (
    check_image_quality,
    compute_laplacian_variance,
)
from casttrace_ml.routing import (
    RoutingThresholds,
    evaluate_routing,
    wilson_score_interval,
)
from casttrace_ml.unfamiliar_input import (
    UnfamiliarInputGuard,
)


def test_deterministic_preprocessing_identical_tensors():
    """Verify that deterministic evaluation and live inference transforms produce bitwise identical tensors."""
    # Create test image with varied patterns and gradients
    arr = np.linspace(0, 255, num=512*512, dtype=np.uint8).reshape((512, 512))
    img = Image.fromarray(arr, mode="L").convert("RGB")

    eval_transform = get_eval_transform()
    inf_transform = get_inference_transform()

    tensor_eval = eval_transform(img)
    tensor_inf = inf_transform(img)

    # 1. Exact equality of tensor shapes
    assert tensor_eval.shape == tensor_inf.shape == (3, 224, 224)
    # 2. Strict bitwise numerical identity
    assert torch.equal(tensor_eval, tensor_inf)
    assert torch.allclose(tensor_eval, tensor_inf, atol=1e-7)


def test_preprocess_pil_and_bytes_identical():
    """Verify that preprocessing from PIL image and from raw bytes yields identical tensors."""
    img = Image.new("RGB", (300, 300), color=(120, 140, 160))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    raw_bytes = buffer.getvalue()

    tensor_from_pil = preprocess_pil(img)
    tensor_from_bytes = preprocess_image_bytes(raw_bytes)

    assert tensor_from_pil.shape == tensor_from_bytes.shape == (1, 3, 224, 224)
    assert torch.equal(tensor_from_pil, tensor_from_bytes)


def test_quality_gate_checks():
    """Verify that the quality gate correctly validates valid images and rejects degraded inputs."""
    # 1. Valid textured image passes
    valid_arr = np.random.randint(40, 200, size=(400, 400), dtype=np.uint8)
    valid_img = Image.fromarray(valid_arr, mode="L").convert("RGB")
    res_valid = check_image_quality(valid_img)
    assert res_valid.passed is True
    assert res_valid.reason is None

    # 2. Too small resolution (< 128px) fails
    tiny_img = Image.new("RGB", (64, 64), color=(100, 100, 100))
    res_tiny = check_image_quality(tiny_img)
    assert res_tiny.passed is False
    assert "Resolution too low" in res_tiny.reason

    # 3. Severely underexposed image fails
    dark_img = Image.new("RGB", (256, 256), color=(5, 5, 5))
    res_dark = check_image_quality(dark_img)
    assert res_dark.passed is False
    assert "underexposed" in res_dark.reason

    # 4. Severely overexposed image fails
    bright_img = Image.new("RGB", (256, 256), color=(250, 250, 250))
    res_bright = check_image_quality(bright_img)
    assert res_bright.passed is False
    assert "overexposed" in res_bright.reason

    # 5. Flat zero-contrast / blurry image fails
    flat_img = Image.new("RGB", (256, 256), color=(128, 128, 128))
    res_flat = check_image_quality(flat_img)
    assert res_flat.passed is False


def test_routing_logic_and_wilson_ci():
    """Verify routing math, precision calculation, miss rate, and Wilson score intervals."""
    scores = np.array([0.05, 0.10, 0.40, 0.85, 0.95])
    labels = np.array([0,    0,    1,    1,    1])  # 0=GOOD, 1=DEFECTIVE

    thresholds = RoutingThresholds(t_ok=0.20, t_def=0.80)
    res = evaluate_routing(scores, labels, thresholds)

    # Buckets:
    # LIKELY_OK (<=0.20): scores 0.05 (Good), 0.10 (Good) -> count=2, 0 false negatives
    # LIKELY_DEFECTIVE (>=0.80): scores 0.85 (Defective), 0.95 (Defective) -> count=2, precision=100%
    # NEEDS_REVIEW: score 0.40 (Defective) -> count=1
    assert res.count_likely_ok == 2
    assert res.count_likely_defective == 2
    assert res.count_needs_review == 1

    assert res.likely_def_precision == 1.0
    assert res.likely_ok_miss_rate == 0.0
    assert res.routing_coverage == 0.8

    # Check Wilson CI bounds: must be in [0, 1]
    low, high = res.likely_def_precision_ci
    assert 0.0 <= low <= high <= 1.0

    # Test unfamiliar or quality failure forces NEEDS_REVIEW
    routed_override = thresholds.route(score_defective=0.01, is_unfamiliar=True, quality_passed=True)
    assert routed_override == "NEEDS_REVIEW"

    routed_override_qf = thresholds.route(score_defective=0.99, is_unfamiliar=False, quality_passed=False)
    assert routed_override_qf == "NEEDS_REVIEW"


def test_unfamiliar_input_guard():
    """Verify that unfamiliar-input guard identifies out-of-distribution inputs."""
    # Mock prototype embedding [1, 512]
    np.random.seed(42)
    proto = np.random.randn(1, 512).astype(np.float32)
    proto /= np.linalg.norm(proto)

    guard = UnfamiliarInputGuard(prototypes=proto, guard_threshold=0.20)

    # In-distribution vector (close to proto, cosine distance < 0.20)
    in_dist = proto + np.random.randn(1, 512).astype(np.float32) * 0.005
    in_dist /= np.linalg.norm(in_dist)
    eval_in = guard.evaluate(in_dist.squeeze(0))
    assert eval_in.is_unfamiliar is False
    assert eval_in.distance < 0.20

    # Out-of-distribution vector (orthogonal/opposite, cosine distance > 0.20)
    out_dist = -proto.squeeze(0)  # Cosine distance = 2.0
    eval_out = guard.evaluate(out_dist)
    assert eval_out.distance > 0.20
    assert eval_out.is_unfamiliar is True


def test_model_architectures_feature_extraction():
    """Verify that both ResNet-18 and MobileNetV3-Small architectures initialize and extract feature tensors."""
    from casttrace_ml.model import build_model

    dummy_input = torch.randn(2, 3, 224, 224)

    # 1. ResNet-18 (512-dim features)
    m_resnet = build_model(architecture="resnet18", pretrained=False)
    m_resnet.eval()
    feat_res = m_resnet.extract_features(dummy_input)
    logits_res = m_resnet(dummy_input)
    assert feat_res.shape == (2, 512)
    assert logits_res.shape == (2, 2)

    # 2. MobileNetV3-Small (576-dim features)
    m_mobilenet = build_model(architecture="mobilenet_v3_small", pretrained=False)
    m_mobilenet.eval()
    feat_mob = m_mobilenet.extract_features(dummy_input)
    logits_mob = m_mobilenet(dummy_input)
    assert feat_mob.shape == (2, 576)
    assert logits_mob.shape == (2, 2)


def test_validation_routing_reconciliation_and_safeguards():
    """Verify that routing reconciliation mathematically balances (194=77 Good + 117 Defective) and safeguards hold."""
    with open("ml/artifacts/model_metadata.json", "r") as f:
        meta = json.load(f)

    routing = meta["validation_routing"]
    counts = routing["ordered_routing_counts"]

    # Verify reconciliation
    ok_g = counts["LIKELY_OK"]["actual_good"]
    ok_d = counts["LIKELY_OK"]["actual_defective"]
    rev_g = counts["NEEDS_REVIEW"]["actual_good"]
    rev_d = counts["NEEDS_REVIEW"]["actual_defective"]
    def_g = counts["LIKELY_DEFECTIVE"]["actual_good"]
    def_d = counts["LIKELY_DEFECTIVE"]["actual_defective"]

    # Sum checks
    assert ok_g + rev_g + def_g == 77, f"Total GOOD {ok_g + rev_g + def_g} != 77"
    assert ok_d + rev_d + def_d == 117, f"Total DEFECTIVE {ok_d + rev_d + def_d} != 117"
    assert counts["LIKELY_OK"]["total"] + counts["NEEDS_REVIEW"]["total"] + counts["LIKELY_DEFECTIVE"]["total"] == 194

    # Safeguard check: 0 defective missed into LIKELY_OK at recommended threshold
    assert ok_d == 0
    assert counts["LIKELY_OK"]["total"] == ok_g

    # Safeguard check: Unfamiliar guard flags routed to NEEDS_REVIEW
    guard_flags = counts["NEEDS_REVIEW"]["subcategories"]["unfamiliar_guard_flags"]
    assert guard_flags["DEFECTIVE"] == 2

