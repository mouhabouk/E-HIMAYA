"""Seasonal programme tables (migration 0055, phase L2, docs/phase-l/design-l2.md §2)."""

import uuid
from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import Date, DateTime, ForeignKey, Integer, SmallInteger, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Programme(Base):
    __tablename__ = "programme"
    __table_args__ = {"schema": "programme"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    code: Mapped[str] = mapped_column(Text, unique=True)
    kind: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    season: Mapped[str] = mapped_column(Text, server_default="")
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, server_default="draft")
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    source_document: Mapped[str] = mapped_column(Text, server_default="")
    # Totals stated in the source file (staff, lifeguards planned and deployed), to compare with the points.
    declared: Mapped[dict[str, int]] = mapped_column(JSONB, server_default="{}")
    approved_by: Mapped[str | None] = mapped_column(Text)
    approved_by_name: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    layer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("geo.layer.id", ondelete="SET NULL")
    )
    created_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str] = mapped_column(Text)
    updated_by_name: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProgrammePoint(Base):
    __tablename__ = "point"
    __table_args__ = (UniqueConstraint("programme_id", "ref", name="uq_programme_point"), {"schema": "programme"})

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    programme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("programme.programme.id", ondelete="CASCADE")
    )
    ref: Mapped[str] = mapped_column(Text)
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    place_name: Mapped[str] = mapped_column(Text)
    sub_points: Mapped[str | None] = mapped_column(Text)
    location: Mapped[object | None] = mapped_column(Geography("POINT", srid=4326))
    geo_confidence: Mapped[str] = mapped_column(Text, server_default="unknown")
    geo_note: Mapped[str | None] = mapped_column(Text)
    staff_count: Mapped[int | None] = mapped_column(Integer)
    staff_composition: Mapped[str | None] = mapped_column(Text)
    supervisors: Mapped[int | None] = mapped_column(Integer)
    lifeguards_planned: Mapped[int | None] = mapped_column(Integer)
    lifeguards_deployed: Mapped[int | None] = mapped_column(Integer)
    equipment: Mapped[str | None] = mapped_column(Text)
    hours: Mapped[str | None] = mapped_column(Text)
    opening_date: Mapped[date | None] = mapped_column(Date)
    closing_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, server_default="open")
    supervisor_name: Mapped[str | None] = mapped_column(Text)
    supervisor_phone: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProgrammeRevision(Base):
    __tablename__ = "revision"
    __table_args__ = (
        UniqueConstraint("programme_id", "number", name="uq_programme_revision"),
        {"schema": "programme"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    programme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("programme.programme.id", ondelete="CASCADE")
    )
    number: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
