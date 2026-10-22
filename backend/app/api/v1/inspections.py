import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.orm import Session

from backend.app.core.errors import AppException
from backend.app.core.idempotency import check_idempotency_key, record_idempotency_result
from backend.app.core.security import get_current_user, require_roles
from backend.app.database import get_db
from backend.app.models.entities import Batch, Image, Inspection, InspectionItem, User
from backend.app.schemas.inspections import (
    InspectionCancelRequest,
    InspectionCreate,
    InspectionItemResponse,
    InspectionItemsRegisterRequest,
    InspectionResponse,
)
from backend.app.services.audit import log_audit_event

router = APIRouter(prefix="/inspections", tags=["Inspections"])


def generate_inspection_number() -> str:
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"INSP-{today_str}-{short_uuid}"


@router.post(
    "",
    response_model=InspectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Draft Inspection",
    description="Initializes a new staging inspection for a batch. Requires Inspector, Supervisor, or Quality Manager.",
)
def create_inspection(
    payload: InspectionCreate,
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(require_roles(["INSPECTOR", "SUPERVISOR", "QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> InspectionResponse:
    cached = check_idempotency_key(
        db=db,
        key=idempotency_key,
        user=current_user,
        endpoint=str(request.url.path),
        payload_dict=payload.model_dump(),
    )
    if cached:
        return InspectionResponse.model_validate(cached[1])

    batch = db.query(Batch).filter(Batch.id == payload.batch_id).first()
    if not batch:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="BATCH_NOT_FOUND",
            message=f"Target batch with ID '{payload.batch_id}' was not found.",
        )
    if batch.status in ["ARCHIVED", "SCRAPPED"]:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="BATCH_TERMINATED",
            message=f"Cannot initiate inspection on a batch with status '{batch.status}'.",
        )

    insp_num = generate_inspection_number()
    inspection = Inspection(
        inspection_number=insp_num,
        batch_id=payload.batch_id,
        inspector_id=current_user.id,
        stage=payload.stage,
        status="DRAFT",
        sampling_plan=payload.sampling_plan,
    )
    db.add(inspection)
    db.flush()

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    log_audit_event(
        db=db,
        actor_id=current_user.id,
        action="INSPECTION_CREATED",
        entity_type="inspections",
        entity_id=inspection.id,
        new_state=payload.model_dump(),
        ip_address=client_ip,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(inspection)

    resp_data = InspectionResponse.model_validate(inspection)
    record_idempotency_result(
        db=db,
        key=idempotency_key,
        user=current_user,
        response_code=status.HTTP_201_CREATED,
        response_body=resp_data.model_dump(mode="json"),
    )
    return resp_data


@router.get(
    "",
    response_model=List[InspectionResponse],
    summary="List Inspections",
    description="List inspections with optional filtering by batch, status, or inspector.",
)
def list_inspections(
    batch_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    inspector_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[InspectionResponse]:
    query = db.query(Inspection)
    if batch_id:
        query = query.filter(Inspection.batch_id == batch_id)
    if status_filter:
        query = query.filter(Inspection.status == status_filter)
    if inspector_id:
        query = query.filter(Inspection.inspector_id == inspector_id)

    inspections = query.order_by(Inspection.created_at.desc()).offset(offset).limit(limit).all()
    return [InspectionResponse.model_validate(i) for i in inspections]


@router.get(
    "/{inspection_id}",
    response_model=InspectionResponse,
    summary="Get Inspection Detail",
    description="Retrieve inspection details and registered physical inspection items.",
)
def get_inspection(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InspectionResponse:
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="INSPECTION_NOT_FOUND",
            message=f"Inspection with ID '{inspection_id}' was not found.",
        )
    return InspectionResponse.model_validate(inspection)


@router.post(
    "/{inspection_id}/items",
    response_model=List[InspectionItemResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register Physical Inspection Items",
    description="Registers one or more physical items to an inspection. Must be in DRAFT status.",
)
def register_inspection_items(
    inspection_id: str,
    payload: InspectionItemsRegisterRequest,
    current_user: User = Depends(require_roles(["INSPECTOR", "QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> List[InspectionItemResponse]:
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="INSPECTION_NOT_FOUND",
            message=f"Inspection with ID '{inspection_id}' was not found.",
        )
    if inspection.status != "DRAFT":
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="INVALID_STATE_TRANSITION",
            message=f"Cannot add items to inspection in '{inspection.status}' state. Must be in 'DRAFT'.",
        )

    # Check for duplicate item identifiers within payload
    identifiers = [it.item_identifier for it in payload.items]
    if len(identifiers) != len(set(identifiers)):
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="DUPLICATE_ITEM_IDENTIFIER",
            message="Payload contains duplicate item identifiers.",
        )

    # Check for existing items in inspection
    existing = db.query(InspectionItem.item_identifier).filter(
        InspectionItem.inspection_id == inspection_id,
        InspectionItem.item_identifier.in_(identifiers),
    ).all()
    if existing:
        dup = [e[0] for e in existing]
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="ITEM_ALREADY_EXISTS",
            message=f"Item(s) already registered in this inspection: {dup}",
        )

    created_items = []
    for it in payload.items:
        item = InspectionItem(
            inspection_id=inspection_id,
            item_identifier=it.item_identifier,
            cavity_number=it.cavity_number,
            status="PENDING",
        )
        db.add(item)
        created_items.append(item)

    db.commit()
    for item in created_items:
        db.refresh(item)
    return [InspectionItemResponse.model_validate(it) for it in created_items]


@router.post(
    "/{inspection_id}/submit",
    response_model=InspectionResponse,
    summary="Submit Inspection for Review",
    description="Transitions inspection from DRAFT to SUBMITTED. Requires at least 1 item and 1 non-superseded image.",
)
def submit_inspection(
    inspection_id: str,
    request: Request,
    current_user: User = Depends(require_roles(["INSPECTOR", "QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> InspectionResponse:
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="INSPECTION_NOT_FOUND",
            message=f"Inspection with ID '{inspection_id}' was not found.",
        )
    if inspection.status != "DRAFT":
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="INVALID_STATE_TRANSITION",
            message=f"Cannot submit inspection in state '{inspection.status}'. Must be in 'DRAFT'.",
        )

    # Validation: Must have >= 1 item and >= 1 non-superseded image
    item_count = db.query(InspectionItem).filter(InspectionItem.inspection_id == inspection_id).count()
    if item_count == 0:
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="NO_ITEMS_REGISTERED",
            message="Inspection must contain at least one physical inspection item before submission.",
        )

    # Check evidence images linked to these items or the batch
    item_ids = [it.id for it in db.query(InspectionItem.id).filter(InspectionItem.inspection_id == inspection_id).all()]
    image_count = db.query(Image).filter(
        Image.inspection_item_id.in_(item_ids),
        Image.is_superseded == False,
    ).count()

    if image_count == 0:
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="INSUFFICIENT_EVIDENCE",
            message="Inspection must contain at least one active, non-superseded evidence image before submission.",
        )

    inspection.status = "SUBMITTED"
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    log_audit_event(
        db=db,
        actor_id=current_user.id,
        action="INSPECTION_SUBMITTED",
        entity_type="inspections",
        entity_id=inspection.id,
        previous_state={"status": "DRAFT"},
        new_state={"status": "SUBMITTED", "item_count": item_count, "image_count": image_count},
        ip_address=client_ip,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(inspection)
    return InspectionResponse.model_validate(inspection)


@router.post(
    "/{inspection_id}/cancel",
    response_model=InspectionResponse,
    summary="Cancel Inspection",
    description="Cancels an inspection session. Inspectors can cancel DRAFT; Quality Managers can cancel at any stage.",
)
def cancel_inspection(
    inspection_id: str,
    payload: InspectionCancelRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InspectionResponse:
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="INSPECTION_NOT_FOUND",
            message=f"Inspection with ID '{inspection_id}' was not found.",
        )

    if inspection.status == "COMPLETED":
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="INVALID_STATE_TRANSITION",
            message="Cannot cancel a completed inspection.",
        )

    # Role permission check: Inspectors can only cancel their own DRAFT inspections
    if current_user.role == "INSPECTOR":
        if inspection.status != "DRAFT" or inspection.inspector_id != current_user.id:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="INSUFFICIENT_PERMISSIONS",
                message="Inspectors can only cancel their own DRAFT inspections.",
            )
    elif current_user.role not in ["QUALITY_MANAGER", "ADMIN"]:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="INSUFFICIENT_PERMISSIONS",
            message="Only Quality Managers can cancel submitted inspections.",
        )

    prev_status = inspection.status
    inspection.status = "CANCELLED"
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    log_audit_event(
        db=db,
        actor_id=current_user.id,
        action="INSPECTION_CANCELLED",
        entity_type="inspections",
        entity_id=inspection.id,
        previous_state={"status": prev_status},
        new_state={"status": "CANCELLED", "reason": payload.reason},
        ip_address=client_ip,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(inspection)
    return InspectionResponse.model_validate(inspection)
