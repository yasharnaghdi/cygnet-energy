"""
🌍 CYGNET ENERGY - Grid Intelligence Platform
Multi-module dashboard for energy data analytics
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
    page_title="CYGNET Energy - Grid Intelligence",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ══════════════════════════════════════════════════════════════
# SIDEBAR - MODULE SELECTOR
# ══════════════════════════════════════════════════════════════
st.sidebar.title("🌍 CYGNET ENERGY")
st.sidebar.markdown("### Grid Intelligence Platform")
st.sidebar.divider()

module = st.sidebar.radio(
    "Select Module",
    ["🏠 Overview", "⚡ Data Explorer", "🌱 Carbon Intelligence", "📊 Technical Info"],
    index=0
)

st.sidebar.divider()
st.sidebar.caption("**Demo Version**")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# ══════════════════════════════════════════════════════════════
# INITIALIZE SERVICES
# ══════════════════════════════════════════════════════════════
@st.cache_resource
def get_db():
    return get_connection()

@st.cache_resource
def get_carbon_service():
    conn = get_db()
    return CarbonIntensityService(conn)

# ══════════════════════════════════════════════════════════════
# MODULE 1: OVERVIEW / LANDING PAGE
# ══════════════════════════════════════════════════════════════
if module == "🏠 Overview":
    st.markdown("# 🌍 CYGNET ENERGY")
    st.markdown("## Grid Intelligence & Carbon Optimization Platform")

    st.markdown("---")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### ⚡ Data Explorer")
        st.markdown("""
        - **Database connectivity** test
        - Query generation data
        - Date range filtering
        - Sample data inspection
        """)

    with col2:
        st.markdown("### 🌱 Carbon Intelligence")
        st.markdown("""
        - Real-time CO₂ intensity
        - Multi-country comparison
        - 24h forecast visualization
        - EV charging optimizer
        """)

    with col3:
        st.markdown("### 📊 Technical Info")
        st.markdown("""
        - System architecture
        - Data pipeline overview
        - API documentation
        - Technology stack
        """)

    st.markdown("---")

    # Project description
    st.markdown("### 🎯 Project Objectives")
    st.markdown("""
    This platform demonstrates:
    1. **Data Engineering**: ENTSO-E API integration → PostgreSQL pipeline
    2. **Analytics & Visualization**: Interactive dashboards with Plotly
    3. **Domain Knowledge**: European energy markets & carbon accounting
    4. **Production Readiness**: Containerized deployment, clean architecture
    """)

    st.info("👈 Select a module from the sidebar to explore specific features")

# ══════════════════════════════════════════════════════════════
# MODULE 2: DATA EXPLORER (streamlit_minimal.py logic)
# ══════════════════════════════════════════════════════════════
elif module == "⚡ Data Explorer":
    st.markdown("# ⚡ Data Explorer")
    st.markdown("### Database Connectivity & Query Testing")

    # Database connection test
    conn = get_db()
    if conn is None:
        st.error("❌ Cannot connect to database. Check configuration.")
        st.stop()
    else:
        st.success("✅ Database connected successfully")

    st.divider()

    # Filters
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        bidding_zone = st.selectbox(
            "Select Country",
            ["DE", "FR", "GB", "ES", "IT"],
            index=0
        )

    with col2:
        default_end = datetime(2020, 6, 30)
        default_start = default_end - timedelta(days=7)
        start_date = st.date_input(
            "Start Date",
            default_start,
            min_value=datetime(2015, 1, 1),
            max_value=datetime(2024, 12, 31)
        )

    with col3:
        end_date = st.date_input(
            "End Date",
            default_end,
            min_value=datetime(2015, 1, 1),
            max_value=datetime(2024, 12, 31)
        )

    st.divider()

    # Data query
    try:
        cursor = conn.cursor()

        # Count query
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM generation_actual
            WHERE bidding_zone_mrid = '{bidding_zone}'
        """)
        count = cursor.fetchone()[0]

        # Display metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Records", f"{count:,}")
        with col2:
            st.metric("Country", bidding_zone)
        with col3:
            st.metric("Date Range", f"{(end_date - start_date).days} days")

        st.divider()

        # Sample data
        st.markdown("### 📊 Sample Data")
        cursor.execute(f"""
            SELECT time, psr_type, actual_generation_mw
            FROM generation_actual
            WHERE bidding_zone_mrid = '{bidding_zone}'
                AND time >= '{start_date}'
                AND time <= '{end_date}'
            ORDER BY time DESC
            LIMIT 100;
        """)
        rows = cursor.fetchall()

        if rows:
            df = pd.DataFrame(rows, columns=['Timestamp', 'Source Type', 'Generation (MW)'])
            st.dataframe(df, use_container_width=True, height=400)

            # Download button
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download CSV",
                csv,
                f"generation_data_{bidding_zone}_{start_date}.csv",
                "text/csv",
                key='download-csv'
            )
        else:
            st.warning(f"No data found for {bidding_zone} in selected date range")

        cursor.close()

    except Exception as e:
        st.error(f"❌ Query error: {e}")

# ══════════════════════════════════════════════════════════════
# MODULE 3: CARBON INTELLIGENCE (streamlit_carbon_app.py logic)
# ══════════════════════════════════════════════════════════════
elif module == "🌱 Carbon Intelligence":
    st.markdown("# 🌱 Carbon Intelligence Dashboard")
    st.markdown("### Real-time CO₂ Intensity Tracking & Optimization")

    # Mode selector
    col1, col2 = st.columns([2, 1])

    with col1:
        selected_countries = st.multiselect(
            "Select countries (max 4)",
            ["DE", "FR", "GB", "ES", "IT"],
            default=["DE"],
            max_selections=4
        )

    with col2:
        view_mode = st.radio(
            "View Mode",
            ["Single", "Comparison"],
            horizontal=True
        )

    st.divider()

    service = get_carbon_service()

    # COMPARISON MODE
    if view_mode == "Comparison" and len(selected_countries) >= 2:
        st.markdown("## 📊 Multi-Country Comparison")

        country_data = {}
        for country in selected_countries:
            data = service.get_current_intensity(country)
            if data:
                country_data[country] = data

        if not country_data:
            st.error("No data available for selected countries")
        else:
            # Metrics
            cols = st.columns(len(country_data))
            flags = {"DE": "🇩🇪", "FR": "🇫🇷", "GB": "🇬🇧", "ES": "🇪🇸", "IT": "🇮🇹"}

            for idx, (country, data) in enumerate(country_data.items()):
                with cols[idx]:
                    st.markdown(f"### {flags.get(country, '')} {country}")
                    st.metric("CO₂", f"{data['co2_intensity']:.0f} g/kWh")
                    st.metric("Renewable", f"{data['renewable_pct']:.1f}%")
                    st.caption(f"Status: {data['status']}")

            st.divider()

            # Comparison chart
            countries = list(country_data.keys())
            intensities = [country_data[c]['co2_intensity'] for c in countries]

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=countries,
                y=intensities,
                marker_color=['#FF6B6B' if i > 300 else '#4ECDC4' if i < 150 else '#FFE66D'
                             for i in intensities],
                text=[f"{i:.0f}" for i in intensities],
                textposition='auto'
            ))

            fig.update_layout(
                title="Carbon Intensity Comparison",
                xaxis_title="Country",
                yaxis_title="gCO₂/kWh",
                height=400
            )

            st.plotly_chart(fig, use_container_width=True)

    # SINGLE MODE
    else:
        country = selected_countries[0] if selected_countries else "DE"

        current_data = service.get_current_intensity(country)

        if current_data:
            # KPI Cards
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "CO₂ Intensity",
                    f"{current_data['co2_intensity']:.0f} g/kWh",
                    delta=current_data['status']
                )

            with col2:
                st.metric(
                    "Renewable Mix",
                    f"{current_data['renewable_pct']:.1f}%"
                )

            with col3:
                st.metric(
                    "Total Generation",
                    f"{current_data['total_generation_mw']:.0f} MW"
                )

            with col4:
                st.metric(
                    "Updated",
                    current_data['timestamp'].strftime("%H:%M")
                )

            st.divider()

            # Generation mix
            st.markdown("### 🔋 Generation Mix")
            mix_data = current_data['generation_mix']

            sources = list(mix_data.keys())
            percentages = [mix_data[s]['pct'] for s in sources]

            fig_pie = go.Figure(data=[go.Pie(
                labels=sources,
                values=percentages,
                hole=0.4
            )])

            fig_pie.update_layout(height=400)
            st.plotly_chart(fig_pie, use_container_width=True)

# ══════════════════════════════════════════════════════════════
# MODULE 4: TECHNICAL INFO
# ══════════════════════════════════════════════════════════════
elif module == "📊 Technical Info":
    st.markdown("# 📊  Documentation")

    tab1, tab2, tab3 = st.tabs(["Architecture", "Data Pipeline", "Tech Stack"])

    with tab1:
        st.markdown("### System Architecture")
        st.code("""
┌─────────────────────────────────────┐
│     ENTSO-E Transparency API        │
└──────────────┬──────────────────────┘
               │ (XML)
               ▼
┌─────────────────────────────────────┐
│     API Client & XML Parser         │
│  (src/api/client.py, parser.py)    │
└──────────────┬──────────────────────┘
               │ (DataFrame)
               ▼
┌─────────────────────────────────────┐
│       PostgreSQL Database           │
│    (generation_actual table)        │
└──────────────┬──────────────────────┘
               │ (SQL Queries)
               ▼
┌─────────────────────────────────────┐
│     Carbon Service Layer            │
│  (src/services/carbon_service.py)  │
└──────────────┬──────────────────────┘
               │ (Data Objects)
               ▼
┌─────────────────────────────────────┐
│    Streamlit Dashboard (app.py)     │
└─────────────────────────────────────┘
        """, language="text")

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

        **4. Presentation**
        - Multi-module Streamlit dashboard
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
