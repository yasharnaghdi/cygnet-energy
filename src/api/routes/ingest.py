from __future__ import annotations

import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from src.api.middleware.auth import verify_token
from src.api.models.schemas import TokenData
from src.api.client import EntsoEAPIClient
from src.db.session import get_db_engine
from src.services.ingestion import EntsoEIngestionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ingest", tags=["ingest"])


class IngestGenerationRequest(BaseModel):
    zone: str = Field(min_length=2, max_length=20)
    start: datetime
    end: datetime
    overwrite: bool = False


class IngestGenerationResponse(BaseModel):
    status: str
    zone: str
    rows_inserted: int
    rows_skipped: int
    start: str
    end: str
    errors: list[str] = Field(default_factory=list)


def _delete_existing_rows(zone: str, start: datetime, end: datetime) -> None:
    engine = get_db_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DELETE FROM generation_records
                WHERE zone = :zone
                  AND timestamp >= :start
                  AND timestamp <= :end
                """
            ),
            {"zone": zone, "start": start, "end": end},
        )
        conn.execute(
            text(
                """
                DELETE FROM load_records
                WHERE zone = :zone
                  AND timestamp >= :start
                  AND timestamp <= :end
                """
            ),
            {"zone": zone, "start": start, "end": end},
        )


@router.post("/generation", response_model=IngestGenerationResponse)
async def ingest_generation(
    payload: IngestGenerationRequest,
    token: TokenData = Depends(verify_token),
) -> IngestGenerationResponse:
    del token
    configured_token = (
        os.getenv("ENTSO_E_API_TOKEN")
        or os.getenv("ENTSOE_API_TOKEN")
        or os.getenv("API_TOKEN")
    )
    if not configured_token:
        raise HTTPException(status_code=500, detail="ENTSO_E_API_TOKEN not set")

    zone = payload.zone.strip().upper()
    supported_zones = sorted(EntsoEAPIClient.BIDDING_ZONES)
    if zone not in EntsoEAPIClient.BIDDING_ZONES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown zone '{zone}'. Supported: {supported_zones}",
        )

    if payload.end <= payload.start:
        raise HTTPException(status_code=400, detail="end must be greater than start")

    if payload.overwrite:
        _delete_existing_rows(zone, payload.start, payload.end)

    service = EntsoEIngestionService()
    try:
        result = service.fetch_and_store(zone=zone, start=payload.start, end=payload.end)
    except Exception as exc:
        logger.exception("Failed ENTSO-E ingestion for zone %s", zone)
        raise HTTPException(status_code=502, detail=f"Ingestion failed: {exc}") from exc

    rows_inserted = int(result.get("generation_records", 0))
    errors: list[str] = []
    if rows_inserted <= 0:
        errors.append("ENTSO-E returned 0 generation rows for requested window")

    return IngestGenerationResponse(
        status="ok" if rows_inserted > 0 else "no_data",
        zone=zone,
        rows_inserted=rows_inserted,
        rows_skipped=0,
        start=payload.start.isoformat(),
        end=payload.end.isoformat(),
        errors=errors,
    )


@router.get("/status")
async def ingest_status(token: TokenData = Depends(verify_token)) -> dict[str, object]:
    del token
    engine = get_db_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT zone, COUNT(*) AS rows, MAX(timestamp) AS latest
                    FROM generation_records
                    GROUP BY zone
                    ORDER BY zone
                    """
                )
            )
            zones = [
                {
                    "zone": str(row.zone),
                    "rows": int(row.rows or 0),
                    "latest": row.latest.isoformat() if row.latest is not None else None,
                }
                for row in result
            ]
    except Exception as exc:
        logger.warning("Failed to read ingest status: %s", exc)
        zones = []
    return {"zones": zones}
