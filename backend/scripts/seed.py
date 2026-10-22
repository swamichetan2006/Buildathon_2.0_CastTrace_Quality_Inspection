import os
import sys
from typing import Optional
import bcrypt
from sqlalchemy.orm import Session

# Ensure root workspace is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.database import SessionLocal
from backend.app.models.entities import User


def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


DEMO_USERS = [
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
    session_provided = db is not None
    if not session_provided:
        db = SessionLocal()
    try:
        created_count = 0
        updated_count = 0

        print("--- CastTrace AI Seed Script Starting ---")
        for user_data in DEMO_USERS:
            existing_user = db.query(User).filter(User.username == user_data["username"]).first()
            hashed_pw = hash_password(user_data["password"])

            if not existing_user:
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
                existing_user.email = user_data["email"]
                existing_user.full_name = user_data["full_name"]
                existing_user.role = user_data["role"]
                existing_user.hashed_password = hashed_pw
                existing_user.is_active = True
                updated_count += 1
                print(f"[UPDATED] User '{user_data['username']}' with role '{user_data['role']}'")

        db.commit()
        print(f"--- Seeding Completed: {created_count} created, {updated_count} updated ---")
    except Exception as exc:
        db.rollback()
        print(f"Error during seeding: {exc}", file=sys.stderr)
        raise exc
    finally:
        if not session_provided:
            db.close()


if __name__ == "__main__":
    seed_database()
