from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src.db.constants import SEED_TENANT_ID


class CountryCode(str, Enum):
    DE = "DE"
    FR = "FR"
    GB = "GB"
    ES = "ES"
    IT = "IT"


class RegionSource(str, Enum):
    entsoe = "entsoe"
    eia = "eia"


class CarbonIntensityQuery(BaseModel):
    zone: CountryCode = Field(default=CountryCode.DE)
    threshold: int = Field(default=200, ge=1, le=2000)


class CarbonIntensityForecastQuery(CarbonIntensityQuery):
    hours: int = Field(default=24, ge=1, le=168)


class CarbonIntensityResponse(BaseModel):
    timestamp: datetime
    zone: CountryCode
    co2_intensity: float
    status: str
    renewable_pct: float
    fossil_pct: float
    total_generation_mw: float

    model_config = {
        "json_schema_extra": {
            "example": {
                "timestamp": "2024-01-01T12:00:00Z",
                "zone": "DE",
                "co2_intensity": 185.4,
                "status": "YELLOW",
                "renewable_pct": 48.2,
                "fossil_pct": 51.8,
                "total_generation_mw": 52340.5,
            }
        }
    }


class EVOptimizationRequest(BaseModel):
    zone: CountryCode
    num_vehicles: int = Field(ge=1, le=100_000)
    daily_mwh_per_vehicle: float = Field(gt=0, le=5)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self) -> "EVOptimizationRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class EVOptimizationResult(BaseModel):
    zone: CountryCode
    num_vehicles: int
    period_days: int
    peak_hour_cost: float
    peak_hour_emissions: float
    optimized_cost: float
    optimized_emissions: float
    cost_savings: float
    emissions_reduction_pct: float
    cost_reduction_pct: float
    best_charging_window: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "zone": "FR",
                "num_vehicles": 1200,
                "period_days": 7,
                "peak_hour_cost": 175000.0,
                "peak_hour_emissions": 420.5,
                "optimized_cost": 52000.0,
                "optimized_emissions": 110.2,
                "cost_savings": 123000.0,
                "emissions_reduction_pct": 73.8,
                "cost_reduction_pct": 70.3,
                "best_charging_window": "Low-carbon off-peak hours",
            }
        }
    }


class GenerationMixQuery(BaseModel):
    zone: CountryCode = Field(default=CountryCode.DE)
    days: int = Field(default=1, ge=1, le=365)


class GenerationMixResponse(BaseModel):
    timestamp: datetime
    zone: CountryCode
    solar_mw: float
    wind_mw: float
    nuclear_mw: float
    coal_mw: float
    gas_mw: float
    hydro_mw: float
    biomass_mw: float
    total_mw: float
    renewable_pct: float

    model_config = {
        "json_schema_extra": {
            "example": {
                "timestamp": "2024-01-01T12:00:00Z",
                "zone": "DE",
                "solar_mw": 6500.0,
                "wind_mw": 14500.0,
                "nuclear_mw": 7800.0,
                "coal_mw": 4200.0,
                "gas_mw": 3100.0,
                "hydro_mw": 2500.0,
                "biomass_mw": 900.0,
                "total_mw": 39500.0,
                "renewable_pct": 61.3,
            }
        }
    }


class IndicatorQuery(BaseModel):
    zone: CountryCode = Field(default=CountryCode.DE)
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    limit: int = Field(default=48, ge=1, le=1000)


class IndicatorPackageResponse(BaseModel):
    timestamp_utc: datetime
    region_type: str
    region_id: str
    granularity: str
    carbon_intensity: float
    fossil_share: float
    volatility: Optional[float]
    clean_window: bool

    model_config = {
        "json_schema_extra": {
            "example": {
                "timestamp_utc": "2024-01-01T12:00:00Z",
                "region_type": "zone",
                "region_id": "DE",
                "granularity": "hour",
                "carbon_intensity": 185.4,
                "fossil_share": 42.8,
                "volatility": 12.5,
                "clean_window": True,
            }
        }
    }


class RegionResponse(BaseModel):
    region_id: str
    region_type: str
    source: RegionSource


class RegimeQuery(BaseModel):
    zone: CountryCode = Field(default=CountryCode.DE)
    date_range: int = Field(default=1, ge=1, le=90)


class RegimeResponse(BaseModel):
    timestamp: datetime
    zone: CountryCode
    regime: str
    confidence: float
    res_penetration: float
    load_tightness: float
    net_import: float

    model_config = {
        "json_schema_extra": {
            "example": {
                "timestamp": "2024-01-01T12:00:00Z",
                "zone": "GB",
                "regime": "NORMAL",
                "confidence": 0.72,
                "res_penetration": 45.8,
                "load_tightness": 0.12,
                "net_import": -1200.5,
            }
        }
    }


class TokenData(BaseModel):
    sub: str
    email: Optional[str] = None
    roles: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)
    issuer: Optional[str] = None
    audience: Optional[str] = None
    tenant_id: UUID = Field(default_factory=lambda: SEED_TENANT_ID)


class ErrorResponse(BaseModel):
    detail: str
    error_code: str
    timestamp: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "detail": "Invalid token",
                "error_code": "INVALID_TOKEN",
                "timestamp": "2024-01-01T12:00:00Z",
            }
        }
    }
