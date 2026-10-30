"""Administrative reference of Tunisia from Map Tunisia (phase M, docs/phase-m/design-m.md §2).

Map Tunisia (ODbL 1.0, © OpenStreetMap contributors, cross-checked against the INS 2024 nomenclature) replaces the
simplified geoBoundaries outlines of the 24 gouvernorats and adds what the reference lacked:

* gouvernorats: INS code, economic region, district (decree 2023-589), census population 2014 and 2024, area;
* délégations: the 279 boundaries, INS code, English name, population, area (our ids and names are kept);
* new tables ``geo.sector`` (2,083 imadas), ``geo.municipality`` (338 of 350 baladiyat), ``geo.economic_region`` (7),
  ``geo.district`` (5), ``geo.city`` (284) and ``geo.water_body`` (67 lakes, dams, sebkhas, chotts, lagoons);
* every report gets the délégation, imada and municipality that contain its position (``delegation_id`` already
  existed but was never filled), and the reports already received are filled once here.

The files are in ``seed/geo/admin/`` (scripts/admin_reference.py, SOURCE.md gives the commit and checksums).

Revision ID: 0079_admin_reference
Revises: 0078_command_voice
Create Date: 2026-10-30
"""

import csv
import gzip
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from alembic import op

from migrations.sqlutil import run_script

revision: str = "0079_admin_reference"
down_revision: str | None = "0078_command_voice"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEED = Path(__file__).resolve().parents[2] / "seed" / "geo"
ADMIN = SEED / "admin"
GEOM = "ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326)), 3))"
LABEL = "ST_SetSRID(ST_MakePoint(:label_lon, :label_lat), 4326)"

UPGRADE = """
CREATE TABLE geo.economic_region (
    code      text PRIMARY KEY,
    short     text NOT NULL UNIQUE,
    name_ar   text NOT NULL,
    name_fr   text NOT NULL,
    name_en   text NOT NULL
);
CREATE TABLE geo.district (
    number    smallint PRIMARY KEY,
    name_ar   text NOT NULL,
    name_fr   text NOT NULL,
    name_en   text NOT NULL
);
ALTER TABLE geo.gouvernorat
    ADD COLUMN ins_code smallint UNIQUE,
    ADD COLUMN region text REFERENCES geo.economic_region(code),
    ADD COLUMN district smallint REFERENCES geo.district(number),
    ADD COLUMN population_2014 integer,
    ADD COLUMN population_2024 integer,
    ADD COLUMN area_km2 real,
    ADD COLUMN label geometry(Point, 4326);
ALTER TABLE geo.delegation
    ADD COLUMN ins_code text UNIQUE,
    ADD COLUMN name_en text,
    ADD COLUMN population_2014 integer,
    ADD COLUMN population_2024 integer,
    ADD COLUMN area_km2 real,
    ADD COLUMN hasc text,
    ADD COLUMN osm_relation bigint,
    ADD COLUMN label geometry(Point, 4326);

-- Imadas: the 6-digit INS geocode, or "x<OSM relation>" where OpenStreetMap has none.
CREATE TABLE geo.sector (
    code              text PRIMARY KEY,
    delegation_id     integer NOT NULL REFERENCES geo.delegation(id),
    gouvernorat_code  smallint NOT NULL REFERENCES geo.gouvernorat(code),
    name_ar           text NOT NULL,
    name_fr           text NOT NULL,
    name_en           text NOT NULL,
    osm_relation      bigint,
    area_km2          real,
    label             geometry(Point, 4326),
    boundary          geometry(MultiPolygon, 4326) NOT NULL
);
CREATE INDEX ix_sector_delegation ON geo.sector (delegation_id);
CREATE INDEX ix_sector_boundary ON geo.sector USING gist (boundary);

-- Municipalities: the OpenStreetMap relation (INS publishes no municipality code).
CREATE TABLE geo.municipality (
    id                bigint PRIMARY KEY,
    gouvernorat_code  smallint NOT NULL REFERENCES geo.gouvernorat(code),
    name_ar           text NOT NULL,
    name_fr           text NOT NULL,
    name_en           text NOT NULL,
    area_km2          real,
    label             geometry(Point, 4326),
    boundary          geometry(MultiPolygon, 4326) NOT NULL
);
CREATE INDEX ix_municipality_gouvernorat ON geo.municipality (gouvernorat_code);
CREATE INDEX ix_municipality_boundary ON geo.municipality USING gist (boundary);

CREATE TABLE geo.water_body (
    id                 text PRIMARY KEY,
    kind               text NOT NULL CHECK (kind IN ('lake', 'reservoir', 'sebkha', 'chott', 'lagoon')),
    gouvernorat_codes  smallint[] NOT NULL,
    name_ar            text NOT NULL,
    name_fr            text NOT NULL,
    name_en            text NOT NULL,
    salt               boolean NOT NULL DEFAULT false,
    intermittent       boolean NOT NULL DEFAULT false,
    area_km2           real,
    label              geometry(Point, 4326),
    boundary           geometry(MultiPolygon, 4326) NOT NULL
);
CREATE INDEX ix_water_body_boundary ON geo.water_body USING gist (boundary);

-- The capital, the gouvernorat capitals and the municipal seats, with their full administrative address.
CREATE TABLE geo.city (
    id                text PRIMARY KEY,
    kind              text NOT NULL CHECK (kind IN ('national_capital', 'governorate_capital', 'city')),
    gouvernorat_code  smallint NOT NULL REFERENCES geo.gouvernorat(code),
    delegation_id     integer REFERENCES geo.delegation(id),
    sector_code       text REFERENCES geo.sector(code),
    municipality_id   bigint REFERENCES geo.municipality(id),
    name_ar           text NOT NULL,
    name_fr           text NOT NULL,
    name_en           text NOT NULL,
    place             text,
    location          geometry(Point, 4326) NOT NULL
);
CREATE INDEX ix_city_gouvernorat ON geo.city (gouvernorat_code);

ALTER TABLE reports.report
    ADD COLUMN sector_code text REFERENCES geo.sector(code),
    ADD COLUMN municipality_id bigint REFERENCES geo.municipality(id);
"""

# Reports already received: the délégation, imada and municipality that contain their position.
BACKFILL = """
UPDATE reports.report r SET delegation_id = d.id
  FROM geo.delegation d
 WHERE r.delegation_id IS NULL AND ST_Intersects(d.boundary, r.location::geometry);
UPDATE reports.report r SET sector_code = s.code
  FROM geo.sector s
 WHERE r.sector_code IS NULL AND ST_Intersects(s.boundary, r.location::geometry);
UPDATE reports.report r SET municipality_id = m.id
  FROM geo.municipality m
 WHERE r.municipality_id IS NULL AND ST_Intersects(m.boundary, r.location::geometry);
"""

DOWNGRADE = """
ALTER TABLE reports.report DROP COLUMN municipality_id, DROP COLUMN sector_code;
DROP TABLE geo.city;
DROP TABLE geo.water_body;
DROP TABLE geo.municipality;
DROP TABLE geo.sector;
ALTER TABLE geo.delegation
    DROP COLUMN label, DROP COLUMN osm_relation, DROP COLUMN hasc, DROP COLUMN area_km2,
    DROP COLUMN population_2024, DROP COLUMN population_2014, DROP COLUMN name_en, DROP COLUMN ins_code;
UPDATE geo.delegation SET boundary = NULL;
ALTER TABLE geo.gouvernorat
    DROP COLUMN label, DROP COLUMN area_km2, DROP COLUMN population_2024, DROP COLUMN population_2014,
    DROP COLUMN district, DROP COLUMN region, DROP COLUMN ins_code;
DROP TABLE geo.district;
DROP TABLE geo.economic_region;
"""


def _features(name: str) -> list[dict[str, Any]]:
    with gzip.open(ADMIN / f"{name}.geojson.gz", "rt", encoding="utf-8") as fh:
        features: list[dict[str, Any]] = json.load(fh)["features"]
    return features


def _csv(name: str) -> list[dict[str, str]]:
    with (ADMIN / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _int(value: Any) -> int | None:
    return int(value) if value not in (None, "") else None


def _real(value: Any) -> float | None:
    return float(value) if value not in (None, "") else None


def _label(p: dict[str, Any]) -> dict[str, float | None]:
    return {"label_lon": _real(p.get("label_lon")), "label_lat": _real(p.get("label_lat"))}


def _expect(bind: sa.Connection, sql: str, count: int, what: str) -> None:
    found = bind.scalar(sa.text(sql))
    if found != count:
        raise RuntimeError(f"expected {count} {what}, found {found}")


def upgrade() -> None:
    run_script(UPGRADE)
    bind = op.get_bind()

    bind.execute(
        sa.text(
            "INSERT INTO geo.economic_region (code, short, name_ar, name_fr, name_en) "
            "VALUES (:id, :code, :name_ar, :name_fr, :name_en)"
        ),
        _csv("regions.csv"),
    )
    bind.execute(
        sa.text("INSERT INTO geo.district (number, name_ar, name_fr, name_en) VALUES (:number, :ar, :fr, :en)"),
        [
            {"number": int(r["number"]), "ar": r["name_ar"], "fr": r["name_fr"], "en": r["name_en"]}
            for r in _csv("districts.csv")
        ],
    )

    bind.execute(
        sa.text(
            f"UPDATE geo.gouvernorat SET boundary = {GEOM}, ins_code = :ins, region = :region, district = :district, "  # noqa: S608 (constant SQL fragments, values are bound)
            f"population_2014 = :p14, population_2024 = :p24, area_km2 = :area, label = {LABEL} WHERE iso_code = :iso"
        ),
        [
            {
                "iso": p["iso_3166_2"],
                "geom": json.dumps(f["geometry"]),
                "ins": int(p["ins_code"]),
                "region": p["region"],
                "district": int(p["district"].removeprefix("district-")),
                "p14": _int(p["population_2014"]),
                "p24": _int(p["population_2024"]),
                "area": _real(p["area_km2"]),
                **_label(p),
            }
            for f in _features("governorates")
            for p in [f["properties"]]
        ],
    )
    _expect(bind, "SELECT count(*) FROM geo.gouvernorat WHERE ins_code IS NOT NULL", 24, "gouvernorats")

    bind.execute(
        sa.text(
            f"UPDATE geo.delegation SET boundary = {GEOM}, ins_code = :ins, name_en = :en, population_2014 = :p14, "  # noqa: S608 (constant SQL fragments, values are bound)
            f"population_2024 = :p24, area_km2 = :area, hasc = NULLIF(:hasc, ''), osm_relation = :osm, "
            f"label = {LABEL} WHERE gouvernorat_code = :gov AND name_fr = :ours"
        ),
        [
            {
                "gov": int(p["governorate"].removeprefix("TN-")),
                "ours": p["ehimaya_name_fr"],
                "geom": json.dumps(f["geometry"]),
                "ins": p["ins_code"],
                "en": p["name_en"],
                "p14": _int(p["population_2014"]),
                "p24": _int(p["population_2024"]),
                "area": _real(p["area_km2"]),
                "hasc": p["hasc"],
                "osm": _int(p["osm_relation"]),
                **_label(p),
            }
            for f in _features("delegations")
            for p in [f["properties"]]
        ],
    )
    _expect(bind, "SELECT count(*) FROM geo.delegation WHERE ins_code IS NOT NULL", 279, "délégations")

    bind.execute(
        sa.text(
            "INSERT INTO geo.sector (code, delegation_id, gouvernorat_code, name_ar, name_fr, name_en, osm_relation, "  # noqa: S608 (constant SQL fragments, values are bound)
            f"area_km2, label, boundary) SELECT :code, d.id, d.gouvernorat_code, :ar, :fr, :en, :osm, :area, {LABEL}, "
            f"{GEOM} FROM geo.delegation d WHERE d.ins_code = :delegation"
        ),
        [
            {
                "code": p["id"].removeprefix("sector-"),
                "delegation": p["delegation"].removeprefix("delegation-"),
                "ar": p["name_ar"],
                "fr": p["name_fr"],
                "en": p["name_en"],
                "osm": _int(p["osm_relation"]),
                "area": _real(p["area_km2"]),
                "geom": json.dumps(f["geometry"]),
                **_label(p),
            }
            for f in _features("sectors")
            for p in [f["properties"]]
        ],
    )
    _expect(bind, "SELECT count(*) FROM geo.sector", 2083, "imadas")

    bind.execute(
        sa.text(
            "INSERT INTO geo.municipality (id, gouvernorat_code, name_ar, name_fr, name_en, area_km2, label, boundary) "  # noqa: S608 (constant SQL fragments, values are bound)
            f"VALUES (:id, :gov, :ar, :fr, :en, :area, {LABEL}, {GEOM})"
        ),
        [
            {
                "id": int(p["id"].removeprefix("municipality-")),
                "gov": int(p["governorate"].removeprefix("TN-")),
                "ar": p["name_ar"],
                "fr": p["name_fr"],
                "en": p["name_en"],
                "area": _real(p["area_km2"]),
                "geom": json.dumps(f["geometry"]),
                **_label(p),
            }
            for f in _features("municipalities")
            for p in [f["properties"]]
        ],
    )
    _expect(bind, "SELECT count(*) FROM geo.municipality", 338, "municipalities")

    # A few water bodies have no name in one language: the other one stands in.
    bind.execute(
        sa.text(
            "INSERT INTO geo.water_body (id, kind, gouvernorat_codes, name_ar, name_fr, name_en, salt, intermittent, "  # noqa: S608 (constant SQL fragments, values are bound)
            f"area_km2, label, boundary) VALUES (:id, :kind, :govs, :ar, :fr, :en, :salt, :intermittent, :area, "
            f"{LABEL}, {GEOM})"
        ),
        [
            {
                "id": p["id"],
                "kind": p["type"],
                "govs": [int(g.removeprefix("TN-")) for g in p["governorates"].split()],
                "ar": p["name_ar"] or p["name_fr"] or p["name_en"],
                "fr": p["name_fr"] or p["name_en"] or p["name_ar"],
                "en": p["name_en"] or p["name_fr"] or p["name_ar"],
                "salt": p["salt"] == "yes",
                "intermittent": p["intermittent"] == "yes",
                "area": _real(p["area_km2"]),
                "geom": json.dumps(f["geometry"]),
                **_label(p),
            }
            for f in _features("water")
            for p in [f["properties"]]
        ],
    )
    _expect(bind, "SELECT count(*) FROM geo.water_body", 67, "water bodies")

    bind.execute(
        sa.text(
            "INSERT INTO geo.city (id, kind, gouvernorat_code, delegation_id, sector_code, municipality_id, name_ar, "
            "name_fr, name_en, place, location) SELECT :id, :kind, :gov, "
            "(SELECT id FROM geo.delegation WHERE ins_code = :delegation), "
            "(SELECT code FROM geo.sector WHERE code = :sector), "
            "(SELECT id FROM geo.municipality WHERE id = :municipality), :ar, :fr, :en, NULLIF(:place, ''), "
            "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)"
        ),
        [
            {
                "id": p["id"],
                "kind": p["type"],
                "gov": int(p["governorate"].removeprefix("TN-")),
                "delegation": p["delegation"].removeprefix("delegation-"),
                "sector": p["sector"].removeprefix("sector-"),
                "municipality": _int(p["municipality"].removeprefix("municipality-")),
                "ar": p["name_ar"] or p["name_fr"],
                "fr": p["name_fr"] or p["name_en"] or p["name_ar"],
                "en": p["name_en"] or p["name_fr"] or p["name_ar"],
                "place": p["place"],
                "lon": f["geometry"]["coordinates"][0],
                "lat": f["geometry"]["coordinates"][1],
            }
            for f in _features("cities")
            for p in [f["properties"]]
        ],
    )
    _expect(bind, "SELECT count(*) FROM geo.city", 284, "cities")

    run_script(BACKFILL)


def downgrade() -> None:
    run_script(DOWNGRADE)
    # The simplified outlines of migration 0003 come back.
    features = json.loads((SEED / "tn_gouvernorats.geojson").read_text(encoding="utf-8"))["features"]
    op.get_bind().execute(
        sa.text(f"UPDATE geo.gouvernorat SET boundary = {GEOM} WHERE iso_code = :iso"),  # noqa: S608 (constant SQL fragments, values are bound)
        [{"iso": f["properties"]["iso_code"], "geom": json.dumps(f["geometry"])} for f in features],
    )
