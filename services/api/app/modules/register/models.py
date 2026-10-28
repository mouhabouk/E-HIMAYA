"""Register of plans, decisions and instructions (migration 0057, phase L3b, docs/phase-l/design-l3b.md)."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Computed, Date, DateTime, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

_S = {"schema": "register"}


def _doc_fk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), ForeignKey("register.document.id", ondelete="CASCADE"))


class Document(Base):
    __tablename__ = "document"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    number: Mapped[str] = mapped_column(Text, unique=True)
    # The official reference: "قرار والي نابل عدد 27 لسنة 2026".
    reference: Mapped[str] = mapped_column(Text, server_default="")
    kind: Mapped[str] = mapped_column(Text)
    # The hazard of a plan (phase PL1, migration 0061); only a plan has one.
    hazard_key: Mapped[str | None] = mapped_column(Text, ForeignKey("register.hazard.key", onupdate="CASCADE"))
    # central | regional (with a gouvernorat).
    level: Mapped[str] = mapped_column(Text)
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    issuer: Mapped[str] = mapped_column(Text)
    signatory: Mapped[str] = mapped_column(Text, server_default="")
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, server_default="")
    body: Mapped[str] = mapped_column(Text, server_default="")
    topics: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    issued_on: Mapped[date] = mapped_column(Date)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, server_default="draft")
    repealed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("register.document.id", ondelete="SET NULL")
    )
    repeal_reason: Mapped[str | None] = mapped_column(Text)
    access: Mapped[str] = mapped_column(Text, server_default="all")
    axis_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), server_default="{}")
    # manual | axis (a signed recommendation or decision of a crisis axis).
    source: Mapped[str] = mapped_column(Text, server_default="manual")
    directive_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crisis.directive.id", ondelete="SET NULL"), unique=True
    )
    signature: Mapped[str | None] = mapped_column(Text)
    key_id: Mapped[str | None] = mapped_column(Text)
    file_key: Mapped[str | None] = mapped_column(Text)
    file_name: Mapped[str | None] = mapped_column(Text)
    file_type: Mapped[str | None] = mapped_column(Text)
    file_size: Mapped[int | None] = mapped_column(Integer)
    file_sha256: Mapped[str | None] = mapped_column(Text)
    norm: Mapped[str] = mapped_column(Text, server_default="")
    search: Mapped[Any] = mapped_column(TSVECTOR, Computed("to_tsvector('simple'::regconfig, norm)"), deferred=True)
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str] = mapped_column(Text)
    updated_by_name: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, server_default="1")


class Hazard(Base):
    """A hazard an intervention plan answers, with the colour of its plan (phase PL1, migration 0061)."""

    __tablename__ = "hazard"
    __table_args__ = _S

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[dict[str, str]] = mapped_column(JSONB)
    colour: Mapped[str] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    updated_by: Mapped[str | None] = mapped_column(Text)
    updated_by_name: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Counter(Base):
    __tablename__ = "counter"
    __table_args__ = _S

    # REG (documents), DIR (directives), NOT (notices).
    series: Mapped[str] = mapped_column(Text, primary_key=True, server_default="REG")
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last: Mapped[int] = mapped_column(Integer)


class Link(Base):
    __tablename__ = "link"
    __table_args__ = _S

    from_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("register.document.id", ondelete="CASCADE"), primary_key=True
    )
    to_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("register.document.id", ondelete="CASCADE"), primary_key=True
    )
    # repeals | amends | complements
    relation: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Recommendation(Base):
    __tablename__ = "recommendation"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    document_id: Mapped[uuid.UUID] = _doc_fk()
    number: Mapped[int] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(Text)
    responsible: Mapped[str] = mapped_column(Text, server_default="")
    due_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, server_default="proposed")
    status_reason: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[str] = mapped_column(Text)
    updated_by_name: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Revision(Base):
    __tablename__ = "revision"
    __table_args__ = _S

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("register.document.id", ondelete="CASCADE"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    change: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Dispatch(Base):
    """A directive of the centre to the gouvernorats, or a notice of a gouvernorat to the centre (design §8)."""

    __tablename__ = "dispatch"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    number: Mapped[str] = mapped_column(Text, unique=True)
    # directive | notice
    kind: Mapped[str] = mapped_column(Text)
    # all | targeted (directives) | centre (notices)
    audience: Mapped[str] = mapped_column(Text)
    origin_gouvernorat: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    urgency: Mapped[str] = mapped_column(Text, server_default="normal")
    subject: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, server_default="")
    topics: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="SET NULL")
    )
    axis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crisis.axis.id", ondelete="SET NULL", use_alter=True)
    )
    reply_required: Mapped[bool] = mapped_column(Boolean, server_default="true")
    reply_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, server_default="open")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by_name: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    norm: Mapped[str] = mapped_column(Text, server_default="")
    search: Mapped[Any] = mapped_column(TSVECTOR, Computed("to_tsvector('simple'::regconfig, norm)"), deferred=True)


class DispatchTarget(Base):
    __tablename__ = "dispatch_target"
    __table_args__ = _S

    dispatch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("register.dispatch.id", ondelete="CASCADE"), primary_key=True
    )
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"), primary_key=True)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seen_by_name: Mapped[str | None] = mapped_column(Text)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replies: Mapped[int] = mapped_column(Integer, server_default="0")


class Reply(Base):
    """One message in the thread of one gouvernorat (the centre and that gouvernorat read it)."""

    __tablename__ = "reply"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    dispatch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("register.dispatch.id", ondelete="CASCADE")
    )
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    # centre | regional
    side: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, server_default="")
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Attachment(Base):
    __tablename__ = "attachment"
    __table_args__ = _S

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    dispatch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("register.dispatch.id", ondelete="CASCADE")
    )
    reply_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("register.reply.id", ondelete="CASCADE")
    )
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    file_key: Mapped[str] = mapped_column(Text)
    file_name: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(Text)
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
