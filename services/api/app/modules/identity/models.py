import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, LargeBinary, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.crypto import EncryptedJSON, EncryptedText, get_cipher
from app.core.db import Base

PHONE_CONTEXT = "identity.profile.phone"


def phone_index(phone: str) -> bytes:
    """Blind index of a normalised phone number (+216XXXXXXXX), for exact lookups of the encrypted phone."""
    return get_cipher().blind_index(phone, context=PHONE_CONTEXT)


# Owner of reports whose reporter was detached by the retention job (architecture §5.3): a fixed account
# with no identifier, created by migration 0010.
DETACHED_ACCOUNT_ID = uuid.UUID(int=0)


class AccountKind(enum.StrEnum):
    CITIZEN = "citizen"
    ORGANIZATION = "organization"
    ANONYMOUS = "anonymous"


class AccountStatus(enum.StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BANNED = "banned"


class Account(Base):
    """One row per user (citizen, institution or anonymous device): the unified USERID."""

    __tablename__ = "account"
    __table_args__ = {"schema": "identity"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    kind: Mapped[AccountKind] = mapped_column(
        Enum(
            AccountKind,
            name="account_kind",
            schema="identity",
            values_callable=lambda e: [m.value for m in e],
        )
    )
    keycloak_sub: Mapped[str | None] = mapped_column(Text, unique=True)
    anon_pseudonym: Mapped[bytes | None] = mapped_column(LargeBinary, unique=True)
    status: Mapped[AccountStatus] = mapped_column(
        Enum(
            AccountStatus,
            name="account_status",
            schema="identity",
            values_callable=lambda e: [m.value for m in e],
        ),
        server_default=AccountStatus.ACTIVE.value,
    )
    false_report_count: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Set when the person exercised the right to erasure: identifiers and profile are gone.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Profile(Base):
    """Citizen profile. Phone, address and medical data are encrypted (columns ``*_enc``); the phone also has
    a blind index for exact lookups. Names and e-mail stay in clear: names for the dispatchers' partial
    search of volunteers, e-mail as the identity-provider login used for delivery and exact lookup."""

    __tablename__ = "profile"
    __table_args__ = {"schema": "identity"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.account.user_id", ondelete="CASCADE"), primary_key=True
    )
    first_name: Mapped[str | None] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    cin_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    cin_hash: Mapped[bytes | None] = mapped_column(LargeBinary, unique=True)
    phone: Mapped[str | None] = mapped_column("phone_enc", EncryptedText(PHONE_CONTEXT))
    phone_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email: Mapped[str | None] = mapped_column(Text)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    delegation_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("geo.delegation.id"))
    address: Mapped[str | None] = mapped_column("address_enc", EncryptedText("identity.profile.address"))
    medical: Mapped[dict[str, Any] | None] = mapped_column("medical_enc", EncryptedJSON("identity.profile.medical"))
    locale: Mapped[str] = mapped_column(Text, server_default="ar")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Consent(Base):
    """Explicit acceptance of the privacy charter (FR-A-001), one row per accepted version."""

    __tablename__ = "consent"
    __table_args__ = {"schema": "identity"}

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.account.user_id", ondelete="CASCADE")
    )
    charter_version: Mapped[str] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(Text)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    platform: Mapped[str | None] = mapped_column(Text)


class ErasureRequest(Base):
    """Identity-provider account to disable after an erasure (POST /me/delete).

    The API holds no Keycloak admin credentials: an administrator (or a future sync job) disables the
    account in the public realm, then sets ``disabled_at``; the row is purged by the retention job.
    """

    __tablename__ = "erasure_request"
    __table_args__ = {"schema": "identity"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    keycloak_sub: Mapped[str] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
