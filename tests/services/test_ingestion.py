from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.db.constants import SEED_TENANT_ID
from src.services.ingestion import EntsoEIngestionService


class DummyApiClient:
    def get_actual_generation(self, zone: str, start: datetime, end: datetime) -> str:
        return "<generation />"

    def get_load(self, zone: str, start: datetime, end: datetime) -> str:
        return "<load />"


class DummySession:
    def __init__(self):
        self.committed = False
        self.closed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


def test_fetch_and_store_aggregates_and_persists(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))
    generation_df = pd.DataFrame(
        [
            {"time": datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc), "psr_type": "B18", "actual_generation_mw": 100.0},
            {"time": datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc), "psr_type": "B19", "actual_generation_mw": 200.0},
            {"time": datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc), "psr_type": "B11", "actual_generation_mw": 50.0},
        ]
    )
    load_df = pd.DataFrame(
        [
            {"time": datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc), "total_load_mw": 310.0},
        ]
    )

    monkeypatch.setattr("src.services.ingestion.EntsoEXMLParser.parse_generation_xml", lambda xml: generation_df)
    monkeypatch.setattr("src.services.ingestion.EntsoEXMLParser.parse_load_xml", lambda xml: load_df)

    session = DummySession()
    service = EntsoEIngestionService(
        api_client=DummyApiClient(),
        session_factory=lambda: session,
    )

    monkeypatch.setattr(service, "_upsert_generation", lambda db, records: None)
    monkeypatch.setattr(service, "_upsert_load", lambda db, records: None)

    result = service.fetch_and_store(
        zone="DE",
        start=datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc),
        end=datetime(2026, 2, 1, 1, 0, tzinfo=timezone.utc),
        tenant_id=SEED_TENANT_ID,
    )

    assert result["zone"] == "DE"
    assert result["generation_records"] == 1
    assert result["load_records"] == 1
    assert result["total_records"] == 2
    assert result["freshest_timestamp"] == datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
    assert session.committed is True
    assert session.closed is True


def test_fetch_and_store_empty_payload(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))
    monkeypatch.setattr("src.services.ingestion.EntsoEXMLParser.parse_generation_xml", lambda xml: None)
    monkeypatch.setattr("src.services.ingestion.EntsoEXMLParser.parse_load_xml", lambda xml: None)

    service = EntsoEIngestionService(api_client=DummyApiClient(), session_factory=lambda: DummySession())
    result = service.fetch_and_store(
        zone="DE",
        start=datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc),
        end=datetime(2026, 2, 1, 1, 0, tzinfo=timezone.utc),
        tenant_id=SEED_TENANT_ID,
    )

    assert result["generation_records"] == 0
    assert result["load_records"] == 0
    assert result["total_records"] == 0
    assert result["freshest_timestamp"] is None
