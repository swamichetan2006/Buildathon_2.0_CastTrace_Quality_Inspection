"""SQLite Database Restoration and Verification Utility for CastTrace AI.

Provides safe, verified database restoration from SQLite backup files.
Features:
1. Pre-flight integrity check on backup file before attempting restoration.
2. Safety backup of existing destination database before overwriting.
3. Official SQLite online backup API restore mechanism.
4. Post-restoration integrity check (PRAGMA integrity_check).
5. Schema and Alembic migration revision verification.
6. Support for target database path override for non-destructive testing.
"""

import os
import sys
import shutil
import sqlite3
import argparse
import datetime
from typing import Optional, List

# Ensure backend can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from app.config import settings

REQUIRED_TABLES = [
    "users",
    "products",
    "batches",
    "inspections",
    "inspection_items",
    "images",
    "model_versions",
    "model_runs",
    "reviews",
    "defects",
    "corrective_actions",
    "reinspections",
    "batch_decisions",
    "audit_log",
    "alembic_version",
]


def parse_sqlite_path(db_url: str) -> str:
    prefix = "sqlite:///"
    if db_url.startswith(prefix):
        return db_url[len(prefix):]
    return "casttrace.db"


def find_latest_backup(backups_dir: str = "backups") -> Optional[str]:
    if not os.path.exists(backups_dir):
        return None
    candidates = [
        os.path.join(backups_dir, f)
        for f in os.listdir(backups_dir)
        if f.startswith("casttrace_backup_") and f.endswith(".db")
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidates[0]


def verify_database_file(db_path: str) -> List[str]:
    """Runs PRAGMA integrity_check and checks for required tables."""
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        raise ValueError(f"Database file '{db_path}' does not exist or is empty.")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA integrity_check;")
        res = cursor.fetchone()
        if not res or res[0] != "ok":
            raise RuntimeError(f"Integrity check failed for '{db_path}': {res}")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        return tables
    finally:
        conn.close()


def restore_database(
    backup_file: str,
    target_db_path: Optional[str] = None,
    create_safety_backup: bool = True,
    required_tables: Optional[List[str]] = None,
) -> str:
    """Restores database from verified backup file using SQLite online backup API."""
    if not os.path.exists(backup_file):
        raise FileNotFoundError(f"Backup file '{backup_file}' was not found.")

    target_path = target_db_path or parse_sqlite_path(settings.DATABASE_URL)
    print(f"=== CastTrace AI Database Restore ===")
    print(f"Source Backup: {backup_file} ({os.path.getsize(backup_file)} bytes)")
    print(f"Target Database: {target_path}")

    # 1. Pre-flight verify the backup file
    print("Step 1/5: Verifying backup file integrity...")
    backup_tables = verify_database_file(backup_file)
    expected_tables = required_tables if required_tables is not None else REQUIRED_TABLES
    missing = [t for t in expected_tables if t not in backup_tables]
    if missing:
        raise RuntimeError(f"Backup file is missing required tables: {missing}")
    print(f"  Backup verified healthy ({len(backup_tables)} tables present, integrity ok).")

    # 2. Safety copy of existing database if it exists
    safety_backup_path = None
    if os.path.exists(target_path) and os.path.getsize(target_path) > 0 and create_safety_backup:
        print("Step 2/5: Creating pre-restore safety copy of existing target database...")
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        target_dir = os.path.dirname(os.path.abspath(target_path)) or "."
        safety_filename = f"{os.path.basename(target_path)}.pre_restore_{timestamp}.bak"
        safety_backup_path = os.path.join(target_dir, safety_filename)

        source_conn = sqlite3.connect(target_path)
        safety_conn = sqlite3.connect(safety_backup_path)
        try:
            source_conn.backup(safety_conn)
            safety_conn.commit()
            print(f"  Pre-restore safety backup preserved at: {safety_backup_path}")
        finally:
            safety_conn.close()
            source_conn.close()
    else:
        print("Step 2/5: Target database does not exist or safety backup skipped.")

    # 3. Perform atomic restoration
    print("Step 3/5: Restoring database content via SQLite backup API...")
    backup_conn = sqlite3.connect(backup_file)
    dest_conn = sqlite3.connect(target_path)
    try:
        backup_conn.backup(dest_conn)
        dest_conn.commit()
    finally:
        dest_conn.close()
        backup_conn.close()

    # 4. Post-restoration verification
    print("Step 4/5: Verifying restored target database...")
    restored_tables = verify_database_file(target_path)
    print(f"  Restored database verified healthy ({len(restored_tables)} tables present).")

    # 5. Check Alembic migration head
    print("Step 5/5: Checking Alembic revision in restored database...")
    check_conn = sqlite3.connect(target_path)
    cursor = check_conn.cursor()
    alembic_version = None
    try:
        cursor.execute("SELECT version_num FROM alembic_version;")
        row = cursor.fetchone()
        alembic_version = row[0] if row else "None"
        print(f"  Alembic Migration Version: {alembic_version}")
    except Exception as e:
        print(f"  Warning: Could not read alembic_version: {e}")
    finally:
        check_conn.close()

    print(f"SUCCESS: Database restored successfully to '{target_path}'.")
    return target_path


def main():
    parser = argparse.ArgumentParser(description="Restore CastTrace AI SQLite database from backup")
    parser.add_argument(
        "--backup-file",
        type=str,
        default=None,
        help="Path to specific backup .db file (defaults to latest in backups/)",
    )
    parser.add_argument(
        "--target-db",
        type=str,
        default=None,
        help="Custom destination SQLite path (useful for testing restore non-destructively)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate the backup file without restoring",
    )
    parser.add_argument(
        "--no-safety-backup",
        action="store_true",
        help="Skip creating a pre-restore safety copy of the existing target database",
    )
    args = parser.parse_args()

    backup_path = args.backup_file or find_latest_backup()
    if not backup_path:
        print("ERROR: No backup file specified and no backup files found in 'backups/' directory.", file=sys.stderr)
        print("Create a backup first with: python scripts/backup_database.py", file=sys.stderr)
        sys.exit(1)

    if args.check_only:
        print(f"Validating backup file: {backup_path}")
        try:
            tables = verify_database_file(backup_path)
            print(f"VALID: Backup integrity ok. Contains {len(tables)} tables: {', '.join(sorted(tables))}")
            sys.exit(0)
        except Exception as e:
            print(f"INVALID: Backup check failed: {e}", file=sys.stderr)
            sys.exit(1)

    try:
        restore_database(
            backup_file=backup_path,
            target_db_path=args.target_db,
            create_safety_backup=not args.no_safety_backup,
        )
    except Exception as e:
        print(f"ERROR: Restore failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
