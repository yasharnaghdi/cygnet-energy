from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.middleware.auth import verify_token
from src.api.models.schemas import TokenData
from src.services.ingestion import EntsoEIngestionService

router = APIRouter(prefix="/api/ingest", tags=["Ingest"])


class IngestGenerationRequest(BaseModel):
    zone: str = Field(min_length=2, max_length=20)
    start: datetime
    end: datetime


@router.post("/generation")
async def ingest_generation(
    payload: IngestGenerationRequest,
    token: TokenData = Depends(verify_token),
) -> dict[str, object]:
    del token
    zone = payload.zone.strip().upper()
    if payload.end <= payload.start:
        raise HTTPException(status_code=400, detail="end must be greater than start")

    service = EntsoEIngestionService()
    result = service.fetch_and_store(zone=zone, start=payload.start, end=payload.end)
    return {
        "zone": zone,
        "rows_inserted": int(result.get("generation_records", 0)),
        "generation_records": int(result.get("generation_records", 0)),
        "load_records": int(result.get("load_records", 0)),
        "total_records": int(result.get("total_records", 0)),
        "freshest_timestamp": result.get("freshest_timestamp"),
    }
