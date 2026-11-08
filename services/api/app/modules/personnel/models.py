"""Personnel management, phase H1 (migration 0096, docs/phase-h/design-h.md).

The members of staff are the ``inv.agent`` rows of the resources register; this module keeps their administrative
file (dated events) and their absences.
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())


class Event(Base):
    """A dated entry of the administrative file: rank, appointment, transfer, sanction or reward."""

    __tablename__ = "event"
    __table_args__ = {"schema": "personnel"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("inv.agent.id", ondelete="CASCADE"))
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    kind: Mapped[str] = mapped_column(Text)
    effective_on: Mapped[date] = mapped_column(Date)
    title: Mapped[str | None] = mapped_column(Text)
    unit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.unit.id"))
    from_unit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.unit.id"))
    previous: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    reference: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_name: Mapped[str | None] = mapped_column(Text)
    cancel_reason: Mapped[str | None] = mapped_column(Text)


class Absence(Base):
    """Leave or absence between two dates (both included)."""

    __tablename__ = "absence"
    __table_args__ = {"schema": "personnel"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("inv.agent.id", ondelete="CASCADE"))
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    kind: Mapped[str] = mapped_column(Text)
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    reference: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by_name: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_name: Mapped[str | None] = mapped_column(Text)
    cancel_reason: Mapped[str | None] = mapped_column(Text)
