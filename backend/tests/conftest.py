import os
import shutil
import tempfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.app.config import settings
from backend.app.core.security import create_access_token, hash_password
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models.entities import User, ModelVersion

# Require TEST_DATABASE_URL to be explicitly configured and use PostgreSQL
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or settings.TEST_DATABASE_URL

if not TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL is not set. A PostgreSQL test database is required. "
        "SQLite is not supported. Please set TEST_DATABASE_URL in .env"
    )

if not (TEST_DATABASE_URL.startswith("postgresql://") or TEST_DATABASE_URL.startswith("postgresql+")):
    raise RuntimeError(
        f"TEST_DATABASE_URL must be a PostgreSQL connection string (postgresql://...). Got: {TEST_DATABASE_URL}. "
        "SQLite and other non-PostgreSQL databases are completely disabled."
    )

# Safeguard: Never run tests against the main development database
dev_db = settings.DATABASE_URL
if dev_db and TEST_DATABASE_URL == dev_db:
    raise RuntimeError(
        f"CRITICAL SAFETY CHECK FAILED: TEST_DATABASE_URL ({TEST_DATABASE_URL}) cannot be identical to DATABASE_URL ({dev_db}). "
        "Tests must run in a dedicated, isolated test database to protect development data."
    )

test_engine = create_engine(
    TEST_DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
    future=True,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def _seed_default_model_version(session):
    mv = session.query(ModelVersion).filter(
        (ModelVersion.id == "mv-resnet18-v1") | (ModelVersion.version_name == "v1.0.0-resnet18")
    ).first()
    if not mv:
        mv = ModelVersion(
            id="mv-resnet18-v1",
            version_name="v1.0.0-resnet18",
            model_architecture="ResNet-18",
            weights_path="ml/artifacts/model_best.pt",
            training_dataset_info={"source": "test_dataset"},
            metrics={"accuracy": 1.0},
            is_active=True,
        )
        session.add(mv)
        session.commit()


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    # Verify PostgreSQL connectivity
    try:
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise RuntimeError(
            f"Failed to connect to PostgreSQL test database at {TEST_DATABASE_URL}. "
            f"Ensure PostgreSQL is running and the database exists. Error: {exc}"
        ) from exc

    Base.metadata.create_all(bind=test_engine)
    with TestingSessionLocal() as session:
        _seed_default_model_version(session)
    yield
    # Clean up schema objects on session teardown
    try:
        with test_engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    except Exception:
        pass


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
        # Truncate tables between tests for complete test isolation without dropping schemas
        try:
            with test_engine.begin() as conn:
                table_names = [f'"{table.name}"' for table in Base.metadata.sorted_tables if table.name != "model_versions"]
                if table_names:
                    conn.execute(text(f"TRUNCATE TABLE {', '.join(table_names)} RESTART IDENTITY CASCADE;"))
        except Exception:
            pass


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def temp_storage(tmp_path, monkeypatch):
    storage_dir = str(tmp_path / "storage" / "evidence")
    os.makedirs(storage_dir, exist_ok=True)
    monkeypatch.setattr(settings, "STORAGE_DIR", storage_dir)
    return storage_dir


@pytest.fixture
def seeded_users(db_session):
    users = {}
    roles = [
        ("test_inspector", "inspector@casttrace.local", "INSPECTOR"),
        ("test_supervisor", "supervisor@casttrace.local", "SUPERVISOR"),
        ("test_qm", "qm@casttrace.local", "QUALITY_MANAGER"),
    ]
    for username, email, role in roles:
        u = db_session.query(User).filter(User.username == username).first()
        if not u:
            u = User(
                username=username,
                email=email,
                full_name=f"Test {role}",
                role=role,
                hashed_password=hash_password("Password123!"),
                is_active=True,
            )
            db_session.add(u)
            db_session.commit()
            db_session.refresh(u)
        users[role] = u
    return users


@pytest.fixture
def inspector_headers(seeded_users):
    user = seeded_users["INSPECTOR"]
    token = create_access_token({"sub": user.id, "username": user.username, "role": user.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def supervisor_headers(seeded_users):
    user = seeded_users["SUPERVISOR"]
    token = create_access_token({"sub": user.id, "username": user.username, "role": user.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def qm_headers(seeded_users):
    user = seeded_users["QUALITY_MANAGER"]
    token = create_access_token({"sub": user.id, "username": user.username, "role": user.role})
    return {"Authorization": f"Bearer {token}"}
