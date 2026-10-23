import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, FetchedValue, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.crypto import EncryptedText
from app.core.db import Base


class ContactRequest(Base):
    """A "contact us" request from the app (phase B1, design §2ter); contact details and texts encrypted."""

    __tablename__ = "request"
    __table_args__ = {"schema": "contact"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    # CT-YYYY-NNNNNN, given by the database (sequence) and read back on insert.
    number: Mapped[str] = mapped_column(Text, server_default=FetchedValue())
    kind: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="received")
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.account.user_id", ondelete="SET NULL")
    )
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    subject: Mapped[str] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column("name_enc", EncryptedText("contact.request.name"))
    phone: Mapped[str | None] = mapped_column("phone_enc", EncryptedText("contact.request.phone"))
    email: Mapped[str | None] = mapped_column("email_enc", EncryptedText("contact.request.email"))
    message: Mapped[str] = mapped_column("message_enc", EncryptedText("contact.request.message"))
    answer: Mapped[str | None] = mapped_column("answer_enc", EncryptedText("contact.request.answer"))
    locale: Mapped[str] = mapped_column(Text, server_default="ar")
    platform: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_to: Mapped[str | None] = mapped_column(Text)
    assigned_name: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContactEvent(Base):
    """History of a request; ``visible`` events (status, answer) are shown to the citizen, notes never."""

    __tablename__ = "request_event"
    __table_args__ = {"schema": "contact"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contact.request.id", ondelete="CASCADE")
    )
    action: Mapped[str] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger)
    note: Mapped[str | None] = mapped_column("note_enc", EncryptedText("contact.request_event.note"))
    visible: Mapped[bool] = mapped_column(Boolean, server_default="false")
    actor: Mapped[str] = mapped_column(Text)
    actor_name: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
