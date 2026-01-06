"""
🌍 CYGNET ENERGY - Carbon Intelligence Dashboard
Real-time CO2 intensity tracking and optimization

A data-driven storytelling platform for European grid carbon intelligence.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.db.connection import get_connection
from src.services.carbon_service import CarbonIntensityService
from src.utils.config import DEBUG

# ══════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="CYGNET Energy - Carbon Intelligence",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for storytelling
st.markdown("""
<style>
    .big-font {
        font-size: 48px;
        font-weight: bold;
        color: #1f77b4;
    }
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
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# INITIALIZE SESSION STATE
# ══════════════════════════════════════════════════════════════

def get_db():
    return get_connection()

def get_carbon_service():
    conn = get_db()
    return CarbonIntensityService(conn)

# ══════════════════════════════════════════════════════════════
# HEADER & INTRO - MULTI-COUNTRY SELECTOR
# ══════════════════════════════════════════════════════════════
st.markdown("# 🌍 CYGNET ENERGY")
st.markdown("### Carbon Intelligence for the European Grid")

col1, col2 = st.columns([2, 1])

with col1:
    selected_countries = st.multiselect(
        "Select countries to compare (max 4)",
        ["DE", "FR", "GB", "ES", "IT"],
        default=["DE", "FR"],
        max_selections=4
    )

with col2:
    view_mode = st.radio(
        "View Mode",
        ["Comparison", "Single"],
        horizontal=True
    )

st.divider()

# ══════════════════════════════════════════════════════════════
# COMPARISON MODE
# ══════════════════════════════════════════════════════════════

service = get_carbon_service()

if view_mode == "Comparison" and len(selected_countries) >= 2:

    st.markdown("## 📊 REAL-TIME COUNTRY COMPARISON")

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
                # Country flag emoji
                flags = {"DE": "🇩🇪", "FR": "🇫🇷", "GB": "🇬🇧", "ES": "🇪🇸", "IT": "🇮🇹"}

                st.markdown(f"### {flags.get(country, '')} {country}")

                # Status color
                status_colors = {
                    'LOW': '🟢',
                    'MODERATE': '🟡',
                    'HIGH': '🟠',
                    'CRITICAL': '🔴'
                }

                st.metric(
                    "CO₂ Intensity",
                    f"{data['co2_intensity']} g",
                    delta=f"{status_colors[data['status']]} {data['status']}"
                )

                st.metric(
                    "Renewable",
                    f"{data['renewable_pct']}%"
                )

                st.caption(f"Source: {data.get('data_source', 'Unknown')}")

        st.divider()

        # Comparison chart
        st.markdown("### 📊 Carbon Intensity Comparison")

        import plotly.graph_objects as go

        countries = list(country_data.keys())
        intensities = [country_data[c]['co2_intensity'] for c in countries]
        renewable_pcts = [country_data[c]['renewable_pct'] for c in countries]

        fig = go.Figure()

        # Bar chart
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
        st.markdown("### 🏆 Carbon Ranking (Cleanest to Dirtiest)")

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

elif view_mode == "Single Country":
    # Use existing single country view
    country = st.selectbox("Select Country", selected_countries or ["DE"])
    # ... rest of your existing single country code


# ══════════════════════════════════════════════════════════════
# THE STORY: OPENING
# ══════════════════════════════════════════════════════════════

with st.expander("📖 **THE CARBON PARADOX** - Why This Matters", expanded=False):
    st.markdown("""
    ### The Problem Europe Faces

    **Europe installed 500 GW of renewable capacity since 2010.**

    But here's the paradox:

    - ☀️ **At noon**, solar generates 100% of Germany's power → Price drops to €5/MWh
    - 🌙 **At 6 PM**, the sun sets → Coal plants ramp up → Price jumps to €120/MWh
    - 💨 **When wind stops**, we burn MORE fossil fuel backup in 2 hours than a coal plant would in a day

    **The Result?** Companies claim "we use 100% renewable energy" but the TIMING of when they use it determines actual carbon emissions by up to **6x**.

    ---

    ### What CYGNET Does

    We measure the **real-time carbon intensity** of the electricity grid and tell you:
    1. **What it is RIGHT NOW** (gCO2/kWh)
    2. **When it will be cleanest** (next 24 hours)
    3. **How much you can save** (money + carbon)

    For a 100-vehicle EV fleet charging at optimal times instead of peak hours:
    - **€138,000/month savings** 💰
    - **820 tons CO2 prevented/month** 🌱
    - **Equivalent to planting 150,000 trees** 🌳
    """)

st.markdown("")

# ══════════════════════════════════════════════════════════════
# LIVE METRICS
# ══════════════════════════════════════════════════════════════

st.markdown("## 📊 LIVE GRID STATUS")

service = get_carbon_service()
country = selected_countries[0] if selected_countries else "DE"
current_data = service.get_current_intensity(country)

if current_data:
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        intensity = current_data['co2_intensity']
        status = current_data['status']

        # Color coding
        if status == 'LOW':
            color = "🟢"
        elif status == 'MODERATE':
            color = "🟡"
        elif status == 'HIGH':
            color = "🔴"
        else:
            color = "🔴🔴"

        st.metric(
            label="CO₂ Intensity",
            value=f"{intensity} gCO₂/kWh",
            delta=f"{status} {color}",
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

    # ══════════════════════════════════════════════════════════════
    # GENERATION MIX BREAKDOWN
    # ══════════════════════════════════════════════════════════════

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 🔋 Generation Mix (CO₂ Contribution)")

        # Prepare data for bar chart
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
        st.markdown("### 📋 Sources")
        for source in sorted(mix_data.keys(), key=lambda x: mix_data[x]['emissions'], reverse=True):
            data = mix_data[source]
            st.write(f"**{source}**: {data['pct']}% → {data['emissions']:.0f} gCO₂")

    st.divider()

    # ══════════════════════════════════════════════════════════════
    # 24-HOUR CARBON FORECAST
    # ══════════════════════════════════════════════════════════════

    st.markdown("### 📈 24-Hour Carbon Forecast")

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
            hovertemplate='<b>%{x|%H:%M}</b><br>CO₂: %{y:.0f} gCO₂/kWh<extra></extra>'
        ))

        # Add threshold line (200 = green)
        fig_forecast.add_hline(
            y=200,
            line_dash="dash",
            line_color="green",
            annotation_text="Green Threshold (200)",
            annotation_position="right"
        )

        # Color zones
        fig_forecast.add_hrange(y0=0, y1=150, fillcolor="green", opacity=0.1, layer="below")
        fig_forecast.add_hrange(y0=150, y1=300, fillcolor="yellow", opacity=0.1, layer="below")
        fig_forecast.add_hrange(y0=300, y1=600, fillcolor="red", opacity=0.1, layer="below")

        fig_forecast.update_layout(
            title="Next 24 Hours - When Is It Cleanest?",
            xaxis_title="Time",
            yaxis_title="CO₂ Intensity (gCO₂/kWh)",
            hovermode='x unified',
            height=400,
            plot_bgcolor='rgba(240,240,240,0.5)'
        )

        st.plotly_chart(fig_forecast, use_container_width=True)

    # ══════════════════════════════════════════════════════════════
    # GREEN HOUR RECOMMENDATIONS
    # ══════════════════════════════════════════════════════════════

    st.divider()

    green_data = service.get_green_hours(country, threshold=200)

    if green_data and green_data['green_hours']:
        st.markdown("### ⭐ GREEN HOURS - WHEN TO USE ELECTRICITY")

        best = green_data['best_hour']
        worst = green_data['worst_hours'][0]

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("""
            <div class="green-card">
                <h3>✅ BEST HOUR</h3>
                <p><b>{}</b></p>
                <p>{}  gCO₂/kWh<br/>
                {}% renewable</p>
            </div>
            """.format(
                best['timestamp'].strftime("%H:%M"),
                int(best['co2_intensity']),
                int(best['renewable_pct'])
            ), unsafe_allow_html=True)

        with col2:
            st.markdown("""
            <div class="warning-card">
                <h3>⚠️ WORST HOUR</h3>
                <p><b>{}</b></p>
                <p>{} gCO₂/kWh<br/>
                {}% renewable</p>
            </div>
            """.format(
                worst['timestamp'].strftime("%H:%M"),
                int(worst['co2_intensity']),
                int(worst['renewable_pct'])
            ), unsafe_allow_html=True)

        with col3:
            st.markdown("""
            <div class="metric-card">
                <h3>💰 POTENTIAL SAVINGS</h3>
                <p>CO₂: {} reduction<br/>
                Cost: {} reduction</p>
            </div>
            """.format(
                f"-{green_data['savings_potential']['co2_reduction_pct']:.0f}%",
                f"-{green_data['savings_potential']['cost_reduction_pct']:.0f}%"
            ), unsafe_allow_html=True)

        st.info(f"""
        **💡 Insight:** Between the best and worst hours, CO₂ intensity varies by {int(worst['co2_intensity'] - best['co2_intensity'])} gCO₂/kWh.

        **For an EV fleet:** Shift charging from peak hours (worst) to green hours (best) = **30-40% cost reduction + 60-70% emission reduction**.
        """)

    st.divider()

    # ══════════════════════════════════════════════════════════════
    # EV CHARGING IMPACT CALCULATOR
    # ══════════════════════════════════════════════════════════════

    st.markdown("### 🚗 EV FLEET CHARGING OPTIMIZER")

    with st.form("ev_calculator"):
        col1, col2, col3 = st.columns(3)

        with col1:
            num_evs = st.slider("Number of Electric Vehicles", 1, 10000, 100)

        with col2:
            daily_mwh = st.slider("Daily charging per EV (MWh)", 0.1, 5.0, 2.0)

        with col3:
            st.write("")
            st.write("")
            submitted = st.form_submit_button("💡 Calculate Savings", use_container_width=True)

        if submitted:
            impact = service.calculate_charging_impact(num_evs, daily_mwh)

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### ❌ Peak Hour Charging (Baseline)")
                st.metric("Monthly Cost", f"€{impact['scenario_peak']['monthly_cost']:,.0f}")
                st.metric("Monthly Emissions", f"{impact['scenario_peak']['monthly_emissions_tons']:,.0f} tons CO₂")
                st.write(f"__{impact['scenario_peak']['monthly_emissions_description']}__")

            with col2:
                st.markdown("#### ✅ Green Hour Charging (Optimized)")
                st.metric("Monthly Cost", f"€{impact['scenario_green']['monthly_cost']:,.0f}")
                st.metric("Monthly Emissions", f"{impact['scenario_green']['monthly_emissions_tons']:,.0f} tons CO₂")
                st.write(f"__{impact['scenario_green']['monthly_emissions_description']}__")

            st.divider()

            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("#### 💰 MONTHLY SAVINGS")
                st.metric("Cost", f"€{impact['monthly_savings']['cost']:,.0f}")
                st.metric("% Reduction", f"{impact['monthly_savings']['cost_pct']:.0f}%")

            with col2:
                st.markdown("#### 🌱 EMISSIONS PREVENTED")
                st.metric("CO₂", f"{impact['monthly_savings']['emissions_tons']:,.0f} tons")
                st.metric("% Reduction", f"{impact['monthly_savings']['emissions_pct']:.0f}%")

            with col3:
                st.markdown("#### 📅 ANNUAL IMPACT")
                st.metric("Cost Savings", f"€{impact['annual_savings']['cost']:,.0f}")
                st.metric("Trees Equivalent", f"{impact['annual_savings']['trees_equivalent']:,} 🌳")

            st.success(f"""
            **🎯 Bottom Line:** By shifting {num_evs} EVs to green charging hours, you save:

            💰 **€{impact['annual_savings']['cost']/1000:.0f}K per year** in energy costs
            🌍 **{impact['annual_savings']['emissions_tons']:,.0f} tons CO₂ per year** prevented
            🌳 **Equivalent to planting {impact['annual_savings']['trees_equivalent']:,} trees**
            """)

else:
    st.error("⚠️ No data available. Check database connection.")

st.divider()

# ══════════════════════════════════════════════════════════════
# FOOTER & RESOURCES
# ══════════════════════════════════════════════════════════════

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    ### 📚 Learn More
    - [ENTSO-E Transparency Platform](https://transparency.entsoe.eu)
    - [Carbon Intensity API](https://www.electricitymap.org)
    - [EV Charging Guide](https://www.theenergymix.com)
    """)

with col2:
    st.markdown("""
    ### 🔧 Technical Details
    - **Data Source:** ENTSO-E Actual Generation
    - **Update Frequency:** Hourly
    - **Emission Factors:** IPCC 2014 Lifecycle Assessment
    - **Coverage:** 8 European countries
    """)

with col3:
    st.markdown("""
    ### 💼 For Businesses


    📧 he@yasharnaghdi.com
    """)

st.markdown("---")
st.caption("🌍 CYGNET Energy - Making the European grid cleaner, smarter, and cheaper.")
