from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    sku: str = Field(..., min_length=3, max_length=64, description="Unique product SKU")
    name: str = Field(..., min_length=1, max_length=128, description="Product name")
    material: str = Field(..., min_length=1, max_length=64, description="Material / alloy")
    drawing_number: Optional[str] = Field(None, max_length=64)
    nominal_weight_kg: Optional[float] = Field(None, ge=0.0)
    specifications: Optional[Dict[str, Any]] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    material: Optional[str] = Field(None, min_length=1, max_length=64)
    drawing_number: Optional[str] = Field(None, max_length=64)
    nominal_weight_kg: Optional[float] = Field(None, ge=0.0)
    specifications: Optional[Dict[str, Any]] = None


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sku: str
    name: str
    material: str
    drawing_number: Optional[str]
    nominal_weight_kg: Optional[float]
    specifications: Optional[Dict[str, Any]]
    is_archived: bool
    created_at: datetime
    updated_at: datetime

