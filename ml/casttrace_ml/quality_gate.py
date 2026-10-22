"""Input image quality verification gate for industrial casting inspection."""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import numpy as np
from PIL import Image


@dataclass
class QualityGateResult:
    passed: bool
    reason: Optional[str] = None
    metrics: Dict[str, Any] = None


def compute_laplacian_variance(gray_arr: np.ndarray) -> float:
    """Compute variance of the discrete 3x3 Laplacian operator for blur detection."""
    # Discrete 3x3 Laplacian kernel: [[0, 1, 0], [1, -4, 1], [0, 1, 0]]
    padded = np.pad(gray_arr, 1, mode="edge").astype(np.float32)
    laplacian = (
        padded[:-2, 1:-1]
        + padded[2:, 1:-1]
        + padded[1:-1, :-2]
        + padded[1:-1, 2:]
        - 4.0 * padded[1:-1, 1:-1]
    )
    return float(np.var(laplacian))


def check_image_quality(
    image: Image.Image,
    min_dimension: int = 128,
    max_aspect_ratio: float = 2.0,
    min_laplacian_var: float = 25.0,
    min_mean_brightness: float = 20.0,
    max_mean_brightness: float = 240.0,
    min_contrast_std: float = 12.0,
) -> QualityGateResult:
    """Validate an input image against industrial quality criteria before ML inference."""
    width, height = image.size
    aspect_ratio = max(width / height, height / width)
    
    # 1. Dimension Check
    if min(width, height) < min_dimension:
        return QualityGateResult(
            passed=False,
            reason=f"Resolution too low ({width}x{height}); minimum dimension required is {min_dimension}px.",
            metrics={"width": width, "height": height, "aspect_ratio": aspect_ratio},
        )

    # 2. Aspect Ratio Check (Cast impellers are circular; extreme elongation indicates corruption/clipping)
    if aspect_ratio > max_aspect_ratio:
        return QualityGateResult(
            passed=False,
            reason=f"Extreme aspect ratio ({aspect_ratio:.2f}); maximum allowable ratio is {max_aspect_ratio}.",
            metrics={"width": width, "height": height, "aspect_ratio": aspect_ratio},
        )

    # Convert to grayscale numpy array for photometric and sharpness checks
    gray = image.convert("L")
    gray_arr = np.array(gray, dtype=np.uint8)

    mean_brightness = float(np.mean(gray_arr))
    contrast_std = float(np.std(gray_arr))
    laplacian_var = compute_laplacian_variance(gray_arr)

    metrics = {
        "width": width,
        "height": height,
        "aspect_ratio": aspect_ratio,
        "mean_brightness": mean_brightness,
        "contrast_std": contrast_std,
        "laplacian_variance": laplacian_var,
    }

    # 3. Brightness / Exposure Check
    if mean_brightness < min_mean_brightness:
        return QualityGateResult(
            passed=False,
            reason=f"Severely underexposed image (mean brightness {mean_brightness:.1f} < {min_mean_brightness}).",
            metrics=metrics,
        )
    if mean_brightness > max_mean_brightness:
        return QualityGateResult(
            passed=False,
            reason=f"Severely overexposed image (mean brightness {mean_brightness:.1f} > {max_mean_brightness}).",
            metrics=metrics,
        )

    # 4. Contrast Check
    if contrast_std < min_contrast_std:
        return QualityGateResult(
            passed=False,
            reason=f"Insufficient contrast (standard deviation {contrast_std:.1f} < {min_contrast_std}).",
            metrics=metrics,
        )

    # 5. Blur Detection Check
    if laplacian_var < min_laplacian_var:
        return QualityGateResult(
            passed=False,
            reason=f"Image out of focus or blurred (Laplacian variance {laplacian_var:.1f} < {min_laplacian_var}).",
            metrics=metrics,
        )

    return QualityGateResult(passed=True, reason=None, metrics=metrics)
