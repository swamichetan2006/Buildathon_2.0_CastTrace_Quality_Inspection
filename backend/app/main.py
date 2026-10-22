import uuid
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.config import settings
from backend.app.core.errors import (
    AppException,
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from backend.app.api.v1 import api_v1_router
from backend.app.api.v1.health import get_health
from backend.app.database import get_db
from backend.app.schemas.health import HealthResponse


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4()}"
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Product Quality Inspection & Defect Tracking System API for Cast Pump Impellers",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Request ID tracking middleware
app.add_middleware(RequestIdMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handlers ensuring standard error envelope
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Root-level health endpoint
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Root Application Health Check",
)
def root_health(response: Response, db: Session = Depends(get_db)) -> HealthResponse:
    return get_health(response=response, db=db)


# Include API v1 routes
app.include_router(api_v1_router, prefix=settings.API_V1_STR)
