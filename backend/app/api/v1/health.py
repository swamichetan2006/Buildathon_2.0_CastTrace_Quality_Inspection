import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Application and Database Health Check",
    description="Actively verifies database connectivity via SELECT 1 and reports latency.",
)
def get_health(response: Response, db: Session = Depends(get_db)) -> HealthResponse:
    start_time = time.perf_counter()
    now_utc = datetime.now(timezone.utc)

    try:
        db.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        from backend.app.services.inference_service import InferenceService
        ml_status = InferenceService().check_artifacts_status()
        return HealthResponse(
            status="healthy",
            app_name=settings.APP_NAME,
            environment=settings.APP_ENV,
            version="1.0.0",
            database="connected",
            database_latency_ms=latency_ms,
            timestamp=now_utc,
            details={
                "database_type": "postgresql",
                "dialect": db.bind.dialect.name if db.bind else "unknown",
                "ml_artifacts": ml_status,
            },
        )
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(
            status="unhealthy",
            app_name=settings.APP_NAME,
            environment=settings.APP_ENV,
            version="1.0.0",
            database="disconnected",
            database_latency_ms=latency_ms,
            timestamp=now_utc,
            details={"error": str(exc)},
        )
