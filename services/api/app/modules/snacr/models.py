"""Risk analysis and coverage plan, SNACR (docs/phase-s/design-s.md): the archive of past interventions, the alternative
names that tie the archive to the INS délégations, the register of specific risks and the plans."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Dataset(Base):
    """One year of the archive: the Office's file, or rows generated [SIM] on the 2022 distributions."""

    __tablename__ = "dataset"
    __table_args__ = {"schema": "snacr"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    year: Mapped[int] = mapped_column(SmallInteger, unique=True)
    source: Mapped[str] = mapped_column(Text)
    simulated: Mapped[bool] = mapped_column(Boolean)
    file_name: Mapped[str | None] = mapped_column(Text)
    rows: Mapped[int] = mapped_column(Integer)
    quality: Mapped[dict[str, Any]] = mapped_column(JSONB)
    imported_by: Mapped[str] = mapped_column(Text)
    imported_by_name: Mapped[str | None] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Intervention(Base):
    """One past intervention, without its address, description, crew or vehicles (dropped on import)."""

    __tablename__ = "intervention"
    __table_args__ = {"schema": "snacr"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("snacr.dataset.id"))
    year: Mapped[int] = mapped_column(SmallInteger)
    family: Mapped[str] = mapped_column(Text)
    nature: Mapped[str] = mapped_column(Text)
    subtype: Mapped[str | None] = mapped_column(Text)
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    delegation_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("geo.delegation.id"))
    delegation_raw: Mapped[str] = mapped_column(Text)
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    departed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrival_min: Mapped[float | None] = mapped_column(Float)
    # Phase S2: the end of the mission and its crew, from the records of the operations room.
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hospital_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    crew_count: Mapped[int | None] = mapped_column(SmallInteger)
    flags: Mapped[list[str]] = mapped_column(ARRAY(Text))


class Alias(Base):
    """Another way the archive writes a délégation ("المنستير المدينة" for المنستير)."""

    __tablename__ = "alias"
    __table_args__ = {"schema": "snacr"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    raw: Mapped[str] = mapped_column(Text)
    normalized: Mapped[str] = mapped_column(Text)
    delegation_id: Mapped[int] = mapped_column(Integer, ForeignKey("geo.delegation.id"))
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SpecialRisk(Base):
    """A specific risk of a gouvernorat (flood, forest fire, industrial site…): probability and gravity, 1 to 5."""

    __tablename__ = "special_risk"
    __table_args__ = {"schema": "snacr"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    hazard: Mapped[str] = mapped_column(Text)
    probability: Mapped[int] = mapped_column(SmallInteger)
    gravity: Mapped[int] = mapped_column(SmallInteger)
    note: Mapped[str | None] = mapped_column(Text)
    simulated: Mapped[bool] = mapped_column(Boolean)
    updated_by: Mapped[str] = mapped_column(Text)
    updated_by_name: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Plan(Base):
    """A national or regional plan: a frozen snapshot of the analysis, a draft until its committee approves it."""

    __tablename__ = "plan"
    __table_args__ = {"schema": "snacr"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    version: Mapped[int] = mapped_column(Integer)
    years: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger))
    status: Mapped[str] = mapped_column(Text)
    simulated: Mapped[bool] = mapped_column(Boolean)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_by: Mapped[str | None] = mapped_column(Text)
    approved_by_name: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
