from enum import Enum
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class DefectCategory(str, Enum):
    BLOWHOLE = "BLOWHOLE"
    SHRINKAGE_POROSITY = "SHRINKAGE_POROSITY"
    PINHOLE = "PINHOLE"
    HOT_TEAR = "HOT_TEAR"
    COLD_SHUT = "COLD_SHUT"
    CRACK = "CRACK"
    SURFACE_ROUGHNESS = "SURFACE_ROUGHNESS"
    INCLUSION = "INCLUSION"
    OTHER = "OTHER"


class DefectSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class DefectStatus(str, Enum):
    OPEN = "OPEN"
    ACTION_ASSIGNED = "ACTION_ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_REINSPECTION = "PENDING_REINSPECTION"
    RESOLVED = "RESOLVED"
    REOPENED = "REOPENED"


class DefectCreate(BaseModel):
    inspection_item_id: Optional[str] = None
    review_id: Optional[str] = None
    category: DefectCategory
    severity: DefectSeverity
    surface_location: Optional[str] = None
    description: str = Field(..., min_length=3, description="Specific defect observation details")
    evidence_image_id: Optional[str] = None
    prior_defect_id: Optional[str] = None


class DefectUpdate(BaseModel):
    severity: Optional[DefectSeverity] = None
    surface_location: Optional[str] = None
    description: Optional[str] = Field(None, min_length=3)


class DefectResolveRequest(BaseModel):
    resolution_notes: str = Field(..., min_length=5, description="Justification and evidence notes for defect resolution")


class DefectReopenRequest(BaseModel):
    reopen_notes: str = Field(..., min_length=5, description="Reason for reopening defect")


class DefectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    defect_number: str
    inspection_item_id: str
    review_id: str
    category: str
    severity: str
    status: str
    surface_location: Optional[str] = None
    description: str
    evidence_image_id: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    prior_defect_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DefectListResponse(BaseModel):
    items: List[DefectResponse]
    total: int
    page: int
    limit: int
