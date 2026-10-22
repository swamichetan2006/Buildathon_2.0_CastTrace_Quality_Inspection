import io
import json
import os
import time
import hashlib
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from PIL import Image

@dataclass
class InferenceResult:
    status: str  # SUCCEEDED or FAILED
    predicted_label: Optional[str] = None  # Strictly binary: GOOD or DEFECTIVE
    score: Optional[float] = None  # PROBABILITY_DEFECTIVE
    score_type: str = "PROBABILITY_DEFECTIVE"
    threshold_applied: float = 0.50000
    routing_outcome: Optional[str] = None  # LIKELY_OK, NEEDS_REVIEW, LIKELY_DEFECTIVE
    routing_reason: Optional[str] = None
    quality_gate_passed: bool = True
    quality_gate_reason: Optional[str] = None
    is_unfamiliar: bool = False
    guard_distance: Optional[float] = None
    guard_threshold: Optional[float] = None
    processing_latency_ms: Optional[int] = None
    error_code: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    model_version_name: Optional[str] = None
    model_architecture: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class InferenceService:
    """Dedicated inference engine executed strictly inside the background worker process.
    
    FastAPI API web server processes MUST NOT instantiate or call this service to load PyTorch weights.
    """

    def __init__(
        self,
        metadata_path: str = "ml/artifacts/model_metadata.json",
        custom_predictor = None,  # For test-only dependency injection
        device: str = "cpu"
    ):
        self.metadata_path = metadata_path
        self.custom_predictor = custom_predictor
        self.device_str = device
        self.model = None
        self.guard = None
        self.eval_transform = None
        self.metadata = None
        self.is_loaded = False
        self.last_error = None

    def _get_sha256(self, filepath: str) -> str:
        with open(filepath, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def verify_artifacts(self) -> Tuple[bool, Optional[str]]:
        """Verify that all required model and guard artifacts exist locally and match their cryptographic hashes."""
        if not os.path.exists(self.metadata_path):
            return False, f"Model metadata not found at {self.metadata_path}"

        try:
            with open(self.metadata_path, "r") as f:
                self.metadata = json.load(f)
        except Exception as e:
            return False, f"Failed to parse model metadata JSON: {e}"

        weights_file = self.metadata.get("weights_file", "model_best.pt")
        weights_path = os.path.join("ml", "artifacts", weights_file)
        expected_weights_sha = self.metadata.get("weights_sha256")

        if not os.path.exists(weights_path):
            return False, f"Model weights not found at {weights_path}"
        if expected_weights_sha:
            actual_weights_sha = self._get_sha256(weights_path)
            if actual_weights_sha != expected_weights_sha:
                return False, f"Weights SHA-256 mismatch: expected {expected_weights_sha}, got {actual_weights_sha}"

        guard_file = self.metadata.get("guard_reference_file", "unfamiliar_guard_reference.json")
        guard_path = os.path.join("ml", "artifacts", guard_file)
        expected_guard_sha = self.metadata.get("guard_reference_sha256")

        if not os.path.exists(guard_path):
            return False, f"Guard reference not found at {guard_path}"
        if expected_guard_sha:
            actual_guard_sha = self._get_sha256(guard_path)
            if actual_guard_sha != expected_guard_sha:
                return False, f"Guard reference SHA-256 mismatch: expected {expected_guard_sha}, got {actual_guard_sha}"

        return True, None

    def load_model(self):
        """Load PyTorch architecture, weights, and unfamiliar-input reference."""
        if self.custom_predictor is not None:
            # Test-only injection mode
            self.is_loaded = True
            return

        valid, err = self.verify_artifacts()
        if not valid:
            self.last_error = err
            raise RuntimeError(f"Artifact verification failed: {err}")

        # Lazy imports of PyTorch and ML packages inside worker only
        import torch
        from casttrace_ml.model import build_model
        from casttrace_ml.preprocessing import get_eval_transform
        from casttrace_ml.unfamiliar_input import UnfamiliarInputGuard

        device = torch.device(self.device_str)
        arch = self.metadata.get("model_architecture", "ResNet-18").lower().replace("-", "")
        if "resnet18" in arch:
            model_arch = "resnet18"
        elif "mobilenet" in arch:
            model_arch = "mobilenet_v3_small"
        else:
            model_arch = "resnet18"

        weights_file = self.metadata.get("weights_file", "model_best.pt")
        weights_path = os.path.join("ml", "artifacts", weights_file)

        checkpoint = torch.load(weights_path, map_location=device)
        self.model = build_model(architecture=model_arch, pretrained=False)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.to(device)
        self.model.eval()

        guard_file = self.metadata.get("guard_reference_file", "unfamiliar_guard_reference.json")
        guard_path = os.path.join("ml", "artifacts", guard_file)
        self.guard = UnfamiliarInputGuard.load(guard_path)
        self.eval_transform = get_eval_transform()

        self.is_loaded = True
        self.last_error = None

    def predict_image(
        self,
        image_bytes: bytes,
        original_filename: str = "image.jpg",
    ) -> InferenceResult:
        """Run the complete, ordered 4-stage inference pipeline on raw image bytes.
        
        Order:
        1. Image usability & quality gate
        2. Unfamiliar-input guard
        3. Classifier forward pass
        4. Final image-level triage outcome
        """
        start_time = time.perf_counter()

        version_name = self.metadata.get("model_version", "v1.0.0-resnet18") if self.metadata else "v1.0.0-resnet18"
        arch_name = self.metadata.get("model_architecture", "ResNet-18") if self.metadata else "ResNet-18"

        # 0. Validate image bytes and format
        try:
            raw_img = Image.open(io.BytesIO(image_bytes))
            raw_img.verify()
            raw_img = Image.open(io.BytesIO(image_bytes))  # Re-open after verify
        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            return InferenceResult(
                status="FAILED",
                error_code="CORRUPTED_IMAGE_DATA",
                error_details={"error": f"Image content is unreadable or corrupted: {str(e)}"},
                processing_latency_ms=latency,
                model_version_name=version_name,
                model_architecture=arch_name,
            )

        # Handle test-only custom predictor
        if self.custom_predictor is not None:
            return self.custom_predictor(image_bytes, raw_img)

        if not self.is_loaded:
            self.load_model()

        # Lazy imports of quality gate
        from casttrace_ml.quality_gate import check_image_quality
        import torch
        import numpy as np

        # Stage 1: Quality Gate
        q_res = check_image_quality(raw_img)
        if not q_res.passed:
            latency = int((time.perf_counter() - start_time) * 1000)
            return InferenceResult(
                status="SUCCEEDED",
                predicted_label=None,
                score=None,
                routing_outcome="NEEDS_REVIEW",
                routing_reason=f"Quality gate failure: {q_res.reason}",
                quality_gate_passed=False,
                quality_gate_reason=q_res.reason,
                processing_latency_ms=latency,
                model_version_name=version_name,
                model_architecture=arch_name,
            )

        # Stage 2: Feature extraction & Unfamiliar-Input Guard
        device = torch.device(self.device_str)
        tensor = self.eval_transform(raw_img.convert("RGB")).unsqueeze(0).to(device)

        with torch.no_grad():
            emb = self.model.extract_features(tensor).squeeze().cpu().numpy()
            emb /= np.maximum(np.linalg.norm(emb), 1e-8)
            g_res = self.guard.evaluate(emb)

        if g_res.is_unfamiliar:
            latency = int((time.perf_counter() - start_time) * 1000)
            return InferenceResult(
                status="SUCCEEDED",
                predicted_label=None,
                score=None,
                routing_outcome="NEEDS_REVIEW",
                routing_reason=f"Unfamiliar-input alert: Feature distance {g_res.distance:.5f} exceeds reference threshold {self.guard.guard_threshold:.5f}",
                quality_gate_passed=True,
                is_unfamiliar=True,
                guard_distance=float(g_res.distance),
                guard_threshold=float(self.guard.guard_threshold),
                processing_latency_ms=latency,
                model_version_name=version_name,
                model_architecture=arch_name,
            )

        # Stage 3: Classifier logits & calibrated routing
        with torch.no_grad():
            logits = self.model(tensor)
            probs = torch.softmax(logits, dim=1).squeeze().cpu().numpy()
            score_defective = float(probs[1])

        # Stage 4: Apply frozen routing thresholds (T_ok = 0.01, T_def = 0.50)
        t_ok = 0.01
        t_def = 0.50

        # Binary prediction (standard 0.50 decision boundary)
        binary_pred = "DEFECTIVE" if score_defective >= 0.50 else "GOOD"

        if score_defective <= t_ok:
            outcome = "LIKELY_OK"
            reason = f"High-confidence conforming (P_def {score_defective:.5f} <= {t_ok})"
        elif score_defective >= t_def:
            outcome = "LIKELY_DEFECTIVE"
            reason = f"High-confidence defect detected (P_def {score_defective:.5f} >= {t_def})"
        else:
            outcome = "NEEDS_REVIEW"
            reason = f"Borderline model score ({t_ok} < P_def {score_defective:.5f} < {t_def}) quarantined for human review"

        latency = int((time.perf_counter() - start_time) * 1000)

        return InferenceResult(
            status="SUCCEEDED",
            predicted_label=binary_pred,
            score=round(score_defective, 5),
            score_type="PROBABILITY_DEFECTIVE",
            threshold_applied=t_def,
            routing_outcome=outcome,
            routing_reason=reason,
            quality_gate_passed=True,
            is_unfamiliar=False,
            guard_distance=float(g_res.distance),
            guard_threshold=float(self.guard.guard_threshold),
            processing_latency_ms=latency,
            model_version_name=version_name,
            model_architecture=arch_name,
        )
