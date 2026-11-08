import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Computed, DateTime, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AuditLog(Base):
    """Append-only, hash-chained audit trail. ``seq``, ``at``, ``prev_hash`` and ``hash`` are set by a DB trigger."""

    __tablename__ = "log"
    __table_args__ = {"schema": "audit"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    seq: Mapped[int] = mapped_column(BigInteger, unique=True, server_default="0")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    target: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), server_default="")
    # Gouvernorats the entry concerns, derived from details["gouvernorats"] (0023_audit_scope); empty = national only.
    gouvernorats: Mapped[list[int]] = mapped_column(
        ARRAY(SmallInteger), Computed("audit.scope_of(details)", persisted=True)
    )


class Change(Base):
    """The change journal ("mouchard", migration 0097): one row per INSERT, UPDATE or DELETE, written by a trigger."""

    __tablename__ = "change"
    __table_args__ = {"schema": "audit"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    txid: Mapped[int] = mapped_column(BigInteger)
    actor: Mapped[str] = mapped_column(Text)
    actor_name: Mapped[str | None] = mapped_column(Text)
    scope: Mapped[str | None] = mapped_column(Text)
    actor_gouvernorat: Mapped[int | None] = mapped_column(SmallInteger)
    request_id: Mapped[str | None] = mapped_column(Text)
    schema_name: Mapped[str] = mapped_column(Text)
    table_name: Mapped[str] = mapped_column(Text)
    op: Mapped[str] = mapped_column(String(1))
    row_key: Mapped[dict[str, Any]] = mapped_column(JSONB)
    columns: Mapped[list[str]] = mapped_column(ARRAY(Text))
    hidden: Mapped[list[str]] = mapped_column(ARRAY(Text))
    old_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    org_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger)
