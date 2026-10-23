import uuid
from datetime import date, datetime, timezone, timedelta
import pytest
from fastapi import status

from backend.app.models.entities import Product, Batch, Inspection, InspectionItem, Defect, CorrectiveAction

JPEG_HEADER = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"\x00" * 50


def test_inspector_allowed_and_forbidden_actions(client, inspector_headers, qm_headers, supervisor_headers, db_session):
    # 1. Inspector CAN list products, batches, and inspections
    r_prods = client.get("/api/v1/products", headers=inspector_headers)
    assert r_prods.status_code == status.HTTP_200_OK

    r_batches = client.get("/api/v1/batches", headers=inspector_headers)
    assert r_batches.status_code == status.HTTP_200_OK

    r_insps = client.get("/api/v1/inspections", headers=inspector_headers)
    assert r_insps.status_code == status.HTTP_200_OK

    # Create a batch via Supervisor to test hold and forbidden actions
    p_sku = f"INSP-PROD-{uuid.uuid4().hex[:6]}"
    r_p = client.post(
        "/api/v1/products",
        headers=qm_headers,
        json={"sku": p_sku, "name": "Impeller for Inspector Test", "material": "CF8M"},
    )
    assert r_p.status_code == status.HTTP_201_CREATED
    product_id = r_p.json()["id"]

    b_num = f"INSP-BATCH-{uuid.uuid4().hex[:6]}"
    r_b = client.post(
        "/api/v1/batches",
        headers=supervisor_headers,
        json={
            "batch_number": b_num,
            "product_id": product_id,
            "manufacture_date": str(date.today()),
            "declared_quantity": 25,
        },
    )
    assert r_b.status_code == status.HTTP_201_CREATED
    batch_id = r_b.json()["id"]

    # 2. Inspector CAN place operational containment hold
    r_hold = client.post(
        f"/api/v1/batches/{batch_id}/hold",
        headers=inspector_headers,
        json={"reason": "Suspected porosity observed during initial visual staging"},
    )
    assert r_hold.status_code == status.HTTP_200_OK
    assert r_hold.json()["status"] == "ON_HOLD"

    # 3. Inspector FORBIDDEN: cannot create products
    r_create_prod = client.post(
        "/api/v1/products",
        headers=inspector_headers,
        json={"sku": f"DENIED-{uuid.uuid4().hex[:6]}", "name": "Denied Product", "material": "CF8M"},
    )
    assert r_create_prod.status_code == status.HTTP_403_FORBIDDEN
    assert r_create_prod.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # 4. Inspector FORBIDDEN: cannot authorize official batch decisions
    r_decision = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=inspector_headers,
        json={"decision": "RELEASE", "reason": "Inspector trying to release batch"},
    )
    assert r_decision.status_code == status.HTTP_403_FORBIDDEN
    assert r_decision.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # 5. Inspector FORBIDDEN: cannot create/assign CAPA
    r_capa = client.post(
        "/api/v1/corrective-actions",
        headers=inspector_headers,
        json={
            "defect_id": str(uuid.uuid4()),
            "title": "Unauthorized CAPA",
            "action_type": "REWORK",
            "description": "Inspector trying to assign CAPA",
            "assigned_to": str(uuid.uuid4()),
            "due_date": str(date.today() + timedelta(days=5)),
        },
    )
    assert r_capa.status_code == status.HTTP_403_FORBIDDEN


def test_supervisor_allowed_and_forbidden_actions(client, supervisor_headers, qm_headers, db_session):
    # Setup product
    p_sku = f"SUP-PROD-{uuid.uuid4().hex[:6]}"
    r_p = client.post(
        "/api/v1/products",
        headers=qm_headers,
        json={"sku": p_sku, "name": "Impeller for Supervisor Test", "material": "Bronze"},
    )
    assert r_p.status_code == status.HTTP_201_CREATED
    product_id = r_p.json()["id"]

    # 1. Supervisor CAN create production batch
    b_num = f"SUP-BATCH-{uuid.uuid4().hex[:6]}"
    r_b = client.post(
        "/api/v1/batches",
        headers=supervisor_headers,
        json={
            "batch_number": b_num,
            "product_id": product_id,
            "manufacture_date": str(date.today()),
            "declared_quantity": 40,
        },
    )
    assert r_b.status_code == status.HTTP_201_CREATED
    batch_id = r_b.json()["id"]

    # 2. Supervisor FORBIDDEN: cannot create products
    r_create_prod = client.post(
        "/api/v1/products",
        headers=supervisor_headers,
        json={"sku": f"DENIED-SUP-{uuid.uuid4().hex[:6]}", "name": "Supervisor Denied Product", "material": "Bronze"},
    )
    assert r_create_prod.status_code == status.HTTP_403_FORBIDDEN
    assert r_create_prod.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # 3. Supervisor FORBIDDEN: cannot authorize official batch decisions
    r_decision = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=supervisor_headers,
        json={"decision": "RELEASE", "reason": "Supervisor trying to release batch"},
    )
    assert r_decision.status_code == status.HTTP_403_FORBIDDEN

    # 4. Supervisor FORBIDDEN: cannot independently verify completed CAPAs (SoD rule)
    fake_action_id = str(uuid.uuid4())
    r_verify = client.post(
        f"/api/v1/corrective-actions/{fake_action_id}/verify",
        headers=supervisor_headers,
        json={"decision": "APPROVED", "notes": "Supervisor attempting verification"},
    )
    assert r_verify.status_code == status.HTTP_403_FORBIDDEN
    assert r_verify.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


def test_four_eyes_separation_of_duty_enforcement(client, qm_headers, supervisor_headers, inspector_headers, seeded_users, db_session):
    qm_user = seeded_users["QUALITY_MANAGER"]

    # 1. Create Product & Batch
    prod = client.post(
        "/api/v1/products",
        headers=qm_headers,
        json={"sku": f"SOD-SKU-{uuid.uuid4().hex[:6]}", "name": "SoD Impeller", "material": "CF8M"},
    ).json()

    batch = client.post(
        "/api/v1/batches",
        headers=supervisor_headers,
        json={
            "batch_number": f"SOD-BATCH-{uuid.uuid4().hex[:6]}",
            "product_id": prod["id"],
            "manufacture_date": str(date.today()),
            "declared_quantity": 10,
        },
    ).json()

    # 2. Create Inspection & Item
    insp = client.post(
        "/api/v1/inspections",
        headers=inspector_headers,
        json={"batch_id": batch["id"], "stage": "FINAL_VISUAL", "sampling_plan": "NORMAL"},
    ).json()

    item = client.post(
        f"/api/v1/inspections/{insp['id']}/items",
        headers=inspector_headers,
        json={"items": [{"item_identifier": f"ITEM-SOD-{uuid.uuid4().hex[:4]}", "cavity_number": 1}]},
    ).json()[0]

    # 3. Log Defect via Review
    rev = client.post(
        "/api/v1/reviews",
        headers=inspector_headers,
        json={
            "inspection_item_id": item["id"],
            "decision": "CONFIRMED_DEFECTIVE",
            "notes": "Surface porosity on suction eye",
            "defect": {
                "category": "SHRINKAGE_POROSITY",
                "severity": "MAJOR",
                "surface_location": "SUCTION_EYE",
                "description": "Porosity cluster observed",
            },
        },
    ).json()
    defect = rev["defects"][0]

    # 4. Assign CAPA with QM as the designated assignee
    r_capa = client.post(
        "/api/v1/corrective-actions",
        headers=qm_headers,
        json={
            "defect_id": defect["id"],
            "title": "Weld Repair of Suction Eye",
            "action_type": "REWORK",
            "description": "Perform TIG weld build-up and contour grind",
            "assigned_to": qm_user.id,
            "due_date": str(date.today() + timedelta(days=4)),
        },
    )
    assert r_capa.status_code == status.HTTP_201_CREATED
    action = r_capa.json()

    # 5. Mark action completed by QM
    r_comp = client.post(
        f"/api/v1/corrective-actions/{action['id']}/complete",
        headers=qm_headers,
        json={"completion_notes": "TIG weld deposit completed and dressed to smooth contour."},
    )
    assert r_comp.status_code == status.HTTP_200_OK

    # 6. Four-Eyes Enforcement: QM user (who is assigned_to) attempts to verify their own implementation
    r_self_verify = client.post(
        f"/api/v1/corrective-actions/{action['id']}/verify",
        headers=qm_headers,
        json={"decision": "APPROVED", "notes": "Attempting self-verification"},
    )
    assert r_self_verify.status_code == status.HTTP_403_FORBIDDEN
    assert r_self_verify.json()["error"]["code"] == "FOUR_EYES_VIOLATION"


def test_batch_release_gate_blocker_enforcement(client, qm_headers, supervisor_headers, inspector_headers, db_session):
    # Create product and batch
    prod = client.post(
        "/api/v1/products",
        headers=qm_headers,
        json={"sku": f"GATE-SKU-{uuid.uuid4().hex[:6]}", "name": "Gate Blocker Impeller", "material": "CF8M"},
    ).json()

    batch = client.post(
        "/api/v1/batches",
        headers=supervisor_headers,
        json={
            "batch_number": f"GATE-LOT-{uuid.uuid4().hex[:6]}",
            "product_id": prod["id"],
            "manufacture_date": str(date.today()),
            "declared_quantity": 20,
        },
    ).json()

    # Create empty inspection (0 items registered, DRAFT status)
    insp = client.post(
        "/api/v1/inspections",
        headers=inspector_headers,
        json={"batch_id": batch["id"], "stage": "FINAL_VISUAL", "sampling_plan": "NORMAL"},
    ).json()

    # Attempt to release batch with empty inspection (gate rules violated)
    r_release = client.post(
        f"/api/v1/batches/{batch['id']}/decisions",
        headers=qm_headers,
        json={"decision": "RELEASE", "reason": "Attempting release on batch with empty inspection"},
    )
    assert r_release.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    err = r_release.json()["error"]
    assert err["code"] == "RELEASE_BLOCKED"
    assert "release is blocked" in err["message"].lower()
    blockers = [b["code"] for b in err["details"]["blockers"]]
    assert "NO_INSPECTION_ITEMS_RECORDED" in blockers or "INSPECTION_NOT_COMPLETED" in blockers
