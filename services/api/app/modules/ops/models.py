import enum
import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class OpLevel(enum.StrEnum):
    NORMAL = "normal"
    CRISIS = "crisis"
    DISASTER = "disaster"


class Incident(Base):
    __tablename__ = "incident"
    __table_args__ = {"schema": "ops"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    category: Mapped[str] = mapped_column(Text)
    severity: Mapped[int | None] = mapped_column(SmallInteger)
    centroid: Mapped[object | None] = mapped_column(Geography("POINT", srid=4326))
    area: Mapped[object | None] = mapped_column(Geography("POLYGON", srid=4326))
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    delegation_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("geo.delegation.id"))
    op_level: Mapped[OpLevel] = mapped_column(
        Enum(OpLevel, name="op_level", schema="ops", values_callable=lambda e: [m.value for m in e]),
        server_default=OpLevel.NORMAL.value,
    )
    status: Mapped[str] = mapped_column(Text, server_default="open")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TimelineEvent(Base):
    __tablename__ = "timeline_event"
    __table_args__ = {"schema": "ops"}

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.incident.id", ondelete="CASCADE")
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
