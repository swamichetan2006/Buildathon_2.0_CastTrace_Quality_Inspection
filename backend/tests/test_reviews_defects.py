import uuid
import hashlib
from datetime import date, datetime, timezone
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
    AuditLog,
)

JPEG_HEADER = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"\x00" * 50


@pytest.fixture
def secondary_qm(db_session):
    """Creates a second Quality Manager for Four-Eyes separation-of-duty tests."""
    u = db_session.query(User).filter(User.username == "test_qm_secondary").first()
    if not u:
        u = User(
            username="test_qm_secondary",
            email="qm2@casttrace.local",
            full_name="Secondary Quality Manager",
            role="QUALITY_MANAGER",
            hashed_password=hash_password("Password123!"),
            is_active=True,
        )
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
    return u


@pytest.fixture
def secondary_qm_headers(secondary_qm):
    token = create_access_token({"sub": secondary_qm.id, "username": secondary_qm.username, "role": secondary_qm.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def quality_lifecycle_setup(client, inspector_headers, supervisor_headers, qm_headers, temp_storage, db_session):
    """Sets up product, batch, inspection, item, image, and model run."""
    # 1. Product & Batch
    prod_sku = f"PROD-QL-{uuid.uuid4().hex[:6]}"
    p_res = client.post(
        "/api/v1/products",
        headers=qm_headers,
        json={"sku": prod_sku, "name": "Impeller 200mm", "material": "CF8M Stainless Steel"},
    )
    prod_id = p_res.json()["id"]

    b_res = client.post(
        "/api/v1/batches",
        headers=supervisor_headers,
        json={
            "batch_number": f"BATCH-QL-{uuid.uuid4().hex[:6]}",
            "product_id": prod_id,
            "manufacture_date": str(date.today()),
            "declared_quantity": 20,
        },
    )
    batch_id = b_res.json()["id"]

    # 2. Inspection & Items
    insp_res = client.post(
        "/api/v1/inspections",
        headers=inspector_headers,
        json={"batch_id": batch_id, "stage": "FINAL_VISUAL", "sampling_plan": "NORMAL"},
    )
    insp_id = insp_res.json()["id"]

    item_res = client.post(
        f"/api/v1/inspections/{insp_id}/items",
        headers=inspector_headers,
        json={"items": [{"item_identifier": f"ITEM-QL-{uuid.uuid4().hex[:4]}", "cavity_number": 1}]},
    )
    item_id = item_res.json()[0]["id"]

    # 3. Model Version
    ver = db_session.query(ModelVersion).filter(ModelVersion.version_name == "v1.0.0-resnet18").first()
    if not ver:
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

    # 4. Upload Image
    file_bytes = JPEG_HEADER + b"evidence_payload_" + uuid.uuid4().hex.encode()
    img_res = client.post(
        "/api/v1/images/upload",
        headers=inspector_headers,
        data={"batch_id": batch_id, "inspection_item_id": item_id, "image_scope": "ITEM"},
        files={"file": ("evidence.jpg", file_bytes, "image/jpeg")},
    )
    image_data = img_res.json()
    image_id = image_data["id"]

    # 5. Model Run (Simulated Succeeded Run predicting DEFECTIVE)
    run = ModelRun(
        logical_run_id=str(uuid.uuid4()),
        image_id=image_id,
        model_version_id=ver.id,
        status="SUCCEEDED",
        predicted_label="DEFECTIVE",
        score=0.96540,
        score_type="PROBABILITY_DEFECTIVE",
        threshold_applied=0.50,
        routing_outcome="LIKELY_DEFECTIVE",
        routing_reason="High-confidence defect detected",
        processing_latency_ms=45,
        attempt_number=1,
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    return {
        "batch_id": batch_id,
        "inspection_id": insp_id,
        "item_id": item_id,
        "image_id": image_id,
        "model_run_id": run.id,
    }


def test_human_review_confirmed_defective_creates_defect_and_snapshot(client, inspector_headers, quality_lifecycle_setup, db_session):
    """Milestone 4A: Inspector confirms defective, defect record is created, and immutable AI snapshot is preserved."""
    item_id = quality_lifecycle_setup["item_id"]
    run_id = quality_lifecycle_setup["model_run_id"]

    payload = {
        "inspection_item_id": item_id,
        "model_run_id": run_id,
        "decision": "CONFIRMED_DEFECTIVE",
        "notes": "Verified surface shrink porosity along vane #2 edge.",
        "defect": {
            "category": "SHRINKAGE_POROSITY",
            "severity": "MAJOR",
            "surface_location": "VANE_PRESSURE_SIDE",
            "description": "4mm porous cluster near outer shroud junction.",
        },
    }

    res = client.post("/api/v1/reviews", headers=inspector_headers, json=payload)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()

    # 1. Verify Review record
    assert data["decision"] == "CONFIRMED_DEFECTIVE"
    assert data["model_disagreement"] is False  # Model was DEFECTIVE, human confirmed DEFECTIVE
    assert data["notes"] == payload["notes"]
    assert len(data["defects"]) == 1

    # 2. Verify Immutable AI Snapshot (Rule 2)
    snapshot = data["ai_snapshot"]
    assert snapshot is not None
    assert snapshot["model_run_id"] == run_id
    assert snapshot["predicted_label"] == "DEFECTIVE"
    assert snapshot["score"] == 0.96540
    assert snapshot["routing_outcome"] == "LIKELY_DEFECTIVE"
    assert snapshot["human_decision"] == "CONFIRMED_DEFECTIVE"
    assert snapshot["image_sha256"] is not None
    assert "evidence_images" in snapshot
    assert snapshot["total_images"] == 1
    assert len(snapshot["evidence_images"]) == 1
    assert snapshot["evidence_images"][0]["sha256_hash"] == snapshot["image_sha256"]

    # 3. Verify Defect record
    defect = data["defects"][0]
    assert defect["defect_number"].startswith("DEF-")
    assert defect["category"] == "SHRINKAGE_POROSITY"
    assert defect["severity"] == "MAJOR"
    assert defect["status"] == "OPEN"
    assert defect["surface_location"] == "VANE_PRESSURE_SIDE"

    # 4. Verify InspectionItem status updated
    item_obj = db_session.get(InspectionItem, item_id)
    assert item_obj.status == "CONFIRMED_DEFECTIVE"

    # 5. Verify Audit Log entry
    audit = db_session.query(AuditLog).filter(AuditLog.entity_id == data["id"], AuditLog.action == "REVIEW_CONFIRMED_DEFECTIVE").first()
    assert audit is not None


def test_human_review_confirmed_good_and_model_disagreement_tracking(client, inspector_headers, quality_lifecycle_setup, db_session):
    """Milestone 4A: Inspector overrides ML defective prediction to GOOD, tracking model disagreement."""
    item_id = quality_lifecycle_setup["item_id"]
    run_id = quality_lifecycle_setup["model_run_id"]

    # Model predicted DEFECTIVE, inspector verifies it is conforming (optical glare/water mark)
    payload = {
        "inspection_item_id": item_id,
        "model_run_id": run_id,
        "decision": "CONFIRMED_GOOD",
        "notes": "Surface inspected under magnification; artifact was grease residue, surface conforms to spec.",
    }

    res = client.post("/api/v1/reviews", headers=inspector_headers, json=payload)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()

    # Disagreement must be TRUE
    assert data["decision"] == "CONFIRMED_GOOD"
    assert data["model_disagreement"] is True
    assert data["defects"] == []

    # Item status is CLEAR
    item_obj = db_session.get(InspectionItem, item_id)
    assert item_obj.status == "CLEAR"

    # Attempting to supply defect details when confirming good must fail with 422
    payload_invalid = {
        "inspection_item_id": item_id,
        "decision": "CONFIRMED_GOOD",
        "defect": {"category": "CRACK", "severity": "MINOR", "description": "Contradictory defect"},
    }
    res_inv = client.post("/api/v1/reviews", headers=inspector_headers, json=payload_invalid)
    assert res_inv.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_controlled_review_outcomes_and_notes_validation(client, inspector_headers, quality_lifecycle_setup):
    """Milestone 4A: DISPUTED and REQUEST_ADDITIONAL_EVIDENCE require explanatory notes."""
    item_id = quality_lifecycle_setup["item_id"]

    # 1. DISPUTED without notes fails
    res_dispute = client.post(
        "/api/v1/reviews",
        headers=inspector_headers,
        json={"inspection_item_id": item_id, "decision": "DISPUTED", "notes": ""},
    )
    assert res_dispute.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 2. REQUEST_ADDITIONAL_EVIDENCE without notes fails
    res_ev = client.post(
        "/api/v1/reviews",
        headers=inspector_headers,
        json={"inspection_item_id": item_id, "decision": "REQUEST_ADDITIONAL_EVIDENCE", "notes": "bad"},
    )
    assert res_ev.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 3. Invalid decision string fails validation
    res_bogus = client.post(
        "/api/v1/reviews",
        headers=inspector_headers,
        json={"inspection_item_id": item_id, "decision": "MAYBE_OK"},
    )
    assert res_bogus.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_dispute_and_adjudication_lifecycle(client, inspector_headers, supervisor_headers, qm_headers, quality_lifecycle_setup, db_session):
    """Milestone 4A: Review dispute escalation and Quality Manager exclusive adjudication."""
    item_id = quality_lifecycle_setup["item_id"]

    # 1. Inspector posts initial review as DISPUTED
    rev_res = client.post(
        "/api/v1/reviews",
        headers=inspector_headers,
        json={
            "inspection_item_id": item_id,
            "decision": "DISPUTED",
            "notes": "Indication near blade tip could be surface oxide rather than cold shut.",
        },
    )
    assert rev_res.status_code == status.HTTP_201_CREATED
    rev_id = rev_res.json()["id"]

    # 2. Inspector attempts to adjudicate -> FORBIDDEN (QM only)
    res_insp_adj = client.post(
        f"/api/v1/reviews/{rev_id}/adjudicate",
        headers=inspector_headers,
        json={"decision": "CONFIRMED_GOOD", "notes": "Inspector trying to self-adjudicate"},
    )
    assert res_insp_adj.status_code == status.HTTP_403_FORBIDDEN

    # 3. Supervisor attempts to adjudicate -> FORBIDDEN
    res_sup_adj = client.post(
        f"/api/v1/reviews/{rev_id}/adjudicate",
        headers=supervisor_headers,
        json={"decision": "CONFIRMED_GOOD", "notes": "Supervisor trying to adjudicate"},
    )
    assert res_sup_adj.status_code == status.HTTP_403_FORBIDDEN

    # 4. Quality Manager adjudicates as CONFIRMED_GOOD
    res_qm_adj = client.post(
        f"/api/v1/reviews/{rev_id}/adjudicate",
        headers=qm_headers,
        json={
            "decision": "CONFIRMED_GOOD",
            "notes": "Metallurgical dye penetrant test negative. Discoloration only; part accepted.",
        },
    )
    assert res_qm_adj.status_code == status.HTTP_200_OK
    adj_data = res_qm_adj.json()
    assert adj_data["decision"] == "CONFIRMED_GOOD"

    # Item is now CLEAR
    item_obj = db_session.get(InspectionItem, item_id)
    assert item_obj.status == "CLEAR"


def test_controlled_defect_categories_and_severities(client, inspector_headers, quality_lifecycle_setup):
    """Milestone 4A: Reject unapproved defect categories; accept approved taxonomy."""
    item_id = quality_lifecycle_setup["item_id"]

    # 1. Guessed category fails
    res_bad = client.post(
        "/api/v1/reviews",
        headers=inspector_headers,
        json={
            "inspection_item_id": item_id,
            "decision": "CONFIRMED_DEFECTIVE",
            "notes": "Testing bad category",
            "defect": {
                "category": "GUESSED_UNOFFICIAL_SCRATCH",
                "severity": "MAJOR",
                "description": "Some defect description",
            },
        },
    )
    assert res_bad.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 2. Approved categories (e.g. CRACK, BLOWHOLE, PINHOLE, COLD_SHUT) succeed
    approved_categories = ["BLOWHOLE", "PINHOLE", "HOT_TEAR", "COLD_SHUT", "CRACK"]
    for cat in approved_categories:
        res_ok = client.post(
            "/api/v1/reviews",
            headers=inspector_headers,
            json={
                "inspection_item_id": item_id,
                "decision": "CONFIRMED_DEFECTIVE",
                "notes": f"Testing approved category {cat}",
                "defect": {
                    "category": cat,
                    "severity": "MINOR",
                    "description": f"Verified {cat} observed on hub.",
                },
            },
        )
        assert res_ok.status_code == status.HTTP_201_CREATED
        assert res_ok.json()["defects"][0]["category"] == cat


def test_four_eyes_separation_of_duty_defect_closure(client, qm_headers, secondary_qm_headers, quality_lifecycle_setup, db_session):
    """Milestone 4A Rule 6: The reviewer who logged the defect cannot approve its closure."""
    item_id = quality_lifecycle_setup["item_id"]

    # 1. Quality Manager 1 logs a confirmed defect
    rev_res = client.post(
        "/api/v1/reviews",
        headers=qm_headers,
        json={
            "inspection_item_id": item_id,
            "decision": "CONFIRMED_DEFECTIVE",
            "notes": "Logged by QM 1",
            "defect": {
                "category": "CRACK",
                "severity": "CRITICAL",
                "description": "Thermal shock crack across vane root.",
            },
        },
    )
    assert rev_res.status_code == status.HTTP_201_CREATED
    defect_id = rev_res.json()["defects"][0]["id"]

    # 2. Quality Manager 1 attempts to resolve their OWN created defect -> FORBIDDEN (Four-Eyes Violation)
    res_self_resolve = client.post(
        f"/api/v1/defects/{defect_id}/resolve",
        headers=qm_headers,
        json={"resolution_notes": "Attempting to self-approve closure of my own defect."},
    )
    assert res_self_resolve.status_code == status.HTTP_403_FORBIDDEN
    assert res_self_resolve.json()["error"]["code"] == "FOUR_EYES_VIOLATION"

    # Defect remains OPEN
    defect_obj = db_session.get(Defect, defect_id)
    assert defect_obj.status == "OPEN"

    # 3. Secondary Quality Manager (independent reviewer) resolves the defect -> SUCCEEDS
    res_independent_resolve = client.post(
        f"/api/v1/defects/{defect_id}/resolve",
        headers=secondary_qm_headers,
        json={"resolution_notes": "Independent review: Dye penetrant inspection confirmed complete weld repair."},
    )
    assert res_independent_resolve.status_code == status.HTTP_200_OK
    resolved_data = res_independent_resolve.json()
    assert resolved_data["status"] == "RESOLVED"
    assert resolved_data["resolved_by"] is not None

    # Defect is now RESOLVED in database
    db_session.refresh(defect_obj)
    assert defect_obj.status == "RESOLVED"


def test_defect_reopen_and_concurrency_protection(client, inspector_headers, secondary_qm_headers, quality_lifecycle_setup, db_session):
    """Milestone 4A: Reopen resolved defect and verify atomic state transition."""
    item_id = quality_lifecycle_setup["item_id"]

    # 1. Create and independently resolve a defect
    rev_res = client.post(
        "/api/v1/reviews",
        headers=inspector_headers,
        json={
            "inspection_item_id": item_id,
            "decision": "CONFIRMED_DEFECTIVE",
            "notes": "Inspector logged",
            "defect": {"category": "PINHOLE", "severity": "MINOR", "description": "Small pinhole on shroud."},
        },
    )
    defect_id = rev_res.json()["defects"][0]["id"]

    # Resolve by QM
    client.post(
        f"/api/v1/defects/{defect_id}/resolve",
        headers=secondary_qm_headers,
        json={"resolution_notes": "Polished and acceptable."},
    )

    # 2. Reopen the resolved defect
    res_reopen = client.post(
        f"/api/v1/defects/{defect_id}/reopen",
        headers=inspector_headers,
        json={"reopen_notes": "Pinhole reappeared after surface grinding."},
    )
    assert res_reopen.status_code == status.HTTP_200_OK
    assert res_reopen.json()["status"] == "REOPENED"

    # 3. Cannot reopen a defect that is already REOPENED
    res_reopen_again = client.post(
        f"/api/v1/defects/{defect_id}/reopen",
        headers=inspector_headers,
        json={"reopen_notes": "Trying to reopen again."},
    )
    assert res_reopen_again.status_code == status.HTTP_409_CONFLICT


def test_recurrence_relationship_preservation(client, inspector_headers, quality_lifecycle_setup, db_session):
    """Milestone 4A Rule 9: Explicit recurrence link between prior defect and new defect."""
    item_id = quality_lifecycle_setup["item_id"]

    # Defect 1
    r1 = client.post(
        "/api/v1/reviews",
        headers=inspector_headers,
        json={
            "inspection_item_id": item_id,
            "decision": "CONFIRMED_DEFECTIVE",
            "notes": "Initial defect",
            "defect": {"category": "HOT_TEAR", "severity": "MAJOR", "description": "Initial tear"},
        },
    )
    def1_id = r1.json()["defects"][0]["id"]

    # Defect 2 explicitly linked as recurrence of Defect 1
    r2 = client.post(
        "/api/v1/reviews",
        headers=inspector_headers,
        json={
            "inspection_item_id": item_id,
            "decision": "CONFIRMED_DEFECTIVE",
            "notes": "Recurrent defect observation",
            "defect": {
                "category": "HOT_TEAR",
                "severity": "CRITICAL",
                "description": "Recurrence along same thermal gradient",
                "prior_defect_id": def1_id,
            },
        },
    )
    assert r2.status_code == status.HTTP_201_CREATED
    def2_id = r2.json()["defects"][0]["id"]

    # Verify database relationship
    def2_obj = db_session.get(Defect, def2_id)
    assert def2_obj.prior_defect_id == def1_id
    assert def2_obj.prior_defect.id == def1_id


def test_review_querying_and_disagreement_filter(client, inspector_headers, quality_lifecycle_setup):
    """Milestone 4A: Query reviews with model_disagreement filter for AI-human disagreement audit."""
    item_id = quality_lifecycle_setup["item_id"]
    run_id = quality_lifecycle_setup["model_run_id"]

    # Post disagreement review
    client.post(
        "/api/v1/reviews",
        headers=inspector_headers,
        json={
            "inspection_item_id": item_id,
            "model_run_id": run_id,
            "decision": "CONFIRMED_GOOD",
            "notes": "Overturning ML suggestion",
        },
    )

    # Query with model_disagreement=true
    res = client.get("/api/v1/reviews?model_disagreement=true", headers=inspector_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["total"] >= 1
    assert all(r["model_disagreement"] is True for r in data["items"])


def test_multi_image_review_snapshot_capture_and_immutability(
    client, inspector_headers, qm_headers, supervisor_headers, temp_storage, db_session
):
    """Verify multi-image review snapshots: captures all active evidence images, hashes, and ensures immutability against later uploads/runs."""
    # 1. Setup item
    prod = client.post(
        "/api/v1/products",
        headers=qm_headers,
        json={"sku": f"SKU-MULTI-{uuid.uuid4().hex[:6]}", "name": "Pump Housing", "material": "Grey Cast Iron"},
    ).json()
    batch = client.post(
        "/api/v1/batches",
        headers=supervisor_headers,
        json={
            "batch_number": f"BATCH-MULTI-{uuid.uuid4().hex[:6]}",
            "product_id": prod["id"],
            "manufacture_date": str(date.today()),
            "declared_quantity": 5,
        },
    ).json()
    insp = client.post(
        "/api/v1/inspections",
        headers=inspector_headers,
        json={"batch_id": batch["id"], "stage": "FINAL_VISUAL", "sampling_plan": "NORMAL"},
    ).json()
    item = client.post(
        f"/api/v1/inspections/{insp['id']}/items",
        headers=inspector_headers,
        json={"items": [{"item_identifier": f"ITEM-MULTI-{uuid.uuid4().hex[:4]}", "cavity_number": 1}]},
    ).json()[0]

    # Model Version
    ver = db_session.query(ModelVersion).filter(ModelVersion.version_name == "v1.0.0-resnet18").first()
    if not ver:
        ver = ModelVersion(
            id="mv-resnet18-v1",
            version_name="v1.0.0-resnet18",
            model_architecture="ResNet-18",
            weights_path="ml/artifacts/model_best.pt",
            training_dataset_info={"source": "test_dataset"},
            metrics={"accuracy": 1.0},
            is_active=True,
        )
        db_session.add(ver)
        db_session.commit()
        db_session.refresh(ver)

    # 2. Upload 3 distinct images for this single physical item
    images = []
    surfaces = ["TOP_FLANGE", "BORE_INTERIOR", "SIDE_WALL"]
    for idx, surface in enumerate(surfaces):
        content = JPEG_HEADER + f"payload_multi_{idx}_{uuid.uuid4().hex}".encode()
        expected_hash = hashlib.sha256(content).hexdigest()
        img_resp = client.post(
            "/api/v1/images/upload",
            headers=inspector_headers,
            data={
                "batch_id": batch["id"],
                "inspection_item_id": item["id"],
                "image_scope": "SURFACE",
                "surface_location": surface,
            },
            files={"file": (f"{surface.lower()}.jpg", content, "image/jpeg")},
        ).json()
        assert img_resp["sha256_hash"] == expected_hash
        images.append((img_resp, expected_hash, surface))

    # 3. Create ModelRun for image 0 and image 1
    run0 = ModelRun(
        logical_run_id=str(uuid.uuid4()),
        image_id=images[0][0]["id"],
        model_version_id=ver.id,
        attempt_number=1,
        status="SUCCEEDED",
        routing_outcome="LIKELY_OK",
        predicted_label="GOOD",
        score=0.012,
        score_type="UNRESTRICTED_LOGIT_SIGMOID_FRACTION",
    )
    run1 = ModelRun(
        logical_run_id=str(uuid.uuid4()),
        image_id=images[1][0]["id"],
        model_version_id=ver.id,
        attempt_number=1,
        status="SUCCEEDED",
        routing_outcome="LIKELY_DEFECTIVE",
        predicted_label="DEFECTIVE",
        score=0.985,
        score_type="UNRESTRICTED_LOGIT_SIGMOID_FRACTION",
    )
    db_session.add_all([run0, run1])
    db_session.commit()

    # 4. Record Human Review on the item
    review_res = client.post(
        "/api/v1/reviews",
        headers=inspector_headers,
        json={
            "inspection_item_id": item["id"],
            "decision": "CONFIRMED_DEFECTIVE",
            "notes": "Defect confirmed on bore surface image",
            "defect": {
                "category": "PINHOLE",
                "severity": "MAJOR",
                "surface_location": "BORE_INTERIOR",
                "description": "Cluster of pinholes in bore",
            },
        },
    )
    assert review_res.status_code == status.HTTP_201_CREATED
    rev_data = review_res.json()
    review_id = rev_data["id"]

    # Verify Snapshot captures all 3 active images
    snapshot = rev_data["ai_snapshot"]
    assert snapshot is not None
    assert snapshot["total_images"] == 3
    assert len(snapshot["evidence_images"]) == 3
    assert len(snapshot["images"]) == 3

    # Verify hashes and metadata match exactly
    recorded_ids = {entry["image_id"]: entry for entry in snapshot["evidence_images"]}
    for img_meta, exp_hash, surf in images:
        assert img_meta["id"] in recorded_ids
        entry = recorded_ids[img_meta["id"]]
        assert entry["sha256_hash"] == exp_hash
        assert entry["surface_location"] == surf
        assert entry["image_scope"] == "SURFACE"
        if img_meta["id"] == images[0][0]["id"]:
            assert entry["routing_outcome"] == "LIKELY_OK"
            assert entry["predicted_label"] == "GOOD"
        elif img_meta["id"] == images[1][0]["id"]:
            assert entry["routing_outcome"] == "LIKELY_DEFECTIVE"
            assert entry["predicted_label"] == "DEFECTIVE"
        elif img_meta["id"] == images[2][0]["id"]:
            assert entry["model_run_id"] is None

    # Preferred defective model run was selected as representative
    assert snapshot["model_run_id"] == run1.id
    assert snapshot["routing_outcome"] == "LIKELY_DEFECTIVE"

    # 5. Immutability Verification:
    # A) Upload a 4th image to the item AFTER the review
    content_post = JPEG_HEADER + b"payload_post_review_" + uuid.uuid4().hex.encode()
    img_post = client.post(
        "/api/v1/images/upload",
        headers=inspector_headers,
        data={
            "batch_id": batch["id"],
            "inspection_item_id": item["id"],
            "image_scope": "SURFACE",
            "surface_location": "EXTERNAL_BOSS",
        },
        files={"file": ("boss.jpg", content_post, "image/jpeg")},
    ).json()

    # B) Execute a new model run attempt on image 0
    run0_rerun = ModelRun(
        logical_run_id=str(uuid.uuid4()),
        image_id=images[0][0]["id"],
        model_version_id=ver.id,
        attempt_number=1,
        status="SUCCEEDED",
        routing_outcome="NEEDS_REVIEW",
        predicted_label="DEFECTIVE",
        score=0.888,
        score_type="UNRESTRICTED_LOGIT_SIGMOID_FRACTION",
    )
    db_session.add(run0_rerun)
    db_session.commit()

    # C) Retrieve review and assert snapshot is completely unchanged
    rev_get = client.get(f"/api/v1/reviews/{review_id}", headers=inspector_headers)
    assert rev_get.status_code == status.HTTP_200_OK
    persisted_snapshot = rev_get.json()["ai_snapshot"]

    assert persisted_snapshot["total_images"] == 3
    assert len(persisted_snapshot["evidence_images"]) == 3
    persisted_ids = [e["image_id"] for e in persisted_snapshot["evidence_images"]]
    assert img_post["id"] not in persisted_ids
    entry0 = [e for e in persisted_snapshot["evidence_images"] if e["image_id"] == images[0][0]["id"]][0]
    assert entry0["model_run_id"] == run0.id
    assert entry0["routing_outcome"] == "LIKELY_OK"
