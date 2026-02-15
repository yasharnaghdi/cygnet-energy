from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes import analytics


class DummyCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, query: str, params=None) -> None:
        self.query = query
        self.params = params

    def fetchall(self):
        return self._rows

    def close(self) -> None:
        return None


class DummyConnection:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self, cursor_factory=None):
        return DummyCursor(self._rows)

    def close(self) -> None:
        return None


def test_renewable_fraction_requires_auth(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_BYPASS_DEV", "false")

    client = TestClient(app)
    response = client.get(
        "/api/analytics/renewable-fraction",
        params={"zone": "DE", "start_date": "2026-02-01", "end_date": "2026-02-02"},
    )

    assert response.status_code == 401


def test_renewable_fraction_with_dev_bypass(monkeypatch) -> None:
    rows = [
        {"timestamp": "2026-02-01T00:00:00+00:00", "renewable_pct": 48.2},
        {"timestamp": "2026-02-01T01:00:00+00:00", "renewable_pct": 51.7},
    ]
    monkeypatch.setenv("AUTH_BYPASS_DEV", "true")
    monkeypatch.setattr(analytics, "get_connection", lambda: DummyConnection(rows))

    client = TestClient(app)
    response = client.get(
        "/api/analytics/renewable-fraction",
        params={"zone": "DE", "start_date": "2026-02-01", "end_date": "2026-02-02"},
    )

    assert response.status_code == 200
    assert response.json() == [
        {"zone": "DE", "timestamp": "2026-02-01T00:00:00+00:00", "renewable_pct": 48.2},
        {"zone": "DE", "timestamp": "2026-02-01T01:00:00+00:00", "renewable_pct": 51.7},
    ]


def test_tight_hours_with_dev_bypass(monkeypatch) -> None:
    rows = [
        {
            "timestamp": "2026-02-01T03:00:00+00:00",
            "margin_mw": 85.5,
            "generation_mw": 1200.0,
            "load_mw": 1114.5,
        }
    ]
    monkeypatch.setenv("AUTH_BYPASS_DEV", "true")
    monkeypatch.setattr(analytics, "get_connection", lambda: DummyConnection(rows))

    client = TestClient(app)
    response = client.get("/api/analytics/tight-hours", params={"zone": "DE", "days": 7})

    assert response.status_code == 200
    assert response.json() == [
        {
            "zone": "DE",
            "timestamp": "2026-02-01T03:00:00+00:00",
            "margin_mw": 85.5,
            "generation_mw": 1200.0,
            "load_mw": 1114.5,
        }
    ]


def test_metrics_endpoint_open() -> None:
    client = TestClient(app)
    response = client.get("/api/metrics")
    assert response.status_code == 200
    assert "HELP" in response.text
