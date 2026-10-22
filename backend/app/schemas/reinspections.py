from enum import Enum
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class ReinspectionOutcome(str, Enum):
    DEFECT_RESOLVED = "DEFECT_RESOLVED"
    DEFECT_RECURRED_REOPENED = "DEFECT_RECURRED_REOPENED"


class ReinspectionCreate(BaseModel):
    defect_id: str = Field(..., description="Target defect UUID")
    corrective_action_id: str = Field(..., description="Associated completed CAPA UUID")
    outcome: ReinspectionOutcome = Field(..., description="Verdict: DEFECT_RESOLVED or DEFECT_RECURRED_REOPENED")
    notes: Optional[str] = Field(None, min_length=5, description="Reinspection evidence summary")
    evidence_image_id: Optional[str] = Field(None, description="Follow-up visual evidence photograph UUID")
    followup_inspection_id: Optional[str] = Field(None, description="Optional follow-up inspection UUID")


class ReinspectionSignOffRequest(BaseModel):
    notes: str = Field(..., min_length=5, description="Quality Manager sign-off notes")


class ReinspectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    defect_id: str
    corrective_action_id: str
    original_inspection_id: str
    followup_inspection_id: str
    outcome: str
    notes: Optional[str] = None
    evidence_image_id: Optional[str] = None
    verified_by: str
    created_at: datetime


class ReinspectionListResponse(BaseModel):
    items: List[ReinspectionResponse]
    total: int
    page: int
    limit: int
