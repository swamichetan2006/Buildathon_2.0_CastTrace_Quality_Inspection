from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.model_runs import ModelRunResponse


class ImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    inspection_item_id: Optional[str]
    batch_id: str
    image_scope: str  # ITEM, SURFACE, BATCH_SAMPLE
    surface_location: Optional[str]
    represented_item_count: int
    original_filename: str
    mime_type: str
    file_size_bytes: int
    sha256_hash: str
    is_superseded: bool
    superseded_by_id: Optional[str]
    supersede_reason: Optional[str]
    uploaded_by: str
    created_at: datetime
    model_runs: Optional[List[ModelRunResponse]] = None



class ImageSupersedeRequest(BaseModel):
    superseded_by_id: str = Field(..., description="UUID of replacement evidence image")
    supersede_reason: str = Field(..., min_length=5, description="Rationale for superseding previous image")
