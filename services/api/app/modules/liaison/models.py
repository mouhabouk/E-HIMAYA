"""Informing the partner bodies by phone, OS20 (migration ``0106_liaison``, docs/phase-os20/design-os20.md)."""

import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

_SCHEMA = {"schema": "liaison"}


class Body(Base):
    """A body of the contact system. No gouvernorat: a national body, kept by the central room."""

    __tablename__ = "body"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    category: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text, server_default="external")
    agency: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    location: Mapped[object | None] = mapped_column(Geography("POINT", srid=4326))
    public_phone: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="active")
    origin_incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by_name: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by_name: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, server_default="1")


class Official(Base):
    """An official of a body, in calling order. The gouvernorat is copied from the body by a trigger."""

    __tablename__ = "official"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    body_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("liaison.body.id", ondelete="CASCADE"))
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    name: Mapped[str] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(Text)
    phones: Mapped[list[str]] = mapped_column(ARRAY(Text))
    email: Mapped[str | None] = mapped_column(Text)
    duty: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(SmallInteger, server_default="1")
    status: Mapped[str] = mapped_column(Text, server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by_name: Mapped[str | None] = mapped_column(Text)


class IncidentLevel(Base):
    """Level 1 (handled in the room) or 2 (bodies informed) of a report."""

    __tablename__ = "incident_level"
    __table_args__ = _SCHEMA

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="CASCADE"), primary_key=True
    )
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    level: Mapped[int] = mapped_column(SmallInteger)
    note: Mapped[str | None] = mapped_column(Text)
    set_by_name: Mapped[str | None] = mapped_column(Text)
    set_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Party(Base):
    """A body informed of a report. Names are copied: the history reads the same after the contact system changes."""

    __tablename__ = "party"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="CASCADE")
    )
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    body_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("liaison.body.id"))
    official_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("liaison.official.id", ondelete="SET NULL")
    )
    body_name: Mapped[str] = mapped_column(Text)
    official_name: Mapped[str | None] = mapped_column(Text)
    official_role: Mapped[str | None] = mapped_column(Text)
    suggested: Mapped[bool] = mapped_column(Boolean, server_default="false")
    reason: Mapped[str | None] = mapped_column(Text)
    added_by_name: Mapped[str | None] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_by_name: Mapped[str | None] = mapped_column(Text)


class Call(Base):
    """A call to a party: its result, what was asked and promised, the expected arrival, a follow-up."""

    __tablename__ = "call"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="CASCADE")
    )
    party_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("liaison.party.id", ondelete="CASCADE"))
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    official_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("liaison.official.id", ondelete="SET NULL")
    )
    official_name: Mapped[str | None] = mapped_column(Text)
    number: Mapped[str] = mapped_column(Text)
    via: Mapped[str] = mapped_column(Text)
    telephony_call_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("telephony.call.id", ondelete="SET NULL")
    )
    duration_s: Mapped[int | None] = mapped_column(Integer)
    result: Mapped[str] = mapped_column(Text)
    asked: Mapped[str | None] = mapped_column(Text)
    promised: Mapped[str | None] = mapped_column(Text)
    eta_min: Mapped[int | None] = mapped_column(SmallInteger)
    note: Mapped[str | None] = mapped_column(Text)
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    follow_up_done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    follow_up_done_by_name: Mapped[str | None] = mapped_column(Text)
    by_subject: Mapped[str] = mapped_column(Text)
    by_name: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
