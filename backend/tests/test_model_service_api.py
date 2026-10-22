import io
import uuid
from datetime import date, datetime, timezone
import pytest
from fastapi import status

from backend.app.models.entities import ModelVersion, ModelRun, WorkerHeartbeat

JPEG_HEADER = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"\x00" * 50


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
def uploaded_test_image(client, inspector_headers, supervisor_headers, qm_headers, temp_storage):
    # Create product & batch
    p_res = client.post(
        "/api/v1/products",
        headers=qm_headers,
        json={"sku": f"PROD-{uuid.uuid4().hex[:6]}", "name": "Impeller", "material": "Stainless"},
    )
    prod_id = p_res.json()["id"]

    b_res = client.post(
        "/api/v1/batches",
        headers=supervisor_headers,
        json={
            "batch_number": f"BATCH-{uuid.uuid4().hex[:6]}",
            "product_id": prod_id,
            "manufacture_date": str(date.today()),
            "declared_quantity": 25,
        },
    )
    batch_id = b_res.json()["id"]

    # Create inspection & item
    insp_res = client.post(
        "/api/v1/inspections",
        headers=inspector_headers,
        json={"batch_id": batch_id, "stage": "STAGING", "sampling_plan": "NORMAL"},
    )
    insp_id = insp_res.json()["id"]

    item_res = client.post(
        f"/api/v1/inspections/{insp_id}/items",
        headers=inspector_headers,
        json={"items": [{"item_identifier": f"ITEM-{uuid.uuid4().hex[:4]}", "cavity_number": 1}]},
    )
    item_id = item_res.json()[0]["id"]

    # Upload image
    file_bytes = JPEG_HEADER + b"test image payload content"
    img_res = client.post(
        "/api/v1/images/upload",
        headers=inspector_headers,
        data={
            "batch_id": batch_id,
            "inspection_item_id": item_id,
            "image_scope": "ITEM",
        },
        files={"file": ("test.jpg", io.BytesIO(file_bytes), "image/jpeg")},
    )
    assert img_res.status_code == status.HTTP_201_CREATED
    return img_res.json()


def test_enqueue_model_run_lifecycle_and_idempotency(client, inspector_headers, active_model_version, uploaded_test_image):
    image_id = uploaded_test_image["id"]

    # 1. Unauthenticated request rejected
    res_unauth = client.post(f"/api/v1/images/{image_id}/infer")
    assert res_unauth.status_code == status.HTTP_401_UNAUTHORIZED

    # 2. Enqueue inference with Idempotency-Key
    idem_key = str(uuid.uuid4())
    res_enq = client.post(
        f"/api/v1/images/{image_id}/infer",
        headers={**inspector_headers, "Idempotency-Key": idem_key},
    )
    assert res_enq.status_code == status.HTTP_202_ACCEPTED
    data = res_enq.json()
    run_id = data["model_run_id"]
    logical_id = data["logical_run_id"]
    assert data["status"] == "QUEUED"
    assert data["attempt_number"] == 1

    # 3. Repeated request with same Idempotency-Key returns cached response
    res_cached = client.post(
        f"/api/v1/images/{image_id}/infer",
        headers={**inspector_headers, "Idempotency-Key": idem_key},
    )
    assert res_cached.status_code in (status.HTTP_200_OK, status.HTTP_202_ACCEPTED)
    assert res_cached.json()["model_run_id"] == run_id

    # 4. Repeated request without idempotency key gracefully returns existing active run
    res_dup = client.post(
        f"/api/v1/images/{image_id}/infer",
        headers=inspector_headers,
    )
    assert res_dup.status_code in (status.HTTP_200_OK, status.HTTP_202_ACCEPTED)
    assert res_dup.json()["model_run_id"] == run_id

    # 5. Retrieve model run by ID
    res_get = client.get(f"/api/v1/model-runs/{run_id}", headers=inspector_headers)
    assert res_get.status_code == status.HTTP_200_OK
    run_data = res_get.json()
    assert run_data["id"] == run_id
    assert run_data["logical_run_id"] == logical_id
    assert run_data["status"] == "QUEUED"

    # 6. List model runs with filters
    res_list = client.get(f"/api/v1/model-runs?image_id={image_id}", headers=inspector_headers)
    assert res_list.status_code == status.HTTP_200_OK
    assert res_list.json()["total"] >= 1
    assert any(r["id"] == run_id for r in res_list.json()["items"])


def test_model_run_retry_policy_and_limits(client, inspector_headers, active_model_version, uploaded_test_image, db_session):
    image_id = uploaded_test_image["id"]

    # 1. Enqueue run
    res = client.post(f"/api/v1/images/{image_id}/infer", headers=inspector_headers)
    run_id = res.json()["model_run_id"]

    # 2. Cannot retry a QUEUED or PROCESSING run
    res_retry_early = client.post(f"/api/v1/model-runs/{run_id}/retry", headers=inspector_headers)
    assert res_retry_early.status_code == status.HTTP_400_BAD_REQUEST
    assert res_retry_early.json()["error"]["code"] == "RUN_NOT_RETRYABLE"

    # 3. Mark attempt 1 as FAILED in database
    run_obj = db_session.get(ModelRun, run_id)
    run_obj.status = "FAILED"
    run_obj.error_code = "SIMULATED_TRANSIENT_FAILURE"
    db_session.commit()

    # 4. Attempt 2 (First Retry) succeeds
    res_r1 = client.post(f"/api/v1/model-runs/{run_id}/retry", headers=inspector_headers)
    assert res_r1.status_code == status.HTTP_201_CREATED
    r1_data = res_r1.json()
    assert r1_data["attempt_number"] == 2
    assert r1_data["parent_run_id"] == run_id
    assert r1_data["logical_run_id"] == run_obj.logical_run_id
    run2_id = r1_data["id"]

    # Mark attempt 2 as FAILED
    run2_obj = db_session.get(ModelRun, run2_id)
    run2_obj.status = "FAILED"
    db_session.commit()

    # 5. Attempt 3 (Second & Final Retry) succeeds
    res_r2 = client.post(f"/api/v1/model-runs/{run2_id}/retry", headers=inspector_headers)
    assert res_r2.status_code == status.HTTP_201_CREATED
    r2_data = res_r2.json()
    assert r2_data["attempt_number"] == 3
    run3_id = r2_data["id"]

    # Mark attempt 3 as FAILED
    run3_obj = db_session.get(ModelRun, run3_id)
    run3_obj.status = "FAILED"
    db_session.commit()

    # 6. Attempt 4 must be REJECTED (max 3 total attempts budget exhausted)
    res_r3 = client.post(f"/api/v1/model-runs/{run3_id}/retry", headers=inspector_headers)
    assert res_r3.status_code == status.HTTP_409_CONFLICT
    assert res_r3.json()["error"]["code"] == "MAX_RETRIES_EXCEEDED"

    # Verify history preservation: all 3 attempts remain in database
    runs = db_session.query(ModelRun).filter(ModelRun.logical_run_id == run_obj.logical_run_id).all()
    assert len(runs) == 3
    assert {r.attempt_number for r in runs} == {1, 2, 3}


def test_worker_status_endpoint_and_role_permissions(client, inspector_headers, supervisor_headers, qm_headers, db_session):
    # 1. Inspector is FORBIDDEN from viewing internal worker operational status
    res_insp = client.get("/api/v1/workers/status", headers=inspector_headers)
    assert res_insp.status_code == status.HTTP_403_FORBIDDEN

    # 2. Register mock worker heartbeat
    now = datetime.now(timezone.utc)
    hb = WorkerHeartbeat(
        worker_id="test-worker-01",
        status="READY",
        started_at=now,
        last_heartbeat_at=now,
        model_ready=True,
    )
    db_session.merge(hb)
    db_session.commit()

    # 3. Supervisor is permitted
    res_sup = client.get("/api/v1/workers/status", headers=supervisor_headers)
    assert res_sup.status_code == status.HTTP_200_OK
    data_sup = res_sup.json()
    assert "workers" in data_sup
    assert "queue_summary" in data_sup
    assert any(w["worker_id"] == "test-worker-01" for w in data_sup["workers"])

    # 4. Quality Manager is permitted
    res_qm = client.get("/api/v1/workers/status", headers=qm_headers)
    assert res_qm.status_code == status.HTTP_200_OK
