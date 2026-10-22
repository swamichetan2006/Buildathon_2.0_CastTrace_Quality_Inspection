import json
import os
import hashlib
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.models.entities import ModelVersion

def get_file_sha256(filepath: str) -> str:
    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def register_approved_model_version(
    db: Session,
    metadata_path: str = "ml/artifacts/model_metadata.json",
    activate: bool = True
) -> ModelVersion:
    """Idempotently register or verify the approved model version in the database."""
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"Model metadata not found at {metadata_path}")

    with open(metadata_path, "r") as f:
        meta = json.load(f)

    version_name = meta.get("model_version", "v1.0.0-resnet18")
    architecture = meta.get("model_architecture", "ResNet-18")
    weights_file = meta.get("weights_file", "model_best.pt")
    weights_path = os.path.join("ml", "artifacts", weights_file)
    expected_weights_sha = meta.get("weights_sha256")
    guard_file = meta.get("guard_reference_file", "unfamiliar_guard_reference.json")
    guard_path = os.path.join("ml", "artifacts", guard_file)
    expected_guard_sha = meta.get("guard_reference_sha256")

    # Verify artifacts exist locally and match expected hashes if present
    if os.path.exists(weights_path) and expected_weights_sha:
        actual_weights_sha = get_file_sha256(weights_path)
        if actual_weights_sha != expected_weights_sha:
            raise ValueError(f"Weights hash mismatch: expected {expected_weights_sha}, got {actual_weights_sha}")

    if os.path.exists(guard_path) and expected_guard_sha:
        actual_guard_sha = get_file_sha256(guard_path)
        if actual_guard_sha != expected_guard_sha:
            raise ValueError(f"Guard hash mismatch: expected {expected_guard_sha}, got {actual_guard_sha}")

    # Build comprehensive dataset and configuration provenance
    training_info = {
        "dataset_source": meta.get("dataset_source", "casting_512x512"),
        "dataset_total_images": meta.get("dataset_total_images", 1300),
        "split_manifest_sha256": meta.get("split_manifest_sha256"),
        "class_mapping": meta.get("class_mapping", {"0": "GOOD", "1": "DEFECTIVE"}),
        "input_size": meta.get("input_size", [224, 224]),
        "preprocessing_parameters": meta.get("preprocessing_parameters"),
        "guard_threshold": meta.get("guard_threshold", 0.13709),
        "guard_reference_file": guard_path,
        "dataset_licence": meta.get("dataset_licence_review"),
        "provenance": meta.get("provenance"),
    }

    # Build evaluation and routing metrics
    metrics_info = {
        "score_semantics": "PROBABILITY_DEFECTIVE",
        "routing_thresholds": {
            "t_ok": 0.01,
            "t_def": 0.50,
            "decision_order": [
                "1. Quality gate (resolution, blur, exposure)",
                "2. Unfamiliar-input guard (OOD outlier check)",
                "3. Classifier score routing",
                "4. Final image-level triage outcome"
            ]
        },
        "validation_metrics": meta.get("validation_metrics"),
        "validation_routing": meta.get("validation_routing"),
        "held_out_test_evaluation": meta.get("held_out_test_evaluation"),
        "evaluation_report_file": "ml/artifacts/test_evaluation_report.json",
    }

    # Query existing version idempotently
    stmt = select(ModelVersion).where(ModelVersion.version_name == version_name)
    existing: Optional[ModelVersion] = db.execute(stmt).scalars().first()

    if existing:
        # Update existing record if needed
        existing.model_architecture = architecture
        existing.weights_path = weights_path
        existing.weights_sha256 = expected_weights_sha
        existing.unfamiliar_guard_sha256 = expected_guard_sha
        existing.training_dataset_info = training_info
        existing.metrics = metrics_info
        if activate:
            existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    # Create new model version record
    new_version = ModelVersion(
        version_name=version_name,
        model_architecture=architecture,
        weights_path=weights_path,
        weights_sha256=expected_weights_sha,
        unfamiliar_guard_sha256=expected_guard_sha,
        training_dataset_info=training_info,
        metrics=metrics_info,
        is_active=activate,
    )
    db.add(new_version)
    db.commit()
    db.refresh(new_version)
    return new_version
