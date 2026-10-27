"""Coastal safety tables (migration 0054, phase L1b)."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, LargeBinary, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Beach(Base):
    __tablename__ = "beach"
    __table_args__ = {"schema": "coastal"}

    feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("geo.layer_feature.id", ondelete="CASCADE"), primary_key=True
    )
    seaward_deg: Mapped[float | None] = mapped_column(Float(precision=24))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_fetch_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    source: Mapped[str | None] = mapped_column(Text)
    simulated: Mapped[bool] = mapped_column(Boolean, server_default="false")


class MarineHour(Base):
    __tablename__ = "marine_hour"
    __table_args__ = {"schema": "coastal"}

    feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coastal.beach.feature_id", ondelete="CASCADE"), primary_key=True
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    wave_height_m: Mapped[float | None] = mapped_column(Float(precision=24))
    wave_period_s: Mapped[float | None] = mapped_column(Float(precision=24))
    wave_direction_deg: Mapped[float | None] = mapped_column(Float(precision=24))
    sea_temp_c: Mapped[float | None] = mapped_column(Float(precision=24))
    current_kmh: Mapped[float | None] = mapped_column(Float(precision=24))
    current_direction_deg: Mapped[float | None] = mapped_column(Float(precision=24))


class BeachDay(Base):
    __tablename__ = "beach_day"
    __table_args__ = {"schema": "coastal"}

    feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coastal.beach.feature_id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    score: Mapped[int] = mapped_column(SmallInteger)
    level: Mapped[str] = mapped_column(Text)
    factors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    source: Mapped[str | None] = mapped_column(Text)
    simulated: Mapped[bool] = mapped_column(Boolean, server_default="false")
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CoastalAlert(Base):
    __tablename__ = "alert"
    __table_args__ = {"schema": "coastal"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coastal.beach.feature_id", ondelete="CASCADE")
    )
    day: Mapped[date] = mapped_column(Date)
    level: Mapped[str] = mapped_column(Text)
    previous_level: Mapped[str | None] = mapped_column(Text)
    score: Mapped[int] = mapped_column(SmallInteger)
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    simulated: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    acked_by: Mapped[str | None] = mapped_column(Text)
    acked_by_name: Mapped[str | None] = mapped_column(Text)
    acked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CoastalSettings(Base):
    __tablename__ = "settings"
    __table_args__ = {"schema": "coastal"}

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    rules: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    updated_by: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Presence(Base):
    __tablename__ = "presence"
    __table_args__ = {"schema": "coastal"}

    feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coastal.beach.feature_id", ondelete="CASCADE"), primary_key=True
    )
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
