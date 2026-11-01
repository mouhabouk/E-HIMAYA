"""The Office's reference lists (migration 0091): a list and its items, kept by the central room."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class RefList(Base):
    __tablename__ = "list"
    __table_args__ = {"schema": "ref"}

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    name_ar: Mapped[str] = mapped_column(Text)
    name_fr: Mapped[str] = mapped_column(Text)
    name_en: Mapped[str] = mapped_column(Text)
    sort: Mapped[int] = mapped_column(SmallInteger)


class RefItem(Base):
    __tablename__ = "item"
    __table_args__ = {"schema": "ref"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    list_key: Mapped[str] = mapped_column(Text, ForeignKey("ref.list.key"))
    code: Mapped[str | None] = mapped_column(Text)
    label_ar: Mapped[str] = mapped_column(Text)
    label_fr: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(Text)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[str] = mapped_column(Text)
    updated_by_name: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
