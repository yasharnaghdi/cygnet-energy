from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean, pstdev
from time import perf_counter
from typing import Any

import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.middleware.auth import verify_token
from src.api.models.schemas import TokenData
from src.db.connection import get_connection
from src.services.llm_client import BackendType, LLMBackend, get_llm
from src.services.report_generator import (
    build_weighted_prompt,
    normalize_scenario_name,
    resolve_parameter_weights,
)
from src.utils.zones import get_zone_keys

router = APIRouter(prefix="/api/reports", tags=["Reports"])

FOSSIL_INTENSITY_G_PER_KWH = 490.0
SOLAR_INTENSITY_G_PER_KWH = 41.0
WIND_INTENSITY_G_PER_KWH = 11.0
HYDRO_INTENSITY_G_PER_KWH = 24.0


class ReportResponse(BaseModel):
    persona: str
    scenario: str
    date_range: list[str]
    parameter_weights: dict[str, float]
    generated_at: datetime
    narrative: str
    data_summary: dict[str, Any]
    backend: str
    backend_info: dict[str, Any]
    generation_time_ms: float
    llm_available: bool


class ReportRequest(BaseModel):
    persona: str = Field(min_length=2, max_length=64)
    zone: str = Field(default="DE", pattern="^[A-Z0-9]{2,20}$")
    date_range: list[str] = Field(default_factory=list, max_length=2)
    scenario: str = Field(default="Base Case", min_length=1, max_length=64)
    parameter_weights: dict[str, float] | None = None
    backend: BackendType | None = None
    current_soc: int = Field(default=35, ge=5, le=95)
    tight_margin_mw: int = Field(default=1500, ge=100, le=10000)


PERSONA_ALIASES = {
    "trader": "trader",
    "power_trader": "trader",
    "operator": "operator",
    "grid_operator": "operator",
    "policymaker": "policymaker",
    "policy_analyst": "policymaker",
    "ev_owner": "ev_owner",
}


def _normalize_persona(value: str) -> str:
    key = value.strip().lower().replace(" ", "_")
    persona = PERSONA_ALIASES.get(key)
    if persona is None:
        valid = ", ".join(sorted(PERSONA_ALIASES))
        raise ValueError(f"Unsupported persona '{value}'. Use one of: {valid}")
    return persona


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_round(value: Any, digits: int = 1, default: float = 0.0) -> float:
    return round(_to_float(value, default), digits)


def _fmt_ts(value: Any) -> str:
    if not isinstance(value, datetime):
        return "n/a"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%d %H:%M UTC")


def _format_hour_list(values: list[datetime], limit: int = 6) -> str:
    if not values:
        return "none"
    rendered = [_fmt_ts(item) for item in values[:limit]]
    if len(values) > limit:
        rendered.append("...")
    return ", ".join(rendered)


def _query_records_tables(cur: psycopg2.extensions.cursor, zone: str, hours: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT
            g.timestamp,
            g.wind_mw,
            g.solar_mw,
            g.hydro_mw,
            g.total_mw,
            l.load_mw,
            p.price_eur_mwh
        FROM generation_records g
        LEFT JOIN load_records l
            ON l.zone = g.zone AND l.timestamp = g.timestamp
        LEFT JOIN price_records p
            ON p.zone = g.zone AND p.timestamp = g.timestamp
        WHERE g.zone = %s
          AND g.timestamp >= NOW() - make_interval(hours => %s)
        ORDER BY g.timestamp ASC
        """,
        (zone, hours),
    )
    rows = cur.fetchall()
    return [dict(row) for row in rows]


def _query_legacy_tables(cur: psycopg2.extensions.cursor, zone: str, hours: int) -> list[dict[str, Any]]:
    zone_keys = get_zone_keys(zone)
    cur.execute(
        """
        WITH generation_hourly AS (
            SELECT
                time AS timestamp,
                SUM(CASE WHEN psr_type IN ('B19', 'B20') THEN actual_generation_mw ELSE 0 END) AS wind_mw,
                SUM(CASE WHEN psr_type IN ('B17', 'B18') THEN actual_generation_mw ELSE 0 END) AS solar_mw,
                SUM(CASE WHEN psr_type IN ('B10', 'B11', 'B12') THEN actual_generation_mw ELSE 0 END) AS hydro_mw,
                SUM(actual_generation_mw) AS total_mw
            FROM generation_actual
            WHERE bidding_zone_mrid = ANY(%s)
              AND time >= NOW() - make_interval(hours => %s)
            GROUP BY time
        ),
        load_hourly AS (
            SELECT
                time AS timestamp,
                SUM(load_consumption_mw) AS load_mw
            FROM load_actual
            WHERE bidding_zone_mrid = ANY(%s)
              AND time >= NOW() - make_interval(hours => %s)
            GROUP BY time
        )
        SELECT
            g.timestamp,
            g.wind_mw,
            g.solar_mw,
            g.hydro_mw,
            g.total_mw,
            l.load_mw,
            NULL::DOUBLE PRECISION AS price_eur_mwh
        FROM generation_hourly g
        LEFT JOIN load_hourly l ON l.timestamp = g.timestamp
        ORDER BY g.timestamp ASC
        """,
        (zone_keys, hours, zone_keys, hours),
    )
    rows = cur.fetchall()
    return [dict(row) for row in rows]


def _fetch_hourly_rows(cur: psycopg2.extensions.cursor, zone: str, hours: int) -> list[dict[str, Any]]:
    try:
        rows = _query_records_tables(cur, zone, hours)
        if rows:
            return rows
    except Exception:
        pass

    try:
        rows = _query_legacy_tables(cur, zone, hours)
        if rows:
            return rows
    except Exception:
        pass

    return []


def _estimate_carbon_intensity(row: dict[str, Any]) -> float:
    total = _to_float(row.get("total_mw"))
    if total <= 0:
        return 0.0
    wind = _to_float(row.get("wind_mw"))
    solar = _to_float(row.get("solar_mw"))
    hydro = _to_float(row.get("hydro_mw"))
    residual = max(0.0, total - wind - solar - hydro)
    weighted = (
        wind * WIND_INTENSITY_G_PER_KWH
        + solar * SOLAR_INTENSITY_G_PER_KWH
        + hydro * HYDRO_INTENSITY_G_PER_KWH
        + residual * FOSSIL_INTENSITY_G_PER_KWH
    )
    return weighted / total


def _build_summary(
    zone: str,
    rows_24h: list[dict[str, Any]],
    rows_7d: list[dict[str, Any]],
    current_soc: int,
    tight_margin_mw: int,
) -> dict[str, Any]:
    latest = rows_24h[-1] if rows_24h else (rows_7d[-1] if rows_7d else {})

    renewable_series: list[float] = []
    margins: list[float] = []
    loads: list[float] = []
    prices: list[float] = []
    carbon_series: list[float] = []
    tight_hours: list[datetime] = []
    green_hours: list[datetime] = []

    for row in rows_24h:
        total = _to_float(row.get("total_mw"))
        wind = _to_float(row.get("wind_mw"))
        solar = _to_float(row.get("solar_mw"))
        hydro = _to_float(row.get("hydro_mw"))
        load = _to_float(row.get("load_mw"), default=-1.0)
        price = row.get("price_eur_mwh")

        if total > 0:
            renewable_pct = ((wind + solar + hydro) / total) * 100.0
            renewable_series.append(renewable_pct)
            carbon_series.append(_estimate_carbon_intensity(row))
            if renewable_pct >= 60:
                ts = row.get("timestamp")
                if isinstance(ts, datetime):
                    green_hours.append(ts)

        if load >= 0:
            margin = total - load
            margins.append(margin)
            loads.append(load)
            if margin < float(tight_margin_mw):
                ts = row.get("timestamp")
                if isinstance(ts, datetime):
                    tight_hours.append(ts)

        if price is not None:
            prices.append(_to_float(price))

    renewable_7d: list[float] = []
    loads_7d: list[tuple[datetime, float]] = []
    carbon_7d: list[float] = []
    tight_hours_7d: list[datetime] = []
    for row in rows_7d:
        total = _to_float(row.get("total_mw"))
        wind = _to_float(row.get("wind_mw"))
        solar = _to_float(row.get("solar_mw"))
        hydro = _to_float(row.get("hydro_mw"))
        load = _to_float(row.get("load_mw"), default=-1.0)
        ts = row.get("timestamp")

        if total > 0:
            renewable_7d.append(((wind + solar + hydro) / total) * 100.0)
            carbon_7d.append(_estimate_carbon_intensity(row))

        if load >= 0 and isinstance(ts, datetime):
            loads_7d.append((ts, load))
            if (total - load) < float(tight_margin_mw):
                tight_hours_7d.append(ts)

    cheap_hours = []
    if rows_24h:
        priced_rows = [row for row in rows_24h if row.get("price_eur_mwh") is not None]
        priced_rows = sorted(priced_rows, key=lambda row: _to_float(row.get("price_eur_mwh")))
        cheap_hours = [
            row.get("timestamp")
            for row in priced_rows[:3]
            if isinstance(row.get("timestamp"), datetime)
        ]

    latest_total = _to_float(latest.get("total_mw"))
    latest_wind = _to_float(latest.get("wind_mw"))
    latest_solar = _to_float(latest.get("solar_mw"))
    latest_hydro = _to_float(latest.get("hydro_mw"))
    current_renewable_pct = ((latest_wind + latest_solar + latest_hydro) / latest_total * 100.0) if latest_total > 0 else 0.0
    current_price = _to_float(latest.get("price_eur_mwh"), default=0.0)

    forecast_load_mw = mean(loads[-6:]) if len(loads) >= 2 else (loads[-1] if loads else 0.0)
    actual_load_mw = loads[-1] if loads else 0.0
    forecast_error_pct = (
        abs(actual_load_mw - forecast_load_mw) / forecast_load_mw * 100.0
        if forecast_load_mw > 0
        else 0.0
    )

    avg_cheap_price = mean([_to_float(row.get("price_eur_mwh")) for row in rows_24h if row.get("price_eur_mwh") is not None]) if prices else 0.0
    if cheap_hours and prices:
        cheap_price_values = sorted(prices)[: min(3, len(prices))]
        avg_cheap_price = mean(cheap_price_values)

    energy_needed_kwh = max(0.0, (80.0 - float(current_soc)) / 100.0 * 75.0)
    cost_now_eur = energy_needed_kwh * (current_price / 1000.0)
    cost_cheap_eur = energy_needed_kwh * (avg_cheap_price / 1000.0)
    savings_eur = max(0.0, cost_now_eur - cost_cheap_eur)

    peak_time = "n/a"
    peak_load_mw = 0.0
    if loads_7d:
        peak_ts, peak_load = max(loads_7d, key=lambda item: item[1])
        peak_time = _fmt_ts(peak_ts)
        peak_load_mw = peak_load

    return {
        "zone": zone,
        "report_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "renewable_pct": _safe_round(mean(renewable_series) if renewable_series else current_renewable_pct, 1),
        "price_eur_mwh": _safe_round(mean(prices), 2) if prices else _safe_round(current_price, 2),
        "tight_hours_count": len(tight_hours),
        "tight_hours_count_24h": len(tight_hours),
        "tight_hours_list": _format_hour_list(tight_hours),
        "wind_mw": _safe_round(latest_wind, 0),
        "solar_mw": _safe_round(latest_solar, 0),
        "margin_mw": _safe_round(mean(margins) if margins else 0.0, 0),
        "forecast_error_pct": _safe_round(forecast_error_pct, 1),
        "forecast_load_mw": _safe_round(forecast_load_mw, 0),
        "actual_load_mw": _safe_round(actual_load_mw, 0),
        "renewable_stddev": _safe_round(pstdev(renewable_series), 2) if len(renewable_series) >= 2 else 0.0,
        "green_hours_list": _format_hour_list(green_hours),
        "cheap_hours_list": _format_hour_list(cheap_hours),
        "avg_cheap_price": _safe_round(avg_cheap_price, 2),
        "current_renewable_pct": _safe_round(current_renewable_pct, 1),
        "current_soc": current_soc,
        "estimated_savings_eur": _safe_round(savings_eur, 2),
        "avg_renewable_pct": _safe_round(mean(renewable_7d), 1) if renewable_7d else 0.0,
        "peak_load_mw": _safe_round(peak_load_mw, 0),
        "peak_time": peak_time,
        "avg_carbon_g_per_kwh": (
            _safe_round(mean(carbon_7d), 0)
            if carbon_7d
            else (_safe_round(mean(carbon_series), 0) if carbon_series else 0.0)
        ),
        "tight_margin_threshold_mw": tight_margin_mw,
        "tight_hours_count_7d": len(tight_hours_7d),
    }


def _fallback_narrative(persona: str, summary: dict[str, Any], reason: str | None = None) -> str:
    prefix = "LLM unavailable. Showing deterministic summary."
    if reason:
        prefix = f"{prefix} {reason}"

    if persona == "trader":
        return (
            f"{prefix}\n\n"
            f"Market snapshot: renewable share is {summary['renewable_pct']}% and average price is "
            f"EUR {summary['price_eur_mwh']}/MWh.\n\n"
            f"Risk window: {summary['tight_hours_count']} tight hours were detected ({summary['tight_hours_list']}). "
            "Consider pre-positioning intraday hedges before tight periods.\n\n"
            "Action: keep storage optionality for tight intervals and reduce open short exposure during expected margin compression."
        )
    if persona == "operator":
        return (
            f"{prefix}\n\n"
            f"System status: average margin is {summary['margin_mw']} MW with renewable variability "
            f"at {summary['renewable_stddev']}%.\n\n"
            f"Risk: {summary['tight_hours_count']} hours are below the {summary['tight_margin_threshold_mw']} MW threshold "
            f"({summary['tight_hours_list']}).\n\n"
            "Mitigation actions:\n"
            "- Prepare demand response activation for tight windows.\n"
            "- Hold fast reserves for load forecast error protection.\n"
            "- Keep storage dispatch available for net margin support."
        )
    if persona == "ev_owner":
        return (
            f"{prefix}\n\n"
            f"Recommended charging windows: cheapest hours {summary['cheap_hours_list']}. "
            f"Green windows: {summary['green_hours_list']}.\n\n"
            f"Current renewable share is {summary['current_renewable_pct']}%. "
            f"Estimated savings versus charging now: EUR {summary['estimated_savings_eur']}."
        )
    return (
        f"{prefix}\n\n"
        f"Weekly snapshot: average renewable share {summary['avg_renewable_pct']}%, estimated carbon intensity "
        f"{summary['avg_carbon_g_per_kwh']} gCO2/kWh.\n\n"
        f"Peak load reached {summary['peak_load_mw']} MW at {summary['peak_time']}. "
        f"Tight hours in recent data: {summary['tight_hours_count_7d']}.\n\n"
        "Policy actions: accelerate storage procurement, strengthen transmission constraints, and target firm low-carbon capacity during recurring tight windows."
    )


@router.get("/backend-status")
async def backend_status(token: TokenData = Depends(verify_token)) -> dict[str, Any]:
    del token
    llm = get_llm()
    llm.refresh_backend()
    return llm.get_backend_info()


def _generate_report_impl(
    persona: str,
    zone: str,
    current_soc: int,
    tight_margin_mw: int,
    scenario: str,
    date_range: list[str] | None,
    parameter_weights: dict[str, float] | None,
    backend: BackendType | None,
) -> ReportResponse:
    started = perf_counter()
    normalized_persona = _normalize_persona(persona)
    normalized_zone = zone.strip().upper()
    normalized_scenario = normalize_scenario_name(scenario)
    resolved_weights = resolve_parameter_weights(normalized_scenario, parameter_weights)
    clean_date_range = [str(item) for item in (date_range or []) if str(item).strip()][:2]

    rows_24h: list[dict[str, Any]] = []
    rows_7d: list[dict[str, Any]] = []
    data_warning: str | None = None
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            rows_24h = _fetch_hourly_rows(cur, normalized_zone, hours=24)
            rows_7d = _fetch_hourly_rows(cur, normalized_zone, hours=24 * 7)
        finally:
            cur.close()
            conn.close()
    except Exception as exc:
        data_warning = f"Grid data unavailable: {exc}"

    data_summary = _build_summary(normalized_zone, rows_24h, rows_7d, current_soc, tight_margin_mw)
    if data_warning:
        data_summary["data_warning"] = data_warning[:240]
    data_summary["scenario"] = normalized_scenario
    data_summary["parameter_weights"] = resolved_weights
    if clean_date_range:
        data_summary["analysis_period"] = clean_date_range

    prompt = build_weighted_prompt(
        data=data_summary,
        persona=normalized_persona,
        scenario=normalized_scenario,
        date_range=clean_date_range,
        weights=resolved_weights,
    )

    llm = get_llm()
    llm.refresh_backend()
    narrative = llm.generate(prompt, temperature=0.7, max_tokens=800, force_backend=backend)
    backend_info = llm.get_backend_info()
    selected_backend = backend if backend is not None else str(
        backend_info.get("backend", LLMBackend.FALLBACK.value)
    )
    backend_info["backend"] = selected_backend
    llm_available = selected_backend != LLMBackend.FALLBACK.value

    if not llm_available and not narrative.strip():
        narrative = _fallback_narrative(normalized_persona, data_summary, reason="No LLM output generated.")

    generation_time_ms = round((perf_counter() - started) * 1000.0, 2)

    return ReportResponse(
        persona=normalized_persona,
        scenario=normalized_scenario,
        date_range=clean_date_range,
        parameter_weights=resolved_weights,
        generated_at=datetime.now(timezone.utc),
        narrative=narrative,
        data_summary=data_summary,
        backend=selected_backend,
        backend_info=backend_info,
        generation_time_ms=generation_time_ms,
        llm_available=llm_available,
    )


@router.post("/generate", response_model=ReportResponse)
async def generate_report(request: ReportRequest, token: TokenData = Depends(verify_token)) -> ReportResponse:
    del token
    try:
        return _generate_report_impl(
            persona=request.persona,
            zone=request.zone,
            current_soc=request.current_soc,
            tight_margin_mw=request.tight_margin_mw,
            scenario=request.scenario,
            date_range=request.date_range,
            parameter_weights=request.parameter_weights,
            backend=request.backend,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/generate", response_model=ReportResponse)
async def generate_report_legacy_get(
    persona: str = Query(..., pattern="^[a-zA-Z_ ]{2,64}$"),
    zone: str = Query(default="DE", pattern="^[A-Z0-9]{2,20}$"),
    current_soc: int = Query(default=35, ge=5, le=95),
    tight_margin_mw: int = Query(default=1500, ge=100, le=10000),
    token: TokenData = Depends(verify_token),
) -> ReportResponse:
    del token
    try:
        return _generate_report_impl(
            persona=persona,
            zone=zone,
            current_soc=current_soc,
            tight_margin_mw=tight_margin_mw,
            scenario="Base Case",
            date_range=[],
            parameter_weights=None,
            backend=None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
