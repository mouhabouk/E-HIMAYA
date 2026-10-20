from geoalchemy2 import Geometry
from sqlalchemy import ForeignKey, Integer, SmallInteger, Text, UniqueConstraint
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

    gouvernorat: Mapped[Gouvernorat] = relationship(back_populates="delegations")
