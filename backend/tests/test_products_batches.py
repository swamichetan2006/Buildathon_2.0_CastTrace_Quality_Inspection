import uuid
from datetime import date
import pytest
from fastapi import status


def test_product_crud_and_permissions(client, qm_headers, inspector_headers):
    unique_sku = f"TEST-SKU-{uuid.uuid4().hex[:6]}"
    # 1. Inspector forbidden from creating products
    resp_forbidden = client.post(
        "/api/v1/products",
        headers=inspector_headers,
        json={"sku": unique_sku, "name": "Impeller 200mm", "material": "CF8M SS"},
    )
    assert resp_forbidden.status_code == status.HTTP_403_FORBIDDEN
    assert resp_forbidden.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # 2. Quality Manager creates product
    resp_create = client.post(
        "/api/v1/products",
        headers=qm_headers,
        json={
            "sku": unique_sku,
            "name": "Closed Vane Impeller 210mm",
            "material": "CF8M Stainless Steel",
            "drawing_number": "DWG-210-REV1",
            "nominal_weight_kg": 4.85,
            "specifications": {"diameter_mm": 210},
        },
    )
    assert resp_create.status_code == status.HTTP_201_CREATED
    product_data = resp_create.json()
    product_id = product_data["id"]
    assert product_data["sku"] == unique_sku
    assert product_data["is_archived"] is False

    # 3. Duplicate SKU fails with 409
    resp_dup = client.post(
        "/api/v1/products",
        headers=qm_headers,
        json={"sku": unique_sku, "name": "Duplicate", "material": "CF8M SS"},
    )
    assert resp_dup.status_code == status.HTTP_409_CONFLICT
    assert resp_dup.json()["error"]["code"] == "SKU_ALREADY_EXISTS"

    # 4. Get product detail
    resp_get = client.get(f"/api/v1/products/{product_id}", headers=inspector_headers)
    assert resp_get.status_code == status.HTTP_200_OK
    assert resp_get.json()["id"] == product_id

    # 5. Update product
    resp_patch = client.post(
        f"/api/v1/products/{product_id}",
        headers=qm_headers,
    ) # check patch method
    resp_patch = client.patch(
        f"/api/v1/products/{product_id}",
        headers=qm_headers,
        json={"name": "Updated Closed Vane Impeller 210mm"},
    )
    assert resp_patch.status_code == status.HTTP_200_OK
    assert resp_patch.json()["name"] == "Updated Closed Vane Impeller 210mm"

    # 6. Soft archive product
    resp_del = client.delete(f"/api/v1/products/{product_id}", headers=qm_headers)
    assert resp_del.status_code == status.HTTP_200_OK
    assert resp_del.json()["is_archived"] is True


def test_batch_lifecycle_and_hold(client, qm_headers, supervisor_headers, inspector_headers):
    # Setup active product
    sku = f"BATCH-PROD-{uuid.uuid4().hex[:6]}"
    p_res = client.post(
        "/api/v1/products",
        headers=qm_headers,
        json={"sku": sku, "name": "Pump Body", "material": "Cast Iron"},
    )
    prod_id = p_res.json()["id"]

    batch_num = f"LOT-{uuid.uuid4().hex[:6]}"

    # Inspector cannot create batch
    r_insp = client.post(
        "/api/v1/batches",
        headers=inspector_headers,
        json={
            "batch_number": batch_num,
            "product_id": prod_id,
            "manufacture_date": str(date.today()),
            "declared_quantity": 50,
        },
    )
    assert r_insp.status_code == status.HTTP_403_FORBIDDEN

    # Supervisor creates batch
    idemp_key = f"key-{uuid.uuid4()}"
    r_create = client.post(
        "/api/v1/batches",
        headers={**supervisor_headers, "Idempotency-Key": idemp_key},
        json={
            "batch_number": batch_num,
            "product_id": prod_id,
            "manufacture_date": str(date.today()),
            "declared_quantity": 50,
            "notes": "Shift A morning pour",
        },
    )
    assert r_create.status_code == status.HTTP_201_CREATED
    batch_data = r_create.json()
    batch_id = batch_data["id"]
    assert batch_data["status"] == "IN_PRODUCTION"

    # Duplicate submission with same Idempotency-Key returns cached response
    r_cached = client.post(
        "/api/v1/batches",
        headers={**supervisor_headers, "Idempotency-Key": idemp_key},
        json={
            "batch_number": batch_num,
            "product_id": prod_id,
            "manufacture_date": str(date.today()),
            "declared_quantity": 50,
        },
    )
    assert r_cached.status_code == status.HTTP_201_CREATED
    assert r_cached.json()["id"] == batch_id

    # 1. Operational Containment Hold: Unauthenticated blocked with 401
    r_hold_unauth = client.post(
        f"/api/v1/batches/{batch_id}/hold",
        json={"reason": "Unauthenticated attempt"},
    )
    assert r_hold_unauth.status_code == status.HTTP_401_UNAUTHORIZED

    # 2. Operational Containment Hold: Shop floor roles (Inspector, Supervisor, QM) are permitted
    # Inspector triggers operational containment hold
    r_hold_insp = client.post(
        f"/api/v1/batches/{batch_id}/hold",
        headers=inspector_headers,
        json={"reason": "Suspected ladle temperature deviation noticed by inspector"},
    )
    assert r_hold_insp.status_code == status.HTTP_200_OK
    assert r_hold_insp.json()["status"] == "ON_HOLD"

    # Supervisor triggers operational containment hold
    r_hold_sup = client.post(
        f"/api/v1/batches/{batch_id}/hold",
        headers=supervisor_headers,
        json={"reason": "Shift handover quarantine hold"},
    )
    assert r_hold_sup.status_code == status.HTTP_200_OK
    assert r_hold_sup.json()["status"] == "ON_HOLD"

    # Quality Manager triggers operational containment hold
    r_hold_qm = client.post(
        f"/api/v1/batches/{batch_id}/hold",
        headers=qm_headers,
        json={"reason": "Quality audit hold"},
    )
    assert r_hold_qm.status_code == status.HTTP_200_OK
    assert r_hold_qm.json()["status"] == "ON_HOLD"

    # 3. Official Batch Decisions: Unauthenticated blocked with 401
    r_dec_unauth = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        json={"decision": "RELEASE", "reason": "No auth"},
    )
    assert r_dec_unauth.status_code == status.HTTP_401_UNAUTHORIZED

    # 4. Official Batch Decisions: Inspector & Supervisor strictly blocked with 403 Forbidden
    # Inspector attempting official RELEASE
    r_dec_insp_rel = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=inspector_headers,
        json={"decision": "RELEASE", "reason": "Inspector trying to release batch"},
    )
    assert r_dec_insp_rel.status_code == status.HTTP_403_FORBIDDEN
    assert r_dec_insp_rel.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # Inspector attempting official HOLD decision
    r_dec_insp_hold = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=inspector_headers,
        json={"decision": "HOLD", "reason": "Inspector trying official hold"},
    )
    assert r_dec_insp_hold.status_code == status.HTTP_403_FORBIDDEN

    # Supervisor attempting official RELEASE
    r_dec_sup_rel = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=supervisor_headers,
        json={"decision": "RELEASE", "reason": "Supervisor trying to release batch"},
    )
    assert r_dec_sup_rel.status_code == status.HTTP_403_FORBIDDEN
    assert r_dec_sup_rel.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # Supervisor attempting official SCRAP
    r_dec_sup_scrap = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=supervisor_headers,
        json={"decision": "REJECT_SCRAP", "reason": "Supervisor trying official scrap"},
    )
    assert r_dec_sup_scrap.status_code == status.HTTP_403_FORBIDDEN

    # 5. Official Batch Decision: Quality Manager authorized to execute official RELEASE
    r_release_qm = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=qm_headers,
        json={"decision": "RELEASE", "reason": "100% inspection completed and zero defects confirmed."},
    )
    assert r_release_qm.status_code == status.HTTP_201_CREATED
    dec_data = r_release_qm.json()
    assert dec_data["decision"] == "RELEASE"
    assert dec_data["batch_id"] == batch_id

    # Verify batch status transitioned to RELEASED
    r_batch_after = client.get(f"/api/v1/batches/{batch_id}", headers=qm_headers)
    assert r_batch_after.json()["status"] == "RELEASED"



def test_batch_creation_on_archived_product_fails(client, qm_headers, supervisor_headers):
    sku = f"ARCH-PROD-{uuid.uuid4().hex[:6]}"
    p_res = client.post(
        "/api/v1/products",
        headers=qm_headers,
        json={"sku": sku, "name": "Old Impeller", "material": "Bronze"},
    )
    prod_id = p_res.json()["id"]

    # Archive product
    client.delete(f"/api/v1/products/{prod_id}", headers=qm_headers)

    # Attempt to create batch for archived product
    r_batch = client.post(
        "/api/v1/batches",
        headers=supervisor_headers,
        json={
            "batch_number": f"FAIL-{uuid.uuid4().hex[:4]}",
            "product_id": prod_id,
            "manufacture_date": str(date.today()),
            "declared_quantity": 25,
        },
    )
    assert r_batch.status_code == status.HTTP_400_BAD_REQUEST
    assert r_batch.json()["error"]["code"] == "PRODUCT_ARCHIVED"


def test_batch_official_decisions_hold_and_concessions(client, qm_headers, supervisor_headers, seeded_users, db_session):
    from backend.app.models.entities import Defect, Inspection, InspectionItem

    # Create product & batch
    sku = f"DEC-PROD-{uuid.uuid4().hex[:6]}"
    p_res = client.post(
        "/api/v1/products",
        headers=qm_headers,
        json={"sku": sku, "name": "Precision Impeller", "material": "CF8M SS"},
    )
    prod_id = p_res.json()["id"]

    batch_num = f"LOT-DEC-{uuid.uuid4().hex[:6]}"
    r_batch = client.post(
        "/api/v1/batches",
        headers=supervisor_headers,
        json={
            "batch_number": batch_num,
            "product_id": prod_id,
            "manufacture_date": str(date.today()),
            "declared_quantity": 40,
        },
    )
    assert r_batch.status_code == status.HTTP_201_CREATED
    batch_id = r_batch.json()["id"]

    # 1. Quality Manager official HOLD decision via POST /batches/{id}/decisions
    r_hold_dec = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=qm_headers,
        json={"decision": "HOLD", "reason": "Official quality containment hold by QM"},
    )
    assert r_hold_dec.status_code == status.HTTP_201_CREATED
    assert r_hold_dec.json()["decision"] == "HOLD"
    r_b = client.get(f"/api/v1/batches/{batch_id}", headers=qm_headers)
    assert r_b.json()["status"] == "ON_HOLD"

    # 2. Add an inspection item with an OPEN defect to this batch in DB
    insp = Inspection(
        batch_id=batch_id,
        inspection_number=f"INSP-{uuid.uuid4().hex[:6]}",
        inspector_id=seeded_users["INSPECTOR"].id,
        stage="FINAL_VISUAL",
        sampling_plan="AQL_LEVEL_II",
        status="IN_PROGRESS",
    )
    db_session.add(insp)
    db_session.flush()

    item = InspectionItem(
        inspection_id=insp.id,
        item_identifier=f"SN-{uuid.uuid4().hex[:6]}",
        status="DEFECTIVE",
    )
    db_session.add(item)
    db_session.flush()

    from backend.app.models.entities import Review

    review = Review(
        inspection_id=insp.id,
        inspection_item_id=item.id,
        reviewer_id=seeded_users["INSPECTOR"].id,
        decision="CONFIRMED_DEFECTIVE",
    )
    db_session.add(review)
    db_session.flush()

    defect = Defect(
        defect_number=f"DEF-{uuid.uuid4().hex[:6]}",
        inspection_item_id=item.id,
        review_id=review.id,
        category="PINHOLE",
        severity="MAJOR",
        status="OPEN",
        description="Cluster of pinholes near impeller blade root",
    )
    db_session.add(defect)
    db_session.commit()

    # 3. Quality Manager attempts standard RELEASE with open defect -> 422 OPEN_DEFECTS_REQUIRE_CONCESSION
    r_fail_rel = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=qm_headers,
        json={
            "decision": "RELEASE",
            "reason": "Attempting standard release with active open defect",
            "is_concession": False,
        },
    )
    assert r_fail_rel.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert r_fail_rel.json()["error"]["code"] == "OPEN_DEFECTS_REQUIRE_CONCESSION"

    # 4. Quality Manager grants authorized Concession Release with documented justification -> 201 Created
    r_conc_rel = client.post(
        f"/api/v1/batches/{batch_id}/decisions",
        headers=qm_headers,
        json={
            "decision": "RELEASE",
            "reason": "Customer agreed to allowable cosmetic porosity concession",
            "is_concession": True,
            "concession_justification": "Permit #ENG-2026-DEV-009 signed by Lead Metallurgist",
        },
    )
    assert r_conc_rel.status_code == status.HTTP_201_CREATED
    assert r_conc_rel.json()["decision"] == "RELEASE"

    # Verify batch status is now RELEASED
    r_b_final = client.get(f"/api/v1/batches/{batch_id}", headers=qm_headers)
    assert r_b_final.json()["status"] == "RELEASED"

