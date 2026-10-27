import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    event,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.crypto import EncryptedJSON, EncryptedText, search_tokens
from app.core.db import Base

SEARCH_CONTEXT = "reports.report.search"


class Report(Base):
    __tablename__ = "report"
    __table_args__ = {"schema": "reports"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tracking_code: Mapped[str] = mapped_column(Text, unique=True)
    client_uuid: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.account.user_id"))
    incident_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.incident.id"))
    # Set when a member reports on behalf of an institution (FR-A-080).
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("org.organization.id"))
    category: Mapped[str] = mapped_column(Text)
    # Free text and its translation are encrypted; ``search_tokens`` holds blind indexes of their words so
    # the dashboard can still search whole words. The point stays in clear (PostGIS: scope, map, grouping).
    text_original: Mapped[str | None] = mapped_column(
        "text_original_enc", EncryptedText("reports.report.text_original")
    )
    lang_original: Mapped[str | None] = mapped_column(Text)
    text_ar: Mapped[str | None] = mapped_column("text_ar_enc", EncryptedText("reports.report.text_ar"))
    search_tokens: Mapped[list[bytes]] = mapped_column(ARRAY(LargeBinary), server_default="{}")
    location: Mapped[object] = mapped_column(Geography("POINT", srid=4326))
    location_accuracy_m: Mapped[float | None] = mapped_column(Float(precision=24))
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    delegation_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("geo.delegation.id"))
    priority_score: Mapped[int | None] = mapped_column(SmallInteger)
    credibility_score: Mapped[int | None] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(Text, server_default="received")
    source: Mapped[str] = mapped_column(Text, server_default="app")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), deferred=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # F-APP-38 (phase P4d): the first team set off, then arrived.
    team_en_route_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    team_on_scene_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Accepted beyond the anonymous budget or while the limiter ran degraded: a human checks it first (A1).
    needs_verification: Mapped[bool] = mapped_column(Boolean, server_default="false")
    verification_reason: Mapped[str | None] = mapped_column(Text)
    # Set by the retention job: reporter detached, free text and media gone, point coarsened (§5.3).
    anonymised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Jurisdiction (phase 9 §4): the location decides who handles the report, only once it is trusted or verified;
    # pending/contradictory reports keep gouvernorat_code NULL and wait in the central geo-verification queue.
    geo_state: Mapped[str] = mapped_column(Text, server_default="trusted")
    geo_candidates: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), server_default="{}")
    geo_reason: Mapped[str | None] = mapped_column(Text)
    geo_verified_by: Mapped[str | None] = mapped_column(Text)
    geo_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Room handling the report: "central" or "g:<code>".
    claimed_room: Mapped[str | None] = mapped_column(Text)
    claimed_by: Mapped[str | None] = mapped_column(Text)
    claimed_by_name: Mapped[str | None] = mapped_column(Text)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Claim deadline from the priority band (national settings); the SLA worker marks unclaimed reports late.
    sla_band: Mapped[str | None] = mapped_column(Text)
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    escalation_state: Mapped[str] = mapped_column(Text, server_default="none")
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    referred_to: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))


def report_search_tokens(text_original: str | None, text_ar: str | None) -> list[bytes]:
    return search_tokens([text_original, text_ar], context=SEARCH_CONTEXT)


@event.listens_for(Report.text_original, "set")
def _text_set(target: Report, value: str | None, _old: object, _initiator: object) -> None:
    target.search_tokens = report_search_tokens(value, target.text_ar)


@event.listens_for(Report.text_ar, "set")
def _text_ar_set(target: Report, value: str | None, _old: object, _initiator: object) -> None:
    target.search_tokens = report_search_tokens(target.text_original, value)


class StatusHistory(Base):
    __tablename__ = "status_history"
    __table_args__ = {"schema": "reports"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.report.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)


class Media(Base):
    __tablename__ = "media"
    __table_args__ = {"schema": "reports"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.report.id", ondelete="CASCADE")
    )
    # Recordings and vision frames of a live stream (phase 6).
    stream_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.live_stream.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(Text)
    object_key: Mapped[str] = mapped_column(Text, unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    bytes: Mapped[int | None] = mapped_column(BigInteger)
    duration_s: Mapped[float | None] = mapped_column(Float(precision=24))
    transcript: Mapped[str | None] = mapped_column("transcript_enc", EncryptedText("reports.media.transcript"))
    translation_ar: Mapped[str | None] = mapped_column(
        "translation_ar_enc", EncryptedText("reports.media.translation_ar")
    )
    # Transcription metadata only (language, model, error); the texts are in the encrypted columns.
    analysis: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    upload_id: Mapped[str | None] = mapped_column(Text, unique=True)
    content_type: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="uploading")
    # Type found in the bytes by the verification worker; media is only ever served with this type (A7).
    verified_type: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    stored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Escalation(Base):
    """One step of a report's escalation (late, central claim, referral, answer, verification, release)."""

    __tablename__ = "escalation"
    __table_args__ = {"schema": "reports"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.report.id", ondelete="CASCADE")
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(Text)
    from_room: Mapped[str | None] = mapped_column(Text)
    to_room: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(Text)
    actor_name: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reason: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")


class ReporterContext(Base):
    """Reporter's residence gouvernorat at creation. Restricted (§1.3): never used to decide who handles a report."""

    __tablename__ = "reporter_context"
    __table_args__ = {"schema": "reports"}

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.report.id", ondelete="CASCADE"), primary_key=True
    )
    reporter_gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    source: Mapped[str] = mapped_column(Text)


class MedicalAttachment(Base):
    """The reporter's medical file, attached to this report only because they ticked it (phase B2, addition 7b).

    Encrypted; read only by staff allowed to see the reporter (each opening audited); deleted 30 days after the report
    is closed, at anonymisation and on erasure."""

    __tablename__ = "medical_attachment"
    __table_args__ = {"schema": "reports"}

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.report.id", ondelete="CASCADE"), primary_key=True
    )
    data: Mapped[dict[str, Any]] = mapped_column("data_enc", EncryptedJSON("reports.medical_attachment.data"))
    attached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
