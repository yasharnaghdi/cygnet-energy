from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.api.middleware.auth import verify_token
from src.api.middleware.rate_limit import limiter
from src.api.models.schemas import (
    CarbonIntensityForecastQuery,
    CarbonIntensityQuery,
    CarbonIntensityResponse,
)
from src.db.connection import get_connection
from src.services.carbon_service import CarbonIntensityService
from src.utils.zones import get_zone_keys

router = APIRouter(
    prefix="/carbon-intensity",
    tags=["Carbon Intensity"],
    dependencies=[Depends(verify_token)],
)


def _status_from_intensity(co2_intensity: float) -> str:
    if co2_intensity < 150:
        return "GREEN"
    if co2_intensity <= 300:
        return "YELLOW"
    return "RED"


@router.get("/current", response_model=CarbonIntensityResponse)
@limiter.limit("100/hour")
def get_current_intensity(
    request: Request,
    query: CarbonIntensityQuery = Depends(),
) -> CarbonIntensityResponse:
    conn = get_connection()
    try:
        service = CarbonIntensityService(conn)
        payload = service.get_current_intensity(query.zone.value)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No carbon intensity data found",
            )

        co2_intensity = float(payload["co2_intensity"])
        renewable_pct = float(payload["renewable_pct"])
        fossil_pct = float(payload["fossil_pct"])
        total_generation_mw = float(payload["total_generation_mw"])

        return CarbonIntensityResponse(
            timestamp=payload["timestamp"],
            zone=query.zone,
            co2_intensity=co2_intensity,
            status=_status_from_intensity(co2_intensity),
            renewable_pct=renewable_pct,
            fossil_pct=fossil_pct,
            total_generation_mw=total_generation_mw,
        )
    finally:
        conn.close()


@router.get("/forecast", response_model=List[CarbonIntensityResponse])
@limiter.limit("100/hour")
def get_intensity_forecast(
    request: Request,
    query: CarbonIntensityForecastQuery = Depends(),
) -> List[CarbonIntensityResponse]:
    conn = get_connection()
    try:
        service = CarbonIntensityService(conn)
        zone_keys = get_zone_keys(query.zone.value)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=query.hours)

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT time, psr_type, actual_generation_mw
            FROM generation_actual
            WHERE bidding_zone_mrid = ANY(%s)
              AND time BETWEEN %s AND %s
            ORDER BY time ASC
            """,
            (zone_keys, start_time, end_time),
        )
        rows = cursor.fetchall()
        cursor.close()

        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No carbon intensity data found for forecast range",
            )

        generation_by_time: Dict[datetime, Dict[str, float]] = defaultdict(dict)
        for ts, psr_type, mw in rows:
            generation_by_time[ts][psr_type] = generation_by_time[ts].get(psr_type, 0) + float(
                mw or 0
            )

        responses: List[CarbonIntensityResponse] = []
        for ts, mix in generation_by_time.items():
            total_generation = sum(mix.values())
            if total_generation <= 0:
                continue
            co2_intensity = service._calculate_intensity(mix, total_generation)
            renewable_pct = service._get_renewable_pct(mix, total_generation)
            responses.append(
                CarbonIntensityResponse(
                    timestamp=ts,
                    zone=query.zone,
                    co2_intensity=round(co2_intensity, 2),
                    status=_status_from_intensity(co2_intensity),
                    renewable_pct=round(renewable_pct, 2),
                    fossil_pct=round(100 - renewable_pct, 2),
                    total_generation_mw=round(total_generation, 2),
                )
            )

        if not responses:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No usable carbon intensity data found",
            )

        return responses
    finally:
        conn.close()
