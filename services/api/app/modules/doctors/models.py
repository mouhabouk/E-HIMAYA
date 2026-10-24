import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, LargeBinary, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.crypto import EncryptedText
from app.core.db import Base


class Doctor(Base):
    """A registered citizen who declares themselves a doctor (phase C1-a). Reviewed by staff before any file."""

    __tablename__ = "doctor"
    __table_args__ = {"schema": "identity"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.account.user_id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    specialties: Mapped[list[str]] = mapped_column(ARRAY(Text))
    licence_no: Mapped[str | None] = mapped_column("licence_no_enc", EncryptedText("identity.doctor.licence_no"))
    workplace: Mapped[str] = mapped_column(Text)
    # The doctor's group: where they work, not where they live.
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    cp_unit: Mapped[str | None] = mapped_column(Text)
    cp_staff_no: Mapped[str | None] = mapped_column("cp_staff_no_enc", EncryptedText("identity.doctor.cp_staff_no"))
    terms_version: Mapped[str] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    review_reason: Mapped[str | None] = mapped_column(Text)
    available_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Member of the national medical committee while ``committee_until`` is in the future (appointed by the sysadmin).
    committee_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    committee_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    committee_by: Mapped[str | None] = mapped_column(Text)
    # Phase C1-b: the doctor's X25519 public key, and their private key locked by their own code (opened on the phone).
    public_key: Mapped[bytes | None] = mapped_column(LargeBinary)
    key_backup: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    key_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DoctorReview(Base):
    __tablename__ = "doctor_review"
    __table_args__ = {"schema": "identity"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.doctor.user_id", ondelete="CASCADE")
    )
    decision: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
