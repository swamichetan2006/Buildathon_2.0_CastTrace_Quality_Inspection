import logging
from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.entities import User
from backend.app.core.security import get_current_user
from backend.app.core.errors import AppException
from backend.app.schemas.intelligence import (
    IntelligenceQueryRequest,
    IntelligenceQueryResponse,
    AttentionResponse,
    HistoricalSimilarityResponse,
    BatchDefectOption,
)
from backend.app.services.intelligence_service import (
    execute_quality_intelligence_query,
    compile_attention_today,
    find_historical_similar_defects,
    list_batch_defects_for_selection,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intelligence", tags=["Quality Intelligence"])
genai_router = APIRouter(prefix="/genai", tags=["Quality Intelligence"])


@router.post(
    "/query",
    response_model=IntelligenceQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Evidence-Grounded Quality Intelligence Query",
    description=(
        "Executes a natural language quality inquiry regarding a manufacturing batch. "
        "All facts, defect counts, inspection coverage, and release blockers are computed "
        "deterministically against PostgreSQL and grounded using Gemini API."
    ),
)
def query_quality_intelligence(
    payload: IntelligenceQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IntelligenceQueryResponse:
    """Answers batch-specific quality, defect, inspection, and release-gate inquiries."""
    try:
        return execute_quality_intelligence_query(db=db, payload=payload, current_user=current_user)
    except AppException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during Quality Intelligence query execution: %s", exc)
        raise AppException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTELLIGENCE_INTERNAL_ERROR",
            message=f"An error occurred while evaluating quality intelligence: {str(exc)}",
        ) from exc


@genai_router.post(
    "/query",
    response_model=IntelligenceQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="GenAI Assistant Query (Alias)",
    description="Alias endpoint for backward compatibility with /api/v1/genai/query contract.",
)
def query_genai_assistant(
    payload: IntelligenceQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IntelligenceQueryResponse:
    """Alias for /api/v1/intelligence/query."""
    try:
        return execute_quality_intelligence_query(db=db, payload=payload, current_user=current_user)
    except AppException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during GenAI Assistant query execution: %s", exc)
        raise AppException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTELLIGENCE_INTERNAL_ERROR",
            message=f"An error occurred while evaluating quality intelligence: {str(exc)}",
        ) from exc


# ==============================================================================
# PHASE 3: FEATURE A — WHAT NEEDS ATTENTION TODAY? ENDPOINTS
# ==============================================================================

@router.get(
    "/attention",
    response_model=AttentionResponse,
    status_code=status.HTTP_200_OK,
    summary="What Needs Attention Today? (Quality Action Queue)",
    description=(
        "Computes an actionable list of draft inspections, unreviewed items, unresolved defects, "
        "overdue or pending-verification CAPAs, and release blockers from PostgreSQL records."
    ),
)
def get_attention_today(
    batch_identifier: Optional[str] = Query(None, description="Optional batch UUID or number filter"),
    batch_number: Optional[str] = Query(None, description="Alias for batch_identifier"),
    priority: Optional[str] = Query(None, description="Filter by priority: CRITICAL, HIGH, MEDIUM, LOW"),
    as_of_date: Optional[date] = Query(None, description="Reference date for deterministic evaluation of day boundaries"),
    limit: int = Query(50, ge=1, le=200, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AttentionResponse:
    target_batch = batch_identifier or batch_number
    return compile_attention_today(
        db=db,
        current_user=current_user,
        batch_identifier=target_batch,
        priority_filter=priority,
        as_of_date=as_of_date,
        limit=limit,
        offset=offset,
    )


@genai_router.get(
    "/attention",
    response_model=AttentionResponse,
    status_code=status.HTTP_200_OK,
    summary="What Needs Attention Today? (Alias)",
    description="Alias endpoint for /api/v1/genai/attention contract.",
)
def get_genai_attention_today(
    batch_identifier: Optional[str] = Query(None, description="Optional batch UUID or number filter"),
    batch_number: Optional[str] = Query(None, description="Alias for batch_identifier"),
    priority: Optional[str] = Query(None, description="Filter by priority: CRITICAL, HIGH, MEDIUM, LOW"),
    as_of_date: Optional[date] = Query(None, description="Reference date for deterministic evaluation of day boundaries"),
    limit: int = Query(50, ge=1, le=200, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AttentionResponse:
    target_batch = batch_identifier or batch_number
    return compile_attention_today(
        db=db,
        current_user=current_user,
        batch_identifier=target_batch,
        priority_filter=priority,
        as_of_date=as_of_date,
        limit=limit,
        offset=offset,
    )


# ==============================================================================
# PHASE 3: FEATURE B — HAVE WE SEEN THIS ISSUE BEFORE? ENDPOINTS
# ==============================================================================

@router.get(
    "/historical-similarity",
    response_model=HistoricalSimilarityResponse,
    status_code=status.HTTP_200_OK,
    summary="Have We Seen This Issue Before? (Defect Recurrence & Similarity Radar)",
    description=(
        "Retrieves real historical defects matching a source defect using multi-factor "
        "similarity scoring (product, category, severity, surface location, lexical description, "
        "and explicit recurrence links), along with recorded prior CAPAs and reinspection outcomes."
    ),
)
def get_historical_similarity(
    defect_id: str = Query(..., description="Target defect UUID or business identifier DEF-YYYYMMDD-XXXX"),
    limit: int = Query(5, ge=1, le=20, description="Max candidate historical defects to return"),
    include_cross_product: bool = Query(True, description="Include cross-product candidates with lower weighting"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HistoricalSimilarityResponse:
    return find_historical_similar_defects(
        db=db,
        current_user=current_user,
        defect_id=defect_id,
        limit=limit,
        include_cross_product=include_cross_product,
    )


@genai_router.get(
    "/historical-similarity",
    response_model=HistoricalSimilarityResponse,
    status_code=status.HTTP_200_OK,
    summary="Have We Seen This Issue Before? (Alias)",
    description="Alias endpoint for /api/v1/genai/historical-similarity contract.",
)
def get_genai_historical_similarity(
    defect_id: str = Query(..., description="Target defect UUID or business identifier DEF-YYYYMMDD-XXXX"),
    limit: int = Query(5, ge=1, le=20, description="Max candidate historical defects to return"),
    include_cross_product: bool = Query(True, description="Include cross-product candidates with lower weighting"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HistoricalSimilarityResponse:
    return find_historical_similar_defects(
        db=db,
        current_user=current_user,
        defect_id=defect_id,
        limit=limit,
        include_cross_product=include_cross_product,
    )


@router.get(
    "/batch-defects",
    response_model=List[BatchDefectOption],
    status_code=status.HTTP_200_OK,
    summary="List Batch Defects for Selection",
    description="Returns all confirmed defects for a batch so the user can explicitly choose which defect to inspect.",
)
def get_batch_defects_for_selection(
    batch_identifier: str = Query(..., description="Batch UUID or business batch number"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[BatchDefectOption]:
    return list_batch_defects_for_selection(
        db=db,
        current_user=current_user,
        batch_identifier=batch_identifier,
    )

