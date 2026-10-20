from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PlatformSetting(Base):
    """One national setting (phase 9 §2): SLA bands and delays, anonymous quota, geographic trust threshold."""

    __tablename__ = "setting"
    __table_args__ = {"schema": "platform"}

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB)
    # Optimistic concurrency: a PUT names the version it read (409 version_conflict otherwise).
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    updated_by: Mapped[str | None] = mapped_column(Text)
    updated_by_name: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
