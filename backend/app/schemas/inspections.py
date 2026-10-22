from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class InspectionCreate(BaseModel):
    batch_id: str = Field(..., description="Target production batch UUID")
    stage: str = Field(default="FINAL_VISUAL", description="Inspection stage: RECEIVING, POST_FETTLING, MACHINED, FINAL_VISUAL")
    sampling_plan: str = Field(default="AQL_LEVEL_II", description="Sampling plan: 100_PERCENT, AQL_LEVEL_II, SPOT_CHECK")


class InspectionItemCreate(BaseModel):
    item_identifier: str = Field(..., min_length=1, max_length=64, description="Physical part serial/tag")
    cavity_number: Optional[int] = Field(None, ge=1, description="Die cavity index")


class InspectionItemsRegisterRequest(BaseModel):
    items: List[InspectionItemCreate] = Field(..., min_length=1, description="List of physical items to register")


class InspectionCancelRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="Administrative reason for cancellation")


class InspectionItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    inspection_id: str
    item_identifier: str
    cavity_number: Optional[int]
    status: str
    created_at: datetime
    updated_at: datetime


class InspectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    inspection_number: str
    batch_id: str
    inspector_id: str
    stage: str
    status: str
    sampling_plan: str
    started_at: datetime
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    items: Optional[List[InspectionItemResponse]] = None

