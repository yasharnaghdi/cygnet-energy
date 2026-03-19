from __future__ import annotations

from src.db import connection


def test_database_url_rewrites_docker_hostname_for_local_runtime(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@postgres:5432/energy_db")
    monkeypatch.delenv("LOCAL_POSTGRES_PORT", raising=False)
    monkeypatch.setattr(connection, "_running_in_docker", lambda: False)

    assert connection.database_url() == "postgresql+psycopg2://user:pass@localhost:5433/energy_db"
    assert connection._psycopg_database_url() == "postgresql://user:pass@localhost:5433/energy_db"


def test_database_url_keeps_docker_hostname_inside_container(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@postgres:5432/energy_db")
    monkeypatch.setattr(connection, "_running_in_docker", lambda: True)

    assert connection.database_url() == "postgresql+psycopg2://user:pass@postgres:5432/energy_db"


def test_database_url_rewrites_alias_hostname_for_local_runtime(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db:5432/energy_db")
    monkeypatch.delenv("LOCAL_POSTGRES_PORT", raising=False)
    monkeypatch.setattr(connection, "_running_in_docker", lambda: False)

    assert connection.database_url() == "postgresql+psycopg2://user:pass@localhost:5433/energy_db"


def test_best_effort_rewrite_handles_unparseable_url(monkeypatch) -> None:
    monkeypatch.setenv("LOCAL_POSTGRES_PORT", "5544")
    monkeypatch.setattr(connection, "_running_in_docker", lambda: False)

    malformed = "postgresql://user:pass@postgres:5432/energy_db trailing"
    rewritten = connection._best_effort_local_rewrite(malformed)
    assert rewritten.startswith("postgresql://user:pass@localhost:5544/energy_db")


def test_get_connection_registers_uuid_and_uses_normalized_url(monkeypatch) -> None:
    calls: dict[str, object] = {}

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@postgres:5432/energy_db")
    monkeypatch.setattr(connection, "_running_in_docker", lambda: False)
    monkeypatch.setattr(connection, "_UUID_ADAPTER_REGISTERED", False)

    def fake_register_uuid() -> None:
        calls["registered"] = int(calls.get("registered", 0)) + 1

    def fake_connect(dsn: str):
        calls["dsn"] = dsn
        return object()

    monkeypatch.setattr(connection.psycopg2.extras, "register_uuid", fake_register_uuid)
    monkeypatch.setattr(connection.psycopg2, "connect", fake_connect)

    connection.get_connection()

    assert calls.get("registered") == 1
    assert calls.get("dsn") == "postgresql://user:pass@localhost:5433/energy_db"
