"""CastTrace AI Machine Learning Engine: Core package exports."""

from casttrace_ml.preprocessing import (
    DEFAULT_INPUT_SIZE,
    IMAGENET_MEAN,
    IMAGENET_STD,
    get_eval_transform,
    get_inference_transform,
    get_train_transform,
    preprocess_image_bytes,
    preprocess_pil,
)

from casttrace_ml.quality_gate import (
    QualityGateResult,
    check_image_quality,
    compute_laplacian_variance,
)

from casttrace_ml.routing import (
    RoutingEvaluationResult,
    RoutingThresholds,
    evaluate_routing,
    optimize_routing_thresholds,
    wilson_score_interval,
)

from casttrace_ml.unfamiliar_input import (
    GuardEvaluationResult,
    UnfamiliarInputGuard,
    build_guard_reference,
)

from casttrace_ml.model import (
    CastingClassifier,
    MobileNetV3SmallClassifier,
    build_model,
    load_model_checkpoint,
)

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_INPUT_SIZE",
    "IMAGENET_MEAN",
    "IMAGENET_STD",
    "get_eval_transform",
    "get_inference_transform",
    "get_train_transform",
    "preprocess_image_bytes",
    "preprocess_pil",
    "QualityGateResult",
    "check_image_quality",
    "compute_laplacian_variance",
    "RoutingEvaluationResult",
    "RoutingThresholds",
    "evaluate_routing",
    "optimize_routing_thresholds",
    "wilson_score_interval",
    "GuardEvaluationResult",
    "UnfamiliarInputGuard",
    "build_guard_reference",
    "CastingClassifier",
    "build_model",
    "load_model_checkpoint",
]

