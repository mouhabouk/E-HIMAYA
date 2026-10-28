"""Sensors read on the local network (L5b, docs/phase-l/design-l5.md §3.0 and §3.1), migration 0069."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, LargeBinary, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class SensorDevice(Base):
    """A rain gauge, water level or thermometer, with its thresholds and its signing key (encrypted)."""

    __tablename__ = "device"
    __table_args__ = {"schema": "sensor"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    code: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    lat: Mapped[float] = mapped_column(Float(precision=53))
    lon: Mapped[float] = mapped_column(Float(precision=53))
    provider: Mapped[str] = mapped_column(Text)
    watch_threshold: Mapped[float] = mapped_column(Float(precision=53))
    alarm_threshold: Mapped[float] = mapped_column(Float(precision=53))
    silent_after_min: Mapped[int] = mapped_column(SmallInteger, server_default="30")
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    simulated: Mapped[bool] = mapped_column(Boolean, server_default="true")
    key_enc: Mapped[bytes] = mapped_column(LargeBinary)
    key_version: Mapped[int] = mapped_column(SmallInteger, server_default="1")
    last_value: Mapped[float | None] = mapped_column(Float(precision=53))
    last_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    level: Mapped[str] = mapped_column(Text, server_default="normal")
    level_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SensorReading(Base):
    """One signed reading relayed by the gateway beside MediaMTX; (sensor, at) is unique against replays."""

    __tablename__ = "reading"
    __table_args__ = {"schema": "sensor"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sensor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sensor.device.id"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    value: Mapped[float] = mapped_column(Float(precision=53))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
