import os
import sys
import time
import signal
import argparse

# Ensure workspace root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.config import settings
from backend.app.database import SessionLocal
from backend.app.services.worker_service import InferenceWorker
from backend.app.services.model_registration import register_approved_model_version

def parse_args():
    parser = argparse.ArgumentParser(description="CastTrace AI Background Inference Worker")
    parser.add_argument("--worker-id", type=str, default=None, help="Custom identifier for this worker instance")
    parser.add_argument("--once", action="store_true", help="Process all currently queued jobs once and exit")
    parser.add_argument("--inject-failure", action="store_true", help="Development-only: Deliberately inject failure on next executed run")
    parser.add_argument("--target-run-id", type=str, default=None, help="Target specific model run ID for failure injection")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="Poll interval in seconds when queue is empty")
    return parser.parse_args()

def main():
    args = parse_args()

    # Stage 10: Reject failure injection if not in development mode
    if args.inject_failure and settings.APP_ENV != "development":
        print("ERROR: --inject-failure is permitted ONLY in 'development' environment.", file=sys.stderr)
        sys.exit(1)

    print(f"=== CastTrace AI Inference Worker Starting ===")
    print(f"Environment: {settings.APP_ENV}")
    print(f"Database: {settings.DATABASE_URL.split('@')[-1]}")

    db = SessionLocal()
    try:
        # Idempotently register model version if not already present
        model_ver = register_approved_model_version(db)
        print(f"Active Model Version: {model_ver.version_name} (Architecture: {model_ver.model_architecture})")
    except Exception as e:
        print(f"Warning: Model version pre-registration encountered: {e}")
    finally:
        db.close()

    worker = InferenceWorker(
        worker_id=args.worker_id,
        enable_demo_failure_injection=args.inject_failure,
        demo_target_run_id=args.target_run_id,
        single_job_mode=args.once,
    )

    db = SessionLocal()
    try:
        ready = worker.initialize(db)
        print(f"Worker ID: {worker.worker_id}")
        print(f"Worker Initialized. Model Ready: {ready}")
    finally:
        db.close()

    # Graceful shutdown handler
    running = True
    def handle_signal(sig, frame):
        nonlocal running
        print(f"\nReceived termination signal ({sig}). Shutting down worker gracefully...")
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print("Worker loop running. Waiting for queued jobs...")
    while running:
        db = SessionLocal()
        try:
            processed = worker.run_cycle(db)
        except Exception as e:
            print(f"Error during worker cycle: {e}", file=sys.stderr)
            processed = False
        finally:
            db.close()

        if args.once:
            if not processed:
                print("No further queued jobs. Exiting (--once).")
                break
        else:
            if not processed:
                time.sleep(args.poll_interval)

    # Final shutdown heartbeat
    db = SessionLocal()
    try:
        worker.send_heartbeat(db, status="OFFLINE")
        print("Worker status set to OFFLINE. Shutdown complete.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
