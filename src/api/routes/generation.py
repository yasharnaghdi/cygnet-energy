from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import psycopg2.extras
from fastapi import APIRouter, Depends, Query

from src.api.middleware.auth import verify_token
from src.api.models.schemas import CountryCode, TokenData
from src.db.connection import get_connection
from src.utils.zones import get_zone_keys

router = APIRouter(prefix="/api/generation", tags=["Generation"])


@router.get("/zones")
async def list_zones(token: TokenData = Depends(verify_token)) -> dict[str, list[str]]:
    del token
    return {"zones": [zone.value for zone in CountryCode]}


@router.get("/latest")
async def latest_generation(
    zone: CountryCode = Query(default=CountryCode.DE),
    token: TokenData = Depends(verify_token),
) -> dict[str, Any]:
    del token
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            WITH latest_ts AS (
                SELECT MAX(time) AS ts
                FROM generation_actual
                WHERE bidding_zone_mrid = ANY(%s)
            )
            SELECT
                g.time AS timestamp,
                SUM(g.actual_generation_mw) AS total_mw
            FROM generation_actual g
            JOIN latest_ts l ON l.ts = g.time
            WHERE g.bidding_zone_mrid = ANY(%s)
            GROUP BY g.time
            """,
            (get_zone_keys(zone.value), get_zone_keys(zone.value)),
        )
        row = cur.fetchone()
    finally:
        cur.close()
        conn.close()

    if not row:
        return {"zone": zone.value, "timestamp": None, "total_mw": None}

    timestamp = row["timestamp"]
    if isinstance(timestamp, datetime):
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = timestamp.astimezone(timezone.utc)

    return {"zone": zone.value, "timestamp": timestamp, "total_mw": row["total_mw"]}
