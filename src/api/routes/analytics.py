from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import psycopg2.extras
from fastapi import APIRouter, Depends, Query, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from src.api.middleware.auth import verify_token
from src.api.models.schemas import TokenData
from src.db.connection import get_connection
from src.db.constants import SEED_TENANT_ID
from src.services.ingestion import DATA_FRESHNESS

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])
metrics_router = APIRouter(prefix="/api", tags=["Metrics"])


def _bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start_dt, end_dt


@router.get("/renewable-fraction")
async def renewable_fraction(
    zone: str = Query(..., min_length=2, max_length=8),
    start_date: date = Query(...),
    end_date: date = Query(...),
    token: TokenData = Depends(verify_token),
) -> list[dict[str, Any]]:
    start_dt, end_dt = _bounds(start_date, end_date)

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            SELECT
                timestamp,
                ROUND(
                    ((COALESCE(wind_mw, 0) + COALESCE(solar_mw, 0) + COALESCE(hydro_mw, 0))
                    / NULLIF(total_mw, 0)) * 100.0,
                    2
                ) AS renewable_pct
            FROM generation_records
            WHERE zone = %s
              AND tenant_id = %s
              AND timestamp >= %s
              AND timestamp < %s
            ORDER BY timestamp
            """,
            (zone, token.tenant_id, start_dt, end_dt),
        )
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    return [
        {"zone": zone, "timestamp": row["timestamp"], "renewable_pct": row["renewable_pct"]}
        for row in rows
    ]


@router.get("/tight-hours")
async def tight_hours(
    zone: str = Query(..., min_length=2, max_length=8),
    days: int = Query(default=7, ge=1, le=365),
    token: TokenData = Depends(verify_token),
) -> list[dict[str, Any]]:
    start_dt = datetime.now(timezone.utc) - timedelta(days=days)

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            WITH generation_hourly AS (
                SELECT
                    timestamp,
                    total_mw AS generation_mw
                FROM generation_records
                WHERE zone = %s
                  AND tenant_id = %s
                  AND timestamp >= %s
            ),
            load_hourly AS (
                SELECT
                    timestamp,
                    load_mw
                FROM load_records
                WHERE zone = %s
                  AND tenant_id = %s
                  AND timestamp >= %s
            )
            SELECT
                g.timestamp,
                g.generation_mw,
                l.load_mw,
                ROUND(g.generation_mw - l.load_mw, 2) AS margin_mw
            FROM generation_hourly g
            JOIN load_hourly l ON l.timestamp = g.timestamp
            WHERE (g.generation_mw - l.load_mw) < 100
            ORDER BY g.timestamp DESC
            """,
            (zone, token.tenant_id, start_dt, zone, token.tenant_id, start_dt),
        )
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    return [
        {
            "zone": zone,
            "timestamp": row["timestamp"],
            "margin_mw": row["margin_mw"],
            "generation_mw": row["generation_mw"],
            "load_mw": row["load_mw"],
        }
        for row in rows
    ]


@metrics_router.get("/metrics")
async def prometheus_metrics(request: Request) -> Response:
    tenant_id = getattr(request.state, "tenant_id", SEED_TENANT_ID)
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT zone, MAX(timestamp) AS max_timestamp
            FROM generation_records
            WHERE tenant_id = %s
            GROUP BY zone
            """,
            (tenant_id,),
        )
        rows = cur.fetchall()
        now = datetime.now(timezone.utc)
        for row in rows:
            max_timestamp = row["max_timestamp"]
            if max_timestamp is None:
                continue
            if max_timestamp.tzinfo is None:
                max_timestamp = max_timestamp.replace(tzinfo=timezone.utc)
            else:
                max_timestamp = max_timestamp.astimezone(timezone.utc)
            age_seconds = max(0.0, (now - max_timestamp).total_seconds())
            DATA_FRESHNESS.labels(zone=row["zone"]).set(age_seconds)
    except Exception:
        pass
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
