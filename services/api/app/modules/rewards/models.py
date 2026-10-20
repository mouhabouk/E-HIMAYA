"""Points ledger, rules, queued awards, badges, nominations and certificates (migration 0017)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

_SCHEMA = {"schema": "rewards"}


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())


class RewardRule(Base):
    __tablename__ = "rule"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = _uuid_pk()
    reason: Mapped[str] = mapped_column(Text)
    # NULL: the default of the reason; otherwise an override for reports of this category.
    category: Mapped[str | None] = mapped_column(Text)
    points: Mapped[int | None] = mapped_column(Integer)
    multiplier: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    is_default: Mapped[bool] = mapped_column(Boolean, server_default="false")
    description: Mapped[dict[str, str]] = mapped_column(JSONB, server_default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(Text)


class LedgerEntry(Base):
    """Append-only (database trigger): corrections are new rows (``manual``, ``revocation``)."""

    __tablename__ = "points_ledger"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    citizen_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.account.user_id", ondelete="CASCADE")
    )
    delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.report.id", ondelete="SET NULL")
    )
    intervention_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="SET NULL")
    )
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rewards.rule.id", ondelete="SET NULL")
    )
    multiplier: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    capped: Mapped[bool] = mapped_column(Boolean, server_default="false")
    dedup_key: Mapped[str | None] = mapped_column(Text, unique=True)
    revokes_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("rewards.points_ledger.id", ondelete="CASCADE"), unique=True
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PendingAward(Base):
    """An automatic award held while its gouvernorat is at level ``disaster``; applied when the level drops."""

    __tablename__ = "pending_award"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    citizen_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.account.user_id", ondelete="CASCADE")
    )
    reason: Mapped[str] = mapped_column(Text)
    points: Mapped[int] = mapped_column(Integer)
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.report.id", ondelete="SET NULL")
    )
    intervention_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="SET NULL")
    )
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rewards.rule.id", ondelete="SET NULL")
    )
    multiplier: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    dedup_key: Mapped[str] = mapped_column(Text, unique=True)
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BadgeAward(Base):
    __tablename__ = "badge_award"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = _uuid_pk()
    citizen_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.account.user_id", ondelete="CASCADE")
    )
    level: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    balance_at_award: Mapped[int] = mapped_column(Integer)
    awarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)


class Nomination(Base):
    __tablename__ = "nomination"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = _uuid_pk()
    kind: Mapped[str] = mapped_column(Text)
    subject_kind: Mapped[str] = mapped_column(Text)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    year: Mapped[int] = mapped_column(SmallInteger)
    reason: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, server_default="proposed")
    proposed_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_by: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    anonymised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RewardCertificate(Base):
    __tablename__ = "certificate"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = _uuid_pk()
    code: Mapped[str] = mapped_column(Text, unique=True)
    kind: Mapped[str] = mapped_column(Text)
    badge_award_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rewards.badge_award.id", ondelete="SET NULL"), unique=True
    )
    nomination_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rewards.nomination.id", ondelete="SET NULL"), unique=True
    )
    subject_kind: Mapped[str] = mapped_column(Text)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    distinction: Mapped[str] = mapped_column(Text)
    initials: Mapped[str] = mapped_column(Text)
    year: Mapped[int] = mapped_column(SmallInteger)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    issued_by: Mapped[str] = mapped_column(Text)
    signature: Mapped[bytes] = mapped_column(LargeBinary)
    pdf_object_key: Mapped[str | None] = mapped_column(Text)
    pdf_sha256: Mapped[str | None] = mapped_column(Text)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[str | None] = mapped_column(Text)
    revoked_reason: Mapped[str | None] = mapped_column(Text)


class ConsumerCursor(Base):
    __tablename__ = "consumer_cursor"
    __table_args__ = _SCHEMA

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    last_id: Mapped[int] = mapped_column(BigInteger, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
