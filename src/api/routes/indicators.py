from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.middleware.auth import verify_token
from src.api.models.schemas import (
    CountryCode,
    IndicatorPackageResponse,
    RegionResponse,
    RegionSource,
)
from src.db.connection import get_connection
from src.utils.zones import get_zone_keys

router = APIRouter(prefix="/v1", tags=["Indicators"], dependencies=[Depends(verify_token)])


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.get("/indicators", response_model=List[IndicatorPackageResponse])
async def get_indicator_packages(
    zone: CountryCode = Query(default=CountryCode.DE),
    start: Optional[datetime] = Query(default=None),
    end: Optional[datetime] = Query(default=None),
    limit: int = Query(default=48, ge=1, le=1000),
) -> List[IndicatorPackageResponse]:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    zone_keys = get_zone_keys(zone.value)
    start_clause = "AND timestamp_utc >= %s" if start else ""
    end_clause = "AND timestamp_utc <= %s" if end else ""

    query = f"""
        SELECT
            timestamp_utc,
            region_type,
            region_id,
            granularity,
            carbon_intensity,
            fossil_share,
            volatility,
            clean_window
        FROM indicator_packages_v1
        WHERE region_id = ANY(%s)
        {start_clause}
        {end_clause}
        ORDER BY timestamp_utc DESC
        LIMIT %s
    """

    params = [zone_keys]
    if start:
        params.append(_to_utc(start))
    if end:
        params.append(_to_utc(end))
    params.append(limit)

    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No indicator data available")

    return [IndicatorPackageResponse(**row) for row in rows]


@router.get("/regions", response_model=List[RegionResponse])
async def get_regions(
    source: RegionSource = Query(default=RegionSource.entsoe),
) -> List[RegionResponse]:
    if source == RegionSource.entsoe:
        return [
            RegionResponse(region_id=zone.value, region_type="zone", source=RegionSource.entsoe)
            for zone in CountryCode
        ]

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT DISTINCT region_id
            FROM canonical_metrics
            WHERE source = 'EIA'
              AND dataset = 'electricity/retail-sales'
              AND metric_name = 'retail_price'
            ORDER BY region_id
            """
        )
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    return [
        RegionResponse(region_id=row[0], region_type="state", source=RegionSource.eia)
        for row in rows
    ]
