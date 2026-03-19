"""add canonical metrics table for EIA and indicator ingestion

Revision ID: 20260314_0004
Revises: 20260221_0003
Create Date: 2026-03-14 16:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260314_0004"
down_revision = "20260221_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
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
            facets JSONB NOT NULL DEFAULT '{}'::jsonb,
            ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (
                timestamp_utc,
                region_type,
                region_id,
                granularity,
                metric_name,
                source,
                dataset
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_canonical_metrics_region_time
        ON canonical_metrics (region_type, region_id, timestamp_utc)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_canonical_metrics_region_time")
    op.execute("DROP TABLE IF EXISTS canonical_metrics")
