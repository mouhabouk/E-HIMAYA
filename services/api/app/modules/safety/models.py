import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, LargeBinary, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.crypto import EncryptedJSON, EncryptedText
from app.core.db import Base

_SCHEMA = {"schema": "safety"}
_ACCOUNT = "identity.account.user_id"


class Invitation(Base):
    """A code one registered user gives another to link their accounts (only its SHA-256 is kept)."""

    __tablename__ = "invitation"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    inviter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey(_ACCOUNT, ondelete="CASCADE"))
    code_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey(_ACCOUNT, ondelete="SET NULL"))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Link(Base):
    """Two accounts linked by an accepted invitation (``user_a < user_b``); it works both ways."""

    __tablename__ = "link"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_a: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey(_ACCOUNT, ondelete="CASCADE"))
    user_b: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey(_ACCOUNT, ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def other(self, user_id: uuid.UUID) -> uuid.UUID:
        return self.user_b if self.user_a == user_id else self.user_a


class LiveShare(Base):
    """A live location link. ``points``: the last positions, newest last (encrypted)."""

    __tablename__ = "live_share"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey(_ACCOUNT, ondelete="CASCADE"))
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    points: Mapped[list[dict[str, Any]] | None] = mapped_column("points_enc", EncryptedJSON("safety.live_share.points"))
    battery: Mapped[int | None] = mapped_column(SmallInteger)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Alert(Base):
    """An SOS message or a fired safety check, sent in the app to linked contacts."""

    __tablename__ = "alert"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    client_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    sender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey(_ACCOUNT, ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column("message_enc", EncryptedText("safety.alert.message"))
    position: Mapped[dict[str, Any] | None] = mapped_column("position_enc", EncryptedJSON("safety.alert.position"))
    battery: Mapped[int | None] = mapped_column(SmallInteger)
    live_share_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("safety.live_share.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AlertRecipient(Base):
    __tablename__ = "alert_recipient"
    __table_args__ = _SCHEMA

    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("safety.alert.id", ondelete="CASCADE"), primary_key=True
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(_ACCOUNT, ondelete="CASCADE"), primary_key=True
    )
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SafetyCheck(Base):
    """A safety check timer: fired by the server at ``due_at`` unless the owner answered "I am fine"."""

    __tablename__ = "safety_check"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey(_ACCOUNT, ondelete="CASCADE"))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    message: Mapped[str] = mapped_column("message_enc", EncryptedText("safety.safety_check.message"))
    position: Mapped[dict[str, Any] | None] = mapped_column(
        "position_enc", EncryptedJSON("safety.safety_check.position")
    )
    battery: Mapped[int | None] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(Text, server_default="active")
    alert_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("safety.alert.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
