"""Periodic inspections of the units, phase I1 (migration 0102, docs/phase-i/design-i.md)."""

import uuid
from datetime import date, datetime, time
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, LargeBinary, SmallInteger, Text, Time, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

_SCHEMA = {"schema": "insp"}


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())


class Inspector(Base):
    """An inspector's app account: registered from the app, activated by the inspector general, one phone."""

    __tablename__ = "inspector"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = _uuid_pk()
    kind: Mapped[str] = mapped_column(Text)
    matricule: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    organisation: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    via: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    expires_on: Mapped[date | None] = mapped_column(Date)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inv.agent.id", ondelete="SET NULL")
    )
    requested_device: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by_name: Mapped[str | None] = mapped_column(Text)
    reject_reason: Mapped[str | None] = mapped_column(Text)
    code_hash: Mapped[str | None] = mapped_column(Text)
    code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    code_attempts: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    device_model: Mapped[str | None] = mapped_column(Text)
    device_platform: Mapped[str | None] = mapped_column(Text)
    device_ref: Mapped[str | None] = mapped_column(Text)
    push_token: Mapped[str | None] = mapped_column(Text)
    refresh_hash: Mapped[str | None] = mapped_column(Text)
    refresh_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lost_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default="1")


class Profile(Base):
    """A version of the calculation model; one is active."""

    __tablename__ = "profile"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, server_default="false")
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderNote(Base):
    """A general recommendation printed on every mission order."""

    __tablename__ = "order_note"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = _uuid_pk()
    position: Mapped[int] = mapped_column(SmallInteger)
    text: Mapped[str] = mapped_column(Text)


class Policy(Base):
    """The disclosure applied to every new inspection (one row)."""

    __tablename__ = "policy"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, server_default="1")
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_by_name: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Mission(Base):
    """A mission order: one inspector, a date and time, one or more units."""

    __tablename__ = "mission"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = _uuid_pk()
    ref: Mapped[str] = mapped_column(Text)
    on_date: Mapped[date] = mapped_column(Date)
    at_time: Mapped[time] = mapped_column(Time)
    kind: Mapped[str] = mapped_column(Text)
    inspector_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("insp.inspector.id"))
    status: Mapped[str] = mapped_column(Text, server_default="planned")
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    published: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MissionSite(Base):
    """One unit of a mission order, with the sections to inspect."""

    __tablename__ = "mission_site"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = _uuid_pk()
    mission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("insp.mission.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(SmallInteger)
    target: Mapped[str] = mapped_column(Text)
    unit_kind: Mapped[str | None] = mapped_column(Text)
    unit_name: Mapped[str | None] = mapped_column(Text)
    unit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.unit.id"))
    room: Mapped[str | None] = mapped_column(Text)
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    sections: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")


class Inspection(Base):
    """The report of one unit; sealed once signed and sent."""

    __tablename__ = "inspection"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = _uuid_pk()
    mission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("insp.mission.id"))
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("insp.mission_site.id"))
    target: Mapped[str] = mapped_column(Text)
    unit_kind: Mapped[str | None] = mapped_column(Text)
    unit_name: Mapped[str | None] = mapped_column(Text)
    unit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.unit.id"))
    room: Mapped[str | None] = mapped_column(Text)
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    inspector_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("insp.inspector.id"))
    kind: Mapped[str] = mapped_column(Text)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("insp.profile.id"))
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, server_default="in_progress")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[object | None] = mapped_column(Geography("POINT", srid=4326))
    answers: Mapped[dict[str, str]] = mapped_column(JSONB, server_default="{}")
    present: Mapped[int | None] = mapped_column(SmallInteger)
    expected: Mapped[int | None] = mapped_column(SmallInteger)
    exit_seconds: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[int | None] = mapped_column(SmallInteger)
    verdict: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    head_name: Mapped[str | None] = mapped_column(Text)
    inspector_sig: Mapped[bytes | None] = mapped_column(LargeBinary)
    head_sig: Mapped[bytes | None] = mapped_column(LargeBinary)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    receipt: Mapped[str | None] = mapped_column(Text)
    disclosure: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by_name: Mapped[str | None] = mapped_column(Text)
    delete_reason: Mapped[str | None] = mapped_column(Text)


class Recommendation(Base):
    """A recommendation of a report and the rooms it is disclosed to."""

    __tablename__ = "recommendation"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = _uuid_pk()
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insp.inspection.id", ondelete="CASCADE")
    )
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    position: Mapped[int] = mapped_column(SmallInteger)
    kind: Mapped[str] = mapped_column(Text)
    item_key: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    priority: Mapped[str | None] = mapped_column(Text)
    to_central: Mapped[bool] = mapped_column(Boolean, server_default="false")
    to_regional: Mapped[bool] = mapped_column(Boolean, server_default="false")
