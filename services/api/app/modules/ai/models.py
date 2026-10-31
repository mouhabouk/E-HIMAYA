import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.crypto import EncryptedJSON, EncryptedText
from app.core.db import Base


class Analysis(Base):
    """AI analysis of one report: pipeline state and the explained results shown to operators."""

    __tablename__ = "analysis"
    __table_args__ = {"schema": "ai"}

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.report.id", ondelete="CASCADE"), primary_key=True
    )
    state: Mapped[str] = mapped_column(Text, server_default="pending")
    generation: Mapped[int] = mapped_column(Integer, server_default="1")
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    # Model output includes a summary of the report text: encrypted like the text itself.
    extraction: Mapped[dict[str, Any] | None] = mapped_column("extraction_enc", EncryptedJSON("ai.analysis.extraction"))
    priority: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    credibility: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    suggestion: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    dismissed: Mapped[list[str]] = mapped_column(JSONB, server_default="[]")
    models: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AiSettingsRow(Base):
    __tablename__ = "settings"
    __table_args__ = {"schema": "ai"}

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, server_default="1")
    value: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_by: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelDecision(Base):
    """A committee decision about a model card (AI-01): thresholds approved or approval withdrawn. Append-only."""

    __tablename__ = "model_decision"
    __table_args__ = {"schema": "ai"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(Text)
    thresholds: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    version: Mapped[str] = mapped_column(Text)
    reference: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text, server_default="")
    decided_by_name: Mapped[str] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Anomaly(Base):
    """An indicator of a gouvernorat or a delegation found outside its usual series on a day (AI4), kept once."""

    __tablename__ = "anomaly"
    __table_args__ = {"schema": "ai"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    indicator: Mapped[str] = mapped_column(Text)
    unit_key: Mapped[str] = mapped_column(Text)
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    delegation_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("geo.delegation.id"))
    day: Mapped[date] = mapped_column(Date)
    value: Mapped[float] = mapped_column(Float)
    mean: Mapped[float] = mapped_column(Float)
    std: Mapped[float] = mapped_column(Float)
    z: Mapped[float] = mapped_column(Float)
    baseline: Mapped[str] = mapped_column(Text)
    points: Mapped[int] = mapped_column(SmallInteger)
    n: Mapped[int] = mapped_column(Integer)
    raised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Dictation(Base):
    """One dictated text (review point 19, phase D): the model's text and the text the user kept, never the audio.

    The pair feeds the word error rate per field, the same measure as the commander's voice notes (AI5)."""

    __tablename__ = "dictation"
    __table_args__ = {"schema": "ai"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    actor: Mapped[str] = mapped_column(Text)
    field: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    duration_s: Mapped[float | None] = mapped_column(Float(precision=24))
    text: Mapped[str | None] = mapped_column("text_enc", EncryptedText("ai.dictation.text"))
    kept: Mapped[str | None] = mapped_column("kept_enc", EncryptedText("ai.dictation.kept"))
    wer: Mapped[float | None] = mapped_column(Float(precision=24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
