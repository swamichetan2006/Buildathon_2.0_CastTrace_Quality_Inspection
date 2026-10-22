from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.security import require_roles
from backend.app.database import get_db
from backend.app.models.entities import AuditLog, User
from backend.app.schemas.audit import AuditLogResponse

router = APIRouter(prefix="/audit-logs", tags=["Audit Trail"])


@router.get(
    "",
    response_model=List[AuditLogResponse],
    summary="List Audit Trail",
    description="Retrieves immutable system audit records. Restricted to QUALITY_MANAGER role.",
)
def list_audit_logs(
    entity_type: Optional[str] = Query(None, description="Filter by target table name"),
    entity_id: Optional[str] = Query(None, description="Filter by target entity UUID"),
    actor_id: Optional[str] = Query(None, description="Filter by user UUID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_roles(["QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> List[AuditLogResponse]:
    query = db.query(AuditLog)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)
    if actor_id:
        query = query.filter(AuditLog.actor_id == actor_id)

    entries = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    return [AuditLogResponse.model_validate(e) for e in entries]
