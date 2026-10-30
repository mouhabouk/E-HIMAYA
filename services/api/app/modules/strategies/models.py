"""The items of the strategies menu that the system administrator adds (phase S, docs/phase-s/design-s.md §2.2)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class StrategyItem(Base):
    """A strategy, a programme or a reference of the strategies menu: its own page (a text in three languages) or a
    link to a page of the platform or to an official site."""

    __tablename__ = "item"
    __table_args__ = {"schema": "strategy"}

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[dict[str, str]] = mapped_column(JSONB)
    summary: Mapped[dict[str, str]] = mapped_column(JSONB, server_default="{}")
    body: Mapped[dict[str, str]] = mapped_column(JSONB, server_default="{}")
    link: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(Text)
    tone: Mapped[str] = mapped_column(Text)
    roles: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    position: Mapped[int] = mapped_column(Integer, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    updated_by: Mapped[str | None] = mapped_column(Text)
    updated_by_name: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
