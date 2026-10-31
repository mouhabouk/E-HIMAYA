"""Live streams, their position track, vision detections and the recording-segment queue (migration 0011)."""

import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class LiveStream(Base):
    __tablename__ = "live_stream"
    __table_args__ = {"schema": "reports"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.report.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.account.user_id"))
    source: Mapped[str] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(Text)
    path: Mapped[str] = mapped_column(Text, unique=True)
    # HMAC of the publish token (app.core.crypto blind index); never the token itself. NULL = cannot publish.
    publish_token_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_reason: Mapped[str | None] = mapped_column(Text)
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    last_location: Mapped[object | None] = mapped_column(Geography("POINT", srid=4326))
    last_location_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_fire_confidence: Mapped[float | None] = mapped_column(Float(precision=24))
    max_smoke_confidence: Mapped[float | None] = mapped_column(Float(precision=24))
    # Start deadline of a citizen's publish token (pending → expired after it).
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Staff member who registered a fixed source.
    created_by: Mapped[str | None] = mapped_column(Text)
    # Last stream.location event sent to the dashboards (throttle).
    location_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    segment_seq: Mapped[int] = mapped_column(Integer, server_default="0")
    # idle → requested (live, vision asked to watch) → watching → stopping (ended) → idle; disabled = no service.
    vision_state: Mapped[str] = mapped_column(Text, server_default="idle")
    vision_attempts: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    vision_next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Last analysed frames [{"at", "fire", "smoke"}] (3-of-5 confirmation) and the last alert per label.
    vision_frames: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    vision_alerts: Mapped[dict[str, str]] = mapped_column(JSONB, server_default="{}")
    # A camera of an institution (phase D, review point 25): its detections go to the owner first (org.prealert).
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org.organization.id", ondelete="SET NULL")
    )
    # A team's stream (phase D, review point 17): the mission and its incident.
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.assignment.id", ondelete="SET NULL")
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="SET NULL")
    )


class StreamLocation(Base):
    __tablename__ = "stream_location"
    __table_args__ = {"schema": "reports"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    stream_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.live_stream.id", ondelete="CASCADE")
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    location: Mapped[object] = mapped_column(Geography("POINT", srid=4326))
    accuracy_m: Mapped[float | None] = mapped_column(Float(precision=24))


class StreamDetection(Base):
    __tablename__ = "stream_detection"
    __table_args__ = {"schema": "reports"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    stream_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.live_stream.id", ondelete="CASCADE")
    )
    media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.media.id", ondelete="CASCADE")
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    label: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float(precision=24))
    # [[x1, y1, x2, y2, conf], …], coordinates normalised to 0..1.
    boxes: Mapped[list[list[float]]] = mapped_column(JSONB, server_default="[]")
    model: Mapped[str | None] = mapped_column(Text)
    confirmed: Mapped[bool] = mapped_column(Boolean, server_default="false")


class StreamSegment(Base):
    __tablename__ = "stream_segment"
    __table_args__ = {"schema": "reports"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    stream_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.live_stream.id", ondelete="CASCADE")
    )
    segment_path: Mapped[str] = mapped_column(Text, unique=True)
    seq: Mapped[int] = mapped_column(Integer)
    duration_s: Mapped[float | None] = mapped_column(Float(precision=24))
    state: Mapped[str] = mapped_column(Text, server_default="pending")
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.media.id", ondelete="SET NULL")
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
