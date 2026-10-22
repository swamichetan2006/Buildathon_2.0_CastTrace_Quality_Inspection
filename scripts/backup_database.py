import os
import sys
import sqlite3
import datetime
from urllib.parse import urlparse

# Ensure backend can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from app.config import settings

from typing import Optional, List

def backup_database(destination_dir: str = "backups", source_db: Optional[str] = None, required_tables: Optional[List[str]] = None) -> str:
    """Create a verified, timestamped, WAL-safe database backup."""
    os.makedirs(destination_dir, exist_ok=True)

    if source_db:
        db_path = source_db
    else:
        db_url = settings.DATABASE_URL
        if db_url.startswith("sqlite"):
            prefix = "sqlite:///"
            if db_url.startswith(prefix):
                db_path = db_url[len(prefix):]
            else:
                db_path = "casttrace.db"
        else:
            raise NotImplementedError("PostgreSQL database backup requires pg_dump utility.")

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Source database file not found at '{db_path}'. Cannot perform backup.")

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_filename = f"casttrace_backup_{timestamp}.db"
    backup_path = os.path.join(destination_dir, backup_filename)

    print(f"Initiating WAL-safe SQLite backup to {backup_path}...")
    source_conn = sqlite3.connect(db_path)
    dest_conn = sqlite3.connect(backup_path)

    try:
        # Official WAL-safe online backup API
        source_conn.backup(dest_conn)
        dest_conn.commit()
    finally:
        dest_conn.close()
        source_conn.close()

    # Verify backup integrity
    verify_conn = sqlite3.connect(backup_path)
    cursor = verify_conn.cursor()
    cursor.execute("PRAGMA integrity_check;")
    result = cursor.fetchone()
    if not result or result[0] != "ok":
        raise RuntimeError(f"Backup integrity check failed: {result}")

    # Verify application tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    check_tables = required_tables if required_tables is not None else ["users", "products", "batches", "inspections", "images", "model_versions", "model_runs"]
    missing = [t for t in check_tables if t not in tables]
    if missing:
        raise RuntimeError(f"Backup missing required application tables: {missing}")

    verify_conn.close()
    sz = os.path.getsize(backup_path)
    print(f"SUCCESS: Database backup created and verified ({sz} bytes, {len(tables)} tables present).")
    return backup_path

# Alias for backwards-compatibility or alternate naming conventions
create_backup = backup_database

if __name__ == "__main__":
    try:
        backup_path = backup_database()
        print(f"Backup file: {backup_path}")
    except Exception as e:
        print(f"ERROR: Backup failed: {e}", file=sys.stderr)
        sys.exit(1)
