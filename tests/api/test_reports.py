from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes import reports


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


class FakeLLM:
    def __init__(self, backend: str, text: str) -> None:
        self._backend = backend
        self._text = text

    def refresh_backend(self) -> None:
        return None

    def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 320) -> str:
        return self._text

    def get_backend_info(self) -> dict[str, Any]:
        if self._backend == "ollama":
            return {
                "backend": "ollama",
                "ollama_url": "http://localhost:11434",
                "ollama_model": "llama2:7b",
                "hf_model": None,
                "hf_device": None,
            }
        if self._backend == "huggingface":
            return {
                "backend": "huggingface",
                "ollama_url": None,
                "ollama_model": None,
                "hf_model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
                "hf_device": "cpu",
            }
        return {
            "backend": "fallback",
            "ollama_url": None,
            "ollama_model": None,
            "hf_model": None,
            "hf_device": None,
        }


def _sample_rows(hours: int = 24):
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    rows = []
    for idx in range(hours):
        ts = now - timedelta(hours=hours - idx)
        rows.append(
            {
                "timestamp": ts,
                "wind_mw": 5500.0 + idx * 5.0,
                "solar_mw": 3200.0 + idx * 3.0,
                "hydro_mw": 1200.0,
                "total_mw": 24000.0 + idx * 10.0,
                "load_mw": 22800.0 + idx * 8.0,
                "price_eur_mwh": 70.0 + idx * 0.4,
            }
        )
    return rows


def test_reports_endpoint_requires_auth_when_bypass_disabled(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_BYPASS_DEV", "false")

    client = TestClient(app)
    response = client.post(
        "/api/reports/generate",
        json={
            "persona": "trader",
            "zone": "DE",
            "scenario": "Base Case",
            "date_range": ["2026-02-16", "2026-02-23"],
        },
    )
    assert response.status_code == 401


def test_reports_generate_with_ollama_backend(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_BYPASS_DEV", "true")
    monkeypatch.setattr(reports, "get_connection", lambda: DummyConnection(_sample_rows(48)))
    monkeypatch.setattr(reports, "get_llm", lambda: FakeLLM("ollama", "Synthetic report from Ollama."))

    client = TestClient(app)
    response = client.post(
        "/api/reports/generate",
        json={
            "persona": "trader",
            "zone": "DE",
            "scenario": "Base Case",
            "date_range": ["2026-02-16", "2026-02-23"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["persona"] == "trader"
    assert payload["scenario"] == "Base Case"
    assert payload["date_range"] == ["2026-02-16", "2026-02-23"]
    assert payload["parameter_weights"] == {
        "price": 0.4,
        "renewable_share": 0.2,
        "margin": 0.2,
        "carbon": 0.2,
    }
    assert payload["backend"] == "ollama"
    assert payload["llm_available"] is True
    assert payload["narrative"] == "Synthetic report from Ollama."
    assert payload["generation_time_ms"] >= 0
    assert payload["data_summary"]["zone"] == "DE"


def test_reports_generate_with_fallback_backend(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_BYPASS_DEV", "true")
    monkeypatch.setattr(reports, "get_connection", lambda: DummyConnection(_sample_rows(72)))
    monkeypatch.setattr(reports, "get_llm", lambda: FakeLLM("fallback", "Structured fallback summary."))

    client = TestClient(app)
    response = client.post(
        "/api/reports/generate",
        json={
            "persona": "policy_analyst",
            "zone": "DE",
            "scenario": "High Renewable",
            "date_range": ["2026-02-16", "2026-02-23"],
            "parameter_weights": {"renewable_share": 0.5, "carbon": 0.3, "price": 0.1, "margin": 0.1},
            "current_soc": 55,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["persona"] == "policymaker"
    assert payload["scenario"] == "High Renewable"
    assert payload["backend"] == "fallback"
    assert payload["llm_available"] is False
    assert payload["narrative"] == "Structured fallback summary."
    assert payload["data_summary"]["current_soc"] == 55


def test_reports_backend_status(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_BYPASS_DEV", "true")
    monkeypatch.setattr(reports, "get_llm", lambda: FakeLLM("huggingface", "unused"))

    client = TestClient(app)
    response = client.get("/api/reports/backend-status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["backend"] == "huggingface"
    assert payload["hf_model"] == "TinyLlama/TinyLlama-1.1B-Chat-v1.0"


def test_reports_generate_when_db_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_BYPASS_DEV", "true")

    def _raise_connection_error():
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(reports, "get_connection", _raise_connection_error)
    monkeypatch.setattr(reports, "get_llm", lambda: FakeLLM("fallback", "Structured fallback summary."))

    client = TestClient(app)
    response = client.post(
        "/api/reports/generate",
        json={
            "persona": "trader",
            "zone": "DE",
            "scenario": "Grid Stress",
            "date_range": ["2026-02-16", "2026-02-23"],
            "parameter_weights": {"price": 0.7, "renewable_share": 0.1, "margin": 0.1, "carbon": 0.1},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["backend"] == "fallback"
    assert payload["llm_available"] is False
    assert payload["narrative"] == "Structured fallback summary."
    assert "data_warning" in payload["data_summary"]


def test_reports_generate_normalizes_custom_parameter_weights(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_BYPASS_DEV", "true")
    monkeypatch.setattr(reports, "get_connection", lambda: DummyConnection(_sample_rows(48)))
    monkeypatch.setattr(reports, "get_llm", lambda: FakeLLM("ollama", "Synthetic report from Ollama."))

    client = TestClient(app)
    response = client.post(
        "/api/reports/generate",
        json={
            "persona": "grid_operator",
            "zone": "DE",
            "scenario": "Custom",
            "date_range": ["2026-02-16", "2026-02-23"],
            "parameter_weights": {"price": 7, "renewable_share": 1, "margin": 1, "carbon": 1},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["persona"] == "operator"
    assert payload["scenario"] == "Custom"
    assert sum(payload["parameter_weights"].values()) == pytest.approx(1.0, abs=1e-9)
    assert payload["parameter_weights"]["price"] == pytest.approx(0.7, abs=1e-9)
