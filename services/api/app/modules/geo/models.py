import uuid
from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geography, Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Gouvernorat(Base):
    __tablename__ = "gouvernorat"
    __table_args__ = {"schema": "geo"}

    code: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    iso_code: Mapped[str] = mapped_column(Text, unique=True)
    name_ar: Mapped[str] = mapped_column(Text)
    name_fr: Mapped[str] = mapped_column(Text)
    # English name (0024_i18n_english): the French one without diacritics where usual ("Gabes", "Beja").
    name_en: Mapped[str] = mapped_column(Text)
    boundary: Mapped[object | None] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), deferred=True)
    # Phase M (migration 0079, Map Tunisia): INS code, economic region, district (decree 2023-589), census, area.
    ins_code: Mapped[int | None] = mapped_column(SmallInteger, unique=True)
    region: Mapped[str | None] = mapped_column(Text, ForeignKey("geo.economic_region.code"))
    district: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.district.number"))
    population_2014: Mapped[int | None] = mapped_column(Integer)
    population_2024: Mapped[int | None] = mapped_column(Integer)
    area_km2: Mapped[float | None] = mapped_column(Float(precision=24))
    label: Mapped[object | None] = mapped_column(Geometry("POINT", srid=4326), deferred=True)

    delegations: Mapped[list["Delegation"]] = relationship(back_populates="gouvernorat", order_by="Delegation.id")


class Delegation(Base):
    __tablename__ = "delegation"
    __table_args__ = (UniqueConstraint("gouvernorat_code", "name_fr"), {"schema": "geo"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    code: Mapped[str] = mapped_column(Text, unique=True)
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    name_ar: Mapped[str] = mapped_column(Text)
    name_fr: Mapped[str] = mapped_column(Text)
    boundary: Mapped[object | None] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), deferred=True)
    # Phase M (migration 0079): the INS 2024 code (4 digits), census and area; our id and names are kept.
    ins_code: Mapped[str | None] = mapped_column(Text, unique=True)
    name_en: Mapped[str | None] = mapped_column(Text)
    population_2014: Mapped[int | None] = mapped_column(Integer)
    population_2024: Mapped[int | None] = mapped_column(Integer)
    area_km2: Mapped[float | None] = mapped_column(Float(precision=24))
    hasc: Mapped[str | None] = mapped_column(Text)
    osm_relation: Mapped[int | None] = mapped_column(BigInteger)
    label: Mapped[object | None] = mapped_column(Geometry("POINT", srid=4326), deferred=True)

    gouvernorat: Mapped[Gouvernorat] = relationship(back_populates="delegations")


class EconomicRegion(Base):
    """One of the 7 economic regions (Grand Tunis, Nord-Est… Sud-Ouest)."""

    __tablename__ = "economic_region"
    __table_args__ = {"schema": "geo"}

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    short: Mapped[str] = mapped_column(Text, unique=True)
    name_ar: Mapped[str] = mapped_column(Text)
    name_fr: Mapped[str] = mapped_column(Text)
    name_en: Mapped[str] = mapped_column(Text)


class District(Base):
    """One of the 5 districts of decree 2023-589 (الأقاليم)."""

    __tablename__ = "district"
    __table_args__ = {"schema": "geo"}

    number: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name_ar: Mapped[str] = mapped_column(Text)
    name_fr: Mapped[str] = mapped_column(Text)
    name_en: Mapped[str] = mapped_column(Text)


class Sector(Base):
    """An imada (عمادة): the 6-digit INS geocode, or ``x<OSM relation>`` where OpenStreetMap has none."""

    __tablename__ = "sector"
    __table_args__ = {"schema": "geo"}

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    delegation_id: Mapped[int] = mapped_column(Integer, ForeignKey("geo.delegation.id"))
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    name_ar: Mapped[str] = mapped_column(Text)
    name_fr: Mapped[str] = mapped_column(Text)
    name_en: Mapped[str] = mapped_column(Text)
    osm_relation: Mapped[int | None] = mapped_column(BigInteger)
    area_km2: Mapped[float | None] = mapped_column(Float(precision=24))
    label: Mapped[object | None] = mapped_column(Geometry("POINT", srid=4326), deferred=True)
    boundary: Mapped[object] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), deferred=True)


class Municipality(Base):
    """A municipality (بلدية), identified by its OpenStreetMap relation (INS publishes no municipality code)."""

    __tablename__ = "municipality"
    __table_args__ = {"schema": "geo"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    name_ar: Mapped[str] = mapped_column(Text)
    name_fr: Mapped[str] = mapped_column(Text)
    name_en: Mapped[str] = mapped_column(Text)
    area_km2: Mapped[float | None] = mapped_column(Float(precision=24))
    label: Mapped[object | None] = mapped_column(Geometry("POINT", srid=4326), deferred=True)
    boundary: Mapped[object] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), deferred=True)


class WaterBody(Base):
    """A lake, dam reservoir, sebkha, chott or lagoon."""

    __tablename__ = "water_body"
    __table_args__ = {"schema": "geo"}

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str] = mapped_column(Text)
    gouvernorat_codes: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger))
    name_ar: Mapped[str] = mapped_column(Text)
    name_fr: Mapped[str] = mapped_column(Text)
    name_en: Mapped[str] = mapped_column(Text)
    salt: Mapped[bool] = mapped_column(Boolean, server_default="false")
    intermittent: Mapped[bool] = mapped_column(Boolean, server_default="false")
    area_km2: Mapped[float | None] = mapped_column(Float(precision=24))
    label: Mapped[object | None] = mapped_column(Geometry("POINT", srid=4326), deferred=True)
    boundary: Mapped[object] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), deferred=True)


class City(Base):
    """The capital, a gouvernorat capital or a municipal seat, with its administrative address."""

    __tablename__ = "city"
    __table_args__ = {"schema": "geo"}

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str] = mapped_column(Text)
    gouvernorat_code: Mapped[int] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    delegation_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("geo.delegation.id"))
    sector_code: Mapped[str | None] = mapped_column(Text, ForeignKey("geo.sector.code"))
    municipality_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("geo.municipality.id"))
    name_ar: Mapped[str] = mapped_column(Text)
    name_fr: Mapped[str] = mapped_column(Text)
    name_en: Mapped[str] = mapped_column(Text)
    place: Mapped[str | None] = mapped_column(Text)
    location: Mapped[object] = mapped_column(Geometry("POINT", srid=4326))


class Layer(Base):
    """A map data layer loaded from files (phase B1, docs/phase-b/design.md §2): hospitals, shelters…"""

    __tablename__ = "layer"
    __table_args__ = {"schema": "geo"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    key: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[dict[str, str]] = mapped_column(JSONB)
    icon: Mapped[str] = mapped_column(Text)
    colour: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(Text, server_default="staff")
    source: Mapped[str] = mapped_column(Text, server_default="")
    licence: Mapped[str] = mapped_column(Text, server_default="")
    to_verify: Mapped[bool] = mapped_column(Boolean, server_default="true")
    # Approximate, invented places for trials ([SIM]), never real ones (migration 0035).
    simulated: Mapped[bool] = mapped_column(Boolean, server_default="false")
    staff_only: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{manager}")
    editors_allowed: Mapped[bool] = mapped_column(Boolean, server_default="false")
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    data_version: Mapped[int] = mapped_column(Integer, server_default="0")
    created_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str] = mapped_column(Text)
    updated_by_name: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Phase L1a (migration 0053, docs/phase-l/design-layers.md §3.3-3.5): who sees the layer and its columns.
    status: Mapped[str] = mapped_column(Text, server_default="published")
    audiences: Mapped[list[str]] = mapped_column(ARRAY(Text))
    scope: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), server_default="{}")
    default_on: Mapped[bool] = mapped_column(Boolean, server_default="true")
    sensitive: Mapped[bool] = mapped_column(Boolean, server_default="false")
    fields: Mapped[dict[str, list[str]]] = mapped_column(JSONB, server_default="{}")
    actions: Mapped[dict[str, bool]] = mapped_column(JSONB)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[str | None] = mapped_column(Text)
    delete_reason: Mapped[str | None] = mapped_column(Text)
    # Phase UI-3b (migration 0058): the folder of the map's layer panel; none means the one the key suggests.
    group_key: Mapped[str | None] = mapped_column(Text, ForeignKey("geo.layer_group.key", onupdate="CASCADE"))


class LayerGroup(Base):
    """A folder of the map's layer panel (phase UI-3b, docs/phase-ui3/design-layer-groups.md): grants nothing."""

    __tablename__ = "layer_group"
    __table_args__ = {"schema": "geo"}

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[dict[str, str]] = mapped_column(JSONB)
    icon: Mapped[str] = mapped_column(Text)
    tone: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, server_default="0")
    sensitive: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(Text)


class LayerRevision(Base):
    """The settings of a layer after one change: going back to it restores them (phase L1a)."""

    __tablename__ = "layer_revision"
    __table_args__ = (UniqueConstraint("layer_id", "number", name="uq_layer_revision"), {"schema": "geo"})

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    layer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("geo.layer.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(Text)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LayerImport(Base):
    """One uploaded file: preview, then applied (or discarded), then possibly undone."""

    __tablename__ = "layer_import"
    __table_args__ = {"schema": "geo"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    layer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("geo.layer.id", ondelete="CASCADE"))
    file_name: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(Text)
    format: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="preview")
    counts: Mapped[dict[str, int]] = mapped_column(JSONB)
    rejected: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    rows: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    undo: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    base_version: Mapped[int] = mapped_column(Integer)
    result_version: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LayerFeature(Base):
    """One place of a layer. ``props`` holds every column but the name, sub-type, phone and position."""

    __tablename__ = "layer_feature"
    __table_args__ = (UniqueConstraint("layer_id", "ref", name="uq_layer_feature_ref"), {"schema": "geo"})

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    layer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("geo.layer.id", ondelete="CASCADE"))
    ref: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    location: Mapped[object] = mapped_column(Geography("POINT", srid=4326))
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("geo.gouvernorat.code"))
    delegation_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("geo.delegation.id"))
    props: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    hidden: Mapped[bool] = mapped_column(Boolean, server_default="false")
    import_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("geo.layer_import.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    updated_by: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Phase L1a: the line or area (``location`` is then a point on it), and the quality of the name.
    shape: Mapped[object | None] = mapped_column(Geography("GEOMETRY", srid=4326))
    name_status: Mapped[str] = mapped_column(Text, server_default="official")
    suggested_name: Mapped[str | None] = mapped_column(Text)
    name_confidence: Mapped[str | None] = mapped_column(Text)
    name_source: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    snapshot_at: Mapped[date | None] = mapped_column(Date)
    possible_duplicate: Mapped[bool] = mapped_column(Boolean, server_default="false")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[str | None] = mapped_column(Text)
    delete_reason: Mapped[str | None] = mapped_column(Text)
