"""Calls, operator endpoints, crisis rooms and inbound SMS (migration 0014_telephony, schema ``telephony``)."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, LargeBinary, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.crypto import EncryptedText
from app.core.db import Base


class Call(Base):
    __tablename__ = "call"
    __table_args__ = {"schema": "telephony"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Asterisk channel id (uniqueid) of the citizen's leg (inbound) or of the operator's leg (outbound).
    channel_id: Mapped[str] = mapped_column(Text, unique=True)
    direction: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, server_default="unknown")
    # The citizen's number (caller of an inbound call, called number of an outbound one), encrypted, with its
    # blind index for exact lookups.
    caller_number: Mapped[str | None] = mapped_column(
        "caller_number_enc", EncryptedText("telephony.call.caller_number")
    )
    caller_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Staff subject (Keycloak "sub" of the staff realm) of the operator who answered or placed the call.
    operator_user_id: Mapped[str | None] = mapped_column(Text)
    operator_endpoint: Mapped[str | None] = mapped_column(Text)
    queue: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="ringing")
    end_reason: Mapped[str | None] = mapped_column(Text)
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.report.id", ondelete="SET NULL")
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="SET NULL")
    )
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    transferred_to: Mapped[str | None] = mapped_column(Text)
    recording_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.media.id", ondelete="SET NULL")
    )
    # none (not recorded yet) → pending (call ended, file to ingest) → done | missing | failed.
    recording_state: Mapped[str] = mapped_column(Text, server_default="none")
    recording_attempts: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    recording_next_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    recording_error: Mapped[str | None] = mapped_column(Text)
    # Staff member who placed an outbound call.
    created_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OperatorEndpoint(Base):
    """The WebRTC endpoint pushed to Asterisk for one staff member while their SIP credentials are valid."""

    __tablename__ = "operator_endpoint"
    __table_args__ = {"schema": "telephony"}

    endpoint: Mapped[str] = mapped_column(Text, primary_key=True)
    user_subject: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Set once the endpoint was deleted from Asterisk and taken out of the queue.
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Conference(Base):
    """A crisis room (ConfBridge) of an incident."""

    __tablename__ = "conference"
    __table_args__ = {"schema": "telephony"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room: Mapped[str] = mapped_column(Text, unique=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="CASCADE")
    )
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    created_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_by: Mapped[str | None] = mapped_column(Text)


class SmsInbound(Base):
    """One SMS received from the gateway (dedup of gateway retries and repeated messages; no text is kept)."""

    __tablename__ = "sms_inbound"
    __table_args__ = {"schema": "telephony"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Blind indexes of the gateway's message id and of the sender's number.
    message_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    sender_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    # The sender's number, encrypted: operators call back from the report (POST /api/v1/staff/calls/dial).
    sender_number: Mapped[str | None] = mapped_column(
        "sender_number_enc", EncryptedText("telephony.sms_inbound.sender_number")
    )
    # First 8 hex digits of the app's client_uuid and the category, as written in the SMS.
    client_prefix: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.report.id", ondelete="SET NULL")
    )
    # created | duplicate | rejected
    outcome: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    # Set when the app later synced the same report (its client_uuid was adopted by the SMS report).
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
