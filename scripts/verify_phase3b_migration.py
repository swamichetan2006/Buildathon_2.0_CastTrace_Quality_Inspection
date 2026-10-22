import sqlite3

conn = sqlite3.connect("casttrace.db")
c = conn.cursor()
c.execute("SELECT sql FROM sqlite_master WHERE name='uq_active_model_run'")
row = c.fetchone()
print("uq_active_model_run SQL:", row[0] if row else None)

# Verify worker_heartbeats exists
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='worker_heartbeats'")
print("worker_heartbeats table exists:", bool(c.fetchone()))

# Test partial unique index functionality
try:
    c.execute("BEGIN TRANSACTION")
    # Insert test image / version
    c.execute("INSERT INTO users (id, username, email, hashed_password, full_name, role, is_active, created_at, updated_at) VALUES ('u1', 'user1', 'u@test.com', 'hash', 'User', 'INSPECTOR', 1, '2026-10-22', '2026-10-22')")
    c.execute("INSERT INTO products (id, sku, name, material, is_archived, created_at, updated_at) VALUES ('p1', 'SKU-1', 'Impeller', 'Cast Iron', 0, '2026-10-22', '2026-10-22')")
    c.execute("INSERT INTO batches (id, batch_number, product_id, manufacture_date, declared_quantity, status, created_by, created_at, updated_at) VALUES ('b1', 'B-1', 'p1', '2026-10-22', 10, 'IN_PRODUCTION', 'u1', '2026-10-22', '2026-10-22')")
    c.execute("INSERT INTO inspections (id, inspection_number, batch_id, inspector_id, stage, status, sampling_plan, started_at, created_at, updated_at) VALUES ('ins1', 'INS-1', 'b1', 'u1', 'STAGING', 'IN_PROGRESS', 'NORMAL', '2026-10-22', '2026-10-22', '2026-10-22')")
    c.execute("INSERT INTO inspection_items (id, inspection_id, item_identifier, status, created_at, updated_at) VALUES ('it1', 'ins1', 'ITEM-1', 'PENDING', '2026-10-22', '2026-10-22')")
    c.execute("INSERT INTO images (id, inspection_item_id, batch_id, image_scope, represented_item_count, storage_path, original_filename, mime_type, file_size_bytes, sha256_hash, is_superseded, uploaded_by, created_at) VALUES ('img1', 'it1', 'b1', 'ITEM', 1, 'storage/test.jpg', 'test.jpg', 'image/jpeg', 100, 'hash', 0, 'u1', '2026-10-22')")
    c.execute("INSERT INTO model_versions (id, version_name, model_architecture, weights_path, training_dataset_info, metrics, is_active, created_at) VALUES ('mv1', 'v1', 'resnet18', 'weights.pt', '{}', '{}', 1, '2026-10-22')")

    # 1. First QUEUED job
    c.execute("INSERT INTO model_runs (id, logical_run_id, image_id, model_version_id, status, score_type, threshold_applied, attempt_number, created_at) VALUES ('r1', 'l1', 'img1', 'mv1', 'QUEUED', 'PROBABILITY_DEFECTIVE', 0.5, 1, '2026-10-22')")

    # 2. Duplicate QUEUED job must raise IntegrityError
    dup_raised = False
    try:
        c.execute("INSERT INTO model_runs (id, logical_run_id, image_id, model_version_id, status, score_type, threshold_applied, attempt_number, created_at) VALUES ('r2', 'l2', 'img1', 'mv1', 'QUEUED', 'PROBABILITY_DEFECTIVE', 0.5, 1, '2026-10-22')")
    except sqlite3.IntegrityError:
        dup_raised = True
    print("Duplicate active job rejected by partial unique index:", dup_raised)
    assert dup_raised, "Expected partial unique index to reject second active job for same image & version"

    # 3. If first job is SUCCEEDED, a new job CAN be enqueued
    c.execute("UPDATE model_runs SET status = 'SUCCEEDED' WHERE id = 'r1'")
    c.execute("INSERT INTO model_runs (id, logical_run_id, image_id, model_version_id, status, score_type, threshold_applied, attempt_number, created_at) VALUES ('r3', 'l3', 'img1', 'mv1', 'QUEUED', 'PROBABILITY_DEFECTIVE', 0.5, 1, '2026-10-22')")
    print("New job allowed after previous completed: True")

    conn.rollback() # Rollback test data to keep database clean
    print("Database verification passed successfully!")
finally:
    conn.close()
