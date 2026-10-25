import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
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
    # Phase P2b: tagged with institution kinds, the tip is awareness for those institutions only.
    org_kinds: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")


class Revision(Base):
    __tablename__ = "revision"
    __table_args__ = {"schema": "content"}

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[int] = mapped_column(BigInteger, server_default="1")


class GuideTopic(Base):
    """A topic of the emergency hub (phase B1, design §2bis): fires, fractures, first aid…"""

    __tablename__ = "guide_topic"
    __table_args__ = {"schema": "content"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    key: Mapped[str] = mapped_column(Text, unique=True)
    title: Mapped[dict[str, str]] = mapped_column(JSONB)
    icon: Mapped[str] = mapped_column(Text)
    colour: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, server_default="0")
    hidden: Mapped[bool] = mapped_column(Boolean, server_default="false")
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    updated_by: Mapped[str] = mapped_column(Text, server_default="system")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GuideItem(Base):
    """An item of a topic: per language a title, "call 198 now if…", numbered steps and "do not"."""

    __tablename__ = "guide_item"
    __table_args__ = {"schema": "content"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content.guide_topic.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer, server_default="0")
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    call_198: Mapped[bool] = mapped_column(Boolean, server_default="false")
    hidden: Mapped[bool] = mapped_column(Boolean, server_default="false")
    validated_by: Mapped[str | None] = mapped_column(Text)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    updated_by: Mapped[str] = mapped_column(Text, server_default="system")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
