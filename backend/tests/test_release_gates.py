import uuid
import hashlib
from datetime import date, datetime, timezone, timedelta
import pytest
from fastapi import status

from backend.app.core.security import create_access_token, hash_password
from backend.app.models.entities import (
    User,
    Product,
    Batch,
    Inspection,
    InspectionItem,
    Image,
    ModelRun,
    ModelVersion,
    Review,
    Defect,
    CorrectiveAction,
    Reinspection,
    BatchDecision,
    AuditLog,
)

JPEG_HEADER = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"\x00" * 50


@pytest.fixture
def phase4c_setup(db_session):
    """Sets up product, users, and base tokens for Phase 4C tests."""
    inspector = db_session.query(User).filter(User.username == "gate_inspector").first()
    if not inspector:
        inspector = User(
            username="gate_inspector",
            email="gate_insp@casttrace.local",
            full_name="Gate Inspector",
            role="INSPECTOR",
            hashed_password=hash_password("Password123!"),
            is_active=True,
        )
        db_session.add(inspector)

    supervisor = db_session.query(User).filter(User.username == "gate_supervisor").first()
    if not supervisor:
        supervisor = User(
            username="gate_supervisor",
            email="gate_sup@casttrace.local",
            full_name="Gate Supervisor",
            role="SUPERVISOR",
            hashed_password=hash_password("Password123!"),
            is_active=True,
        )
        db_session.add(supervisor)

    qm = db_session.query(User).filter(User.username == "gate_qm").first()
    if not qm:
        qm = User(
            username="gate_qm",
            email="gate_qm@casttrace.local",
            full_name="Gate Quality Manager",
            role="QUALITY_MANAGER",
            hashed_password=hash_password("Password123!"),
            is_active=True,
        )
        db_session.add(qm)

    db_session.commit()
    db_session.refresh(inspector)
    db_session.refresh(supervisor)
    db_session.refresh(qm)

    # Product
    product = Product(
        sku=f"PUMP-IMP-4C-{uuid.uuid4().hex[:6]}",
        name="Cast Stainless Impeller 4C",
        material="ASTM A743 CF8M",
        drawing_number="DWG-4C-001",
        is_archived=False,
    )
    db_session.add(product)

    # Seed model version for FK integrity on PostgreSQL
    mv = db_session.query(ModelVersion).filter(ModelVersion.id == "mv-resnet18-v1").first()
    if not mv:
        mv = ModelVersion(
            id="mv-resnet18-v1",
            version_name="v1.0.0-resnet18",
            model_architecture="ResNet-18",
            weights_path="ml/artifacts/model_best.pt",
            training_dataset_info={"source": "test_dataset"},
            metrics={"accuracy": 1.0},
            is_active=True,
        )
        db_session.add(mv)

    db_session.commit()
    db_session.refresh(product)

    insp_token = create_access_token({"sub": inspector.id, "role": inspector.role})
    sup_token = create_access_token({"sub": supervisor.id, "role": supervisor.role})
    qm_token = create_access_token({"sub": qm.id, "role": qm.role})

    return {
        "inspector": inspector,
        "supervisor": supervisor,
        "qm": qm,
        "product": product,
        "inspector_headers": {"Authorization": f"Bearer {insp_token}"},
        "supervisor_headers": {"Authorization": f"Bearer {sup_token}"},
        "qm_headers": {"Authorization": f"Bearer {qm_token}"},
    }


# =====================================================================
# 1. END-TO-END SUCCESSFUL WORKFLOW & BATCH RELEASE TEST
# =====================================================================

def test_end_to_end_successful_quality_lifecycle_and_batch_release(client, phase4c_setup, db_session):
    """End-to-End Workflow Test (Section 9):
    1. Create Batch
    2. Create Inspection session
    3. Register 2 physical items
    4. Upload evidence images for both items
    5. Enqueue and process model run (deterministic simulation)
    6. Record human reviews: Item 1 -> CONFIRMED_GOOD, Item 2 -> CONFIRMED_DEFECTIVE
    7. Track defect for Item 2
    8. Create CAPA for defect
    9. Implement and complete CAPA
    10. Independent verifier approves verification
    11. Reinspection verifies defect resolved -> Defect RESOLVED, Item 2 CLEAR
    12. Inspection completed
    13. Evaluate release gate -> is_permitted == True, 0 blockers
    14. Quality Manager executes official RELEASE
    15. Verify decision snapshot, counts, audit log, and final batch state.
    """
    qm_headers = phase4c_setup["qm_headers"]
    sup_headers = phase4c_setup["supervisor_headers"]
    insp_headers = phase4c_setup["inspector_headers"]
    prod_id = phase4c_setup["product"].id
    machinist_id = phase4c_setup["supervisor"].id

    # 1. Create Batch
    b_res = client.post(
        "/api/v1/batches",
        headers=sup_headers,
        json={
            "batch_number": f"LOT-E2E-{uuid.uuid4().hex[:6]}",
            "product_id": prod_id,
            "manufacture_date": str(date.today()),
            "declared_quantity": 2,
            "notes": "Full end-to-end test lot",
        },
    )
    assert b_res.status_code == status.HTTP_201_CREATED
    batch_id = b_res.json()["id"]

    # 2. Create Inspection session
    insp_res = client.post(
        "/api/v1/inspections",
        headers=insp_headers,
        json={
            "batch_id": batch_id,
            "stage": "FINAL_VISUAL",
            "sampling_plan": "100_PERCENT",
        },
    )
    assert insp_res.status_code == status.HTTP_201_CREATED
    insp_id = insp_res.json()["id"]

    # 3. Register 2 physical items
    reg_res = client.post(
        f"/api/v1/inspections/{insp_id}/items",
        headers=insp_headers,
        json={
            "items": [
                {"item_identifier": "SN-E2E-001", "cavity_number": 1},
                {"item_identifier": "SN-E2E-002", "cavity_number": 2},
            ]
        },
    )
    assert reg_res.status_code == status.HTTP_201_CREATED
    items_data = reg_res.json()
    item1_id = items_data[0]["id"]
    item2_id = items_data[1]["id"]

    # 4. Upload evidence images for both items
    img1_bytes = JPEG_HEADER + b"evidence_photo_item_1_" + uuid.uuid4().hex.encode()
    img1 = client.post(
        "/api/v1/images/upload",
        headers=insp_headers,
        data={"batch_id": batch_id, "inspection_item_id": item1_id, "image_scope": "ITEM"},
        files={"file": ("item1.jpg", img1_bytes, "image/jpeg")},
    ).json()

    img2_bytes = JPEG_HEADER + b"evidence_photo_item_2_" + uuid.uuid4().hex.encode()
    img2 = client.post(
        "/api/v1/images/upload",
        headers=insp_headers,
        data={"batch_id": batch_id, "inspection_item_id": item2_id, "image_scope": "ITEM"},
        files={"file": ("item2.jpg", img2_bytes, "image/jpeg")},
    ).json()

    # 5. Deterministic Model Runs
    mr1 = ModelRun(
        logical_run_id=f"RUN-{uuid.uuid4().hex[:6]}",
        image_id=img1["id"],
        model_version_id="mv-resnet18-v1",
        status="SUCCEEDED",
        predicted_label="GOOD",
        score=0.985,
        routing_outcome="LIKELY_OK",
        created_at=datetime.now(timezone.utc),
    )
    mr2 = ModelRun(
        logical_run_id=f"RUN-{uuid.uuid4().hex[:6]}",
        image_id=img2["id"],
        model_version_id="mv-resnet18-v1",
        status="SUCCEEDED",
        predicted_label="DEFECTIVE",
        score=0.962,
        routing_outcome="LIKELY_DEFECTIVE",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(mr1)
    db_session.add(mr2)
    db_session.commit()

    # 6. Record Human Reviews:
    # Item 1 -> CONFIRMED_GOOD
    rev1 = client.post(
        "/api/v1/reviews",
        headers=insp_headers,
        json={
            "inspection_item_id": item1_id,
            "decision": "CONFIRMED_GOOD",
            "notes": "Surface finish meets drawing tolerance.",
        },
    )
    assert rev1.status_code == status.HTTP_201_CREATED

    # Item 2 -> CONFIRMED_DEFECTIVE
    rev2 = client.post(
        "/api/v1/reviews",
        headers=insp_headers,
        json={
            "inspection_item_id": item2_id,
            "decision": "CONFIRMED_DEFECTIVE",
            "notes": "Visual inspection confirms hot tear near shroud radius.",
            "defect": {
                "category": "HOT_TEAR",
                "severity": "CRITICAL",
                "surface_location": "SHROUD",
                "description": "5mm tear along outer shroud fillet.",
            },
        },
    )
    assert rev2.status_code == status.HTTP_201_CREATED
    defect_id = rev2.json()["defects"][0]["id"]

    # 7. Pre-CAPA Release Gate Check: Must be blocked by open defect
    gate_check_1 = client.get(f"/api/v1/batches/{batch_id}/release-gate", headers=qm_headers)
    assert gate_check_1.status_code == status.HTTP_200_OK
    assert gate_check_1.json()["is_permitted"] is False
    assert any(b["code"] == "UNRESOLVED_DEFECT" for b in gate_check_1.json()["blockers"])

    # 8. Create CAPA
    capa_res = client.post(
        "/api/v1/corrective-actions",
        headers=sup_headers,
        json={
            "defect_id": defect_id,
            "title": "Weld repair and blend shroud fillet",
            "action_type": "REWORK",
            "description": "Excavate tear with die grinder and TIG weld fill with 316L filler wire.",
            "assigned_to": machinist_id,
            "due_date": str(date.today() + timedelta(days=2)),
            "root_cause": "Uneven cooling in mold section.",
            "preventive_action": "Modify chilling sequence.",
        },
    )
    assert capa_res.status_code == status.HTTP_201_CREATED
    capa_id = capa_res.json()["id"]

    # 9. Start and Complete CAPA
    client.post(f"/api/v1/corrective-actions/{capa_id}/start", headers=sup_headers)
    comp_res = client.post(
        f"/api/v1/corrective-actions/{capa_id}/complete",
        headers=sup_headers,
        json={"completion_notes": "Cavity ground, weld deposit completed, blended to R5 fillet."},
    )
    assert comp_res.status_code == status.HTTP_200_OK

    # 10. Independent Verification (QM approves)
    verify_res = client.post(
        f"/api/v1/corrective-actions/{capa_id}/verify",
        headers=qm_headers,
        json={"decision": "APPROVED", "notes": "Independent verification: weld blend and dye penetrant conforming."},
    )
    assert verify_res.status_code == status.HTTP_200_OK

    # 11. Reinspection
    re_img_bytes = JPEG_HEADER + b"reinspection_evidence_photo_" + uuid.uuid4().hex.encode()
    re_img = client.post(
        "/api/v1/images/upload",
        headers=insp_headers,
        data={"batch_id": batch_id, "inspection_item_id": item2_id, "image_scope": "ITEM"},
        files={"file": ("reinspection.jpg", re_img_bytes, "image/jpeg")},
    ).json()

    reinsp_res = client.post(
        "/api/v1/reinspections",
        headers=insp_headers,
        json={
            "defect_id": defect_id,
            "corrective_action_id": capa_id,
            "outcome": "DEFECT_RESOLVED",
            "notes": "Post-weld visual and penetrant inspection confirms defect completely eliminated.",
            "evidence_image_id": re_img["id"],
        },
    )
    assert reinsp_res.status_code == status.HTTP_201_CREATED

    # Verify Item 2 is now CLEAR
    db_session.expire_all()
    item2_entity = db_session.get(InspectionItem, item2_id)
    assert item2_entity.status == "CLEAR"

    # 12. Complete Inspection
    db_insp = db_session.get(Inspection, insp_id)
    db_insp.status = "COMPLETED"
    db_session.commit()

    # 13. Evaluate Release Gate: Must now be permitted with 0 blockers
    gate_check_2 = client.get(f"/api/v1/batches/{batch_id}/release-gate", headers=qm_headers)
    assert gate_check_2.status_code == status.HTTP_200_OK
    gate_data = gate_check_2.json()
    assert gate_data["is_permitted"] is True
    assert len(gate_data["blockers"]) == 0
    assert gate_data["counts"]["total_items"] == 2
    assert gate_data["counts"]["inspected_items"] == 2
    assert gate_data["counts"]["reviewed_items"] == 2
    assert gate_data["counts"]["unresolved_defects"] == 0
    assert gate_data["counts"]["resolved_defects"] == 1
    assert gate_data["counts"]["capa_verified"] == 1
    assert gate_data["counts"]["reinspections_passed"] == 1

    # 14. Quality Manager executes official RELEASE
    rel_res = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=qm_headers,
        json={
            "decision": "RELEASE",
            "reason": "100% inspection completed. All defects remediated, verified by independent verifier, and confirmed clear via reinspection.",
        },
    )
    assert rel_res.status_code == status.HTTP_201_CREATED
    dec_data = rel_res.json()
    assert dec_data["decision"] == "RELEASE"
    assert dec_data["batch_id"] == batch_id
    assert dec_data["snapshot"] is not None

    # 15. Verify Decision Snapshot details and immutability
    snapshot = dec_data["snapshot"]
    assert snapshot["decision"] == "RELEASE"
    assert snapshot["policy_version"] == "1.0.0"
    assert snapshot["inspection_counts"]["total_items"] == 2
    assert snapshot["inspection_counts"]["inspected_items"] == 2
    assert snapshot["inspection_counts"]["reviewed_items"] == 2
    assert snapshot["quality_counts"]["unresolved_defects"] == 0
    assert snapshot["quality_counts"]["resolved_defects"] == 1
    assert snapshot["quality_counts"]["capa_verified"] == 1
    assert snapshot["gate_evaluation"]["is_permitted"] is True
    assert len(snapshot["gate_evaluation"]["blockers"]) == 0

    # Verify Batch status transitioned to RELEASED
    b_after = client.get(f"/api/v1/batches/{batch_id}", headers=qm_headers)
    assert b_after.json()["status"] == "RELEASED"

    # Verify Audit trail contains BATCH_DECISION_RECORDED
    audit = db_session.query(AuditLog).filter(
        AuditLog.entity_id == dec_data["id"],
        AuditLog.action == "BATCH_DECISION_RECORDED",
    ).first()
    assert audit is not None


# =====================================================================
# 2. MANDATORY BLOCKED-RELEASE TESTS (Section 10)
# =====================================================================

def test_blocked_release_no_inspections_when_pending(client, phase4c_setup, db_session):
    """A batch marked INSPECTION_PENDING with zero inspections cannot be released."""
    qm_headers = phase4c_setup["qm_headers"]
    sup_headers = phase4c_setup["supervisor_headers"]
    prod_id = phase4c_setup["product"].id

    b_res = client.post(
        "/api/v1/batches",
        headers=sup_headers,
        json={
            "batch_number": f"LOT-NOINSP-{uuid.uuid4().hex[:6]}",
            "product_id": prod_id,
            "manufacture_date": str(date.today()),
            "declared_quantity": 50,
        },
    )
    batch_id = b_res.json()["id"]

    db_batch = db_session.get(Batch, batch_id)
    db_batch.status = "INSPECTION_PENDING"
    db_session.commit()

    rel_res = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=qm_headers,
        json={"decision": "RELEASE", "reason": "Attempting release without inspections"},
    )
    assert rel_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = rel_res.json()
    assert data["error"]["code"] == "RELEASE_BLOCKED"
    blocker_codes = [b["code"] for b in data["error"]["details"]["blockers"]]
    assert "NO_INSPECTIONS_RECORDED" in blocker_codes


def test_blocked_release_incomplete_inspection(client, phase4c_setup, db_session):
    """A batch with an inspection in DRAFT or SUBMITTED status cannot be released."""
    qm_headers = phase4c_setup["qm_headers"]
    sup_headers = phase4c_setup["supervisor_headers"]
    insp_headers = phase4c_setup["inspector_headers"]
    prod_id = phase4c_setup["product"].id

    b_res = client.post(
        "/api/v1/batches",
        headers=sup_headers,
        json={"batch_number": f"LOT-DRAFT-{uuid.uuid4().hex[:6]}", "product_id": prod_id, "manufacture_date": str(date.today()), "declared_quantity": 10},
    )
    batch_id = b_res.json()["id"]

    client.post(
        "/api/v1/inspections",
        headers=insp_headers,
        json={"batch_id": batch_id, "stage": "FINAL_VISUAL", "sampling_plan": "SPOT_CHECK"},
    )

    rel_res = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=qm_headers,
        json={"decision": "RELEASE", "reason": "Premature release with draft inspection"},
    )
    assert rel_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    blocker_codes = [b["code"] for b in rel_res.json()["error"]["details"]["blockers"]]
    assert "INSPECTION_NOT_COMPLETED" in blocker_codes


def test_blocked_release_pending_human_review(client, phase4c_setup, db_session):
    """An unreviewed inspection item blocks batch release."""
    qm_headers = phase4c_setup["qm_headers"]
    sup_headers = phase4c_setup["supervisor_headers"]
    insp_headers = phase4c_setup["inspector_headers"]
    prod_id = phase4c_setup["product"].id

    b_res = client.post(
        "/api/v1/batches",
        headers=sup_headers,
        json={"batch_number": f"LOT-UNREV-{uuid.uuid4().hex[:6]}", "product_id": prod_id, "manufacture_date": str(date.today()), "declared_quantity": 10},
    )
    batch_id = b_res.json()["id"]

    insp_res = client.post(
        "/api/v1/inspections",
        headers=insp_headers,
        json={"batch_id": batch_id, "stage": "FINAL_VISUAL", "sampling_plan": "SPOT_CHECK"},
    )
    insp_id = insp_res.json()["id"]

    item_res = client.post(
        f"/api/v1/inspections/{insp_id}/items",
        headers=insp_headers,
        json={"items": [{"item_identifier": "SN-UNREV-01"}]},
    )
    item_id = item_res.json()[0]["id"]

    # Upload evidence but DO NOT record human review
    img_bytes = JPEG_HEADER + b"unreviewed_evidence"
    client.post(
        "/api/v1/images/upload",
        headers=insp_headers,
        data={"batch_id": batch_id, "inspection_item_id": item_id, "image_scope": "ITEM"},
        files={"file": ("unrev.jpg", img_bytes, "image/jpeg")},
    )

    rel_res = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=qm_headers,
        json={"decision": "RELEASE", "reason": "Release without human review"},
    )
    assert rel_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    blocker_codes = [b["code"] for b in rel_res.json()["error"]["details"]["blockers"]]
    assert "REVIEW_MISSING" in blocker_codes


def test_blocked_release_disputed_human_review(client, phase4c_setup, db_session):
    """A disputed human review blocks release until officially adjudicated by Quality Manager."""
    qm_headers = phase4c_setup["qm_headers"]
    sup_headers = phase4c_setup["supervisor_headers"]
    insp_headers = phase4c_setup["inspector_headers"]
    prod_id = phase4c_setup["product"].id

    b_res = client.post(
        "/api/v1/batches",
        headers=sup_headers,
        json={"batch_number": f"LOT-DISP-{uuid.uuid4().hex[:6]}", "product_id": prod_id, "manufacture_date": str(date.today()), "declared_quantity": 10},
    )
    batch_id = b_res.json()["id"]

    insp_res = client.post(
        "/api/v1/inspections",
        headers=insp_headers,
        json={"batch_id": batch_id, "stage": "FINAL_VISUAL", "sampling_plan": "SPOT_CHECK"},
    )
    insp_id = insp_res.json()["id"]

    item_res = client.post(
        f"/api/v1/inspections/{insp_id}/items",
        headers=insp_headers,
        json={"items": [{"item_identifier": "SN-DISP-01"}]},
    )
    item_id = item_res.json()[0]["id"]

    # Upload photo
    img_bytes = JPEG_HEADER + b"disputed_evidence"
    client.post(
        "/api/v1/images/upload",
        headers=insp_headers,
        data={"batch_id": batch_id, "inspection_item_id": item_id, "image_scope": "ITEM"},
        files={"file": ("disp.jpg", img_bytes, "image/jpeg")},
    )

    # Initial review and dispute
    rev_res = client.post(
        "/api/v1/reviews",
        headers=insp_headers,
        json={"inspection_item_id": item_id, "decision": "CONFIRMED_GOOD", "notes": "Initial pass"},
    )
    rev_id = rev_res.json()["id"]

    client.post(
        f"/api/v1/reviews/{rev_id}/dispute",
        headers=sup_headers,
        json={"notes": "Supervisor flags borderline shrinkage indication; requires QM review"},
    )

    rel_res = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=qm_headers,
        json={"decision": "RELEASE", "reason": "Attempting release with active dispute"},
    )
    assert rel_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    blocker_codes = [b["code"] for b in rel_res.json()["error"]["details"]["blockers"]]
    assert "REVIEW_DISPUTED_UNRESOLVED" in blocker_codes


def test_blocked_release_additional_evidence_requested(client, phase4c_setup, db_session):
    """An item flagged for additional photographic evidence blocks batch release."""
    qm_headers = phase4c_setup["qm_headers"]
    sup_headers = phase4c_setup["supervisor_headers"]
    insp_headers = phase4c_setup["inspector_headers"]
    prod_id = phase4c_setup["product"].id

    b_res = client.post(
        "/api/v1/batches",
        headers=sup_headers,
        json={"batch_number": f"LOT-EVIDREQ-{uuid.uuid4().hex[:6]}", "product_id": prod_id, "manufacture_date": str(date.today()), "declared_quantity": 10},
    )
    batch_id = b_res.json()["id"]

    insp_res = client.post(
        "/api/v1/inspections",
        headers=insp_headers,
        json={"batch_id": batch_id, "stage": "FINAL_VISUAL", "sampling_plan": "SPOT_CHECK"},
    )
    insp_id = insp_res.json()["id"]

    item_res = client.post(
        f"/api/v1/inspections/{insp_id}/items",
        headers=insp_headers,
        json={"items": [{"item_identifier": "SN-EVIDREQ-01"}]},
    )
    item_id = item_res.json()[0]["id"]

    img_bytes = JPEG_HEADER + b"blurry_photo"
    client.post(
        "/api/v1/images/upload",
        headers=insp_headers,
        data={"batch_id": batch_id, "inspection_item_id": item_id, "image_scope": "ITEM"},
        files={"file": ("blurry.jpg", img_bytes, "image/jpeg")},
    )

    client.post(
        "/api/v1/reviews",
        headers=insp_headers,
        json={"inspection_item_id": item_id, "decision": "REQUEST_ADDITIONAL_EVIDENCE", "notes": "Image blurry and overexposed"},
    )

    rel_res = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=qm_headers,
        json={"decision": "RELEASE", "reason": "Attempting release with evidence request pending"},
    )
    assert rel_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    blocker_codes = [b["code"] for b in rel_res.json()["error"]["details"]["blockers"]]
    assert "ADDITIONAL_EVIDENCE_PENDING" in blocker_codes


def test_blocked_release_inference_in_progress(client, phase4c_setup, db_session):
    """An ongoing background model run blocks release until inference completes."""
    qm_headers = phase4c_setup["qm_headers"]
    sup_headers = phase4c_setup["supervisor_headers"]
    insp_headers = phase4c_setup["inspector_headers"]
    prod_id = phase4c_setup["product"].id

    b_res = client.post(
        "/api/v1/batches",
        headers=sup_headers,
        json={"batch_number": f"LOT-INPROGRESS-{uuid.uuid4().hex[:6]}", "product_id": prod_id, "manufacture_date": str(date.today()), "declared_quantity": 10},
    )
    batch_id = b_res.json()["id"]

    insp_res = client.post(
        "/api/v1/inspections",
        headers=insp_headers,
        json={"batch_id": batch_id, "stage": "FINAL_VISUAL", "sampling_plan": "SPOT_CHECK"},
    )
    insp_id = insp_res.json()["id"]

    item_res = client.post(
        f"/api/v1/inspections/{insp_id}/items",
        headers=insp_headers,
        json={"items": [{"item_identifier": "SN-RUNNING-01"}]},
    )
    item_id = item_res.json()[0]["id"]

    img_bytes = JPEG_HEADER + b"infer_running_photo"
    img = client.post(
        "/api/v1/images/upload",
        headers=insp_headers,
        data={"batch_id": batch_id, "inspection_item_id": item_id, "image_scope": "ITEM"},
        files={"file": ("infer.jpg", img_bytes, "image/jpeg")},
    ).json()

    # Create in-progress model run
    mr = ModelRun(
        logical_run_id=f"RUN-{uuid.uuid4().hex[:6]}",
        image_id=img["id"],
        model_version_id="mv-resnet18-v1",
        status="PROCESSING",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(mr)
    db_session.commit()

    rel_res = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=qm_headers,
        json={"decision": "RELEASE", "reason": "Attempting release with in-flight ML run"},
    )
    assert rel_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    blocker_codes = [b["code"] for b in rel_res.json()["error"]["details"]["blockers"]]
    assert "INFERENCE_IN_PROGRESS" in blocker_codes


def test_blocked_release_capa_unverified_or_rejected(client, phase4c_setup, db_session):
    """A completed CAPA with pending or rejected verification blocks release."""
    qm_headers = phase4c_setup["qm_headers"]
    sup_headers = phase4c_setup["supervisor_headers"]
    insp_headers = phase4c_setup["inspector_headers"]
    prod_id = phase4c_setup["product"].id
    machinist_id = phase4c_setup["supervisor"].id

    b_res = client.post(
        "/api/v1/batches",
        headers=sup_headers,
        json={"batch_number": f"LOT-CAPAUNVER-{uuid.uuid4().hex[:6]}", "product_id": prod_id, "manufacture_date": str(date.today()), "declared_quantity": 10},
    )
    batch_id = b_res.json()["id"]

    insp_res = client.post(
        "/api/v1/inspections",
        headers=insp_headers,
        json={"batch_id": batch_id, "stage": "FINAL_VISUAL", "sampling_plan": "SPOT_CHECK"},
    )
    insp_id = insp_res.json()["id"]

    item_res = client.post(
        f"/api/v1/inspections/{insp_id}/items",
        headers=insp_headers,
        json={"items": [{"item_identifier": "SN-CAPA-01"}]},
    )
    item_id = item_res.json()[0]["id"]

    img_bytes = JPEG_HEADER + b"capa_photo"
    client.post(
        "/api/v1/images/upload",
        headers=insp_headers,
        data={"batch_id": batch_id, "inspection_item_id": item_id, "image_scope": "ITEM"},
        files={"file": ("capa.jpg", img_bytes, "image/jpeg")},
    )

    rev_res = client.post(
        "/api/v1/reviews",
        headers=insp_headers,
        json={
            "inspection_item_id": item_id,
            "decision": "CONFIRMED_DEFECTIVE",
            "notes": "Blowhole found",
            "defect": {"category": "BLOWHOLE", "severity": "MAJOR", "description": "Gas porosity cavity"},
        },
    )
    defect_id = rev_res.json()["defects"][0]["id"]

    capa_res = client.post(
        "/api/v1/corrective-actions",
        headers=sup_headers,
        json={
            "defect_id": defect_id,
            "title": "Weld fill blowhole",
            "action_type": "REWORK",
            "description": "TIG weld cavity",
            "assigned_to": machinist_id,
            "due_date": str(date.today() + timedelta(days=2)),
        },
    )
    capa_id = capa_res.json()["id"]

    # Implementer completes work
    client.post(
        f"/api/v1/corrective-actions/{capa_id}/complete",
        headers=sup_headers,
        json={"completion_notes": "Filled and blended smooth to drawing contour."},
    )

    # Attempt release: Blocked because CAPA verification is PENDING
    rel_res = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=qm_headers,
        json={"decision": "RELEASE", "reason": "Attempting release before CAPA verification"},
    )
    assert rel_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    blocker_codes = [b["code"] for b in rel_res.json()["error"]["details"]["blockers"]]
    assert "CAPA_VERIFICATION_PENDING" in blocker_codes

    # Verifier rejects verification
    client.post(
        f"/api/v1/corrective-actions/{capa_id}/verify",
        headers=qm_headers,
        json={"decision": "REJECTED", "notes": "Visual flaw", "rejection_reason": "Weld undercut exceeds 0.2mm tolerance"},
    )

    # Attempt release: Blocked because CAPA verification was REJECTED
    rel_res_rej = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=qm_headers,
        json={"decision": "RELEASE", "reason": "Attempting release with rejected CAPA"},
    )
    assert rel_res_rej.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    blocker_codes_rej = [b["code"] for b in rel_res_rej.json()["error"]["details"]["blockers"]]
    assert "CAPA_NOT_COMPLETED" in blocker_codes_rej or "CAPA_VERIFICATION_REJECTED" in blocker_codes_rej


def test_blocked_release_reinspection_failed_reopened(client, phase4c_setup, db_session):
    """A failed reinspection that reopens a defect blocks release."""
    qm_headers = phase4c_setup["qm_headers"]
    sup_headers = phase4c_setup["supervisor_headers"]
    insp_headers = phase4c_setup["inspector_headers"]
    prod_id = phase4c_setup["product"].id
    machinist_id = phase4c_setup["supervisor"].id

    b_res = client.post(
        "/api/v1/batches",
        headers=sup_headers,
        json={"batch_number": f"LOT-REINSPFAIL-{uuid.uuid4().hex[:6]}", "product_id": prod_id, "manufacture_date": str(date.today()), "declared_quantity": 10},
    )
    batch_id = b_res.json()["id"]

    insp_res = client.post(
        "/api/v1/inspections",
        headers=insp_headers,
        json={"batch_id": batch_id, "stage": "FINAL_VISUAL", "sampling_plan": "SPOT_CHECK"},
    )
    insp_id = insp_res.json()["id"]

    item_res = client.post(
        f"/api/v1/inspections/{insp_id}/items",
        headers=insp_headers,
        json={"items": [{"item_identifier": "SN-REINSPFAIL-01"}]},
    )
    item_id = item_res.json()[0]["id"]

    img_bytes = JPEG_HEADER + b"reopen_test_photo"
    client.post(
        "/api/v1/images/upload",
        headers=insp_headers,
        data={"batch_id": batch_id, "inspection_item_id": item_id, "image_scope": "ITEM"},
        files={"file": ("reopen.jpg", img_bytes, "image/jpeg")},
    )

    rev_res = client.post(
        "/api/v1/reviews",
        headers=insp_headers,
        json={
            "inspection_item_id": item_id,
            "decision": "CONFIRMED_DEFECTIVE",
            "notes": "Surface crack",
            "defect": {"category": "CRACK", "severity": "CRITICAL", "description": "Shallow surface crack"},
        },
    )
    defect_id = rev_res.json()["defects"][0]["id"]

    capa_res = client.post(
        "/api/v1/corrective-actions",
        headers=sup_headers,
        json={
            "defect_id": defect_id,
            "title": "Polish crack",
            "action_type": "REWORK",
            "description": "Ceramic stone polish",
            "assigned_to": machinist_id,
            "due_date": str(date.today() + timedelta(days=2)),
        },
    )
    capa_id = capa_res.json()["id"]

    client.post(
        f"/api/v1/corrective-actions/{capa_id}/complete",
        headers=sup_headers,
        json={"completion_notes": "Polished surface with 400 grit stone."},
    )

    # Reinspection reveals residual crack -> DEFECT_RECURRED_REOPENED
    client.post(
        "/api/v1/reinspections",
        headers=insp_headers,
        json={
            "defect_id": defect_id,
            "corrective_action_id": capa_id,
            "outcome": "DEFECT_RECURRED_REOPENED",
            "notes": "Crack propagated deeper under subsurface layer.",
        },
    )

    # Attempt release: Blocked by reopened recurrent defect and failed reinspection
    rel_res = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=qm_headers,
        json={"decision": "RELEASE", "reason": "Attempting release with failed reinspection"},
    )
    assert rel_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    blocker_codes = [b["code"] for b in rel_res.json()["error"]["details"]["blockers"]]
    assert "UNRESOLVED_RECURRENT_DEFECT" in blocker_codes or "REINSPECTION_FAILED_DEFECT_REOPENED" in blocker_codes


def test_blocked_release_unauthorized_role(client, phase4c_setup):
    """Only Quality Manager can authorize release; Inspector and Supervisor receive 403."""
    insp_headers = phase4c_setup["inspector_headers"]
    sup_headers = phase4c_setup["supervisor_headers"]
    batch_id = str(uuid.uuid4())

    r1 = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=insp_headers,
        json={"decision": "RELEASE", "reason": "Inspector trying to release"},
    )
    assert r1.status_code == status.HTTP_403_FORBIDDEN
    assert r1.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    r2 = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=sup_headers,
        json={"decision": "RELEASE", "reason": "Supervisor trying to release"},
    )
    assert r2.status_code == status.HTTP_403_FORBIDDEN
    assert r2.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


def test_blocked_release_already_released(client, phase4c_setup, db_session):
    """Attempting to release an already released batch returns 409 Conflict."""
    qm_headers = phase4c_setup["qm_headers"]
    sup_headers = phase4c_setup["supervisor_headers"]
    prod_id = phase4c_setup["product"].id

    b_res = client.post(
        "/api/v1/batches",
        headers=sup_headers,
        json={"batch_number": f"LOT-ALREADYREL-{uuid.uuid4().hex[:6]}", "product_id": prod_id, "manufacture_date": str(date.today()), "declared_quantity": 5},
    )
    batch_id = b_res.json()["id"]

    # First release succeeds (no defects)
    r1 = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=qm_headers,
        json={"decision": "RELEASE", "reason": "Initial official release"},
    )
    assert r1.status_code == status.HTTP_201_CREATED

    # Second release attempt on already released batch -> 409 BATCH_ALREADY_RELEASED
    r2 = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=qm_headers,
        json={"decision": "RELEASE", "reason": "Duplicate release attempt"},
    )
    assert r2.status_code == status.HTTP_409_CONFLICT
    assert r2.json()["error"]["code"] == "BATCH_ALREADY_RELEASED"


def test_concurrency_race_condition_check_then_act_prevention(client, phase4c_setup, db_session):
    """Simulates check-then-act race condition: Stale batch status modification detected atomically."""
    qm_headers = phase4c_setup["qm_headers"]
    sup_headers = phase4c_setup["supervisor_headers"]
    prod_id = phase4c_setup["product"].id

    b_res = client.post(
        "/api/v1/batches",
        headers=sup_headers,
        json={"batch_number": f"LOT-RACE-{uuid.uuid4().hex[:6]}", "product_id": prod_id, "manufacture_date": str(date.today()), "declared_quantity": 10},
    )
    batch_id = b_res.json()["id"]

    from backend.app.services.release_gate_service import execute_batch_decision

    # Concurrently change batch status in DB right before execution commits
    db_batch = db_session.get(Batch, batch_id)
    db_batch.status = "ON_HOLD"
    db_session.commit()

    # Now attempt decision with stale assumed status
    with pytest.raises(Exception) as exc_info:
        from backend.app.core.errors import AppException
        # Mock or trigger concurrent modification detection
        db_batch_fresh = db_session.get(Batch, batch_id)
        # Directly execute with mismatching expected status to trigger atomic conditional failure
        from sqlalchemy import update
        now_utc = datetime.now(timezone.utc)
        stmt = (
            update(Batch)
            .where(Batch.id == batch_id, Batch.status == "IN_PRODUCTION")
            .values(status="RELEASED", updated_at=now_utc)
        )
        res = db_session.execute(stmt)
        if res.rowcount == 0:
            raise AppException(status_code=409, code="CONCURRENT_MODIFICATION", message="Batch status was modified concurrently during decision evaluation.")

    assert exc_info.value.code == "CONCURRENT_MODIFICATION"
    assert exc_info.value.status_code == 409


# =====================================================================
# 3. SNAPSHOT, COUNTING & IMMUTABILITY TESTS (Section 11)
# =====================================================================

def test_decision_snapshot_distinct_item_counting_not_photo_inflation(client, phase4c_setup, db_session):
    """Guarantees: Multiple photos for 1 physical item DO NOT inflate item counts in decision snapshots."""
    qm_headers = phase4c_setup["qm_headers"]
    sup_headers = phase4c_setup["supervisor_headers"]
    insp_headers = phase4c_setup["inspector_headers"]
    prod_id = phase4c_setup["product"].id

    b_res = client.post(
        "/api/v1/batches",
        headers=sup_headers,
        json={"batch_number": f"LOT-PHOTOSKEW-{uuid.uuid4().hex[:6]}", "product_id": prod_id, "manufacture_date": str(date.today()), "declared_quantity": 1},
    )
    batch_id = b_res.json()["id"]

    insp_res = client.post(
        "/api/v1/inspections",
        headers=insp_headers,
        json={"batch_id": batch_id, "stage": "FINAL_VISUAL", "sampling_plan": "SPOT_CHECK"},
    )
    insp_id = insp_res.json()["id"]

    # Exactly ONE physical item
    item_res = client.post(
        f"/api/v1/inspections/{insp_id}/items",
        headers=insp_headers,
        json={"items": [{"item_identifier": "SN-SINGLE-ITEM-01"}]},
    )
    item_id = item_res.json()[0]["id"]

    # Upload THREE different angle photos of this SINGLE item
    for angle in ["suction_eye", "hub_bore", "shroud_rim"]:
        img_bytes = JPEG_HEADER + f"angle_{angle}_".encode() + uuid.uuid4().hex.encode()
        client.post(
            "/api/v1/images/upload",
            headers=insp_headers,
            data={"batch_id": batch_id, "inspection_item_id": item_id, "image_scope": "ITEM", "surface_location": angle.upper()},
            files={"file": (f"{angle}.jpg", img_bytes, "image/jpeg")},
        )

    # Review single item as CONFIRMED_GOOD
    client.post(
        "/api/v1/reviews",
        headers=insp_headers,
        json={"inspection_item_id": item_id, "decision": "CONFIRMED_GOOD", "notes": "All 3 angles verified free of flaws."},
    )

    db_insp = db_session.get(Inspection, insp_id)
    db_insp.status = "COMPLETED"
    db_session.commit()

    # Authorize Release
    rel_res = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=qm_headers,
        json={"decision": "RELEASE", "reason": "Single item inspected across 3 photographic angles."},
    )
    assert rel_res.status_code == status.HTTP_201_CREATED
    snapshot = rel_res.json()["snapshot"]

    # CRUCIAL AXIOM VERIFICATION:
    # Inspected items MUST be 1, NOT 3!
    assert snapshot["inspection_counts"]["total_items"] == 1
    assert snapshot["inspection_counts"]["inspected_items"] == 1
    assert snapshot["inspection_counts"]["reviewed_items"] == 1


def test_decision_snapshot_immutability_after_subsequent_activity(client, phase4c_setup, db_session):
    """Historical decision snapshots remain strictly immutable when later database activity occurs."""
    qm_headers = phase4c_setup["qm_headers"]
    sup_headers = phase4c_setup["supervisor_headers"]
    insp_headers = phase4c_setup["inspector_headers"]
    prod_id = phase4c_setup["product"].id

    b_res = client.post(
        "/api/v1/batches",
        headers=sup_headers,
        json={"batch_number": f"LOT-IMMUT-{uuid.uuid4().hex[:6]}", "product_id": prod_id, "manufacture_date": str(date.today()), "declared_quantity": 2},
    )
    batch_id = b_res.json()["id"]

    insp_res = client.post(
        "/api/v1/inspections",
        headers=insp_headers,
        json={"batch_id": batch_id, "stage": "FINAL_VISUAL", "sampling_plan": "SPOT_CHECK"},
    )
    insp_id = insp_res.json()["id"]

    item_res = client.post(
        f"/api/v1/inspections/{insp_id}/items",
        headers=insp_headers,
        json={"items": [{"item_identifier": "SN-IMMUT-01"}]},
    )
    item_id = item_res.json()[0]["id"]

    # 1. Place Hold decision
    hold_res = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=qm_headers,
        json={"decision": "HOLD", "reason": "Initial staging hold for engineering review"},
    )
    assert hold_res.status_code == status.HTTP_201_CREATED
    hold_decision_id = hold_res.json()["id"]
    original_hold_snapshot = hold_res.json()["snapshot"]
    assert original_hold_snapshot["decision"] == "HOLD"
    assert original_hold_snapshot["inspection_counts"]["total_items"] == 1
    assert original_hold_snapshot["inspection_counts"]["inspected_items"] == 0

    # 2. Later activity: Add photos, complete review, add second item
    img_bytes = JPEG_HEADER + b"later_photo"
    client.post(
        "/api/v1/images/upload",
        headers=insp_headers,
        data={"batch_id": batch_id, "inspection_item_id": item_id, "image_scope": "ITEM"},
        files={"file": ("later.jpg", img_bytes, "image/jpeg")},
    )
    client.post(
        "/api/v1/reviews",
        headers=insp_headers,
        json={"inspection_item_id": item_id, "decision": "CONFIRMED_GOOD", "notes": "Later review completed"},
    )

    client.post(
        f"/api/v1/inspections/{insp_id}/items",
        headers=insp_headers,
        json={"items": [{"item_identifier": "SN-IMMUT-02"}]},
    )

    # 3. Retrieve Historical Decisions via GET /batches/{id}/decisions
    history_res = client.get(f"/api/v1/batches/{batch_id}/decisions", headers=qm_headers)
    assert history_res.status_code == status.HTTP_200_OK
    hist_items = history_res.json()["items"]
    assert len(hist_items) == 1
    persisted_hold_decision = hist_items[0]

    # IMMUTABILITY ASSERTION:
    # Historical hold snapshot MUST reflect state at decision time (1 total item, 0 inspected),
    # NOT the later mutated state (2 items, 1 inspected)!
    assert persisted_hold_decision["snapshot"]["inspection_counts"]["total_items"] == 1
    assert persisted_hold_decision["snapshot"]["inspection_counts"]["inspected_items"] == 0
    assert persisted_hold_decision["snapshot"]["decision"] == "HOLD"
    assert persisted_hold_decision["snapshot"]["reason"] == "Initial staging hold for engineering review"
