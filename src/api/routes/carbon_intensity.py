from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.middleware.auth import verify_token
from src.api.models.schemas import CountryCode, TokenData
from src.db.connection import get_connection
from src.services.carbon_service import CarbonIntensityService

router = APIRouter(prefix="/api/carbon-intensity", tags=["Carbon Intensity"])


@router.get("/current")
async def current_intensity(
    zone: CountryCode = Query(default=CountryCode.DE),
    token: TokenData = Depends(verify_token),
) -> dict:
    del token
    conn = get_connection()
    try:
        service = CarbonIntensityService(conn)
        current = service.get_current_intensity(zone.value)
    finally:
        conn.close()

    if current is None:
        raise HTTPException(status_code=404, detail=f"No carbon intensity data available for zone {zone.value}")
    return current
