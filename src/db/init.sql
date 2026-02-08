-- Initialize CYGNET Energy database schema

CREATE TABLE IF NOT EXISTS generation_actual (
    time TIMESTAMP NOT NULL,
    bidding_zone_mrid VARCHAR(20) NOT NULL,
    psr_type VARCHAR(50) NOT NULL,
    actual_generation_mw NUMERIC(12, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (time, bidding_zone_mrid, psr_type)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_generation_time ON generation_actual(time DESC);
CREATE INDEX IF NOT EXISTS idx_generation_zone ON generation_actual(bidding_zone_mrid);
CREATE INDEX IF NOT EXISTS idx_generation_type ON generation_actual(psr_type);
CREATE INDEX IF NOT EXISTS idx_generation_zone_time ON generation_actual(bidding_zone_mrid, time DESC);

-- Insert sample metadata
CREATE TABLE IF NOT EXISTS metadata (
    key VARCHAR(50) PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO metadata (key, value)
VALUES ('schema_version', '1.0.1')
ON CONFLICT (key) DO NOTHING;

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
