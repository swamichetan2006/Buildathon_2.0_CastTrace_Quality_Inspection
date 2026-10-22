from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from backend.app.models.entities import InspectionItem, Image, ModelRun

def get_current_model_run_for_image(db: Session, image_id: str) -> Optional[ModelRun]:
    """Retrieve the current model run attempt for an image (highest attempt number of the latest logical request)."""
    # 1. Find latest logical_run_id for this image
    stmt = (
        select(ModelRun.logical_run_id)
        .where(ModelRun.image_id == image_id)
        .order_by(desc(ModelRun.created_at))
        .limit(1)
    )
    latest_logical_id = db.execute(stmt).scalars().first()
    if not latest_logical_id:
        return None

    # 2. Get highest attempt number for this logical run
    stmt_attempt = (
        select(ModelRun)
        .where(ModelRun.image_id == image_id, ModelRun.logical_run_id == latest_logical_id)
        .order_by(desc(ModelRun.attempt_number))
        .limit(1)
    )
    return db.execute(stmt_attempt).scalars().first()


def derive_item_level_routing(db: Session, item_id: str) -> Dict[str, Any]:
    """Derive the item-level routing outcome across all non-superseded current images.
    
    Rules (docs/state-machines.md & Stage 13):
    1. If any usable image has current outcome LIKELY_DEFECTIVE => derive LIKELY_DEFECTIVE.
    2. Otherwise, if any required image is NEEDS_REVIEW, failed, processing, queued,
       missing result, or failed safeguard => derive NEEDS_REVIEW.
    3. Derive LIKELY_OK only when EVERY required current image has a successful result routed LIKELY_OK.
    4. If an item has both LIKELY_DEFECTIVE and another review-required/failed image,
       preserve derived outcome LIKELY_DEFECTIVE but flag additional_review_required = True.
    """
    item = db.get(InspectionItem, item_id)
    if not item:
        raise ValueError(f"Inspection item {item_id} not found")

    # Get non-superseded images linked to this item
    images_stmt = (
        select(Image)
        .where(Image.inspection_item_id == item_id, Image.is_superseded == False)
        .order_by(Image.created_at)
    )
    images = list(db.execute(images_stmt).scalars().all())

    if not images:
        return {
            "inspection_item_id": item_id,
            "derived_routing_outcome": "NEEDS_REVIEW",
            "derived_reason": "No active images uploaded for inspection item",
            "total_images": 0,
            "has_defective_flag": False,
            "has_review_or_incomplete_flag": True,
            "additional_review_required": True,
            "image_details": [],
        }

    image_summaries = []
    has_defective = False
    has_review_or_incomplete = False

    for img in images:
        run = get_current_model_run_for_image(db, img.id)
        if not run:
            status = "MISSING_RUN"
            outcome = "NEEDS_REVIEW"
            has_review_or_incomplete = True
        elif run.status in ("QUEUED", "PROCESSING"):
            status = run.status
            outcome = "NEEDS_REVIEW"
            has_review_or_incomplete = True
        elif run.status == "FAILED":
            status = "FAILED"
            outcome = "NEEDS_REVIEW"
            has_review_or_incomplete = True
        elif run.status == "SUCCEEDED":
            status = "SUCCEEDED"
            outcome = run.routing_outcome or "NEEDS_REVIEW"
            if outcome == "LIKELY_DEFECTIVE":
                has_defective = True
            elif outcome == "NEEDS_REVIEW":
                has_review_or_incomplete = True
        else:
            status = run.status
            outcome = "NEEDS_REVIEW"
            has_review_or_incomplete = True

        image_summaries.append({
            "image_id": img.id,
            "original_filename": img.original_filename,
            "image_scope": img.image_scope,
            "represented_item_count": img.represented_item_count,
            "run_id": run.id if run else None,
            "run_status": status,
            "routing_outcome": outcome,
            "score": float(run.score) if run and run.score is not None else None,
        })

    # Apply precedence rules
    if has_defective:
        derived_outcome = "LIKELY_DEFECTIVE"
        additional_review = has_review_or_incomplete
        reason = "Defect detected in one or more item images"
        if additional_review:
            reason += " (additional images require manual inspection review)"
    elif has_review_or_incomplete:
        derived_outcome = "NEEDS_REVIEW"
        additional_review = True
        reason = "One or more images are borderline, failing safeguards, processing, or failed"
    else:
        derived_outcome = "LIKELY_OK"
        additional_review = False
        reason = "All required item images triaged conforming with high confidence"

    return {
        "inspection_item_id": item_id,
        "derived_routing_outcome": derived_outcome,
        "derived_reason": reason,
        "total_images": len(images),
        "has_defective_flag": has_defective,
        "has_review_or_incomplete_flag": has_review_or_incomplete,
        "additional_review_required": additional_review,
        "image_details": image_summaries,
    }
