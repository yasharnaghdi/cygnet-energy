from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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
