import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

_S = {"schema": "decision_window"}


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())


class WindowDelegation(Base):
    """The window opened to one account, for a period, on selected events (L4 §5)."""

    __tablename__ = "delegation"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = _pk()
    grantee: Mapped[str] = mapped_column(Text)
    grantee_name: Mapped[str | None] = mapped_column(Text)
    grantee_roles: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    grantee_gouvernorat: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    reason: Mapped[str] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    granted_by: Mapped[str] = mapped_column(Text)
    granted_by_name: Mapped[str | None] = mapped_column(Text)
    # central | g:<code>
    granted_room: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_name: Mapped[str | None] = mapped_column(Text)
    revoke_reason: Mapped[str | None] = mapped_column(Text)


class WindowEvent(Base):
    __tablename__ = "delegation_event"
    __table_args__ = _S

    delegation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("decision_window.delegation.id", ondelete="CASCADE"), primary_key=True
    )
    # axis | incident
    kind: Mapped[str] = mapped_column(Text, primary_key=True)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    label: Mapped[str] = mapped_column(Text, server_default="")
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    added_by_name: Mapped[str | None] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SavedSearch(Base):
    __tablename__ = "saved_search"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = _pk()
    owner: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    # search | compare
    kind: Mapped[str] = mapped_column(Text)
    query: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Synonym(Base):
    __tablename__ = "synonym"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = _pk()
    meaning: Mapped[str] = mapped_column(Text)
    words: Mapped[list[str]] = mapped_column(ARRAY(Text))
    updated_by_name: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
