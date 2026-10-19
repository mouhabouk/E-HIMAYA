import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Report(Base):
    __tablename__ = "report"
    __table_args__ = {"schema": "reports"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tracking_code: Mapped[str] = mapped_column(Text, unique=True)
    client_uuid: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.account.user_id"))
    incident_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.incident.id"))
    category: Mapped[str] = mapped_column(Text)
    text_original: Mapped[str | None] = mapped_column(Text)
    lang_original: Mapped[str | None] = mapped_column(Text)
    text_ar: Mapped[str | None] = mapped_column(Text)
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


class Media(Base):
    __tablename__ = "media"
    __table_args__ = {"schema": "reports"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.report.id", ondelete="CASCADE")
    )
    stream_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(Text)
    object_key: Mapped[str] = mapped_column(Text, unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    bytes: Mapped[int | None] = mapped_column(BigInteger)
    duration_s: Mapped[float | None] = mapped_column(Float(precision=24))
    transcript: Mapped[str | None] = mapped_column(Text)
    analysis: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
