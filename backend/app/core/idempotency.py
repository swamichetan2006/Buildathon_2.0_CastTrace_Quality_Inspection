import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from fastapi import Header, Request, status
from sqlalchemy.orm import Session

from backend.app.core.errors import AppException
from backend.app.models.entities import IdempotencyKey, User


def check_idempotency_key(
    db: Session,
    key: Optional[str],
    user: User,
    endpoint: str,
    payload_dict: Optional[Dict[str, Any]] = None,
) -> Optional[Tuple[int, Dict[str, Any]]]:
    """
    Checks if an idempotency key has already been processed or is in progress.
    If already completed, returns (status_code, response_body).
    If in progress, raises 409 Conflict.
    If not found, registers the key as IN_PROGRESS.
    """
    if not key:
        return None

    existing = db.query(IdempotencyKey).filter(
        IdempotencyKey.key == key,
        IdempotencyKey.user_id == user.id,
    ).first()

    now = datetime.now(timezone.utc)
    if existing:
        if existing.status == "IN_PROGRESS":
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="REQUEST_IN_PROGRESS",
                message="A request with this Idempotency-Key is currently in progress. Please wait before retrying.",
            )
        elif existing.status == "COMPLETED":
            return existing.response_code, existing.response_body

    payload_str = json.dumps(payload_dict or {}, sort_keys=True)
    req_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    new_entry = IdempotencyKey(
        key=key,
        user_id=user.id,
        endpoint=endpoint,
        request_hash=req_hash,
        status="IN_PROGRESS",
        expires_at=now + timedelta(hours=24),
    )
    db.add(new_entry)
    db.commit()
    return None


def record_idempotency_result(
    db: Session,
    key: Optional[str],
    user: User,
    response_code: int,
    response_body: Dict[str, Any],
) -> None:
    if not key:
        return

    entry = db.query(IdempotencyKey).filter(
        IdempotencyKey.key == key,
        IdempotencyKey.user_id == user.id,
    ).first()

    if entry:
        entry.status = "COMPLETED"
        entry.response_code = response_code
        entry.response_body = response_body
        db.commit()
