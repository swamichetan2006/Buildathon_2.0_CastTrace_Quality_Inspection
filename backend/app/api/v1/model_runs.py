import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Header, Request, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, desc, func

from backend.app.core.errors import AppException
from backend.app.core.idempotency import check_idempotency_key, record_idempotency_result
from backend.app.core.security import get_current_user, require_roles
from backend.app.database import get_db
from backend.app.models.entities import Image, ModelRun, ModelVersion, User, InspectionItem
from backend.app.schemas.model_runs import (
    ModelRunResponse,
    ModelRunEnqueueResponse,
    ModelRunListResponse,
    ItemRoutingSummaryResponse,
)
from backend.app.services.audit import log_audit_event
from backend.app.services.aggregation_service import (
    derive_item_level_routing,
    get_current_model_run_for_image,
)

router = APIRouter(tags=["Model Runs & Inference"])


@router.post(
    "/images/{image_id}/infer",
    response_model=ModelRunEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue Model Inference for Image",
    description="Idempotently enqueues background ML inference for authorized evidence image.",
)
@router.post(
    "/images/{image_id}/model-runs",
    response_model=ModelRunEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    include_in_schema=False,
)
async def enqueue_model_run(
    image_id: str,
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(require_roles(["INSPECTOR", "QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> ModelRunEnqueueResponse:
    # 1. Idempotency Check
    if idempotency_key:
        cached = check_idempotency_key(
            db=db,
            key=idempotency_key,
            user=current_user,
            endpoint=request.url.path,
            payload_dict={"image_id": image_id},
        )
        if cached:
            status_code, body = cached
            return ModelRunEnqueueResponse(**body)

    # 2. Validate Image
    image = db.get(Image, image_id)
    if not image:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="IMAGE_NOT_FOUND",
            message=f"Evidence image with ID '{image_id}' was not found.",
        )

    if image.is_superseded:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="IMAGE_SUPERSEDED",
            message="Cannot enqueue inference on a superseded evidence image. Use the replacement image instead.",
        )

    # 3. Find Active Model Version
    stmt_v = select(ModelVersion).where(ModelVersion.is_active == True).limit(1)
    model_version = db.execute(stmt_v).scalars().first()
    if not model_version:
        raise AppException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="NO_ACTIVE_MODEL_VERSION",
            message="No active registered model version found in database.",
        )

    # 4. Concurrency & Duplicate Check: Search for active job (QUEUED or PROCESSING)
    active_stmt = (
        select(ModelRun)
        .where(
            ModelRun.image_id == image_id,
            ModelRun.model_version_id == model_version.id,
            ModelRun.status.in_(["QUEUED", "PROCESSING"]),
        )
        .limit(1)
    )
    active_run = db.execute(active_stmt).scalars().first()

    if active_run:
        # Gracefully return existing active job instead of 500 error
        res_data = ModelRunEnqueueResponse(
            model_run_id=active_run.id,
            logical_run_id=active_run.logical_run_id,
            image_id=active_run.image_id,
            status=active_run.status,
            attempt_number=active_run.attempt_number,
            message="Inference job already active for this image; returning existing task.",
        )
        if idempotency_key:
            record_idempotency_result(
                db=db,
                key=idempotency_key,
                user=current_user,
                response_code=status.HTTP_200_OK,
                response_body=res_data.model_dump(),
            )
            db.commit()
        return res_data

    # 5. Create new logical run attempt
    logical_id = str(uuid.uuid4())
    new_run = ModelRun(
        logical_run_id=logical_id,
        image_id=image_id,
        model_version_id=model_version.id,
        status="QUEUED",
        attempt_number=1,
    )
    db.add(new_run)
    db.flush()

    # Audit log
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    log_audit_event(
        db=db,
        actor_id=current_user.id,
        action="MODEL_RUN_ENQUEUED",
        entity_type="model_runs",
        entity_id=new_run.id,
        new_state={
            "image_id": image_id,
            "logical_run_id": logical_id,
            "model_version_id": model_version.id,
            "attempt": 1,
            "status": "QUEUED",
        },
        ip_address=client_ip,
        user_agent=user_agent,
    )

    db.commit()
    db.refresh(new_run)

    response_data = ModelRunEnqueueResponse(
        model_run_id=new_run.id,
        logical_run_id=new_run.logical_run_id,
        image_id=new_run.image_id,
        status=new_run.status,
        attempt_number=new_run.attempt_number,
        message="Inference task successfully enqueued for background worker.",
    )

    if idempotency_key:
        record_idempotency_result(
            db=db,
            key=idempotency_key,
            user=current_user,
            response_code=status.HTTP_202_ACCEPTED,
            response_body=response_data.model_dump(),
        )
        db.commit()

    return response_data


@router.get(
    "/model-runs/{run_id}",
    response_model=ModelRunResponse,
    summary="Get Model Run Status and Result",
    description="Retrieves a specific model run attempt by ID.",
)
def get_model_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ModelRunResponse:
    run = db.get(ModelRun, run_id)
    if not run:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="MODEL_RUN_NOT_FOUND",
            message=f"Model run with ID '{run_id}' was not found.",
        )
    return ModelRunResponse.model_validate(run)


@router.get(
    "/model-runs",
    response_model=ModelRunListResponse,
    summary="List Model Runs",
    description="Lists model runs with optional filtering by image_id, status, or logical_run_id.",
)
def list_model_runs(
    image_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    logical_run_id: Optional[str] = Query(None),
    current_only: bool = Query(False, description="Filter to only the latest attempt of latest logical run per image"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ModelRunListResponse:
    query = select(ModelRun)

    if image_id:
        query = query.where(ModelRun.image_id == image_id)
    if status_filter:
        query = query.where(ModelRun.status == status_filter)
    if logical_run_id:
        query = query.where(ModelRun.logical_run_id == logical_run_id)

    if current_only and image_id:
        current_run = get_current_model_run_for_image(db, image_id)
        if current_run:
            return ModelRunListResponse(
                items=[ModelRunResponse.model_validate(current_run)],
                total=1,
            )
        return ModelRunListResponse(items=[], total=0)

    # Count total
    count_stmt = select(func.count()).select_from(query.subquery())
    total = db.execute(count_stmt).scalar() or 0

    # Retrieve page
    stmt = query.order_by(desc(ModelRun.created_at)).offset(skip).limit(limit)
    runs = list(db.execute(stmt).scalars().all())

    return ModelRunListResponse(
        items=[ModelRunResponse.model_validate(r) for r in runs],
        total=total,
    )


@router.post(
    "/model-runs/{run_id}/retry",
    response_model=ModelRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Retry a Failed Model Run",
    description="Manually retries a failed inference attempt subject to the maximum 3-attempt limit.",
)
def retry_model_run(
    run_id: str,
    request: Request,
    current_user: User = Depends(require_roles(["INSPECTOR", "QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> ModelRunResponse:
    run = db.get(ModelRun, run_id)
    if not run:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="MODEL_RUN_NOT_FOUND",
            message=f"Model run with ID '{run_id}' was not found.",
        )

    if run.status != "FAILED":
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="RUN_NOT_RETRYABLE",
            message=f"Only runs in FAILED status can be retried. Current status is '{run.status}'.",
        )

    # Stage 7: Maximum 3 total attempts
    if run.attempt_number >= 3:
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="MAX_RETRIES_EXCEEDED",
            message="Maximum retry limit (3 attempts total) has been exhausted for this inference request.",
        )

    # Check if an active run already exists for this image & model version
    active_stmt = (
        select(ModelRun)
        .where(
            ModelRun.image_id == run.image_id,
            ModelRun.model_version_id == run.model_version_id,
            ModelRun.status.in_(["QUEUED", "PROCESSING"]),
        )
    )
    if db.execute(active_stmt).scalars().first():
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="ACTIVE_RUN_EXISTS",
            message="An active inference run is already queued or processing for this image.",
        )

    # Create next attempt
    next_run = ModelRun(
        logical_run_id=run.logical_run_id,
        image_id=run.image_id,
        model_version_id=run.model_version_id,
        status="QUEUED",
        attempt_number=run.attempt_number + 1,
        parent_run_id=run.id,
        next_retry_at=None,  # Immediate execution on manual retry
    )
    db.add(next_run)
    db.flush()

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    log_audit_event(
        db=db,
        actor_id=current_user.id,
        action="MODEL_RUN_RETRIED",
        entity_type="model_runs",
        entity_id=next_run.id,
        new_state={
            "parent_run_id": run.id,
            "attempt": next_run.attempt_number,
            "status": "QUEUED",
        },
        ip_address=client_ip,
        user_agent=user_agent,
    )

    db.commit()
    db.refresh(next_run)
    return ModelRunResponse.model_validate(next_run)


@router.get(
    "/items/{item_id}/routing-summary",
    response_model=ItemRoutingSummaryResponse,
    summary="Get Item-Level Multi-Image Routing Summary",
    description="Derives item-level routing summary across all non-superseded current images.",
)
def get_item_routing_summary(
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ItemRoutingSummaryResponse:
    item = db.get(InspectionItem, item_id)
    if not item:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="ITEM_NOT_FOUND",
            message=f"Inspection item with ID '{item_id}' was not found.",
        )

    summary = derive_item_level_routing(db, item_id)
    return ItemRoutingSummaryResponse(**summary)
