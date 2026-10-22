import os
import sqlite3
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from backend.app.config import Settings, settings
from backend.app.services.inference_service import InferenceService
from backend.app.models.entities import Image, Product, Batch
from scripts.backup_database import create_backup
from scripts.restore_database import restore_database, verify_database_file


class TestSettingsSecurityValidation:
    """Validates configuration security and fail-safe constraints in production mode."""

    def test_production_rejects_default_secret_key(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                APP_ENV="production",
                SECRET_KEY="casttrace-dev-insecure-secret-key-change-in-production-32bytes-min",
                APP_DEBUG=False,
                BACKEND_CORS_ORIGINS=["https://app.casttrace.local"],
            )
        assert "A default or development SECRET_KEY cannot be used in production" in str(exc_info.value)

    def test_production_rejects_short_secret_key(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                APP_ENV="production",
                SECRET_KEY="abc123xyz-short-key",
                APP_DEBUG=False,
                BACKEND_CORS_ORIGINS=["https://app.casttrace.local"],
            )
        assert "Production SECRET_KEY must be at least 32 characters long" in str(exc_info.value)

    def test_production_rejects_debug_mode_enabled(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                APP_ENV="production",
                SECRET_KEY="cf8m_super_secure_random_production_key_9999",
                APP_DEBUG=True,
                BACKEND_CORS_ORIGINS=["https://app.casttrace.local"],
            )
        assert "APP_DEBUG must be set to false in production" in str(exc_info.value)

    def test_production_rejects_wildcard_cors(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                APP_ENV="production",
                SECRET_KEY="cf8m_super_secure_random_production_key_9999",
                APP_DEBUG=False,
                BACKEND_CORS_ORIGINS=["*"],
            )
        assert "BACKEND_CORS_ORIGINS must not contain wildcard '*'" in str(exc_info.value)

    def test_production_accepts_valid_hardened_configuration(self):
        cfg = Settings(
            APP_ENV="production",
            SECRET_KEY="cf8m_super_secure_random_production_key_9999",
            APP_DEBUG=False,
            BACKEND_CORS_ORIGINS=["https://app.casttrace.local"],
        )
        assert cfg.APP_ENV == "production"
        assert cfg.APP_DEBUG is False
        assert len(cfg.SECRET_KEY) >= 32


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


class TestSQLiteBackupAndRestore:
    """Validates SQLite online backup and safe restoration without touching real DB."""

    def test_backup_and_restore_cycle(self, tmp_path):
        # Create a source test database with schema and data
        source_db = str(tmp_path / "test_source.db")
        conn = sqlite3.connect(source_db)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, name TEXT);")
        cursor.execute("INSERT INTO test_data (name) VALUES ('Impeller-Batch-A');")
        cursor.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);")
        cursor.execute("INSERT INTO alembic_version VALUES ('6eae03ca7c6e');")
        conn.commit()
        conn.close()

        # Perform backup
        backup_dir = str(tmp_path / "backups")
        backup_path = create_backup(destination_dir=backup_dir, source_db=source_db, required_tables=["test_data", "alembic_version"])
        assert os.path.exists(backup_path)

        # Check-only verification
        verified_tables = verify_database_file(backup_path)
        assert "test_data" in verified_tables
        assert "alembic_version" in verified_tables

        # Restore to new target database
        restored_db = str(tmp_path / "test_restored.db")
        target_path = restore_database(
            backup_file=backup_path,
            target_db_path=restored_db,
            create_safety_backup=False,
            required_tables=["test_data", "alembic_version"],
        )
        assert target_path == restored_db

        # Verify restored DB integrity and records
        rconn = sqlite3.connect(restored_db)
        rcursor = rconn.cursor()
        rcursor.execute("PRAGMA integrity_check;")
        assert rcursor.fetchone()[0] == "ok"
        rcursor.execute("SELECT name FROM test_data WHERE id = 1;")
        assert rcursor.fetchone()[0] == "Impeller-Batch-A"
        rconn.close()
