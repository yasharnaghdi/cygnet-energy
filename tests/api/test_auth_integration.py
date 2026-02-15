from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import app


def test_generation_endpoint_requires_token_when_bypass_disabled(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_BYPASS_DEV", "false")
    client = TestClient(app)
    response = client.get("/api/generation/zones")
    assert response.status_code == 401


def test_generation_endpoint_with_dev_bypass(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_BYPASS_DEV", "true")
    client = TestClient(app)
    response = client.get("/api/generation/zones")
    assert response.status_code == 200
    assert "zones" in response.json()


def test_whoami_returns_claims(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_BYPASS_DEV", "true")
    monkeypatch.setenv("AUTH_BYPASS_SUB", "qa-user")
    monkeypatch.setenv("AUTH_BYPASS_ROLES", "analyst,developer")
    monkeypatch.setenv("AUTH_BYPASS_SCOPES", "api.read,api.write")

    client = TestClient(app)
    response = client.get("/api/whoami")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sub"] == "qa-user"
    assert payload["roles"] == ["analyst", "developer"]
    assert payload["scopes"] == ["api.read", "api.write"]
