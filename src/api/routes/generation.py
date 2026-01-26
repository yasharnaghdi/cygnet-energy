from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.api.middleware.auth import verify_token
from src.api.middleware.rate_limit import limiter
from src.api.models.schemas import GenerationMixQuery, GenerationMixResponse
from src.db.connection import get_connection
from src.utils.zones import get_zone_keys

router = APIRouter(
    prefix="/generation",
    tags=["Generation"],
    dependencies=[Depends(verify_token)],
)

PSR_MAPPING = {
    "solar": {"B18"},
    "wind": {"B19", "B20"},
    "biomass": {"B01"},
    "gas": {"B04"},
    "coal": {"B05"},
    "nuclear": {"B14"},
    "hydro": {"B16"},
}


@router.get("/mix", response_model=GenerationMixResponse)
@limiter.limit("100/hour")
def get_generation_mix(
    request: Request,
    query: GenerationMixQuery = Depends(),
) -> GenerationMixResponse:
    conn = get_connection()
    try:
        zone_keys = get_zone_keys(query.zone.value)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT psr_type, SUM(actual_generation_mw) AS total_mw
            FROM generation_actual
            WHERE bidding_zone_mrid = ANY(%s)
              AND time >= NOW() - (%s || ' days')::interval
            GROUP BY psr_type
            """,
            (zone_keys, query.days),
        )
        rows = cursor.fetchall()

        cursor.execute(
            """
            SELECT MAX(time)
            FROM generation_actual
            WHERE bidding_zone_mrid = ANY(%s)
              AND time >= NOW() - (%s || ' days')::interval
            """,
            (zone_keys, query.days),
        )
        latest_time = cursor.fetchone()[0]
        cursor.close()

        if not rows or latest_time is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No generation mix data found",
            )

        totals = {
            "solar": 0.0,
            "wind": 0.0,
            "biomass": 0.0,
            "gas": 0.0,
            "coal": 0.0,
            "nuclear": 0.0,
            "hydro": 0.0,
        }
        total_generation = 0.0

        for psr_type, total_mw in rows:
            total_generation += float(total_mw or 0)
            for key, psr_set in PSR_MAPPING.items():
                if psr_type in psr_set:
                    totals[key] += float(total_mw or 0)

        renewable_total = totals["solar"] + totals["wind"] + totals["hydro"] + totals["biomass"]
        renewable_pct = (renewable_total / total_generation * 100) if total_generation else 0.0

        return GenerationMixResponse(
            timestamp=latest_time,
            zone=query.zone,
            solar_mw=round(totals["solar"], 2),
            wind_mw=round(totals["wind"], 2),
            nuclear_mw=round(totals["nuclear"], 2),
            coal_mw=round(totals["coal"], 2),
            gas_mw=round(totals["gas"], 2),
            hydro_mw=round(totals["hydro"], 2),
            biomass_mw=round(totals["biomass"], 2),
            total_mw=round(total_generation, 2),
            renewable_pct=round(renewable_pct, 2),
        )
    finally:
        conn.close()
