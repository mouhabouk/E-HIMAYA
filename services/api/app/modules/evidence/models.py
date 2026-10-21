import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Anchor(Base):
    """One sealed batch. Append-only (a trigger refuses changes, except filling in the time stamp)."""

    __tablename__ = "anchor"
    __table_args__ = {"schema": "evidence"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    seq: Mapped[int] = mapped_column(BigInteger, unique=True)
    from_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    to_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    media_count: Mapped[int] = mapped_column(Integer)
    media_root: Mapped[str | None] = mapped_column(String(64))
    audit_seq: Mapped[int | None] = mapped_column(BigInteger)
    audit_hash: Mapped[str | None] = mapped_column(String(64))
    prev_anchor_hash: Mapped[str | None] = mapped_column(String(64))
    anchor_hash: Mapped[str] = mapped_column(String(64), unique=True)
    signature: Mapped[str | None] = mapped_column(Text)
    key_id: Mapped[str | None] = mapped_column(String(16))
    tsa_url: Mapped[str | None] = mapped_column(Text)
    tsa_token: Mapped[bytes | None] = mapped_column(LargeBinary)
    tsa_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Leaf(Base):
    """A media hash covered by an anchor, at its position in the Merkle tree. Kept after the media is erased."""

    __tablename__ = "leaf"
    __table_args__ = {"schema": "evidence"}

    anchor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("evidence.anchor.id"), primary_key=True)
    idx: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
