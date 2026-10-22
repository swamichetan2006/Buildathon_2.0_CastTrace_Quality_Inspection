from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict

class WorkerStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    worker_id: str
    status: str  # READY, BUSY, STARTING, OFFLINE
    started_at: datetime
    last_heartbeat_at: datetime
    model_ready: bool
    model_version_id: Optional[str] = None
    last_error_code: Optional[str] = None
    is_alive: bool


class WorkerOperationalStatusResponse(BaseModel):
    workers: List[WorkerStatusResponse]
    queue_summary: Dict[str, int]
    system_time: datetime
