import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, LargeBinary, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

_SCHEMA = {"schema": "medical"}
_DOCTOR = "identity.doctor.user_id"


class LockedFile(Base):
    """The part of a medical file that is not on the emergency card, locked on the reporter's phone (phase C1-b).

    The server stores it and never opens it: only the doctors holding a ``FileKey`` can."""

    __tablename__ = "locked_file"
    __table_args__ = _SCHEMA

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.medical_attachment.report_id", ondelete="CASCADE"), primary_key=True
    )
    nonce: Mapped[bytes] = mapped_column(LargeBinary)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FileKey(Base):
    """The file key locked for one doctor (ephemeral X25519, HKDF-SHA256, AES-256-GCM)."""

    __tablename__ = "file_key"
    __table_args__ = _SCHEMA

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medical.locked_file.report_id", ondelete="CASCADE"), primary_key=True
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(_DOCTOR, ondelete="CASCADE"), primary_key=True
    )
    via: Mapped[str] = mapped_column(Text)
    eph_public: Mapped[bytes] = mapped_column(LargeBinary)
    nonce: Mapped[bytes] = mapped_column(LargeBinary)
    wrapped: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FileOpening(Base):
    __tablename__ = "file_opening"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medical.locked_file.report_id", ondelete="CASCADE")
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey(_DOCTOR, ondelete="CASCADE"))
    as_committee: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
