"""Weather grid, hourly values, alert rules and suggested alerts (migration 0012)."""

import uuid
from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class GridPoint(Base):
    __tablename__ = "grid_point"
    __table_args__ = {"schema": "weather"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    location: Mapped[object] = mapped_column(Geography("POINT", srid=4326))
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    codes: Mapped[dict[str, float] | None] = mapped_column(JSONB)
    codes_date: Mapped[date | None] = mapped_column(Date)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_fetch_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    source: Mapped[str | None] = mapped_column(Text)
    simulated: Mapped[bool] = mapped_column(Boolean, server_default="false")


class Observation(Base):
    __tablename__ = "observation"
    __table_args__ = {"schema": "weather"}

    point_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("weather.grid_point.id", ondelete="CASCADE"), primary_key=True
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    temperature_c: Mapped[float | None] = mapped_column(Float(precision=24))
    relative_humidity_pct: Mapped[float | None] = mapped_column(Float(precision=24))
    wind_speed_kmh: Mapped[float | None] = mapped_column(Float(precision=24))
    wind_gust_kmh: Mapped[float | None] = mapped_column(Float(precision=24))
    wind_direction_deg: Mapped[float | None] = mapped_column(Float(precision=24))
    precipitation_mm: Mapped[float | None] = mapped_column(Float(precision=24))
    precipitation_24h_mm: Mapped[float | None] = mapped_column(Float(precision=24))
    weather_code: Mapped[int | None] = mapped_column(SmallInteger)
    ffmc: Mapped[float | None] = mapped_column(Float(precision=24))
    dmc: Mapped[float | None] = mapped_column(Float(precision=24))
    dc: Mapped[float | None] = mapped_column(Float(precision=24))
    isi: Mapped[float | None] = mapped_column(Float(precision=24))
    bui: Mapped[float | None] = mapped_column(Float(precision=24))
    fwi: Mapped[float | None] = mapped_column(Float(precision=24))
    fire_danger: Mapped[str | None] = mapped_column(Text)
    heavy_rain: Mapped[str] = mapped_column(Text, server_default="none")
    forecast: Mapped[bool] = mapped_column(Boolean, server_default="true")


class Rule(Base):
    __tablename__ = "rule"
    __table_args__ = {"schema": "weather"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    metric: Mapped[str] = mapped_column(Text)
    threshold: Mapped[float] = mapped_column(Float(precision=24))
    severity: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    updated_by: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlertSuggestion(Base):
    __tablename__ = "alert_suggestion"
    __table_args__ = {"schema": "weather"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric: Mapped[str] = mapped_column(Text)
    gouvernorat_codes: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger))
    category: Mapped[str] = mapped_column(Text, server_default="weather")
    hazard: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text)
    title: Mapped[dict[str, str]] = mapped_column(JSONB)
    body: Mapped[dict[str, str]] = mapped_column(JSONB)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    simulated: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_by: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismiss_reason: Mapped[str | None] = mapped_column(Text)
