"""Context-aware prompt templates for stakeholder-specific narratives."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


TRADER_USER_TEMPLATE = """Analyze this grid data for {zone}:

Grid status:
- Renewable share: {renewable_pct}%
- Reserve margin: {margin_mw} MW
- Carbon intensity: {avg_carbon_g_per_kwh} gCO2/kWh

Load context:
{load_context_summary}

Carbon context:
{carbon_context_summary}

Price context:
{price_context_summary}

User analysis session:
- Scenario: {scenario}
- Tabs explored: {visited_tabs}
- Date range: {date_range}
- Charts generated: {generated_charts}

Write 3 concise paragraphs:
1. Market conditions summary using all available context
2. Main risk windows in the next 24h
3. Recommended trading actions
"""


OPERATOR_TEMPLATE = """Assess the grid for {zone}:

- Scenario: {scenario}
- Date range: {date_range}
- Tabs explored: {visited_tabs}
- Renewable share: {renewable_pct}%
- Reserve margin: {margin_mw} MW
- Tight hours: {tight_hours_count_7d}

Generation context:
{generation_context_summary}

Load context:
{load_context_summary}

Write 3 concise paragraphs:
1. Current system status
2. Reliability risks using cross-tab context
3. Operational mitigations
"""


POLICY_TEMPLATE = """Prepare a policy brief for {zone}:

- Scenario: {scenario}
- Date range: {date_range}
- Tabs explored: {visited_tabs}
- Carbon intensity: {avg_carbon_g_per_kwh} gCO2/kWh
- Peak load: {peak_load_mw} MW

Generation context:
{generation_context_summary}

Carbon context:
{carbon_context_summary}

Price context:
{price_context_summary}

Write 3 concise paragraphs:
1. Current system performance
2. Structural risk and resilience gaps
3. Recommended policy and investment actions
"""


EV_TEMPLATE = """Advise an EV owner for {zone}:

- Scenario: {scenario}
- Date range: {date_range}
- Tabs explored: {visited_tabs}
- Current renewable share: {current_renewable_pct}%
- Estimated savings: EUR {estimated_savings_eur}

Price context:
{price_context_summary}

Carbon context:
{carbon_context_summary}

Write 3 concise paragraphs:
1. Charging conditions summary
2. Low-cost / low-carbon timing guidance
3. Practical charging plan
"""


def _summarize_context(context: Any) -> str:
    if not isinstance(context, Mapping) or not context:
        return "Not analyzed yet"

    parts: list[str] = []
    for key, value in context.items():
        if isinstance(value, Mapping):
            if "zone" in value:
                parts.append(f"{key} zone={value.get('zone')}")
            elif "state" in value:
                parts.append(f"{key} state={value.get('state')}")
            elif "rows" in value:
                parts.append(f"{key} rows={value.get('rows')}")
            continue
        if isinstance(value, list):
            if value:
                preview = ",".join(str(item) for item in value[:3])
                parts.append(f"{key}={preview}")
            continue
        if value in (None, "", {}):
            continue
        parts.append(f"{key}={value}")

    if not parts:
        return "Not analyzed yet"
    return "; ".join(parts[:6])


def get_prompt(persona: str, data: dict[str, Any]) -> str:
    templates = {
        "trader": TRADER_USER_TEMPLATE,
        "operator": OPERATOR_TEMPLATE,
        "policymaker": POLICY_TEMPLATE,
        "ev_owner": EV_TEMPLATE,
    }
    template = templates.get(persona)
    if template is None:
        raise ValueError(f"Unsupported persona: {persona}")

    payload = dict(data)
    payload["generation_context_summary"] = _summarize_context(payload.get("generation_context"))
    payload["load_context_summary"] = _summarize_context(payload.get("load_context"))
    payload["carbon_context_summary"] = _summarize_context(payload.get("carbon_context"))
    payload["price_context_summary"] = _summarize_context(payload.get("price_context"))
    payload["visited_tabs"] = ", ".join(payload.get("visited_tabs", []) or []) or "None"
    payload["generated_charts"] = ", ".join(payload.get("generated_charts", []) or []) or "None"
    payload["date_range"] = payload.get("analysis_period") or payload.get("date_range") or "Not set"
    payload.setdefault("scenario", "Base Case")
    payload.setdefault("zone", "DE")
    payload.setdefault("renewable_pct", 0.0)
    payload.setdefault("margin_mw", 0.0)
    payload.setdefault("avg_carbon_g_per_kwh", 0.0)
    payload.setdefault("tight_hours_count_7d", 0)
    payload.setdefault("peak_load_mw", 0.0)
    payload.setdefault("current_renewable_pct", 0.0)
    payload.setdefault("estimated_savings_eur", 0.0)

    return template.format(**payload)
