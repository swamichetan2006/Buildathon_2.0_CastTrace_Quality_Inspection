from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field

class ModelRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    logical_run_id: str
    image_id: str
    model_version_id: Optional[str] = None
    status: str
    predicted_label: Optional[str] = None
    score: Optional[float] = None
    score_type: str = "PROBABILITY_DEFECTIVE"
    threshold_applied: float = 0.50000
    routing_outcome: Optional[str] = None
    routing_reason: Optional[str] = None
    processing_latency_ms: Optional[int] = None
    attempt_number: int = 1
    parent_run_id: Optional[str] = None
    error_code: Optional[str] = None
    is_retryable: Optional[bool] = True
    error_details: Optional[Dict[str, Any]] = None
    executed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class ModelRunEnqueueResponse(BaseModel):
    model_run_id: str
    logical_run_id: str
    image_id: str
    status: str
    attempt_number: int
    message: str


class ModelRunListResponse(BaseModel):
    items: List[ModelRunResponse]
    total: int


class ItemImageRoutingDetail(BaseModel):
    image_id: str
    original_filename: str
    image_scope: str
    represented_item_count: int
    run_id: Optional[str] = None
    run_status: str
    routing_outcome: str
    score: Optional[float] = None


class ItemRoutingSummaryResponse(BaseModel):
    inspection_item_id: str
    derived_routing_outcome: str
    derived_reason: str
    total_images: int
    has_defective_flag: bool
    has_review_or_incomplete_flag: bool
    additional_review_required: bool
    image_details: List[ItemImageRoutingDetail]
