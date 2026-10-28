"""Disaster and crisis axis tables (migration 0056, phase L3, docs/phase-l/design-l3.md)."""

import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

_S = {"schema": "crisis"}


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())


def _axis_fk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), ForeignKey("crisis.axis.id", ondelete="CASCADE"))


class Axis(Base):
    __tablename__ = "axis"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = _pk()
    number: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    # gouvernorat (a regional axis or the sub-axis of a national one) | national (a root without gouvernorat).
    scope: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crisis.axis.id", ondelete="CASCADE")
    )
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    area: Mapped[object | None] = mapped_column(Geography("MULTIPOLYGON", srid=4326))
    level: Mapped[int] = mapped_column(SmallInteger)
    plan: Mapped[str] = mapped_column(Text, server_default="")
    # The plan in force as a document of the register (phase L3b); ``plan`` keeps a plan that is not recorded.
    plan_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("register.document.id", ondelete="SET NULL", use_alter=True)
    )
    status: Mapped[str] = mapped_column(Text, server_default="open")
    request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    opened_by: Mapped[str] = mapped_column(Text)
    opened_by_name: Mapped[str | None] = mapped_column(Text)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_by: Mapped[str | None] = mapped_column(Text)
    closed_by_name: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closing: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    next_sitrep_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    memory_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Counter(Base):
    __tablename__ = "counter"
    __table_args__ = _S

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last: Mapped[int] = mapped_column(Integer)


class DeclarationRequest(Base):
    __tablename__ = "request"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = _pk()
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    level: Mapped[int] = mapped_column(SmallInteger)
    facts: Mapped[str] = mapped_column(Text)
    incident_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), server_default="{}")
    area: Mapped[object | None] = mapped_column(Geography("MULTIPOLYGON", srid=4326))
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_by: Mapped[str | None] = mapped_column(Text)
    decided_by_name: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    axis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crisis.axis.id", ondelete="SET NULL")
    )


class AxisIncident(Base):
    __tablename__ = "axis_incident"
    __table_args__ = _S

    axis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crisis.axis.id", ondelete="CASCADE"), primary_key=True
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="CASCADE"), primary_key=True
    )
    attached_by: Mapped[str] = mapped_column(Text)
    attached_by_name: Mapped[str | None] = mapped_column(Text)
    attached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    detached_by: Mapped[str | None] = mapped_column(Text)
    detached_by_name: Mapped[str | None] = mapped_column(Text)
    detached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detach_reason: Mapped[str | None] = mapped_column(Text)


class Dismissal(Base):
    __tablename__ = "dismissal"
    __table_args__ = _S

    axis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crisis.axis.id", ondelete="CASCADE"), primary_key=True
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="CASCADE"), primary_key=True
    )
    dismissed_by: Mapped[str] = mapped_column(Text)
    dismissed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Shelter(Base):
    __tablename__ = "shelter"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = _pk()
    axis_id: Mapped[uuid.UUID] = _axis_fk()
    name: Mapped[str] = mapped_column(Text)
    location: Mapped[object | None] = mapped_column(Geography("POINT", srid=4326))
    capacity: Mapped[int] = mapped_column(Integer)
    occupants: Mapped[int] = mapped_column(Integer, server_default="0")
    updated_by: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Evacuation(Base):
    __tablename__ = "evacuation"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = _pk()
    axis_id: Mapped[uuid.UUID] = _axis_fk()
    name: Mapped[str] = mapped_column(Text)
    area: Mapped[object | None] = mapped_column(Geography("MULTIPOLYGON", srid=4326))
    evacuated: Mapped[int] = mapped_column(Integer, server_default="0")
    updated_by: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Need(Base):
    __tablename__ = "need"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = _pk()
    axis_id: Mapped[uuid.UUID] = _axis_fk()
    label: Mapped[str] = mapped_column(Text)
    quantity: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, server_default="raised")
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    met_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Directive(Base):
    __tablename__ = "directive"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = _pk()
    axis_id: Mapped[uuid.UUID] = _axis_fk()
    number: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    area: Mapped[object | None] = mapped_column(Geography("MULTIPOLYGON", srid=4326))
    executor: Mapped[str] = mapped_column(Text)
    executor_name: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, server_default="issued")
    status_reason: Mapped[str | None] = mapped_column(Text)
    issuer_role: Mapped[str] = mapped_column(Text)
    issued_by: Mapped[str] = mapped_column(Text)
    issued_by_name: Mapped[str | None] = mapped_column(Text)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    signature: Mapped[str | None] = mapped_column(Text)
    key_id: Mapped[str | None] = mapped_column(Text)
    overridden_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("crisis.directive.id"))
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    overdue_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DirectiveEvent(Base):
    __tablename__ = "directive_event"
    __table_args__ = _S

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    directive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crisis.directive.id", ondelete="CASCADE")
    )
    axis_id: Mapped[uuid.UUID] = _axis_fk()
    status: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    by_actor: Mapped[str] = mapped_column(Text)
    by_name: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Sitrep(Base):
    __tablename__ = "sitrep"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = _pk()
    axis_id: Mapped[uuid.UUID] = _axis_fk()
    number: Mapped[int] = mapped_column(Integer)
    figures: Mapped[dict[str, Any]] = mapped_column(JSONB)
    assessment: Mapped[str] = mapped_column(Text, server_default="")
    status: Mapped[str] = mapped_column(Text, server_default="draft")
    created_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_by: Mapped[str | None] = mapped_column(Text)
    sent_by_name: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AxisEvent(Base):
    __tablename__ = "event"
    __table_args__ = _S

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    axis_id: Mapped[uuid.UUID] = _axis_fk()
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor: Mapped[str] = mapped_column(Text)
    actor_name: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
