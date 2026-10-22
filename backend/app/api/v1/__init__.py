from fastapi import APIRouter
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.products import router as products_router
from backend.app.api.v1.batches import router as batches_router
from backend.app.api.v1.inspections import router as inspections_router
from backend.app.api.v1.images import router as images_router
from backend.app.api.v1.model_runs import router as model_runs_router
from backend.app.api.v1.workers import router as workers_router
from backend.app.api.v1.audit import router as audit_router
from backend.app.api.v1.reviews import router as reviews_router
from backend.app.api.v1.defects import router as defects_router
from backend.app.api.v1.health import router as health_router

api_v1_router = APIRouter()
api_v1_router.include_router(auth_router)
api_v1_router.include_router(products_router)
api_v1_router.include_router(batches_router)
api_v1_router.include_router(inspections_router)
api_v1_router.include_router(images_router)
api_v1_router.include_router(model_runs_router)
api_v1_router.include_router(reviews_router)
api_v1_router.include_router(defects_router)
api_v1_router.include_router(workers_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(health_router)

__all__ = ["api_v1_router"]
