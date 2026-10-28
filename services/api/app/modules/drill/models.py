import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

_S = {"schema": "drill"}


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())


class Exercise(Base):
    """A digital dry run (L5a): a timed scenario played to the rooms of the gouvernorats that approved it."""

    __tablename__ = "exercise"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = _pk()
    title: Mapped[str] = mapped_column(Text)
    objective: Mapped[str] = mapped_column(Text)
    hazard_key: Mapped[str | None] = mapped_column(Text)
    plan_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    gouvernorats: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger))
    # central | g:<code>: the room that planned it.
    room: Mapped[str] = mapped_column(Text)
    planned_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_min: Mapped[int] = mapped_column(SmallInteger)
    evaluator: Mapped[str | None] = mapped_column(Text)
    evaluator_name: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="draft")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stop_reason: Mapped[str | None] = mapped_column(Text)
    stopped_by_name: Mapped[str | None] = mapped_column(Text)
    # {"<code>": {"<kind>": available count}} when the run started.
    resources_at_start: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    conclusion: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Participant(Base):
    __tablename__ = "participant"
    __table_args__ = _S

    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drill.exercise.id", ondelete="CASCADE"), primary_key=True
    )
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"), primary_key=True)
    # pending | approved | refused | withdrawn
    decision: Mapped[str] = mapped_column(Text, server_default="pending")
    reason: Mapped[str | None] = mapped_column(Text)
    decided_by_name: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Inject(Base):
    """A timed message of the scenario, delivered ``offset_min`` minutes after the start."""

    __tablename__ = "inject"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = _pk()
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drill.exercise.id", ondelete="CASCADE")
    )
    offset_min: Mapped[int] = mapped_column(SmallInteger)
    # None: every gouvernorat of the dry run.
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    kind: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, server_default="")
    # {"<resource kind>": count}
    needs: Mapped[dict[str, int]] = mapped_column(JSONB, server_default="{}")
    expected: Mapped[str] = mapped_column(Text, server_default="")
    generated: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Response(Base):
    __tablename__ = "response"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = _pk()
    inject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("drill.inject.id", ondelete="CASCADE"))
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    action: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, server_default="")
    responded_by: Mapped[str] = mapped_column(Text)
    responded_by_name: Mapped[str | None] = mapped_column(Text)
    responded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Booking(Base):
    """A real resource booked inside the dry run only; its real status is never touched."""

    __tablename__ = "booking"
    __table_args__ = _S

    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drill.exercise.id", ondelete="CASCADE"), primary_key=True
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.resource.id", ondelete="CASCADE"), primary_key=True
    )
    response_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drill.response.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(Text)
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    booked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), primary_key=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Evaluation(Base):
    __tablename__ = "evaluation"
    __table_args__ = _S

    inject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drill.inject.id", ondelete="CASCADE"), primary_key=True
    )
    plan_followed: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(SmallInteger)
    notes: Mapped[str] = mapped_column(Text, server_default="")
    evaluated_by_name: Mapped[str | None] = mapped_column(Text)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StressRun(Base):
    __tablename__ = "stress_run"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = _pk()
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drill.exercise.id", ondelete="CASCADE")
    )
    environment: Mapped[str] = mapped_column(Text)
    results: Mapped[dict[str, Any]] = mapped_column(JSONB)
    recorded_by_name: Mapped[str | None] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
