from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from statistics import mean, pstdev
from time import perf_counter
from typing import Any

import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.middleware.auth_dev import auth_bypass_enabled
from src.api.middleware.auth import verify_token
from src.api.models.schemas import TokenData
from src.db.connection import get_connection, get_db_session
from src.db.models import ReportHistory, ReportSession
from src.services.llm_client import BackendType, LLMBackend, get_llm
from src.services.report_storage import save_report_to_s3
from src.services.report_templates import get_prompt as get_context_prompt
from src.services.report_generator import (
    build_weighted_prompt,
    normalize_scenario_name,
    resolve_parameter_weights,
)
from src.utils.zones import get_zone_keys

router = APIRouter(prefix="/api/reports", tags=["Reports"])
logger = logging.getLogger(__name__)

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
    report_id: str | None = None
    session_id: str | None = None


class ReportRequest(BaseModel):
    persona: str = Field(min_length=2, max_length=64)
    zone: str = Field(default="DE", pattern="^[A-Z0-9]{2,20}$")
    date_range: list[str] = Field(default_factory=list, max_length=2)
    scenario: str = Field(default="Base Case", min_length=1, max_length=64)
    parameter_weights: dict[str, float] | None = None
    session_context: dict[str, Any] | None = None
    backend: BackendType | None = None
    model: str | None = Field(default=None, min_length=1, max_length=128)
    current_soc: int = Field(default=35, ge=5, le=95)
    tight_margin_mw: int = Field(default=1500, ge=100, le=10000)
    session_id: str | None = Field(default=None, min_length=1, max_length=64)
    save_history: bool = True


class ReportHistoryItem(BaseModel):
    report_id: str
    session_id: str
    generated_at: datetime
    persona: str
    zone: str
    scenario: str | None
    backend: str
    model: str | None
    is_favorite: bool
    tags: list[str] | None


class ReportHistoryListResponse(BaseModel):
    reports: list[ReportHistoryItem]
    total: int
    limit: int
    offset: int


class ReportHistoryDetailResponse(BaseModel):
    report_id: str
    session_id: str
    generated_at: datetime
    persona: str
    zone: str
    scenario: str | None
    date_range_start: date | None
    date_range_end: date | None
    parameter_weights: dict[str, float] | None
    narrative: str
    data_summary: dict[str, Any]
    backend: str
    model: str | None
    generation_time_ms: float | None
    tags: list[str] | None
    notes: str | None
    is_favorite: bool


class ReportHistoryUpdateRequest(BaseModel):
    tags: list[str] | None = None
    notes: str | None = None
    is_favorite: bool | None = None


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


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _resolve_model_name(backend: str, backend_info: dict[str, Any], requested_model: str | None) -> str | None:
    if requested_model:
        return requested_model
    if backend == LLMBackend.OPENAI.value:
        return backend_info.get("openai_model")
    if backend == LLMBackend.OLLAMA.value:
        return backend_info.get("ollama_model")
    if backend == LLMBackend.HUGGINGFACE.value:
        return backend_info.get("hf_model")
    return None


def _apply_history_scope(query: Any, token: TokenData) -> Any:
    if auth_bypass_enabled():
        return query
    return query.join(ReportSession, ReportHistory.session_id == ReportSession.session_id).filter(
        ReportSession.user_id == token.sub
    )


def _context_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _context_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _resolve_generation_context(context: dict[str, Any]) -> dict[str, Any]:
    generation_ctx = _context_dict(context.get("generation_context"))
    if generation_ctx:
        return generation_ctx
    return _context_dict(context.get("generation_params"))


def _normalize_date_range(value: Any) -> list[str]:
    return [str(item) for item in _context_list(value) if str(item).strip()][:2]


def _default_date_range() -> list[str]:
    today = datetime.now(timezone.utc).date()
    return [(today - timedelta(days=30)).isoformat(), today.isoformat()]


def _resolve_zone_and_dates(session_context: dict[str, Any]) -> tuple[str, list[str]]:
    """
    Priority (highest first):
    1. generation_context.zone / generation_context.date_range
    2. session_context.zone / session_context.date_range
    3. ai_insights_params.zone / ai_insights_params.date_range
    4. Hardcoded fallback: DE / last 30 days
    """
    generation_ctx = _resolve_generation_context(session_context)
    ai_ctx = _context_dict(session_context.get("ai_insights_params"))

    zone = str(
        generation_ctx.get("zone")
        or session_context.get("zone")
        or ai_ctx.get("zone")
        or "DE"
    ).strip().upper()

    date_range = (
        _normalize_date_range(generation_ctx.get("date_range"))
        or _normalize_date_range(session_context.get("date_range"))
        or _normalize_date_range(ai_ctx.get("date_range"))
        or _default_date_range()
    )
    return zone, date_range


def _extract_request_context(request: ReportRequest) -> dict[str, Any]:
    ctx = _context_dict(request.session_context)
    resolved_zone, resolved_date_range = _resolve_zone_and_dates(ctx)
    generation_ctx = _resolve_generation_context(ctx)
    ai_ctx = _context_dict(ctx.get("ai_insights_params"))
    scenario = str(ctx.get("scenario") or request.scenario or "Base Case")
    request_date_range = _normalize_date_range(request.date_range)
    has_ctx_zone = bool(generation_ctx.get("zone") or ctx.get("zone") or ai_ctx.get("zone"))
    has_ctx_date = bool(
        _normalize_date_range(generation_ctx.get("date_range"))
        or _normalize_date_range(ctx.get("date_range"))
        or _normalize_date_range(ai_ctx.get("date_range"))
    )
    if ctx:
        zone = resolved_zone if has_ctx_zone else str(request.zone or resolved_zone or "DE").strip().upper()
        date_range = resolved_date_range if has_ctx_date else (request_date_range or resolved_date_range)
    else:
        zone = str(request.zone or resolved_zone or "DE").strip().upper()
        date_range = request_date_range or resolved_date_range or _default_date_range()

    weights = _context_dict(ctx.get("parameter_weights")) or request.parameter_weights

    return {
        "zone": zone,
        "scenario": scenario,
        "date_range": date_range,
        "parameter_weights": weights,
        "session_context": ctx,
    }


def _summarize_context(context: dict[str, Any]) -> dict[str, Any]:
    generation_ctx = _resolve_generation_context(context)
    load_ctx = _context_dict(context.get("load_params"))
    carbon_ctx = _context_dict(context.get("carbon_params"))
    price_ctx = _context_dict(context.get("price_params"))
    visited_tabs = [str(item) for item in _context_list(context.get("visited_tabs")) if str(item).strip()]
    generated_charts = [str(item) for item in _context_list(context.get("generated_charts")) if str(item).strip()]

    return {
        "session_id": context.get("session_id"),
        "session_started_at": context.get("started_at"),
        "session_updated_at": context.get("updated_at"),
        "visited_tabs": visited_tabs,
        "generated_charts": generated_charts,
        "generation_context": generation_ctx,
        "load_context": load_ctx,
        "carbon_context": carbon_ctx,
        "price_context": price_ctx,
    }


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


def _apply_generation_context_overrides(data_summary: dict[str, Any], context: dict[str, Any]) -> None:
    generation_ctx = _resolve_generation_context(context)
    if not generation_ctx:
        return

    generation_zone = str(generation_ctx.get("zone") or "").strip().upper()
    if generation_zone:
        data_summary["zone"] = generation_zone

    generation_period = _normalize_date_range(generation_ctx.get("date_range"))
    if generation_period:
        data_summary["analysis_period"] = generation_period

    renewable_pct = _to_float(generation_ctx.get("renewable_pct"), default=0.0)
    if renewable_pct > 0:
        renewable_pct = _safe_round(renewable_pct, 1)
        data_summary["renewable_pct"] = renewable_pct
        data_summary["current_renewable_pct"] = renewable_pct
        data_summary["avg_renewable_pct"] = renewable_pct

    total_generation = _to_float(generation_ctx.get("total_generation_mwh"), default=0.0)
    if total_generation > 0:
        data_summary["total_generation_mwh"] = _safe_round(total_generation, 2)


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
    model: str | None,
    session_context: dict[str, Any] | None = None,
) -> ReportResponse:
    started = perf_counter()
    context_for_prompt = _context_dict(session_context)
    resolved_zone, resolved_date_range = _resolve_zone_and_dates(context_for_prompt)
    normalized_persona = _normalize_persona(persona)
    normalized_zone = (zone or "DE").strip().upper()
    if context_for_prompt:
        normalized_zone = resolved_zone
    normalized_scenario = normalize_scenario_name(scenario)
    resolved_weights = resolve_parameter_weights(normalized_scenario, parameter_weights)
    clean_date_range = _normalize_date_range(date_range)
    if context_for_prompt:
        clean_date_range = _normalize_date_range(resolved_date_range) or clean_date_range
    if not clean_date_range:
        clean_date_range = _default_date_range()

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
    data_summary.update(_summarize_context(context_for_prompt))
    if clean_date_range:
        data_summary["analysis_period"] = clean_date_range
    _apply_generation_context_overrides(data_summary, context_for_prompt)
    if context_for_prompt:
        try:
            prompt = get_context_prompt(normalized_persona, data_summary)
        except Exception:
            prompt = build_weighted_prompt(
                data=data_summary,
                persona=normalized_persona,
                scenario=normalized_scenario,
                date_range=clean_date_range,
                weights=resolved_weights,
                session_context=context_for_prompt,
            )
    else:
        prompt = build_weighted_prompt(
            data=data_summary,
            persona=normalized_persona,
            scenario=normalized_scenario,
            date_range=clean_date_range,
            weights=resolved_weights,
            session_context=context_for_prompt,
        )

    llm = get_llm()
    llm.refresh_backend()
    narrative = llm.generate(
        prompt,
        temperature=0.7,
        max_tokens=800,
        force_backend=backend,
        force_model=model,
    )
    backend_info = llm.get_backend_info()
    selected_backend = backend if backend is not None else str(
        backend_info.get("active_backend") or backend_info.get("backend", LLMBackend.FALLBACK.value)
    )
    backend_info["backend"] = selected_backend
    if model:
        backend_info["requested_model"] = model
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


def _save_report_history(request: ReportRequest, response: ReportResponse, token: TokenData) -> tuple[str, str]:
    db: Session = get_db_session()
    try:
        context = _context_dict(request.session_context)
        context_session_id = str(context.get("session_id", "")).strip()
        session_id = (request.session_id or "").strip() or context_session_id or str(uuid.uuid4())
        session = db.query(ReportSession).filter(ReportSession.session_id == session_id).first()

        if session is None:
            session = ReportSession(session_id=session_id, user_id=token.sub)
            db.add(session)
            db.flush()
        elif not auth_bypass_enabled() and session.user_id and session.user_id != token.sub:
            raise HTTPException(status_code=403, detail="Session does not belong to current user")

        if not session.user_id:
            session.user_id = token.sub
        session.updated_at = datetime.now(timezone.utc)

        start_date = _parse_date(response.date_range[0]) if len(response.date_range) >= 1 else None
        end_date = _parse_date(response.date_range[1]) if len(response.date_range) >= 2 else None
        model_name = _resolve_model_name(response.backend, response.backend_info, request.model)
        report_id = str(uuid.uuid4())

        record = ReportHistory(
            session_id=session_id,
            report_id=report_id,
            persona=response.persona,
            zone=str(response.data_summary.get("zone", request.zone)).strip().upper(),
            scenario=response.scenario,
            date_range_start=start_date,
            date_range_end=end_date,
            parameter_weights=response.parameter_weights,
            backend=response.backend,
            model=model_name,
            generation_time_ms=response.generation_time_ms,
            narrative=response.narrative,
            data_summary=response.data_summary,
        )
        db.add(record)
        db.commit()
        return report_id, session_id
    except HTTPException:
        db.rollback()
        raise
    finally:
        db.close()


def _save_report_s3_backup(report_id: str, request: ReportRequest, response: ReportResponse, token: TokenData) -> None:
    report_data = {
        "report_id": report_id,
        "session_id": response.session_id,
        "narrative": response.narrative,
        "data_summary": response.data_summary,
        "persona": request.persona,
        "generated_at": response.generated_at.isoformat(),
    }
    s3_url = save_report_to_s3(report_id, report_data)
    if not s3_url or not hasattr(ReportHistory, "s3_url"):
        return

    db: Session = get_db_session()
    try:
        query = db.query(ReportHistory)
        query = _apply_history_scope(query, token)
        row = query.filter(ReportHistory.report_id == report_id).first()
        if row is None:
            return

        row.s3_url = s3_url
        db.commit()
    except Exception as exc:  # pragma: no cover - optional persistence metadata
        db.rollback()
        logger.warning("Failed to persist report s3_url metadata: %s", exc)
    finally:
        db.close()


@router.post("/generate", response_model=ReportResponse)
async def generate_report(request: ReportRequest, token: TokenData = Depends(verify_token)) -> ReportResponse:
    try:
        context_inputs = _extract_request_context(request)
        response = _generate_report_impl(
            persona=request.persona,
            zone=context_inputs["zone"],
            current_soc=request.current_soc,
            tight_margin_mw=request.tight_margin_mw,
            scenario=context_inputs["scenario"],
            date_range=context_inputs["date_range"],
            parameter_weights=context_inputs["parameter_weights"],
            backend=request.backend,
            model=request.model,
            session_context=context_inputs["session_context"],
        )

        if request.save_history:
            try:
                report_id, session_id = _save_report_history(request, response, token)
                response = response.model_copy(update={"report_id": report_id, "session_id": session_id})
                _save_report_s3_backup(report_id, request, response, token)
            except Exception as exc:  # pragma: no cover - defensive persistence fallback
                logger.warning("Failed to save report history: %s", exc)
                response.backend_info["history_warning"] = str(exc)

        return response
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/history", response_model=ReportHistoryListResponse)
async def list_report_history(
    session_id: str | None = Query(default=None),
    persona: str | None = Query(default=None),
    zone: str | None = Query(default=None),
    scenario: str | None = Query(default=None),
    is_favorite: bool | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    token: TokenData = Depends(verify_token),
) -> ReportHistoryListResponse:
    db: Session = get_db_session()
    try:
        query = db.query(ReportHistory)
        query = _apply_history_scope(query, token)

        if session_id:
            query = query.filter(ReportHistory.session_id == session_id)
        if persona:
            try:
                normalized_persona = _normalize_persona(persona)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            query = query.filter(ReportHistory.persona == normalized_persona)
        if zone:
            query = query.filter(ReportHistory.zone == zone.strip().upper())
        if scenario:
            query = query.filter(ReportHistory.scenario == normalize_scenario_name(scenario))
        if is_favorite is not None:
            query = query.filter(ReportHistory.is_favorite == is_favorite)

        total = query.count()
        rows = query.order_by(ReportHistory.generated_at.desc()).offset(offset).limit(limit).all()

        items = [
            ReportHistoryItem(
                report_id=row.report_id,
                session_id=row.session_id,
                generated_at=row.generated_at,
                persona=row.persona,
                zone=row.zone,
                scenario=row.scenario,
                backend=row.backend,
                model=row.model,
                is_favorite=row.is_favorite,
                tags=row.tags,
            )
            for row in rows
        ]
        return ReportHistoryListResponse(reports=items, total=total, limit=limit, offset=offset)
    finally:
        db.close()


@router.get("/history/{report_id}", response_model=ReportHistoryDetailResponse)
async def get_report_history_item(
    report_id: str,
    token: TokenData = Depends(verify_token),
) -> ReportHistoryDetailResponse:
    db: Session = get_db_session()
    try:
        query = db.query(ReportHistory)
        query = _apply_history_scope(query, token)
        row = query.filter(ReportHistory.report_id == report_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Report not found")

        weights = None
        if isinstance(row.parameter_weights, dict):
            weights = {str(key): float(value) for key, value in row.parameter_weights.items()}

        return ReportHistoryDetailResponse(
            report_id=row.report_id,
            session_id=row.session_id,
            generated_at=row.generated_at,
            persona=row.persona,
            zone=row.zone,
            scenario=row.scenario,
            date_range_start=row.date_range_start,
            date_range_end=row.date_range_end,
            parameter_weights=weights,
            narrative=row.narrative,
            data_summary=row.data_summary or {},
            backend=row.backend,
            model=row.model,
            generation_time_ms=row.generation_time_ms,
            tags=row.tags,
            notes=row.notes,
            is_favorite=row.is_favorite,
        )
    finally:
        db.close()


@router.patch("/history/{report_id}")
async def update_report_history_item(
    report_id: str,
    request: ReportHistoryUpdateRequest,
    token: TokenData = Depends(verify_token),
) -> dict[str, str]:
    if request.tags is None and request.notes is None and request.is_favorite is None:
        raise HTTPException(status_code=400, detail="Provide at least one field to update")

    db: Session = get_db_session()
    try:
        query = db.query(ReportHistory)
        query = _apply_history_scope(query, token)
        row = query.filter(ReportHistory.report_id == report_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Report not found")

        if request.tags is not None:
            row.tags = request.tags
        if request.notes is not None:
            row.notes = request.notes
        if request.is_favorite is not None:
            row.is_favorite = request.is_favorite

        db.commit()
        return {"status": "updated"}
    finally:
        db.close()


@router.delete("/history/{report_id}")
async def delete_report_history_item(
    report_id: str,
    token: TokenData = Depends(verify_token),
) -> dict[str, str]:
    db: Session = get_db_session()
    try:
        query = db.query(ReportHistory)
        query = _apply_history_scope(query, token)
        row = query.filter(ReportHistory.report_id == report_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Report not found")

        db.delete(row)
        db.commit()
        return {"status": "deleted"}
    finally:
        db.close()


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
            model=None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
