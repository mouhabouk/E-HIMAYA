from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Computed, DateTime, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
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
