"""create regime_states table

Revision ID: 20260221_0003
Revises: 20260218_0002
Create Date: 2026-02-21 11:00:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260221_0003"
down_revision = "20260218_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
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
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_regime_states_zone_time
        ON regime_states (zone, time DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_regime_states_zone_time")
    op.execute("DROP TABLE IF EXISTS regime_states")
