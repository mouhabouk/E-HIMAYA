"""Resources register of every gouvernorat (phase R1, docs/phase-r/design-resources.md §2).

The vehicles are the ``ops.resource`` rows of phase 4, with their catalogue type and specifications (migration 0059).
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())


class Category(Base):
    """A vehicle or equipment type with its specifications, or a staff speciality with its levels."""

    __tablename__ = "category"
    __table_args__ = {"schema": "inv"}

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str] = mapped_column(Text)
    family: Mapped[str | None] = mapped_column(Text)
    name: Mapped[dict[str, str]] = mapped_column(JSONB)
    specs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    levels: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    position: Mapped[int] = mapped_column(Integer, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(Text)


class Stock(Base):
    """Equipment counted by quantity in a unit."""

    __tablename__ = "stock"
    __table_args__ = {"schema": "inv"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.unit.id"))
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    category_key: Mapped[str] = mapped_column(Text, ForeignKey("inv.category.key", onupdate="CASCADE"))
    specs: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    qty_ready: Mapped[int] = mapped_column(Integer, server_default="0")
    qty_broken: Mapped[int] = mapped_column(Integer, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text)
    # Carried by this vehicle of the unit (R3); None: kept at the unit.
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.resource.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(Text)


class Agent(Base):
    """A member of the civil protection staff; the name and phone are personal data."""

    __tablename__ = "agent"
    __table_args__ = {"schema": "inv"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.unit.id"))
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    matricule: Mapped[str] = mapped_column(Text, unique=True)
    full_name: Mapped[str] = mapped_column(Text)
    rank: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    availability: Mapped[str] = mapped_column(Text, server_default="on_duty")
    notes: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(Text)


class AgentSkill(Base):
    __tablename__ = "agent_skill"
    __table_args__ = {"schema": "inv"}

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inv.agent.id", ondelete="CASCADE"), primary_key=True
    )
    skill_key: Mapped[str] = mapped_column(Text, ForeignKey("inv.category.key", onupdate="CASCADE"), primary_key=True)
    level: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    cert_expires: Mapped[date | None] = mapped_column(Date)


class InventoryRevision(Base):
    """A vehicle, stock line or staff member after one change, with its reason."""

    __tablename__ = "revision"
    __table_args__ = {"schema": "inv"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    entity: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    action: Mapped[str] = mapped_column(Text)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UnitCheck(Base):
    """When the regional room last confirmed a unit's figures (a monthly reminder after 30 days)."""

    __tablename__ = "unit_check"
    __table_args__ = {"schema": "inv"}

    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.unit.id"), primary_key=True)
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    verified_by: Mapped[str] = mapped_column(Text)
    verified_by_name: Mapped[str | None] = mapped_column(Text)


class Transfer(Base):
    """A member of staff moving to another gouvernorat (R3): sent by the room they leave, decided by the joining one."""

    __tablename__ = "transfer"
    __table_args__ = {"schema": "inv"}

    id: Mapped[uuid.UUID] = _uuid_pk()
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("inv.agent.id", ondelete="CASCADE"))
    from_gouvernorat: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    from_unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.unit.id"))
    to_gouvernorat: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    to_unit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.unit.id"))
    effective_on: Mapped[date | None] = mapped_column(Date)
    # pending | accepted | refused | cancelled
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    reason: Mapped[str] = mapped_column(Text)
    decision_reason: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str] = mapped_column(Text)
    requested_by_name: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_by_name: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
