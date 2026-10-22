from typing import Optional, List
from fastapi import APIRouter, Depends, Header, Request, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from backend.app.core.errors import AppException
from backend.app.core.idempotency import check_idempotency_key, record_idempotency_result
from backend.app.core.security import get_current_user, require_roles
from backend.app.database import get_db
from backend.app.models.entities import Review, Defect, User
from backend.app.schemas.reviews import (
    ReviewCreate,
    ReviewDisputeRequest,
    ReviewAdjudicateRequest,
    ReviewResponse,
    ReviewListResponse,
)
from backend.app.schemas.defects import DefectResponse
from backend.app.services.quality_lifecycle_service import (
    record_human_review,
    dispute_review,
    adjudicate_review,
)

router = APIRouter(prefix="/reviews", tags=["Human Reviews & Disputes"])


@router.post(
    "",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record Human Review",
    description="Records human inspector or QM decision on an item. If confirming defective, requires defect payload.",
)
def create_review(
    payload: ReviewCreate,
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(require_roles(["INSPECTOR", "QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> ReviewResponse:
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
            return ReviewResponse(**body)

    # 2. Record review
    review, created_defect = record_human_review(db=db, payload=payload, current_user=current_user)

    defects_list = [DefectResponse.model_validate(created_defect)] if created_defect else []
    resp = ReviewResponse(
        id=review.id,
        inspection_id=review.inspection_id,
        inspection_item_id=review.inspection_item_id,
        model_run_id=review.model_run_id,
        reviewer_id=review.reviewer_id,
        decision=review.decision,
        model_disagreement=review.model_disagreement,
        notes=review.notes,
        ai_snapshot=review.ai_snapshot,
        created_at=review.created_at,
        defects=defects_list,
    )

    if idempotency_key:
        record_idempotency_result(
            db=db,
            key=idempotency_key,
            user=current_user,
            response_code=status.HTTP_201_CREATED,
            response_body=resp.model_dump(mode="json"),
        )

    return resp


@router.get(
    "",
    response_model=ReviewListResponse,
    summary="List Human Reviews",
    description="Query and filter human reviews with disagreement and status filters.",
)
def list_reviews(
    inspection_id: Optional[str] = Query(None),
    inspection_item_id: Optional[str] = Query(None),
    reviewer_id: Optional[str] = Query(None),
    decision: Optional[str] = Query(None),
    model_disagreement: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewListResponse:
    stmt = select(Review)
    if inspection_id:
        stmt = stmt.where(Review.inspection_id == inspection_id)
    if inspection_item_id:
        stmt = stmt.where(Review.inspection_item_id == inspection_item_id)
    if reviewer_id:
        stmt = stmt.where(Review.reviewer_id == reviewer_id)
    if decision:
        stmt = stmt.where(Review.decision == decision)
    if model_disagreement is not None:
        stmt = stmt.where(Review.model_disagreement == model_disagreement)

    total = len(list(db.execute(stmt).scalars().all()))
    stmt = stmt.order_by(desc(Review.created_at)).offset((page - 1) * limit).limit(limit)
    reviews = list(db.execute(stmt).scalars().all())

    items = []
    for r in reviews:
        defects_list = [DefectResponse.model_validate(d) for d in r.defects]
        items.append(
            ReviewResponse(
                id=r.id,
                inspection_id=r.inspection_id,
                inspection_item_id=r.inspection_item_id,
                model_run_id=r.model_run_id,
                reviewer_id=r.reviewer_id,
                decision=r.decision,
                model_disagreement=r.model_disagreement,
                notes=r.notes,
                ai_snapshot=r.ai_snapshot,
                created_at=r.created_at,
                defects=defects_list,
            )
        )

    return ReviewListResponse(items=items, total=total, page=page, limit=limit)


@router.get(
    "/{id}",
    response_model=ReviewResponse,
    summary="Get Review Details",
)
def get_review(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewResponse:
    r = db.get(Review, id)
    if not r:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="REVIEW_NOT_FOUND",
            message=f"Review '{id}' not found.",
        )
    defects_list = [DefectResponse.model_validate(d) for d in r.defects]
    return ReviewResponse(
        id=r.id,
        inspection_id=r.inspection_id,
        inspection_item_id=r.inspection_item_id,
        model_run_id=r.model_run_id,
        reviewer_id=r.reviewer_id,
        decision=r.decision,
        model_disagreement=r.model_disagreement,
        notes=r.notes,
        ai_snapshot=r.ai_snapshot,
        created_at=r.created_at,
        defects=defects_list,
    )


@router.post(
    "/{id}/dispute",
    response_model=ReviewResponse,
    summary="Dispute / Escalate Review",
    description="Flags a review as disputed, requiring Quality Management adjudication.",
)
def dispute_review_endpoint(
    id: str,
    payload: ReviewDisputeRequest,
    current_user: User = Depends(require_roles(["INSPECTOR", "SUPERVISOR", "QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> ReviewResponse:
    dispute_rev = dispute_review(db=db, review_id=id, notes=payload.notes, current_user=current_user)
    return ReviewResponse(
        id=dispute_rev.id,
        inspection_id=dispute_rev.inspection_id,
        inspection_item_id=dispute_rev.inspection_item_id,
        model_run_id=dispute_rev.model_run_id,
        reviewer_id=dispute_rev.reviewer_id,
        decision=dispute_rev.decision,
        model_disagreement=dispute_rev.model_disagreement,
        notes=dispute_rev.notes,
        ai_snapshot=dispute_rev.ai_snapshot,
        created_at=dispute_rev.created_at,
        defects=[],
    )


@router.post(
    "/{id}/adjudicate",
    response_model=ReviewResponse,
    summary="Adjudicate Disputed Review",
    description="Quality Manager resolves a disputed review with final verdict and rationale.",
)
def adjudicate_review_endpoint(
    id: str,
    payload: ReviewAdjudicateRequest,
    current_user: User = Depends(require_roles(["QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> ReviewResponse:
    rev, defect = adjudicate_review(
        db=db,
        review_id=id,
        decision=payload.decision,
        notes=payload.notes,
        defect_payload=payload.defect,
        current_user=current_user,
    )
    defects_list = [DefectResponse.model_validate(defect)] if defect else []
    return ReviewResponse(
        id=rev.id,
        inspection_id=rev.inspection_id,
        inspection_item_id=rev.inspection_item_id,
        model_run_id=rev.model_run_id,
        reviewer_id=rev.reviewer_id,
        decision=rev.decision,
        model_disagreement=rev.model_disagreement,
        notes=rev.notes,
        ai_snapshot=rev.ai_snapshot,
        created_at=rev.created_at,
        defects=defects_list,
    )
