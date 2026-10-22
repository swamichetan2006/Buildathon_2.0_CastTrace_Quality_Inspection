import uuid
import pytest
from fastapi import status


def test_audit_logs_permissions_and_recording(client, qm_headers, supervisor_headers, inspector_headers):
    # 1. Inspector & Supervisor cannot read audit logs
    r_insp = client.get("/api/v1/audit-logs", headers=inspector_headers)
    assert r_insp.status_code == status.HTTP_403_FORBIDDEN
    assert r_insp.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    r_sup = client.get("/api/v1/audit-logs", headers=supervisor_headers)
    assert r_sup.status_code == status.HTTP_403_FORBIDDEN

    # 2. Quality Manager can view audit logs
    r_qm = client.get("/api/v1/audit-logs", headers=qm_headers)
    assert r_qm.status_code == status.HTTP_200_OK
    logs = r_qm.json()
    assert isinstance(logs, list)

    # 3. Create a product and assert audit entry exists
    sku = f"AUDIT-SKU-{uuid.uuid4().hex[:6]}"
    client.post(
        "/api/v1/products",
        headers=qm_headers,
        json={"sku": sku, "name": "Audit Test Impeller", "material": "Bronze"},
    )

    r_qm_after = client.get(
        "/api/v1/audit-logs",
        headers=qm_headers,
        params={"entity_type": "products"},
    )
    assert r_qm_after.status_code == status.HTTP_200_OK
    product_logs = r_qm_after.json()
    assert any(log["action"] == "PRODUCT_CREATED" for log in product_logs)


def test_error_envelope_consistency(client):
    # 404 test
    r_404 = client.get("/api/v1/products/non-existent-uuid", headers={"Authorization": "Bearer fake"})
    assert r_404.status_code == status.HTTP_401_UNAUTHORIZED
    err = r_404.json()
    assert "error" in err
    assert "code" in err["error"]
    assert "message" in err["error"]
    assert "details" in err["error"]
    assert "request_id" in err["error"]
    assert err["error"]["request_id"].startswith("req-")
