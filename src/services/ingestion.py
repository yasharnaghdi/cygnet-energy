from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus
from uuid import UUID

from prometheus_client import Gauge, Histogram

from src.api.client import EntsoEAPIClient
from src.api.parser import EntsoEXMLParser
from src.db.connection import database_url as resolve_database_url, load_config

DATA_FRESHNESS = Gauge(
    "cygnet_data_freshness_seconds",
    "Seconds between now and newest ingested point",
    ["zone"],
)
SCRAPE_DURATION = Histogram(
    "cygnet_scrape_duration_seconds",
    "ENTSO-E scrape and persistence duration",
    ["zone"],
)

SOLAR_TYPES = {"B17", "B18"}
WIND_TYPES = {"B19", "B20"}
HYDRO_TYPES = {"B10", "B11", "B12"}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class EntsoEIngestionService:
    def __init__(
        self,
        api_client: EntsoEAPIClient | None = None,
        session_factory: Any | None = None,
    ) -> None:
        self.api_client = api_client or EntsoEAPIClient()
        self._session_factory = session_factory

    def fetch_and_store(
        self,
        zone: str,
        start: datetime,
        end: datetime,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        start = _as_utc(start)
        end = _as_utc(end)

        with SCRAPE_DURATION.labels(zone=zone).time():
            generation_xml = self.api_client.get_actual_generation(zone, start, end)
            load_xml = self.api_client.get_load(zone, start, end)

            generation_df = EntsoEXMLParser.parse_generation_xml(generation_xml) if generation_xml else None
            load_df = EntsoEXMLParser.parse_load_xml(load_xml) if load_xml else None

            generation_records = self._build_generation_records(zone, generation_df, tenant_id)
            load_records = self._build_load_records(zone, load_df, tenant_id)

            generation_inserted, load_inserted, freshest = self._persist(generation_records, load_records)

        if freshest is not None:
            freshness_seconds = max(0.0, (datetime.now(timezone.utc) - freshest).total_seconds())
            DATA_FRESHNESS.labels(zone=zone).set(freshness_seconds)

        return {
            "zone": zone,
            "generation_records": generation_inserted,
            "load_records": load_inserted,
            "total_records": generation_inserted + load_inserted,
            "freshest_timestamp": freshest,
        }

    def _persist(
        self,
        generation_records: list[dict[str, Any]],
        load_records: list[dict[str, Any]],
    ) -> tuple[int, int, datetime | None]:
        if not generation_records and not load_records:
            return 0, 0, None

        session_factory = self._session_factory or self._build_session_factory()
        session = session_factory()
        freshest: datetime | None = None
        try:
            if generation_records:
                self._upsert_generation(session, generation_records)
                freshest = max(record["timestamp"] for record in generation_records)
            if load_records:
                self._upsert_load(session, load_records)
                load_latest = max(record["timestamp"] for record in load_records)
                freshest = load_latest if freshest is None else max(freshest, load_latest)
            session.commit()
            return len(generation_records), len(load_records), freshest
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _build_generation_records(self, zone: str, df: Any, tenant_id: UUID) -> list[dict[str, Any]]:
        if df is None or df.empty:
            return []

        working = df.copy()
        working["time"] = working["time"].apply(_as_utc)

        rows: list[dict[str, Any]] = []
        for timestamp, frame in working.groupby("time"):
            wind_mw = float(frame[frame["psr_type"].isin(WIND_TYPES)]["actual_generation_mw"].sum())
            solar_mw = float(frame[frame["psr_type"].isin(SOLAR_TYPES)]["actual_generation_mw"].sum())
            hydro_mw = float(frame[frame["psr_type"].isin(HYDRO_TYPES)]["actual_generation_mw"].sum())
            total_mw = float(frame["actual_generation_mw"].sum())
            rows.append(
                {
                    "tenant_id": tenant_id,
                    "zone": zone,
                    "timestamp": timestamp,
                    "wind_mw": wind_mw,
                    "solar_mw": solar_mw,
                    "hydro_mw": hydro_mw,
                    "total_mw": total_mw,
                }
            )
        return rows

    def _build_load_records(self, zone: str, df: Any, tenant_id: UUID) -> list[dict[str, Any]]:
        if df is None or df.empty:
            return []

        load_column = "total_load_mw" if "total_load_mw" in df.columns else "load_consumption_mw"
        working = df.copy()
        working["time"] = working["time"].apply(_as_utc)
        rows: list[dict[str, Any]] = []
        for timestamp, frame in working.groupby("time"):
            rows.append(
                {
                    "tenant_id": tenant_id,
                    "zone": zone,
                    "timestamp": timestamp,
                    "load_mw": float(frame[load_column].sum()),
                }
            )
        return rows

    def _upsert_generation(self, session: Any, records: list[dict[str, Any]]) -> None:
        from sqlalchemy.dialects.postgresql import insert

        from src.db.models import GenerationRecord

        stmt = insert(GenerationRecord).values(records)
        update_map = {
            "tenant_id": stmt.excluded.tenant_id,
            "wind_mw": stmt.excluded.wind_mw,
            "solar_mw": stmt.excluded.solar_mw,
            "hydro_mw": stmt.excluded.hydro_mw,
            "total_mw": stmt.excluded.total_mw,
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["zone", "timestamp"],
            set_=update_map,
        )
        session.execute(stmt)

    def _upsert_load(self, session: Any, records: list[dict[str, Any]]) -> None:
        from sqlalchemy.dialects.postgresql import insert

        from src.db.models import LoadRecord

        stmt = insert(LoadRecord).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["zone", "timestamp"],
            set_={
                "tenant_id": stmt.excluded.tenant_id,
                "load_mw": stmt.excluded.load_mw,
            },
        )
        session.execute(stmt)

    def _build_session_factory(self) -> Any:
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
        except ModuleNotFoundError as exc:
            raise RuntimeError("SQLAlchemy is required for ingestion persistence") from exc

        database_url = self._database_url()
        engine = create_engine(database_url, pool_pre_ping=True, future=True)
        return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def _database_url(self) -> str:
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            return resolve_database_url()

        cfg = load_config()["database"]
        user = quote_plus(str(cfg["user"]))
        password = quote_plus(str(cfg["password"]))
        host = cfg["host"]
        port = cfg["port"]
        name = cfg["name"]
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
