"""Training samples, trained versions and jobs of the self-learning models (migration 0076, docs/learning.md)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.crypto import EncryptedText
from app.core.db import Base


class Sample(Base):
    """One anonymised text and its labels; ``label_origin`` says who gave the labels (weak = read from the system)."""

    __tablename__ = "learning_sample"
    __table_args__ = {"schema": "ai"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    source: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str] = mapped_column(Text)
    group_key: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column("text_enc", EncryptedText("ai.learning_sample.text"))
    label: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    label_origin: Mapped[str] = mapped_column(Text)
    split: Mapped[str] = mapped_column(Text)
    labelled_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LearnedModel(Base):
    """One trained version of a task's model: plain numbers, its heldout figures, and whether it is the current one."""

    __tablename__ = "learning_model"
    __table_args__ = {"schema": "ai"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    task: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    algorithm: Mapped[str] = mapped_column(Text)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB)
    primary_metric: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    train_samples: Mapped[int] = mapped_column(Integer)
    heldout_samples: Mapped[int] = mapped_column(Integer)
    trained_by_name: Mapped[str] = mapped_column(Text)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TrainingJob(Base):
    """A training launched by the system administrator or by the schedule, and its result."""

    __tablename__ = "training_job"
    __table_args__ = {"schema": "ai"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    task: Mapped[str] = mapped_column(Text)
    trigger: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, server_default="queued")
    requested_by: Mapped[str] = mapped_column(Text)
    requested_by_name: Mapped[str] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    error: Mapped[str | None] = mapped_column(Text)
    model_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ai.learning_model.id"))
