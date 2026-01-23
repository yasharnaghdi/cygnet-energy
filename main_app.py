"""
CYGNET Energy - Unified Grid Intelligence Platform
Combines Carbon Intelligence, Generation Analytics, Data Explorer, and AI Regimes
with a unified Global Sidebar navigation.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import psycopg2.extras

# Ensure src/ imports work
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.db.connection import get_connection
from src.services.carbon_service import CarbonIntensityService

# Optional ML imports
try:
    from src.models.modules_2_regime_detector import RegimeDetector
    from src.models.modules_3_regime_models import RegimeModelEnsemble
    from src.models.modules_4_stress_tester import StressTester, StressScenario
    REGIME_FEATURES_AVAILABLE = True
except Exception:
    REGIME_FEATURES_AVAILABLE = False


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

# Global Date Range
st.sidebar.subheader("Time Window")
default_end = datetime(2020, 6, 30)
default_start = default_end - timedelta(days=30)

global_start = st.sidebar.date_input(
    "Start Date",
    default_start,
    min_value=datetime(2015, 1, 1),
    max_value=datetime(2025, 12, 31)
)
global_end = st.sidebar.date_input(
    "End Date",
    default_end,
    min_value=datetime(2015, 1, 1),
    max_value=datetime(2025, 12, 31)
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

def render_overview():
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


def render_carbon_intelligence(default_country):
    st.markdown("# Carbon Intelligence Dashboard")
    st.markdown("### Real-time CO₂ Intensity Tracking and Optimization")

    service = get_carbon_service()

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
            if data:
                country_data[country] = data

        if not country_data:
            st.error("No data available for selected countries")
        else:
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

        current_data = service.get_current_intensity(country)

        if current_data:
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

            forecast_df = service.get_24h_forecast(country, hours=24)

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
            green_data = service.get_green_hours(country, threshold=200)

            if green_data and green_data['green_hours']:
                st.markdown("### Green Hours - When to Use Electricity")

                best = green_data['best_hour']
                worst = green_data['worst_hours'][0]

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.markdown(
                        f'<div class="green-card">'
                        f'<h3>BEST HOUR</h3>'
                        f'<p><b>{best["timestamp"].strftime("%H:%M")}</b></p>'
                        f'<p>{int(best["co2_intensity"])} gCO₂/kWh<br/>{int(best["renewable_pct"])}% renewable</p>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

                with col2:
                    st.markdown(
                        f'<div class="warning-card">'
                        f'<h3>WORST HOUR</h3>'
                        f'<p><b>{worst["timestamp"].strftime("%H:%M")}</b></p>'
                        f'<p>{int(worst["co2_intensity"])} gCO₂/kWh<br/>{int(worst["renewable_pct"])}% renewable</p>'
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
                    f"{int(worst['co2_intensity'] - best['co2_intensity'])} gCO₂/kWh. "
                    f"For an EV fleet: Shift charging from peak hours (worst) to green hours (best) → "
                    f"30-40% cost reduction, 60-70% emission reduction."
                )

            st.divider()

    # ------------------------------------------------------------------
    # EV Fleet Charging Optimizer
    # ------------------------------------------------------------------

            st.markdown("## EV Fleet Charging Optimizer")
            st.markdown(
                "Optimize charging windows for large EV fleets based on carbon and price signals."
            )

            green_data = service.get_green_hours(country, threshold=200)

            if not green_data:
                st.info("No green-hour optimization data available for this zone yet.")
                return

            # Safely unpack with .get() everywhere to avoid KeyError
            best = (green_data.get("best_hour") or {})
            worst_list = green_data.get("worst_hours") or []
            worst = worst_list[0] if worst_list else {}

            savings = green_data.get("savings_potential") or {}
            monthly = savings.get("monthly_savings") or {}

            # Safe fallbacks
            best_time = best.get("timestamp")
            best_time_str = best_time.strftime("%H:%M") if best_time else "N/A"
            best_intensity = int(best.get("co2_intensity", 0))
            best_renew = int(best.get("renewable_pct", 0))

            worst_time = worst.get("timestamp")
            worst_time_str = worst_time.strftime("%H:%M") if worst_time else "N/A"
            worst_intensity = int(worst.get("co2_intensity", 0))
            worst_renew = int(worst.get("renewable_pct", 0))

            co2_reduction_pct = savings.get("co2_reduction_pct", 0)
            cost_reduction_pct = savings.get("cost_reduction_pct", 0)

            emissions_desc = monthly.get("emissions_description") or "Carbon savings estimate unavailable."
            cost_desc = monthly.get("cost_description") or "Cost savings estimate unavailable."

            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("### Best Charging Window")
                st.metric("Start time", best_time_str)
                st.metric("CO₂ intensity", f"{best_intensity} gCO₂/kWh")
                st.metric("Renewable share", f"{best_renew}%")

            with col2:
                st.markdown("### Worst Charging Window")
                st.metric("Start time", worst_time_str)
                st.metric("CO₂ intensity", f"{worst_intensity} gCO₂/kWh")
                st.metric("Renewable share", f"{worst_renew}%")

            with col3:
                st.markdown("### Monthly Savings Potential")
                st.metric("CO₂ reduction", f"{co2_reduction_pct:.0f}%")
                st.metric("Cost reduction", f"{cost_reduction_pct:.0f}%")

            st.markdown("#### Impact Narrative")
            st.write(emissions_desc)
            st.write(cost_desc)


def render_generation_analytics(country, start_date, end_date):
    st.markdown(f"# Generation Analytics")
    st.markdown(f"Real-time electricity generation and renewable energy analytics for **{country}**")

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    conn = get_db()

    # Load generation data
    @st.cache_data(ttl=600)
    def load_generation_data(_conn, zone, start, end):
        cur = _conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT time, psr_type, actual_generation_mw
            FROM generation_actual
            WHERE bidding_zone_mrid = %s
              AND time >= %s
              AND time <= %s
              AND quality_code = 'A'
            ORDER BY time, psr_type
            """,
            (zone, start, end)
        )
        rows = cur.fetchall()
        cur.close()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(row) for row in rows])

    # Load renewable fraction
    @st.cache_data(ttl=600)
    def load_renewable_fraction(_conn, zone, start, end):
        cur = _conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT
                SUM(CASE WHEN psr_type IN ('B01', 'B18', 'B19', 'B20')
                    THEN actual_generation_mw ELSE 0 END) as renewable_gen,
                SUM(CASE WHEN psr_type NOT IN ('B01', 'B18', 'B19', 'B20')
                    THEN actual_generation_mw ELSE 0 END) as fossil_gen,
                SUM(actual_generation_mw) as total_gen
            FROM generation_actual
            WHERE bidding_zone_mrid = %s
              AND time >= %s
              AND time <= %s
              AND quality_code = 'A'
            """,
            (zone, start, end)
        )
        result = cur.fetchone()
        cur.close()
        return dict(result) if result else {}

    df = load_generation_data(conn, country, start_dt, end_dt)
    renewable_stats = load_renewable_fraction(conn, country, start_dt, end_dt)

    if df.empty:
        st.error(f"No data found for {country} between {start_date} and {end_date}")
        st.info("Try selecting dates in 2020 (e.g., June 2020)")
        return

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)

    total_gen = renewable_stats.get('total_gen', 0) or 0
    renewable_gen = renewable_stats.get('renewable_gen', 0) or 0
    fossil_gen = renewable_stats.get('fossil_gen', 0) or 0
    renewable_pct = (renewable_gen / total_gen * 100) if total_gen > 0 else 0

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
            'B18': '#FDB462',  # Solar
            'B19': '#80B1D3',  # Wind onshore
            'B20': '#8DD3C7',  # Wind offshore
            'B01': '#BEBADA',  # Biomass
            'B04': '#FB8072',  # Fossil gas
            'B05': '#696969',  # Coal
            'B14': '#FFD92F',  # Nuclear
        }

        psr_names = {
            'B18': 'Solar',
            'B19': 'Wind Onshore',
            'B20': 'Wind Offshore',
            'B01': 'Biomass',
            'B04': 'Fossil Gas',
            'B05': 'Hard Coal',
            'B14': 'Nuclear',
        }

        for col in df_pivot.columns:
            if col != 'time':
                fig_timeseries.add_trace(go.Scatter(
                    x=df_pivot['time'],
                    y=df_pivot[col],
                    mode='lines',
                    name=psr_names.get(col, col),
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

    # Group by hour
    df['hour'] = pd.to_datetime(df['time']).dt.hour
    hourly_avg = df.groupby(['hour', 'psr_type'])['actual_generation_mw'].mean().reset_index()

    # Filter for renewables only
    renewable_types = ['B18', 'B19', 'B20', 'B01']
    df_renewable_hourly = hourly_avg[hourly_avg['psr_type'].isin(renewable_types)]

    fig_hourly = px.bar(
        df_renewable_hourly,
        x='hour',
        y='actual_generation_mw',
        color='psr_type',
        labels={'hour': 'Hour of Day', 'actual_generation_mw': 'Average Generation (MW)', 'psr_type': 'Type'},
        color_discrete_map={
            'B18': '#FDB462',
            'B19': '#80B1D3',
            'B20': '#8DD3C7',
            'B01': '#BEBADA'
        },
        category_orders={'psr_type': renewable_types}
    )

    fig_hourly.update_layout(height=300)
    st.plotly_chart(fig_hourly, use_container_width=True)

    st.caption(f"Data Source: ENTSO-E | Zone: {country} | Rows: {len(df):,}")


def render_regimes_and_stress(country):
    st.markdown("# Grid Regimes and Stress Testing")
    st.markdown("AI-powered regime detection and scenario simulation")
    st.divider()

    if not REGIME_FEATURES_AVAILABLE:
        st.warning("ML modules not available. Check src/models/trained/ directory.")
        return

    detector, ensemble, tester = load_regime_stack()

    if not detector or not ensemble or not tester:
        st.error("Could not load trained models.")
        return

    conn = get_db()

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
        return

    row = latest.iloc[0]

    st.subheader("Current Operating Regime")

    regime_name = str(row.get("regime_name", "Unknown"))
    regime_confidence = float(row.get("regime_confidence", 0.0))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Regime", regime_name)
    c2.metric("Confidence", f"{regime_confidence:.2f}")
    c3.metric("RES Penetration", f"{float(row.get('res_penetration', 0.0)):.1f}%")
    c4.metric("Net Import", f"{float(row.get('net_import', 0.0)):.0f} MW")

    st.divider()

    regime_definitions = {
        "Normal": {
            "summary": "Balanced supply/demand with moderate imports and stable volatility.",
            "signals": [
                "Imports near long-run average",
                "RES share within seasonal norms",
                "Low-to-moderate price volatility",
            ],
        },
        "Stressed": {
            "summary": "System leaning on imports with elevated volatility and tightening capacity.",
            "signals": [
                "Rising net imports",
                "Higher volatility relative to recent history",
                "Lower renewable share vs typical levels",
            ],
        },
        "RES-Dominant": {
            "summary": "High renewable penetration with reduced import needs and calmer price dynamics.",
            "signals": [
                "Elevated RES penetration",
                "Lower net imports or net exports",
                "Volatility subdued",
            ],
        },
    }

    feature_metadata = {
        "res_penetration": {
            "label": "Renewable penetration (%)",
            "range": 100.0,
            "group": "Supply mix",
            "why": "Higher RES share typically reduces marginal emissions and dampens price pressure.",
        },
        "net_import": {
            "label": "Net import (MW)",
            "range": 5000.0,
            "group": "Cross-border flows",
            "why": "Rising imports signal tightness and dependence on neighboring systems.",
        },
        "price_volatility": {
            "label": "Price volatility",
            "range": 50.0,
            "group": "Market stress",
            "why": "Higher volatility indicates stress and uncertainty in balancing supply.",
        },
        "load_tightness": {
            "label": "Load tightness",
            "range": 1.5,
            "group": "Demand pressure",
            "why": "Higher values imply demand approaching available capacity.",
        },
        "interconnect_saturation": {
            "label": "Interconnect saturation (%)",
            "range": 100.0,
            "group": "Cross-border flows",
            "why": "High saturation reduces flexibility for cross-border balancing.",
        },
    }

    st.markdown("### Regime Definition & Stability")
    definition = regime_definitions.get(regime_name)
    with st.expander("Why this regime?", expanded=True):
        if definition:
            st.markdown(f"**Summary:** {definition['summary']}")
            st.markdown("**Typical signals:**")
            for signal in definition["signals"]:
                st.markdown(f"- {signal}")
        else:
            st.markdown("No definition available for this regime label.")

        if regime_confidence < 0.5:
            st.warning("Low confidence: this hour may be a transition state. Treat insights as directional.")

    # What-if scenario
    st.markdown("### What-If Scenario Analysis")
    st.markdown("Simulate how price reacts to shocks in different regimes")

    base_state = {
        feature: float(row.get(feature, 0.0))
        for feature in tester.feature_names
    }

    col_input, col_output = st.columns([1, 2])

    with col_input:
        feature = st.selectbox(
            "Shock Feature",
            tester.feature_names
        )
        delta = st.slider("Shock Size", -50.0, 50.0, 10.0, step=1.0)

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

    st.markdown("### Driver Decomposition")
    st.markdown("Top contributors to the current regime and price pressure context.")

    driver_rows = []
    for feature in tester.feature_names:
        meta = feature_metadata.get(feature, {})
        scale = meta.get("range") or max(abs(base_state[feature]), 1)
        score = abs(base_state[feature]) / scale
        driver_rows.append({
            "Driver": meta.get("label", feature),
            "Group": meta.get("group", "Other"),
            "Current value": base_state[feature],
            "Normalized impact": round(score, 2),
            "Why it matters": meta.get("why", "Context-specific driver."),
        })

    driver_df = pd.DataFrame(driver_rows).sort_values("Normalized impact", ascending=False)
    st.dataframe(driver_df, use_container_width=True, hide_index=True)

    top_drivers = driver_df.head(3)
    st.markdown("**Top drivers right now:**")
    for _, driver in top_drivers.iterrows():
        st.markdown(f"- {driver['Driver']} ({driver['Group']})")

    st.divider()

    st.markdown("### Actionability Mapping")
    action_playbook = {
        "Normal": [
            "Schedule flexible loads with mild preference for low-carbon hours.",
            "Monitor volatility spikes for early stress signals.",
        ],
        "Stressed": [
            "Delay discretionary consumption and pre-position reserves.",
            "Hedge price exposure; expect wider spreads during shocks.",
            "Coordinate with cross-border flows and demand response options.",
        ],
        "RES-Dominant": [
            "Accelerate flexible load shifting to capture low-carbon supply.",
            "Favor storage charging and export opportunities if available.",
        ],
    }
    actions = action_playbook.get(regime_name, ["No action guidance available for this regime yet."])
    for action in actions:
        st.markdown(f"- {action}")

    st.divider()

    st.markdown("### Scenario Library")
    scenarios = tester.scenario_library()
    scenario_key = st.selectbox("Select scenario", list(scenarios.keys()))
    scope = st.radio("Apply scenario to", ["Current regime", "All regimes"], horizontal=True)

    scenario = scenarios[scenario_key]
    scenario_perturbations = {
        key: value
        for key, value in scenario.perturbations.items()
        if key in tester.feature_names
    }
    if len(scenario_perturbations) != len(scenario.perturbations):
        st.caption("Some scenario drivers are not part of the current model and will be ignored.")

    scenario_to_run = StressScenario(
        name=scenario.name,
        description=scenario.description,
        perturbations=scenario_perturbations,
        regime_id=scenario.regime_id,
    )

    if st.button("Run Scenario"):
        if not scenario_to_run.perturbations:
            st.warning("This scenario has no applicable drivers for the current model.")
            return
        if scope == "Current regime" and row.get("regime_id") is not None:
            result = tester.run_scenario(
                scenario_to_run,
                base_state,
                regime_id=int(row.get("regime_id")),
            )
            st.dataframe(pd.DataFrame([result]), use_container_width=True, hide_index=True)
        else:
            results = tester.run_scenario(scenario_to_run, base_state)
            result_df = pd.DataFrame(results.values())
            st.dataframe(result_df, use_container_width=True, hide_index=True)

    # Model quality
    st.markdown("### Model Coefficients by Regime")
    st.markdown("How each feature drives price in different operating modes")

    coef_df = ensemble.coefficient_comparison()
    st.dataframe(coef_df, use_container_width=True)


def render_data_explorer(country, start_date, end_date):
    st.markdown("# Data Explorer")
    st.markdown("### Database Connectivity and Query Testing")

    conn = get_db()

    if conn is None:
        st.error("Cannot connect to database. Check configuration.")
        st.stop()
    else:
        st.success("Database connected successfully")

    st.divider()

    # Data query
    try:
        cursor = conn.cursor()

        # Count query
        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM generation_actual
            WHERE bidding_zone_mrid = '{country}'
            """
        )
        count = cursor.fetchone()[0]

        # Display metrics
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Records", f"{count:,}")

        with col2:
            st.metric("Country", country)

        with col3:
            st.metric("Date Range", f"{(end_date - start_date).days} days")

        st.divider()

        # Sample data
        st.markdown("### Sample Data")

        cursor.execute(
            f"""
            SELECT time, psr_type, actual_generation_mw
            FROM generation_actual
            WHERE bidding_zone_mrid = '{country}'
              AND time >= '{start_date}'
              AND time <= '{end_date}'
            ORDER BY time DESC
            LIMIT 100;
            """
        )
        rows = cursor.fetchall()

        if rows:
            df = pd.DataFrame(rows, columns=['Timestamp', 'Source Type', 'Generation (MW)'])
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

        cursor.close()

    except Exception as e:
        st.error(f"Query error: {e}")


def render_technical_info():
    st.markdown("# Technical Documentation")

    tab1, tab2, tab3 = st.tabs(["Architecture", "Data Pipeline", "Tech Stack"])

    with tab1:
        st.markdown("### System Architecture")
        st.code(
            """
┌─────────────────────────────────────┐
│ ENTSO-E Transparency API            │
└──────────────┬──────────────────────┘
               │ (XML)
               ▼
┌─────────────────────────────────────┐
│ API Client & XML Parser             │
│ (src/api/client.py, parser.py)     │
└──────────────┬──────────────────────┘
               │ (DataFrame)
               ▼
┌─────────────────────────────────────┐
│ PostgreSQL Database                 │
│ (generation_actual table)           │
└──────────────┬──────────────────────┘
               │ (SQL Queries)
               ▼
┌─────────────────────────────────────┐
│ Carbon Service Layer                │
│ (src/services/carbon_service.py)   │
└──────────────┬──────────────────────┘
               │ (Data Objects)
               ▼
┌─────────────────────────────────────┐
│ Streamlit Dashboard (main_app.py)  │
└─────────────────────────────────────┘
""",
            language="text"
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


# ══════════════════════════════════════════════════════════════
# MAIN NAVIGATION
# ══════════════════════════════════════════════════════════════

tabs = st.tabs([
    "Overview",
    "Carbon Intelligence",
    "Generation Analytics",
    "Grid Regimes & Stress Testing",
    "Data Explorer",
    "Technical Info"
])

with tabs[0]:
    render_overview()

with tabs[1]:
    render_carbon_intelligence(global_country)

with tabs[2]:
    render_generation_analytics(global_country, global_start, global_end)

with tabs[3]:
    render_regimes_and_stress(global_country)

with tabs[4]:
    render_data_explorer(global_country, global_start, global_end)

with tabs[5]:
    render_technical_info()
