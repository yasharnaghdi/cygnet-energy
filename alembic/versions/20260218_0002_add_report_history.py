"""add report history tables

Revision ID: 20260218_0002
Revises: 20260215_0001
Create Date: 2026-02-18 03:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260218_0002"
down_revision = "20260215_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index("idx_report_sessions_created_at", "report_sessions", ["created_at"], unique=False)
    op.create_index("idx_report_sessions_user_id", "report_sessions", ["user_id"], unique=False)

    op.create_table(
        "report_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("persona", sa.String(length=50), nullable=False),
        sa.Column("zone", sa.String(length=10), nullable=False),
        sa.Column("scenario", sa.String(length=100), nullable=True),
        sa.Column("date_range_start", sa.Date(), nullable=True),
        sa.Column("date_range_end", sa.Date(), nullable=True),
        sa.Column("parameter_weights", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("backend", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("generation_time_ms", sa.Float(), nullable=True),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("data_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_favorite", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["report_sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id"),
    )
    op.create_index("idx_report_history_generated_at", "report_history", ["generated_at"], unique=False)
    op.create_index("idx_report_history_is_favorite", "report_history", ["is_favorite"], unique=False)
    op.create_index("idx_report_history_persona", "report_history", ["persona"], unique=False)
    op.create_index("idx_report_history_session_id", "report_history", ["session_id"], unique=False)
    op.create_index("idx_report_history_zone", "report_history", ["zone"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_report_history_zone", table_name="report_history")
    op.drop_index("idx_report_history_session_id", table_name="report_history")
    op.drop_index("idx_report_history_persona", table_name="report_history")
    op.drop_index("idx_report_history_is_favorite", table_name="report_history")
    op.drop_index("idx_report_history_generated_at", table_name="report_history")
    op.drop_table("report_history")

    op.drop_index("idx_report_sessions_user_id", table_name="report_sessions")
    op.drop_index("idx_report_sessions_created_at", table_name="report_sessions")
    op.drop_table("report_sessions")
