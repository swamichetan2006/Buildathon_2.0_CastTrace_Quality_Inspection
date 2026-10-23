"""
CastTrace AI — SQLite to PostgreSQL Data Migration Script
Repeatable, idempotent, transactional migration preserving primary keys,
foreign keys, timestamps, JSON attributes, audit ledger, and relationships.
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, date
from typing import Dict, List, Any, Optional

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

# Ensure backend path is available
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# pyrefly: ignore[missing-import]
from backend.app.config import settings

# Ordered tables preserving dependency graph
TABLE_ORDER = [
    "users",
    "products",
    "model_versions",
    "batches",
    "inspections",
    "inspection_items",
    "images",
    "model_runs",
    "worker_heartbeats",
    "reviews",
    "defects",
    "corrective_actions",
    "reinspections",
    "batch_decisions",
    "audit_log",
    "idempotency_keys",
    "genai_queries",
]


def clean_val(val: Any) -> Any:
    """Ensure data types conform across SQLite and PostgreSQL."""
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return json.dumps(val)
    return val


def migrate_data(sqlite_path: str = "casttrace.db", target_db_url: Optional[str] = None) -> Dict[str, Dict[str, int]]:
    """Migrates all rows from SQLite to PostgreSQL transactionally and idempotently."""
    if not os.path.exists(sqlite_path):
        raise FileNotFoundError(f"Source SQLite database not found at: {sqlite_path}")

    dest_url = target_db_url or settings.DATABASE_URL
    if not dest_url.startswith("postgresql"):
        raise ValueError(f"Target DATABASE_URL must be PostgreSQL, got: {dest_url}")

    print(f"Connecting to source SQLite: {sqlite_path}")
    sqlite_conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    print(f"Connecting to target PostgreSQL: {dest_url.split('@')[-1] if '@' in dest_url else dest_url}")
    pg_engine = create_engine(dest_url)
    inspector = inspect(pg_engine)

    results = {}

    with pg_engine.begin() as pg_conn:
        # Check if user has superuser to use session_replication_role
        has_replica_role = False
        try:
            pg_conn.execute(text("SET session_replication_role = 'replica';"))
            has_replica_role = True
        except Exception:
            print("Note: Running without session_replication_role (standard user mode).")

        for table in TABLE_ORDER:
            # Check if table exists in SQLite
            sqlite_cur.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='{table}';")
            if sqlite_cur.fetchone()[0] == 0:
                results[table] = {"source": 0, "target": 0}
                continue

            # Fetch source records
            sqlite_cur.execute(f'SELECT * FROM "{table}"')
            rows = sqlite_cur.fetchall()
            source_count = len(rows)

            if source_count == 0:
                # Count current in target
                cur_pg_count = pg_conn.execute(text(f'SELECT COUNT(*) FROM "{table}";')).scalar()
                results[table] = {"source": 0, "target": cur_pg_count}
                continue

            col_names = [col[0] for col in sqlite_cur.description]
            primary_key = "id" if "id" in col_names else col_names[0]

            # Upsert into PostgreSQL
            cols_clause = ", ".join([f'"{c}"' for c in col_names])
            params_clause = ", ".join([f":{c}" for c in col_names])
            update_clause = ", ".join([f'"{c}" = EXCLUDED."{c}"' for c in col_names if c != primary_key])

            if update_clause:
                upsert_sql = f"""
                    INSERT INTO "{table}" ({cols_clause})
                    VALUES ({params_clause})
                    ON CONFLICT ("{primary_key}") DO UPDATE
                    SET {update_clause};
                """
            else:
                upsert_sql = f"""
                    INSERT INTO "{table}" ({cols_clause})
                    VALUES ({params_clause})
                    ON CONFLICT ("{primary_key}") DO NOTHING;
                """

            # Inspect column types from PostgreSQL
            pg_col_types = {col["name"]: str(col["type"]).upper() for col in inspector.get_columns(table)}

            # Prepare parameters with strict type casting
            records_data = []
            for row in rows:
                record = {}
                for col in col_names:
                    val = row[col]
                    col_type = pg_col_types.get(col, "")

                    if val is not None:
                        # 1. Cast boolean
                        if "BOOLEAN" in col_type:
                            val = bool(val)
                        # 2. Format JSON
                        elif "JSON" in col_type:
                            if isinstance(val, (dict, list)):
                                val = json.dumps(val)
                            elif isinstance(val, str):
                                try:
                                    json.loads(val)
                                except Exception:
                                    val = json.dumps(val)
                        # 3. Parse DateTime
                        elif "TIMESTAMP" in col_type or "DATETIME" in col_type:
                            if isinstance(val, str):
                                try:
                                    val = datetime.fromisoformat(val)
                                except Exception:
                                    pass
                        # 4. Parse Date
                        elif col_type == "DATE":
                            if isinstance(val, str):
                                try:
                                    val = date.fromisoformat(val.split("T")[0].split(" ")[0])
                                except Exception:
                                    pass

                    record[col] = val
                records_data.append(record)

            # Execute batch insert
            pg_conn.execute(text(upsert_sql), records_data)

            # Query destination count
            target_count = pg_conn.execute(text(f'SELECT COUNT(*) FROM "{table}";')).scalar()
            results[table] = {"source": source_count, "target": target_count}
            print(f"  [OK] {table}: migrated {source_count} rows -> {target_count} total in target.")

        if has_replica_role:
            pg_conn.execute(text("SET session_replication_role = 'origin';"))

    sqlite_conn.close()
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate CastTrace AI SQLite database to PostgreSQL")
    parser.add_argument("--source", default="casttrace.db", help="Source SQLite database path")
    parser.add_argument("--target", default=None, help="Target PostgreSQL connection URL (defaults to DATABASE_URL in .env)")
    args = parser.parse_args()

    print("=================================================================")
    print(" CastTrace AI — SQLite to PostgreSQL Migration Runner")
    print("=================================================================")
    try:
        report = migrate_data(sqlite_path=args.source, target_db_url=args.target)
        print("\n=================== MIGRATION SUMMARY ===================")
        print(f"{'Table':<25} {'Source Rows':<15} {'Target Rows':<15} {'Status'}")
        print("-" * 65)
        all_match = True
        for tbl, counts in report.items():
            src = counts["source"]
            tgt = counts["target"]
            status = "MATCH" if tgt >= src else "MISMATCH"
            if status != "MATCH":
                all_match = False
            print(f"{tbl:<25} {src:<15} {tgt:<15} {status}")
        print("-" * 65)
        if all_match:
            print("SUCCESS: All SQLite tables migrated and verified in PostgreSQL.")
        else:
            print("WARNING: Row count discrepancies detected. Please review logs.")
    except Exception as e:
        print(f"\nERROR: Migration failed: {e}")
        sys.exit(1)
