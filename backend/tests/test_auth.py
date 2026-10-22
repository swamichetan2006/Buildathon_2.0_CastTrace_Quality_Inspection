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


def test_get_me_success(client, inspector_headers):
    response = client.get("/api/v1/auth/me", headers=inspector_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["username"] == "test_inspector"
    assert data["role"] == "INSPECTOR"


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
