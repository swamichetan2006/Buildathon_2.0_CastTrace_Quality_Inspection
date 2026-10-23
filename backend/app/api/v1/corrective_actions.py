from typing import Optional, List
from fastapi import APIRouter, Depends, Header, Request, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, or_

from backend.app.core.errors import AppException
from backend.app.core.idempotency import check_idempotency_key, record_idempotency_result
from backend.app.core.security import get_current_user, require_roles
from backend.app.database import get_db
from backend.app.models.entities import CorrectiveAction, User
from backend.app.schemas.corrective_actions import (
    CorrectiveActionCreate,
    CorrectiveActionUpdate,
    CorrectiveActionCompleteRequest,
    CorrectiveActionCancelRequest,
    CorrectiveActionVerifyRequest,
    CorrectiveActionResponse,
    CorrectiveActionListResponse,
)
from backend.app.services.quality_lifecycle_service import (
    create_corrective_action,
    start_corrective_action,
    update_corrective_action,
    complete_corrective_action,
    cancel_corrective_action,
    verify_corrective_action,
)

router = APIRouter(prefix="/corrective-actions", tags=["Corrective Actions (CAPA)"])


@router.get(
    "",
    response_model=CorrectiveActionListResponse,
    summary="List Corrective Actions",
    description="Query and filter CAPA tasks by defect, assignee, status, or action type.",
)
def list_corrective_actions(
    defect_id: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CorrectiveActionListResponse:
    stmt = select(CorrectiveAction)
    if defect_id:
        stmt = stmt.where(CorrectiveAction.defect_id == defect_id)
    if assigned_to:
        stmt = stmt.where(CorrectiveAction.assigned_to == assigned_to)
    if status:
        stmt = stmt.where(CorrectiveAction.status == status)
    if action_type:
        stmt = stmt.where(CorrectiveAction.action_type == action_type)

    total = len(list(db.execute(stmt).scalars().all()))
    stmt = stmt.order_by(desc(CorrectiveAction.created_at)).offset((page - 1) * limit).limit(limit)
    actions = list(db.execute(stmt).scalars().all())

    return CorrectiveActionListResponse(
        items=[CorrectiveActionResponse.model_validate(a) for a in actions],
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/{id}",
    response_model=CorrectiveActionResponse,
    summary="Get Corrective Action Details",
)
def get_corrective_action_endpoint(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CorrectiveActionResponse:
    action = db.query(CorrectiveAction).filter(or_(CorrectiveAction.id == id, CorrectiveAction.action_number == id)).first()
    if not action:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="ACTION_NOT_FOUND",
            message=f"Corrective action '{id}' not found.",
        )
    return CorrectiveActionResponse.model_validate(action)


@router.post(
    "",
    response_model=CorrectiveActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign Corrective Action (CAPA)",
    description="Assigns remediation plan to an open defect. Roles: SUPERVISOR, QUALITY_MANAGER.",
)
def create_corrective_action_endpoint(
    payload: CorrectiveActionCreate,
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(require_roles(["SUPERVISOR", "QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> CorrectiveActionResponse:
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
            return CorrectiveActionResponse(**body)

    action = create_corrective_action(db=db, payload=payload, current_user=current_user)
    resp = CorrectiveActionResponse.model_validate(action)

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
    "/{id}/start",
    response_model=CorrectiveActionResponse,
    summary="Start Execution of Corrective Action",
    description="Transitions CAPA from OPEN to IN_PROGRESS. Permitted: Assignee, SUPERVISOR, QUALITY_MANAGER.",
)
def start_corrective_action_endpoint(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CorrectiveActionResponse:
    action = start_corrective_action(db=db, action_id=id, current_user=current_user)
    return CorrectiveActionResponse.model_validate(action)


@router.patch(
    "/{id}",
    response_model=CorrectiveActionResponse,
    summary="Update Corrective Action",
    description="Updates description, root cause, preventive action, or due date. Permitted: Assignee, SUPERVISOR, QUALITY_MANAGER.",
)
def patch_corrective_action_endpoint(
    id: str,
    payload: CorrectiveActionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CorrectiveActionResponse:
    action = update_corrective_action(db=db, action_id=id, payload=payload, current_user=current_user)
    return CorrectiveActionResponse.model_validate(action)


@router.post(
    "/{id}/complete",
    response_model=CorrectiveActionResponse,
    summary="Complete Corrective Action",
    description="Documents remediation work done and marks action COMPLETED; transitions defect to PENDING_REINSPECTION.",
)
def complete_corrective_action_endpoint(
    id: str,
    payload: CorrectiveActionCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CorrectiveActionResponse:
    action = complete_corrective_action(
        db=db,
        action_id=id,
        completion_notes=payload.completion_notes,
        completion_evidence_image_id=payload.completion_evidence_image_id,
        current_user=current_user,
    )
    return CorrectiveActionResponse.model_validate(action)


@router.post(
    "/{id}/cancel",
    response_model=CorrectiveActionResponse,
    summary="Cancel Corrective Action",
    description="Cancels an open or in-progress action. Roles: QUALITY_MANAGER only.",
)
def cancel_corrective_action_endpoint(
    id: str,
    payload: CorrectiveActionCancelRequest,
    current_user: User = Depends(require_roles(["QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> CorrectiveActionResponse:
    action = cancel_corrective_action(
        db=db,
        action_id=id,
        reason=payload.reason,
        current_user=current_user,
    )
    return CorrectiveActionResponse.model_validate(action)


@router.post(
    "/{id}/verify",
    response_model=CorrectiveActionResponse,
    summary="Independent Verification of Completed Action",
    description="Independent verification with Four-Eyes control (implementer cannot verify their own action). Roles: INSPECTOR, QUALITY_MANAGER.",
)
def verify_corrective_action_endpoint(
    id: str,
    payload: CorrectiveActionVerifyRequest,
    current_user: User = Depends(require_roles(["INSPECTOR", "QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> CorrectiveActionResponse:
    action = verify_corrective_action(
        db=db,
        action_id=id,
        decision=payload.decision,
        notes=payload.notes,
        rejection_reason=payload.rejection_reason,
        current_user=current_user,
    )
    return CorrectiveActionResponse.model_validate(action)
