import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.app.database import SessionLocal
from backend.app.services.model_registration import register_approved_model_version

def main():
    db = SessionLocal()
    try:
        model_ver = register_approved_model_version(db)
        print(f"Registered model version: {model_ver.version_name} (ID: {model_ver.id}, Architecture: {model_ver.model_architecture}, Active: {model_ver.is_active})")
    finally:
        db.close()

if __name__ == "__main__":
    main()
