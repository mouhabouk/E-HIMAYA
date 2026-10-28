"""Daily, weekly and monthly programmes of every gouvernorat (phase PL2, docs/phase-pl/design-plans.md §3)."""

import uuid
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, SmallInteger, Text, Time, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())


class Setting(Base):
    """How a gouvernorat approves its programmes."""

    __tablename__ = "setting"
    __table_args__ = {"schema": "sched"}

    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"), primary_key=True)
    approval: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[str | None] = mapped_column(Text)
    updated_by_name: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Period(Base):
    """The programme of a gouvernorat for a day, a week or a month."""

    __tablename__ = "period"
    __table_args__ = {"schema": "sched"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    span: Mapped[str] = mapped_column(Text)
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, server_default="draft")
    approval: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, server_default="")
    return_reason: Mapped[str | None] = mapped_column(Text)
    submitted_by_name: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_name: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    centre_approved_by_name: Mapped[str | None] = mapped_column(Text)
    centre_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    created_by: Mapped[str | None] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by_name: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Item(Base):
    """An activity of a programme and its follow-up."""

    __tablename__ = "item"
    __table_args__ = {"schema": "sched"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    period_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sched.period.id", ondelete="CASCADE"))
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    series_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    activity: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    on_date: Mapped[date] = mapped_column(Date)
    starts_at: Mapped[time | None] = mapped_column(Time)
    ends_at: Mapped[time | None] = mapped_column(Time)
    unit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.unit.id"))
    place: Mapped[str] = mapped_column(Text, server_default="")
    responsible: Mapped[str] = mapped_column(Text, server_default="")
    staff_count: Mapped[int | None] = mapped_column(Integer)
    resources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    plan_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("register.document.id"))
    notes: Mapped[str] = mapped_column(Text, server_default="")
    status: Mapped[str] = mapped_column(Text, server_default="planned")
    status_reason: Mapped[str | None] = mapped_column(Text)
    status_by_name: Mapped[str | None] = mapped_column(Text)
    status_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
