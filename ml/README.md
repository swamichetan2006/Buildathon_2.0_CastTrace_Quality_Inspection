# CastTrace ML Package

Shared machine learning package for CastTrace AI containing:
- Shared deterministic preprocessing transforms
- Input quality gate (blur, resolution, aspect ratio, extreme brightness/contrast)
- Unfamiliar-input out-of-distribution guard with persisted reference features
- Three-tier validation routing (`LIKELY_OK`, `NEEDS_REVIEW`, `LIKELY_DEFECTIVE`) with Wilson score confidence intervals
- PyTorch transfer learning model definitions
