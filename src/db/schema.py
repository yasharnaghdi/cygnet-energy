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

"""

def create_schema() -> None:

    conn = get_connection()

    cur = conn.cursor()

    cur.execute(SCHEMA_SQL)

    conn.commit()

    cur.close()

    conn.close()
