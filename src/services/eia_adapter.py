from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin

import psycopg2
import requests

EIA_BASE = "https://api.eia.gov/v2/"
RETAIL_SALES_DATASET = "electricity/retail-sales"
NON_STATE_REGION_IDS = {"US", "PR", "VI", "GU", "MP", "AS", "OT", "NA"}


@dataclass(frozen=True)
class EIAQuery:
    path: str
    api_key: str
    data: Optional[List[str]] = None
    facets: Optional[Dict[str, List[str]]] = None
    frequency: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    sort_column: Optional[str] = None
    sort_direction: Optional[str] = None
    length: Optional[int] = None
    offset: Optional[int] = None


def _require_api_key() -> str:
    api_key = os.getenv("EIA_API_KEY")
    if not api_key:
        raise RuntimeError("EIA_API_KEY is required but not set")
    return api_key


def build_eia_url(q: EIAQuery, *, data_mode: bool) -> Tuple[str, List[Tuple[str, str]]]:
    endpoint = f"{q.path}/data" if data_mode else q.path
    url = urljoin(EIA_BASE, endpoint)

    params: List[Tuple[str, str]] = [("api_key", q.api_key)]

    if data_mode and q.data:
        for col in q.data:
            params.append(("data[]", col))

    if data_mode and q.facets:
        for facet_id, values in q.facets.items():
            key = f"facets[{facet_id}][]"
            for value in values:
                params.append((key, value))

    if data_mode and q.frequency:
        params.append(("frequency", q.frequency))
    if data_mode and q.start:
        params.append(("start", q.start))
    if data_mode and q.end:
        params.append(("end", q.end))

    if data_mode and q.sort_column:
        params.append(("sort[0][column]", q.sort_column))
        params.append(("sort[0][direction]", q.sort_direction or "desc"))

    if data_mode and q.length is not None:
        params.append(("length", str(q.length)))
    if data_mode and q.offset is not None:
        params.append(("offset", str(q.offset)))

    return url, params


def eia_get(session: requests.Session, url: str, params: List[Tuple[str, str]], timeout: int = 30) -> dict:
    response = session.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def fetch_all_pages(
    session: requests.Session,
    base_query: EIAQuery,
    *,
    sleep_seconds: float = 0.0,
) -> List[dict]:
    page_size = base_query.length or 5000
    offset = 0
    rows: List[dict] = []

    while True:
        query = EIAQuery(**{**base_query.__dict__, "length": page_size, "offset": offset})
        url, params = build_eia_url(query, data_mode=True)
        payload = eia_get(session, url, params)

        resp = payload.get("response", {})
        data = resp.get("data", [])
        total = resp.get("total")

        rows.extend(data)

        if total is None:
            if len(data) < page_size:
                break
            offset += page_size
        else:
            offset += page_size
            if offset >= int(total):
                break
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return rows


class EIAAdapter:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or _require_api_key()
        self.page_sleep_seconds = float(os.getenv("EIA_PAGE_SLEEP_SECONDS", "0.15"))
        self.session = requests.Session()

    def fetch_metadata(self, path: str = RETAIL_SALES_DATASET) -> dict:
        query = EIAQuery(path=path, api_key=self.api_key)
        url, params = build_eia_url(query, data_mode=False)
        return eia_get(self.session, url, params)

    def fetch_facet_values(self, path: str, facet_id: str) -> List[dict]:
        query = EIAQuery(path=f"{path}/facet/{facet_id}", api_key=self.api_key)
        url, params = build_eia_url(query, data_mode=False)
        payload = eia_get(self.session, url, params)
        return payload.get("response", {}).get("data", [])

    def fetch_retail_prices(
        self,
        *,
        state_ids: Iterable[str],
        sector_ids: Iterable[str],
        start: str,
        end: str,
        frequency: str = "monthly",
    ) -> List[dict]:
        facets = {"stateid": list(state_ids), "sectorid": list(sector_ids)}
        query = EIAQuery(
            path=RETAIL_SALES_DATASET,
            api_key=self.api_key,
            data=["price"],
            facets=facets,
            frequency=frequency,
            start=start,
            end=end,
            sort_column="period",
            sort_direction="desc",
            length=5000,
            offset=0,
        )
        return fetch_all_pages(
            self.session,
            query,
            sleep_seconds=self.page_sleep_seconds,
        )

    def fetch_retail_state_ids(self, include_territories: bool = False) -> List[str]:
        facet_rows = self.fetch_facet_values(RETAIL_SALES_DATASET, "stateid")
        out: List[str] = []
        seen = set()
        for row in facet_rows:
            candidate = (
                row.get("id")
                or row.get("stateid")
                or row.get("value")
                or row.get("code")
            )
            if not candidate:
                continue
            state_id = str(candidate).strip().upper()
            if len(state_id) != 2:
                continue
            if not include_territories and state_id in NON_STATE_REGION_IDS:
                continue
            if state_id not in seen:
                seen.add(state_id)
                out.append(state_id)
        out.sort()
        return out

    def ingest_retail_prices(
        self,
        *,
        state_ids: Iterable[str],
        sector_ids: Iterable[str],
        start: str,
        end: str,
    ) -> int:
        rows = self.fetch_retail_prices(
            state_ids=state_ids,
            sector_ids=sector_ids,
            start=start,
            end=end,
        )
        records = list(self._normalize_retail_prices(rows))
        if not records:
            return 0

        import psycopg2.extras
        from src.db.connection import get_connection

        conn = get_connection()
        cur = conn.cursor()
        prepared_records = [
            (
                rec[0],
                rec[1],
                rec[2],
                rec[3],
                rec[4],
                rec[5],
                rec[6],
                rec[7],
                rec[8],
                psycopg2.extras.Json(rec[9]),
                rec[10],
            )
            for rec in records
        ]
        try:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO canonical_metrics (
                    timestamp_utc,
                    region_type,
                    region_id,
                    granularity,
                    metric_name,
                    metric_value,
                    metric_unit,
                    source,
                    dataset,
                    facets,
                    ingestion_timestamp
                )
                VALUES %s
                ON CONFLICT (
                    timestamp_utc,
                    region_type,
                    region_id,
                    granularity,
                    metric_name,
                    source,
                    dataset
                )
                DO UPDATE SET
                    metric_value = EXCLUDED.metric_value,
                    metric_unit = EXCLUDED.metric_unit,
                    facets = EXCLUDED.facets,
                    ingestion_timestamp = EXCLUDED.ingestion_timestamp
                """,
                prepared_records,
            )
            conn.commit()
        except psycopg2.errors.UndefinedTable as exc:
            conn.rollback()
            raise RuntimeError(
                "canonical_metrics is missing. Run the latest database migrations "
                "(for example: `poetry run alembic upgrade head` or the Docker migration step) "
                "and retry EIA ingestion."
            ) from exc
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
        return len(records)

    def _normalize_retail_prices(self, rows: Iterable[dict]) -> Iterable[Tuple]:
        for row in rows:
            period = row.get("period")
            state_id = row.get("stateid")
            sector_id = row.get("sectorid")
            price = row.get("price")

            if not (period and state_id and sector_id and price is not None):
                continue

            try:
                year, month = period.split("-")
                timestamp = datetime(int(year), int(month), 1, tzinfo=timezone.utc)
            except ValueError:
                continue

            price_cents_per_kwh = float(price)
            price_usd_per_mwh = price_cents_per_kwh * 10

            yield (
                timestamp,
                "state",
                state_id,
                "month",
                "retail_price",
                price_usd_per_mwh,
                "USD/MWh",
                "EIA",
                RETAIL_SALES_DATASET,
                {"stateid": state_id, "sectorid": sector_id},
                datetime.now(timezone.utc),
            )
