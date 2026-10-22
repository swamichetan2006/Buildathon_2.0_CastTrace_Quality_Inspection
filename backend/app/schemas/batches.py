from datetime import date, datetime
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict, Field


class BatchCreate(BaseModel):
    batch_number: str = Field(..., min_length=3, max_length=64, description="Manufacturing lot number")
    product_id: str = Field(..., description="Target product UUID")
    manufacture_date: date = Field(..., description="Date casting was poured")
    heat_number: Optional[str] = Field(None, max_length=64)
    declared_quantity: int = Field(..., gt=0, description="Declared production lot size")
    notes: Optional[str] = None


class BatchUpdate(BaseModel):
    heat_number: Optional[str] = Field(None, max_length=64)
    notes: Optional[str] = None


class BatchHoldRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="Engineering/containment reason for hold")


class BatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    batch_number: str
    product_id: str
    manufacture_date: date
    heat_number: Optional[str]
    declared_quantity: int
    status: str
    notes: Optional[str]
    created_by: str
    created_at: datetime
    updated_at: datetime


class BatchDecisionCreate(BaseModel):
    decision: str = Field(..., description="Decision: RELEASE, HOLD, REJECT_SCRAP, CONCESSION_DEVIATION")
    reason: str = Field(..., min_length=5, description="Formal engineering justification")
    is_concession: bool = Field(False, description="Whether release is under authorized concession")
    concession_justification: Optional[str] = Field(None, description="Concession justification if open defects exist")
    conditions: Optional[str] = Field(None, description="Conditional release terms")


class ReleaseBlocker(BaseModel):
    code: str = Field(..., description="Machine-readable blocker identifier")
    message: str = Field(..., description="Human-readable explanation")
    entity_type: Optional[str] = Field(None, description="Related entity table name if applicable")
    entity_id: Optional[str] = Field(None, description="Related entity UUID if applicable")


class ReleaseGateResponse(BaseModel):
    batch_id: str
    batch_status: str
    is_permitted: bool
    summary: str
    blockers: list[ReleaseBlocker]
    counts: dict[str, Any]
    evaluated_at: datetime


class BatchDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    batch_id: str
    decision: str
    reason: str
    decided_by: str
    conditions: Optional[str] = None
    snapshot: Optional[dict[str, Any]] = None
    created_at: datetime


class BatchDecisionListResponse(BaseModel):
    items: list[BatchDecisionResponse]
    total: int
    batch_id: str
