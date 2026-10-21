from fastapi import FastAPI, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.api.v1 import api_v1_router
from backend.app.api.v1.health import get_health
from backend.app.database import get_db
from backend.app.schemas.health import HealthResponse

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Product Quality Inspection & Defect Tracking System API for Cast Pump Impellers",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root-level health endpoint for direct container / cluster healthchecks
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Root Application Health Check",
)
def root_health(response: Response, db: Session = Depends(get_db)) -> HealthResponse:
    return get_health(response=response, db=db)


# Include API v1 router
app.include_router(api_v1_router, prefix=settings.API_V1_STR)
