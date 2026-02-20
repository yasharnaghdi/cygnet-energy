from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

SUPPORTED_WEIGHT_KEYS = ("price", "renewable_share", "margin", "carbon")

WEIGHT_LABELS = {
    "price": "Price",
    "renewable_share": "Renewable Share",
    "margin": "Reserve Margin",
    "carbon": "Carbon Intensity",
}

SCENARIO_DEFAULT_WEIGHTS: dict[str, dict[str, float]] = {
    "base case": {"price": 0.4, "renewable_share": 0.2, "margin": 0.2, "carbon": 0.2},
    "high renewable": {"renewable_share": 0.5, "carbon": 0.3, "price": 0.1, "margin": 0.1},
    "grid stress": {"margin": 0.5, "price": 0.3, "renewable_share": 0.1, "carbon": 0.1},
    "custom": {"price": 0.25, "renewable_share": 0.25, "margin": 0.25, "carbon": 0.25},
}

SCENARIO_LABELS = {
    "base": "Base Case",
    "base case": "Base Case",
    "high renewable": "High Renewable",
    "grid stress": "Grid Stress",
    "custom": "Custom",
}

PERSONA_CONTEXT = {
    "trader": (
        "power trader",
        (
            "Write exactly 3 concise paragraphs: (1) current market setup, "
            "(2) risk windows, (3) hedging or positioning actions."
        ),
    ),
    "operator": (
        "grid operator",
        (
            "Write exactly 3 concise paragraphs: (1) system status, "
            "(2) near-term reliability risks, (3) operational mitigations."
        ),
    ),
    "policymaker": (
        "policy analyst",
        (
            "Write exactly 3 concise paragraphs: (1) current system performance, "
            "(2) structural risks, (3) concrete policy and investment actions."
        ),
    ),
    "ev_owner": (
        "electric-vehicle owner",
        (
            "Write exactly 3 concise paragraphs: (1) current conditions, "
            "(2) low-cost/low-carbon charging windows, (3) practical charging plan."
        ),
    ),
}


def _scenario_key(value: str | None) -> str:
    if not value:
        return "base case"
    key = value.strip().lower()
    if key in SCENARIO_DEFAULT_WEIGHTS:
        return key
    if key in SCENARIO_LABELS:
        return key
    return "base case"


def normalize_scenario_name(scenario: str | None) -> str:
    key = _scenario_key(scenario)
    return SCENARIO_LABELS.get(key, "Base Case")


def default_weights_for_scenario(scenario: str | None) -> dict[str, float]:
    key = _scenario_key(scenario)
    defaults = SCENARIO_DEFAULT_WEIGHTS.get(key, SCENARIO_DEFAULT_WEIGHTS["base case"])
    return dict(defaults)


def resolve_parameter_weights(
    scenario: str | None,
    parameter_weights: Mapping[str, float] | None,
) -> dict[str, float]:
    if not parameter_weights:
        return default_weights_for_scenario(scenario)

    raw: dict[str, float] = {}
    for key in SUPPORTED_WEIGHT_KEYS:
        value = parameter_weights.get(key, 0.0)
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = 0.0
        raw[key] = max(0.0, numeric)

    total = sum(raw.values())
    if total <= 0:
        return default_weights_for_scenario(scenario)

    return {key: raw[key] / total for key in SUPPORTED_WEIGHT_KEYS}


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _resolve_period_label(date_range: Sequence[str] | None) -> str:
    if not date_range:
        return "Recent operating window"
    if len(date_range) == 1:
        return str(date_range[0])
    return f"{date_range[0]} to {date_range[1]}"


def _summarize_context_mapping(value: Any) -> str:
    if not isinstance(value, Mapping) or not value:
        return "Not analyzed yet"
    parts: list[str] = []
    for key, raw in value.items():
        if isinstance(raw, Mapping):
            if "zone" in raw:
                parts.append(f"{key}={raw.get('zone')}")
            elif "state" in raw:
                parts.append(f"{key}={raw.get('state')}")
            elif "rows" in raw:
                parts.append(f"{key} rows={raw.get('rows')}")
            continue
        if isinstance(raw, list):
            if raw:
                parts.append(f"{key}={','.join(str(item) for item in raw[:3])}")
            continue
        if raw in (None, "", {}):
            continue
        parts.append(f"{key}={raw}")
    if not parts:
        return "Not analyzed yet"
    return "; ".join(parts[:6])


def build_weighted_prompt(
    data: Mapping[str, Any],
    persona: str,
    scenario: str,
    date_range: Sequence[str] | None,
    weights: Mapping[str, float],
    session_context: Mapping[str, Any] | None = None,
) -> str:
    persona_role, persona_task = PERSONA_CONTEXT.get(
        persona,
        (
            "energy analyst",
            "Write exactly 3 concise paragraphs with findings, risks, and actions.",
        ),
    )

    sorted_weights = sorted(
        [(key, float(weights.get(key, 0.0))) for key in SUPPORTED_WEIGHT_KEYS],
        key=lambda item: item[1],
        reverse=True,
    )
    primary_focus = sorted_weights[0][0]
    secondary_focus = sorted_weights[1][0] if len(sorted_weights) > 1 else sorted_weights[0][0]
    priority_lines = "\n".join(
        f"- {WEIGHT_LABELS.get(key, key)}: {value:.0%} importance" for key, value in sorted_weights
    )
    session_context = session_context or {}
    visited_tabs = session_context.get("visited_tabs") or data.get("visited_tabs") or []
    if isinstance(visited_tabs, Sequence) and not isinstance(visited_tabs, str):
        visited_tabs_label = ", ".join(str(item) for item in visited_tabs) if visited_tabs else "None"
    else:
        visited_tabs_label = str(visited_tabs)
    generated_charts = session_context.get("generated_charts") or data.get("generated_charts") or []
    if isinstance(generated_charts, Sequence) and not isinstance(generated_charts, str):
        generated_charts_label = ", ".join(str(item) for item in generated_charts) if generated_charts else "None"
    else:
        generated_charts_label = str(generated_charts)

    generation_context = data.get("generation_context") or session_context.get("generation_params")
    load_context = data.get("load_context") or session_context.get("load_params")
    carbon_context = data.get("carbon_context") or session_context.get("carbon_params")
    price_context = data.get("price_context") or session_context.get("price_params")

    return (
        f"You are an energy market analyst supporting a {persona_role}.\n\n"
        f"Scenario: {scenario}\n"
        f"Analysis period: {_resolve_period_label(date_range)}\n\n"
        f"ANALYSIS PRIORITIES (attention weights):\n"
        f"{priority_lines}\n\n"
        f"PRIMARY FOCUS: {WEIGHT_LABELS.get(primary_focus, primary_focus)}\n"
        f"SECONDARY FOCUS: {WEIGHT_LABELS.get(secondary_focus, secondary_focus)}\n\n"
        "Market Data:\n"
        f"- Zone: {data.get('zone', 'n/a')}\n"
        f"- Renewable Share: {_to_float(data.get('renewable_pct')):.1f}%\n"
        f"- Average Price: EUR {_to_float(data.get('price_eur_mwh')):.2f}/MWh\n"
        f"- Reserve Margin: {_to_float(data.get('margin_mw')):.0f} MW\n"
        f"- Carbon Intensity: {_to_float(data.get('avg_carbon_g_per_kwh')):.0f} gCO2/kWh\n"
        f"- Tight Hours (7d): {_to_float(data.get('tight_hours_count_7d')):.0f}\n"
        f"- Peak Load: {_to_float(data.get('peak_load_mw')):.0f} MW\n\n"
        "Session Context Across Dashboard Tabs:\n"
        f"- Tabs visited: {visited_tabs_label}\n"
        f"- Charts generated: {generated_charts_label}\n"
        f"- Generation context: {_summarize_context_mapping(generation_context)}\n"
        f"- Load context: {_summarize_context_mapping(load_context)}\n"
        f"- Carbon context: {_summarize_context_mapping(carbon_context)}\n"
        f"- Price context: {_summarize_context_mapping(price_context)}\n\n"
        "Instructions:\n"
        f"- {persona_task}\n"
        "- Distribute attention proportionally to the listed weights.\n"
        "- Focus first on the primary focus, then secondary focus, and mention other factors briefly.\n"
        "- Keep the analysis operational, concrete, and numerically grounded.\n"
        "- Reference insights from visited tabs when available."
    )
