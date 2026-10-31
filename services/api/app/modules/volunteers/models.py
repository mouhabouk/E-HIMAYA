import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.crypto import EncryptedText
from app.core.db import Base


class Volunteer(Base):
    """A registered citizen who volunteers (FR-A-020). Extends the account; reviewed by staff (FR-A-021)."""

    __tablename__ = "volunteer"
    __table_args__ = {"schema": "identity"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.account.user_id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    skills: Mapped[list[str]] = mapped_column(ARRAY(Text))
    # The volunteer's own free text is encrypted.
    other_skill: Mapped[str | None] = mapped_column("other_skill_enc", EncryptedText("identity.volunteer.other_skill"))
    availability: Mapped[str] = mapped_column(Text)
    period_from: Mapped[date] = mapped_column(Date)
    period_to: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column("notes_enc", EncryptedText("identity.volunteer.notes"))
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    review_reason: Mapped[str | None] = mapped_column(Text)
    # Readiness end (FR-A-022); the live position is in Valkey only (volunteers.presence).
    ready_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    # Phase D (S2-5): the key of the volunteer's signed SMS answers (EH3), and the time of the last one applied.
    sms_key: Mapped[str | None] = mapped_column("sms_key_enc", EncryptedText("identity.volunteer.sms_key"))
    sms_last_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VolunteerReview(Base):
    __tablename__ = "volunteer_review"
    __table_args__ = {"schema": "identity"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.volunteer.user_id", ondelete="CASCADE")
    )
    decision: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
