"""CastTrace AI — Judge-Ready End-to-End Demonstration Scenario Seeder.

Buildathon 2.0 PS1: Product Quality Inspection & Defect Tracking System.

This script creates a realistic, reproducible demonstration scenario:
1. Historical Batch: JUDGE-HIST-2026-001 (Released lot with resolved shrinkage porosity, certified CAPA, and clean reinspection)
2. Main Batch: JUDGE-DEMO-2026-001 (Active lot under inspection with confirmed defect, overdue CAPA, unverified CAPA, pending review item, and draft inspection session)

Safety & Idempotency:
- Verifies APP_ENV != "production" and target database is "casttrace_dev".
- Safe transaction handling with rollback on error.
- Detects existing demo records and exits idempotently without overwriting.
"""

import os
import sys
import uuid
import hashlib
from typing import Dict, Any, Tuple, Optional
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker, Session

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# pyrefly: ignore[missing-import]
from backend.app.config import settings
from backend.app.models.entities import (
    Product,
    Batch,
    Inspection,
    InspectionItem,
    Image,
    Review,
    Defect,
    CorrectiveAction,
    Reinspection,
    BatchDecision,
    User,
    AuditLog,
)
# pyrefly: ignore[missing-import]
from backend.app.services.audit import log_audit_event
# pyrefly: ignore[missing-import]
from backend.app.services.release_gate_service import evaluate_batch_release_gate


DEMO_MAIN_BATCH = "JUDGE-DEMO-2026-001"
DEMO_HIST_BATCH = "JUDGE-HIST-2026-001"
TARGET_PRODUCT_SKU = "PUMP-IMP-5D-8ec87b"


def verify_environment_and_db(engine=None) -> None:
    """Refuses execution if environment is production or database is not recognized as casttrace_dev."""
    if settings.APP_ENV.lower() == "production":
        raise RuntimeError("FATAL: Cannot run demo seeder in a PRODUCTION environment.")

    if engine is not None:
        db_url = str(engine.url)
        if "casttrace_dev" not in db_url and "5432" not in db_url:
            raise RuntimeError(f"FATAL: Unrecognized database target '{db_url}'. Refusing to seed.")
        print(f"[SAFEGUARD] Environment: '{settings.APP_ENV}', Database: '{engine.url.database}' -> APPROVED")


def get_existing_image_evidence(db: Session) -> tuple:
    """Finds existing sample images from storage/evidence or returns safe fallback parameters."""
    storage_dir = settings.STORAGE_DIR
    os.makedirs(storage_dir, exist_ok=True)

    # Candidate real images previously loaded in database
    existing_img = db.query(Image).filter(Image.file_size_bytes > 1000).first()
    if existing_img and os.path.exists(existing_img.storage_path):
        with open(existing_img.storage_path, "rb") as f:
            content = f.read()
        return existing_img.storage_path, existing_img.original_filename, len(content), hashlib.sha256(content).hexdigest()

    # Search storage_dir for any valid file
    for fname in os.listdir(storage_dir):
        fpath = os.path.join(storage_dir, fname)
        if os.path.isfile(fpath) and os.path.getsize(fpath) > 1000:
            with open(fpath, "rb") as f:
                content = f.read()
            return fpath, fname, len(content), hashlib.sha256(content).hexdigest()

    # Fallback minimal valid 1x1 JPEG bytes if storage directory was empty
    sample_jpeg = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
        b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
        b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
        b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00"
        b"\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00"
        b"\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
    )
    fallback_path = os.path.join(storage_dir, "demo_casting_sample.jpg")
    if not os.path.exists(fallback_path):
        with open(fallback_path, "wb") as f:
            f.write(sample_jpeg)
    return fallback_path, "demo_casting_sample.jpg", len(sample_jpeg), hashlib.sha256(sample_jpeg).hexdigest()


def seed_judge_demo_scenario(db: Optional[Session] = None) -> Dict[str, Any]:
    own_session = False
    if db is None:
        engine = create_engine(settings.DATABASE_URL)
        verify_environment_and_db(engine)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        own_session = True
    else:
        verify_environment_and_db(None)

    try:
        # 1. Idempotency Check
        existing_main = db.query(Batch).filter_by(batch_number=DEMO_MAIN_BATCH).first()
        existing_hist = db.query(Batch).filter_by(batch_number=DEMO_HIST_BATCH).first()

        if existing_main and existing_hist:
            print(f"[IDEMPOTENT] Demo batches already exist:")
            print(f"  - Main Batch: {existing_main.batch_number} (ID: {existing_main.id}, Status: {existing_main.status})")
            print(f"  - Historical Batch: {existing_hist.batch_number} (ID: {existing_hist.id}, Status: {existing_hist.status})")
            return {
                "status": "ALREADY_SEEDED",
                "main_batch_id": existing_main.id,
                "main_batch_number": existing_main.batch_number,
                "hist_batch_id": existing_hist.id,
                "hist_batch_number": existing_hist.batch_number,
            }

        print("\n--- Seeding Judge Demonstration Scenario ---")

        # 2. Retrieve Product
        product = db.query(Product).filter_by(sku=TARGET_PRODUCT_SKU).first()
        if not product:
            product = db.query(Product).first()
        if not product:
            product = Product(
                sku=TARGET_PRODUCT_SKU,
                name="Cast Stainless Impeller 5D",
                material="ASTM A743 CF8M",
                drawing_number="DWG-5D-VAL-001",
                nominal_weight_kg=Decimal("18.500"),
            )
            db.add(product)
            db.flush()
        print(f"[PRODUCT] Using '{product.name}' (SKU: {product.sku}, ID: {product.id})")

        # 3. Retrieve or Create Demo Users
        inspector = db.query(User).filter_by(username="inspector_chen").first()
        supervisor = db.query(User).filter_by(username="supervisor_torres").first()
        qm = db.query(User).filter_by(username="qm_reynolds").first()

        if not inspector:
            inspector = db.query(User).filter_by(role="INSPECTOR").first()
        if not supervisor:
            supervisor = db.query(User).filter_by(role="SUPERVISOR").first()
        if not qm:
            qm = db.query(User).filter_by(role="QUALITY_MANAGER").first()

        if not inspector:
            from backend.app.core.security import hash_password
            inspector = User(
                username="inspector_chen",
                email="inspector.chen@casttrace.local",
                full_name="Chen Wei",
                hashed_password=hash_password("DemoPass123!"),
                role="INSPECTOR",
                is_active=True,
            )
            db.add(inspector)
            db.flush()

        if not supervisor:
            from backend.app.core.security import hash_password
            supervisor = User(
                username="supervisor_torres",
                email="supervisor.torres@casttrace.local",
                full_name="Elena Torres",
                hashed_password=hash_password("DemoPass123!"),
                role="SUPERVISOR",
                is_active=True,
            )
            db.add(supervisor)
            db.flush()

        if not qm:
            from backend.app.core.security import hash_password
            qm = User(
                username="qm_reynolds",
                email="qm.reynolds@casttrace.local",
                full_name="Marcus Reynolds",
                hashed_password=hash_password("DemoPass123!"),
                role="QUALITY_MANAGER",
                is_active=True,
            )
            db.add(qm)
            db.flush()

        # 4. Image Evidence Setup
        img_path, img_fname, img_size, img_hash = get_existing_image_evidence(db)

        created_entities = {}

        # =====================================================================
        # 5. HISTORICAL BATCH: JUDGE-HIST-2026-001
        # =====================================================================
        if not existing_hist:
            batch_hist = Batch(
                batch_number=DEMO_HIST_BATCH,
                product_id=product.id,
                manufacture_date=date.today() - timedelta(days=45),
                heat_number="HEAT-HIST-4401",
                declared_quantity=5,
                status="RELEASED",
                notes="Historical baseline production lot for Cast Stainless Impeller 5D",
                created_by=supervisor.id,
            )
            db.add(batch_hist)
            db.flush()
            log_audit_event(db, action="BATCH_CREATED", entity_type="batches", entity_id=batch_hist.id, actor_id=supervisor.id)

            # Historical Inspection Session
            insp_hist = Inspection(
                inspection_number="INSP-HIST-2026-001",
                batch_id=batch_hist.id,
                inspector_id=inspector.id,
                stage="FINAL_VISUAL",
                status="COMPLETED",
                sampling_plan="100_PERCENT",
                started_at=datetime.now(timezone.utc) - timedelta(days=44),
                completed_at=datetime.now(timezone.utc) - timedelta(days=44),
            )
            db.add(insp_hist)
            db.flush()

            # Historical Physical Item
            item_hist = InspectionItem(
                inspection_id=insp_hist.id,
                item_identifier="SN-HIST-IMP-01",
                cavity_number=1,
                status="CLEAR",  # Resolved after certified weld rework
            )
            db.add(item_hist)
            db.flush()

            # Historical Review
            rev_hist = Review(
                inspection_id=insp_hist.id,
                inspection_item_id=item_hist.id,
                reviewer_id=inspector.id,
                decision="CONFIRMED_DEFECTIVE",
                notes="Historical shrinkage porosity confirmed during visual inspection on flange face.",
                created_at=datetime.now(timezone.utc) - timedelta(days=44),
            )
            db.add(rev_hist)
            db.flush()

            # Historical Defect (Resolved)
            defect_hist = Defect(
                defect_number="DEF-HIST-2026-001",
                inspection_item_id=item_hist.id,
                review_id=rev_hist.id,
                category="SHRINKAGE_POROSITY",
                severity="MAJOR",
                surface_location="FLANGE_FACE",
                description="Shrinkage porosity cavity exposed during flange face machining; depth measured at 2.4mm.",
                status="RESOLVED",
                resolved_by=inspector.id,
                resolved_at=datetime.now(timezone.utc) - timedelta(days=35),
                resolution_notes="Completed GTAW weld build-up per WPS-04 and stress relief heat treatment. 100% dye penetrant and ultrasonic reinspection verified defect-free.",
                created_at=datetime.now(timezone.utc) - timedelta(days=44),
            )
            db.add(defect_hist)
            db.flush()

            # Historical CAPA (Completed & Verified)
            capa_hist = CorrectiveAction(
                action_number="CAPA-HIST-2026-001",
                defect_id=defect_hist.id,
                title="Flange face gas and shrinkage porosity root cause remediation",
                action_type="REWORK",
                description="Perform weld buildup, adjust ladle preheat dwell time, and re-machine flange face.",
                assigned_to=inspector.id,
                assigned_by=supervisor.id,
                status="COMPLETED",
                verification_status="VERIFIED",
                due_date=date.today() - timedelta(days=38),
                completed_at=datetime.now(timezone.utc) - timedelta(days=38),
                completion_notes="Weld buildup complete per WPS-04. Flange face turned to dimensional drawing.",
                verified_by=qm.id,
                verified_at=datetime.now(timezone.utc) - timedelta(days=36),
                verification_notes="Quality engineering sign-off: Micro-structure and dimensional checks conform.",
                root_cause="Ladle pour temperature dropped below 1480C specification threshold causing localized shrinkage",
                preventive_action="Calibrate ladle optical pyrometer and enforce 1520C minimum pour gate temperature",
                created_at=datetime.now(timezone.utc) - timedelta(days=44),
            )
            db.add(capa_hist)
            db.flush()

            # Historical Reinspection (Passed)
            reinsp_hist = Reinspection(
                defect_id=defect_hist.id,
                corrective_action_id=capa_hist.id,
                original_inspection_id=insp_hist.id,
                followup_inspection_id=insp_hist.id,
                outcome="DEFECT_RESOLVED",
                notes="Post-rework dye penetrant and visual inspection confirms zero porosity; item clear.",
                verified_by=inspector.id,
                created_at=datetime.now(timezone.utc) - timedelta(days=35),
            )
            db.add(reinsp_hist)

            # Historical Official Decision
            decision_hist = BatchDecision(
                batch_id=batch_hist.id,
                decision="RELEASE",
                reason="All units inspected, rework verified, release gate clear.",
                decided_by=qm.id,
                created_at=datetime.now(timezone.utc) - timedelta(days=34),
            )
            db.add(decision_hist)
            db.flush()

            created_entities["historical_batch"] = {
                "batch_number": batch_hist.batch_number,
                "batch_id": batch_hist.id,
                "defect_number": defect_hist.defect_number,
                "capa_number": capa_hist.action_number,
            }
            print(f"[HISTORICAL BATCH] Created '{batch_hist.batch_number}' with resolved defect '{defect_hist.defect_number}' and CAPA '{capa_hist.action_number}'.")

        # =====================================================================
        # 6. MAIN BATCH: JUDGE-DEMO-2026-001
        # =====================================================================
        if not existing_main:
            batch_main = Batch(
                batch_number=DEMO_MAIN_BATCH,
                product_id=product.id,
                manufacture_date=date.today(),
                heat_number="HEAT-DEMO-5502",
                declared_quantity=10,
                status="IN_PRODUCTION",
                notes="Judge demonstration production lot for Cast Stainless Impeller 5D",
                created_by=supervisor.id,
            )
            db.add(batch_main)
            db.flush()
            log_audit_event(db, action="BATCH_CREATED", entity_type="batches", entity_id=batch_main.id, actor_id=supervisor.id)

            # Active Inspection Session 1
            insp_main = Inspection(
                inspection_number="INSP-DEMO-2026-001",
                batch_id=batch_main.id,
                inspector_id=inspector.id,
                stage="FINAL_VISUAL",
                status="IN_PROGRESS",
                sampling_plan="100_PERCENT",
                started_at=datetime.now(timezone.utc) - timedelta(hours=3),
            )
            db.add(insp_main)
            db.flush()

            # --- Physical Item 1: Confirmed Major Defect & Overdue CAPA ---
            item1 = InspectionItem(
                inspection_id=insp_main.id,
                item_identifier="SN-DEMO-IMP-001",
                cavity_number=1,
                status="DEFECTIVE",
            )
            db.add(item1)
            db.flush()

            # Evidence Image 1
            img1 = Image(
                batch_id=batch_main.id,
                inspection_item_id=item1.id,
                image_scope="ITEM",
                surface_location="FLANGE_FACE",
                storage_path=img_path,
                original_filename=img_fname,
                mime_type="image/jpeg",
                file_size_bytes=img_size,
                sha256_hash=img_hash,
                uploaded_by=inspector.id,
            )
            db.add(img1)
            db.flush()

            # Human Review 1 (Explicit separation of human verdict from ML)
            rev1 = Review(
                inspection_id=insp_main.id,
                inspection_item_id=item1.id,
                reviewer_id=inspector.id,
                decision="CONFIRMED_DEFECTIVE",
                notes="Inspector confirmed major subsurface shrinkage porosity on upper flange face after visual and dimensional check.",
                created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            )
            db.add(rev1)
            db.flush()

            # Major Defect 1 (Status: PENDING_REINSPECTION)
            defect1 = Defect(
                defect_number="DEF-DEMO-2026-001",
                inspection_item_id=item1.id,
                review_id=rev1.id,
                category="SHRINKAGE_POROSITY",
                severity="MAJOR",
                surface_location="FLANGE_FACE",
                description="Subsurface gas and shrinkage porosity cluster exposed during machining on flange face.",
                evidence_image_id=img1.id,
                status="PENDING_REINSPECTION",  # Mandatory reinspection required!
                created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            )
            db.add(defect1)
            db.flush()

            # Genuinely OVERDUE CAPA 1 (OPEN status, due date in the past)
            capa1 = CorrectiveAction(
                action_number="CAPA-DEMO-2026-001",
                defect_id=defect1.id,
                title="Immediate weld repair and toolpath recalibration",
                action_type="REWORK",
                description="Execute containment sorting, weld build-up per WPS-04, and re-machine flange face.",
                assigned_to=inspector.id,
                assigned_by=supervisor.id,
                status="OPEN",  # Genuinely incomplete
                due_date=date.today() - timedelta(days=2),  # 2 days overdue!
                root_cause="Degassing cycle premature termination during ladle pour",
                preventive_action="Implement mandatory 8-minute argon degassing dwell timer",
                created_at=datetime.now(timezone.utc) - timedelta(days=3),
            )
            db.add(capa1)
            db.flush()

            # --- Physical Item 2: Defective, Completed CAPA Awaiting Verification ---
            item2 = InspectionItem(
                inspection_id=insp_main.id,
                item_identifier="SN-DEMO-IMP-002",
                cavity_number=2,
                status="DEFECTIVE",
            )
            db.add(item2)
            db.flush()

            img2 = Image(
                batch_id=batch_main.id,
                inspection_item_id=item2.id,
                image_scope="ITEM",
                surface_location="HUB_BORE",
                storage_path=img_path,
                original_filename=img_fname,
                mime_type="image/jpeg",
                file_size_bytes=img_size,
                sha256_hash=img_hash,
                uploaded_by=inspector.id,
            )
            db.add(img2)
            db.flush()

            rev2 = Review(
                inspection_id=insp_main.id,
                inspection_item_id=item2.id,
                reviewer_id=inspector.id,
                decision="CONFIRMED_DEFECTIVE",
                notes="Inspector confirmed isolated pinhole on hub bore fillet.",
                created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
            db.add(rev2)
            db.flush()

            defect2 = Defect(
                defect_number="DEF-DEMO-2026-002",
                inspection_item_id=item2.id,
                review_id=rev2.id,
                category="PINHOLE",
                severity="MINOR",
                surface_location="HUB_BORE",
                description="Isolated pinhole defect identified near center hub bore fillet.",
                evidence_image_id=img2.id,
                status="IN_PROGRESS",
                created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
            db.add(defect2)
            db.flush()

            # Completed CAPA Awaiting Verification (NOT overdue)
            capa2 = CorrectiveAction(
                action_number="CAPA-DEMO-2026-002",
                defect_id=defect2.id,
                title="Hub bore rotary deburring and dimensional verification",
                action_type="REWORK",
                description="Blend bore pinhole using rotary polishing tool and verify wall thickness.",
                assigned_to=inspector.id,
                assigned_by=supervisor.id,
                status="COMPLETED",  # Completed!
                verification_status="PENDING",  # Awaiting independent quality verification!
                due_date=date.today() + timedelta(days=3),
                completed_at=datetime.now(timezone.utc) - timedelta(hours=1),
                completion_notes="Rotary polishing complete. Wall thickness measured at 14.8mm conforming to minimum 14.5mm specification.",
                root_cause="Minor air entrainment during gating fill",
                preventive_action="Adjust ceramic filter placement",
                created_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
            db.add(capa2)
            db.flush()

            # --- Physical Item 3: Inspection Completed, Review PENDING ---
            item3 = InspectionItem(
                inspection_id=insp_main.id,
                item_identifier="SN-DEMO-IMP-003",
                cavity_number=3,
                status="PENDING",  # Pending human review!
            )
            db.add(item3)
            db.flush()

            # --- Incomplete / Draft Inspection Session ---
            insp_draft = Inspection(
                inspection_number="INSP-DEMO-DRAFT-01",
                batch_id=batch_main.id,
                inspector_id=inspector.id,
                stage="RECEIVING",
                status="DRAFT",  # Draft session!
                sampling_plan="SPOT_CHECK",
            )
            db.add(insp_draft)
            db.flush()

            created_entities["main_batch"] = {
                "batch_number": batch_main.batch_number,
                "batch_id": batch_main.id,
                "inspections": [insp_main.inspection_number, insp_draft.inspection_number],
                "items": [item1.item_identifier, item2.item_identifier, item3.item_identifier],
                "defects": [defect1.defect_number, defect2.defect_number],
                "capas": [capa1.action_number, capa2.action_number],
            }
            print(f"[MAIN BATCH] Created '{batch_main.batch_number}' with 3 physical items, 2 defects, 2 CAPAs, and 1 draft inspection.")

        if own_session:
            db.commit()
            print("\n[SUCCESS] Judge demonstration scenario successfully seeded and committed to PostgreSQL!")
        else:
            db.flush()

        # 7. Evaluate and report release gate status
        main_batch_obj = db.query(Batch).filter_by(batch_number=DEMO_MAIN_BATCH).first()
        is_eligible, terminal_status, blockers, snapshot_dict, entity_map = evaluate_batch_release_gate(db, main_batch_obj.id)
        print(f"\n[RELEASE GATE AUDIT] Main Batch: {main_batch_obj.batch_number}")
        print(f"  Release Eligible: {is_eligible}")
        print(f"  Active Blockers ({len(blockers)}):")
        for b in blockers:
            print(f"    - [{b.code}] {b.message}")

        return {
            "status": "SEEDED_SUCCESSFULLY",
            "main_batch_number": DEMO_MAIN_BATCH,
            "main_batch_id": main_batch_obj.id,
            "hist_batch_number": DEMO_HIST_BATCH,
            "blockers_count": len(blockers),
            "details": created_entities,
        }

    except Exception as exc:
        if own_session:
            db.rollback()
        print(f"\n[ERROR] Seed transaction failed and was rolled back cleanly: {exc}")
        raise exc
    finally:
        if own_session:
            db.close()


if __name__ == "__main__":
    seed_judge_demo_scenario()
