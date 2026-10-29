"""Drone positions, the zones the rooms draw, and the alerts they raise (L5b, design-l5.md §3.3), migration 0071."""

import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DroneZone(Base):
    """A work area or a no-fly zone of a gouvernorat (airport, plant…), drawn by its room."""

    __tablename__ = "drone_zone"
    __table_args__ = {"schema": "reports"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    kind: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    area: Mapped[object] = mapped_column(Geography("POLYGON", srid=4326))
    margin_m: Mapped[int] = mapped_column(Integer, server_default="500")
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DroneTelemetry(Base):
    """Where a drone was, read from its stream or a bridge; (drone, at) is unique."""

    __tablename__ = "drone_telemetry"
    __table_args__ = {"schema": "reports"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stream_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("reports.live_stream.id"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lat: Mapped[float] = mapped_column(Float(precision=53))
    lon: Mapped[float] = mapped_column(Float(precision=53))
    alt_m: Mapped[float | None] = mapped_column(Float(precision=24))
    heading_deg: Mapped[float | None] = mapped_column(Float(precision=24))
    sensor_az_deg: Mapped[float | None] = mapped_column(Float(precision=24))
    sensor_hfov_deg: Mapped[float | None] = mapped_column(Float(precision=24))
    battery_pct: Mapped[float | None] = mapped_column(Float(precision=24))
    mode: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DroneAlert(Base):
    __tablename__ = "drone_alert"
    __table_args__ = {"schema": "reports"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stream_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("reports.live_stream.id"))
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    kind: Mapped[str] = mapped_column(Text)
    zone_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("reports.drone_zone.id"))
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    acknowledged_by: Mapped[str | None] = mapped_column(Text)
    acknowledged_by_name: Mapped[str | None] = mapped_column(Text)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
