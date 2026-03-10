from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes import reports
from src.services.llm_client import LLMBackend, UnifiedLLMClient


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
        self.last_force_backend: str | None = None

    def refresh_backend(self) -> None:
        return None

    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 320,
        force_backend: str | None = None,
        force_model: str | None = None,
    ) -> str:
        self.last_force_backend = force_backend
        self.last_force_model = force_model
        return self._text

    def get_backend_info(self) -> dict[str, Any]:
        active_backend = self.last_force_backend or self._backend
        if active_backend == "ollama":
            return {
                "backend": "ollama",
                "active_backend": "ollama",
                "available_backends": [{"type": "ollama", "models": ["llama2:7b"]}, {"type": "fallback", "models": ["template"]}],
                "available_backend_types": ["ollama", "fallback"],
                "ollama_url": "http://localhost:11434",
                "ollama_model": "llama2:7b",
                "openai_model": None,
                "hf_model": None,
                "hf_device": None,
            }
        if active_backend == "huggingface":
            return {
                "backend": "huggingface",
                "active_backend": "huggingface",
                "available_backends": [{"type": "huggingface", "models": ["TinyLlama/TinyLlama-1.1B-Chat-v1.0"]}, {"type": "fallback", "models": ["template"]}],
                "available_backend_types": ["huggingface", "fallback"],
                "openai_model": None,
                "ollama_url": None,
                "ollama_model": None,
                "hf_model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
                "hf_device": "cpu",
            }
        if active_backend == "openai":
            return {
                "backend": "openai",
                "active_backend": "openai",
                "available_backends": [{"type": "openai", "models": ["gpt-4o-mini"]}, {"type": "fallback", "models": ["template"]}],
                "available_backend_types": ["openai", "fallback"],
                "openai_model": "gpt-4o-mini",
                "ollama_url": None,
                "ollama_model": None,
                "hf_model": None,
                "hf_device": None,
            }
        return {
            "backend": "fallback",
            "active_backend": "fallback",
            "available_backends": [{"type": "fallback", "models": ["template"]}],
            "available_backend_types": ["fallback"],
            "openai_model": None,
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


def test_reports_generate_passes_backend_override(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_BYPASS_DEV", "true")
    monkeypatch.setattr(reports, "get_connection", lambda: DummyConnection(_sample_rows(48)))
    fake_llm = FakeLLM("ollama", "Synthetic report from OpenAI.")
    monkeypatch.setattr(reports, "get_llm", lambda: fake_llm)

    client = TestClient(app)
    response = client.post(
        "/api/reports/generate",
        json={
            "persona": "trader",
            "zone": "DE",
            "scenario": "Base Case",
            "date_range": ["2026-02-16", "2026-02-23"],
            "backend": "openai",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert fake_llm.last_force_backend == "openai"
    assert payload["backend"] == "openai"
    assert payload["llm_available"] is True


def test_reports_generate_passes_model_override(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_BYPASS_DEV", "true")
    monkeypatch.setattr(reports, "get_connection", lambda: DummyConnection(_sample_rows(48)))
    fake_llm = FakeLLM("ollama", "Synthetic report from Ollama.")
    monkeypatch.setattr(reports, "get_llm", lambda: fake_llm)

    client = TestClient(app)
    response = client.post(
        "/api/reports/generate",
        json={
            "persona": "trader",
            "zone": "DE",
            "scenario": "Base Case",
            "date_range": ["2026-02-16", "2026-02-23"],
            "backend": "ollama",
            "model": "phi3:mini",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert fake_llm.last_force_backend == "ollama"
    assert fake_llm.last_force_model == "phi3:mini"
    assert payload["backend_info"]["requested_model"] == "phi3:mini"


def test_unified_llm_client_falls_back_when_forced_backend_errors(monkeypatch) -> None:
    client = UnifiedLLMClient()

    monkeypatch.setattr(client, "_is_backend_available", lambda backend: True)

    def _boom(*args, **kwargs):
        raise RuntimeError("openai auth failed")

    monkeypatch.setattr(client, "_generate_with_backend", _boom)

    text = client.generate("test prompt", force_backend="openai")

    assert "Structured summary mode" in text
    assert client.backend == LLMBackend.FALLBACK


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


def test_reports_generate_uses_session_context_values(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_BYPASS_DEV", "true")
    monkeypatch.setattr(reports, "get_connection", lambda: DummyConnection(_sample_rows(48)))
    monkeypatch.setattr(reports, "get_llm", lambda: FakeLLM("fallback", "Context-aware report."))

    client = TestClient(app)
    response = client.post(
        "/api/reports/generate",
        json={
            "persona": "trader",
            "zone": "FR",
            "scenario": "Base Case",
            "date_range": ["2026-02-01", "2026-02-02"],
            "save_history": False,
            "session_context": {
                "session_id": "session-ctx-123",
                "zone": "DE",
                "scenario": "Grid Stress",
                "date_range": ["2026-02-10", "2026-02-12"],
                "parameter_weights": {"price": 0.5, "renewable_share": 0.2, "margin": 0.2, "carbon": 0.1},
                "visited_tabs": ["generation", "load", "carbon", "price"],
                "generated_charts": ["generation_mix_area", "load_curve", "carbon_trend", "price_trend"],
                "generation_params": {"zone": "DE", "renewable_pct": 51.2},
                "load_params": {"peak_hour": 18, "peak_mw": 61200},
                "carbon_params": {"avg_intensity": 243.1},
                "price_params": {"latest_price": 101.4},
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario"] == "Grid Stress"
    assert payload["date_range"] == ["2026-02-10", "2026-02-12"]
    assert payload["parameter_weights"]["price"] == pytest.approx(0.5, abs=1e-9)
    assert payload["data_summary"]["zone"] == "DE"
    assert payload["data_summary"]["session_id"] == "session-ctx-123"
    assert payload["data_summary"]["visited_tabs"] == ["generation", "load", "carbon", "price"]
    assert payload["data_summary"]["generated_charts"] == [
        "generation_mix_area",
        "load_curve",
        "carbon_trend",
        "price_trend",
    ]
    assert payload["data_summary"]["generation_context"] == {"zone": "DE", "renewable_pct": 51.2}
    assert payload["data_summary"]["load_context"] == {"peak_hour": 18, "peak_mw": 61200}
    assert payload["data_summary"]["carbon_context"] == {"avg_intensity": 243.1}
    assert payload["data_summary"]["price_context"] == {"latest_price": 101.4}


def test_reports_generate_overrides_zero_summary_with_generation_context(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_BYPASS_DEV", "true")
    monkeypatch.setattr(reports, "get_connection", lambda: DummyConnection([]))
    monkeypatch.setattr(reports, "get_llm", lambda: FakeLLM("fallback", "Context-bridged report."))

    client = TestClient(app)
    response = client.post(
        "/api/reports/generate",
        json={
            "persona": "trader",
            "zone": "FR",
            "scenario": "Base Case",
            "date_range": ["2024-12-12", "2024-12-12"],
            "save_history": False,
            "session_context": {
                "zone": "FR",
                "date_range": ["2024-12-12", "2024-12-12"],
                "generation_context": {
                    "zone": "DE",
                    "date_range": ["2025-12-01", "2025-12-31"],
                    "rows": 1260,
                    "renewable_pct": 64.07,
                    "total_generation_mwh": 987654.32,
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["date_range"] == ["2025-12-01", "2025-12-31"]
    assert payload["data_summary"]["zone"] == "DE"
    assert payload["data_summary"]["analysis_period"] == ["2025-12-01", "2025-12-31"]
    assert payload["data_summary"]["renewable_pct"] == pytest.approx(64.1, abs=1e-9)
    assert payload["data_summary"]["current_renewable_pct"] == pytest.approx(64.1, abs=1e-9)
    assert payload["data_summary"]["avg_renewable_pct"] == pytest.approx(64.1, abs=1e-9)
    assert payload["data_summary"]["total_generation_mwh"] == pytest.approx(987654.32, abs=1e-9)
