from enum import Enum
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class ActionType(str, Enum):
    REWORK = "REWORK"
    SCRAP = "SCRAP"
    PROCESS_ADJUSTMENT = "PROCESS_ADJUSTMENT"
    TOOLING_REPAIR = "TOOLING_REPAIR"
    MOLD_INSPECTION = "MOLD_INSPECTION"


class ActionStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class VerificationDecision(str, Enum):
    APPROVED = "APPROVED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class CorrectiveActionCreate(BaseModel):
    defect_id: str = Field(..., description="Target defect UUID")
    title: str = Field(..., min_length=3, max_length=128, description="Remediation summary")
    action_type: ActionType = Field(default=ActionType.REWORK, description="CAPA action category")
    description: str = Field(..., min_length=5, description="Engineering remediation instructions")
    assigned_to: str = Field(..., description="Assigned implementer user UUID")
    due_date: date = Field(..., description="Target completion date (must be today or future)")
    root_cause: Optional[str] = Field(None, min_length=3, description="Identified root cause")
    preventive_action: Optional[str] = Field(None, min_length=3, description="Preventive action to prevent recurrence")


class CorrectiveActionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=128)
    action_type: Optional[ActionType] = None
    description: Optional[str] = Field(None, min_length=5)
    due_date: Optional[date] = None
    root_cause: Optional[str] = None
    preventive_action: Optional[str] = None


class CorrectiveActionCompleteRequest(BaseModel):
    completion_notes: str = Field(..., min_length=10, description="Documentation of work done")
    completion_evidence_image_id: Optional[str] = Field(None, description="Optional photographic proof of completed work")


class CorrectiveActionCancelRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="Quality Manager cancellation justification")


class CorrectiveActionVerifyRequest(BaseModel):
    decision: VerificationDecision = Field(..., description="APPROVED or REJECTED")
    notes: str = Field(..., min_length=5, description="Verification observations")
    rejection_reason: Optional[str] = Field(None, description="Required explanation when decision is REJECTED")


class CorrectiveActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    action_number: str
    defect_id: str
    title: str
    action_type: str
    description: str
    assigned_to: str
    assigned_by: str
    status: str
    due_date: date
    root_cause: Optional[str] = None
    preventive_action: Optional[str] = None
    completed_at: Optional[datetime] = None
    completion_notes: Optional[str] = None
    completion_evidence_image_id: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    verification_notes: Optional[str] = None
    verification_status: Optional[str] = None
    rejection_reason: Optional[str] = None
    verification_history: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    updated_at: datetime


class CorrectiveActionListResponse(BaseModel):
    items: List[CorrectiveActionResponse]
    total: int
    page: int
    limit: int
