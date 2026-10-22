from datetime import date, datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.orm import Session

from backend.app.core.errors import AppException
from backend.app.core.idempotency import check_idempotency_key, record_idempotency_result
from backend.app.core.security import get_current_user, require_roles
from backend.app.database import get_db
from backend.app.models.entities import Batch, BatchDecision, Defect, Inspection, InspectionItem, Product, User
from backend.app.schemas.batches import (
    BatchCreate,
    BatchDecisionCreate,
    BatchDecisionResponse,
    BatchDecisionListResponse,
    BatchHoldRequest,
    BatchResponse,
    BatchUpdate,
    ReleaseGateResponse,
)
from backend.app.services.audit import log_audit_event
from backend.app.services.release_gate_service import (
    evaluate_batch_release_gate,
    execute_batch_decision,
)

router = APIRouter(prefix="/batches", tags=["Batches"])


@router.get(
    "",
    response_model=List[BatchResponse],
    summary="List Production Batches",
    description="List casting production lots with multi-criteria filtering.",
)
def list_batches(
    status_filter: Optional[str] = Query(None, alias="status"),
    product_id: Optional[str] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[BatchResponse]:
    query = db.query(Batch)
    if status_filter:
        query = query.filter(Batch.status == status_filter)
    if product_id:
        query = query.filter(Batch.product_id == product_id)
    if from_date:
        query = query.filter(Batch.manufacture_date >= from_date)
    if to_date:
        query = query.filter(Batch.manufacture_date <= to_date)

    batches = query.order_by(Batch.created_at.desc()).offset(offset).limit(limit).all()
    return [BatchResponse.model_validate(b) for b in batches]


@router.get(
    "/{batch_id}",
    response_model=BatchResponse,
    summary="Get Batch Detail",
    description="Retrieve production batch details by UUID.",
)
def get_batch(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatchResponse:
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="BATCH_NOT_FOUND",
            message=f"Batch with ID '{batch_id}' was not found.",
        )
    return BatchResponse.model_validate(batch)


@router.post(
    "",
    response_model=BatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Production Batch",
    description="Initializes a new manufacturing casting lot. Requires SUPERVISOR or QUALITY_MANAGER role.",
)
def create_batch(
    payload: BatchCreate,
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(require_roles(["SUPERVISOR", "QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> BatchResponse:
    cached = check_idempotency_key(
        db=db,
        key=idempotency_key,
        user=current_user,
        endpoint=str(request.url.path),
        payload_dict=payload.model_dump(mode="json"),
    )
    if cached:
        return BatchResponse.model_validate(cached[1])

    # Validate target product
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not product:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="PRODUCT_NOT_FOUND",
            message=f"Target product with ID '{payload.product_id}' does not exist.",
        )
    if product.is_archived:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="PRODUCT_ARCHIVED",
            message="Cannot create a production batch for an archived product model.",
        )

    # Check unique batch number
    existing_batch = db.query(Batch).filter(Batch.batch_number == payload.batch_number).first()
    if existing_batch:
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="BATCH_ALREADY_EXISTS",
            message=f"A batch with number '{payload.batch_number}' already exists.",
        )

    batch = Batch(
        batch_number=payload.batch_number,
        product_id=payload.product_id,
        manufacture_date=payload.manufacture_date,
        heat_number=payload.heat_number,
        declared_quantity=payload.declared_quantity,
        status="IN_PRODUCTION",
        notes=payload.notes,
        created_by=current_user.id,
    )
    db.add(batch)
    db.flush()

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    log_audit_event(
        db=db,
        actor_id=current_user.id,
        action="BATCH_INITIALIZED",
        entity_type="batches",
        entity_id=batch.id,
        new_state=payload.model_dump(mode="json"),
        ip_address=client_ip,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(batch)

    resp_data = BatchResponse.model_validate(batch)
    record_idempotency_result(
        db=db,
        key=idempotency_key,
        user=current_user,
        response_code=status.HTTP_201_CREATED,
        response_body=resp_data.model_dump(mode="json"),
    )
    return resp_data


@router.patch(
    "/{batch_id}",
    response_model=BatchResponse,
    summary="Update Batch Metadata",
    description="Updates heat number or production notes.",
)
def update_batch(
    batch_id: str,
    payload: BatchUpdate,
    request: Request,
    current_user: User = Depends(require_roles(["SUPERVISOR", "QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> BatchResponse:
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="BATCH_NOT_FOUND",
            message=f"Batch with ID '{batch_id}' was not found.",
        )

    prev_state = {"heat_number": batch.heat_number, "notes": batch.notes}
    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(batch, field, val)

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    log_audit_event(
        db=db,
        actor_id=current_user.id,
        action="BATCH_METADATA_UPDATED",
        entity_type="batches",
        entity_id=batch.id,
        previous_state=prev_state,
        new_state=update_data,
        ip_address=client_ip,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(batch)
    return BatchResponse.model_validate(batch)


@router.post(
    "/{batch_id}/hold",
    response_model=BatchResponse,
    summary="Place Operational Containment Hold on Batch",
    description="Immediately suspends batch shipping/movement on shop floor. Permitted for INSPECTOR, SUPERVISOR, and QUALITY_MANAGER.",
)
def place_batch_hold(
    batch_id: str,
    payload: BatchHoldRequest,
    request: Request,
    current_user: User = Depends(require_roles(["INSPECTOR", "SUPERVISOR", "QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> BatchResponse:
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    execute_batch_decision(
        db=db,
        batch_id=batch_id,
        decision="HOLD",
        reason=payload.reason,
        current_user=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
        audit_action="BATCH_HELD",
    )
    batch = db.get(Batch, batch_id)
    return BatchResponse.model_validate(batch)


@router.get(
    "/{batch_id}/release-gate",
    response_model=ReleaseGateResponse,
    summary="Evaluate Batch Release Gates",
    description="Evaluates all quality, inspection, review, inference, defect, CAPA, and reinspection gates for a batch.",
)
def get_batch_release_gate(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReleaseGateResponse:
    batch = db.get(Batch, batch_id)
    if not batch:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="BATCH_NOT_FOUND",
            message=f"Batch with ID '{batch_id}' was not found.",
        )
    is_permitted, summary, blockers, counts, _ = evaluate_batch_release_gate(db=db, batch_id=batch_id)
    return ReleaseGateResponse(
        batch_id=batch_id,
        batch_status=batch.status,
        is_permitted=is_permitted,
        summary=summary,
        blockers=blockers,
        counts=counts,
        evaluated_at=datetime.now(timezone.utc),
    )


@router.get(
    "/{batch_id}/decisions",
    response_model=BatchDecisionListResponse,
    summary="List Batch Decision History",
    description="Retrieves the immutable decision ledger and snapshots for a batch.",
)
def list_batch_decisions(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatchDecisionListResponse:
    batch = db.get(Batch, batch_id)
    if not batch:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="BATCH_NOT_FOUND",
            message=f"Batch with ID '{batch_id}' was not found.",
        )
    decisions = (
        db.query(BatchDecision)
        .filter(BatchDecision.batch_id == batch_id)
        .order_by(BatchDecision.created_at.desc())
        .all()
    )
    return BatchDecisionListResponse(
        items=[BatchDecisionResponse.model_validate(d) for d in decisions],
        total=len(decisions),
        batch_id=batch_id,
    )


@router.post(
    "/{batch_id}/decisions",
    response_model=BatchDecisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Authorize Batch Decision",
    description="Authorize engineering release, hold, scrap, or concession for a batch. Restricted to Quality Manager.",
)
def create_batch_decision(
    batch_id: str,
    payload: BatchDecisionCreate,
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(require_roles(["QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> BatchDecisionResponse:
    cached = check_idempotency_key(
        db=db,
        key=idempotency_key,
        user=current_user,
        endpoint=str(request.url.path),
        payload_dict=payload.model_dump(),
    )
    if cached:
        return BatchDecisionResponse.model_validate(cached[1])

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    decision_record = execute_batch_decision(
        db=db,
        batch_id=batch_id,
        decision=payload.decision,
        reason=payload.reason,
        current_user=current_user,
        is_concession=payload.is_concession,
        concession_justification=payload.concession_justification,
        conditions=payload.conditions,
        client_ip=client_ip,
        user_agent=user_agent,
    )

    resp_data = BatchDecisionResponse.model_validate(decision_record)
    record_idempotency_result(
        db=db,
        key=idempotency_key,
        user=current_user,
        response_code=status.HTTP_201_CREATED,
        response_body=resp_data.model_dump(mode="json"),
    )
    return resp_data

