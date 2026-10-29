"""The task list read from an intervention plan (migration 0072, docs/phase-l/design-l5.md §2.3, AI2)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

_S = {"schema": "crisis"}


class Checklist(Base):
    __tablename__ = "checklist"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    # Exactly one owner: a crisis axis or a dry run.
    axis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crisis.axis.id", ondelete="CASCADE"), unique=True
    )
    exercise_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drill.exercise.id", ondelete="CASCADE"), unique=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("register.document.id"))
    file_sha256: Mapped[str] = mapped_column(Text)
    # queued | reading | review | approved | failed
    state: Mapped[str] = mapped_column(Text, server_default="queued")
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    model: Mapped[str | None] = mapped_column(Text)
    pages: Mapped[int | None] = mapped_column(SmallInteger)
    pages_read: Mapped[int | None] = mapped_column(SmallInteger)
    requested_by: Mapped[str] = mapped_column(Text)
    requested_by_name: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(Text)
    approved_by_name: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, server_default="1")


class ChecklistTask(Base):
    __tablename__ = "checklist_task"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    checklist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crisis.checklist.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(SmallInteger)
    action: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(Text, server_default="")
    resource: Mapped[str] = mapped_column(Text, server_default="")
    page: Mapped[int | None] = mapped_column(SmallInteger)
    quote: Mapped[str] = mapped_column(Text, server_default="")
    quote_found: Mapped[bool | None] = mapped_column(Boolean)
    # ai | manual
    origin: Mapped[str] = mapped_column(Text)
    # suggested | accepted | edited | deleted | added
    review: Mapped[str] = mapped_column(Text)
    suggested: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # todo | doing | done | not_applicable
    status: Mapped[str] = mapped_column(Text, server_default="todo")
    note: Mapped[str] = mapped_column(Text, server_default="")
    status_by_name: Mapped[str | None] = mapped_column(Text)
    status_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_name: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
