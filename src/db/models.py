from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class GenerationRecord(Base):
    __tablename__ = "generation_records"
    __table_args__ = (
        Index("idx_generation_records_zone_timestamp", "zone", "timestamp"),
    )

    zone: Mapped[str] = mapped_column(Text, primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, index=True)
    wind_mw: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    solar_mw: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    hydro_mw: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_mw: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class LoadRecord(Base):
    __tablename__ = "load_records"
    __table_args__ = (
        Index("idx_load_records_zone_timestamp", "zone", "timestamp"),
    )

    zone: Mapped[str] = mapped_column(Text, primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, index=True)
    load_mw: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class PriceRecord(Base):
    __tablename__ = "price_records"
    __table_args__ = (
        Index("idx_price_records_zone_timestamp", "zone", "timestamp"),
    )

    zone: Mapped[str] = mapped_column(Text, primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, index=True)
    price_eur_mwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class ReportSession(Base):
    __tablename__ = "report_sessions"
    __table_args__ = (
        Index("idx_report_sessions_created_at", "created_at"),
        Index("idx_report_sessions_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=func.now(),
    )

    reports: Mapped[list["ReportHistory"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class ReportHistory(Base):
    __tablename__ = "report_history"
    __table_args__ = (
        Index("idx_report_history_session_id", "session_id"),
        Index("idx_report_history_persona", "persona"),
        Index("idx_report_history_zone", "zone"),
        Index("idx_report_history_generated_at", "generated_at"),
        Index("idx_report_history_is_favorite", "is_favorite"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    report_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    persona: Mapped[str] = mapped_column(String(50), nullable=False)
    zone: Mapped[str] = mapped_column(String(10), nullable=False)
    scenario: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_range_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_range_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    parameter_weights: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    backend: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    generation_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    data_summary: Mapped[dict] = mapped_column(JSONB, nullable=False)

    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_favorite: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    session: Mapped["ReportSession"] = relationship(back_populates="reports")
