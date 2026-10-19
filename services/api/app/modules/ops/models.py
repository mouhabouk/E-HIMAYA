import enum
import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class OpLevel(enum.StrEnum):
    NORMAL = "normal"
    CRISIS = "crisis"
    DISASTER = "disaster"


class Incident(Base):
    __tablename__ = "incident"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    category: Mapped[str] = mapped_column(Text)
    severity: Mapped[int | None] = mapped_column(SmallInteger)
    centroid: Mapped[object | None] = mapped_column(Geography("POINT", srid=4326))
    area: Mapped[object | None] = mapped_column(Geography("POLYGON", srid=4326))
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    delegation_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("geo.delegation.id"))
    op_level: Mapped[OpLevel] = mapped_column(
        Enum(OpLevel, name="op_level", schema="ops", values_callable=lambda e: [m.value for m in e]),
        server_default=OpLevel.NORMAL.value,
    )
    status: Mapped[str] = mapped_column(Text, server_default="open")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_into: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.incident.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Incident card and closing evaluation (FR-C-09, phase 5).
    title: Mapped[str | None] = mapped_column(Text)
    classification: Mapped[str | None] = mapped_column(Text)
    evaluation: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class TimelineEvent(Base):
    __tablename__ = "timeline_event"
    __table_args__ = {"schema": "ops"}

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="CASCADE")
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")


_LEVEL_ENUM = Enum(OpLevel, name="op_level", schema="ops", values_callable=lambda e: [m.value for m in e])


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())


class LevelState(Base):
    """Operational level of one gouvernorat (requirements §6.4)."""

    __tablename__ = "level_state"
    __table_args__ = {"schema": "ops"}

    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"), primary_key=True)
    level: Mapped[OpLevel] = mapped_column(_LEVEL_ENUM, server_default=OpLevel.NORMAL.value)
    since: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reason: Mapped[str | None] = mapped_column(Text)
    set_by: Mapped[str | None] = mapped_column(Text)
    set_by_name: Mapped[str | None] = mapped_column(Text)


class Directive(Base):
    __tablename__ = "directive"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    urgency: Mapped[str] = mapped_column(Text)
    from_level: Mapped[str] = mapped_column(Text)
    gouvernorat_codes: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), server_default="{}")
    issuer_scope: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    issued_by: Mapped[str] = mapped_column(Text)
    issued_by_name: Mapped[str | None] = mapped_column(Text)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DirectiveAck(Base):
    __tablename__ = "directive_ack"
    __table_args__ = {"schema": "ops"}

    directive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.directive.id", ondelete="CASCADE"), primary_key=True
    )
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"), primary_key=True)
    acked_by: Mapped[str] = mapped_column(Text)
    acked_by_name: Mapped[str | None] = mapped_column(Text)
    acked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    note: Mapped[str | None] = mapped_column(Text)


class Unit(Base):
    """A civil protection unit (directorate, unit, advanced post)."""

    __tablename__ = "unit"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    name_ar: Mapped[str] = mapped_column(Text)
    name_fr: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    location: Mapped[object] = mapped_column(Geography("POINT", srid=4326))
    phone: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Resource(Base):
    """A vehicle or piece of equipment that can be assigned to an intervention."""

    __tablename__ = "resource"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.unit.id"))
    kind: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="available")
    notes: Mapped[str | None] = mapped_column(Text)
    location: Mapped[object | None] = mapped_column(Geography("POINT", srid=4326))
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Callout(Base):
    """A call for volunteers with a given skill around an incident (UC-05)."""

    __tablename__ = "callout"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    incident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.incident.id"))
    skill: Mapped[str] = mapped_column(Text)
    requested: Mapped[int] = mapped_column(SmallInteger)
    radius_km: Mapped[int] = mapped_column(SmallInteger)
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="open")
    created_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Assignment(Base):
    """An order given to a resource or a volunteer on an incident (أمر التكليف)."""

    __tablename__ = "assignment"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    incident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.incident.id"))
    kind: Mapped[str] = mapped_column(Text)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.resource.id"))
    volunteer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.volunteer.user_id", ondelete="SET NULL")
    )
    callout_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.callout.id"))
    order: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    en_route_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    on_scene_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CalloutTarget(Base):
    __tablename__ = "callout_target"
    __table_args__ = {"schema": "ops"}

    callout_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.callout.id", ondelete="CASCADE"), primary_key=True
    )
    volunteer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.volunteer.user_id", ondelete="CASCADE"), primary_key=True
    )
    distance_m: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, server_default="sent")
    eta_minutes: Mapped[int | None] = mapped_column(SmallInteger)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.assignment.id"))
