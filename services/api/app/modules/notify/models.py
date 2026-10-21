import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geography, Geometry
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

_SCHEMA = {"schema": "notify"}


class Device(Base):
    """A phone that receives pushes: FCM token, owner account, coarse position for location alerts."""

    __tablename__ = "device"
    __table_args__ = _SCHEMA

    token: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.account.user_id", ondelete="CASCADE")
    )
    platform: Mapped[str] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(Text, server_default="ar")
    location: Mapped[object | None] = mapped_column(Geography("POINT", srid=4326))
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Message(Base):
    """An informational notification (FR-C-17) or an urgent geographic alert (FR-C-18)."""

    __tablename__ = "message"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    kind: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="draft")
    title: Mapped[dict[str, str]] = mapped_column(JSONB)
    body: Mapped[dict[str, str]] = mapped_column(JSONB)
    channels: Mapped[list[str]] = mapped_column(ARRAY(Text))
    topic: Mapped[str | None] = mapped_column(Text)
    audience: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.account.user_id", ondelete="SET NULL")
    )
    severity: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    hazard: Mapped[str | None] = mapped_column(Text)
    area_polygon: Mapped[object | None] = mapped_column(Geometry("POLYGON", srid=4326))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gouvernorat_codes: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), server_default="{}")
    creator_scope: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_by: Mapped[str | None] = mapped_column(Text)
    published_by_name: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    # Four eyes (phase 10 §5.1): last editor, emergency override and the acknowledgement afterwards.
    updated_by: Mapped[str | None] = mapped_column(Text)
    updated_by_name: Mapped[str | None] = mapped_column(Text)
    single_reviewer: Mapped[bool] = mapped_column(Boolean, server_default="false")
    emergency_reason: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    reviewed_by_name: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Dispatch(Base):
    """Fan-out of one message on one channel, resumable from its cursor."""

    __tablename__ = "dispatch"
    __table_args__ = _SCHEMA

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notify.message.id", ondelete="CASCADE"), primary_key=True
    )
    channel: Mapped[str] = mapped_column(Text, primary_key=True)
    purpose: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    cursor: Mapped[str | None] = mapped_column(Text)
    sent: Mapped[int] = mapped_column(Integer, server_default="0")
    failed: Mapped[int] = mapped_column(Integer, server_default="0")
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class Outbox(Base):
    """One push to an account's devices or one e-mail, sent after commit with retries."""

    __tablename__ = "outbox"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    channel: Mapped[str] = mapped_column(Text)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.account.user_id", ondelete="CASCADE")
    )
    address: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    last_error: Mapped[str | None] = mapped_column(Text)


class OrgDigest(Base):
    __tablename__ = "digest"
    __table_args__ = {"schema": "org"}

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org.organization.id", ondelete="CASCADE"), primary_key=True
    )
    fingerprint: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
