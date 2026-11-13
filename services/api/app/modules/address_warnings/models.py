"""Address warnings, OS8 (migration ``0103_address_warnings``, docs/phase-os8/design-os8.md)."""

import uuid
from datetime import date, datetime

from geoalchemy2 import Geography
from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

_SCHEMA = {"schema": "aw"}


class Category(Base):
    """A kind of mark: its circle, its review period, whether the team sees it, and when it is critical."""

    __tablename__ = "category"
    __table_args__ = _SCHEMA

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(Text)
    colour: Mapped[str] = mapped_column(Text)
    personal: Mapped[bool] = mapped_column(Boolean, server_default="false")
    radius_m: Mapped[int] = mapped_column(Integer)
    review_months: Mapped[int] = mapped_column(SmallInteger)
    team: Mapped[bool] = mapped_column(Boolean, server_default="true")
    critical_with: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    examples: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    position: Mapped[int] = mapped_column(SmallInteger)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by_name: Mapped[str | None] = mapped_column(Text)


class Marker(Base):
    """A mark on an address. Personal marks belong to their owner (citizen app, consent)."""

    __tablename__ = "marker"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    category: Mapped[str] = mapped_column(Text, ForeignKey("aw.category.key"))
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    location: Mapped[object] = mapped_column(Geography("POINT", srid=4326))
    address: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    source_ref: Mapped[str | None] = mapped_column(Text)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org.organization.id", ondelete="SET NULL")
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="SET NULL")
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.account.user_id", ondelete="CASCADE")
    )
    team_visible: Mapped[bool] = mapped_column(Boolean, server_default="true")
    # Minutes of the day (local time) during which the mark applies; both empty = always.
    active_from: Mapped[int | None] = mapped_column(SmallInteger)
    active_to: Mapped[int | None] = mapped_column(SmallInteger)
    review_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by_name: Mapped[str | None] = mapped_column(Text)
    decision_reason: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # OS8-3: a field check asked from the review reminder, cleared by a confirm or an archive.
    check_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    check_requested_by_name: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, server_default="1")


class Ack(Base):
    """The room or the team read a warning of an incident."""

    __tablename__ = "ack"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    marker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("aw.marker.id", ondelete="CASCADE"))
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="CASCADE")
    )
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    by_kind: Mapped[str] = mapped_column(Text)
    by_subject: Mapped[str] = mapped_column(Text)
    by_name: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Reveal(Base):
    """A room showed the name and phone of a personal mark, with the reason."""

    __tablename__ = "reveal"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    marker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("aw.marker.id", ondelete="CASCADE"))
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.account.user_id", ondelete="CASCADE")
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="SET NULL")
    )
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    by_subject: Mapped[str] = mapped_column(Text)
    by_name: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # OS8-2: how the owner was told (push, sms, or none), and the owner's objection.
    notified_via: Mapped[str | None] = mapped_column(Text)
    disputed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispute_note: Mapped[str | None] = mapped_column(Text)


class ReminderDay(Base):
    """OS8-3: the morning review reminder went to a gouvernorat's room that day (sent once across workers)."""

    __tablename__ = "reminder_day"
    __table_args__ = _SCHEMA

    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    late: Mapped[int] = mapped_column(Integer)
    soon: Mapped[int] = mapped_column(Integer)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
