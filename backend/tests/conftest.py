import os
import shutil
import tempfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.config import settings
from backend.app.core.security import create_access_token, hash_password
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models.entities import User

# Test database URL
TEST_DATABASE_URL = "sqlite:///./casttrace_test.db"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists("./casttrace_test.db"):
        try:
            os.remove("./casttrace_test.db")
        except OSError:
            pass


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


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
