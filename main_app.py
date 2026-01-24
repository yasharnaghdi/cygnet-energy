"""
CYGNET Energy - Unified Grid Intelligence Platform
Combines Carbon Intelligence, Generation Analytics, Data Explorer, and AI Regimes
with a unified Global Sidebar navigation.
"""

import sys
import os
import math
from pathlib import Path
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import psycopg2.extras
from streamlit.components.v1 import html as components_html

# Ensure src/ imports work
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.db.connection import get_connection
from src.services.carbon_service import CarbonIntensityService
from src.api.client import EntsoEAPIClient
from src.api.parser import EntsoEXMLParser
from src.utils.zones import get_zone_keys

# Optional ML imports
try:
    from src.models.modules_2_regime_detector import RegimeDetector
    from src.models.modules_3_regime_models import RegimeModelEnsemble
    from src.models.modules_4_stress_tester import StressTester
    REGIME_FEATURES_AVAILABLE = True
except Exception:
    REGIME_FEATURES_AVAILABLE = False

PSR_LABELS = {
    "B01": "Biomass",
    "B02": "Brown Coal/Lignite",
    "B03": "Coal-Derived Gas",
    "B04": "Fossil Gas",
    "B05": "Hard Coal",
    "B06": "Fossil Oil",
    "B07": "Oil Shale",
    "B08": "Peat",
    "B09": "Geothermal",
    "B10": "Hydro Pumped Storage",
    "B11": "Hydro Run-of-River",
    "B12": "Hydro Reservoir",
    "B13": "Marine",
    "B14": "Nuclear",
    "B15": "Other",
    "B16": "Other Renewable",
    "B17": "Solar",
    "B18": "Solar PV",
    "B19": "Wind Onshore",
    "B20": "Wind Offshore",
    "B21": "Waste",
}

REGIME_FEATURE_LABELS = {
    "res_penetration": "RES penetration (%)",
    "net_import": "Net import (MW)",
    "price_volatility": "Price volatility",
}

REGIME_FEATURE_DETAILS = {
    "res_penetration": "Share of demand met by renewables. Higher values usually lower carbon intensity.",
    "net_import": "Net imports into the zone. Higher values can signal tighter local supply.",
    "price_volatility": "Price variability over recent hours. Higher values indicate instability or stress.",
}


# ══════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="CYGNET Energy - Grid Intelligence Platform",
    layout="wide",
    page_icon="🌍",
    initial_sidebar_state="expanded",
)

# Professional CSS (kept from original streamlit_carbon_app.py)
st.markdown(
    """
<style>
.big-font { font-size: 48px; font-weight: bold; color: #1f77b4; }
.metric-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 20px;
    border-radius: 10px;
    color: white;
    text-align: center;
}
.green-card {
    background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
    padding: 20px;
    border-radius: 10px;
    color: white;
}
.warning-card {
    background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
    padding: 20px;
    border-radius: 10px;
    color: white;
}
.story-box {
    background-color: #f0f2f6;
    padding: 15px;
    border-left: 4px solid #1f77b4;
    border-radius: 5px;
    margin: 10px 0;
}
</style>
""",
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════
# SHARED SERVICES
# ══════════════════════════════════════════════════════════════
@st.cache_resource
def get_db():
    return get_connection()

def render_db_error(context, exc):
    st.error(f"{context} is unavailable because the database connection failed.")
    st.caption(f"Error: {exc}")

@st.cache_resource
def get_carbon_service():
    conn = get_db()
    return CarbonIntensityService(conn)

@st.cache_resource
def load_regime_stack():
    """Load trained ML models if available."""
    if not REGIME_FEATURES_AVAILABLE:
        return None, None, None
    try:
        detector = RegimeDetector()
        detector.load("src/models/trained/regime_detector.pkl")
        ensemble = RegimeModelEnsemble()
        ensemble.load("src/models/trained/regime_models")
        tester = StressTester(ensemble)
        return detector, ensemble, tester
    except Exception as e:
        return None, None, None

@st.cache_data(ttl=600)
def get_data_coverage(_conn, zone):
    if _conn is None:
        return {"min_date": None, "max_date": None, "monthly": pd.DataFrame()}

    zone_keys = get_zone_keys(zone)
    bounds = pd.read_sql_query(
        """
        SELECT MIN(time) AS min_time, MAX(time) AS max_time
        FROM generation_actual
        WHERE bidding_zone_mrid = ANY(%s)
        """,
        _conn,
        params=(zone_keys,)
    )
    min_time = bounds["min_time"].iloc[0]
    max_time = bounds["max_time"].iloc[0]

    monthly = pd.read_sql_query(
        """
        SELECT date_trunc('month', time) AS month, COUNT(*) AS rows
        FROM generation_actual
        WHERE bidding_zone_mrid = ANY(%s)
        GROUP BY 1
        ORDER BY 1
        """,
        _conn,
        params=(zone_keys,)
    )

    return {
        "min_date": min_time.date() if pd.notnull(min_time) else None,
        "max_date": max_time.date() if pd.notnull(max_time) else None,
        "monthly": monthly
    }

def fetch_generation_data(conn, country, start_dt, end_dt):
    api_client = EntsoEAPIClient()
    xml_data = api_client.get_actual_generation(country, start_dt, end_dt)
    if not xml_data:
        return 0

    df = EntsoEXMLParser.parse_generation_xml(xml_data)
    if df is None or df.empty:
        return 0

    df["bidding_zone_mrid"] = api_client.BIDDING_ZONES.get(country, country)
    df["quality_code"] = "A"
    df["data_source"] = "ENTSOE_API"

    records = df[[
        "time",
        "bidding_zone_mrid",
        "psr_type",
        "actual_generation_mw",
        "quality_code",
        "data_source",
    ]].to_dict("records")

    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(
            cur,
            """
            INSERT INTO generation_actual
            (time, bidding_zone_mrid, psr_type, actual_generation_mw, quality_code, data_source)
            VALUES (%(time)s, %(bidding_zone_mrid)s, %(psr_type)s, %(actual_generation_mw)s, %(quality_code)s, %(data_source)s)
            ON CONFLICT (time, bidding_zone_mrid, psr_type)
            DO UPDATE SET actual_generation_mw = EXCLUDED.actual_generation_mw
            """,
            records,
            page_size=1000
        )
    conn.commit()
    return len(records)

def set_global_range(start_date, end_date):
    st.session_state["global_start"] = start_date
    st.session_state["global_end"] = end_date

def intensity_status(intensity):
    if intensity < 150:
        return "LOW"
    if intensity < 300:
        return "MODERATE"
    if intensity < 500:
        return "HIGH"
    return "CRITICAL"

def build_demo_mix(intensity, renewable_pct):
    renewable_share = min(75.0, max(20.0, renewable_pct))
    nuclear_share = 15.0 if renewable_share < 60 else 10.0
    fossil_share = max(5.0, 100.0 - renewable_share - nuclear_share)
    if renewable_share + nuclear_share + fossil_share != 100.0:
        renewable_share = 100.0 - nuclear_share - fossil_share

    mix = [
        ("Solar", renewable_share * 0.35),
        ("Wind Onshore", renewable_share * 0.4),
        ("Wind Offshore", renewable_share * 0.25),
        ("Nuclear", nuclear_share),
        ("Fossil Gas", fossil_share * 0.7),
        ("Hard Coal", fossil_share * 0.3),
    ]

    formatted = {}
    for name, pct in mix:
        pct = round(pct, 1)
        emissions = round((pct / 100.0) * intensity * 10, 0)
        formatted[name] = {"mw": None, "pct": pct, "emissions": emissions}
    return formatted

def build_demo_current_data(country):
    base_intensity = {
        "DE": 260,
        "FR": 120,
        "GB": 220,
        "ES": 180,
        "IT": 240,
    }.get(country, 210)
    renewable_pct = max(20.0, min(75.0, 70.0 - (base_intensity - 100) * 0.2))
    return {
        "timestamp": datetime.now().replace(minute=0, second=0, microsecond=0),
        "country": country,
        "co2_intensity": round(base_intensity, 2),
        "generation_mix": build_demo_mix(base_intensity, renewable_pct),
        "renewable_pct": round(renewable_pct, 1),
        "fossil_pct": round(100 - renewable_pct, 1),
        "status": intensity_status(base_intensity),
        "total_generation_mw": round(45000 + base_intensity * 10, 2),
        "data_source": "Demo",
    }

def build_demo_green_data(forecast_df, threshold=200):
    if forecast_df is None or forecast_df.empty:
        return None
    df = forecast_df.copy()
    df["co2_intensity"] = pd.to_numeric(df["co2_intensity"], errors="coerce")
    df = df.dropna(subset=["co2_intensity"])
    if df.empty:
        return None
    green = df[df["co2_intensity"] <= threshold]
    worst = df.nlargest(3, "co2_intensity")
    best = df.loc[df["co2_intensity"].idxmin()]
    avg_intensity = df["co2_intensity"].mean()
    green_intensity = green["co2_intensity"].mean() if not green.empty else avg_intensity
    co2_reduction_pct = ((avg_intensity - green_intensity) / avg_intensity * 100) if avg_intensity else 0
    return {
        "green_hours": green[["timestamp", "co2_intensity", "renewable_pct"]].to_dict("records"),
        "best_hour": {
            "timestamp": best["timestamp"],
            "co2_intensity": best["co2_intensity"],
            "renewable_pct": best["renewable_pct"],
        },
        "worst_hours": worst[["timestamp", "co2_intensity", "renewable_pct"]].to_dict("records"),
        "average_intensity": round(avg_intensity, 2),
        "savings_potential": {
            "co2_reduction_pct": round(co2_reduction_pct, 1),
            "cost_reduction_pct": round(co2_reduction_pct * 0.8, 1),
        },
    }

def build_demo_carbon_snapshot(country, hours=24):
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    base = build_demo_current_data(country)
    rows = []
    for i in range(hours):
        tstamp = now + timedelta(hours=i)
        phase = 2 * math.pi * i / 24
        intensity = base["co2_intensity"] + 60 * math.sin(phase) + 15 * math.sin(phase * 3)
        intensity = max(80.0, intensity)
        renewable_pct = max(15.0, min(80.0, 70.0 - (intensity - 100) * 0.18))
        rows.append({
            "timestamp": tstamp,
            "co2_intensity": round(intensity, 2),
            "renewable_pct": round(renewable_pct, 1),
            "status": intensity_status(intensity),
        })
    forecast_df = pd.DataFrame(rows)
    current = base.copy()
    current.update({
        "co2_intensity": forecast_df["co2_intensity"].iloc[0],
        "renewable_pct": forecast_df["renewable_pct"].iloc[0],
        "fossil_pct": round(100 - forecast_df["renewable_pct"].iloc[0], 1),
        "status": forecast_df["status"].iloc[0],
        "generation_mix": build_demo_mix(forecast_df["co2_intensity"].iloc[0],
                                         forecast_df["renewable_pct"].iloc[0]),
        "data_source": "Demo",
    })
    green_data = build_demo_green_data(forecast_df)
    return current, forecast_df, green_data

def build_demo_generation_data(start_dt, end_dt):
    if end_dt <= start_dt:
        end_dt = start_dt + timedelta(days=1)
    horizon_days = min(14, max(1, (end_dt - start_dt).days))
    start = end_dt - timedelta(days=horizon_days)
    times = pd.date_range(start=start, end=end_dt, freq="H")
    rows = []
    for ts in times:
        hour = ts.hour
        solar = max(0.0, math.sin((hour - 6) / 12 * math.pi)) * 8000
        wind_on = 5000 + 1500 * math.sin(2 * math.pi * hour / 24 + 0.7)
        wind_off = 3500 + 1200 * math.sin(2 * math.pi * hour / 24 + 1.4)
        gas = 10000 + 2000 * math.cos(2 * math.pi * hour / 24)
        nuclear = 8000
        rows.extend([
            {"time": ts.to_pydatetime(), "psr_type": "B18", "actual_generation_mw": solar},
            {"time": ts.to_pydatetime(), "psr_type": "B19", "actual_generation_mw": wind_on},
            {"time": ts.to_pydatetime(), "psr_type": "B20", "actual_generation_mw": wind_off},
            {"time": ts.to_pydatetime(), "psr_type": "B04", "actual_generation_mw": gas},
            {"time": ts.to_pydatetime(), "psr_type": "B14", "actual_generation_mw": nuclear},
        ])
    return pd.DataFrame(rows)

def compute_renewable_stats_from_df(df):
    renewable_types = {"B01", "B17", "B18", "B19", "B20"}
    total_gen = df["actual_generation_mw"].sum()
    renewable_gen = df[df["psr_type"].isin(renewable_types)]["actual_generation_mw"].sum()
    fossil_gen = total_gen - renewable_gen
    return {
        "total_gen": total_gen,
        "renewable_gen": renewable_gen,
        "fossil_gen": fossil_gen,
    }

def describe_data_sufficiency(coverage):
    if not coverage:
        return "Unknown"
    min_date = coverage.get("min_date")
    max_date = coverage.get("max_date")
    if not min_date or not max_date:
        return "Sparse (no DB coverage)"
    span_days = (max_date - min_date).days
    if span_days >= 180:
        return f"Dense ({span_days} days in DB)"
    if span_days >= 30:
        return f"Moderate ({span_days} days in DB)"
    return f"Sparse ({span_days} days in DB)"

def build_gap_story(current_data, forecast_df):
    if not current_data:
        return "No current measurement available to compare against a baseline."
    if forecast_df is None or forecast_df.empty:
        return "No forecast baseline available; interpret this as a point-in-time signal."
    current = float(current_data.get("co2_intensity", 0.0))
    avg = float(pd.to_numeric(forecast_df["co2_intensity"], errors="coerce").mean())
    diff = current - avg
    direction = "above" if diff > 0 else "below"
    gap = abs(diff)
    avg_renewable = None
    if "renewable_pct" in forecast_df:
        avg_renewable = float(pd.to_numeric(forecast_df["renewable_pct"], errors="coerce").mean())
    renewable = current_data.get("renewable_pct")
    renewable_note = ""
    if renewable is not None and avg_renewable is not None:
        renewable_note = (
            f" Renewable share is {renewable:.1f}% versus a {avg_renewable:.1f}% forecast average."
        )
    return (
        f"Current intensity is {gap:.0f} gCO2/kWh {direction} the next-24h average. "
        "This is the gap between expected conditions and the live signal."
        + renewable_note
    )

def render_mermaid(diagram, height=320):
    components_html(
        f"""
        <div class="mermaid">
        {diagram}
        </div>
        <script type="module">
          import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
          mermaid.initialize({{ startOnLoad: true }});
        </script>
        """,
        height=height,
        scrolling=False,
    )

def build_generation_gap_story(df):
    if df is None or df.empty:
        return "No generation data available to contrast expected vs observed behavior."
    hourly_total = df.groupby("time")["actual_generation_mw"].sum()
    peak = float(hourly_total.max())
    trough = float(hourly_total.min())
    gap = peak - trough
    return (
        f"Observed swing between peak and trough generation is {gap:,.0f} MW. "
        "This highlights the operational amplitude in the selected window."
    )

def render_interpretation_panel(
    context_key,
    decision_question,
    what,
    how,
    why,
    model_status,
    training_regime,
    data_sufficiency,
    uncertainty_class,
    gap_story=None,
    assumptions=None,
    responsibility_lines=None,
):
    st.markdown("### Interpretation Panel")
    st.caption("Scientific framing, data lineage, and inference scope.")
    st.markdown(f"**Analytical objective:** {decision_question}")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown("**Phenomenon**")
        st.write(what)
    with col_b:
        st.markdown("**Methodology**")
        st.write(how)
    with col_c:
        st.markdown("**Operational relevance**")
        st.write(why)

    st.markdown("**Model governance**")
    trust_a, trust_b = st.columns(2)
    with trust_a:
        st.write(f"Model status: {model_status}")
        st.write(f"Training regime: {training_regime}")
    with trust_b:
        st.write(f"Data sufficiency: {data_sufficiency}")
        st.write(f"Uncertainty class: {uncertainty_class}")

    if gap_story:
        st.markdown("**Observed vs baseline deviation**")
        st.write(gap_story)

    st.markdown("**Assumptions (toggle to reframe interpretation)**")
    assumptions = assumptions or []
    for idx, assumption in enumerate(assumptions):
        label = assumption.get("label", f"Assumption {idx + 1}")
        note = assumption.get("impact", "")
        is_on = st.toggle(label, value=True, key=f"{context_key}_assumption_{idx}")
        if not is_on and note:
            st.caption(note)

    st.markdown("**Inference scope**")
    responsibility_lines = responsibility_lines or []
    if responsibility_lines:
        st.markdown("\n".join([f"- {line}" for line in responsibility_lines]))

    st.divider()


# ══════════════════════════════════════════════════════════════
# GLOBAL SIDEBAR (Control Center)
# ══════════════════════════════════════════════════════════════
st.sidebar.markdown("# CYGNET ENERGY")
st.sidebar.markdown("### Grid Intelligence Platform")
st.sidebar.divider()

st.sidebar.header("Global Context")

# Global Country Selector
global_country = st.sidebar.selectbox(
    "Select Grid Zone",
    ["DE", "FR", "GB", "ES", "IT"],
    index=0,
    help="This selection applies to all tabs"
)

# Data coverage (for guidance and defaults)
try:
    coverage = get_data_coverage(get_db(), global_country)
except Exception:
    coverage = {"min_date": None, "max_date": None, "monthly": pd.DataFrame()}

# Global Date Range
st.sidebar.subheader("Time Window")
default_end = datetime(2020, 6, 30).date()
default_start = (datetime(2020, 6, 30) - timedelta(days=30)).date()

min_date = coverage.get("min_date")
max_date = coverage.get("max_date")
if min_date and max_date:
    default_end = max_date
    default_start = max(min_date, max_date - timedelta(days=30))

if "global_start" not in st.session_state:
    st.session_state["global_start"] = default_start
if "global_end" not in st.session_state:
    st.session_state["global_end"] = default_end

def on_live_range_toggle():
    if st.session_state.get("live_range"):
        today = datetime.now().date()
        st.session_state["global_start"] = today - timedelta(days=30)
        st.session_state["global_end"] = today
    elif min_date and max_date:
        st.session_state["global_end"] = max_date
        st.session_state["global_start"] = max(min_date, max_date - timedelta(days=30))

live_range = st.sidebar.checkbox(
    "Enable live range (fetch on demand)",
    value=False,
    key="live_range",
    on_change=on_live_range_toggle,
    help="Allow any date range; data will be fetched from ENTSO-E when needed."
)

# Ensure defaults sit inside the allowed date bounds before widget instantiation
if live_range:
    min_bound = datetime(2015, 1, 1).date()
    max_bound = datetime(2025, 12, 31).date()
else:
    min_bound = min_date or datetime(2015, 1, 1).date()
    max_bound = max_date or datetime(2025, 12, 31).date()
if st.session_state["global_start"] < min_bound:
    st.session_state["global_start"] = min_bound
if st.session_state["global_start"] > max_bound:
    st.session_state["global_start"] = max_bound
if st.session_state["global_end"] < min_bound:
    st.session_state["global_end"] = min_bound
if st.session_state["global_end"] > max_bound:
    st.session_state["global_end"] = max_bound
if st.session_state["global_start"] > st.session_state["global_end"]:
    st.session_state["global_start"] = min_bound

def resolve_range_preset(preset):
    if preset == "Custom":
        return None, None
    today = datetime.now().date()
    base_end = today if live_range else (max_date or today)
    if preset == "Last 7 days":
        start = base_end - timedelta(days=7)
        end = base_end
    elif preset == "Last 30 days":
        start = base_end - timedelta(days=30)
        end = base_end
    elif preset == "Last 90 days":
        start = base_end - timedelta(days=90)
        end = base_end
    elif preset == "Most recent 30 days (DB)" and max_date:
        start = max(min_date or max_date, max_date - timedelta(days=30))
        end = max_date
    elif preset == "Prior 30 days (DB)" and max_date:
        recent_start = max(min_date or max_date, max_date - timedelta(days=30))
        end = recent_start - timedelta(days=1)
        start = max(min_date or end, end - timedelta(days=30))
    else:
        return None, None
    start = max(min_bound, start)
    end = min(max_bound, end)
    return start, end

def on_range_preset_change():
    preset = st.session_state.get("range_preset", "Custom")
    start, end = resolve_range_preset(preset)
    if start and end:
        st.session_state["global_start"] = start
        st.session_state["global_end"] = end

if min_date and max_date:
    st.sidebar.caption(f"DB coverage: {min_date} → {max_date}")

    recent_start = max(min_date, max_date - timedelta(days=30))
    previous_end = recent_start - timedelta(days=1)
    previous_start = max(min_date, previous_end - timedelta(days=30))

    if not live_range:
        col_recent, col_prev = st.sidebar.columns(2)
        with col_recent:
            if st.button("Recent 30d", use_container_width=True):
                st.session_state["global_start"] = recent_start
                st.session_state["global_end"] = max_date
                st.rerun()
        with col_prev:
            if st.button("Prior 30d", use_container_width=True):
                st.session_state["global_start"] = previous_start
                st.session_state["global_end"] = previous_end
                st.rerun()
if live_range:
    st.sidebar.caption("Live range enabled: dates can exceed current DB coverage.")
st.sidebar.caption(f"Date bounds: {min_bound} → {max_bound}")

st.sidebar.subheader("Quick Range")
range_options = [
    "Custom",
    "Last 7 days",
    "Last 30 days",
    "Last 90 days",
    "Most recent 30 days (DB)",
    "Prior 30 days (DB)",
]
st.sidebar.selectbox(
    "Preset",
    range_options,
    key="range_preset",
    on_change=on_range_preset_change,
)

global_start = st.sidebar.date_input(
    "Start Date",
    key="global_start",
    min_value=min_bound,
    max_value=max_bound
)
global_end = st.sidebar.date_input(
    "End Date",
    key="global_end",
    min_value=min_bound,
    max_value=max_bound
)

st.sidebar.divider()
st.sidebar.info(
    f"**Active Context**\n\n"
    f"Zone: {global_country}\n\n"
    f"Period: {(global_end - global_start).days} days"
)
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")


# ══════════════════════════════════════════════════════════════
# TAB RENDERERS
# ══════════════════════════════════════════════════════════════

def render_overview(country, coverage):
    data_sufficiency = describe_data_sufficiency(coverage)
    min_date = coverage.get("min_date") if coverage else None
    max_date = coverage.get("max_date") if coverage else None
    gap_story = None
    if min_date and max_date:
        gap_story = (
            f"Stored data spans {min_date} to {max_date}. "
            "Use this window to anchor comparisons before switching to live ranges."
        )

    render_interpretation_panel(
        "overview",
        decision_question="Module orientation and data coverage context for the selected zone.",
        what="Available analytical modules plus DB coverage windows for the current zone.",
        how="Coverage metadata is read from the database and aligned to module availability.",
        why="Establishes the data scope before any analytical inference.",
        model_status="Not applicable (navigation layer)",
        training_regime="N/A",
        data_sufficiency=data_sufficiency,
        uncertainty_class="Contextual (depends on downstream modules)",
        gap_story=gap_story,
        assumptions=[
            {
                "label": "Assumes DB coverage reflects what analysts will use.",
                "impact": "If this is false, prioritization should follow live data fetches.",
            },
            {
                "label": "Assumes the selected zone is decision-relevant.",
                "impact": "If the zone is not the decision scope, switch before interpreting.",
            },
            {
                "label": "Assumes baseline scope is sufficient for the question.",
                "impact": "If not, expand data coverage or add a comparison zone.",
            },
        ],
        responsibility_lines=[
            "Data indicates available coverage.",
            "System enumerates module readiness.",
            "Analyst validates scope and relevance.",
        ],
    )

    st.markdown("# CYGNET ENERGY")
    st.markdown("## Grid Intelligence and Carbon Optimization Platform")
    st.markdown("---")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### Data Explorer")
        st.markdown("""
- Database connectivity test
- Query generation data
- Date range filtering
- Sample data inspection
""")

    with col2:
        st.markdown("### Carbon Intelligence")
        st.markdown("""
- Real-time CO₂ intensity
- Multi-country comparison
- 24h forecast visualization
- EV charging optimizer
""")

    with col3:
        st.markdown("### Grid Regimes")
        st.markdown("""
- AI-powered regime detection
- Stress testing scenarios
- What-if simulations
- Model diagnostics
""")

    st.markdown("---")

    st.markdown("### Project Objectives")
    st.markdown("""
This platform demonstrates:

1. **Data Engineering**: ENTSO-E API integration → PostgreSQL pipeline
2. **Analytics & Visualization**: Interactive dashboards with Plotly
3. **Domain Knowledge**: European energy markets & carbon accounting
4. **Machine Learning**: Regime detection and scenario stress testing
5. **Production Readiness**: Containerized deployment, clean architecture
""")

    st.markdown("---")
    st.markdown("### Insight Planner")
    st.markdown(
        "Start with country selection, then use the data coverage view below to pick a "
        "recent window and a past comparison window. This prevents blind date selection "
        "and makes regime stress results easier to interpret."
    )

    monthly = coverage.get("monthly") if coverage else pd.DataFrame()
    if monthly is not None and not monthly.empty:
        fig_monthly = px.bar(
            monthly,
            x="month",
            y="rows",
            title=f"{country} data coverage by month",
            labels={"month": "Month", "rows": "Rows"}
        )
        fig_monthly.update_layout(height=300)
        st.plotly_chart(fig_monthly, use_container_width=True)
    else:
        st.info("No data coverage summary available yet for this zone.")

    min_date = coverage.get("min_date") if coverage else None
    max_date = coverage.get("max_date") if coverage else None
    if min_date and max_date:
        recent_start = max(min_date, max_date - timedelta(days=30))
        previous_end = recent_start - timedelta(days=1)
        previous_start = max(min_date, previous_end - timedelta(days=30))

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Recent window (suggested)**")
            st.write(f"{recent_start} → {max_date}")
            st.button(
                "Use recent window",
                on_click=set_global_range,
                args=(recent_start, max_date)
            )
        with col_b:
            st.markdown("**Past window (suggested)**")
            st.write(f"{previous_start} → {previous_end}")
            st.button(
                "Use past window",
                on_click=set_global_range,
                args=(previous_start, previous_end)
            )

        st.caption(
            "Suggested flow: run Generation Analytics on the past window, then on the "
            "recent window, and compare shifts in RES penetration and volatility."
        )

    st.markdown("---")
    st.markdown("### Reporting Snapshot (Auto-Generated)")
    snapshot_cols = st.columns(4)

    try:
        conn = get_db()
        service = CarbonIntensityService(conn)
    except Exception:
        service = CarbonIntensityService(None)

    current = service.get_current_intensity(country)
    forecast = service.get_24h_forecast(country, hours=24) if current else None
    if current is None:
        current, forecast, _ = build_demo_carbon_snapshot(country)

    with snapshot_cols[0]:
        st.metric("Current CO₂", f"{current['co2_intensity']} gCO₂/kWh")
    with snapshot_cols[1]:
        st.metric("Renewables", f"{current['renewable_pct']}%")
    with snapshot_cols[2]:
        st.metric("Data Source", current.get("data_source", "Unknown"))
    with snapshot_cols[3]:
        window_label = "DB window" if min_date and max_date else "Live window"
        st.metric("Coverage", window_label)

    report_lines = []
    report_lines.append(f"Zone: {country}")
    if min_date and max_date:
        report_lines.append(f"DB coverage: {min_date} to {max_date}")
    report_lines.append(f"Current intensity: {current['co2_intensity']} gCO2/kWh")
    report_lines.append(f"Renewable share: {current['renewable_pct']}%")

    if forecast is not None and not forecast.empty:
        avg_intensity = float(pd.to_numeric(forecast['co2_intensity'], errors='coerce').mean())
        min_intensity = float(pd.to_numeric(forecast['co2_intensity'], errors='coerce').min())
        max_intensity = float(pd.to_numeric(forecast['co2_intensity'], errors='coerce').max())
        report_lines.append(
            f"Forecast range (24h): {min_intensity:.0f} to {max_intensity:.0f} gCO2/kWh"
        )
        report_lines.append(f"Forecast average (24h): {avg_intensity:.0f} gCO2/kWh")

    report_md = "\n".join([f"- {line}" for line in report_lines])
    st.markdown("**Summary**")
    st.markdown(report_md)
    st.caption("Use this snapshot as the executive baseline before drilling into modules.")

    st.download_button(
        "Download snapshot (Markdown)",
        data=f"# CYGNET Snapshot\n\n{report_md}\n",
        file_name=f"cygnet_snapshot_{country}.md",
        mime="text/markdown",
    )

    st.markdown("### Predictive Modules You Can Use Next")
    st.markdown("""
- **Scenario Library**: multi-factor shocks mapped to grid events.
- **Predictive Response Curve**: shows price sensitivity across a shock range.
- **Regime Coefficients**: explain which features drive outcomes per regime.
""")


def render_carbon_intelligence(default_country):
    st.markdown("# Carbon Intelligence Dashboard")
    st.markdown("### Real-time CO₂ Intensity Tracking and Optimization")

    try:
        conn = get_db()
        service = CarbonIntensityService(conn)
    except Exception as exc:
        st.warning("Database unavailable; using live API data where possible.")
        st.caption(f"DB error: {exc}")
        service = CarbonIntensityService(None)

    # View mode selector
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_countries = st.multiselect(
            "Select countries to compare (max 4)",
            ["DE", "FR", "GB", "ES", "IT"],
            default=[default_country],
            max_selections=4,
        )
    with col2:
        view_mode = st.radio(
            "View Mode",
            ["Single", "Comparison"],
            horizontal=True,
        )

    st.divider()

    # ══════════════════════════════════════════════════════════════
    # COMPARISON MODE
    # ══════════════════════════════════════════════════════════════
    if view_mode == "Comparison" and len(selected_countries) >= 2:
        st.markdown("## Real-Time Country Comparison")

        # Fetch data for all countries
        country_data = {}
        for country in selected_countries:
            data = service.get_current_intensity(country)
            if not data:
                data = build_demo_current_data(country)
            country_data[country] = data

        if any(d.get("data_source") == "Demo" for d in country_data.values()):
            st.info("Live data unavailable for some zones; showing demo data.")

        if not country_data:
            st.error("No data available for selected countries")
        else:
            intensities = [d.get("co2_intensity") for d in country_data.values() if d]
            gap_story = None
            if intensities:
                min_country = min(country_data, key=lambda k: country_data[k]["co2_intensity"])
                max_country = max(country_data, key=lambda k: country_data[k]["co2_intensity"])
                min_val = country_data[min_country]["co2_intensity"]
                max_val = country_data[max_country]["co2_intensity"]
                gap_story = (
                    f"Cleanest zone is {min_country} at {min_val:.0f} gCO2/kWh; "
                    f"dirtiest is {max_country} at {max_val:.0f} gCO2/kWh. "
                    f"Observed gap is {(max_val - min_val):.0f} gCO2/kWh."
                )

            render_interpretation_panel(
                "carbon_compare",
                decision_question="Cross-zone carbon intensity comparison using the latest available signals.",
                what="Side-by-side CO2 intensity and renewable share across selected zones.",
                how="Latest DB records with ENTSO-E live API fallback.",
                why="Quantifies relative exposure and highlights zones with higher carbon load.",
                model_status="Operational (descriptive, no forecasting)",
                training_regime="Latest available measurements",
                data_sufficiency="Mixed (DB + Live API)",
                uncertainty_class="Statistical (live API variability)",
                gap_story=gap_story,
                assumptions=[
                    {
                        "label": "Assumes live API snapshots are representative.",
                        "impact": "If live data is volatile, prioritize DB-backed zones for decisions.",
                    },
                    {
                        "label": "Assumes zones are comparable without demand normalization.",
                        "impact": "If scale matters, compare intensity alongside absolute load.",
                    },
                    {
                        "label": "Assumes emission factors are stable across zones.",
                        "impact": "If factors differ, interpret rankings as directional.",
                    },
                ],
                responsibility_lines=[
                    "Data indicates current intensity levels by zone.",
                    "System ranks relative exposure.",
                    "Analyst validates comparability across zones.",
                ],
            )

            # Create comparison metrics
            cols = st.columns(len(country_data))
            for idx, (country, data) in enumerate(country_data.items()):
                with cols[idx]:
                    st.markdown(f"### {country}")
                    st.metric(
                        "CO₂ Intensity",
                        f"{data['co2_intensity']} g",
                        delta=f"{data['status']}"
                    )
                    st.metric(
                        "Renewable",
                        f"{data['renewable_pct']}%"
                    )
                    st.caption(f"Source: {data.get('data_source', 'Unknown')}")

            st.divider()

            # Comparison chart
            st.markdown("### Carbon Intensity Comparison")
            countries = list(country_data.keys())
            intensities = [country_data[c]['co2_intensity'] for c in countries]

            fig = go.Figure()
            fig.add_trace(go.Bar(
                name='CO₂ Intensity (gCO₂/kWh)',
                x=countries,
                y=intensities,
                marker_color=['#FF6B6B' if i > 300 else '#4ECDC4' if i < 150 else '#FFE66D'
                              for i in intensities],
                text=[f"{i:.0f}" for i in intensities],
                textposition='auto'
            ))
            fig.update_layout(
                title="Current Carbon Intensity by Country",
                xaxis_title="Country",
                yaxis_title="gCO₂/kWh",
                height=400,
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)

            # Ranking table
            st.markdown("### Carbon Ranking (Cleanest to Dirtiest)")
            ranking_data = []
            for country, data in sorted(country_data.items(),
                                      key=lambda x: x[1]['co2_intensity']):
                ranking_data.append({
                    'Rank': f"#{len(ranking_data) + 1}",
                    'Country': country,
                    'CO₂ (g/kWh)': data['co2_intensity'],
                    'Renewable %': data['renewable_pct'],
                    'Status': data['status']
                })
            st.dataframe(ranking_data, use_container_width=True, hide_index=True)

    # ══════════════════════════════════════════════════════════════
    # SINGLE COUNTRY MODE
    # ══════════════════════════════════════════════════════════════
    else:
        country = selected_countries[0] if selected_countries else default_country

        # The Carbon Paradox Expander
        with st.expander("The Carbon Paradox - Why This Matters", expanded=False):
            st.markdown("""
### The Problem Europe Faces

**Europe installed 500 GW of renewable capacity since 2010.**
But here's the paradox:

- At noon, solar generates 100% of Germany's power → Price drops to €5/MWh
- At 6 PM, the sun sets → Coal plants ramp up → Price jumps to €120/MWh
- When wind stops, we burn MORE fossil fuel backup in 2 hours than a coal plant would in a day

**The Result?** Companies claim "we use 100% renewable energy" but the TIMING of when they use it determines actual carbon emissions by up to **6x**.

---

### What CYGNET Does

We measure the **real-time carbon intensity** of the electricity grid and tell you:

1. **What it is RIGHT NOW** (gCO2/kWh)
2. **When it will be cleanest** (next 24 hours)
3. **How much you can save** (money + carbon)

For a 100-vehicle EV fleet charging at optimal times instead of peak hours:

- €138,000/month savings
- 820 tons CO2 prevented/month
- Equivalent to planting 150,000 trees
""")

        st.markdown("")

        # Live Grid Status
        st.markdown("## Live Grid Status")

        demo_mode = False
        forecast_df = None
        green_data = None
        current_data = service.get_current_intensity(country)
        if not current_data:
            demo_mode = True
            st.info("Live data unavailable; showing demo data.")
            current_data, forecast_df, green_data = build_demo_carbon_snapshot(country)

        if current_data:
            if not demo_mode:
                forecast_df = service.get_24h_forecast(country, hours=24)
            if forecast_df is None or forecast_df.empty:
                st.info("Forecast unavailable; showing demo forecast.")
                _, forecast_df, _ = build_demo_carbon_snapshot(country)

            try:
                coverage = get_data_coverage(get_db(), country)
            except Exception:
                coverage = None
            data_sufficiency = "Demo (synthetic)" if demo_mode else describe_data_sufficiency(coverage)
            gap_story = build_gap_story(current_data, forecast_df)

            render_interpretation_panel(
                "carbon_single",
                decision_question="Current CO2 intensity and near-term clean window identification.",
                what="Current intensity, generation mix, and 24-hour outlook with low-carbon windows.",
                how="Latest DB snapshot with ENTSO-E fallback; forecast uses hourly pattern profiles.",
                why="Supports operational scheduling and compliance evidence.",
                model_status="Operational (heuristic forecast)",
                training_regime="DB last 30 days or live 24h fallback",
                data_sufficiency=data_sufficiency,
                uncertainty_class="Structural when DB is sparse; statistical when live",
                gap_story=gap_story,
                assumptions=[
                    {
                        "label": "Assumes hourly patterns are stable for 24h.",
                        "impact": "If patterns break, treat green-hour guidance as directional only.",
                    },
                    {
                        "label": "Assumes no cross-border spillover is dominant.",
                        "impact": "If interconnectors dominate, validate with regional context.",
                    },
                    {
                        "label": "Assumes emission factors are constant.",
                        "impact": "If factors shift, update policy assumptions before decisions.",
                    },
                ],
                responsibility_lines=[
                    "Data indicates current carbon intensity.",
                    "Model suggests low-carbon windows and expected range.",
                    "Operator validates feasibility before action.",
                ],
            )

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                intensity = current_data['co2_intensity']
                status = current_data['status']
                st.metric(
                    label="CO₂ Intensity",
                    value=f"{intensity} gCO₂/kWh",
                    delta=f"{status}",
                    delta_color="inverse"
                )

            with col2:
                renewable_pct = current_data['renewable_pct']
                st.metric(
                    label="Renewable Mix",
                    value=f"{renewable_pct}%",
                    delta=f"Fossil: {current_data['fossil_pct']}%"
                )

            with col3:
                st.metric(
                    label="Total Generation",
                    value=f"{current_data['total_generation_mw']:.0f} MW",
                    delta="Last hour"
                )

            with col4:
                st.metric(
                    label="Updated",
                    value=current_data['timestamp'].strftime("%H:%M"),
                    delta=datetime.now().strftime("%Y-%m-%d")
                )

            st.divider()

            # Generation Mix Breakdown
            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown("### Generation Mix (CO₂ Contribution)")

                mix_data = current_data['generation_mix']
                sources = list(mix_data.keys())
                emissions = [mix_data[s]['emissions'] for s in sources]
                percentages = [mix_data[s]['pct'] for s in sources]

                df_mix = pd.DataFrame({
                    'Source': sources,
                    'Emissions (gCO₂)': emissions,
                    'Percentage': percentages
                }).sort_values('Emissions (gCO₂)', ascending=True)

                fig_mix = px.bar(
                    df_mix,
                    x='Emissions (gCO₂)',
                    y='Source',
                    orientation='h',
                    title="Carbon Contribution by Source",
                    color='Emissions (gCO₂)',
                    color_continuous_scale='RdYlGn_r',
                    labels={'Emissions (gCO₂)': 'gCO₂ (total from this source)'}
                )
                fig_mix.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig_mix, use_container_width=True)

            with col2:
                st.markdown("### Sources")
                for source in sorted(mix_data.keys(),
                                   key=lambda x: mix_data[x]['emissions'],
                                   reverse=True):
                    data = mix_data[source]
                    st.write(f"**{source}**: {data['pct']}% → {data['emissions']:.0f} gCO₂")

            st.divider()

            # 24-Hour Carbon Forecast
            st.markdown("### 24-Hour Carbon Forecast")
            if forecast_df is None or forecast_df.empty:
                _, forecast_df, _ = build_demo_carbon_snapshot(country)

            if forecast_df is not None and not forecast_df.empty:
                fig_forecast = go.Figure()

                # Main line
                fig_forecast.add_trace(go.Scatter(
                    x=forecast_df['timestamp'],
                    y=forecast_df['co2_intensity'],
                    mode='lines+markers',
                    name='CO₂ Intensity',
                    line=dict(color='#1f77b4', width=3),
                    fill='tozeroy',
                    fillcolor='rgba(31, 119, 180, 0.3)',
                ))

                # Add threshold line
                fig_forecast.add_hline(
                    y=200,
                    line_dash="dash",
                    line_color="green",
                    annotation_text="Green Threshold (200)",
                    annotation_position="right"
                )

                # Color zones
                fig_forecast.add_hrect(y0=0, y1=150, fillcolor="green", opacity=0.1, layer="below")
                fig_forecast.add_hrect(y0=150, y1=300, fillcolor="yellow", opacity=0.1, layer="below")
                fig_forecast.add_hrect(y0=300, y1=600, fillcolor="red", opacity=0.1, layer="below")

                fig_forecast.update_layout(
                    title="Next 24 Hours - When Is It Cleanest?",
                    xaxis_title="Time",
                    yaxis_title="CO₂ Intensity (gCO₂/kWh)",
                    hovermode='x unified',
                    height=400,
                    plot_bgcolor='rgba(240,240,240,0.5)'
                )

                st.plotly_chart(fig_forecast, use_container_width=True)

            st.divider()

            # Green Hours
            if green_data is None and not demo_mode:
                green_data = service.get_green_hours(country, threshold=200)
            if green_data is None:
                green_data = build_demo_green_data(forecast_df)

            if green_data and green_data['green_hours']:
                st.markdown("### Green Hours - When to Use Electricity")

                best = green_data.get('best_hour') or {}
                worst_hours = green_data.get('worst_hours') or []
                worst = worst_hours[0] if worst_hours else {}

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.markdown(
                        f'<div class="green-card">'
                        f'<h3>BEST HOUR</h3>'
                        f'<p><b>{best.get("timestamp").strftime("%H:%M") if best.get("timestamp") else "N/A"}</b></p>'
                        f'<p>{int(best.get("co2_intensity", 0))} gCO₂/kWh<br/>{int(best.get("renewable_pct", 0))}% renewable</p>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

                with col2:
                    st.markdown(
                        f'<div class="warning-card">'
                        f'<h3>WORST HOUR</h3>'
                        f'<p><b>{worst.get("timestamp").strftime("%H:%M") if worst.get("timestamp") else "N/A"}</b></p>'
                        f'<p>{int(worst.get("co2_intensity", 0))} gCO₂/kWh<br/>{int(worst.get("renewable_pct", 0))}% renewable</p>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

                with col3:
                    st.markdown(
                        f'<div class="metric-card">'
                        f'<h3>POTENTIAL SAVINGS</h3>'
                        f'<p>CO₂: {green_data["savings_potential"]["co2_reduction_pct"]:.0f}% reduction<br/>'
                        f'Cost: {green_data["savings_potential"]["cost_reduction_pct"]:.0f}% reduction</p>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

                st.info(
                    f"Insight: Between the best and worst hours, CO₂ intensity varies by "
                    f"{int(worst.get('co2_intensity', 0) - best.get('co2_intensity', 0))} gCO₂/kWh. "
                    f"For an EV fleet: Shift charging from peak hours (worst) to green hours (best) → "
                    f"30-40% cost reduction, 60-70% emission reduction."
                )

            st.divider()

    # ------------------------------------------------------------------
    # EV Fleet Charging Optimizer
    # ------------------------------------------------------------------

            st.markdown("## EV Fleet Charging Optimizer")
            st.markdown(
                "Quantify carbon and cost outcomes by shifting fleet charging between low-"
                " and high-intensity windows."
            )

            optimizer_green_data = green_data
            if optimizer_green_data is None and not demo_mode:
                optimizer_green_data = service.get_green_hours(country, threshold=200)
            if optimizer_green_data is None:
                st.info("No green-hour optimization data available for this zone yet.")
                return

            best = (optimizer_green_data.get("best_hour") or {})
            worst_list = optimizer_green_data.get("worst_hours") or []
            worst = worst_list[0] if worst_list else {}

            best_time = best.get("timestamp")
            best_time_str = best_time.strftime("%H:%M") if best_time else "N/A"
            best_intensity = float(best.get("co2_intensity", 0.0))
            best_renew = float(best.get("renewable_pct", 0.0))

            worst_time = worst.get("timestamp")
            worst_time_str = worst_time.strftime("%H:%M") if worst_time else "N/A"
            worst_intensity = float(worst.get("co2_intensity", 0.0))
            worst_renew = float(worst.get("renewable_pct", 0.0))

            col_inputs, col_results = st.columns([1, 2])
            with col_inputs:
                fleet_size = st.number_input("Fleet size (vehicles)", min_value=1, value=120, step=5)
                daily_mwh = st.number_input("Daily energy per vehicle (MWh)", min_value=0.1, value=0.25, step=0.05)
                price_green = st.number_input("Low-carbon price (€/MWh)", min_value=0.0, value=35.0, step=1.0)
                price_peak = st.number_input("High-carbon price (€/MWh)", min_value=0.0, value=85.0, step=1.0)

            daily_total_mwh = fleet_size * daily_mwh
            monthly_total_mwh = daily_total_mwh * 30
            price_delta = price_peak - price_green
            cost_savings_monthly = monthly_total_mwh * price_delta

            intensity_delta = max(0.0, worst_intensity - best_intensity)
            co2_savings_monthly_tons = (intensity_delta * daily_total_mwh * 1000 * 30) / 1e6

            with col_results:
                st.markdown("### Window Comparison")
                result_cols = st.columns(2)
                with result_cols[0]:
                    st.metric("Best window", best_time_str)
                    st.metric("CO₂ intensity", f"{best_intensity:.0f} gCO₂/kWh")
                    st.metric("Renewable share", f"{best_renew:.0f}%")
                with result_cols[1]:
                    st.metric("Worst window", worst_time_str)
                    st.metric("CO₂ intensity", f"{worst_intensity:.0f} gCO₂/kWh")
                    st.metric("Renewable share", f"{worst_renew:.0f}%")

                st.markdown("### Estimated Monthly Impact")
                st.metric("Energy shifted", f"{monthly_total_mwh:,.0f} MWh")
                st.metric("CO₂ avoided", f"{co2_savings_monthly_tons:,.1f} tons")
                st.metric("Cost savings", f"€{cost_savings_monthly:,.0f}")

                st.caption(
                    "Assumes charging shifts from the highest-intensity hour to the lowest-"
                    "intensity hour in the current 24h window. Prices are adjustable inputs."
                )


def render_generation_analytics(country, start_date, end_date):
    st.markdown(f"# Generation Analytics")
    st.markdown(f"Real-time electricity generation and renewable energy analytics for **{country}**")

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    try:
        conn = get_db()
    except Exception as exc:
        render_db_error("Generation Analytics", exc)
        return

    # Load generation data
    @st.cache_data(ttl=600)
    def load_generation_data(_conn, zone, start, end):
        zone_keys = get_zone_keys(zone)
        cur = _conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT time, psr_type, actual_generation_mw
            FROM generation_actual
            WHERE bidding_zone_mrid = ANY(%s)
              AND time >= %s
              AND time <= %s
              AND quality_code = 'A'
            ORDER BY time, psr_type
            """,
            (zone_keys, start, end)
        )
        rows = cur.fetchall()
        cur.close()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(row) for row in rows])

    # Load renewable fraction
    @st.cache_data(ttl=600)
    def load_renewable_fraction(_conn, zone, start, end):
        zone_keys = get_zone_keys(zone)
        cur = _conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT
                SUM(CASE WHEN psr_type IN ('B01', 'B17', 'B18', 'B19', 'B20')
                    THEN actual_generation_mw ELSE 0 END) as renewable_gen,
                SUM(CASE WHEN psr_type NOT IN ('B01', 'B17', 'B18', 'B19', 'B20')
                    THEN actual_generation_mw ELSE 0 END) as fossil_gen,
                SUM(actual_generation_mw) as total_gen
            FROM generation_actual
            WHERE bidding_zone_mrid = ANY(%s)
              AND time >= %s
              AND time <= %s
              AND quality_code = 'A'
            """,
            (zone_keys, start, end)
        )
        result = cur.fetchone()
        cur.close()
        return dict(result) if result else {}

    df = load_generation_data(conn, country, start_dt, end_dt)
    renewable_stats = load_renewable_fraction(conn, country, start_dt, end_dt)
    demo_mode = False

    if df.empty:
        st.error(f"No data found for {country} between {start_date} and {end_date}")
        st.info("You can fetch the selected period directly from ENTSO-E.")

        col_fetch, col_demo = st.columns(2)
        with col_fetch:
            if st.button("Fetch from ENTSO-E API for this period", key="fetch_gen_analytics"):
                with st.spinner("Fetching live data and storing in the database..."):
                    inserted = fetch_generation_data(conn, country, start_dt, end_dt)
                if inserted > 0:
                    st.success(f"Inserted {inserted:,} rows. Reloading view...")
                    st.rerun()
                else:
                    st.warning("No data returned for this range. Try a shorter window.")
        with col_demo:
            if st.button("Show demo sample data", key="demo_gen_analytics"):
                st.session_state["demo_gen_analytics"] = True

        if not st.session_state.get("demo_gen_analytics"):
            return

        demo_mode = True
        df = build_demo_generation_data(start_dt, end_dt)
        renewable_stats = compute_renewable_stats_from_df(df)
        st.caption("Demo data in use for this view.")

    coverage = get_data_coverage(conn, country)
    data_sufficiency = "Demo (synthetic)" if demo_mode else describe_data_sufficiency(coverage)
    total_gen = renewable_stats.get('total_gen', 0) or 0
    renewable_gen = renewable_stats.get('renewable_gen', 0) or 0
    fossil_gen = renewable_stats.get('fossil_gen', 0) or 0
    renewable_pct = (renewable_gen / total_gen * 100) if total_gen > 0 else 0

    render_interpretation_panel(
        "generation",
        decision_question="Generation mix characterization over the selected time window.",
        what="Time series by PSR type and renewable share for the selected period.",
        how="Aggregates DB records for the zone and window (demo data if empty).",
        why="Supports audits, operational planning, and regulatory reporting.",
        model_status="Descriptive (no forecasting)",
        training_regime="Not applicable (direct aggregation)",
        data_sufficiency=data_sufficiency,
        uncertainty_class="Data completeness and coverage variability",
        gap_story=build_generation_gap_story(df),
        assumptions=[
            {
                "label": "Assumes the selected window represents the decision period.",
                "impact": "If not, widen the window or add a comparison period.",
            },
            {
                "label": "Assumes generation labels map cleanly to renewables.",
                "impact": "If classification is debated, adjust the renewable mapping.",
            },
            {
                "label": "Assumes no missing intervals in the window.",
                "impact": "If intervals are missing, interpret totals as directional.",
            },
        ],
        responsibility_lines=[
            "Data indicates observed generation for the selected window.",
            "System computes renewable share and mix distribution.",
            "Analyst validates the reporting context.",
        ],
    )

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Generation", f"{total_gen:,.0f} MWh")

    with col2:
        st.metric("Renewable Energy", f"{renewable_gen:,.0f} MWh", delta=f"{renewable_pct:.1f}%")

    with col3:
        st.metric("Fossil Energy", f"{fossil_gen:,.0f} MWh")

    with col4:
        avg_gen = df.groupby('time')['actual_generation_mw'].sum().mean()
        st.metric("Average Hourly", f"{avg_gen:,.0f} MW")

    st.markdown("---")

    # Layout: 2 columns
    left_col, right_col = st.columns([2, 1])

    # LEFT: Time series chart
    with left_col:
        st.subheader("Generation Time Series")

        # Pivot data for plotting
        df_pivot = df.pivot_table(
            index='time',
            columns='psr_type',
            values='actual_generation_mw',
            aggfunc='sum'
        ).reset_index()

        # Create line chart
        fig_timeseries = go.Figure()

        # PSR type colors
        colors = {
            'B17': '#FDE68A',  # Solar
            'B18': '#FDB462',  # Solar PV
            'B19': '#80B1D3',  # Wind onshore
            'B20': '#8DD3C7',  # Wind offshore
            'B01': '#BEBADA',  # Biomass
            'B04': '#FB8072',  # Fossil gas
            'B05': '#696969',  # Coal
            'B14': '#FFD92F',  # Nuclear
        }

        for col in df_pivot.columns:
            if col != 'time':
                fig_timeseries.add_trace(go.Scatter(
                    x=df_pivot['time'],
                    y=df_pivot[col],
                    mode='lines',
                    name=PSR_LABELS.get(col, col),
                    line=dict(color=colors.get(col, '#cccccc'), width=2),
                    stackgroup='one'
                ))

        fig_timeseries.update_layout(
            xaxis_title="Time",
            yaxis_title="Generation (MW)",
            hovermode='x unified',
            height=400,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        st.plotly_chart(fig_timeseries, use_container_width=True)
        st.caption("Legend labels are ENTSO-E generation types mapped to plain names.")

    # RIGHT: Renewable pie chart
    with right_col:
        st.subheader("Energy Mix")

        if renewable_pct > 0:
            fig_pie = go.Figure(data=[go.Pie(
                labels=['Renewable', 'Fossil'],
                values=[renewable_gen, fossil_gen],
                marker=dict(colors=['#2ECC71', '#E74C3C']),
                hole=0.4,
                textinfo='label+percent',
                textfont_size=14
            )])

            fig_pie.update_layout(
                showlegend=True,
                height=400,
                annotations=[dict(text=f'{renewable_pct:.1f}%', x=0.5, y=0.5, font_size=20, showarrow=False)]
            )

            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No renewable data for selected period")

    st.markdown("---")

    # Bottom: Daily patterns
    st.subheader("Daily Generation Patterns")
    st.caption(
        "Hourly averages show diurnal structure for renewable sources. "
        "Use this to identify the hours where variability is structurally highest."
    )

    # Group by hour
    df['hour'] = pd.to_datetime(df['time']).dt.hour
    hourly_avg = df.groupby(['hour', 'psr_type'])['actual_generation_mw'].mean().reset_index()

    # Filter for renewables only
    renewable_types = ['B17', 'B18', 'B19', 'B20', 'B01']
    df_renewable_hourly = hourly_avg[hourly_avg['psr_type'].isin(renewable_types)].copy()
    df_renewable_hourly['psr_name'] = df_renewable_hourly['psr_type'].map(PSR_LABELS).fillna(df_renewable_hourly['psr_type'])

    fig_hourly = px.bar(
        df_renewable_hourly,
        x='hour',
        y='actual_generation_mw',
        color='psr_name',
        labels={'hour': 'Hour of Day', 'actual_generation_mw': 'Average Generation (MW)', 'psr_name': 'Type'},
        color_discrete_map={
            'Solar': '#FDE68A',
            'Solar PV': '#FDB462',
            'Wind Onshore': '#80B1D3',
            'Wind Offshore': '#8DD3C7',
            'Biomass': '#BEBADA'
        },
        category_orders={'psr_name': [PSR_LABELS.get(code, code) for code in renewable_types]}
    )

    fig_hourly.update_layout(height=300)
    st.plotly_chart(fig_hourly, use_container_width=True)

    hourly_totals = df.groupby('hour')['actual_generation_mw'].sum().reset_index()
    hourly_renewable = df[df['psr_type'].isin(renewable_types)].groupby('hour')['actual_generation_mw'].sum().reset_index()
    merged = hourly_totals.merge(hourly_renewable, on='hour', how='left', suffixes=('_total', '_renewable'))
    merged['renewable_share_pct'] = (merged['actual_generation_mw_renewable'] / merged['actual_generation_mw_total'] * 100).fillna(0.0)

    top_renewable = merged.sort_values('renewable_share_pct', ascending=False).head(3)
    top_total = merged.sort_values('actual_generation_mw_total', ascending=False).head(3)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Peak renewable share hours**")
        st.dataframe(
            top_renewable[['hour', 'renewable_share_pct']].rename(columns={
                'hour': 'Hour',
                'renewable_share_pct': 'Renewable share (%)'
            }),
            use_container_width=True,
            hide_index=True
        )
    with col_b:
        st.markdown("**Peak total generation hours**")
        st.dataframe(
            top_total[['hour', 'actual_generation_mw_total']].rename(columns={
                'hour': 'Hour',
                'actual_generation_mw_total': 'Total generation (MW)'
            }),
            use_container_width=True,
            hide_index=True
        )

    source_label = "Demo (synthetic)" if demo_mode else "ENTSO-E"
    st.caption(f"Data Source: {source_label} | Zone: {country} | Rows: {len(df):,}")


def render_regimes_and_stress(country):
    st.markdown("# Grid Regimes and Stress Testing")
    st.markdown("AI-powered regime detection and scenario simulation")
    st.divider()

    try:
        coverage = get_data_coverage(get_db(), country)
    except Exception:
        coverage = None
    data_sufficiency = describe_data_sufficiency(coverage)
    model_status = "Experimental (models unavailable)" if not REGIME_FEATURES_AVAILABLE else "Experimental (trained models)"

    render_interpretation_panel(
        "regimes",
        decision_question="Regime classification and stress-response sensitivity analysis.",
        what="Regime assignment, driver signals, and counterfactual stress scenarios.",
        how="Clustering assigns regimes; per-regime models estimate sensitivity to shocks.",
        why="Quantifies directional risk drivers and scenario impacts.",
        model_status=model_status,
        training_regime="Historical regime states; manual refresh cadence",
        data_sufficiency=data_sufficiency,
        uncertainty_class="Structural (model assumptions) and data sparsity",
        gap_story="Compare stored regime with live detector output to surface drift.",
        assumptions=[
            {
                "label": "Assumes regime clusters are stable through time.",
                "impact": "If regimes drift, rerun clustering before acting on sensitivities.",
            },
            {
                "label": "Assumes linear response within each regime.",
                "impact": "If shocks are nonlinear, treat deltas as directional only.",
            },
            {
                "label": "Assumes regime_states are up to date.",
                "impact": "If data is stale, refresh the regime pipeline first.",
            },
        ],
        responsibility_lines=[
            "Model suggests the current regime and sensitivity direction.",
            "Data indicates driver inputs used by the model.",
            "Analyst validates whether to act on scenarios.",
        ],
    )

    if not REGIME_FEATURES_AVAILABLE:
        st.warning("ML modules not available. Check src/models/trained/ directory.")
        if st.button("Show demo regime snapshot", key="demo_regime_missing"):
            st.subheader("Current Operating Regime (Demo)")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Regime", "Stressed")
            c2.metric("Confidence", "0.72")
            c3.metric("RES Penetration", "28.4%")
            c4.metric("Net Import", "1,450 MW")
            st.markdown("### Driver Snapshot (Demo)")
            st.dataframe(
                pd.DataFrame(
                    [
                        {"driver": "Net import constraint", "impact": "High"},
                        {"driver": "RES drop", "impact": "Medium"},
                        {"driver": "Load surge", "impact": "Medium"},
                    ]
                ),
                use_container_width=True,
                hide_index=True
            )
        return

    detector, ensemble, tester = load_regime_stack()

    if not detector or not ensemble or not tester:
        st.error("Could not load trained models.")
        return

    with st.expander("How the 4 modules work (and how to read them)", expanded=False):
        st.markdown("""
**Module 1: State Variables**
Turns raw generation into 5 operating gauges: load tightness, RES penetration, net import,
interconnect saturation, and price volatility. These are the inputs to all regimes.

**Module 2: Regime Detector**
Clusters system states into operating modes. Confidence reflects distance to the nearest
cluster center, not forecast certainty.

**Module 3: Regime Models**
Fits a separate linear model per regime so sensitivity (coefficients) changes by regime.
Use R²/MAE and sample size to judge reliability.

**Module 4: Stress Tester**
Applies counterfactual shocks to the state variables and shows price impact deltas. Use
direction and magnitude, not absolute price, as the insight.
""")

    st.caption(
        "Inputs for this view come from the `regime_states` table and the trained models "
        "under `src/models/trained`."
    )

    st.subheader("How to interpret this page")
    st.write(
        "Regimes describe operating conditions, not price forecasts. Use the driver "
        "signals to understand why the regime is assigned, then test sensitivity "
        "using the what-if tools."
    )
    with st.expander("Feature definitions", expanded=False):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Feature": REGIME_FEATURE_LABELS.get(key, key),
                        "Meaning": REGIME_FEATURE_DETAILS.get(key, ""),
                    }
                    for key in REGIME_FEATURE_LABELS
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

    try:
        conn = get_db()
    except Exception as exc:
        render_db_error("Grid Regimes & Stress Testing", exc)
        return

    # Latest regime state
    latest = pd.read_sql_query(
        """
        SELECT *
        FROM regime_states
        WHERE zone = %s
        ORDER BY time DESC
        LIMIT 1
        """,
        conn,
        params=(country,)
    )

    if latest.empty:
        st.info(f"No regime data available for {country}. Run the regime computation pipeline first.")
        if st.button("Show demo regime snapshot", key="demo_regime_empty"):
            st.subheader("Current Operating Regime (Demo)")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Regime", "Balanced")
            c2.metric("Confidence", "0.65")
            c3.metric("RES Penetration", "41.2%")
            c4.metric("Net Import", "620 MW")
            st.markdown("### Driver Snapshot (Demo)")
            st.dataframe(
                pd.DataFrame(
                    [
                        {"driver": "Wind rebound", "impact": "High"},
                        {"driver": "Interconnect easing", "impact": "Medium"},
                        {"driver": "Price volatility", "impact": "Low"},
                    ]
                ),
                use_container_width=True,
                hide_index=True
            )
        return

    row = latest.iloc[0]

    st.subheader("Current Operating Regime")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Regime", str(row.get("regime_name", "Unknown")))
    c2.metric("Confidence", f"{float(row.get('regime_confidence', 0.0)):.2f}")
    c3.metric("RES Penetration", f"{float(row.get('res_penetration', 0.0)):.1f}%")
    c4.metric("Net Import", f"{float(row.get('net_import', 0.0)):.0f} MW")
    st.caption(
        "RES penetration = share of demand met by renewables; net import = external supply balance."
    )

    required_features = ensemble.feature_names or [
        "res_penetration",
        "net_import",
        "price_volatility",
    ]
    current_regime_id = row.get("regime_id")
    if pd.isna(current_regime_id):
        current_regime_id = None
    if current_regime_id is not None:
        current_regime_id = int(current_regime_id)
    missing_values = [feat for feat in required_features if feat not in row.index]
    if missing_values:
        st.warning(
            "Missing required features in `regime_states`: "
            + ", ".join(missing_values)
        )

    if detector and all(
        feat in row.index
        for feat in ["res_penetration", "net_import", "price_volatility"]
    ):
        live_pred = detector.predict_regime(
            float(row.get("res_penetration", 0.0)),
            float(row.get("net_import", 0.0)),
            float(row.get("price_volatility", 0.0)),
        )
        stored_regime = str(row.get("regime_name", "Unknown"))
        st.caption(
            "Detector check: model predicts "
            f"{live_pred['regime_name']} (conf {live_pred['confidence']:.2f}); "
            f"stored regime is {stored_regime}."
        )
        if stored_regime not in ("Unknown", live_pred["regime_name"]):
            st.warning(
                "Stored regime name differs from live detector output. "
                "Consider re-running the regime assignment pipeline."
            )
        if current_regime_id is None:
            current_regime_id = live_pred["regime_id"]

        profile = detector.regime_profile(live_pred["regime_id"])
        st.markdown("**Regime profile (typical center)**")
        st.write(
            f"RES penetration {profile['res_penetration']:.1f}%, "
            f"net import {profile['net_import']:.0f} MW, "
            f"price volatility {profile['price_volatility']:.1f}."
        )

    st.divider()

    # What-if scenario
    st.markdown("### What-If Scenario Analysis")
    st.markdown(
        "Simulate how price reacts to shocks in different regimes. "
        "Use the direction of change to guide decisions; absolute values are model-specific."
    )

    feature_ranges = {
        "res_penetration": (-20.0, 20.0, 5.0),
        "net_import": (-500.0, 500.0, 100.0),
        "price_volatility": (-30.0, 30.0, 5.0),
    }
    base_state = {
        feature: float(row.get(feature, 0.0))
        for feature in required_features
    }

    col_input, col_output = st.columns([1, 2])

    with col_input:
        feature = st.selectbox(
            "Shock Feature",
            required_features,
            format_func=lambda key: REGIME_FEATURE_LABELS.get(key, key)
        )
        min_val, max_val, default_val = feature_ranges.get(feature, (-50.0, 50.0, 10.0))
        delta = st.slider("Shock Size", min_val, max_val, default_val, step=1.0)

        if st.button("Run Cross-Regime Stress Test"):
            result = tester.regime_comparison(base_state, feature, delta)
            st.session_state['stress_result'] = result

    with col_output:
        if 'stress_result' in st.session_state:
            result_df = st.session_state['stress_result']
            st.dataframe(
                result_df[['regime_name', 'baseline_pred', 'shocked_pred', 'delta_pred', 'pct_change']],
                use_container_width=True,
                hide_index=True
            )

            st.markdown("**Narratives:**")
            for _, outcome in result_df.iterrows():
                text = tester.narrative(outcome.to_dict())
                st.write(f"- {text}")

    st.divider()

    st.markdown("### Scenario Library")
    st.markdown("Pre-built multi-factor shocks mapped to common grid events.")

    scenarios = tester.scenario_library()
    scenario_names = list(scenarios.keys())
    selected_key = st.selectbox(
        "Choose a scenario",
        scenario_names,
        format_func=lambda key: scenarios[key].name
    )
    scenario = scenarios[selected_key]
    st.caption(scenario.description)

    scenario_features = [feat for feat in scenario.perturbations.keys() if feat not in base_state]
    if scenario_features:
        friendly = [REGIME_FEATURE_LABELS.get(feat, feat) for feat in scenario_features]
        st.warning(
            "Scenario uses features not in the current model: "
            + ", ".join(friendly)
        )
    elif st.button("Run Scenario Across Regimes"):
        scenario_results = tester.run_scenario(scenario, base_state)
        rows = []
        narratives = []
        for regime_id, outcome in scenario_results.items():
            rows.append({
                "regime_name": outcome["regime_name"],
                "baseline_pred": outcome["baseline_pred"],
                "shocked_pred": outcome["shocked_pred"],
                "delta_pred": outcome["delta_pred"],
                "pct_change": outcome["pct_change"],
            })
            narratives.append(tester.narrative(outcome))
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True
        )
        st.markdown("**Narratives:**")
        for text in narratives:
            st.write(f"- {text}")

    st.divider()

    st.markdown("### Predictive Response Curve")
    st.markdown(
        "Quantify the price impact of shocks and compare sensitivity across regimes. "
        "Use this to evaluate which levers move price most."
    )

    if current_regime_id is None:
        st.info("Current regime ID unavailable. Add `regime_id` to `regime_states` to enable.")
    else:
        curve_feature = st.selectbox(
            "Feature to sweep",
            required_features,
            format_func=lambda key: REGIME_FEATURE_LABELS.get(key, key),
            key="curve_feature"
        )
        curve_min, curve_max, _ = feature_ranges.get(curve_feature, (-50.0, 50.0, 10.0))
        curve_range = st.slider(
            "Shock range",
            curve_min,
            curve_max,
            (curve_min, curve_max),
            step=1.0
        )
        curve_points = st.slider("Resolution", 6, 24, 12)
        compare_regimes = st.checkbox("Compare all regimes", value=True)

        curve_df = tester.sensitivity_curve(
            current_regime_id,
            base_state,
            curve_feature,
            curve_range,
            n_points=curve_points
        )

        if compare_regimes:
            all_curves = []
            for rid in sorted(ensemble.models.keys()):
                df = tester.sensitivity_curve(
                    rid,
                    base_state,
                    curve_feature,
                    curve_range,
                    n_points=curve_points
                )
                df["regime_id"] = rid
                all_curves.append(df)
            combined = pd.concat(all_curves, ignore_index=True)
            fig_curve = px.line(
                combined,
                x="feature_value",
                y="predicted_output",
                color="regime_id",
                title="Predicted price response by regime",
                labels={
                    "feature_value": REGIME_FEATURE_LABELS.get(curve_feature, curve_feature),
                    "predicted_output": "Predicted price",
                }
            )
        else:
            fig_curve = px.line(
                curve_df,
                x="feature_value",
                y="predicted_output",
                title=f"Predicted price response in Regime {current_regime_id}",
                labels={
                    "feature_value": REGIME_FEATURE_LABELS.get(curve_feature, curve_feature),
                    "predicted_output": "Predicted price",
                }
            )

        fig_curve.update_layout(height=320)
        st.plotly_chart(fig_curve, use_container_width=True)

        step_map = {
            "res_penetration": 1.0,
            "net_import": 50.0,
            "price_volatility": 1.0,
        }
        delta_step = step_map.get(curve_feature, 1.0)
        impact = tester.stress_single_feature(
            current_regime_id,
            base_state,
            curve_feature,
            delta_step
        )
        baseline = impact["baseline_pred"]
        per_unit = impact["delta_pred"]
        pct_change = impact["pct_change"]

        st.markdown("**Impact summary (current regime)**")
        st.write(
            f"Baseline: {baseline:.2f} | "
            f"Δ per {delta_step:g} {REGIME_FEATURE_LABELS.get(curve_feature, curve_feature)}: {per_unit:+.2f} "
            f"({pct_change:+.2f}%)"
        )

    st.divider()

    # Model quality
    st.markdown("### Model Coefficients by Regime")
    st.markdown("How each feature drives price in different operating modes")

    coef_df = ensemble.coefficient_comparison()
    st.dataframe(coef_df, use_container_width=True)

    metrics_rows = []
    for regime_id, model in ensemble.models.items():
        if model.metrics:
            metrics_rows.append({
                "regime_id": regime_id,
                "regime_name": model.regime_name,
                "r2": model.metrics.get("r2"),
                "mae": model.metrics.get("mae"),
                "rmse": model.metrics.get("rmse"),
                "n_samples": model.metrics.get("n_samples"),
            })
    if metrics_rows:
        st.markdown("### Model Fit Diagnostics")
        st.dataframe(pd.DataFrame(metrics_rows), use_container_width=True, hide_index=True)


def render_data_explorer(country, start_date, end_date):
    st.markdown("# Data Explorer")
    st.markdown("### Database Connectivity and Query Testing")

    try:
        conn = get_db()
    except Exception as exc:
        render_db_error("Data Explorer", exc)
        return

    coverage = get_data_coverage(conn, country)
    data_sufficiency = describe_data_sufficiency(coverage)
    render_interpretation_panel(
        "data_explorer",
        decision_question="Data availability and integrity check for the selected zone.",
        what="Raw record counts and sample rows for the selected window.",
        how="Direct SQL queries against the historical generation table.",
        why="Validates data readiness before any analytical claims.",
        model_status="Raw data (no modeling)",
        training_regime="Not applicable",
        data_sufficiency=data_sufficiency,
        uncertainty_class="Data completeness and query window mismatch",
        gap_story=None,
        assumptions=[
            {
                "label": "Assumes DB coverage matches the decision window.",
                "impact": "If coverage is sparse, use live range or fetch fresh data.",
            },
            {
                "label": "Assumes latest data is not delayed.",
                "impact": "If latency exists, validate timestamps before acting.",
            },
            {
                "label": "Assumes PSR codes map to expected categories.",
                "impact": "If mappings change, update PSR labels before reporting.",
            },
        ],
        responsibility_lines=[
            "Data indicates raw availability and sample values.",
            "System flags gaps or empty windows.",
            "Analyst confirms data fitness for use.",
        ],
    )

    if conn is None:
        st.error("Cannot connect to database. Check configuration.")
        st.stop()
    else:
        st.success("Database connected successfully")

    st.divider()

    # Data query
    try:
        cursor = conn.cursor()
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        zone_keys = get_zone_keys(country)

        # Count total records
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM generation_actual
            WHERE bidding_zone_mrid = ANY(%s)
            """,
            (zone_keys,)
        )
        total_count = cursor.fetchone()[0]

        # Count records in selected range
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM generation_actual
            WHERE bidding_zone_mrid = ANY(%s)
              AND time >= %s
              AND time <= %s
            """,
            (zone_keys, start_dt, end_dt)
        )
        range_count = cursor.fetchone()[0]

        # Display metrics
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Records", f"{total_count:,}")

        with col2:
            st.metric("Country", country)

        with col3:
            st.metric("Date Range", f"{(end_date - start_date).days} days")

        st.divider()
        st.caption(f"Selected range: {start_date} → {end_date}")

        coverage = get_data_coverage(conn, country)
        if coverage.get("min_date") and coverage.get("max_date"):
            st.caption(
                f"Available data for {country}: "
                f"{coverage['min_date']} → {coverage['max_date']}"
            )
        else:
            st.info(
                f"No stored generation data found for {country}. "
                "Data coverage is currently strongest for DE."
            )

        if range_count == 0:
            col_fetch, col_demo = st.columns(2)
            with col_fetch:
                if st.button("Fetch from ENTSO-E API for this period", key="fetch_data_explorer"):
                    with st.spinner("Fetching live data and storing in the database..."):
                        inserted = fetch_generation_data(conn, country, start_dt, end_dt)
                    if inserted > 0:
                        st.success(f"Inserted {inserted:,} rows. Reloading view...")
                        st.rerun()
                    else:
                        st.warning("No data returned for this range. Try a shorter window.")
            with col_demo:
                if st.button("Show demo sample data", key="demo_data_explorer"):
                    st.session_state["demo_data_explorer"] = True

        # Sample data
        st.markdown("### Sample Data")

        if range_count > 0:
            cursor.execute(
                """
                SELECT time, psr_type, actual_generation_mw
                FROM generation_actual
                WHERE bidding_zone_mrid = ANY(%s)
                  AND time >= %s
                  AND time <= %s
                ORDER BY time DESC
                LIMIT 100;
                """,
                (zone_keys, start_dt, end_dt)
            )
            rows = cursor.fetchall()

            if rows:
                df = pd.DataFrame(rows, columns=['Timestamp', 'Source Type', 'Generation (MW)'])
                df['Source Name'] = df['Source Type'].map(PSR_LABELS).fillna(df['Source Type'])
                df = df[['Timestamp', 'Source Type', 'Source Name', 'Generation (MW)']]
                st.dataframe(df, use_container_width=True, height=400)

                # Download button
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "Download CSV",
                    csv,
                    f"generation_data_{country}_{start_date}.csv",
                    "text/csv",
                )
            else:
                st.warning(f"No data found for {country} in selected date range")
        else:
            if st.session_state.get("demo_data_explorer"):
                demo_df = build_demo_generation_data(start_dt, end_dt).head(100)
                demo_df = demo_df.rename(columns={
                    "time": "Timestamp",
                    "psr_type": "Source Type",
                    "actual_generation_mw": "Generation (MW)",
                })
                demo_df["Source Name"] = demo_df["Source Type"].map(PSR_LABELS).fillna(demo_df["Source Type"])
                demo_df = demo_df[['Timestamp', 'Source Type', 'Source Name', 'Generation (MW)']]
                st.caption("Demo data in use for this table.")
                st.dataframe(demo_df, use_container_width=True, height=400)
            else:
                st.warning(f"No data found for {country} in selected date range")
                st.caption("Use live range and fetch data for the selected window.")

        cursor.close()

    except Exception as e:
        st.error(f"Query error: {e}")


def render_technical_info():
    st.markdown("# Technical Documentation")

    render_interpretation_panel(
        "technical_info",
        decision_question="System architecture and provenance documentation.",
        what="Architecture, data pipeline, and technology stack references.",
        how="Static documentation of ingestion, storage, modeling, and presentation layers.",
        why="Supports governance review, compliance onboarding, and audit readiness.",
        model_status="Not applicable (documentation)",
        training_regime="N/A",
        data_sufficiency="Reference only",
        uncertainty_class="None (explanatory)",
        gap_story="Use this view to trace any chart back to its data source.",
        assumptions=[
            {
                "label": "Assumes documentation matches deployed code.",
                "impact": "If code changes, update this page to preserve trust.",
            },
            {
                "label": "Assumes external APIs remain stable.",
                "impact": "If APIs change, update ingestion logic and note impacts.",
            },
            {
                "label": "Assumes model artifacts are versioned.",
                "impact": "If artifacts drift, document the new provenance.",
            },
        ],
        responsibility_lines=[
            "Documentation describes system behavior.",
            "Engineering validates deployment consistency.",
            "Governance teams confirm compliance alignment.",
        ],
    )

    tab1, tab2, tab3 = st.tabs(["Architecture", "Data Pipeline", "Tech Stack"])

    with tab1:
        st.markdown("### System Architecture")
        st.markdown(
            "This pipeline exists to turn raw grid telemetry into decisions. "
            "We pull operational data, convert it into consistent state variables, "
            "then explain regimes and stress impacts in plain terms."
        )

        st.graphviz_chart("""
digraph {
  rankdir=LR;
  node [shape=box, style="rounded,filled", color="#1f77b4", fillcolor="#e8f0fe"];
  entsoe [label="ENTSO-E API\\nRaw XML"];
  api [label="API Client & Parser\\nNormalized DataFrame"];
  db [label="PostgreSQL\\nHistorical Storage"];
  svc [label="Service Layer\\nCarbon + Regime Inputs"];
  ml [label="ML Modules\\nRegimes + Stress Tests"];
  ui [label="Streamlit UI\\nGuided Insights"];
  entsoe -> api -> db -> svc -> ml -> ui;
}
""")
        st.markdown("### Architecture (Mermaid)")
        try:
            render_mermaid(
                """
                flowchart LR
                  A[ENTSO-E API] --> B[API Client & Parser]
                  B --> C[(PostgreSQL)]
                  C --> D[Service Layer]
                  D --> E[ML Modules]
                  E --> F[Streamlit UI]
                """
            )
        except Exception:
            st.code("flowchart LR: ENTSO-E API -> Parser -> PostgreSQL -> Service -> ML -> UI")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Why this matters**")
            st.markdown(
                "Grid emissions depend on *when* you consume electricity. "
                "We need time-aligned signals, not annual averages."
            )
        with col2:
            st.markdown("**What we measure**")
            st.markdown(
                "State variables capture stress, renewable share, and volatility "
                "so regimes are operationally meaningful."
            )
        with col3:
            st.markdown("**How we act**")
            st.markdown(
                "Regime-aware stress tests show directional risk. "
                "This guides decisions like shifting load or hedging."
            )

    with tab2:
        st.markdown("### Data Pipeline")
        st.markdown("""
**1. Data Ingestion**
- `scripts/fetch_entsoe_data.py` - Fetch from API
- `scripts/load_csv_to_db.py` - Load historical data

**2. Storage**
- PostgreSQL with normalized schema
- Composite unique constraints
- Indexed for fast queries

**3. Processing**
- Carbon intensity calculations (IPCC 2014 factors)
- Aggregation by time/country
- Real-time updates

**4. Machine Learning**
- Regime detection (clustering)
- Per-regime predictive models
- Stress testing simulations

**5. Presentation**
- Unified Streamlit dashboard
- Interactive Plotly visualizations
- Responsive design
""")
        st.markdown("### Pipeline (Mermaid)")
        try:
            render_mermaid(
                """
                sequenceDiagram
                  participant API as ENTSO-E API
                  participant Parser as XML Parser
                  participant DB as PostgreSQL
                  participant Service as Service Layer
                  participant UI as Dashboard
                  API->>Parser: Fetch XML
                  Parser->>DB: Normalize & store
                  DB->>Service: Query slices
                  Service->>UI: Emit metrics
                """,
                height=340,
            )
        except Exception:
            st.code("sequence: ENTSO-E -> Parser -> DB -> Service -> UI")

    with tab3:
        st.markdown("### Technology Stack")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Backend**")
            st.markdown("""
- Python 3.10+
- PostgreSQL 14
- psycopg2 (DB driver)
- pandas (data processing)
- scikit-learn (ML)
""")

            st.markdown("**API Integration**")
            st.markdown("""
- requests
- lxml (XML parsing)
- ENTSO-E Transparency Platform
""")

        with col2:
            st.markdown("**Frontend**")
            st.markdown("""
- Streamlit 1.29+
- Plotly (charts)
- Custom CSS styling
""")

            st.markdown("**Deployment**")
            st.markdown("""
- Docker containerization
- Docker Compose orchestration
- Streamlit Cloud ready
""")


def render_health_setup(country, coverage):
    st.markdown("# Health & Setup")
    st.markdown("Preflight checks to keep the demo stable and easy to run.")

    data_sufficiency = describe_data_sufficiency(coverage)
    render_interpretation_panel(
        "health_setup",
        decision_question="Operational readiness checks and data coverage verification.",
        what="Environment, database, and data coverage checks for baseline readiness.",
        how="Validates API token, DB connectivity, and coverage bounds.",
        why="Prevents failed demos and clarifies what must be fixed first.",
        model_status="Operational checks",
        training_regime="Not applicable",
        data_sufficiency=data_sufficiency,
        uncertainty_class="Operational (connectivity and credentials)",
        gap_story=None,
        assumptions=[
            {
                "label": "Assumes environment variables are configured.",
                "impact": "If missing, add .env values before using live data.",
            },
            {
                "label": "Assumes DB is reachable from this host.",
                "impact": "If not, verify Docker or local Postgres status.",
            },
            {
                "label": "Assumes sample CSV is loaded.",
                "impact": "If not, run load_csv_to_db before demos.",
            },
        ],
        responsibility_lines=[
            "System reports readiness checks.",
            "Operators resolve missing configuration.",
            "Analysts proceed only when checks are green.",
        ],
    )

    st.subheader("System Checks")
    col1, col2, col3 = st.columns(3)

    api_token = os.getenv("API_TOKEN")
    with col1:
        if api_token:
            st.success("ENTSO-E API token detected")
        else:
            st.error("ENTSO-E API token missing")
            st.caption("Add `API_TOKEN` to `.env` for live data fetches.")

    with col2:
        try:
            conn = get_db()
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
            st.success("Database connection OK")
        except Exception as exc:
            st.error("Database connection failed")
            st.caption(f"{exc}")

    with col3:
        if coverage and coverage.get("min_date") and coverage.get("max_date"):
            st.success("Historical data available")
            st.caption(
                f"{country}: {coverage['min_date']} → {coverage['max_date']}"
            )
        else:
            st.warning("No historical data found")
            st.caption("Enable live range and fetch from ENTSO-E for a demo window.")

    st.divider()

    st.subheader("Demo Readiness")
    steps = [
        "Pick a zone with data coverage (DE recommended).",
        "Use the suggested recent window in the sidebar.",
        "Run Generation Analytics to confirm charts populate.",
        "Open Grid Regimes & Stress Testing (requires trained models).",
    ]
    st.write("Suggested demo flow:")
    st.write("\n".join([f"- {step}" for step in steps]))

    if not REGIME_FEATURES_AVAILABLE:
        st.info("Regime models not detected. Add files under `src/models/trained` for ML demos.")


# ══════════════════════════════════════════════════════════════
# MAIN NAVIGATION
# ══════════════════════════════════════════════════════════════

sections = [
    "Overview",
    "Carbon Intelligence",
    "Generation Analytics",
    "Grid Regimes & Stress Testing",
    "Data Explorer",
    "Technical Info",
    "Health & Setup",
]
section = st.sidebar.radio("Navigate", sections, key="section")

if section == "Overview":
    render_overview(global_country, coverage)
elif section == "Carbon Intelligence":
    render_carbon_intelligence(global_country)
elif section == "Generation Analytics":
    render_generation_analytics(global_country, global_start, global_end)
elif section == "Grid Regimes & Stress Testing":
    render_regimes_and_stress(global_country)
elif section == "Data Explorer":
    render_data_explorer(global_country, global_start, global_end)
elif section == "Technical Info":
    render_technical_info()
elif section == "Health & Setup":
    render_health_setup(global_country, coverage)
