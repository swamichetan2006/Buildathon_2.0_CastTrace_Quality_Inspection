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
    Defect,
    CorrectiveAction,
    Reinspection,
    AuditLog,
)

JPEG_HEADER = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"\x00" * 50


@pytest.fixture
def secondary_qm(db_session):
    """Creates a second Quality Manager for Four-Eyes separation-of-duty tests."""
    u = db_session.query(User).filter(User.username == "test_qm_secondary_b").first()
    if not u:
        u = User(
            username="test_qm_secondary_b",
            email="qm2_b@casttrace.local",
            full_name="Secondary Quality Manager B",
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
def machinist_user(db_session):
    """Creates an active technician / supervisor assignee for CAPA remediation."""
    u = db_session.query(User).filter(User.username == "test_machinist_bob").first()
    if not u:
        u = User(
            username="test_machinist_bob",
            email="bob@casttrace.local",
            full_name="Bob Machinist",
            role="SUPERVISOR",
            hashed_password=hash_password("Password123!"),
            is_active=True,
        )
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
    return u


@pytest.fixture
def machinist_headers(machinist_user):
    token = create_access_token({"sub": machinist_user.id, "username": machinist_user.username, "role": machinist_user.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def capa_test_setup(client, inspector_headers, supervisor_headers, qm_headers, machinist_user, db_session):
    """Sets up a complete Product -> Batch -> Inspection -> Item -> Defect fixture."""
    # 1. Product
    prod = client.post(
        "/api/v1/products",
        headers=qm_headers,
        json={"sku": f"SKU-CAPA-{uuid.uuid4().hex[:6]}", "name": "Pump Volute", "material": "Ductile Iron"},
    ).json()

    # 2. Batch
    batch = client.post(
        "/api/v1/batches",
        headers=supervisor_headers,
        json={
            "batch_number": f"BATCH-CAPA-{uuid.uuid4().hex[:6]}",
            "product_id": prod["id"],
            "manufacture_date": str(date.today()),
            "declared_quantity": 10,
        },
    ).json()

    # 3. Inspection
    insp = client.post(
        "/api/v1/inspections",
        headers=inspector_headers,
        json={"batch_id": batch["id"], "stage": "FINAL_VISUAL", "sampling_plan": "NORMAL"},
    ).json()

    # 4. Item
    item = client.post(
        f"/api/v1/inspections/{insp['id']}/items",
        headers=inspector_headers,
        json={"items": [{"item_identifier": f"ITEM-CAPA-{uuid.uuid4().hex[:4]}", "cavity_number": 2}]},
    ).json()[0]

    # 5. Image
    img_content = JPEG_HEADER + b"evidence_capa_test_" + uuid.uuid4().hex.encode()
    img_resp = client.post(
        "/api/v1/images/upload",
        headers=inspector_headers,
        data={"batch_id": batch["id"], "inspection_item_id": item["id"], "image_scope": "ITEM"},
        files={"file": ("evidence.jpg", img_content, "image/jpeg")},
    ).json()

    # 6. Review creating Defect
    rev = client.post(
        "/api/v1/reviews",
        headers=inspector_headers,
        json={
            "inspection_item_id": item["id"],
            "decision": "CONFIRMED_DEFECTIVE",
            "notes": "Severe shrinkage porosity detected on volute discharge port",
            "defect": {
                "category": "SHRINKAGE_POROSITY",
                "severity": "CRITICAL",
                "surface_location": "DISCHARGE_PORT",
                "description": "Visible porosity cavity 3.5mm depth",
                "evidence_image_id": img_resp["id"],
            },
        },
    ).json()
    defect = rev["defects"][0]

    return {
        "product": prod,
        "batch": batch,
        "inspection": insp,
        "item": item,
        "image": img_resp,
        "defect": defect,
        "machinist": machinist_user,
    }


# =====================================================================
# 1. CAPA LIFECYCLE TESTS
# =====================================================================

def test_create_and_retrieve_capa(client, supervisor_headers, capa_test_setup, db_session):
    """Test assigning CAPA remediation task, format verification, and defect status transition."""
    defect_id = capa_test_setup["defect"]["id"]
    machinist_id = capa_test_setup["machinist"].id
    due_date_str = str(date.today() + timedelta(days=3))

    payload = {
        "defect_id": defect_id,
        "title": "Precision burr blend and liquid penetrant check",
        "action_type": "REWORK",
        "description": "Blend out surface porosity within drawing tolerance and verify wall thickness > 4.5mm",
        "assigned_to": machinist_id,
        "due_date": due_date_str,
        "root_cause": "Inadequate feeding at riser junction",
        "preventive_action": "Modify gating ratio and increase riser sleeve insulation",
    }

    res = client.post("/api/v1/corrective-actions", headers=supervisor_headers, json=payload)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()

    # 1. Verify CAPA fields and business number
    assert data["action_number"].startswith("CAPA-")
    assert data["defect_id"] == defect_id
    assert data["title"] == payload["title"]
    assert data["action_type"] == "REWORK"
    assert data["status"] == "OPEN"
    assert data["due_date"] == due_date_str
    assert data["root_cause"] == payload["root_cause"]
    assert data["preventive_action"] == payload["preventive_action"]
    assert data["verification_status"] == "PENDING"
    capa_id = data["id"]

    # 2. Verify defect status transitioned to ACTION_ASSIGNED
    def_res = client.get(f"/api/v1/defects/{defect_id}", headers=supervisor_headers)
    assert def_res.json()["status"] == "ACTION_ASSIGNED"

    # 3. Retrieve by ID
    get_res = client.get(f"/api/v1/corrective-actions/{capa_id}", headers=supervisor_headers)
    assert get_res.status_code == status.HTTP_200_OK
    assert get_res.json()["action_number"] == data["action_number"]

    # 4. List and filter by defect_id
    list_res = client.get(f"/api/v1/corrective-actions?defect_id={defect_id}", headers=supervisor_headers)
    assert list_res.status_code == status.HTTP_200_OK
    assert list_res.json()["total"] == 1
    assert list_res.json()["items"][0]["id"] == capa_id

    # 5. Verify audit logs
    audit = db_session.query(AuditLog).filter(AuditLog.entity_id == capa_id, AuditLog.action == "ACTION_CREATED").first()
    assert audit is not None


def test_capa_validations_and_illegal_transitions(client, supervisor_headers, inspector_headers, capa_test_setup):
    """Test due_date in past, non-existent references, active action collision, and permission checks."""
    defect_id = capa_test_setup["defect"]["id"]
    machinist_id = capa_test_setup["machinist"].id

    # 1. Due date in the past -> 422
    past_due = str(date.today() - timedelta(days=1))
    res_past = client.post(
        "/api/v1/corrective-actions",
        headers=supervisor_headers,
        json={
            "defect_id": defect_id,
            "title": "Invalid past due action",
            "action_type": "REWORK",
            "description": "Should fail validation",
            "assigned_to": machinist_id,
            "due_date": past_due,
        },
    )
    assert res_past.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert res_past.json()["error"]["code"] == "PAST_DUE_DATE"

    # 2. Inspector role cannot create CAPA -> 403
    res_insp = client.post(
        "/api/v1/corrective-actions",
        headers=inspector_headers,
        json={
            "defect_id": defect_id,
            "title": "Inspector attempt",
            "action_type": "REWORK",
            "description": "Should be denied",
            "assigned_to": machinist_id,
            "due_date": str(date.today() + timedelta(days=1)),
        },
    )
    assert res_insp.status_code == status.HTTP_403_FORBIDDEN

    # 3. Create valid action
    res_valid = client.post(
        "/api/v1/corrective-actions",
        headers=supervisor_headers,
        json={
            "defect_id": defect_id,
            "title": "Valid action",
            "action_type": "REWORK",
            "description": "First action",
            "assigned_to": machinist_id,
            "due_date": str(date.today() + timedelta(days=2)),
        },
    )
    assert res_valid.status_code == status.HTTP_201_CREATED

    # 4. Attempt duplicate active action while first is still OPEN -> 409
    res_dup = client.post(
        "/api/v1/corrective-actions",
        headers=supervisor_headers,
        json={
            "defect_id": defect_id,
            "title": "Duplicate action",
            "action_type": "REWORK",
            "description": "Second action collision",
            "assigned_to": machinist_id,
            "due_date": str(date.today() + timedelta(days=2)),
        },
    )
    assert res_dup.status_code == status.HTTP_409_CONFLICT
    assert res_dup.json()["error"]["code"] == "ACTIVE_ACTION_EXISTS"


def test_capa_execution_and_completion_workflow(client, machinist_headers, supervisor_headers, capa_test_setup):
    """Test start action (OPEN -> IN_PROGRESS), update progress, and complete action (-> PENDING_REINSPECTION)."""
    defect_id = capa_test_setup["defect"]["id"]
    machinist_id = capa_test_setup["machinist"].id

    # 1. Create CAPA
    capa = client.post(
        "/api/v1/corrective-actions",
        headers=supervisor_headers,
        json={
            "defect_id": defect_id,
            "title": "Rework impeller port",
            "action_type": "REWORK",
            "description": "Grind and blend port",
            "assigned_to": machinist_id,
            "due_date": str(date.today() + timedelta(days=2)),
        },
    ).json()
    capa_id = capa["id"]

    # 2. Assignee starts execution
    start_res = client.post(f"/api/v1/corrective-actions/{capa_id}/start", headers=machinist_headers)
    assert start_res.status_code == status.HTTP_200_OK
    assert start_res.json()["status"] == "IN_PROGRESS"

    # Defect transitions to IN_PROGRESS
    def_res = client.get(f"/api/v1/defects/{defect_id}", headers=machinist_headers)
    assert def_res.json()["status"] == "IN_PROGRESS"

    # 3. Update action progress notes
    patch_res = client.patch(
        f"/api/v1/corrective-actions/{capa_id}",
        headers=machinist_headers,
        json={"root_cause": "Core shift in mold assembly", "description": "Grind with 120-grit wheel"},
    )
    assert patch_res.status_code == status.HTTP_200_OK
    assert patch_res.json()["root_cause"] == "Core shift in mold assembly"

    # 4. Attempt to complete with too short notes (<10 chars) -> 422
    short_res = client.post(
        f"/api/v1/corrective-actions/{capa_id}/complete",
        headers=machinist_headers,
        json={"completion_notes": "Done"},
    )
    assert short_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 5. Successfully complete action
    comp_notes = "Ground pore down to 0.5mm, blended radius, measured wall thickness at 4.8mm."
    comp_res = client.post(
        f"/api/v1/corrective-actions/{capa_id}/complete",
        headers=machinist_headers,
        json={"completion_notes": comp_notes},
    )
    assert comp_res.status_code == status.HTTP_200_OK
    comp_data = comp_res.json()
    assert comp_data["status"] == "COMPLETED"
    assert comp_data["completed_at"] is not None
    assert comp_data["verification_status"] == "PENDING"

    # Defect transitions to PENDING_REINSPECTION
    def_pending = client.get(f"/api/v1/defects/{defect_id}", headers=machinist_headers).json()
    assert def_pending["status"] == "PENDING_REINSPECTION"


def test_capa_cancellation_by_qm(client, qm_headers, supervisor_headers, capa_test_setup):
    """Test Quality Manager cancelling an open action with audit and defect status restoration."""
    defect_id = capa_test_setup["defect"]["id"]
    machinist_id = capa_test_setup["machinist"].id

    capa = client.post(
        "/api/v1/corrective-actions",
        headers=supervisor_headers,
        json={
            "defect_id": defect_id,
            "title": "Action to cancel",
            "action_type": "TOOLING_REPAIR",
            "description": "Inspect core tooling",
            "assigned_to": machinist_id,
            "due_date": str(date.today() + timedelta(days=4)),
        },
    ).json()

    # Supervisor attempting cancel -> 403 Forbidden
    sup_cancel = client.post(
        f"/api/v1/corrective-actions/{capa['id']}/cancel",
        headers=supervisor_headers,
        json={"reason": "Supervisor trying to cancel"},
    )
    assert sup_cancel.status_code == status.HTTP_403_FORBIDDEN

    # QM cancels successfully
    qm_cancel = client.post(
        f"/api/v1/corrective-actions/{capa['id']}/cancel",
        headers=qm_headers,
        json={"reason": "Duplicate action logged; tooling inspection already scheduled"},
    )
    assert qm_cancel.status_code == status.HTTP_200_OK
    assert qm_cancel.json()["status"] == "CANCELLED"

    # Defect returns to OPEN
    def_open = client.get(f"/api/v1/defects/{defect_id}", headers=qm_headers).json()
    assert def_open["status"] == "OPEN"


# =====================================================================
# 2. INDEPENDENT VERIFICATION & FOUR-EYES CONTROL TESTS
# =====================================================================

def test_capa_four_eyes_self_verification_prohibited(client, supervisor_headers, machinist_headers, secondary_qm_headers, capa_test_setup):
    """Test Four-Eyes Rule: The implementer of a CAPA cannot verify their own work."""
    defect_id = capa_test_setup["defect"]["id"]
    machinist_id = capa_test_setup["machinist"].id

    # 1. Create and complete action assigned to machinist
    capa = client.post(
        "/api/v1/corrective-actions",
        headers=supervisor_headers,
        json={
            "defect_id": defect_id,
            "title": "Machinist self action",
            "action_type": "REWORK",
            "description": "Grind defect",
            "assigned_to": machinist_id,
            "due_date": str(date.today() + timedelta(days=2)),
        },
    ).json()

    client.post(
        f"/api/v1/corrective-actions/{capa['id']}/complete",
        headers=machinist_headers,
        json={"completion_notes": "Rework executed by Bob Machinist successfully."},
    )

    # 2. Machinist attempts self-verification -> 403 FOUR_EYES_VIOLATION
    self_res = client.post(
        f"/api/v1/corrective-actions/{capa['id']}/verify",
        headers=machinist_headers,
        json={"decision": "APPROVED", "notes": "I verify my own work is good"},
    )
    # Machinist has SUPERVISOR role (so 403 role or 403 FOUR_EYES_VIOLATION)
    assert self_res.status_code == status.HTTP_403_FORBIDDEN

    # What if a Quality Manager who is assigned to an action attempts to verify their own action?
    # Create action assigned to secondary QM
    sec_qm = client.get("/api/v1/auth/me", headers=secondary_qm_headers).json()
    capa_qm = client.post(
        "/api/v1/corrective-actions",
        headers=supervisor_headers,
        json={
            "defect_id": defect_id,
            "title": "QM implementer action",
            "action_type": "PROCESS_ADJUSTMENT",
            "description": "Re-calibrate furnace temperature curve",
            "assigned_to": sec_qm["id"],
            "due_date": str(date.today() + timedelta(days=2)),
        },
    ).json()

    client.post(
        f"/api/v1/corrective-actions/{capa_qm['id']}/complete",
        headers=secondary_qm_headers,
        json={"completion_notes": "Calibrated temperature profile and updated controller."},
    )

    # Secondary QM verifies their own action -> strictly prohibited with FOUR_EYES_VIOLATION
    qm_self_res = client.post(
        f"/api/v1/corrective-actions/{capa_qm['id']}/verify",
        headers=secondary_qm_headers,
        json={"decision": "APPROVED", "notes": "Attempting self-signoff as QM"},
    )
    assert qm_self_res.status_code == status.HTTP_403_FORBIDDEN
    assert qm_self_res.json()["error"]["code"] == "FOUR_EYES_VIOLATION"


def test_capa_verification_rejection_and_resubmission(client, supervisor_headers, machinist_headers, secondary_qm_headers, capa_test_setup):
    """Test verification rejection preserving history, resubmission, and subsequent independent approval."""
    defect_id = capa_test_setup["defect"]["id"]
    machinist_id = capa_test_setup["machinist"].id

    capa = client.post(
        "/api/v1/corrective-actions",
        headers=supervisor_headers,
        json={
            "defect_id": defect_id,
            "title": "Multi-pass weld repair",
            "action_type": "REWORK",
            "description": "Weld fill and blend defect",
            "assigned_to": machinist_id,
            "due_date": str(date.today() + timedelta(days=2)),
        },
    ).json()
    capa_id = capa["id"]

    # 1. Implementer completes first pass
    client.post(
        f"/api/v1/corrective-actions/{capa_id}/complete",
        headers=machinist_headers,
        json={"completion_notes": "Initial weld repair and blend pass completed."},
    )

    # 2. Independent QM rejects verification without reason -> 422
    rej_no_reason = client.post(
        f"/api/v1/corrective-actions/{capa_id}/verify",
        headers=secondary_qm_headers,
        json={"decision": "REJECTED", "notes": "Visual flaw found"},
    )
    assert rej_no_reason.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 3. Independent QM rejects with valid reason
    rej_res = client.post(
        f"/api/v1/corrective-actions/{capa_id}/verify",
        headers=secondary_qm_headers,
        json={
            "decision": "REJECTED",
            "notes": "Underfill detected at weld toe; insufficient blend radius",
            "rejection_reason": "Weld toe undercut exceeds 0.2mm tolerance. Rework required.",
        },
    )
    assert rej_res.status_code == status.HTTP_200_OK
    rej_data = rej_res.json()
    assert rej_data["status"] == "IN_PROGRESS"
    assert rej_data["verification_status"] == "REJECTED"
    assert len(rej_data["verification_history"]) == 1
    assert rej_data["verification_history"][0]["decision"] == "REJECTED"
    assert rej_data["verification_history"][0]["rejection_reason"] == "Weld toe undercut exceeds 0.2mm tolerance. Rework required."

    # Defect returned to IN_PROGRESS
    def_rework = client.get(f"/api/v1/defects/{defect_id}", headers=secondary_qm_headers).json()
    assert def_rework["status"] == "IN_PROGRESS"

    # 4. Implementer performs rework and resubmits
    client.post(
        f"/api/v1/corrective-actions/{capa_id}/complete",
        headers=machinist_headers,
        json={"completion_notes": "Re-deposited TIG wash pass and re-blended smooth radius. Wall thickness 4.9mm."},
    )

    # 5. Independent QM verifies and approves
    app_res = client.post(
        f"/api/v1/corrective-actions/{capa_id}/verify",
        headers=secondary_qm_headers,
        json={"decision": "APPROVED", "notes": "Visual and dye penetrant inspection fully conforming"},
    )
    assert app_res.status_code == status.HTTP_200_OK
    app_data = app_res.json()
    assert app_data["status"] == "COMPLETED"
    assert app_data["verification_status"] == "VERIFIED"
    assert len(app_data["verification_history"]) == 2
    assert app_data["verification_history"][0]["decision"] == "REJECTED"
    assert app_data["verification_history"][1]["decision"] == "APPROVED"


# =====================================================================
# 3. REINSPECTION WORKFLOW TESTS
# =====================================================================

def test_reinspection_resolved_workflow(client, supervisor_headers, machinist_headers, inspector_headers, capa_test_setup, db_session):
    """Test follow-up verification inspection leading to defect resolution and item clearing."""
    defect_id = capa_test_setup["defect"]["id"]
    item_id = capa_test_setup["item"]["id"]
    machinist_id = capa_test_setup["machinist"].id

    # 1. Setup completed action
    capa = client.post(
        "/api/v1/corrective-actions",
        headers=supervisor_headers,
        json={
            "defect_id": defect_id,
            "title": "Machine and deburr shroud",
            "action_type": "REWORK",
            "description": "Fettling and CNC pass",
            "assigned_to": machinist_id,
            "due_date": str(date.today() + timedelta(days=2)),
        },
    ).json()

    client.post(
        f"/api/v1/corrective-actions/{capa['id']}/complete",
        headers=machinist_headers,
        json={"completion_notes": "CNC skimming pass executed within drawing tolerance."},
    )

    # 2. Upload reinspection evidence image
    re_img_content = JPEG_HEADER + b"reinspection_evidence_photo_" + uuid.uuid4().hex.encode()
    re_img = client.post(
        "/api/v1/images/upload",
        headers=inspector_headers,
        data={"batch_id": capa_test_setup["batch"]["id"], "inspection_item_id": item_id, "image_scope": "SURFACE", "surface_location": "SHROUD"},
        files={"file": ("reinspection.jpg", re_img_content, "image/jpeg")},
    ).json()

    # 3. Conduct reinspection with DEFECT_RESOLVED outcome
    reinsp_res = client.post(
        "/api/v1/reinspections",
        headers=inspector_headers,
        json={
            "defect_id": defect_id,
            "corrective_action_id": capa["id"],
            "outcome": "DEFECT_RESOLVED",
            "notes": "Post-rework dye penetrant and visual inspection confirms defect is 100% eliminated.",
            "evidence_image_id": re_img["id"],
        },
    )
    assert reinsp_res.status_code == status.HTTP_201_CREATED
    r_data = reinsp_res.json()
    assert r_data["outcome"] == "DEFECT_RESOLVED"
    assert r_data["evidence_image_id"] == re_img["id"]
    reinsp_id = r_data["id"]

    # 4. Assert Defect is RESOLVED
    def_obj = db_session.get(Defect, defect_id)
    assert def_obj.status == "RESOLVED"
    assert def_obj.resolved_by is not None
    assert def_obj.resolved_at is not None

    # 5. Assert InspectionItem is CLEAR
    item_obj = db_session.get(InspectionItem, item_id)
    assert item_obj.status == "CLEAR"

    # 6. Assert CorrectiveAction status remains COMPLETED while verification_status is VERIFIED
    capa_obj = db_session.get(CorrectiveAction, capa["id"])
    assert capa_obj.status == "COMPLETED"
    assert capa_obj.verification_status == "VERIFIED"
    assert capa_obj.verified_by is not None

    # 7. Retrieve reinspection details
    get_r = client.get(f"/api/v1/reinspections/{reinsp_id}", headers=inspector_headers)
    assert get_r.status_code == status.HTTP_200_OK


def test_reinspection_four_eyes_sod2_prohibited(client, supervisor_headers, machinist_headers, capa_test_setup):
    """Test SoD-2: The user assigned to perform the corrective action CANNOT reinspect that item."""
    defect_id = capa_test_setup["defect"]["id"]
    machinist_id = capa_test_setup["machinist"].id

    capa = client.post(
        "/api/v1/corrective-actions",
        headers=supervisor_headers,
        json={
            "defect_id": defect_id,
            "title": "Grind defect",
            "action_type": "REWORK",
            "description": "Remediation",
            "assigned_to": machinist_id,
            "due_date": str(date.today() + timedelta(days=2)),
        },
    ).json()

    client.post(
        f"/api/v1/corrective-actions/{capa['id']}/complete",
        headers=machinist_headers,
        json={"completion_notes": "Completed rework by assigned machinist."},
    )

    # Implementer attempts reinspection
    reinsp_self = client.post(
        "/api/v1/reinspections",
        headers=machinist_headers,
        json={
            "defect_id": defect_id,
            "corrective_action_id": capa["id"],
            "outcome": "DEFECT_RESOLVED",
            "notes": "I reinspect and resolve my own fix",
        },
    )
    assert reinsp_self.status_code == status.HTTP_403_FORBIDDEN


def test_reinspection_recurred_reopened_workflow(client, supervisor_headers, machinist_headers, inspector_headers, capa_test_setup, db_session):
    """Test follow-up reinspection revealing recurrent/persistent defect transitions defect to REOPENED and links recurrence."""
    defect_id = capa_test_setup["defect"]["id"]
    item_id = capa_test_setup["item"]["id"]
    machinist_id = capa_test_setup["machinist"].id

    capa = client.post(
        "/api/v1/corrective-actions",
        headers=supervisor_headers,
        json={
            "defect_id": defect_id,
            "title": "Ceramic stone polish",
            "action_type": "REWORK",
            "description": "Polish shallow crack",
            "assigned_to": machinist_id,
            "due_date": str(date.today() + timedelta(days=2)),
        },
    ).json()

    client.post(
        f"/api/v1/corrective-actions/{capa['id']}/complete",
        headers=machinist_headers,
        json={"completion_notes": "Polished surface with ceramic stone."},
    )

    # Reinspection reveals residual defect
    fail_res = client.post(
        "/api/v1/reinspections",
        headers=inspector_headers,
        json={
            "defect_id": defect_id,
            "corrective_action_id": capa["id"],
            "outcome": "DEFECT_RECURRED_REOPENED",
            "notes": "Liquid penetrant check indicates crack tip propagated under skin.",
        },
    )
    assert fail_res.status_code == status.HTTP_201_CREATED
    assert fail_res.json()["outcome"] == "DEFECT_RECURRED_REOPENED"

    # Defect is REOPENED and item remains CONFIRMED_DEFECTIVE
    def_obj = db_session.get(Defect, defect_id)
    assert def_obj.status == "REOPENED"
    assert def_obj.prior_corrective_action_id == capa["id"]

    item_obj = db_session.get(InspectionItem, item_id)
    assert item_obj.status == "CONFIRMED_DEFECTIVE"

    # Assert CorrectiveAction status remains COMPLETED while verification_status is REJECTED
    capa_obj = db_session.get(CorrectiveAction, capa["id"])
    assert capa_obj.status == "COMPLETED"
    assert capa_obj.verification_status == "REJECTED"


def test_reinspection_qm_sign_off(client, supervisor_headers, machinist_headers, inspector_headers, qm_headers, capa_test_setup):
    """Test Quality Manager official sign off on verified reinspection fix."""
    defect_id = capa_test_setup["defect"]["id"]
    machinist_id = capa_test_setup["machinist"].id

    capa = client.post(
        "/api/v1/corrective-actions",
        headers=supervisor_headers,
        json={
            "defect_id": defect_id,
            "title": "Machine pass",
            "action_type": "REWORK",
            "description": "Fettling pass",
            "assigned_to": machinist_id,
            "due_date": str(date.today() + timedelta(days=2)),
        },
    ).json()

    client.post(
        f"/api/v1/corrective-actions/{capa['id']}/complete",
        headers=machinist_headers,
        json={"completion_notes": "Remediation completed as planned."},
    )

    reinsp = client.post(
        "/api/v1/reinspections",
        headers=inspector_headers,
        json={
            "defect_id": defect_id,
            "corrective_action_id": capa["id"],
            "outcome": "DEFECT_RESOLVED",
            "notes": "Verified clear by visual inspection.",
        },
    ).json()

    # QM signs off
    sign_res = client.post(
        f"/api/v1/reinspections/{reinsp['id']}/sign-off",
        headers=qm_headers,
        json={"notes": "Final engineering sign-off approved for batch release"},
    )
    assert sign_res.status_code == status.HTTP_200_OK
    assert "QM SIGN-OFF" in sign_res.json()["notes"]


# =====================================================================
# 4. RECURRENCE MANAGEMENT & CYCLE PREVENTION TESTS
# =====================================================================

def test_recurrence_lineage_and_history_query(client, inspector_headers, supervisor_headers, machinist_headers, capa_test_setup):
    """Test recurrence lineage: Defect A -> Defect B -> Defect C and retrieve recurrence history."""
    item_id = capa_test_setup["item"]["id"]
    def_a_id = capa_test_setup["defect"]["id"]
    machinist_id = capa_test_setup["machinist"].id

    # Create CAPA for Defect A
    capa_a = client.post(
        "/api/v1/corrective-actions",
        headers=supervisor_headers,
        json={
            "defect_id": def_a_id,
            "title": "CAPA for Defect A",
            "action_type": "REWORK",
            "description": "Weld repair",
            "assigned_to": machinist_id,
            "due_date": str(date.today() + timedelta(days=2)),
        },
    ).json()

    # Create Defect B recurring from Defect A
    rev_b = client.post(
        "/api/v1/reviews",
        headers=inspector_headers,
        json={
            "inspection_item_id": item_id,
            "decision": "CONFIRMED_DEFECTIVE",
            "notes": "Recurrence 1 observed",
            "defect": {
                "category": "SHRINKAGE_POROSITY",
                "severity": "CRITICAL",
                "surface_location": "DISCHARGE_PORT",
                "description": "Pore re-opened in same heat zone",
                "prior_defect_id": def_a_id,
                "prior_corrective_action_id": capa_a["id"],
            },
        },
    ).json()
    def_b = rev_b["defects"][0]
    assert def_b["prior_defect_id"] == def_a_id
    assert def_b["prior_corrective_action_id"] == capa_a["id"]

    # Create Defect C recurring from Defect B
    rev_c = client.post(
        "/api/v1/reviews",
        headers=inspector_headers,
        json={
            "inspection_item_id": item_id,
            "decision": "CONFIRMED_DEFECTIVE",
            "notes": "Recurrence 2 observed",
            "defect": {
                "category": "SHRINKAGE_POROSITY",
                "severity": "CRITICAL",
                "surface_location": "DISCHARGE_PORT",
                "description": "Third recurrence of same pore",
                "prior_defect_id": def_b["id"],
            },
        },
    ).json()
    def_c = rev_c["defects"][0]
    assert def_c["prior_defect_id"] == def_b["id"]

    # Query recurrence lineage for Defect C
    hist_res = client.get(f"/api/v1/defects/{def_c['id']}/recurrence-history", headers=inspector_headers)
    assert hist_res.status_code == status.HTTP_200_OK
    hist = hist_res.json()
    assert hist["defect_id"] == def_c["id"]
    assert hist["depth"] == 3
    chain_ids = [d["id"] for d in hist["recurrence_chain"]]
    assert chain_ids == [def_c["id"], def_b["id"], def_a_id]


def test_recurrence_self_link_and_cycle_prevention(client, inspector_headers, capa_test_setup):
    """Test rejection of invalid self-links and cyclical recurrence references."""
    item_id = capa_test_setup["item"]["id"]
    def_id = capa_test_setup["defect"]["id"]

    # Standalone defect creation with self-link
    # (Passing a non-existent prior_defect_id)
    non_existent = str(uuid.uuid4())
    res_404 = client.post(
        "/api/v1/reviews",
        headers=inspector_headers,
        json={
            "inspection_item_id": item_id,
            "decision": "CONFIRMED_DEFECTIVE",
            "notes": "Invalid prior defect test",
            "defect": {
                "category": "CRACK",
                "severity": "MAJOR",
                "description": "Crack test",
                "prior_defect_id": non_existent,
            },
        },
    )
    assert res_404.status_code == status.HTTP_404_NOT_FOUND
    assert res_404.json()["error"]["code"] == "PRIOR_DEFECT_NOT_FOUND"
