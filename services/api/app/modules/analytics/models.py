"""What-if scenarios, reports repository, scheduled reports and staff notifications (migration 0015)."""

import uuid
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, SmallInteger, Text, Time, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

_SCHEMA = {"schema": "analytics"}


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())


class Scenario(Base):
    """A what-if run (FR-C-12): parameters, seed and result of the seeded queue simulation."""

    __tablename__ = "scenario"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text)
    gouvernorats: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger))
    category: Mapped[str | None] = mapped_column(Text)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    seed: Mapped[int] = mapped_column(BigInteger)
    runs: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, server_default="done")
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    creator_scope: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    created_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Schedule(Base):
    """A scheduled report: generated at a time of day (Africa/Tunis), recipients notified in the app."""

    __tablename__ = "schedule"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = _uuid_pk()
    kind: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    gouvernorats: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), server_default="{}")
    format: Mapped[str] = mapped_column(Text)
    lang: Mapped[str] = mapped_column(Text, server_default="ar")
    frequency: Mapped[str] = mapped_column(Text)
    at_time: Mapped[time] = mapped_column(Time)
    weekday: Mapped[int | None] = mapped_column(SmallInteger)
    day: Mapped[int | None] = mapped_column(SmallInteger)
    recipients: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_report_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    creator_scope: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    created_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Report(Base):
    """A document of the reports repository (FR-C-21); the file is a ``reports.media`` row."""

    __tablename__ = "report"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = _uuid_pk()
    kind: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    lang: Mapped[str] = mapped_column(Text, server_default="ar")
    period_from: Mapped[date] = mapped_column(Date)
    period_to: Mapped[date] = mapped_column(Date)
    gouvernorats: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), server_default="{}")
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    format: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="queued")
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.media.id", ondelete="SET NULL")
    )
    sha256: Mapped[str | None] = mapped_column(Text)
    bytes: Mapped[int | None] = mapped_column(BigInteger)
    creator_scope: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    created_by: Mapped[str] = mapped_column(Text)
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analytics.schedule.id", ondelete="SET NULL")
    )
    # Staff subjects notified in the app when the document is ready (the creator is always notified).
    recipients: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(Base):
    """An in-app notification of a staff member (staff realm subject)."""

    __tablename__ = "notification"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    recipient: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text, server_default="report_ready")
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analytics.report.id", ondelete="CASCADE")
    )
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analytics.schedule.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
