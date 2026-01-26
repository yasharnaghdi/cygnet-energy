from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from src.api.middleware.auth import verify_token
from src.api.middleware.rate_limit import limiter
from src.api.models.schemas import EVOptimizationRequest, EVOptimizationResult
from src.db.connection import get_connection
from src.services.carbon_service import CarbonIntensityService

router = APIRouter(
    prefix="/optimization",
    tags=["Optimization"],
    dependencies=[Depends(verify_token)],
)


@router.post("/ev", response_model=EVOptimizationResult)
@limiter.limit("100/hour")
def optimize_ev_charging(
    request: Request,
    payload: EVOptimizationRequest,
) -> EVOptimizationResult:
    conn = get_connection()
    try:
        service = CarbonIntensityService(conn)
        impact = service.calculate_charging_impact(
            num_evs=payload.num_vehicles,
            daily_charging_mwh=payload.daily_mwh_per_vehicle,
        )

        period_days = (payload.end_date - payload.start_date).days + 1

        scenario_peak = impact["scenario_peak"]
        scenario_green = impact["scenario_green"]
        monthly_savings = impact["monthly_savings"]

        return EVOptimizationResult(
            zone=payload.zone,
            num_vehicles=payload.num_vehicles,
            period_days=period_days,
            peak_hour_cost=float(scenario_peak["monthly_cost"]),
            peak_hour_emissions=float(scenario_peak["monthly_emissions_tons"]),
            optimized_cost=float(scenario_green["monthly_cost"]),
            optimized_emissions=float(scenario_green["monthly_emissions_tons"]),
            cost_savings=float(monthly_savings["cost"]),
            emissions_reduction_pct=float(monthly_savings["emissions_pct"]),
            cost_reduction_pct=float(monthly_savings["cost_pct"]),
            best_charging_window="Low-carbon off-peak hours",
        )
    finally:
        conn.close()
