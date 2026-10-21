import pytest
from fastapi import status
from sqlalchemy.exc import OperationalError
from backend.app.database import get_db
from backend.app.main import app


def test_health_check_healthy(client):
    """Verify that /health returns 200 and reports healthy when DB is accessible."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["app_name"] == "CastTrace AI"
    assert "timestamp" in data
    assert data["database_latency_ms"] is not None
    assert data["database_latency_ms"] >= 0


def test_api_v1_health_check_healthy(client):
    """Verify that /api/v1/health returns 200 and matches the root healthcheck."""
    response = client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


def test_health_check_database_failure(client):
    """Verify that /health returns 503 and reports disconnected when DB fails."""
    class FailingDBSession:
        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("Database connection refused"))

    def override_broken_db():
        yield FailingDBSession()

    app.dependency_overrides[get_db] = override_broken_db
    try:
        response = client.get("/health")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
        assert "error" in data["details"]
    finally:
        app.dependency_overrides.clear()
