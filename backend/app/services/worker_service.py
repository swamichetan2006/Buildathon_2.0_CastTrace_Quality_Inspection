import os
import time
import hashlib
import uuid
import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import select, update, and_, or_, desc

from backend.app.config import settings
from backend.app.models.entities import ModelRun, ModelVersion, Image, WorkerHeartbeat
from backend.app.services.audit import log_audit_event
from backend.app.services.inference_service import InferenceService, InferenceResult

SYSTEM_WORKER_ACTOR = "system:ml-worker"

class InferenceWorker:
    """Lightweight, resilient database-backed inference worker.
    
    Operates outside the FastAPI API server process.
    """

    def __init__(
        self,
        worker_id: Optional[str] = None,
        inference_service: Optional[InferenceService] = None,
        heartbeat_interval_seconds: int = 10,
        lease_duration_seconds: int = 45,
        enable_demo_failure_injection: bool = False,
        demo_target_run_id: Optional[str] = None,
        single_job_mode: bool = False,
    ):
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.inference_service = inference_service or InferenceService()
        self.heartbeat_interval = heartbeat_interval_seconds
        self.lease_duration = lease_duration_seconds
        self.enable_demo_failure_injection = enable_demo_failure_injection
        self.demo_target_run_id = demo_target_run_id
        self.single_job_mode = single_job_mode
        self.is_running = False
        self.last_heartbeat_time = 0.0
        self.started_at = datetime.datetime.now(datetime.timezone.utc)
        self.active_model_version_id: Optional[str] = None
        self.last_error_code: Optional[str] = None

    def initialize(self, db: Session) -> bool:
        """Verify model artifacts and register/update worker heartbeat as STARTING/READY."""
        is_ready = False
        err_code = None

        try:
            valid, err = self.inference_service.verify_artifacts()
            if valid:
                self.inference_service.load_model()
                is_ready = True
            else:
                err_code = "ARTIFACT_VERIFICATION_FAILED"
                self.last_error_code = err_code
        except Exception as e:
            err_code = "MODEL_LOAD_FAILED"
            self.last_error_code = err_code

        # Find active model version ID
        stmt = select(ModelVersion.id).where(ModelVersion.is_active == True).limit(1)
        self.active_model_version_id = db.execute(stmt).scalars().first()

        now = datetime.datetime.now(datetime.timezone.utc)
        hb = db.get(WorkerHeartbeat, self.worker_id)
        if not hb:
            hb = WorkerHeartbeat(
                worker_id=self.worker_id,
                status="READY" if is_ready else "OFFLINE",
                started_at=self.started_at,
                last_heartbeat_at=now,
                model_version_id=self.active_model_version_id,
                model_ready=is_ready,
                last_error_code=err_code,
                details={"hostname": os.environ.get("COMPUTERNAME", "localhost")},
            )
            db.add(hb)
        else:
            hb.status = "READY" if is_ready else "OFFLINE"
            hb.last_heartbeat_at = now
            hb.model_version_id = self.active_model_version_id
            hb.model_ready = is_ready
            hb.last_error_code = err_code

        db.commit()
        return is_ready

    def send_heartbeat(self, db: Session, status: str = "READY", error_code: Optional[str] = None):
        """Update worker heartbeat in database."""
        now = datetime.datetime.now(datetime.timezone.utc)
        hb = db.get(WorkerHeartbeat, self.worker_id)
        if hb:
            hb.status = status
            hb.last_heartbeat_at = now
            hb.model_ready = self.inference_service.is_loaded
            if error_code:
                hb.last_error_code = error_code
            db.commit()
        self.last_heartbeat_time = time.time()

    def recover_stale_leases(self, db: Session) -> int:
        """Find processing jobs with expired leases and recover or fail them."""
        now = datetime.datetime.now(datetime.timezone.utc)
        stale_stmt = (
            select(ModelRun)
            .where(
                ModelRun.status == "PROCESSING",
                ModelRun.lease_expires_at < now,
            )
        )
        stale_runs = list(db.execute(stale_stmt).scalars().all())
        recovered_count = 0

        for run in stale_runs:
            recovered_count += 1
            if run.attempt_number < 3:
                # Mark current attempt as FAILED with LEASE_EXPIRED
                run.status = "FAILED"
                run.error_code = "LEASE_EXPIRED"
                run.is_retryable = True
                run.completed_at = now
                run.error_details = {"reason": "Worker lease expired before job was completed"}

                # Schedule next attempt with backoff: attempt 1->2 is 5s, attempt 2->3 is 30s
                delay_sec = 5 if run.attempt_number == 1 else 30
                next_retry = now + datetime.timedelta(seconds=delay_sec)

                next_run = ModelRun(
                    logical_run_id=run.logical_run_id,
                    image_id=run.image_id,
                    model_version_id=run.model_version_id,
                    status="QUEUED",
                    attempt_number=run.attempt_number + 1,
                    parent_run_id=run.id,
                    next_retry_at=next_retry,
                )
                db.add(next_run)

                # Audit log
                log_audit_event(
                    db=db,
                    entity_type="model_runs",
                    entity_id=run.id,
                    action="MODEL_RUN_LEASE_EXPIRED_RETRIED",
                    previous_state={"status": "PROCESSING", "attempt": run.attempt_number, "actor": SYSTEM_WORKER_ACTOR},
                    new_state={"status": "FAILED", "next_attempt": run.attempt_number + 1, "next_retry_at": next_retry.isoformat()},
                )
            else:
                # Exceeded 3 attempts: terminal failure
                run.status = "FAILED"
                run.error_code = "RETRY_EXHAUSTED"
                run.is_retryable = False
                run.completed_at = now
                run.error_details = {"reason": "Worker lease expired and maximum retry attempts (3) exhausted"}

                log_audit_event(
                    db=db,
                    entity_type="model_runs",
                    entity_id=run.id,
                    action="MODEL_RUN_RETRY_EXHAUSTED",
                    previous_state={"status": "PROCESSING", "attempt": run.attempt_number, "actor": SYSTEM_WORKER_ACTOR},
                    new_state={"status": "FAILED", "error_code": "RETRY_EXHAUSTED"},
                )

        if recovered_count > 0:
            db.commit()
        return recovered_count

    def claim_next_job(self, db: Session) -> Optional[ModelRun]:
        """Atomically claim the next eligible QUEUED job.
        
        Concurrency safe on SQLite and PostgreSQL.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        lease_expiry = now + datetime.timedelta(seconds=self.lease_duration)

        # 1. Select candidate queued job ordered by creation date
        candidate_stmt = (
            select(ModelRun.id)
            .where(
                ModelRun.status == "QUEUED",
                or_(ModelRun.next_retry_at == None, ModelRun.next_retry_at <= now),
            )
            .order_by(ModelRun.created_at.asc())
            .limit(1)
        )
        candidate_id = db.execute(candidate_stmt).scalars().first()
        if not candidate_id:
            return None

        # 2. Conditional atomic update (verifies status is still QUEUED)
        update_stmt = (
            update(ModelRun)
            .where(ModelRun.id == candidate_id, ModelRun.status == "QUEUED")
            .values(
                status="PROCESSING",
                claimed_by_worker_id=self.worker_id,
                lease_expires_at=lease_expiry,
                executed_at=now,
            )
        )
        res = db.execute(update_stmt)
        if res.rowcount == 1:
            db.commit()
            return db.get(ModelRun, candidate_id)
        else:
            db.rollback()
            return None

    def process_job(self, db: Session, run: ModelRun):
        """Execute evidence verification and ML inference for claimed run."""
        now = datetime.datetime.now(datetime.timezone.utc)

        # Update worker status to BUSY
        self.send_heartbeat(db, status="BUSY")

        image = db.get(Image, run.image_id)
        if not image:
            run.status = "FAILED"
            run.error_code = "IMAGE_RECORD_NOT_FOUND"
            run.is_retryable = False
            run.completed_at = now
            run.error_details = {"error": f"Image record {run.image_id} not found in database"}
            db.commit()
            return

        # Stage 9: Verify evidence integrity before inference
        if not os.path.exists(image.storage_path):
            run.status = "FAILED"
            run.error_code = "EVIDENCE_FILE_NOT_FOUND"
            run.is_retryable = False
            run.completed_at = now
            run.error_details = {"error": f"Evidence file missing on disk at '{image.storage_path}'"}
            db.commit()
            return

        with open(image.storage_path, "rb") as f:
            evidence_bytes = f.read()

        computed_sha = hashlib.sha256(evidence_bytes).hexdigest()
        if computed_sha != image.sha256_hash:
            # Evidence tamper / corruption detected! Permanent failure.
            run.status = "FAILED"
            run.error_code = "EVIDENCE_INTEGRITY_MISMATCH"
            run.is_retryable = False
            run.completed_at = now
            run.error_details = {
                "error": "Evidence integrity failure: Computed SHA-256 does not match recorded upload digest",
                "recorded_sha256": image.sha256_hash,
                "computed_sha256": computed_sha,
            }

            log_audit_event(
                db=db,
                entity_type="model_runs",
                entity_id=run.id,
                action="EVIDENCE_INTEGRITY_MISMATCH",
                previous_state={"image_id": image.id, "recorded_sha": image.sha256_hash, "actor": SYSTEM_WORKER_ACTOR},
                new_state={"computed_sha": computed_sha, "status": "FAILED"},
            )
            db.commit()
            return

        # Stage 10: Development-only Failure Injection
        is_dev = settings.APP_ENV == "development"
        inject_failure = False
        if self.enable_demo_failure_injection and is_dev:
            if self.demo_target_run_id is None or self.demo_target_run_id == run.id:
                inject_failure = True
                # Consume single-target injection
                if self.demo_target_run_id == run.id:
                    self.demo_target_run_id = None
                self.enable_demo_failure_injection = False

        if inject_failure:
            run.status = "FAILED"
            run.error_code = "DEMO_INJECTED_FAILURE"
            run.completed_at = now
            run.error_details = {"reason": "Controlled development-only failure injection for demonstration"}

            if run.attempt_number < 3:
                run.is_retryable = True
                delay_sec = 5 if run.attempt_number == 1 else 30
                next_retry = now + datetime.timedelta(seconds=delay_sec)

                next_run = ModelRun(
                    logical_run_id=run.logical_run_id,
                    image_id=run.image_id,
                    model_version_id=run.model_version_id,
                    status="QUEUED",
                    attempt_number=run.attempt_number + 1,
                    parent_run_id=run.id,
                    next_retry_at=next_retry,
                )
                db.add(next_run)

                log_audit_event(
                    db=db,
                    entity_type="model_runs",
                    entity_id=run.id,
                    action="MODEL_RUN_DEMO_FAILURE_INJECTED",
                    previous_state={"attempt": run.attempt_number, "actor": SYSTEM_WORKER_ACTOR},
                    new_state={"status": "FAILED", "scheduled_retry_at": next_retry.isoformat()},
                )
            else:
                run.is_retryable = False
                log_audit_event(
                    db=db,
                    entity_type="model_runs",
                    entity_id=run.id,
                    action="MODEL_RUN_RETRY_EXHAUSTED",
                    previous_state={"attempt": run.attempt_number, "actor": SYSTEM_WORKER_ACTOR},
                    new_state={"status": "FAILED", "error_code": "RETRY_EXHAUSTED"},
                )

            db.commit()
            return

        # Normal ML inference execution via InferenceService
        result: InferenceResult = self.inference_service.predict_image(
            evidence_bytes,
            original_filename=image.original_filename,
        )

        completed_at = datetime.datetime.now(datetime.timezone.utc)
        if result.status == "SUCCEEDED":
            run.status = "SUCCEEDED"
            run.predicted_label = result.predicted_label
            run.score = result.score
            run.score_type = result.score_type
            run.threshold_applied = result.threshold_applied
            run.routing_outcome = result.routing_outcome
            run.routing_reason = result.routing_reason
            run.processing_latency_ms = result.processing_latency_ms
            run.completed_at = completed_at
            run.error_details = {
                "quality_gate_passed": result.quality_gate_passed,
                "quality_gate_reason": result.quality_gate_reason,
                "is_unfamiliar": result.is_unfamiliar,
                "guard_distance": result.guard_distance,
                "guard_threshold": result.guard_threshold,
            }

            log_audit_event(
                db=db,
                entity_type="model_runs",
                entity_id=run.id,
                action="MODEL_RUN_SUCCEEDED",
                previous_state={"status": "PROCESSING", "actor": SYSTEM_WORKER_ACTOR},
                new_state={
                    "status": "SUCCEEDED",
                    "predicted_label": result.predicted_label,
                    "score": result.score,
                    "routing_outcome": result.routing_outcome,
                    "latency_ms": result.processing_latency_ms,
                },
            )

        else:
            # Inference returned FAILED
            run.status = "FAILED"
            run.error_code = result.error_code or "INFERENCE_ERROR"
            run.error_details = result.error_details
            run.processing_latency_ms = result.processing_latency_ms
            run.completed_at = completed_at
            run.is_retryable = False

            log_audit_event(
                db=db,
                entity_type="model_runs",
                entity_id=run.id,
                action="MODEL_RUN_FAILED",
                previous_state={"status": "PROCESSING", "actor": SYSTEM_WORKER_ACTOR},
                new_state={"status": "FAILED", "error_code": run.error_code},
            )

        db.commit()
        self.send_heartbeat(db, status="READY")

    def run_cycle(self, db: Session) -> bool:
        """Execute one complete worker iteration: heartbeat, recovery, and job processing."""
        # 1. Heartbeat check
        if time.time() - self.last_heartbeat_time >= self.heartbeat_interval:
            self.send_heartbeat(db, status="READY")

        # 2. Recover stale leases
        self.recover_stale_leases(db)

        # 3. Claim and process next job
        job = self.claim_next_job(db)
        if job:
            self.process_job(db, job)
            return True
        return False
