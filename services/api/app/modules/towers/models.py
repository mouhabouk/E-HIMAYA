"""Watch towers and the events their edge computers confirm (L5b, docs/phase-l/design-l5.md §3.2), migration 0070."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CameraTower(Base):
    """The tower of a fixed camera: place, bearing, field of view, range, and its edge signing key (encrypted)."""

    __tablename__ = "camera_tower"
    __table_args__ = {"schema": "reports"}

    stream_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.live_stream.id", ondelete="CASCADE"), primary_key=True
    )
    code: Mapped[str] = mapped_column(Text)
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    lat: Mapped[float] = mapped_column(Float(precision=53))
    lon: Mapped[float] = mapped_column(Float(precision=53))
    bearing_deg: Mapped[int] = mapped_column(SmallInteger)
    fov_deg: Mapped[int] = mapped_column(SmallInteger)
    range_m: Mapped[int] = mapped_column(Integer)
    simulated: Mapped[bool] = mapped_column(Boolean, server_default="true")
    key_enc: Mapped[bytes] = mapped_column(LargeBinary)
    key_version: Mapped[int] = mapped_column(SmallInteger, server_default="1")
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TowerEvent(Base):
    """A fire or smoke confirmed on the tower (3 of 5 frames), signed; (tower, at, label) is unique against replays."""

    __tablename__ = "tower_event"
    __table_args__ = {"schema": "reports"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stream_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("reports.camera_tower.stream_id"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    label: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float(precision=24))
    hits: Mapped[int] = mapped_column(SmallInteger)
    frames: Mapped[int] = mapped_column(SmallInteger)
    model: Mapped[str | None] = mapped_column(Text)
    media_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("reports.media.id"))
    suggestion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weather.alert_suggestion.id")
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
