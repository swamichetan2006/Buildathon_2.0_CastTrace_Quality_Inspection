import datetime
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from backend.app.core.security import require_roles
from backend.app.database import get_db
from backend.app.models.entities import WorkerHeartbeat, ModelRun, User
from backend.app.schemas.workers import (
    WorkerStatusResponse,
    WorkerOperationalStatusResponse,
)

router = APIRouter(prefix="/workers", tags=["Workers & Operations"])

HEARTBEAT_TIMEOUT_SECONDS = 30


@router.get(
    "/status",
    response_model=WorkerOperationalStatusResponse,
    summary="Get Worker Operational Status",
    description="Inspects background inference worker health, heartbeats, and queue statistics. Restricted to supervisors, quality managers, and admins.",
)
def get_worker_status(
    current_user: User = Depends(require_roles(["SUPERVISOR", "QUALITY_MANAGER", "ADMIN"])),
    db: Session = Depends(get_db),
) -> WorkerOperationalStatusResponse:
    now = datetime.datetime.now(datetime.timezone.utc)
    threshold = now - datetime.timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS)

    # 1. Fetch heartbeats
    stmt = select(WorkerHeartbeat).order_by(WorkerHeartbeat.last_heartbeat_at.desc())
    heartbeats = list(db.execute(stmt).scalars().all())

    worker_items = []
    for hb in heartbeats:
        last_hb = hb.last_heartbeat_at
        if last_hb.tzinfo is None:
            last_hb = last_hb.replace(tzinfo=datetime.timezone.utc)

        is_alive = last_hb >= threshold and hb.status != "OFFLINE"
        current_status = hb.status
        if not is_alive and current_status != "OFFLINE":
            current_status = "OFFLINE"

        worker_items.append(
            WorkerStatusResponse(
                worker_id=hb.worker_id,
                status=current_status,
                started_at=hb.started_at,
                last_heartbeat_at=hb.last_heartbeat_at,
                model_ready=hb.model_ready,
                model_version_id=hb.model_version_id,
                last_error_code=hb.last_error_code,
                is_alive=is_alive,
            )
        )

    # 2. Inexpensive Queue Counts
    q_counts = (
        db.query(ModelRun.status, func.count(ModelRun.id))
        .group_by(ModelRun.status)
        .all()
    )
    queue_summary = {s: cnt for s, cnt in q_counts}
    queue_summary.setdefault("QUEUED", 0)
    queue_summary.setdefault("PROCESSING", 0)
    queue_summary.setdefault("SUCCEEDED", 0)
    queue_summary.setdefault("FAILED", 0)

    return WorkerOperationalStatusResponse(
        workers=worker_items,
        queue_summary=queue_summary,
        system_time=now,
    )
