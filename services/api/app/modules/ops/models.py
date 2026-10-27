import enum
import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, SmallInteger, Text, func
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
    # Lead gouvernorat (phase 9 §5.1): fixed at creation, changed only by an audited transfer.
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
    lead_set_by: Mapped[str | None] = mapped_column(Text)
    lead_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # regional | central (phase 9 §5.3).
    command_level: Mapped[str] = mapped_column(Text, server_default="regional")
    command_level_reason: Mapped[str | None] = mapped_column(Text)
    command_level_manual: Mapped[bool] = mapped_column(Boolean, server_default="false")


class IncidentGouvernorat(Base):
    """Lead and participating gouvernorats of an incident; the lead row follows ``incident.gouvernorat_code``
    (database trigger)."""

    __tablename__ = "incident_gouvernorat"
    __table_args__ = {"schema": "ops"}

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="CASCADE"), primary_key=True
    )
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"), primary_key=True)
    role: Mapped[str] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    added_by: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)


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
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.resource_request.id", ondelete="SET NULL")
    )
    order: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    en_route_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    on_scene_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Phase P4a: the shift holding the vehicle, and when its leader saw the mission on the staff app.
    shift_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.shift.id"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Phase P4b: a number the room gives the team for the scene ("المبلّغ" on the phone).
    contact_phone: Mapped[str | None] = mapped_column(Text)


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


class ResourceRequest(Base):
    """A room asks the gouvernorat owning a resource to engage it on an incident (phase 9 §5.4)."""

    __tablename__ = "resource_request"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="CASCADE")
    )
    # "central" or "g:<code>".
    from_room: Mapped[str] = mapped_column(Text)
    to_gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.resource.id", ondelete="SET NULL")
    )
    resource_kind: Mapped[str] = mapped_column(Text)
    quantity: Mapped[int] = mapped_column(SmallInteger, server_default="1")
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    requested_by: Mapped[str] = mapped_column(Text)
    requested_by_name: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_by: Mapped[str | None] = mapped_column(Text)
    decided_by_name: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)


class StaffDevice(Base):
    """A team leader's phone bound to their staff account (phase P4a). Revoked = wiped remotely."""

    __tablename__ = "staff_device"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    subject: Mapped[str] = mapped_column(Text)
    holder_name: Mapped[str | None] = mapped_column(Text)
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    label: Mapped[str | None] = mapped_column(Text)
    platform: Mapped[str] = mapped_column(Text)
    app_build: Mapped[int | None] = mapped_column(Integer)
    push_token: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[str | None] = mapped_column(Text)


class Shift(Base):
    """A team leader on duty with one vehicle and a crew (phase P4a, F-STF-01)."""

    __tablename__ = "shift"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    subject: Mapped[str] = mapped_column(Text)
    leader_name: Mapped[str | None] = mapped_column(Text)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.staff_device.id"))
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.resource.id"))
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    crew_size: Mapped[int] = mapped_column(SmallInteger)
    crew_names: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CrewEvent(Base):
    """A write from the staff app, keyed by the id the phone generated: sent twice, applied once."""

    __tablename__ = "crew_event"
    __table_args__ = {"schema": "ops"}

    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.assignment.id", ondelete="CASCADE")
    )
    shift_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.shift.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    subject: Mapped[str] = mapped_column(Text)
    device_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FieldReport(Base):
    """A field report of a team on scene: the first situation report and its updates (phase P4a, F-STF-03), or the
    detailed report built from a template (phase P4b, F-STF-05: ``answers``, no severity)."""

    __tablename__ = "field_report"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="CASCADE")
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.assignment.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(Text, server_default="first")
    category: Mapped[str] = mapped_column(Text)
    classification: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[int | None] = mapped_column(SmallInteger)
    backup_needed: Mapped[bool] = mapped_column(Boolean, server_default="false")
    backup_note: Mapped[str | None] = mapped_column(Text)
    backup_kinds: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    crew_danger: Mapped[bool] = mapped_column(Boolean, server_default="false")
    template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.report_template.id"))
    template_version: Mapped[int | None] = mapped_column(Integer)
    answers: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    note: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str] = mapped_column(Text)
    author_name: Mapped[str | None] = mapped_column(Text)
    device_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CasualtyCount(Base):
    """Live casualty counters of an incident (phase P4a, F-STF-04)."""

    __tablename__ = "casualty_count"
    __table_args__ = {"schema": "ops"}

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="CASCADE"), primary_key=True
    )
    injured_light: Mapped[int] = mapped_column(Integer, server_default="0")
    injured_serious: Mapped[int] = mapped_column(Integer, server_default="0")
    deceased: Mapped[int] = mapped_column(Integer, server_default="0")
    rescued: Mapped[int] = mapped_column(Integer, server_default="0")
    trapped: Mapped[int] = mapped_column(Integer, server_default="0")
    updated_by: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CasualtyTransport(Base):
    """A person taken to hospital, without a name (phase P4a, F-STF-04)."""

    __tablename__ = "casualty_transport"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="CASCADE")
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.assignment.id", ondelete="CASCADE")
    )
    triage: Mapped[str] = mapped_column(Text)
    age_band: Mapped[str] = mapped_column(Text)
    sex: Mapped[str] = mapped_column(Text)
    hospital: Mapped[str] = mapped_column(Text)
    # Phase P4b: the place of a map layer the leader picked (null when typed under "other").
    hospital_ref: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("geo.layer_feature.id", ondelete="SET NULL")
    )
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    device_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CrewAlert(Base):
    """ "Backup" or "danger to the crew" from a team, at any moment of its mission, until the room has seen it
    (phase P4b, design §5.4)."""

    __tablename__ = "crew_alert"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="CASCADE")
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.assignment.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(Text)
    items: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    device_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    seen_by: Mapped[str | None] = mapped_column(Text)
    seen_by_name: Mapped[str | None] = mapped_column(Text)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FieldAttachment(Base):
    """A photo, a voice note or a short text from the scene (phase P4b, design §5.8)."""

    __tablename__ = "field_attachment"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="CASCADE")
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.assignment.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    object_key: Mapped[str | None] = mapped_column(Text, unique=True)
    content_type: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(Text)
    bytes: Mapped[int | None] = mapped_column(Integer)
    duration_s: Mapped[float | None] = mapped_column(Float(precision=24))
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    device_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportTemplate(Base):
    """The detailed report of a category (and optionally a classification), versioned; one approved version at a
    time (phase P4b, F-STF-05, design §5.7)."""

    __tablename__ = "report_template"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    category: Mapped[str] = mapped_column(Text)
    classification: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text)
    fields: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    simulated: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_by: Mapped[str | None] = mapped_column(Text)
    approved_by_name: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
