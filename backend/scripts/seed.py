import os
import sys
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

# Ensure root workspace is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.config import settings
from backend.app.core.security import hash_password, verify_password
from backend.app.database import SessionLocal
from backend.app.models.entities import User


DEMO_USERS = [
    {
        "username": "inspector@casttrace.demo",
        "email": "inspector@casttrace.demo",
        "full_name": "Inspector (QA Station)",
        "role": "INSPECTOR",
        "password": "Inspect@123",
    },
    {
        "username": "supervisor@casttrace.demo",
        "email": "supervisor@casttrace.demo",
        "full_name": "Supervisor (Production)",
        "role": "SUPERVISOR",
        "password": "Supervise@123",
    },
    {
        "username": "quality@casttrace.demo",
        "email": "quality@casttrace.demo",
        "full_name": "Quality Manager (Governance)",
        "role": "QUALITY_MANAGER",
        "password": "Quality@123",
    },
    # Retain legacy personas for backward compatibility with integration tests
    {
        "username": "inspector_chen",
        "email": "inspector.chen@casttrace.local",
        "full_name": "David Chen",
        "role": "INSPECTOR",
        "password": "Password123!",
    },
    {
        "username": "supervisor_torres",
        "email": "supervisor.torres@casttrace.local",
        "full_name": "Elena Torres",
        "role": "SUPERVISOR",
        "password": "Password123!",
    },
    {
        "username": "qm_reynolds",
        "email": "qm.reynolds@casttrace.local",
        "full_name": "Dr. Edward Reynolds",
        "role": "QUALITY_MANAGER",
        "password": "Password123!",
    },
]


def seed_database(db: Optional[Session] = None) -> None:
    if settings.APP_ENV == "production" and not os.environ.get("ALLOW_PRODUCTION_DEMO_SEED"):
        print("Demo seeding skipped in production environment.", file=sys.stderr)
        return

    session_provided = db is not None
    if not session_provided:
        db = SessionLocal()
    try:
        created_count = 0
        updated_count = 0
        idempotent_count = 0

        print("--- CastTrace AI Seed Script Starting ---")
        for user_data in DEMO_USERS:
            existing_user = db.query(User).filter(
                or_(User.username == user_data["username"], User.email == user_data["email"])
            ).first()

            if not existing_user:
                hashed_pw = hash_password(user_data["password"])
                new_user = User(
                    username=user_data["username"],
                    email=user_data["email"],
                    full_name=user_data["full_name"],
                    role=user_data["role"],
                    hashed_password=hashed_pw,
                    is_active=True,
                )
                db.add(new_user)
                created_count += 1
                print(f"[CREATED] User '{user_data['username']}' with role '{user_data['role']}'")
            else:
                updated = False
                if existing_user.role != user_data["role"]:
                    existing_user.role = user_data["role"]
                    updated = True
                if existing_user.full_name != user_data["full_name"]:
                    existing_user.full_name = user_data["full_name"]
                    updated = True
                if not existing_user.is_active:
                    existing_user.is_active = True
                    updated = True
                if not verify_password(user_data["password"], existing_user.hashed_password):
                    existing_user.hashed_password = hash_password(user_data["password"])
                    updated = True

                if updated:
                    updated_count += 1
                    print(f"[UPDATED] User '{user_data['username']}' with role '{user_data['role']}'")
                else:
                    idempotent_count += 1
                    print(f"[UNCHANGED] User '{user_data['username']}' already up to date")

        db.commit()
        print(f"--- Seeding Completed: {created_count} created, {updated_count} updated, {idempotent_count} unchanged ---")
    except Exception as exc:
        db.rollback()
        print(f"Error during seeding: {exc}", file=sys.stderr)
        raise exc
    finally:
        if not session_provided:
            db.close()


if __name__ == "__main__":
    seed_database()
