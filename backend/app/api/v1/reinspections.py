from typing import Optional, List
from fastapi import APIRouter, Depends, Header, Request, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from backend.app.core.errors import AppException
from backend.app.core.idempotency import check_idempotency_key, record_idempotency_result
from backend.app.core.security import get_current_user, require_roles
from backend.app.database import get_db
from backend.app.models.entities import Reinspection, User
from backend.app.schemas.reinspections import (
    ReinspectionCreate,
    ReinspectionSignOffRequest,
    ReinspectionResponse,
    ReinspectionListResponse,
)
from backend.app.services.quality_lifecycle_service import (
    create_reinspection,
    sign_off_reinspection,
)

router = APIRouter(prefix="/reinspections", tags=["Reinspections"])


@router.get(
    "",
    response_model=ReinspectionListResponse,
    summary="List Reinspections",
    description="Query and filter follow-up verification reinspections.",
)
def list_reinspections(
    defect_id: Optional[str] = Query(None),
    corrective_action_id: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    verified_by: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReinspectionListResponse:
    stmt = select(Reinspection)
    if defect_id:
        stmt = stmt.where(Reinspection.defect_id == defect_id)
    if corrective_action_id:
        stmt = stmt.where(Reinspection.corrective_action_id == corrective_action_id)
    if outcome:
        stmt = stmt.where(Reinspection.outcome == outcome)
    if verified_by:
        stmt = stmt.where(Reinspection.verified_by == verified_by)

    total = len(list(db.execute(stmt).scalars().all()))
    stmt = stmt.order_by(desc(Reinspection.created_at)).offset((page - 1) * limit).limit(limit)
    reinspections = list(db.execute(stmt).scalars().all())

    return ReinspectionListResponse(
        items=[ReinspectionResponse.model_validate(r) for r in reinspections],
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/{id}",
    response_model=ReinspectionResponse,
    summary="Get Reinspection Details",
)
def get_reinspection_endpoint(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReinspectionResponse:
    reinspection = db.get(Reinspection, id)
    if not reinspection:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="REINSPECTION_NOT_FOUND",
            message=f"Reinspection '{id}' not found.",
        )
    return ReinspectionResponse.model_validate(reinspection)


@router.post(
    "",
    response_model=ReinspectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Conduct Follow-up Reinspection",
    description="Records follow-up verification inspection after CAPA completion. Enforces Four-Eyes SoD-2. Roles: INSPECTOR, QUALITY_MANAGER.",
)
def create_reinspection_endpoint(
    payload: ReinspectionCreate,
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(require_roles(["INSPECTOR", "QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> ReinspectionResponse:
    # 1. Idempotency Check
    if idempotency_key:
        cached = check_idempotency_key(
            db=db,
            key=idempotency_key,
            user=current_user,
            endpoint=str(request.url.path),
            payload_dict=payload.model_dump(mode="json"),
        )
        if cached:
            status_code, body = cached
            return ReinspectionResponse(**body)

    reinspection = create_reinspection(db=db, payload=payload, current_user=current_user)
    resp = ReinspectionResponse.model_validate(reinspection)

    if idempotency_key:
        record_idempotency_result(
            db=db,
            key=idempotency_key,
            user=current_user,
            response_code=status.HTTP_201_CREATED,
            response_body=resp.model_dump(mode="json"),
        )
    return resp


@router.post(
    "/{id}/sign-off",
    response_model=ReinspectionResponse,
    summary="Sign Off on Verified Defect Fix",
    description="Quality Manager official sign-off on completed reinspection fix (permissions.md:64). Roles: QUALITY_MANAGER only.",
)
def sign_off_reinspection_endpoint(
    id: str,
    payload: ReinspectionSignOffRequest,
    current_user: User = Depends(require_roles(["QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> ReinspectionResponse:
    reinspection = sign_off_reinspection(
        db=db,
        reinspection_id=id,
        notes=payload.notes,
        current_user=current_user,
    )
    return ReinspectionResponse.model_validate(reinspection)
