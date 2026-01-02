"""Cygnet Energy - Streamlit Dashboard for Grid Intelligence."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import psycopg2.extras
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.db.connection import get_connection

# Page config
st.set_page_config(
    page_title="Cygnet Energy - Grid Intelligence",
    page_icon="⚡",
    layout="wide"
)

# Title
st.title("⚡ Cygnet Energy - European Grid Intelligence")
st.markdown("Real-time electricity generation and renewable energy analytics")

# Sidebar filters
st.sidebar.header("📊 Filters")
bidding_zone = st.sidebar.selectbox("Country", ["DE", "FR", "GB", "ES", "IT"], index=0)

# Date range picker (default: 7 days in 2020)
default_end = datetime(2020, 6, 30)
default_start = default_end - timedelta(days=7)

start_date = st.sidebar.date_input("Start Date", default_start, min_value=datetime(2015, 1, 1), max_value=datetime(2020, 12, 31))
end_date = st.sidebar.date_input("End Date", default_end, min_value=datetime(2015, 1, 1), max_value=datetime(2020, 12, 31))

# Convert to datetime
start_dt = datetime.combine(start_date, datetime.min.time())
end_dt = datetime.combine(end_date, datetime.max.time())

# Database connection
@st.cache_resource
def get_db_connection():
    return get_connection()

# Load generation data
@st.cache_data(ttl=600)
def load_generation_data(_conn, zone, start, end):
    cur = _conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT time, psr_type, actual_generation_mw
        FROM generation_actual
        WHERE bidding_zone_mrid = %s
          AND time >= %s
          AND time <= %s
          AND quality_code = 'A'
        ORDER BY time, psr_type
    """, (zone, start, end))

    rows = cur.fetchall()
    cur.close()

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame([dict(row) for row in rows])

# Load renewable fraction
@st.cache_data(ttl=600)
def load_renewable_fraction(_conn, zone, start, end):
    cur = _conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
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
    """, (zone, start, end))

    result = cur.fetchone()
    cur.close()

    return dict(result) if result else {}

# Load data
conn = get_db_connection()
df = load_generation_data(conn, bidding_zone, start_dt, end_dt)
renewable_stats = load_renewable_fraction(conn, bidding_zone, start_dt, end_dt)

# Check if data exists
if df.empty:
    st.error(f"❌ No data found for {bidding_zone} between {start_date} and {end_date}")
    st.info("Try selecting dates in 2020 (e.g., June 2020)")
    st.stop()

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
    st.subheader("📈 Generation Time Series")

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
        'B18': '#FDB462',  # Solar - orange
        'B19': '#80B1D3',  # Wind onshore - blue
        'B20': '#8DD3C7',  # Wind offshore - cyan
        'B01': '#BEBADA',  # Biomass - purple
        'B04': '#FB8072',  # Fossil gas - red
        'B05': '#696969',  # Coal - dark gray
        'B14': '#FFD92F',  # Nuclear - yellow
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
    st.subheader("🌱 Energy Mix")

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
st.subheader("🕐 Daily Generation Patterns")

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

# Footer
st.markdown("---")
st.caption(f"📊 Data Source: Open Power System Data (2015-2020) | Zone: {bidding_zone} | Rows: {len(df):,}")
