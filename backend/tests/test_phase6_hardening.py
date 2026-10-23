import os
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from backend.app.config import Settings, settings
from backend.app.services.inference_service import InferenceService
from backend.app.models.entities import Image, Product, Batch


class TestSettingsSecurityValidation:
    """Validates configuration security and fail-safe constraints in production mode."""

    def test_production_rejects_default_secret_key(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                APP_ENV="production",
                SECRET_KEY="casttrace-dev-insecure-secret-key-change-in-production-32bytes-min",
                APP_DEBUG=False,
                BACKEND_CORS_ORIGINS=["https://app.casttrace.local"],
                DATABASE_URL="postgresql://postgres:password@localhost:5432/casttrace_dev",
                TEST_DATABASE_URL="postgresql://postgres:password@localhost:5432/casttrace_test",
            )
        assert "A default or development SECRET_KEY cannot be used in production" in str(exc_info.value)

    def test_production_rejects_short_secret_key(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                APP_ENV="production",
                SECRET_KEY="abc123xyz-short-key",
                APP_DEBUG=False,
                BACKEND_CORS_ORIGINS=["https://app.casttrace.local"],
                DATABASE_URL="postgresql://postgres:password@localhost:5432/casttrace_dev",
                TEST_DATABASE_URL="postgresql://postgres:password@localhost:5432/casttrace_test",
            )
        assert "Production SECRET_KEY must be at least 32 characters long" in str(exc_info.value)

    def test_production_rejects_debug_mode_enabled(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                APP_ENV="production",
                SECRET_KEY="cf8m_super_secure_random_production_key_9999",
                APP_DEBUG=True,
                BACKEND_CORS_ORIGINS=["https://app.casttrace.local"],
                DATABASE_URL="postgresql://postgres:password@localhost:5432/casttrace_dev",
                TEST_DATABASE_URL="postgresql://postgres:password@localhost:5432/casttrace_test",
            )
        assert "APP_DEBUG must be set to false in production" in str(exc_info.value)

    def test_production_rejects_wildcard_cors(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                APP_ENV="production",
                SECRET_KEY="cf8m_super_secure_random_production_key_9999",
                APP_DEBUG=False,
                BACKEND_CORS_ORIGINS=["*"],
                DATABASE_URL="postgresql://postgres:password@localhost:5432/casttrace_dev",
                TEST_DATABASE_URL="postgresql://postgres:password@localhost:5432/casttrace_test",
            )
        assert "BACKEND_CORS_ORIGINS must not contain wildcard '*'" in str(exc_info.value)

    def test_production_accepts_valid_hardened_configuration(self):
        cfg = Settings(
            APP_ENV="production",
            SECRET_KEY="cf8m_super_secure_random_production_key_9999",
            APP_DEBUG=False,
            BACKEND_CORS_ORIGINS=["https://app.casttrace.local"],
            DATABASE_URL="postgresql://postgres:password@localhost:5432/casttrace_dev",
            TEST_DATABASE_URL="postgresql://postgres:password@localhost:5432/casttrace_test",
        )
        assert cfg.APP_ENV == "production"
        assert cfg.APP_DEBUG is False
        assert len(cfg.SECRET_KEY) >= 32
        assert cfg.DATABASE_URL.startswith("postgresql://")
        assert cfg.TEST_DATABASE_URL.startswith("postgresql://")


class TestPostgreSQLConfigurationValidation:
    """Validates that PostgreSQL is strictly enforced and SQLite is completely rejected."""

    def test_rejects_missing_database_url(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                DATABASE_URL="",
                TEST_DATABASE_URL="postgresql://postgres:password@localhost:5432/casttrace_test",
            )
        assert "DATABASE_URL is required" in str(exc_info.value)

    def test_rejects_sqlite_database_url(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                DATABASE_URL="sqlite:///./casttrace.db",
                TEST_DATABASE_URL="postgresql://postgres:password@localhost:5432/casttrace_test",
            )
        assert "SQLite is not supported" in str(exc_info.value)

    def test_rejects_missing_test_database_url(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                DATABASE_URL="postgresql://postgres:password@localhost:5432/casttrace_dev",
                TEST_DATABASE_URL="",
            )
        assert "TEST_DATABASE_URL is required" in str(exc_info.value)

    def test_rejects_sqlite_test_database_url(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                DATABASE_URL="postgresql://postgres:password@localhost:5432/casttrace_dev",
                TEST_DATABASE_URL="sqlite:///./casttrace_test.db",
            )
        assert "SQLite is not supported" in str(exc_info.value)

    def test_accepts_valid_postgresql_drivers(self):
        urls = [
            "postgresql://user:pass@localhost:5432/casttrace_dev",
            "postgresql+psycopg2://user:pass@localhost:5432/casttrace_dev",
            "postgresql+asyncpg://user:pass@localhost:5432/casttrace_dev",
        ]
        for url in urls:
            cfg = Settings(
                DATABASE_URL=url,
                TEST_DATABASE_URL="postgresql://user:pass@localhost:5432/casttrace_test",
            )
            assert cfg.DATABASE_URL == url


class TestEvidenceStorageHardening:
    """Validates path traversal protection and secure file storage boundaries."""

    def test_image_content_path_traversal_forbidden(self, client, db_session, seeded_users, inspector_headers, tmp_path, monkeypatch):
        # Set storage dir to a dedicated temp directory
        storage_dir = str(tmp_path / "storage" / "evidence")
        os.makedirs(storage_dir, exist_ok=True)
        monkeypatch.setattr(settings, "STORAGE_DIR", storage_dir)

        # Place a dummy file outside the storage dir
        outside_file = tmp_path / "sensitive.txt"
        outside_file.write_text("sensitive contents")

        inspector = seeded_users["INSPECTOR"]
        prod = Product(sku=f"SKU-{os.urandom(4).hex()}", name="Impeller", material="CF8M")
        db_session.add(prod)
        db_session.commit()

        batch = Batch(
            batch_number=f"BATCH-{os.urandom(4).hex()}",
            product_id=prod.id,
            manufacture_date=datetime.now(timezone.utc).date(),
            declared_quantity=10,
            created_by=inspector.id,
        )
        db_session.add(batch)
        db_session.commit()

        # Manually create an Image pointing outside storage dir
        img = Image(
            batch_id=batch.id,
            uploaded_by=inspector.id,
            storage_path=str(outside_file),
            original_filename="sensitive.txt",
            mime_type="text/plain",
            file_size_bytes=18,
            sha256_hash="fakehash",
            image_scope="ITEM",
        )
        db_session.add(img)
        db_session.commit()
        db_session.refresh(img)

        # Attempt to access the content via API
        response = client.get(f"/api/v1/images/{img.id}/content", headers=inspector_headers)
        assert response.status_code == 403
        data = response.json()
        assert data["error"]["code"] == "ACCESS_DENIED"
        assert "Path escapes the authorized evidence storage repository" in data["error"]["message"]


class TestMLArtifactDiagnostics:
    """Validates preflight artifact diagnostics and health response structure."""

    def test_check_artifacts_status_structure(self):
        svc = InferenceService()
        status = svc.check_artifacts_status()

        assert "metadata_present" in status
        assert "weights_present" in status
        assert "weights_sha256_match" in status
        assert "guard_present" in status
        assert "guard_sha256_match" in status
        assert "is_inference_ready" in status
        assert isinstance(status["is_inference_ready"], bool)

    def test_health_endpoint_includes_ml_artifacts(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "details" in data
        assert "ml_artifacts" in data["details"]
        artifacts = data["details"]["ml_artifacts"]
        assert "is_inference_ready" in artifacts
