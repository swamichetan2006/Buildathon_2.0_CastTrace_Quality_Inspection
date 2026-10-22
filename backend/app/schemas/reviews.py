from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.defects import DefectCreate, DefectResponse


class ReviewDecision(str, Enum):
    CONFIRMED_GOOD = "CONFIRMED_GOOD"
    CONFIRMED_DEFECTIVE = "CONFIRMED_DEFECTIVE"
    DISPUTED = "DISPUTED"
    REQUEST_ADDITIONAL_EVIDENCE = "REQUEST_ADDITIONAL_EVIDENCE"
    ADDITIONAL_EVIDENCE_REQUESTED = "ADDITIONAL_EVIDENCE_REQUESTED"


class ReviewCreate(BaseModel):
    inspection_item_id: str
    decision: ReviewDecision
    notes: Optional[str] = None
    model_run_id: Optional[str] = None
    defect: Optional[DefectCreate] = None


class ReviewDisputeRequest(BaseModel):
    notes: str = Field(..., min_length=5, description="Rationale for disputing or escalating review verdict")


class ReviewAdjudicateRequest(BaseModel):
    decision: ReviewDecision
    notes: str = Field(..., min_length=5, description="Quality Manager adjudication rationale")
    defect: Optional[DefectCreate] = None


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    inspection_id: str
    inspection_item_id: str
    model_run_id: Optional[str] = None
    reviewer_id: str
    decision: str
    model_disagreement: bool
    notes: Optional[str] = None
    ai_snapshot: Optional[Dict[str, Any]] = None
    created_at: datetime
    defects: Optional[List[DefectResponse]] = None


class ReviewListResponse(BaseModel):
    items: List[ReviewResponse]
    total: int
    page: int
    limit: int
