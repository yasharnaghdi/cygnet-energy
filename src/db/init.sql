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
