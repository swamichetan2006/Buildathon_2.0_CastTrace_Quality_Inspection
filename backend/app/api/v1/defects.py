from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, Request, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from backend.app.core.errors import AppException
from backend.app.core.idempotency import check_idempotency_key, record_idempotency_result
from backend.app.core.security import get_current_user, require_roles
from backend.app.database import get_db
from backend.app.models.entities import Defect, Review, InspectionItem, User
from backend.app.schemas.defects import (
    DefectCreate,
    DefectUpdate,
    DefectResolveRequest,
    DefectReopenRequest,
    DefectResponse,
    DefectListResponse,
)
from backend.app.services.quality_lifecycle_service import (
    generate_defect_number,
    update_defect,
    resolve_defect,
    reopen_defect,
)
from backend.app.services.audit import log_audit_event

router = APIRouter(prefix="/defects", tags=["Defects"])


@router.get(
    "",
    response_model=DefectListResponse,
    summary="List Confirmed Defects",
    description="Query and filter confirmed defects by status, severity, category, or inspection item.",
)
def list_defects(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    inspection_item_id: Optional[str] = Query(None),
    batch_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DefectListResponse:
    stmt = select(Defect)
    if status:
        stmt = stmt.where(Defect.status == status)
    if severity:
        stmt = stmt.where(Defect.severity == severity)
    if category:
        stmt = stmt.where(Defect.category == category)
    if inspection_item_id:
        stmt = stmt.where(Defect.inspection_item_id == inspection_item_id)
    if batch_id:
        stmt = stmt.join(InspectionItem).join(InspectionItem.inspection).where(InspectionItem.inspection.has(batch_id=batch_id))

    total = len(list(db.execute(stmt).scalars().all()))
    stmt = stmt.order_by(desc(Defect.created_at)).offset((page - 1) * limit).limit(limit)
    defects = list(db.execute(stmt).scalars().all())

    return DefectListResponse(
        items=[DefectResponse.model_validate(d) for d in defects],
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/{id}",
    response_model=DefectResponse,
    summary="Get Defect Details",
)
def get_defect(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DefectResponse:
    d = db.get(Defect, id)
    if not d:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DEFECT_NOT_FOUND",
            message=f"Defect '{id}' not found.",
        )
    return DefectResponse.model_validate(d)


@router.post(
    "",
    response_model=DefectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Standalone Defect",
    description="Creates a defect record linked to an existing review and item.",
)
def create_defect_endpoint(
    payload: DefectCreate,
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(require_roles(["INSPECTOR", "QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> DefectResponse:
    if not payload.inspection_item_id or not payload.review_id:
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="REQUIRED_RELATIONSHIPS_MISSING",
            message="Both inspection_item_id and review_id are required for standalone defect creation.",
        )

    # 1. Idempotency Check
    if idempotency_key:
        cached = check_idempotency_key(
            db=db,
            key=idempotency_key,
            user=current_user,
            endpoint=str(request.url.path),
            payload_dict=payload.model_dump(),
        )
        if cached:
            status_code, body = cached
            return DefectResponse(**body)

    # Verify review and item
    item = db.get(InspectionItem, payload.inspection_item_id)
    if not item:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="ITEM_NOT_FOUND",
            message=f"Inspection item '{payload.inspection_item_id}' not found.",
        )

    review = db.get(Review, payload.review_id)
    if not review:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="REVIEW_NOT_FOUND",
            message=f"Review '{payload.review_id}' not found.",
        )

    now_utc = datetime.now(timezone.utc)
    defect_num = generate_defect_number(db)
    defect = Defect(
        defect_number=defect_num,
        inspection_item_id=item.id,
        review_id=review.id,
        category=payload.category.value,
        severity=payload.severity.value,
        status="OPEN",
        surface_location=payload.surface_location,
        description=payload.description,
        evidence_image_id=payload.evidence_image_id,
        prior_defect_id=payload.prior_defect_id,
        created_at=now_utc,
        updated_at=now_utc,
    )
    db.add(defect)
    item.status = "CONFIRMED_DEFECTIVE"

    log_audit_event(
        db=db,
        action="DEFECT_LOGGED",
        entity_type="defects",
        entity_id=defect.id,
        actor_id=current_user.id,
        previous_state=None,
        new_state={
            "defect_number": defect_num,
            "category": defect.category,
            "severity": defect.severity,
            "status": "OPEN",
        },
    )

    db.commit()
    db.refresh(defect)

    resp = DefectResponse.model_validate(defect)
    if idempotency_key:
        record_idempotency_result(
            db=db,
            key=idempotency_key,
            user=current_user,
            response_code=status.HTTP_201_CREATED,
            response_body=resp.model_dump(mode="json"),
        )
    return resp


@router.patch(
    "/{id}",
    response_model=DefectResponse,
    summary="Update Defect Details",
    description="Updates severity, surface location, or description. Inspector allowed only on OPEN defects; QM on all active.",
)
def patch_defect(
    id: str,
    payload: DefectUpdate,
    current_user: User = Depends(require_roles(["INSPECTOR", "QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> DefectResponse:
    defect = update_defect(db=db, defect_id=id, payload=payload, current_user=current_user)
    return DefectResponse.model_validate(defect)


@router.post(
    "/{id}/resolve",
    response_model=DefectResponse,
    summary="Resolve Defect (Quality Manager Only, Four-Eyes Enforced)",
    description="Marks defect as RESOLVED. Prohibits the reviewer who logged the defect from closing it.",
)
def resolve_defect_endpoint(
    id: str,
    payload: DefectResolveRequest,
    current_user: User = Depends(require_roles(["QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> DefectResponse:
    defect = resolve_defect(
        db=db,
        defect_id=id,
        resolution_notes=payload.resolution_notes,
        current_user=current_user,
    )
    return DefectResponse.model_validate(defect)


@router.post(
    "/{id}/reopen",
    response_model=DefectResponse,
    summary="Reopen Defect",
    description="Reopens a RESOLVED or PENDING_REINSPECTION defect.",
)
def reopen_defect_endpoint(
    id: str,
    payload: DefectReopenRequest,
    current_user: User = Depends(require_roles(["INSPECTOR", "QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> DefectResponse:
    defect = reopen_defect(
        db=db,
        defect_id=id,
        reopen_notes=payload.reopen_notes,
        current_user=current_user,
    )
    return DefectResponse.model_validate(defect)
