import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.crypto import EncryptedJSON
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
