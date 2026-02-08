from .connection import get_connection

SCHEMA_SQL = """

CREATE TABLE IF NOT EXISTS generation_actual (

time TIMESTAMPTZ NOT NULL,

bidding_zone_mrid VARCHAR(50) NOT NULL,

psr_type VARCHAR(50) NOT NULL,

actual_generation_mw NUMERIC(12, 3),

quality_code VARCHAR(1) DEFAULT 'A',

data_source VARCHAR(20) DEFAULT 'OPS',

ingestion_timestamp TIMESTAMPTZ DEFAULT NOW(),

PRIMARY KEY (time, bidding_zone_mrid, psr_type)

);

CREATE INDEX IF NOT EXISTS idx_generation_zone_time

ON generation_actual (bidding_zone_mrid, time DESC);

CREATE INDEX IF NOT EXISTS idx_generation_psr_time

ON generation_actual (psr_type, time DESC);

CREATE TABLE IF NOT EXISTS load_actual (

time TIMESTAMPTZ NOT NULL,

bidding_zone_mrid VARCHAR(50) NOT NULL,

load_consumption_mw NUMERIC(12, 3),

quality_code VARCHAR(1) DEFAULT 'A',

data_source VARCHAR(20) DEFAULT 'OPS',

ingestion_timestamp TIMESTAMPTZ DEFAULT NOW()

);

CREATE INDEX IF NOT EXISTS idx_load_zone_time

ON load_actual (bidding_zone_mrid, time DESC);

CREATE TABLE IF NOT EXISTS metadata (

mrid VARCHAR(50) PRIMARY KEY,

entity_type VARCHAR(50),

name VARCHAR(255),

country_code VARCHAR(2),

psr_type VARCHAR(50),

nominal_capacity_mw NUMERIC(12, 3),

updated_at TIMESTAMPTZ DEFAULT NOW()

);

CREATE INDEX IF NOT EXISTS idx_metadata_country

ON metadata (country_code);

CREATE TABLE IF NOT EXISTS regime_states (

time TIMESTAMPTZ NOT NULL,

zone VARCHAR(50) NOT NULL,

load_tightness NUMERIC,

res_penetration NUMERIC,

net_import NUMERIC,

interconnect_saturation NUMERIC,

price_volatility NUMERIC,

regime_id INT,

regime_name VARCHAR(50),

regime_confidence NUMERIC,

PRIMARY KEY (time, zone)

);

CREATE INDEX IF NOT EXISTS idx_regime_states_zone_time

ON regime_states (zone, time DESC);

CREATE TABLE IF NOT EXISTS canonical_metrics (
timestamp_utc TIMESTAMPTZ NOT NULL,
region_type VARCHAR(20) NOT NULL,
region_id VARCHAR(50) NOT NULL,
granularity VARCHAR(20) NOT NULL,
metric_name VARCHAR(50) NOT NULL,
metric_value NUMERIC(16, 6),
metric_unit VARCHAR(20),
source VARCHAR(50) NOT NULL,
dataset VARCHAR(100) NOT NULL,
facets JSONB DEFAULT '{}'::jsonb,
ingestion_timestamp TIMESTAMPTZ DEFAULT NOW(),
PRIMARY KEY (
    timestamp_utc,
    region_type,
    region_id,
    granularity,
    metric_name,
    source,
    dataset
)
);

CREATE INDEX IF NOT EXISTS idx_canonical_metrics_region_time
ON canonical_metrics (region_type, region_id, timestamp_utc DESC);

CREATE OR REPLACE VIEW indicator_packages_v1 AS
WITH generation_rollup AS (
    SELECT
        time AS timestamp_utc,
        bidding_zone_mrid AS region_id,
        SUM(actual_generation_mw) AS total_mw,
        SUM(
            actual_generation_mw * CASE psr_type
                WHEN 'B01' THEN 120
                WHEN 'B02' THEN 820
                WHEN 'B03' THEN 490
                WHEN 'B04' THEN 490
                WHEN 'B05' THEN 820
                WHEN 'B06' THEN 650
                WHEN 'B07' THEN 820
                WHEN 'B08' THEN 820
                WHEN 'B09' THEN 45
                WHEN 'B10' THEN 24
                WHEN 'B11' THEN 24
                WHEN 'B12' THEN 24
                WHEN 'B13' THEN 20
                WHEN 'B14' THEN 12
                WHEN 'B15' THEN 100
                WHEN 'B16' THEN 50
                WHEN 'B17' THEN 41
                WHEN 'B18' THEN 41
                WHEN 'B19' THEN 11
                WHEN 'B20' THEN 11
                WHEN 'B21' THEN 120
                ELSE 0
            END
        ) AS total_emissions,
        SUM(
            CASE
                WHEN psr_type IN ('B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08')
                THEN actual_generation_mw
                ELSE 0
            END
        ) AS fossil_mw
    FROM generation_actual
    GROUP BY time, bidding_zone_mrid
),
metrics AS (
    SELECT
        timestamp_utc,
        region_id,
        total_mw,
        total_emissions / NULLIF(total_mw, 0) AS carbon_intensity,
        fossil_mw / NULLIF(total_mw, 0) * 100 AS fossil_share,
        STDDEV_SAMP(total_emissions / NULLIF(total_mw, 0)) OVER (
            PARTITION BY region_id
            ORDER BY timestamp_utc
            ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS volatility
    FROM generation_rollup
)
SELECT
    timestamp_utc,
    'zone'::text AS region_type,
    region_id,
    'hour'::text AS granularity,
    carbon_intensity,
    fossil_share,
    volatility,
    (carbon_intensity <= 200) AS clean_window,
    'ENTSOE'::text AS source,
    'generation_actual'::text AS dataset
FROM metrics;

"""

def create_schema() -> None:

    conn = get_connection()

    cur = conn.cursor()

    cur.execute(SCHEMA_SQL)

    conn.commit()

    cur.close()

    conn.close()
