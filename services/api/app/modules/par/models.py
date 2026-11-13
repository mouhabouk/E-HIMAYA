"""Crew accountability in danger zones, OS7 (migration ``0107_par``)."""

import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

_SCHEMA = {"schema": "par"}


class Setting(Base):
    """The intervals of a gouvernorat (the operations commander and the regional room change them)."""

    __tablename__ = "setting"
    __table_args__ = _SCHEMA

    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"), primary_key=True)
    hot_s: Mapped[int] = mapped_column(Integer)
    warm_s: Mapped[int] = mapped_column(Integer)
    grace_s: Mapped[int] = mapped_column(Integer)
    auto_events: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by_name: Mapped[str | None] = mapped_column(Text)


class Team(Base):
    """A team inside a danger zone: one assignment of the vehicle a leader holds on shift."""

    __tablename__ = "team"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.assignment.id"))
    incident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.incident.id"))
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    label: Mapped[str] = mapped_column(Text)
    task: Mapped[str | None] = mapped_column(Text)
    zone: Mapped[str] = mapped_column(Text)
    # [{"key": "m1", "name": "...", "role": "..."}]; the leader is "m0".
    members: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    # {"m3": {"why": "air", "at": "2026-11-13T10:00:00+00:00"}}
    away: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    leader_subject: Mapped[str] = mapped_column(Text)
    leader_name: Mapped[str | None] = mapped_column(Text)
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    next_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pause_reason: Mapped[str | None] = mapped_column(Text)
    alarmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    out_count: Mapped[int | None] = mapped_column(SmallInteger)


class Missing(Base):
    """A missing resource or piece of equipment, and who had it."""

    __tablename__ = "missing"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    team_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("par.team.id"))
    incident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.incident.id"))
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    resource: Mapped[str] = mapped_column(Text)
    carrier: Mapped[str] = mapped_column(Text)
    place: Mapped[str | None] = mapped_column(Text)
    location: Mapped[object | None] = mapped_column(Geography("POINT", srid=4326))
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reported_by_name: Mapped[str | None] = mapped_column(Text)
    replacement_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replacement_by_name: Mapped[str | None] = mapped_column(Text)
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recovered_by_name: Mapped[str | None] = mapped_column(Text)


class Sitrep(Base):
    """The team leader's word from the scene."""

    __tablename__ = "sitrep"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("par.team.id"))
    incident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.incident.id"))
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    situation: Mapped[str] = mapped_column(Text)
    reinforcement: Mapped[bool] = mapped_column(Boolean, server_default="false")
    text: Mapped[str | None] = mapped_column(Text)
    voice_seconds: Mapped[int | None] = mapped_column(SmallInteger)
    transcript: Mapped[str | None] = mapped_column(Text)
    by_name: Mapped[str | None] = mapped_column(Text)


class Event(Base):
    """A line of the check's log."""

    __tablename__ = "event"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.incident.id"))
    team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("par.team.id"))
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    kind: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    by_name: Mapped[str | None] = mapped_column(Text)


class Closure(Base):
    """The end of the check of an incident: archived with the intervention, off the live follow-up."""

    __tablename__ = "closure"
    __table_args__ = _SCHEMA

    incident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.incident.id"), primary_key=True)
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_by_name: Mapped[str | None] = mapped_column(Text)
    automatic: Mapped[bool] = mapped_column(Boolean, server_default="false")
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
