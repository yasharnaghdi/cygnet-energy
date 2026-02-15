"""create generation/load/price timeseries records

Revision ID: 20260215_0001
Revises:
Create Date: 2026-02-15 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260215_0001"
down_revision = None
branch_labels = None
depends_on = None


def _create_hypertable(table_name: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                PERFORM create_hypertable(
                    '{table_name}',
                    'timestamp',
                    chunk_time_interval => INTERVAL '1 month',
                    if_not_exists => TRUE
                );
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            CREATE EXTENSION IF NOT EXISTS timescaledb;
        EXCEPTION
            WHEN undefined_file THEN
                RAISE NOTICE 'timescaledb extension is not installed; continuing without hypertables';
        END
        $$;
        """
    )

    op.create_table(
        "generation_records",
        sa.Column("zone", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("wind_mw", sa.Float(), nullable=False, server_default="0"),
        sa.Column("solar_mw", sa.Float(), nullable=False, server_default="0"),
        sa.Column("hydro_mw", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_mw", sa.Float(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("zone", "timestamp"),
    )
    op.create_index("ix_generation_records_zone", "generation_records", ["zone"])
    op.create_index("ix_generation_records_timestamp", "generation_records", ["timestamp"])
    op.create_index(
        "idx_generation_records_zone_timestamp",
        "generation_records",
        ["zone", "timestamp"],
    )

    op.create_table(
        "load_records",
        sa.Column("zone", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("load_mw", sa.Float(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("zone", "timestamp"),
    )
    op.create_index("ix_load_records_zone", "load_records", ["zone"])
    op.create_index("ix_load_records_timestamp", "load_records", ["timestamp"])
    op.create_index("idx_load_records_zone_timestamp", "load_records", ["zone", "timestamp"])

    op.create_table(
        "price_records",
        sa.Column("zone", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("price_eur_mwh", sa.Float(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("zone", "timestamp"),
    )
    op.create_index("ix_price_records_zone", "price_records", ["zone"])
    op.create_index("ix_price_records_timestamp", "price_records", ["timestamp"])
    op.create_index(
        "idx_price_records_zone_timestamp",
        "price_records",
        ["zone", "timestamp"],
    )

    _create_hypertable("generation_records")
    _create_hypertable("load_records")
    _create_hypertable("price_records")


def downgrade() -> None:
    op.drop_index("idx_price_records_zone_timestamp", table_name="price_records")
    op.drop_index("ix_price_records_timestamp", table_name="price_records")
    op.drop_index("ix_price_records_zone", table_name="price_records")
    op.drop_table("price_records")

    op.drop_index("idx_load_records_zone_timestamp", table_name="load_records")
    op.drop_index("ix_load_records_timestamp", table_name="load_records")
    op.drop_index("ix_load_records_zone", table_name="load_records")
    op.drop_table("load_records")

    op.drop_index("idx_generation_records_zone_timestamp", table_name="generation_records")
    op.drop_index("ix_generation_records_timestamp", table_name="generation_records")
    op.drop_index("ix_generation_records_zone", table_name="generation_records")
    op.drop_table("generation_records")
