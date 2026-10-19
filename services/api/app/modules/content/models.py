import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class SafetyTip(Base):
    """Safety advice for one hazard in three languages (FR-A-062, FR-C-19)."""

    __tablename__ = "safety_tip"
    __table_args__ = {"schema": "content"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    hazard: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, server_default="0")
    status: Mapped[str] = mapped_column(Text, server_default="draft")
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Revision(Base):
    __tablename__ = "revision"
    __table_args__ = {"schema": "content"}

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[int] = mapped_column(BigInteger, server_default="1")
