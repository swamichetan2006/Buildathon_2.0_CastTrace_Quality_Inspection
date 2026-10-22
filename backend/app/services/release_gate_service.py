import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import update
from fastapi import status

from backend.app.core.errors import AppException
from backend.app.models.entities import (
    Batch,
    Inspection,
    InspectionItem,
    Image,
    ModelRun,
    Review,
    Defect,
    CorrectiveAction,
    Reinspection,
    BatchDecision,
    User,
)
from backend.app.schemas.batches import ReleaseBlocker
from backend.app.services.quality_lifecycle_service import log_audit_event


def evaluate_batch_release_gate(
    db: Session,
    batch_id: str,
    is_concession: bool = False,
    concession_justification: Optional[str] = None,
) -> Tuple[bool, str, List[ReleaseBlocker], Dict[str, Any], Dict[str, List[str]]]:
    """Centralized release-gate evaluation across inspections, items, images, inference, reviews, defects, CAPAs, and reinspections.

    Guarantees:
    - Counts distinct physical items, not photographs.
    - No duplicate joins inflate quality counts.
    - Full blocker evaluation with structured codes, messages, and entity references.
    """
    batch = db.get(Batch, batch_id)
    if not batch:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="BATCH_NOT_FOUND",
            message=f"Batch with ID '{batch_id}' was not found.",
        )

    blockers: List[ReleaseBlocker] = []

    # 1. Batch State Check (Section 3.F)
    if batch.status == "RELEASED":
        blockers.append(
            ReleaseBlocker(
                code="BATCH_ALREADY_RELEASED",
                message=f"Batch '{batch.batch_number}' is already in RELEASED status.",
                entity_type="batches",
                entity_id=batch.id,
            )
        )
    elif batch.status in ("ARCHIVED", "SCRAPPED"):
        blockers.append(
            ReleaseBlocker(
                code="BATCH_TERMINAL_STATE",
                message=f"Batch '{batch.batch_number}' is in terminal status '{batch.status}' and cannot be released.",
                entity_type="batches",
                entity_id=batch.id,
            )
        )

    # 2. Query Batch Inspections & Distinct Physical Items (Section 3.A)
    inspections = (
        db.query(Inspection)
        .filter(Inspection.batch_id == batch.id)
        .all()
    )

    if len(inspections) == 0 and batch.status in ("INSPECTION_PENDING", "UNDER_REVIEW"):
        blockers.append(
            ReleaseBlocker(
                code="NO_INSPECTIONS_RECORDED",
                message=f"Batch '{batch.batch_number}' is in '{batch.status}' but has zero inspection staging sessions.",
                entity_type="batches",
                entity_id=batch.id,
            )
        )

    for insp in inspections:
        if insp.status in ("DRAFT", "SUBMITTED"):
            blockers.append(
                ReleaseBlocker(
                    code="INSPECTION_NOT_COMPLETED",
                    message=f"Inspection '{insp.inspection_number}' is in status '{insp.status}' and has not been completed.",
                    entity_type="inspections",
                    entity_id=insp.id,
                )
            )
        if len(insp.items) == 0 and insp.status != "CANCELLED":
            blockers.append(
                ReleaseBlocker(
                    code="NO_INSPECTION_ITEMS_RECORDED",
                    message=f"Inspection '{insp.inspection_number}' has zero inspection items registered.",
                    entity_type="inspections",
                    entity_id=insp.id,
                )
            )

    items = (
        db.query(InspectionItem)
        .join(Inspection, InspectionItem.inspection_id == Inspection.id)
        .filter(Inspection.batch_id == batch.id)
        .all()
    )

    # 3. Item Level Evidence & Review Evaluation (Section 3.B & 3.C)
    reviewed_item_ids = set()
    pending_review_item_ids = set()

    for item in items:
        # Check photographic evidence
        item_images = (
            db.query(Image)
            .filter(Image.inspection_item_id == item.id, Image.is_superseded.is_(False))
            .all()
        )
        if len(item_images) == 0 and not (is_concession and concession_justification):
            blockers.append(
                ReleaseBlocker(
                    code="ITEM_EVIDENCE_MISSING",
                    message=f"Inspection item '{item.item_identifier}' has no associated non-superseded photographic evidence.",
                    entity_type="inspection_items",
                    entity_id=item.id,
                )
            )

        # Check human reviews
        item_reviews = (
            db.query(Review)
            .filter(Review.inspection_item_id == item.id)
            .order_by(Review.created_at.desc())
            .all()
        )
        if len(item_reviews) == 0:
            blockers.append(
                ReleaseBlocker(
                    code="REVIEW_MISSING",
                    message=f"Inspection item '{item.item_identifier}' has not been reviewed by a human inspector.",
                    entity_type="inspection_items",
                    entity_id=item.id,
                )
            )
            pending_review_item_ids.add(item.id)
        else:
            latest_review = item_reviews[0]
            if latest_review.decision == "DISPUTED":
                blockers.append(
                    ReleaseBlocker(
                        code="REVIEW_DISPUTED_UNRESOLVED",
                        message=f"Item '{item.item_identifier}' has an unresolved dispute requiring Quality Manager adjudication.",
                        entity_type="reviews",
                        entity_id=latest_review.id,
                    )
                )
                pending_review_item_ids.add(item.id)
            elif latest_review.decision == "REQUEST_ADDITIONAL_EVIDENCE" and item.status != "CLEAR":
                blockers.append(
                    ReleaseBlocker(
                        code="ADDITIONAL_EVIDENCE_PENDING",
                        message=f"Item '{item.item_identifier}' requires additional photographic evidence.",
                        entity_type="reviews",
                        entity_id=latest_review.id,
                    )
                )
                pending_review_item_ids.add(item.id)
            elif latest_review.decision in ("CONFIRMED_GOOD", "CONFIRMED_DEFECTIVE"):
                reviewed_item_ids.add(item.id)

        # Check item status
        if item.status != "CLEAR":
            # If not authorized under concession, or item is in preliminary/disputed status
            if not is_concession or item.status in ("PENDING", "AI_FLAGGED", "DISPUTED"):
                blockers.append(
                    ReleaseBlocker(
                        code="ITEM_NOT_CLEAR",
                        message=f"Inspection item '{item.item_identifier}' is in non-clear status '{item.status}'.",
                        entity_type="inspection_items",
                        entity_id=item.id,
                    )
                )

    # 4. Evidence & Inference Job Evaluation (Section 3.B)
    batch_images = (
        db.query(Image)
        .filter(Image.batch_id == batch.id, Image.is_superseded.is_(False))
        .all()
    )
    for img in batch_images:
        runs = (
            db.query(ModelRun)
            .filter(ModelRun.image_id == img.id)
            .order_by(ModelRun.attempt_number.desc())
            .all()
        )
        if runs:
            latest_run = runs[0]
            if latest_run.status in ("QUEUED", "PROCESSING"):
                blockers.append(
                    ReleaseBlocker(
                        code="INFERENCE_IN_PROGRESS",
                        message=f"Inference run '{latest_run.id}' for image '{img.id}' is still in progress ({latest_run.status}).",
                        entity_type="model_runs",
                        entity_id=latest_run.id,
                    )
                )
            elif latest_run.status == "FAILED":
                # Only a blocker if the item hasn't been reviewed by a human (degraded mode allows manual override)
                if img.inspection_item_id and img.inspection_item_id not in reviewed_item_ids:
                    blockers.append(
                        ReleaseBlocker(
                            code="INFERENCE_FAILED_UNRESOLVED",
                            message=f"Inference run for image '{img.id}' failed and item has not been resolved by human review.",
                            entity_type="model_runs",
                            entity_id=latest_run.id,
                        )
                    )

    # 5. Defects & Recurrence Evaluation (Section 3.D)
    defects = (
        db.query(Defect)
        .join(InspectionItem, Defect.inspection_item_id == InspectionItem.id)
        .join(Inspection, InspectionItem.inspection_id == Inspection.id)
        .filter(Inspection.batch_id == batch.id)
        .all()
    )

    unresolved_defects = []
    resolved_defects = []
    defects_requiring_reinspection = []

    for defect in defects:
        if defect.status in ("OPEN", "ACTION_ASSIGNED", "IN_PROGRESS", "PENDING_REINSPECTION", "REOPENED"):
            unresolved_defects.append(defect)
            if defect.status == "PENDING_REINSPECTION":
                defects_requiring_reinspection.append(defect)

            # Check if covered by authorized Quality Manager concession
            if not (is_concession and concession_justification):
                if defect.prior_defect_id or defect.prior_corrective_action_id:
                    blockers.append(
                        ReleaseBlocker(
                            code="UNRESOLVED_RECURRENT_DEFECT",
                            message=f"Recurring defect '{defect.defect_number}' ({defect.category}, {defect.severity}) is in status '{defect.status}'.",
                            entity_type="defects",
                            entity_id=defect.id,
                        )
                    )
                else:
                    blockers.append(
                        ReleaseBlocker(
                            code="UNRESOLVED_DEFECT",
                            message=f"Defect '{defect.defect_number}' ({defect.category}, {defect.severity}) is in status '{defect.status}'.",
                            entity_type="defects",
                            entity_id=defect.id,
                        )
                    )
        elif defect.status == "RESOLVED":
            resolved_defects.append(defect)
            if not defect.resolved_by or not defect.resolved_at:
                blockers.append(
                    ReleaseBlocker(
                        code="DEFECT_RESOLUTION_INVALID",
                        message=f"Defect '{defect.defect_number}' is marked RESOLVED but lacks verifier authorization metadata.",
                        entity_type="defects",
                        entity_id=defect.id,
                    )
                )

    # 6. CAPA & Reinspection Evaluation (Section 3.E)
    all_capas: List[CorrectiveAction] = []
    all_reinspections: List[Reinspection] = []

    capa_active_count = 0
    capa_pending_verification_count = 0
    capa_verified_count = 0

    reinspections_passed_count = 0
    reinspections_failed_count = 0

    for defect in defects:
        for action in defect.corrective_actions:
            all_capas.append(action)
            if action.status in ("OPEN", "IN_PROGRESS"):
                capa_active_count += 1
                blockers.append(
                    ReleaseBlocker(
                        code="CAPA_NOT_COMPLETED",
                        message=f"Corrective action '{action.action_number}' is still in status '{action.status}'.",
                        entity_type="corrective_actions",
                        entity_id=action.id,
                    )
                )
            elif action.status == "COMPLETED":
                if action.verification_status == "VERIFIED":
                    capa_verified_count += 1
                elif action.verification_status == "REJECTED":
                    capa_pending_verification_count += 1
                    blockers.append(
                        ReleaseBlocker(
                            code="CAPA_VERIFICATION_REJECTED",
                            message=f"Corrective action '{action.action_number}' verification was rejected and requires rework.",
                            entity_type="corrective_actions",
                            entity_id=action.id,
                        )
                    )
                else:
                    capa_pending_verification_count += 1
                    blockers.append(
                        ReleaseBlocker(
                            code="CAPA_VERIFICATION_PENDING",
                            message=f"Corrective action '{action.action_number}' is completed but pending independent verification.",
                            entity_type="corrective_actions",
                            entity_id=action.id,
                        )
                    )

        for reinsp in defect.reinspections:
            all_reinspections.append(reinsp)
            if reinsp.outcome == "DEFECT_RESOLVED":
                reinspections_passed_count += 1
            elif reinsp.outcome == "DEFECT_RECURRED_REOPENED":
                reinspections_failed_count += 1
                if defect.status != "RESOLVED":
                    blockers.append(
                        ReleaseBlocker(
                            code="REINSPECTION_FAILED_DEFECT_REOPENED",
                            message=f"Reinspection for defect '{defect.defect_number}' failed (recurrent defect detected).",
                            entity_type="reinspections",
                            entity_id=reinsp.id,
                        )
                    )

        if defect.status == "PENDING_REINSPECTION":
            blockers.append(
                ReleaseBlocker(
                    code="REINSPECTION_PENDING",
                    message=f"Defect '{defect.defect_number}' is pending mandatory reinspection.",
                    entity_type="defects",
                    entity_id=defect.id,
                )
            )

    # 7. Aggregate Mathematical Counts (Distinct Physical Items, not photographs!)
    total_items = len(items)
    inspected_items = len(
        set(
            img.inspection_item_id
            for img in batch_images
            if img.inspection_item_id is not None
        )
    )
    reviewed_items = len(reviewed_item_ids)
    pending_inspection_items = max(0, total_items - inspected_items)
    pending_review_items = len(pending_review_item_ids)

    counts = {
        "total_items": total_items,
        "inspected_items": inspected_items,
        "reviewed_items": reviewed_items,
        "pending_inspection_items": pending_inspection_items,
        "pending_review_items": pending_review_items,
        "unresolved_defects": len(unresolved_defects),
        "resolved_defects": len(resolved_defects),
        "defects_requiring_reinspection": len(defects_requiring_reinspection),
        "capa_active": capa_active_count,
        "capa_pending_verification": capa_pending_verification_count,
        "capa_verified": capa_verified_count,
        "reinspections_total": len(all_reinspections),
        "reinspections_passed": reinspections_passed_count,
        "reinspections_failed": reinspections_failed_count,
    }

    entity_ids = {
        "inspection_ids": [insp.id for insp in inspections],
        "item_ids": [item.id for item in items],
        "defect_ids": [d.id for d in defects],
        "capa_ids": [a.id for a in all_capas],
        "reinspection_ids": [r.id for r in all_reinspections],
    }

    is_permitted = (len(blockers) == 0)
    if is_permitted:
        summary = "All mandatory release gate criteria satisfied. Batch is eligible for authorized release."
        if is_concession and concession_justification:
            summary += f" (Authorized under Quality Manager concession: {concession_justification})"
    else:
        summary = f"Batch release is blocked by {len(blockers)} unresolved quality requirement(s)."

    return is_permitted, summary, blockers, counts, entity_ids


def build_decision_snapshot(
    decision_id: str,
    batch: Batch,
    decision: str,
    reason: str,
    decided_by: str,
    is_concession: bool,
    concession_justification: Optional[str],
    conditions: Optional[str],
    is_permitted: bool,
    blockers: List[ReleaseBlocker],
    counts: Dict[str, Any],
    entity_ids: Dict[str, List[str]],
) -> Dict[str, Any]:
    """Builds an immutable, auditable batch decision snapshot dictionary."""
    now_utc = datetime.now(timezone.utc)
    return {
        "decision_id": decision_id,
        "batch_id": batch.id,
        "batch_number": batch.batch_number,
        "decision": decision,
        "decided_by": decided_by,
        "decided_at": now_utc.isoformat(),
        "reason": reason,
        "policy_version": "1.0.0",
        "is_concession": is_concession,
        "concession_justification": concession_justification,
        "conditions": conditions,
        "inspection_counts": {
            "total_items": counts.get("total_items", 0),
            "inspected_items": counts.get("inspected_items", 0),
            "reviewed_items": counts.get("reviewed_items", 0),
            "pending_inspection_items": counts.get("pending_inspection_items", 0),
            "pending_review_items": counts.get("pending_review_items", 0),
        },
        "quality_counts": {
            "unresolved_defects": counts.get("unresolved_defects", 0),
            "resolved_defects": counts.get("resolved_defects", 0),
            "defects_requiring_reinspection": counts.get("defects_requiring_reinspection", 0),
            "capa_active": counts.get("capa_active", 0),
            "capa_pending_verification": counts.get("capa_pending_verification", 0),
            "capa_verified": counts.get("capa_verified", 0),
            "reinspections_total": counts.get("reinspections_total", 0),
            "reinspections_passed": counts.get("reinspections_passed", 0),
            "reinspections_failed": counts.get("reinspections_failed", 0),
        },
        "gate_evaluation": {
            "is_permitted": is_permitted,
            "blockers_count": len(blockers),
            "blockers": [b.model_dump() for b in blockers],
            "entity_ids": entity_ids,
            "evaluated_at": now_utc.isoformat(),
        },
    }


def execute_batch_decision(
    db: Session,
    batch_id: str,
    decision: str,
    reason: str,
    current_user: User,
    is_concession: bool = False,
    concession_justification: Optional[str] = None,
    conditions: Optional[str] = None,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    audit_action: Optional[str] = None,
) -> BatchDecision:
    """Executes atomic, concurrency-protected batch decision with release-gate enforcement and immutable snapshot creation."""
    batch = db.get(Batch, batch_id)
    if not batch:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="BATCH_NOT_FOUND",
            message=f"Batch with ID '{batch_id}' was not found.",
        )

    valid_decisions = ["RELEASE", "HOLD", "REJECT_SCRAP", "CONCESSION_DEVIATION"]
    if decision not in valid_decisions:
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="INVALID_DECISION",
            message=f"decision must be one of: {valid_decisions}",
        )

    # Defense-in-depth role check: Only Quality Manager can authorize release, scrap, or concession
    if decision in ("RELEASE", "REJECT_SCRAP", "CONCESSION_DEVIATION") and current_user.role != "QUALITY_MANAGER":
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="INSUFFICIENT_PERMISSIONS",
            message="Only Quality Manager can authorize batch release, scrap, or concession decisions.",
        )

    prev_status = batch.status
    now_utc = datetime.now(timezone.utc)
    decision_id = str(uuid.uuid4())

    # 1. Evaluate Release Gates
    is_permitted, summary, blockers, counts, entity_ids = evaluate_batch_release_gate(
        db=db,
        batch_id=batch_id,
        is_concession=is_concession,
        concession_justification=concession_justification,
    )

    if decision in ("RELEASE", "CONCESSION_DEVIATION"):
        # A. Already released check
        if prev_status == "RELEASED":
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="BATCH_ALREADY_RELEASED",
                message=f"Batch '{batch.batch_number}' is already in RELEASED status.",
            )

        # B. Terminal status check
        if prev_status in ("ARCHIVED", "SCRAPPED"):
            raise AppException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="BATCH_TERMINAL_STATE",
                message=f"Cannot release a batch in terminal status '{prev_status}'.",
            )

        # C. Gate Enforcement
        if not is_permitted:
            # Check if blockers are exclusively unresolved defects (for backward compatible error code)
            open_defects_count = counts.get("unresolved_defects", 0)
            if open_defects_count > 0 and not (is_concession and concession_justification):
                raise AppException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    code="OPEN_DEFECTS_REQUIRE_CONCESSION",
                    message="Cannot release batch with open defects without an explicit Quality Manager concession justification.",
                    details={
                        "open_defects_count": open_defects_count,
                        "blockers": [b.model_dump() for b in blockers],
                    },
                )

            raise AppException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="RELEASE_BLOCKED",
                message=summary,
                details={
                    "blockers": [b.model_dump() for b in blockers],
                    "counts": counts,
                },
            )

        new_status = "RELEASED"
    elif decision == "HOLD":
        new_status = "ON_HOLD"
    elif decision == "REJECT_SCRAP":
        new_status = "SCRAPPED"
    else:
        new_status = prev_status

    # 2. Build Immutable Snapshot
    final_conditions = conditions
    if is_concession and concession_justification:
        concession_note = f"Concession: {concession_justification}"
        final_conditions = f"{final_conditions}; {concession_note}" if final_conditions else concession_note

    snapshot = build_decision_snapshot(
        decision_id=decision_id,
        batch=batch,
        decision=decision,
        reason=reason,
        decided_by=current_user.id,
        is_concession=is_concession,
        concession_justification=concession_justification,
        conditions=final_conditions,
        is_permitted=is_permitted,
        blockers=blockers,
        counts=counts,
        entity_ids=entity_ids,
    )

    # 3. Atomic Conditional Status Update (Concurrency / Race-Condition Prevention)
    stmt = (
        update(Batch)
        .where(Batch.id == batch.id, Batch.status == prev_status)
        .values(status=new_status, updated_at=now_utc)
    )
    res = db.execute(stmt)
    if res.rowcount == 0:
        db.rollback()
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="CONCURRENT_MODIFICATION",
            message="Batch status was modified concurrently during decision evaluation.",
        )

    # 4. Create Decision Record with Snapshot
    decision_record = BatchDecision(
        id=decision_id,
        batch_id=batch.id,
        decision=decision,
        reason=reason,
        decided_by=current_user.id,
        conditions=final_conditions,
        snapshot=snapshot,
        created_at=now_utc,
    )
    db.add(decision_record)
    db.flush()

    # 5. Immutable Audit Event
    audit_action_name = audit_action or "BATCH_DECISION_RECORDED"
    log_audit_event(
        db=db,
        actor_id=current_user.id,
        action=audit_action_name,
        entity_type="batch_decisions",
        entity_id=decision_record.id,
        previous_state={"batch_status": prev_status},
        new_state={
            "decision": decision,
            "batch_status": new_status,
            "reason": reason,
            "is_concession": is_concession,
        },
        ip_address=client_ip,
        user_agent=user_agent,
    )

    db.commit()
    db.refresh(decision_record)
    return decision_record
