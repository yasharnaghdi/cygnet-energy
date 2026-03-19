"""add tenant_id to tenant-scoped tables

Revision ID: 20260318_0005
Revises: 20260314_0004
Create Date: 2026-03-18 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError

from alembic import op
from src.db.constants import SEED_TENANT_ID

# revision identifiers, used by Alembic.
revision = "20260318_0005"
down_revision = "20260314_0004"
branch_labels = None
depends_on = None


TABLES: tuple[str, ...] = (
    "generation_records",
    "load_records",
    "price_records",
    "report_history",
    "regime_states",
    "canonical_metrics",
)

def _add_tenant_column(table_name: str) -> None:
    op.execute(
        sa.text(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN IF NOT EXISTS tenant_id UUID NOT NULL DEFAULT '{SEED_TENANT_ID}'
            """
        )
    )


def _create_index_concurrently(table_name: str) -> None:
    index_name = f"ix_{table_name}_tenant_id"
    try:
        with op.get_context().autocommit_block():
            op.execute(
                sa.text(
                    f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name} "
                    f"ON {table_name}(tenant_id)"
                )
            )
    except DBAPIError as exc:
        error_text = str(getattr(exc, "orig", exc)).lower()
        if "hypertables do not support concurrent index creation" not in error_text:
            raise
        op.execute(
            sa.text(
                f"CREATE INDEX IF NOT EXISTS {index_name} "
                f"ON {table_name}(tenant_id)"
            )
        )


def _drop_index_concurrently(table_name: str) -> None:
    index_name = f"ix_{table_name}_tenant_id"
    with op.get_context().autocommit_block():
        op.execute(sa.text(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}"))


def upgrade() -> None:
    for table_name in TABLES:
        _add_tenant_column(table_name)

    for table_name in TABLES:
        _create_index_concurrently(table_name)


def downgrade() -> None:
    for table_name in TABLES:
        _drop_index_concurrently(table_name)

    for table_name in TABLES:
        op.execute(sa.text(f"ALTER TABLE {table_name} DROP COLUMN IF EXISTS tenant_id"))
