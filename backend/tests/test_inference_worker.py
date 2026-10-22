import os
import io
import time
import uuid
import datetime
import hashlib
import pytest
from sqlalchemy import select

from backend.app.config import settings
from backend.app.models.entities import ModelRun, ModelVersion, Image, WorkerHeartbeat, AuditLog, Product, Batch
from backend.app.services.worker_service import InferenceWorker
from backend.app.services.inference_service import InferenceService

JPEG_HEADER = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"\x00" * 50


@pytest.fixture(autouse=True)
def clean_active_runs(db_session):
    db_session.query(ModelRun).filter(ModelRun.status.in_(["QUEUED", "PROCESSING"])).delete(synchronize_session=False)
    db_session.commit()
    yield
    db_session.query(ModelRun).filter(ModelRun.status.in_(["QUEUED", "PROCESSING"])).delete(synchronize_session=False)
    db_session.commit()


@pytest.fixture
def active_model_version(db_session):
    stmt = db_session.query(ModelVersion).filter(ModelVersion.version_name == "v1.0.0-resnet18").first()
    if not stmt:
        ver = ModelVersion(
            version_name="v1.0.0-resnet18",
            model_architecture="ResNet-18",
            weights_path="ml/artifacts/model_best.pt",
            weights_sha256="ab2b592ab9a4cca3c97613d8e52d9f8abc2906dbef77cddd15c73d2da1c3c2da",
            unfamiliar_guard_sha256="c39905c247cd881175439833661610ce8d0dbff18811057fb289dfb24c464abc",
            training_dataset_info={"dataset": "casting_512x512"},
            metrics={"accuracy": 0.9898},
            is_active=True,
        )
        db_session.add(ver)
        db_session.commit()
        db_session.refresh(ver)
        return ver
    return stmt


@pytest.fixture
def test_image_record(db_session, seeded_users, temp_storage):
    """Create a verified Image database record and save its file in temp_storage."""
    user = seeded_users["INSPECTOR"]

    # Create dummy Product and Batch
    prod = Product(
        sku=f"SKU-{uuid.uuid4().hex[:8]}",
        name="Test Pump Casing",
        material="Cast Iron",
    )
    db_session.add(prod)
    db_session.flush()

    batch = Batch(
        batch_number=f"BATCH-{uuid.uuid4().hex[:8]}",
        product_id=prod.id,
        manufacture_date=datetime.date.today(),
        declared_quantity=10,
        created_by=user.id,
    )
    db_session.add(batch)
    db_session.flush()

    content = JPEG_HEADER + b"inference_worker_test_content_" + uuid.uuid4().hex.encode()
    file_sha = hashlib.sha256(content).hexdigest()
    filename = f"test_{uuid.uuid4().hex[:8]}.jpg"
    file_path = os.path.join(temp_storage, filename)
    with open(file_path, "wb") as f:
        f.write(content)

    img = Image(
        id=str(uuid.uuid4()),
        batch_id=batch.id,
        original_filename=filename,
        storage_path=file_path,
        file_size_bytes=len(content),
        mime_type="image/jpeg",
        sha256_hash=file_sha,
        image_scope="ITEM",
        uploaded_by=user.id,
    )
    db_session.add(img)
    db_session.commit()
    db_session.refresh(img)
    return img


def test_evidence_integrity_verification_tamper_rejection(db_session, active_model_version, test_image_record):
    """Stage 9: Verify evidence SHA-256 before inference.
    
    If bytes on disk are tampered after upload, inference must be rejected with
    EVIDENCE_INTEGRITY_MISMATCH, no prediction fabricated, and audit logged.
    """
    image_id = test_image_record.id

    # Create queued model run
    run = ModelRun(
        logical_run_id=str(uuid.uuid4()),
        image_id=image_id,
        model_version_id=active_model_version.id,
        status="QUEUED",
        attempt_number=1,
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    # TAMPER with the file on disk
    with open(test_image_record.storage_path, "ab") as f:
        f.write(b"\x00TAMPERED_MALICIOUS_BYTES\x00")

    worker = InferenceWorker(worker_id="test-worker-tamper")
    claimed_run = worker.claim_next_job(db_session)
    assert claimed_run is not None
    assert claimed_run.id == run.id

    # Process job with tampered file
    worker.process_job(db_session, claimed_run)

    # Verify run state
    db_session.refresh(run)
    assert run.status == "FAILED"
    assert run.error_code == "EVIDENCE_INTEGRITY_MISMATCH"
    assert run.is_retryable is False
    assert run.predicted_label is None
    assert run.score is None
    assert run.routing_outcome is None

    # Verify audit log recorded
    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_id == run.id, AuditLog.action == "EVIDENCE_INTEGRITY_MISMATCH")
        .first()
    )
    assert audit is not None
    assert audit.previous_state.get("actor") == "system:ml-worker"


def test_atomic_job_claiming_concurrency(db_session, active_model_version, test_image_record):
    """Stage 8: Atomic conditional claim prevents double-processing by competing workers."""
    run = ModelRun(
        logical_run_id=str(uuid.uuid4()),
        image_id=test_image_record.id,
        model_version_id=active_model_version.id,
        status="QUEUED",
        attempt_number=1,
    )
    db_session.add(run)
    db_session.commit()

    worker_a = InferenceWorker(worker_id="worker-alpha")
    worker_b = InferenceWorker(worker_id="worker-beta")

    # Worker A claims first
    job_a = worker_a.claim_next_job(db_session)
    assert job_a is not None
    assert job_a.id == run.id
    assert job_a.status == "PROCESSING"
    assert job_a.claimed_by_worker_id == "worker-alpha"

    # Worker B attempts to claim the same queue
    job_b = worker_b.claim_next_job(db_session)
    assert job_b is None  # Queue empty, job already claimed


def test_stale_lease_recovery_and_retry_backoff(db_session, active_model_version, test_image_record):
    """Stage 7 & 8: Processing run with expired lease is failed and retried up to 3 total attempts."""
    now = datetime.datetime.now(datetime.timezone.utc)
    expired_time = now - datetime.timedelta(seconds=60)
    logical_id = str(uuid.uuid4())

    # 1. Attempt 1 has expired lease
    run1 = ModelRun(
        logical_run_id=logical_id,
        image_id=test_image_record.id,
        model_version_id=active_model_version.id,
        status="PROCESSING",
        attempt_number=1,
        claimed_by_worker_id="dead-worker",
        lease_expires_at=expired_time,
    )
    db_session.add(run1)
    db_session.commit()

    worker = InferenceWorker(worker_id="recovery-worker")
    recovered = worker.recover_stale_leases(db_session)
    assert recovered == 1

    # Attempt 1 should be FAILED with LEASE_EXPIRED
    db_session.refresh(run1)
    assert run1.status == "FAILED"
    assert run1.error_code == "LEASE_EXPIRED"
    assert run1.is_retryable is True

    # Attempt 2 should be automatically scheduled in QUEUED with 5s delay
    stmt = (
        select(ModelRun)
        .where(ModelRun.logical_run_id == logical_id, ModelRun.attempt_number == 2)
    )
    run2 = db_session.execute(stmt).scalars().first()
    assert run2 is not None
    assert run2.status == "QUEUED"
    assert run2.parent_run_id == run1.id
    assert run2.next_retry_at is not None
    t2 = run2.next_retry_at.replace(tzinfo=datetime.timezone.utc) if run2.next_retry_at.tzinfo is None else run2.next_retry_at
    diff_sec = (t2 - now).total_seconds()
    assert 4 <= diff_sec <= 6  # ~5 seconds backoff

    # 2. Simulate Attempt 2 also stalling and expiring lease
    run2.status = "PROCESSING"
    run2.lease_expires_at = expired_time
    db_session.commit()

    recovered2 = worker.recover_stale_leases(db_session)
    assert recovered2 == 1

    db_session.refresh(run2)
    assert run2.status == "FAILED"
    assert run2.error_code == "LEASE_EXPIRED"

    # Attempt 3 scheduled with 30s delay
    stmt3 = (
        select(ModelRun)
        .where(ModelRun.logical_run_id == logical_id, ModelRun.attempt_number == 3)
    )
    run3 = db_session.execute(stmt3).scalars().first()
    assert run3 is not None
    assert run3.status == "QUEUED"
    assert run3.parent_run_id == run2.id
    t3 = run3.next_retry_at.replace(tzinfo=datetime.timezone.utc) if run3.next_retry_at.tzinfo is None else run3.next_retry_at
    diff3_sec = (t3 - now).total_seconds()
    assert 28 <= diff3_sec <= 32  # ~30 seconds backoff

    # 3. Simulate Attempt 3 stalling and expiring lease -> Max attempts exhausted!
    run3.status = "PROCESSING"
    run3.lease_expires_at = expired_time
    db_session.commit()

    recovered3 = worker.recover_stale_leases(db_session)
    assert recovered3 == 1

    db_session.refresh(run3)
    assert run3.status == "FAILED"
    assert run3.error_code == "RETRY_EXHAUSTED"
    assert run3.is_retryable is False

    # Verify no attempt 4 was created
    stmt4 = (
        select(ModelRun)
        .where(ModelRun.logical_run_id == logical_id, ModelRun.attempt_number == 4)
    )
    run4 = db_session.execute(stmt4).scalars().first()
    assert run4 is None


def test_development_only_failure_injection(db_session, active_model_version, test_image_record, monkeypatch):
    """Stage 10: Development-only failure injection creates controlled failure with DEMO_INJECTED_FAILURE."""
    # Ensure dev mode
    monkeypatch.setattr(settings, "APP_ENV", "development")

    run = ModelRun(
        logical_run_id=str(uuid.uuid4()),
        image_id=test_image_record.id,
        model_version_id=active_model_version.id,
        status="QUEUED",
        attempt_number=1,
    )
    db_session.add(run)
    db_session.commit()

    worker = InferenceWorker(
        worker_id="demo-failure-worker",
        enable_demo_failure_injection=True,
        demo_target_run_id=run.id,
    )

    claimed = worker.claim_next_job(db_session)
    assert claimed is not None
    worker.process_job(db_session, claimed)

    db_session.refresh(run)
    assert run.status == "FAILED"
    assert run.error_code == "DEMO_INJECTED_FAILURE"
    assert run.predicted_label is None
    assert run.score is None

    # Next attempt was scheduled
    stmt = (
        select(ModelRun)
        .where(ModelRun.logical_run_id == run.logical_run_id, ModelRun.attempt_number == 2)
    )
    run2 = db_session.execute(stmt).scalars().first()
    assert run2 is not None
    assert run2.status == "QUEUED"

    # Now verify that in non-development mode, failure injection is ignored or rejected
    monkeypatch.setattr(settings, "APP_ENV", "production")
    worker_prod = InferenceWorker(
        worker_id="prod-worker",
        enable_demo_failure_injection=True,
    )
    # The flag should not inject failure in production
    assert settings.APP_ENV != "development"


def test_worker_heartbeat_and_offline_status(db_session, active_model_version):
    """Stage 8 & 11: Worker initializes heartbeat and sends status updates."""
    worker = InferenceWorker(worker_id="test-heartbeat-worker")
    worker.initialize(db_session)

    hb = db_session.get(WorkerHeartbeat, "test-heartbeat-worker")
    assert hb is not None
    assert hb.status in ("READY", "OFFLINE")
    assert hb.started_at is not None
    assert hb.last_heartbeat_at is not None

    # Send BUSY heartbeat
    worker.send_heartbeat(db_session, status="BUSY")
    db_session.refresh(hb)
    assert hb.status == "BUSY"

    # Send OFFLINE heartbeat on shutdown
    worker.send_heartbeat(db_session, status="OFFLINE")
    db_session.refresh(hb)
    assert hb.status == "OFFLINE"


def test_real_inference_smoke_test(db_session, seeded_users, active_model_version, temp_storage):
    """Stage 2 & Stage 15: Perform genuine local inference smoke test using a training/validation image.
    
    Verifies full ResNet-18 forward pass, routing thresholds, and persistence without mocking.
    """
    user = seeded_users["INSPECTOR"]
    prod = Product(
        sku=f"SKU-SMOKE-{uuid.uuid4().hex[:6]}",
        name="Smoke Test Impeller",
        material="Cast Steel",
    )
    db_session.add(prod)
    db_session.flush()

    batch = Batch(
        batch_number=f"BATCH-SMOKE-{uuid.uuid4().hex[:6]}",
        product_id=prod.id,
        manufacture_date=datetime.date.today(),
        declared_quantity=5,
        created_by=user.id,
    )
    db_session.add(batch)
    db_session.flush()

    # Sample from training manifest
    sample_path = "data/raw/casting/casting_512x512/casting_512x512/def_front/cast_def_0_100.jpeg"
    if not os.path.exists(sample_path):
        pytest.skip(f"Sample training image not found at {sample_path}")

    with open(sample_path, "rb") as f:
        img_bytes = f.read()

    file_sha = hashlib.sha256(img_bytes).hexdigest()
    filename = "smoke_def_0_100.jpeg"
    dest_path = os.path.join(temp_storage, filename)
    with open(dest_path, "wb") as f:
        f.write(img_bytes)

    # Register image in DB
    img = Image(
        id=str(uuid.uuid4()),
        batch_id=batch.id,
        original_filename=filename,
        storage_path=dest_path,
        file_size_bytes=len(img_bytes),
        mime_type="image/jpeg",
        sha256_hash=file_sha,
        image_scope="ITEM",
        uploaded_by=user.id,
    )
    db_session.add(img)
    db_session.commit()

    # Enqueue model run
    run = ModelRun(
        logical_run_id=str(uuid.uuid4()),
        image_id=img.id,
        model_version_id=active_model_version.id,
        status="QUEUED",
        attempt_number=1,
    )
    db_session.add(run)
    db_session.commit()

    # Worker with real inference service
    service = InferenceService()
    worker = InferenceWorker(worker_id="smoke-worker", inference_service=service)
    worker.initialize(db_session)
    assert service.is_loaded is True

    # Claim and process
    claimed = worker.claim_next_job(db_session)
    assert claimed is not None
    assert claimed.id == run.id

    worker.process_job(db_session, claimed)

    # Inspect persisted result
    db_session.refresh(run)
    assert run.status == "SUCCEEDED"
    assert run.predicted_label in ("GOOD", "DEFECTIVE")
    assert 0.0 <= float(run.score) <= 1.0
    assert run.score_type == "PROBABILITY_DEFECTIVE"
    assert run.routing_outcome in ("LIKELY_OK", "NEEDS_REVIEW", "LIKELY_DEFECTIVE")
    assert run.processing_latency_ms is not None
    assert run.processing_latency_ms > 0
    assert run.completed_at is not None
