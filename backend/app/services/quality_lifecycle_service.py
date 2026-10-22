import uuid
from datetime import datetime, timezone, date
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, update, and_, or_, desc, func
from fastapi import status

from backend.app.core.errors import AppException
from backend.app.models.entities import (
    Review,
    Defect,
    Inspection,
    InspectionItem,
    ModelRun,
    Image,
    User,
)
from backend.app.services.aggregation_service import get_current_model_run_for_image
from backend.app.services.audit import log_audit_event
from backend.app.schemas.reviews import ReviewCreate, ReviewDecision
from backend.app.schemas.defects import DefectCategory, DefectSeverity, DefectStatus, DefectCreate, DefectUpdate


def generate_defect_number(db: Session) -> str:
    """Generate business identifier DEF-YYYYMMDD-XXXX."""
    today_str = date.today().strftime("%Y%m%d")
    prefix = f"DEF-{today_str}-"
    stmt = (
        select(func.count(Defect.id))
        .where(Defect.defect_number.like(f"{prefix}%"))
    )
    count = db.execute(stmt).scalar() or 0
    return f"{prefix}{count + 1:04d}"


def record_human_review(
    db: Session,
    payload: ReviewCreate,
    current_user: User,
) -> Tuple[Review, Optional[Defect]]:
    """Record a human inspector or Quality Manager verification decision on an inspection item."""
    # 1. Fetch InspectionItem and verify existence
    item = db.get(InspectionItem, payload.inspection_item_id)
    if not item:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="ITEM_NOT_FOUND",
            message=f"Inspection item '{payload.inspection_item_id}' not found.",
        )

    inspection = item.inspection
    if not inspection:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="INSPECTION_NOT_FOUND",
            message="Associated inspection not found.",
        )

    # Cannot review on CANCELLED inspections
    if inspection.status == "CANCELLED":
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="INSPECTION_CANCELLED",
            message="Cannot review items for a cancelled inspection.",
        )

    # Normalize decision
    decision_val = payload.decision.value
    if decision_val == "ADDITIONAL_EVIDENCE_REQUESTED":
        decision_val = "REQUEST_ADDITIONAL_EVIDENCE"

    # Validation: Notes required for DISPUTED and REQUEST_ADDITIONAL_EVIDENCE
    if decision_val in ("DISPUTED", "REQUEST_ADDITIONAL_EVIDENCE"):
        if not payload.notes or len(payload.notes.strip()) < 5:
            raise AppException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="NOTES_REQUIRED",
                message=f"Detailed notes (min 5 characters) required for decision '{decision_val}'.",
            )

    # 2. Gather active images for this inspection item
    active_images = sorted(
        [img for img in item.images if not img.is_superseded],
        key=lambda x: (x.created_at or datetime.min, x.id),
    )

    # 3. Locate applicable ModelRun
    model_run: Optional[ModelRun] = None
    if payload.model_run_id:
        model_run = db.get(ModelRun, payload.model_run_id)
        if not model_run:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="MODEL_RUN_NOT_FOUND",
                message=f"Model run '{payload.model_run_id}' not found.",
            )
        if model_run.image and model_run.image not in active_images and not model_run.image.is_superseded:
            active_images.append(model_run.image)

    # Build auditable evidence images list with model runs at review time
    evidence_images = []
    preferred_defective_run = None
    first_candidate_run = None

    for img in active_images:
        current_run = get_current_model_run_for_image(db, img.id)
        if current_run:
            if not first_candidate_run:
                first_candidate_run = current_run
            if current_run.routing_outcome == "LIKELY_DEFECTIVE" and not preferred_defective_run:
                preferred_defective_run = current_run

        evidence_images.append({
            "image_id": img.id,
            "sha256_hash": img.sha256_hash,
            "original_filename": img.original_filename,
            "image_scope": img.image_scope,
            "surface_location": img.surface_location,
            "represented_item_count": img.represented_item_count,
            "file_size_bytes": img.file_size_bytes,
            "mime_type": img.mime_type,
            "created_at": img.created_at.isoformat() if img.created_at else None,
            "model_run_id": current_run.id if current_run else None,
            "predicted_label": current_run.predicted_label if current_run else None,
            "score": float(current_run.score) if (current_run and current_run.score is not None) else None,
            "routing_outcome": current_run.routing_outcome if current_run else None,
        })

    if not model_run:
        model_run = preferred_defective_run or first_candidate_run

    # 4. Model Disagreement Detection
    model_disagreement = False
    if model_run and model_run.predicted_label:
        if model_run.predicted_label == "DEFECTIVE" and decision_val == "CONFIRMED_GOOD":
            model_disagreement = True
        elif model_run.predicted_label == "GOOD" and decision_val == "CONFIRMED_DEFECTIVE":
            model_disagreement = True

    # 5. Construct Immutable AI Snapshot (Rule 2)
    now_utc = datetime.now(timezone.utc)
    target_image: Optional[Image] = None
    if model_run and model_run.image:
        target_image = model_run.image
    elif active_images:
        target_image = active_images[0]

    ai_snapshot = {
        "model_run_id": model_run.id if model_run else None,
        "model_version": model_run.model_version.version_name if (model_run and model_run.model_version) else None,
        "model_architecture": model_run.model_version.model_architecture if (model_run and model_run.model_version) else None,
        "predicted_label": model_run.predicted_label if model_run else None,
        "score": float(model_run.score) if (model_run and model_run.score is not None) else None,
        "score_type": model_run.score_type if model_run else None,
        "threshold_applied": float(model_run.threshold_applied) if (model_run and model_run.threshold_applied is not None) else None,
        "routing_outcome": model_run.routing_outcome if model_run else None,
        "routing_reason": model_run.routing_reason if model_run else None,
        "image_id": target_image.id if target_image else None,
        "image_sha256": target_image.sha256_hash if target_image else None,
        "evidence_images": evidence_images,
        "images": evidence_images,
        "total_images": len(evidence_images),
        "reviewer_id": current_user.id,
        "reviewer_username": current_user.username,
        "review_timestamp": now_utc.isoformat(),
        "human_decision": decision_val,
        "human_explanation": payload.notes,
        "model_disagreement": model_disagreement,
    }

    # 5. Create Review Entity
    review = Review(
        inspection_id=inspection.id,
        inspection_item_id=item.id,
        model_run_id=model_run.id if model_run else None,
        reviewer_id=current_user.id,
        decision=decision_val,
        model_disagreement=model_disagreement,
        notes=payload.notes,
        ai_snapshot=ai_snapshot,
        created_at=now_utc,
    )
    db.add(review)
    db.flush()

    # 6. Defect Handling
    created_defect: Optional[Defect] = None
    if decision_val == "CONFIRMED_DEFECTIVE":
        if not payload.defect:
            raise AppException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="DEFECT_PAYLOAD_REQUIRED",
                message="Defect details (category, severity, description) required when confirming defective.",
            )

        # Validate Defect Category against approved taxonomy
        if payload.defect.category not in DefectCategory:
            raise AppException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="INVALID_DEFECT_CATEGORY",
                message=f"Category '{payload.defect.category}' is not in approved taxonomy.",
            )

        # Generate unique business ID
        defect_num = generate_defect_number(db)
        evidence_img_id = payload.defect.evidence_image_id or (target_image.id if target_image else None)

        created_defect = Defect(
            defect_number=defect_num,
            inspection_item_id=item.id,
            review_id=review.id,
            category=payload.defect.category.value,
            severity=payload.defect.severity.value,
            status="OPEN",
            surface_location=payload.defect.surface_location,
            description=payload.defect.description,
            evidence_image_id=evidence_img_id,
            prior_defect_id=payload.defect.prior_defect_id,
            created_at=now_utc,
            updated_at=now_utc,
        )
        db.add(created_defect)
        item.status = "CONFIRMED_DEFECTIVE"

    elif decision_val == "CONFIRMED_GOOD":
        if payload.defect:
            raise AppException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="INVALID_DEFECT_FOR_GOOD",
                message="Cannot create defect record when item is confirmed good.",
            )
        item.status = "CLEAR"

    elif decision_val == "DISPUTED":
        item.status = "DISPUTED"

    elif decision_val == "REQUEST_ADDITIONAL_EVIDENCE":
        item.status = "PENDING"

    # 7. Update Inspection Status: If in DRAFT or SUBMITTED, transition to IN_REVIEW
    if inspection.status in ("DRAFT", "SUBMITTED"):
        inspection.status = "IN_REVIEW"

    # Check if all items in inspection have been reviewed; if so, inspection is ready for completion
    all_reviewed = True
    for insp_item in inspection.items:
        if insp_item.id == item.id:
            continue
        item_reviews = db.query(Review).filter(Review.inspection_item_id == insp_item.id).count()
        if item_reviews == 0:
            all_reviewed = False
            break

    if all_reviewed and inspection.status == "IN_REVIEW":
        inspection.status = "COMPLETED"
        inspection.completed_at = now_utc

    # 8. Record Immutable Audit Event
    log_audit_event(
        db=db,
        action=f"REVIEW_{decision_val}",
        entity_type="reviews",
        entity_id=review.id,
        actor_id=current_user.id,
        previous_state={"item_id": item.id, "item_status": item.status},
        new_state={
            "decision": decision_val,
            "model_disagreement": model_disagreement,
            "defect_id": created_defect.id if created_defect else None,
            "inspection_status": inspection.status,
        },
    )

    db.commit()
    db.refresh(review)
    if created_defect:
        db.refresh(created_defect)

    return review, created_defect


def dispute_review(
    db: Session,
    review_id: str,
    notes: str,
    current_user: User,
) -> Review:
    """Escalate review verdict to Quality Management due to uncertainty or disagreement."""
    original_review = db.get(Review, review_id)
    if not original_review:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="REVIEW_NOT_FOUND",
            message=f"Review '{review_id}' not found.",
        )

    item = original_review.inspection_item
    now_utc = datetime.now(timezone.utc)

    # Append new revision record
    dispute_rev = Review(
        inspection_id=original_review.inspection_id,
        inspection_item_id=original_review.inspection_item_id,
        model_run_id=original_review.model_run_id,
        reviewer_id=current_user.id,
        decision="DISPUTED",
        model_disagreement=original_review.model_disagreement,
        notes=f"DISPUTE on Review {review_id}: {notes}",
        ai_snapshot=original_review.ai_snapshot,
        created_at=now_utc,
    )
    db.add(dispute_rev)
    item.status = "DISPUTED"

    log_audit_event(
        db=db,
        action="REVIEW_DISPUTED",
        entity_type="reviews",
        entity_id=dispute_rev.id,
        actor_id=current_user.id,
        previous_state={"original_review_id": review_id, "original_decision": original_review.decision},
        new_state={"decision": "DISPUTED", "notes": notes},
    )

    db.commit()
    db.refresh(dispute_rev)
    return dispute_rev


def adjudicate_review(
    db: Session,
    review_id: str,
    decision: ReviewDecision,
    notes: str,
    defect_payload: Optional[DefectCreate],
    current_user: User,
) -> Tuple[Review, Optional[Defect]]:
    """Quality Manager final adjudication of a disputed or escalated review."""
    original_review = db.get(Review, review_id)
    if not original_review:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="REVIEW_NOT_FOUND",
            message=f"Review '{review_id}' not found.",
        )

    # Only Quality Manager can adjudicate
    if current_user.role != "QUALITY_MANAGER":
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="INSUFFICIENT_PERMISSIONS",
            message="Only Quality Manager can adjudicate disputed reviews.",
        )

    decision_val = decision.value
    if decision_val not in ("CONFIRMED_GOOD", "CONFIRMED_DEFECTIVE"):
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="INVALID_ADJUDICATION_DECISION",
            message="Adjudication decision must be CONFIRMED_GOOD or CONFIRMED_DEFECTIVE.",
        )

    item = original_review.inspection_item
    now_utc = datetime.now(timezone.utc)

    # Calculate model disagreement
    model_run = original_review.model_run
    model_disagreement = False
    if model_run and model_run.predicted_label:
        if model_run.predicted_label == "DEFECTIVE" and decision_val == "CONFIRMED_GOOD":
            model_disagreement = True
        elif model_run.predicted_label == "GOOD" and decision_val == "CONFIRMED_DEFECTIVE":
            model_disagreement = True

    # Construct adjudication snapshot
    ai_snapshot = dict(original_review.ai_snapshot or {})
    ai_snapshot.update({
        "adjudicated_by": current_user.id,
        "adjudication_timestamp": now_utc.isoformat(),
        "adjudication_decision": decision_val,
        "adjudication_notes": notes,
        "prior_review_id": review_id,
    })

    adjudicated_review = Review(
        inspection_id=original_review.inspection_id,
        inspection_item_id=original_review.inspection_item_id,
        model_run_id=original_review.model_run_id,
        reviewer_id=current_user.id,
        decision=decision_val,
        model_disagreement=model_disagreement,
        notes=f"QM ADJUDICATION: {notes}",
        ai_snapshot=ai_snapshot,
        created_at=now_utc,
    )
    db.add(adjudicated_review)
    db.flush()

    created_defect: Optional[Defect] = None
    if decision_val == "CONFIRMED_DEFECTIVE":
        if not defect_payload:
            raise AppException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="DEFECT_PAYLOAD_REQUIRED",
                message="Defect details required when adjudicating defective.",
            )
        defect_num = generate_defect_number(db)
        created_defect = Defect(
            defect_number=defect_num,
            inspection_item_id=item.id,
            review_id=adjudicated_review.id,
            category=defect_payload.category.value,
            severity=defect_payload.severity.value,
            status="OPEN",
            surface_location=defect_payload.surface_location,
            description=defect_payload.description,
            evidence_image_id=defect_payload.evidence_image_id,
            prior_defect_id=defect_payload.prior_defect_id,
            created_at=now_utc,
            updated_at=now_utc,
        )
        db.add(created_defect)
        item.status = "CONFIRMED_DEFECTIVE"
    else:
        item.status = "CLEAR"

    log_audit_event(
        db=db,
        action="DISPUTE_ADJUDICATED",
        entity_type="reviews",
        entity_id=adjudicated_review.id,
        actor_id=current_user.id,
        previous_state={"disputed_review_id": review_id, "previous_decision": original_review.decision},
        new_state={"adjudication_decision": decision_val, "notes": notes},
    )

    db.commit()
    db.refresh(adjudicated_review)
    if created_defect:
        db.refresh(created_defect)

    return adjudicated_review, created_defect


def update_defect(
    db: Session,
    defect_id: str,
    payload: DefectUpdate,
    current_user: User,
) -> Defect:
    """Update defect severity, location, or description with concurrency check."""
    defect = db.get(Defect, defect_id)
    if not defect:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DEFECT_NOT_FOUND",
            message=f"Defect '{defect_id}' not found.",
        )

    # Permission check: Inspector can only edit OPEN defects; Quality Manager can edit any non-resolved
    if current_user.role == "INSPECTOR" and defect.status != "OPEN":
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="INSUFFICIENT_PERMISSIONS",
            message="Inspectors can only update OPEN defects.",
        )

    if defect.status == "RESOLVED":
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="DEFECT_RESOLVED",
            message="Cannot modify a RESOLVED defect. Reopen it first.",
        )

    prev_state = {
        "severity": defect.severity,
        "surface_location": defect.surface_location,
        "description": defect.description,
    }

    now_utc = datetime.now(timezone.utc)
    if payload.severity is not None:
        defect.severity = payload.severity.value
    if payload.surface_location is not None:
        defect.surface_location = payload.surface_location
    if payload.description is not None:
        defect.description = payload.description

    defect.updated_at = now_utc

    log_audit_event(
        db=db,
        action="DEFECT_UPDATED",
        entity_type="defects",
        entity_id=defect.id,
        actor_id=current_user.id,
        previous_state=prev_state,
        new_state={
            "severity": defect.severity,
            "surface_location": defect.surface_location,
            "description": defect.description,
        },
    )

    db.commit()
    db.refresh(defect)
    return defect


def resolve_defect(
    db: Session,
    defect_id: str,
    resolution_notes: str,
    current_user: User,
) -> Defect:
    """Resolve a defect with Four-Eyes separation-of-duty enforcement and atomic concurrency."""
    # 1. Permission check: Only Quality Manager can resolve defects
    if current_user.role != "QUALITY_MANAGER":
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="INSUFFICIENT_PERMISSIONS",
            message="Only Quality Managers can mark defects as RESOLVED.",
        )

    defect = db.get(Defect, defect_id)
    if not defect:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DEFECT_NOT_FOUND",
            message=f"Defect '{defect_id}' not found.",
        )

    # 2. Four-Eyes Separation-of-Duty Rule (Rule 6):
    # The person who performed the human review cannot independently approve closure of their own review-created defect.
    if defect.review and defect.review.reviewer_id == current_user.id:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FOUR_EYES_VIOLATION",
            message="Separation of duties violation: The reviewer who logged the defect cannot approve its closure. An independent Quality Manager must sign off.",
        )

    if defect.status == "RESOLVED":
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="ALREADY_RESOLVED",
            message="Defect is already in RESOLVED state.",
        )

    now_utc = datetime.now(timezone.utc)
    old_status = defect.status

    # 3. Atomic conditional update (concurrency protection Rule 5)
    stmt = (
        update(Defect)
        .where(Defect.id == defect_id, Defect.status != "RESOLVED")
        .values(
            status="RESOLVED",
            resolved_by=current_user.id,
            resolved_at=now_utc,
            resolution_notes=resolution_notes,
            updated_at=now_utc,
        )
    )
    res = db.execute(stmt)
    if res.rowcount == 0:
        db.rollback()
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="CONCURRENT_MODIFICATION",
            message="Defect was concurrently modified or already resolved.",
        )

    # Check if inspection item has remaining unclosed defects
    item = defect.inspection_item
    open_defects_count = (
        db.query(Defect)
        .filter(Defect.inspection_item_id == item.id, Defect.id != defect.id, Defect.status != "RESOLVED")
        .count()
    )
    if open_defects_count == 0:
        item.status = "CLEAR"

    log_audit_event(
        db=db,
        action="DEFECT_RESOLVED",
        entity_type="defects",
        entity_id=defect.id,
        actor_id=current_user.id,
        previous_state={"status": old_status},
        new_state={
            "status": "RESOLVED",
            "resolved_by": current_user.id,
            "resolution_notes": resolution_notes,
            "item_status": item.status,
        },
    )

    db.commit()
    db.refresh(defect)
    return defect


def reopen_defect(
    db: Session,
    defect_id: str,
    reopen_notes: str,
    current_user: User,
) -> Defect:
    """Reopen a resolved or pending reinspection defect with atomic concurrency check."""
    defect = db.get(Defect, defect_id)
    if not defect:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DEFECT_NOT_FOUND",
            message=f"Defect '{defect_id}' not found.",
        )

    if defect.status not in ("RESOLVED", "PENDING_REINSPECTION"):
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="INVALID_STATE_FOR_REOPEN",
            message=f"Cannot reopen defect from status '{defect.status}'. Must be RESOLVED or PENDING_REINSPECTION.",
        )

    now_utc = datetime.now(timezone.utc)
    old_status = defect.status

    # Atomic conditional update
    stmt = (
        update(Defect)
        .where(Defect.id == defect_id, Defect.status.in_(["RESOLVED", "PENDING_REINSPECTION"]))
        .values(
            status="REOPENED",
            resolution_notes=f"REOPENED by {current_user.username}: {reopen_notes} (Previous notes: {defect.resolution_notes or ''})",
            updated_at=now_utc,
        )
    )
    res = db.execute(stmt)
    if res.rowcount == 0:
        db.rollback()
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="CONCURRENT_MODIFICATION",
            message="Defect status was changed concurrently.",
        )

    # Set item status back to CONFIRMED_DEFECTIVE
    item = defect.inspection_item
    item.status = "CONFIRMED_DEFECTIVE"

    log_audit_event(
        db=db,
        action="DEFECT_REOPENED",
        entity_type="defects",
        entity_id=defect.id,
        actor_id=current_user.id,
        previous_state={"status": old_status},
        new_state={"status": "REOPENED", "reopen_notes": reopen_notes},
    )

    db.commit()
    db.refresh(defect)
    return defect
