import pytest
from fastapi import status


def test_login_success(client, seeded_users):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "test_inspector", "password": "Password123!"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "test_inspector"
    assert data["user"]["role"] == "INSPECTOR"
    # Verify HttpOnly cookie is set
    assert "casttrace_session" in response.cookies


def test_login_with_email(client, seeded_users):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "inspector@casttrace.local", "password": "Password123!"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["user"]["email"] == "inspector@casttrace.local"
    assert data["user"]["role"] == "INSPECTOR"


def test_login_invalid_password(client, seeded_users):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "test_inspector", "password": "WrongPassword!"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    assert data["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_unknown_user(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "non_existent_user", "password": "Password123!"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    assert data["error"]["code"] == "INVALID_CREDENTIALS"


def test_get_me_success_bearer_token(client, inspector_headers):
    response = client.get("/api/v1/auth/me", headers=inspector_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["username"] == "test_inspector"
    assert data["role"] == "INSPECTOR"


def test_get_me_success_cookie(client, seeded_users):
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "test_supervisor", "password": "Password123!"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    cookie_token = login_res.cookies.get("casttrace_session")
    assert cookie_token

    # Request without Authorization header, using cookie
    response = client.get("/api/v1/auth/me", cookies={"casttrace_session": cookie_token})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["username"] == "test_supervisor"
    assert data["role"] == "SUPERVISOR"


def test_get_me_unauthenticated(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    assert data["error"]["code"] == "UNAUTHENTICATED"


def test_get_me_invalid_token(client):
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.payload"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    assert data["error"]["code"] == "INVALID_TOKEN"


def test_logout_revokes_token_and_clears_cookie(client, seeded_users):
    # 1. Login to obtain token and cookie
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "test_qm", "password": "Password123!"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    token = login_res.json()["access_token"]

    # 2. Verify token works
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == status.HTTP_200_OK

    # 3. Logout
    logout_res = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == status.HTTP_200_OK

    # 4. Verify token is now rejected as revoked
    post_logout_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert post_logout_res.status_code == status.HTTP_401_UNAUTHORIZED
    assert post_logout_res.json()["error"]["code"] == "TOKEN_REVOKED"


def test_rbac_inspector_forbidden_from_qm_action(client, inspector_headers):
    # Inspector attempts to authorize a batch decision (QM only)
    response = client.post(
        "/api/v1/batches/dummy-batch-id/decisions",
        json={"decision": "RELEASE", "reason": "Unauthorized attempt by inspector"},
        headers=inspector_headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


def test_rbac_supervisor_forbidden_from_qm_action(client, supervisor_headers):
    # Supervisor attempts to authorize a batch decision (QM only)
    response = client.post(
        "/api/v1/batches/dummy-batch-id/decisions",
        json={"decision": "RELEASE", "reason": "Unauthorized attempt by supervisor"},
        headers=supervisor_headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


def test_rbac_inspector_forbidden_from_creating_batch(client, inspector_headers):
    # Inspector attempts to create a production batch (Supervisor or QM only)
    response = client.post(
        "/api/v1/batches",
        json={
            "batch_number": "BATCH-FORBIDDEN-001",
            "product_id": "dummy-product",
            "manufacture_date": "2026-10-24",
            "declared_quantity": 100,
        },
        headers=inspector_headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


def test_demo_accounts_login_and_roles(client, db_session):
    from backend.scripts.seed import seed_database
    seed_database(db=db_session)

    demo_credentials = [
        ("inspector@casttrace.demo", "Inspect@123", "INSPECTOR"),
        ("supervisor@casttrace.demo", "Supervise@123", "SUPERVISOR"),
        ("quality@casttrace.demo", "Quality@123", "QUALITY_MANAGER"),
    ]

    for user_id, password, expected_role in demo_credentials:
        # Successful login
        res = client.post("/api/v1/auth/login", json={"username": user_id, "password": password})
        assert res.status_code == status.HTTP_200_OK, f"Failed login for {user_id}"
        data = res.json()
        assert data["user"]["role"] == expected_role
        token = data["access_token"]

        # Verify /auth/me reflects identity and role
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == status.HTTP_200_OK
        assert me.json()["role"] == expected_role

        # Reject incorrect password
        bad_res = client.post("/api/v1/auth/login", json={"username": user_id, "password": "WrongPassword!"})
        assert bad_res.status_code == status.HTTP_401_UNAUTHORIZED
        assert bad_res.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_unauthenticated_requests_to_protected_endpoints(client):
    endpoints = [
        ("GET", "/api/v1/auth/me"),
        ("POST", "/api/v1/inspections"),
        ("POST", "/api/v1/batches"),
        ("GET", "/api/v1/audit-logs"),
    ]
    for method, path in endpoints:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, json={})
        assert res.status_code == status.HTTP_401_UNAUTHORIZED, f"{method} {path} should be 401"

