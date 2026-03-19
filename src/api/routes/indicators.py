from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, Query, Request

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
    request: Request,
    zone: CountryCode = Query(default=CountryCode.DE),
    start: Optional[datetime] = Query(default=None),
    end: Optional[datetime] = Query(default=None),
    limit: int = Query(default=48, ge=1, le=1000),
) -> List[IndicatorPackageResponse]:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    zone_keys = get_zone_keys(zone.value)
    tenant_id = request.state.tenant_id
    start_clause = "AND timestamp >= %s" if start else ""
    end_clause = "AND timestamp <= %s" if end else ""

    query = f"""
        WITH base AS (
            SELECT
                timestamp AS timestamp_utc,
                zone AS region_id,
                total_mw,
                (
                    (
                        GREATEST(total_mw - COALESCE(wind_mw, 0) - COALESCE(solar_mw, 0) - COALESCE(hydro_mw, 0), 0) * 490
                        + COALESCE(wind_mw, 0) * 11
                        + COALESCE(solar_mw, 0) * 41
                        + COALESCE(hydro_mw, 0) * 24
                    ) / NULLIF(total_mw, 0)
                ) AS carbon_intensity,
                (
                    GREATEST(total_mw - COALESCE(wind_mw, 0) - COALESCE(solar_mw, 0) - COALESCE(hydro_mw, 0), 0)
                    / NULLIF(total_mw, 0) * 100.0
                ) AS fossil_share
            FROM generation_records
            WHERE zone = ANY(%s)
              AND tenant_id = %s
              {start_clause}
              {end_clause}
              AND total_mw > 0
        ),
        metrics AS (
            SELECT
                timestamp_utc,
                region_id,
                carbon_intensity,
                fossil_share,
                STDDEV_SAMP(carbon_intensity) OVER (
                    PARTITION BY region_id
                    ORDER BY timestamp_utc
                    ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
                ) AS volatility
            FROM base
        )
        SELECT
            timestamp_utc,
            'zone'::text AS region_type,
            region_id,
            'hour'::text AS granularity,
            carbon_intensity,
            fossil_share,
            volatility,
            (carbon_intensity <= 200) AS clean_window
        FROM metrics
        ORDER BY timestamp_utc DESC
        LIMIT %s
    """

    params = [zone_keys, tenant_id]
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
    request: Request,
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
            WHERE tenant_id = %s
              AND source = 'EIA'
              AND dataset = 'electricity/retail-sales'
              AND metric_name = 'retail_price'
            ORDER BY region_id
            """,
            (request.state.tenant_id,),
        )
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    return [
        RegionResponse(region_id=row[0], region_type="state", source=RegionSource.eia)
        for row in rows
    ]
