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
    CorrectiveAction,
    Reinspection,
    Inspection,
    InspectionItem,
    ModelRun,
    Image,
    User,
)
from backend.app.services.aggregation_service import get_current_model_run_for_image
from backend.app.services.audit import log_audit_event
from backend.app.schemas.reviews import ReviewCreate, ReviewDecision
from backend.app.schemas.defects import (
    DefectCategory,
    DefectSeverity,
    DefectStatus,
    DefectCreate,
    DefectUpdate,
    DefectResponse,
    DefectRecurrenceHistoryResponse,
)
from backend.app.schemas.corrective_actions import (
    CorrectiveActionCreate,
    CorrectiveActionUpdate,
    VerificationDecision,
    ActionType,
    ActionStatus,
)
from backend.app.schemas.reinspections import (
    ReinspectionCreate,
    ReinspectionOutcome,
)


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


def generate_action_number(db: Session) -> str:
    """Generate business identifier CAPA-YYYYMMDD-XXXX."""
    today_str = date.today().strftime("%Y%m%d")
    prefix = f"CAPA-{today_str}-"
    stmt = (
        select(func.count(CorrectiveAction.id))
        .where(CorrectiveAction.action_number.like(f"{prefix}%"))
    )
    count = db.execute(stmt).scalar() or 0
    return f"{prefix}{count + 1:04d}"


def validate_and_resolve_recurrence(
    db: Session,
    prior_defect_id: Optional[str],
    current_defect_id: Optional[str] = None,
    prior_corrective_action_id: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Validate prior defect and recurrence relationships, preventing self-links and cycles."""
    if not prior_defect_id:
        if prior_corrective_action_id:
            capa = db.get(CorrectiveAction, prior_corrective_action_id)
            if not capa:
                raise AppException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="CORRECTIVE_ACTION_NOT_FOUND",
                    message=f"Referenced prior corrective action '{prior_corrective_action_id}' not found.",
                )
        return None, prior_corrective_action_id

    # Self-link check
    if current_defect_id and prior_defect_id == current_defect_id:
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="SELF_RECURRENCE_PROHIBITED",
            message="A defect cannot reference itself as a prior defect.",
        )

    prior = db.get(Defect, prior_defect_id)
    if not prior:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="PRIOR_DEFECT_NOT_FOUND",
            message=f"Prior defect with ID '{prior_defect_id}' was not found.",
        )

    # Cycle detection
    visited = {prior.id}
    curr = prior
    while curr.prior_defect_id:
        if current_defect_id and curr.prior_defect_id == current_defect_id:
            raise AppException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="CYCLIC_RECURRENCE_DETECTED",
                message="Cyclic recurrence relationship detected in defect lineage.",
            )
        if curr.prior_defect_id in visited:
            raise AppException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="CYCLIC_RECURRENCE_DETECTED",
                message="Cyclic recurrence loop detected in prior defect chain.",
            )
        visited.add(curr.prior_defect_id)
        curr = db.get(Defect, curr.prior_defect_id)
        if not curr:
            break

    resolved_capa_id = prior_corrective_action_id
    if resolved_capa_id:
        capa = db.get(CorrectiveAction, resolved_capa_id)
        if not capa:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="CORRECTIVE_ACTION_NOT_FOUND",
                message=f"Referenced prior corrective action '{resolved_capa_id}' not found.",
            )
    else:
        # Auto-associate latest corrective action from prior defect if one exists
        latest_capa = (
            db.query(CorrectiveAction)
            .filter(CorrectiveAction.defect_id == prior.id)
            .order_by(desc(CorrectiveAction.created_at))
            .first()
        )
        if latest_capa:
            resolved_capa_id = latest_capa.id

    return prior.id, resolved_capa_id


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
        # Validate recurrence links if provided
        prior_def_id, prior_capa_id = validate_and_resolve_recurrence(
            db=db,
            prior_defect_id=payload.defect.prior_defect_id,
            prior_corrective_action_id=payload.defect.prior_corrective_action_id,
        )

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
            prior_defect_id=prior_def_id,
            prior_corrective_action_id=prior_capa_id,
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
        prior_def_id, prior_capa_id = validate_and_resolve_recurrence(
            db=db,
            prior_defect_id=defect_payload.prior_defect_id,
            prior_corrective_action_id=defect_payload.prior_corrective_action_id,
        )
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
            prior_defect_id=prior_def_id,
            prior_corrective_action_id=prior_capa_id,
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


# =====================================================================
# PHASE 4B: CAPA, INDEPENDENT VERIFICATION & REINSPECTION WORKFLOW
# =====================================================================

def create_corrective_action(
    db: Session,
    payload: CorrectiveActionCreate,
    current_user: User,
) -> CorrectiveAction:
    """Assign a CAPA remediation task for an open or reopened defect."""
    # 1. Authorization: SUPERVISOR or QUALITY_MANAGER
    if current_user.role not in ("SUPERVISOR", "QUALITY_MANAGER"):
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="INSUFFICIENT_PERMISSIONS",
            message="Only Supervisors and Quality Managers can create and assign corrective actions.",
        )

    # 2. Validate due_date
    if payload.due_date < date.today():
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="PAST_DUE_DATE",
            message="due_date must be today or in the future.",
        )

    # 3. Locate and validate defect
    defect = db.get(Defect, payload.defect_id)
    if not defect:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DEFECT_NOT_FOUND",
            message=f"Defect '{payload.defect_id}' not found.",
        )

    if defect.status == "RESOLVED":
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="INVALID_STATE_TRANSITION",
            message="Cannot assign a corrective action to an already resolved defect.",
        )

    # 4. Check for existing active action on this defect
    active_capa = (
        db.query(CorrectiveAction)
        .filter(
            CorrectiveAction.defect_id == defect.id,
            CorrectiveAction.status.in_(["OPEN", "IN_PROGRESS"]),
        )
        .first()
    )
    if active_capa:
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="ACTIVE_ACTION_EXISTS",
            message=f"An active corrective action '{active_capa.action_number}' is already in progress for this defect.",
        )

    # 5. Validate assignee
    assignee = db.get(User, payload.assigned_to)
    if not assignee or not assignee.is_active:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="ASSIGNEE_NOT_FOUND",
            message=f"Assigned user '{payload.assigned_to}' not found or inactive.",
        )

    now_utc = datetime.now(timezone.utc)
    action_num = generate_action_number(db)
    action = CorrectiveAction(
        id=str(uuid.uuid4()),
        action_number=action_num,
        defect_id=defect.id,
        title=payload.title,
        action_type=payload.action_type.value,
        description=payload.description,
        assigned_to=assignee.id,
        assigned_by=current_user.id,
        status="OPEN",
        due_date=payload.due_date,
        root_cause=payload.root_cause,
        preventive_action=payload.preventive_action,
        verification_status="PENDING",
        verification_history=[],
        created_at=now_utc,
        updated_at=now_utc,
    )
    db.add(action)
    db.flush()

    old_defect_status = defect.status
    defect.status = "ACTION_ASSIGNED"
    defect.updated_at = now_utc

    log_audit_event(
        db=db,
        action="ACTION_CREATED",
        entity_type="corrective_actions",
        entity_id=action.id,
        actor_id=current_user.id,
        previous_state=None,
        new_state={
            "action_number": action_num,
            "defect_id": defect.id,
            "title": action.title,
            "action_type": action.action_type,
            "assigned_to": assignee.username,
            "due_date": str(payload.due_date),
            "status": "OPEN",
        },
    )

    log_audit_event(
        db=db,
        action="DEFECT_ACTION_ASSIGNED",
        entity_type="defects",
        entity_id=defect.id,
        actor_id=current_user.id,
        previous_state={"status": old_defect_status},
        new_state={"status": "ACTION_ASSIGNED", "action_number": action_num},
    )

    db.commit()
    db.refresh(action)
    return action


def start_corrective_action(
    db: Session,
    action_id: str,
    current_user: User,
) -> CorrectiveAction:
    """Acknowledge and transition an action from OPEN to IN_PROGRESS."""
    action = db.get(CorrectiveAction, action_id)
    if not action:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="ACTION_NOT_FOUND",
            message=f"Corrective action '{action_id}' not found.",
        )

    # Assignee, Supervisor, or Quality Manager can start work
    if current_user.role not in ("SUPERVISOR", "QUALITY_MANAGER") and action.assigned_to != current_user.id:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="INSUFFICIENT_PERMISSIONS",
            message="Only the assigned implementer, Supervisor, or Quality Manager can start this action.",
        )

    if action.status != "OPEN":
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="INVALID_STATE_TRANSITION",
            message=f"Cannot start corrective action in status '{action.status}'. Must be 'OPEN'.",
        )

    now_utc = datetime.now(timezone.utc)
    stmt = (
        update(CorrectiveAction)
        .where(CorrectiveAction.id == action_id, CorrectiveAction.status == "OPEN")
        .values(status="IN_PROGRESS", updated_at=now_utc)
    )
    res = db.execute(stmt)
    if res.rowcount == 0:
        db.rollback()
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="CONCURRENT_MODIFICATION",
            message="Corrective action status was modified concurrently.",
        )

    if action.defect and action.defect.status == "ACTION_ASSIGNED":
        action.defect.status = "IN_PROGRESS"
        action.defect.updated_at = now_utc

    log_audit_event(
        db=db,
        action="ACTION_STARTED",
        entity_type="corrective_actions",
        entity_id=action.id,
        actor_id=current_user.id,
        previous_state={"status": "OPEN"},
        new_state={"status": "IN_PROGRESS"},
    )

    log_audit_event(
        db=db,
        action="DEFECT_REMEDIATION_STARTED",
        entity_type="defects",
        entity_id=action.defect_id,
        actor_id=current_user.id,
        previous_state={"status": "ACTION_ASSIGNED"},
        new_state={"status": "IN_PROGRESS"},
    )

    db.commit()
    db.refresh(action)
    return action


def update_corrective_action(
    db: Session,
    action_id: str,
    payload: CorrectiveActionUpdate,
    current_user: User,
) -> CorrectiveAction:
    """Update progress, description, root cause, or due date for an active action."""
    action = db.get(CorrectiveAction, action_id)
    if not action:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="ACTION_NOT_FOUND",
            message=f"Corrective action '{action_id}' not found.",
        )

    if current_user.role not in ("SUPERVISOR", "QUALITY_MANAGER") and action.assigned_to != current_user.id:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="INSUFFICIENT_PERMISSIONS",
            message="Only the assigned implementer, Supervisor, or Quality Manager can update this action.",
        )

    if action.status in ("COMPLETED", "CANCELLED"):
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="ACTION_CLOSED",
            message=f"Cannot update a corrective action in '{action.status}' state.",
        )

    if payload.due_date and payload.due_date < date.today():
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="PAST_DUE_DATE",
            message="due_date must be today or in the future.",
        )

    old_state = {
        "title": action.title,
        "description": action.description,
        "due_date": str(action.due_date),
        "root_cause": action.root_cause,
        "preventive_action": action.preventive_action,
    }

    if payload.title is not None:
        action.title = payload.title
    if payload.action_type is not None:
        action.action_type = payload.action_type.value
    if payload.description is not None:
        action.description = payload.description
    if payload.due_date is not None:
        action.due_date = payload.due_date
    if payload.root_cause is not None:
        action.root_cause = payload.root_cause
    if payload.preventive_action is not None:
        action.preventive_action = payload.preventive_action

    now_utc = datetime.now(timezone.utc)
    action.updated_at = now_utc

    log_audit_event(
        db=db,
        action="ACTION_UPDATED",
        entity_type="corrective_actions",
        entity_id=action.id,
        actor_id=current_user.id,
        previous_state=old_state,
        new_state={
            "title": action.title,
            "description": action.description,
            "due_date": str(action.due_date),
            "root_cause": action.root_cause,
            "preventive_action": action.preventive_action,
        },
    )

    db.commit()
    db.refresh(action)
    return action


def complete_corrective_action(
    db: Session,
    action_id: str,
    completion_notes: str,
    completion_evidence_image_id: Optional[str],
    current_user: User,
) -> CorrectiveAction:
    """Document completed remediation work and mark action COMPLETED; transitions defect to PENDING_REINSPECTION."""
    action = db.get(CorrectiveAction, action_id)
    if not action:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="ACTION_NOT_FOUND",
            message=f"Corrective action '{action_id}' not found.",
        )

    if current_user.role not in ("SUPERVISOR", "QUALITY_MANAGER") and action.assigned_to != current_user.id:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="INSUFFICIENT_PERMISSIONS",
            message="Only the assigned implementer, Supervisor, or Quality Manager can complete this action.",
        )

    if not completion_notes or len(completion_notes.strip()) < 10:
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="NOTES_TOO_SHORT",
            message="completion_notes must describe the remediation work in at least 10 characters.",
        )

    if action.status not in ("OPEN", "IN_PROGRESS"):
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="INVALID_STATE_TRANSITION",
            message=f"Cannot complete corrective action in status '{action.status}'. Must be OPEN or IN_PROGRESS.",
        )

    if completion_evidence_image_id:
        img = db.get(Image, completion_evidence_image_id)
        if not img:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="IMAGE_NOT_FOUND",
                message=f"Completion evidence image '{completion_evidence_image_id}' not found.",
            )

    now_utc = datetime.now(timezone.utc)
    stmt = (
        update(CorrectiveAction)
        .where(
            CorrectiveAction.id == action_id,
            CorrectiveAction.status.in_(["OPEN", "IN_PROGRESS"]),
        )
        .values(
            status="COMPLETED",
            completed_at=now_utc,
            completion_notes=completion_notes,
            completion_evidence_image_id=completion_evidence_image_id,
            verification_status="PENDING",
            updated_at=now_utc,
        )
    )
    res = db.execute(stmt)
    if res.rowcount == 0:
        db.rollback()
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="CONCURRENT_MODIFICATION",
            message="Corrective action was completed concurrently.",
        )

    old_defect_status = action.defect.status
    action.defect.status = "PENDING_REINSPECTION"
    action.defect.updated_at = now_utc

    log_audit_event(
        db=db,
        action="ACTION_COMPLETED",
        entity_type="corrective_actions",
        entity_id=action.id,
        actor_id=current_user.id,
        previous_state={"status": action.status},
        new_state={
            "status": "COMPLETED",
            "completion_notes": completion_notes,
            "completed_at": now_utc.isoformat(),
        },
    )

    log_audit_event(
        db=db,
        action="DEFECT_REMEDIATION_COMPLETED",
        entity_type="defects",
        entity_id=action.defect_id,
        actor_id=current_user.id,
        previous_state={"status": old_defect_status},
        new_state={"status": "PENDING_REINSPECTION", "action_id": action.id},
    )

    db.commit()
    db.refresh(action)
    return action


def cancel_corrective_action(
    db: Session,
    action_id: str,
    reason: str,
    current_user: User,
) -> CorrectiveAction:
    """Cancel a corrective action (Quality Manager only)."""
    if current_user.role != "QUALITY_MANAGER":
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="INSUFFICIENT_PERMISSIONS",
            message="Only Quality Managers can cancel corrective actions.",
        )

    action = db.get(CorrectiveAction, action_id)
    if not action:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="ACTION_NOT_FOUND",
            message=f"Corrective action '{action_id}' not found.",
        )

    if action.status not in ("OPEN", "IN_PROGRESS"):
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="INVALID_STATE_TRANSITION",
            message=f"Cannot cancel corrective action in status '{action.status}'. Must be OPEN or IN_PROGRESS.",
        )

    if not reason or len(reason.strip()) < 5:
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="REASON_REQUIRED",
            message="A detailed reason (min 5 characters) is required to cancel a corrective action.",
        )

    now_utc = datetime.now(timezone.utc)
    stmt = (
        update(CorrectiveAction)
        .where(
            CorrectiveAction.id == action_id,
            CorrectiveAction.status.in_(["OPEN", "IN_PROGRESS"]),
        )
        .values(
            status="CANCELLED",
            verification_status="CANCELLED",
            rejection_reason=f"CANCELLED: {reason}",
            updated_at=now_utc,
        )
    )
    res = db.execute(stmt)
    if res.rowcount == 0:
        db.rollback()
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="CONCURRENT_MODIFICATION",
            message="Corrective action was modified concurrently.",
        )

    # If defect has no other active actions, return defect to OPEN or REOPENED
    defect = action.defect
    remaining_active = (
        db.query(CorrectiveAction)
        .filter(
            CorrectiveAction.defect_id == defect.id,
            CorrectiveAction.id != action.id,
            CorrectiveAction.status.in_(["OPEN", "IN_PROGRESS"]),
        )
        .count()
    )
    if remaining_active == 0 and defect.status in ("ACTION_ASSIGNED", "IN_PROGRESS"):
        defect.status = "REOPENED" if defect.prior_defect_id else "OPEN"
        defect.updated_at = now_utc

    log_audit_event(
        db=db,
        action="ACTION_CANCELLED",
        entity_type="corrective_actions",
        entity_id=action.id,
        actor_id=current_user.id,
        previous_state={"status": action.status},
        new_state={"status": "CANCELLED", "reason": reason},
    )

    db.commit()
    db.refresh(action)
    return action


def verify_corrective_action(
    db: Session,
    action_id: str,
    decision: VerificationDecision,
    notes: str,
    rejection_reason: Optional[str],
    current_user: User,
) -> CorrectiveAction:
    """Independent verification of a completed CAPA with Four-Eyes separation-of-duty enforcement."""
    # 1. Permission: Inspector or Quality Manager only
    if current_user.role not in ("INSPECTOR", "QUALITY_MANAGER"):
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="INSUFFICIENT_PERMISSIONS",
            message="Only Inspectors and Quality Managers can verify corrective actions.",
        )

    action = db.get(CorrectiveAction, action_id)
    if not action:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="ACTION_NOT_FOUND",
            message=f"Corrective action '{action_id}' not found.",
        )

    # 2. Four-Eyes Separation-of-Duty Rule (Mandatory Rule 6):
    # The person who implements a CAPA must not independently verify their own implementation.
    if action.assigned_to == current_user.id:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FOUR_EYES_VIOLATION",
            message="Separation of duties violation: The person responsible for implementing a CAPA cannot independently verify their own work.",
        )

    if action.status != "COMPLETED":
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="ACTION_NOT_COMPLETED",
            message=f"Corrective action must be COMPLETED before verification. Current status is '{action.status}'.",
        )

    if not notes or len(notes.strip()) < 5:
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="NOTES_REQUIRED",
            message="Verification notes (min 5 characters) are required.",
        )

    now_utc = datetime.now(timezone.utc)
    history = list(action.verification_history or [])

    if decision == VerificationDecision.REJECTED:
        if not rejection_reason or len(rejection_reason.strip()) < 5:
            raise AppException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="REJECTION_REASON_REQUIRED",
                message="A detailed rejection explanation (min 5 characters) is required when rejecting verification.",
            )

        # Record failed attempt into immutable history
        attempt_record = {
            "attempt": len(history) + 1,
            "decision": "REJECTED",
            "verifier_id": current_user.id,
            "verifier_username": current_user.username,
            "verified_at": now_utc.isoformat(),
            "notes": notes,
            "rejection_reason": rejection_reason,
        }
        history.append(attempt_record)

        # Return action to IN_PROGRESS so implementer can perform remediation rework
        stmt = (
            update(CorrectiveAction)
            .where(CorrectiveAction.id == action_id, CorrectiveAction.status == "COMPLETED")
            .values(
                status="IN_PROGRESS",
                verification_status="REJECTED",
                rejection_reason=rejection_reason,
                verification_notes=notes,
                verification_history=history,
                updated_at=now_utc,
            )
        )
        res = db.execute(stmt)
        if res.rowcount == 0:
            db.rollback()
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="CONCURRENT_MODIFICATION",
                message="Action status was concurrently modified.",
            )

        # Defect returns from PENDING_REINSPECTION back to IN_PROGRESS
        if action.defect:
            action.defect.status = "IN_PROGRESS"
            action.defect.updated_at = now_utc

        log_audit_event(
            db=db,
            action="ACTION_VERIFICATION_REJECTED",
            entity_type="corrective_actions",
            entity_id=action.id,
            actor_id=current_user.id,
            previous_state={"verification_status": action.verification_status},
            new_state={
                "status": "IN_PROGRESS",
                "verification_status": "REJECTED",
                "rejection_reason": rejection_reason,
                "attempt": len(history),
            },
        )

    else:
        # APPROVED / VERIFIED
        attempt_record = {
            "attempt": len(history) + 1,
            "decision": "APPROVED",
            "verifier_id": current_user.id,
            "verifier_username": current_user.username,
            "verified_at": now_utc.isoformat(),
            "notes": notes,
        }
        history.append(attempt_record)

        stmt = (
            update(CorrectiveAction)
            .where(CorrectiveAction.id == action_id, CorrectiveAction.status == "COMPLETED")
            .values(
                verification_status="VERIFIED",
                verified_by=current_user.id,
                verified_at=now_utc,
                verification_notes=notes,
                rejection_reason=None,
                verification_history=history,
                updated_at=now_utc,
            )
        )
        res = db.execute(stmt)
        if res.rowcount == 0:
            db.rollback()
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="CONCURRENT_MODIFICATION",
                message="Action status was concurrently modified.",
            )

        log_audit_event(
            db=db,
            action="ACTION_VERIFIED",
            entity_type="corrective_actions",
            entity_id=action.id,
            actor_id=current_user.id,
            previous_state={"verification_status": action.verification_status},
            new_state={
                "verification_status": "VERIFIED",
                "verified_by": current_user.id,
                "attempt": len(history),
            },
        )

    db.commit()
    db.refresh(action)
    return action


def create_reinspection(
    db: Session,
    payload: ReinspectionCreate,
    current_user: User,
) -> Reinspection:
    """Conduct follow-up quality inspection after remediation, enforcing SoD-2 and updating defect/item state."""
    # 1. Role: INSPECTOR or QUALITY_MANAGER
    if current_user.role not in ("INSPECTOR", "QUALITY_MANAGER"):
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="INSUFFICIENT_PERMISSIONS",
            message="Only Inspectors and Quality Managers can conduct reinspections.",
        )

    defect = db.get(Defect, payload.defect_id)
    if not defect:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DEFECT_NOT_FOUND",
            message=f"Defect '{payload.defect_id}' not found.",
        )

    if defect.status != "PENDING_REINSPECTION":
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="INVALID_STATE_TRANSITION",
            message=f"Defect must be in 'PENDING_REINSPECTION' status to conduct reinspection. Current status is '{defect.status}'.",
        )

    action = db.get(CorrectiveAction, payload.corrective_action_id)
    if not action:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="ACTION_NOT_FOUND",
            message=f"Corrective action '{payload.corrective_action_id}' not found.",
        )

    if action.defect_id != defect.id:
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="CAPA_DEFECT_MISMATCH",
            message="The specified corrective action does not belong to this defect.",
        )

    if action.status != "COMPLETED":
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="ACTION_NOT_COMPLETED",
            message=f"Corrective action must be COMPLETED before conducting reinspection. Current status is '{action.status}'.",
        )

    # 2. Four-Eyes Separation-of-Duty Rule SoD-2 (permissions.md:91):
    # The user assigned to perform the corrective action CANNOT perform the subsequent reinspection on that same item.
    if action.assigned_to == current_user.id:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FOUR_EYES_VIOLATION",
            message="Separation of duties violation: The user assigned to implement the corrective action cannot perform the verification reinspection.",
        )

    if payload.evidence_image_id:
        img = db.get(Image, payload.evidence_image_id)
        if not img:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="IMAGE_NOT_FOUND",
                message=f"Reinspection evidence image '{payload.evidence_image_id}' not found.",
            )

    orig_insp_id = defect.inspection_item.inspection_id
    followup_insp_id = payload.followup_inspection_id or orig_insp_id
    followup_insp = db.get(Inspection, followup_insp_id)
    if not followup_insp:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="INSPECTION_NOT_FOUND",
            message=f"Follow-up inspection '{followup_insp_id}' not found.",
        )

    now_utc = datetime.now(timezone.utc)
    outcome_val = payload.outcome.value

    # 3. State Transitions & Concurrency Protection
    if outcome_val == "DEFECT_RESOLVED":
        stmt = (
            update(Defect)
            .where(Defect.id == defect.id, Defect.status == "PENDING_REINSPECTION")
            .values(
                status="RESOLVED",
                resolved_by=current_user.id,
                resolved_at=now_utc,
                resolution_notes=payload.notes,
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

        # Mark action verified
        action.verification_status = "VERIFIED"
        action.verified_by = current_user.id
        action.verified_at = now_utc
        action.verification_notes = payload.notes

        # If item has no remaining open defects, set status to CLEAR
        item = defect.inspection_item
        open_count = (
            db.query(Defect)
            .filter(
                Defect.inspection_item_id == item.id,
                Defect.id != defect.id,
                Defect.status != "RESOLVED",
            )
            .count()
        )
        if open_count == 0:
            item.status = "CLEAR"

        log_audit_event(
            db=db,
            action="DEFECT_RESOLVED",
            entity_type="defects",
            entity_id=defect.id,
            actor_id=current_user.id,
            previous_state={"status": "PENDING_REINSPECTION"},
            new_state={"status": "RESOLVED", "resolved_by": current_user.id, "resolution_notes": payload.notes},
        )

    else:
        # DEFECT_RECURRED_REOPENED
        stmt = (
            update(Defect)
            .where(Defect.id == defect.id, Defect.status == "PENDING_REINSPECTION")
            .values(
                status="REOPENED",
                resolution_notes=f"Reinspection revealed persistent/recurrent defect: {payload.notes or ''}",
                prior_corrective_action_id=action.id,
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

        action.verification_status = "REJECTED"
        action.rejection_reason = payload.notes
        defect.inspection_item.status = "CONFIRMED_DEFECTIVE"

        log_audit_event(
            db=db,
            action="DEFECT_REOPENED",
            entity_type="defects",
            entity_id=defect.id,
            actor_id=current_user.id,
            previous_state={"status": "PENDING_REINSPECTION"},
            new_state={"status": "REOPENED", "notes": payload.notes},
        )

    # 4. Create immutable Reinspection record
    reinspection = Reinspection(
        id=str(uuid.uuid4()),
        defect_id=defect.id,
        corrective_action_id=action.id,
        original_inspection_id=orig_insp_id,
        followup_inspection_id=followup_insp_id,
        outcome=outcome_val,
        notes=payload.notes,
        evidence_image_id=payload.evidence_image_id,
        verified_by=current_user.id,
        created_at=now_utc,
    )
    db.add(reinspection)
    db.flush()

    log_audit_event(
        db=db,
        action="REINSPECTION_RECORDED",
        entity_type="reinspections",
        entity_id=reinspection.id,
        actor_id=current_user.id,
        previous_state=None,
        new_state={
            "defect_id": defect.id,
            "corrective_action_id": action.id,
            "outcome": outcome_val,
            "notes": payload.notes,
        },
    )

    db.commit()
    db.refresh(reinspection)
    return reinspection


def sign_off_reinspection(
    db: Session,
    reinspection_id: str,
    notes: str,
    current_user: User,
) -> Reinspection:
    """Quality Manager sign off on verified defect fix (permissions.md:64)."""
    if current_user.role != "QUALITY_MANAGER":
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="INSUFFICIENT_PERMISSIONS",
            message="Only Quality Managers can sign off on verified reinspections.",
        )

    reinspection = db.get(Reinspection, reinspection_id)
    if not reinspection:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="REINSPECTION_NOT_FOUND",
            message=f"Reinspection '{reinspection_id}' not found.",
        )

    # Four-Eyes check: QM cannot be the person who implemented the remediation
    if reinspection.corrective_action and reinspection.corrective_action.assigned_to == current_user.id:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FOUR_EYES_VIOLATION",
            message="Separation of duties violation: The implementer of the remediation cannot sign off on the reinspection.",
        )

    now_utc = datetime.now(timezone.utc)
    old_notes = reinspection.notes or ""
    reinspection.notes = f"{old_notes} | QM SIGN-OFF ({current_user.username}): {notes}".strip(" | ")

    log_audit_event(
        db=db,
        action="REINSPECTION_SIGNED_OFF",
        entity_type="reinspections",
        entity_id=reinspection.id,
        actor_id=current_user.id,
        previous_state={"notes": old_notes},
        new_state={"notes": reinspection.notes, "signed_off_at": now_utc.isoformat()},
    )

    db.commit()
    db.refresh(reinspection)
    return reinspection


def get_defect_recurrence_history(
    db: Session,
    defect_id: str,
) -> DefectRecurrenceHistoryResponse:
    """Retrieve full recurrence lineage for a defect, traversing prior_defect_id links."""
    defect = db.get(Defect, defect_id)
    if not defect:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DEFECT_NOT_FOUND",
            message=f"Defect '{defect_id}' not found.",
        )

    chain: List[DefectResponse] = [DefectResponse.model_validate(defect)]
    visited = {defect.id}
    curr = defect

    while curr.prior_defect_id:
        prior = db.get(Defect, curr.prior_defect_id)
        if not prior or prior.id in visited:
            break
        visited.add(prior.id)
        chain.append(DefectResponse.model_validate(prior))
        curr = prior

    return DefectRecurrenceHistoryResponse(
        defect_id=defect.id,
        defect_number=defect.defect_number,
        category=defect.category,
        recurrence_chain=chain,
        depth=len(chain),
    )
