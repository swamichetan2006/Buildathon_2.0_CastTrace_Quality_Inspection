from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall health: healthy, degraded, or unhealthy")
    app_name: str = Field(..., description="Name of application")
    environment: str = Field(..., description="Runtime environment")
    version: str = Field(default="1.0.0", description="API version")
    database: str = Field(..., description="Database connection status: connected or disconnected")
    database_latency_ms: Optional[float] = Field(None, description="Ping latency to database in milliseconds")
    timestamp: datetime = Field(..., description="UTC timestamp of the health check")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Diagnostic details")
