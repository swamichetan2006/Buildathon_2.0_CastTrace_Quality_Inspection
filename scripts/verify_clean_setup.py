"""CastTrace AI — Clean-Setup Verification & Smoke Test Script.

Validates application reproducibility, isolated database migration/seeding,
live service health, ML artifact integrity, authentication, and read-only APIs.

Safety: Performs database migration and seeding checks against an ISOLATED
temporary SQLite database file without touching the active development database.
"""

import os
import sys
import time
import sqlite3
import tempfile
import httpx
from datetime import datetime, timezone

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8001")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

checks = []

def record_check(category: str, name: str, passed: bool, details: str = ""):
    status_str = "PASS" if passed else "FAIL"
    checks.append({"category": category, "name": name, "status": status_str, "details": details})
    print(f"[{status_str}] {category} -> {name}: {details}")
    if not passed:
        print(f"  FAILED CHECK: {name}")


def main():
    print("=" * 80)
    print("CASTTRACE AI — REPRODUCIBLE CLEAN-SETUP VERIFICATION")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # 1. RUNTIME & CONFIGURATION VERIFICATION
    # -------------------------------------------------------------------------
    print("\n--- 1. Runtime & Configuration Verification ---")
    py_ver = sys.version_info
    py_ok = py_ver.major == 3 and py_ver.minor >= 10
    record_check("Runtime", "Python Version >= 3.10", py_ok, f"Python {py_ver.major}.{py_ver.minor}.{py_ver.micro}")

    try:
        from backend.app.config import settings
        record_check("Configuration", "Load Settings", True, f"App: {settings.APP_NAME}, Env: {settings.APP_ENV}")
    except Exception as e:
        record_check("Configuration", "Load Settings", False, str(e))

    # -------------------------------------------------------------------------
    # 2. ISOLATED CLEAN-DATABASE MIGRATION & SEEDING (TEMP DB)
    # -------------------------------------------------------------------------
    print("\n--- 2. Isolated Clean SQLite Database Migration & Seeding ---")
    temp_dir = tempfile.mkdtemp(prefix="casttrace_clean_setup_")
    temp_db_path = os.path.join(temp_dir, "clean_test.db")
    temp_db_url = f"sqlite:///{temp_db_path}"

    try:
        print(f"Creating isolated temporary database at: {temp_db_path}")
        # Run Alembic migrations programmatically
        os.environ["ALEMBIC_DATABASE_URL"] = temp_db_url
        alembic_cfg = Config(os.path.join(PROJECT_ROOT, "alembic.ini"))
        alembic_cfg.set_main_option("sqlalchemy.url", temp_db_url)
        alembic_cfg.set_main_option("script_location", os.path.join(PROJECT_ROOT, "backend", "alembic"))
        command.upgrade(alembic_cfg, "head")
        os.environ.pop("ALEMBIC_DATABASE_URL", None)

        # Verify integrity of newly migrated schema
        conn = sqlite3.connect(temp_db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        res = cur.fetchone()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cur.fetchall()]
        conn.close()

        mig_passed = (res and res[0] == "ok" and len(tables) >= 15)
        record_check("Database Migration", "Alembic Upgrade Head on Fresh SQLite", mig_passed,
                     f"Integrity {res[0]}, created {len(tables)} tables")

        # Test seeding demo accounts into isolated DB
        from backend.scripts.seed import seed_database
        engine = create_engine(temp_db_url)
        SessionTest = sessionmaker(bind=engine)
        test_session = SessionTest()
        try:
            seed_database(test_session)
            from backend.app.models.entities import User
            users = test_session.query(User).all()
            user_roles = {u.username: u.role for u in users}
            expected_roles = {
                "inspector_chen": "INSPECTOR",
                "supervisor_torres": "SUPERVISOR",
                "qm_reynolds": "QUALITY_MANAGER",
            }
            seed_ok = all(user_roles.get(u) == r for u, r in expected_roles.items())
            record_check("Database Seeding", "Seed Demo Accounts on Fresh SQLite", seed_ok,
                         f"Seeded accounts: {', '.join(user_roles.keys())}")
        finally:
            test_session.close()
            engine.dispose()

    except Exception as e:
        record_check("Database Setup", "Isolated Clean DB Migration & Seeding", False, str(e))
    finally:
        # Clean up temporary database directory
        try:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
            os.rmdir(temp_dir)
            print("Cleaned up isolated temporary test database.")
        except Exception as e:
            print(f"Note on temp cleanup: {e}")

    # -------------------------------------------------------------------------
    # 3. ML ARTIFACT REPRODUCIBILITY & INTEGRITY
    # -------------------------------------------------------------------------
    print("\n--- 3. ML Artifact Reproducibility & Integrity ---")
    try:
        from backend.app.services.inference_service import InferenceService
        service = InferenceService()
        art_status = service.check_artifacts_status()
        record_check("ML Artifacts", "Model Metadata Present", art_status["metadata_present"], f"Path: {service.metadata_path}")
        record_check("ML Artifacts", "ResNet-18 Weights Verified", art_status["weights_present"] and art_status["weights_sha256_match"],
                     f"weights_present={art_status['weights_present']}, sha256_match={art_status['weights_sha256_match']}")
        record_check("ML Artifacts", "Unfamiliar-Input Reference Verified", art_status["guard_present"] and art_status["guard_sha256_match"],
                     f"guard_present={art_status['guard_present']}, sha256_match={art_status['guard_sha256_match']}")
        record_check("ML Artifacts", "Inference Readiness Flag", art_status["is_inference_ready"],
                     f"is_inference_ready={art_status['is_inference_ready']}, reason={art_status.get('reason')}")
    except Exception as e:
        record_check("ML Artifacts", "Artifact Integrity Verification", False, str(e))

    # -------------------------------------------------------------------------
    # 4. LIVE SERVICE CONNECTIVITY & HEALTH CHECKS
    # -------------------------------------------------------------------------
    print("\n--- 4. Live Backend & Frontend Health Probes ---")
    client = httpx.Client(timeout=5.0)

    # 4.1 Backend Direct Health
    try:
        r_backend = client.get(f"{BACKEND_URL}/health")
        data = r_backend.json()
        b_ok = (r_backend.status_code == 200 and data.get("status") == "healthy" and data.get("database") == "connected")
        record_check("Live Service", "FastAPI Backend /health", b_ok,
                     f"HTTP {r_backend.status_code}, db={data.get('database')}, latency={data.get('database_latency_ms')}ms")
    except Exception as e:
        record_check("Live Service", "FastAPI Backend /health", False, f"Failed to connect to {BACKEND_URL}: {e}")

    # 4.2 Frontend Dev Server & Reverse Proxy
    try:
        r_fe = client.get(f"{FRONTEND_URL}/health")
        fe_data = r_fe.json()
        fe_ok = (r_fe.status_code == 200 and fe_data.get("status") == "healthy")
        record_check("Live Service", "Vite Reverse Proxy /health", fe_ok,
                     f"Proxied through {FRONTEND_URL}/health (HTTP {r_fe.status_code})")
    except Exception as e:
        record_check("Live Service", "Vite Reverse Proxy /health", False, f"Failed to connect to {FRONTEND_URL}: {e}")

    # -------------------------------------------------------------------------
    # 5. AUTHENTICATION & REPRESENTATIVE READ-ONLY API
    # -------------------------------------------------------------------------
    print("\n--- 5. Authentication & Representative Read-Only API ---")
    qm_token = None
    try:
        login_res = client.post(
            f"{BACKEND_URL}/api/v1/auth/login",
            json={"username": "qm_reynolds", "password": "Password123!"},
        )
        if login_res.status_code == 200:
            qm_token = login_res.json()["access_token"]
            record_check("Authentication", "Quality Manager Login", True, "Successfully obtained JWT bearer token")
        else:
            record_check("Authentication", "Quality Manager Login", False, f"HTTP {login_res.status_code}: {login_res.text}")
    except Exception as e:
        record_check("Authentication", "Quality Manager Login", False, str(e))

    if qm_token:
        headers = {"Authorization": f"Bearer {qm_token}"}
        try:
            prod_res = client.get(f"{BACKEND_URL}/api/v1/products", headers=headers)
            passed = (prod_res.status_code == 200 and isinstance(prod_res.json(), list))
            record_check("Read-Only API", "List Products (GET /api/v1/products)", passed,
                         f"HTTP 200, returned {len(prod_res.json())} product(s)")
        except Exception as e:
            record_check("Read-Only API", "List Products (GET /api/v1/products)", False, str(e))

        try:
            batch_res = client.get(f"{BACKEND_URL}/api/v1/batches", headers=headers)
            passed = (batch_res.status_code == 200 and isinstance(batch_res.json(), list))
            record_check("Read-Only API", "List Batches (GET /api/v1/batches)", passed,
                         f"HTTP 200, returned {len(batch_res.json())} batch(es)")
        except Exception as e:
            record_check("Read-Only API", "List Batches (GET /api/v1/batches)", False, str(e))

        try:
            worker_res = client.get(f"{BACKEND_URL}/api/v1/workers/status", headers=headers)
            passed = (worker_res.status_code == 200 and "workers" in worker_res.json())
            record_check("Read-Only API", "Worker Operational Status (GET /api/v1/workers/status)", passed,
                         f"HTTP 200, {len(worker_res.json().get('workers', []))} worker(s) registered")
        except Exception as e:
            record_check("Read-Only API", "Worker Operational Status", False, str(e))

    # -------------------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("CLEAN-SETUP VERIFICATION SUMMARY")
    print("=" * 80)
    passed_count = sum(1 for c in checks if c["status"] == "PASS")
    total_count = len(checks)
    print(f"Total Checks: {total_count}")
    print(f"Passed:       {passed_count}")
    print(f"Failed:       {total_count - passed_count}")
    print("=" * 80)

    if passed_count == total_count:
        print("ALL CLEAN-SETUP REPRODUCIBILITY & HEALTH CHECKS PASSED!")
        return 0
    else:
        print("SOME CLEAN-SETUP CHECKS FAILED — REVIEW OUTPUT ABOVE")
        return 1


if __name__ == "__main__":
    sys.exit(main())
