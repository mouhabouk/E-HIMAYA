"""Population and places exposed to a hazard, on the area of a crisis axis (OS14, docs/phase-os14/design-os14.md).

No hazard is drawn twice: the footprint is the axis area (its sub-axes included), the "core"; a "ring" of 0 to 5 km
around it is the warning and precautionary evacuation band. The estimate crosses that footprint with what the
platform already holds:

* the delegations and their 2024 census (INS, ``geo.delegation``): the people of a delegation are spread by two
  methods, its share of the area and its share of the places of daily life (schools, places of worship,
  pharmacies, supermarkets, bus stops: the built-up part), and the estimate keeps both as a range;
* the places of the map layers (``geo.layer_feature``): health, elderly homes and education first, then hazardous
  sites (domino effect), transport and gatherings, each in the core or the ring;
* the lines of the transport layers (railways, roads when a roads layer is loaded): the kilometres inside, cut
  when they cross the core.

The result is stored as an event of the axis timeline (``crisis.event``, kind ``exposure``): every estimate stays in
the record with its footprint, figures and sources, and the decision window, the axis page and the interactive map
read the latest one. A planning figure, never a count: it does not know who is home now.
"""

import json
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Ring widths offered (metres) and the default by kind of disaster (crisis.axis.kind).
RINGS = (0, 500, 1000, 2000, 5000)
DEFAULT_RING: dict[str, int] = {
    "flood": 1000,
    "forest_fire": 1000,
    "technological": 2000,
    "storm": 0,
    "earthquake": 0,
    "health": 0,
    "other": 500,
}
# Places of daily life that show where people live inside a delegation (stems of the layer keys).
BUILT_STEMS = ("schools", "worship", "pharmacies", "supermarkets", "bus_stops")
# Weight of the area share in the built-up share: a delegation with few places leans on its area.
PRIOR = 10
# Groups of places, in the order of priority for alerting and evacuation. ``sensitive``: listed in full.
GROUPS: dict[str, tuple[tuple[str, ...], bool]] = {
    "health": (("hospitals", "clinics"), True),
    "elderly": (("elderly_homes",), True),
    "education": (("schools", "institutes", "faculties", "universities"), True),
    "hazardous": (("fuel_stations", "factories"), False),
    "transport": (("train_stations", "bus_stations", "airports"), False),
    "gathering": (("hotels", "worship", "sports"), False),
}
LINE_STEMS = ("railways", "roads")
MAX_SENSITIVE = 300
MAX_OTHER = 10
MAX_PLACES = 3000
# Two places of one group with the same name closer than this are one (OSM keeps a building and its grounds).
SAME_PLACE_M = 300
CENSUS = "INS RGPH 2024"


@dataclass(frozen=True, slots=True)
class Delegation:
    id: int
    name_ar: str
    name_fr: str
    gouvernorat_code: int
    population: int
    area_m2: float
    ring_m2: float
    core_m2: float
    built: int = 0
    built_ring: int = 0
    built_core: int = 0


@dataclass(frozen=True, slots=True)
class Place:
    name: str
    stem: str
    lat: float
    lon: float
    core: bool
    to_verify: bool


def shares(d: Delegation, *, core: bool) -> tuple[float, float]:
    """The share of the delegation's people inside, by area and by places of daily life (pulled to the area)."""
    if d.area_m2 <= 0:
        return 0.0, 0.0
    by_area = min(1.0, (d.core_m2 if core else d.ring_m2) / d.area_m2)
    inside = d.built_core if core else d.built_ring
    by_built = (inside + PRIOR * by_area) / (d.built + PRIOR)
    return by_area, min(1.0, by_built)


def rounded(n: float) -> int:
    """A planning figure: to the thousand from 10 000, the hundred from 1 000, the ten below."""
    n = max(0.0, n)
    step = 1000 if n >= 10_000 else 100 if n >= 1000 else 10
    return int(round(n / step) * step)


def estimate(d: Delegation, *, core: bool) -> tuple[int, int, int]:
    """(low, high, central) people of the delegation in the core or the whole footprint."""
    a, b = shares(d, core=core)
    low, high = sorted((d.population * a, d.population * b))
    return round(low), round(high), round((low + high) / 2)


def _metres(a: Place, b: Place) -> float:
    k = math.cos(math.radians((a.lat + b.lat) / 2))
    return math.hypot((a.lon - b.lon) * k, a.lat - b.lat) * 111_320


def _norm(name: str) -> str:
    return " ".join(name.casefold().split())


def dedupe(places: Iterable[Place]) -> list[Place]:
    """One entry per place: the same name in the same group within ``SAME_PLACE_M`` is a duplicate (core first)."""
    kept: list[Place] = []
    for p in sorted(places, key=lambda x: (not x.core, _norm(x.name))):
        if any(_norm(k.name) == _norm(p.name) and _metres(k, p) < SAME_PLACE_M for k in kept):
            continue
        kept.append(p)
    return kept


def group_of(stem: str) -> str | None:
    for key, (stems, _) in GROUPS.items():
        if stem in stems:
            return key
    return None


def summarise(
    delegations: Sequence[Delegation],
    places: Sequence[Place],
    lines: Sequence[tuple[str, str, float, bool]],
    *,
    ring_m: int,
    core_km2: float,
    ring_km2: float,
    layers: Sequence[tuple[str, bool]],
    at: datetime,
) -> dict[str, Any]:
    """The stored result: figures, rows and sources (no person, only public places and census totals)."""
    rows: list[dict[str, Any]] = []
    tot = {"low": 0, "high": 0, "mid": 0, "core_low": 0, "core_high": 0, "core_mid": 0}
    for d in delegations:
        lo, hi, mid = estimate(d, core=False)
        clo, chi, cmid = estimate(d, core=True)
        if hi <= 0:
            continue
        for k, v in zip(tot, (lo, hi, mid, clo, chi, cmid), strict=True):
            tot[k] += v
        rows.append(
            {
                "id": d.id,
                "name_ar": d.name_ar,
                "name_fr": d.name_fr,
                "gouvernorat_code": d.gouvernorat_code,
                "population": d.population,
                "area_share": round(min(1.0, d.ring_m2 / d.area_m2) * 100, 1) if d.area_m2 else 0.0,
                "low": rounded(lo),
                "high": rounded(hi),
                "estimate": rounded(mid),
                "core": rounded(cmid),
            }
        )
    rows.sort(key=lambda r: -r["estimate"])
    groups: dict[str, dict[str, Any]] = {}
    for key, (_, sensitive) in GROUPS.items():
        items = [p for p in places if group_of(p.stem) == key]
        shown = items[: MAX_SENSITIVE if sensitive else MAX_OTHER]
        groups[key] = {
            "count": len(items),
            "core": sum(1 for p in items if p.core),
            "sensitive": sensitive,
            "items": [
                {
                    "name": p.name,
                    "layer": p.stem,
                    "lat": round(p.lat, 6),
                    "lon": round(p.lon, 6),
                    "zone": "core" if p.core else "ring",
                }
                for p in shown
            ],
        }
    by_line: dict[tuple[str, str], list[float]] = {}
    for stem, name, km, cut in lines:
        acc = by_line.setdefault((stem, name), [0.0, 0.0])
        acc[0] += km
        acc[1] = max(acc[1], 1.0 if cut else 0.0)
    kept = sorted(((s, n, v) for (s, n), v in by_line.items() if v[0] >= 0.05), key=lambda x: (not x[2][1], -x[2][0]))
    line_rows: list[dict[str, Any]] = [
        {"layer": s, "name": n, "km": round(v[0], 1), "cut": bool(v[1])} for s, n, v in kept
    ]
    population = {
        "estimate": rounded(tot["mid"]),
        "low": rounded(tot["low"]),
        "high": rounded(tot["high"]),
        "core": rounded(tot["core_mid"]),
        "core_low": rounded(tot["core_low"]),
        "core_high": rounded(tot["core_high"]),
    }
    brief = {
        "population": population["estimate"],
        "core_population": population["core"],
        "health": groups["health"]["count"],
        "elderly": groups["elderly"]["count"],
        "education": groups["education"]["count"],
        "lines_cut": sum(1 for r in line_rows if r["cut"]),
        "ring_m": ring_m,
        "at": at.isoformat(),
    }
    return {
        "ring_m": ring_m,
        "core_km2": round(core_km2, 1),
        "area_km2": round(ring_km2, 1),
        "population": population,
        "delegations": rows,
        "groups": groups,
        "lines": line_rows,
        "brief": brief,
        "sources": {
            "census": CENSUS,
            "layers": [{"layer": s, "to_verify": v} for s, v in layers],
        },
        "computed_at": at.isoformat(),
    }


# ---------------------------------------------------------------- the database side

_STEM = "regexp_replace(l.key, '^osm_', '')"
_LIVE = "l.deleted_at IS NULL AND NOT p.hidden"


async def footprint(
    session: AsyncSession, axis_ids: Sequence[Any], ring_m: int
) -> tuple[str, str, float, float] | None:
    """(core EWKT, ring EWKT, core km², footprint km²) of the axes' areas, or None when none has an area."""
    row = (
        await session.execute(
            text(
                "WITH c AS (SELECT ST_Multi(ST_Union(CAST(area AS geometry))) AS g FROM crisis.axis "
                "WHERE id = ANY(CAST(:ids AS uuid[])) AND area IS NOT NULL), "
                "r AS (SELECT g, CASE WHEN :m > 0 THEN CAST(ST_Buffer(CAST(g AS geography), :m) AS geometry) "
                "ELSE g END AS ring FROM c WHERE g IS NOT NULL) "
                "SELECT ST_AsEWKT(g), ST_AsEWKT(ring), ST_Area(CAST(g AS geography)) / 1e6, "
                "ST_Area(CAST(ring AS geography)) / 1e6 FROM r"
            ),
            {"ids": [str(i) for i in axis_ids], "m": ring_m},
        )
    ).first()
    if row is None or row[0] is None:
        return None
    return str(row[0]), str(row[1]), float(row[2]), float(row[3])


async def delegations(session: AsyncSession, core: str, ring: str) -> list[Delegation]:
    rows = (
        await session.execute(
            text(
                "WITH f AS (SELECT ST_GeomFromEWKT(:core) AS c, ST_GeomFromEWKT(:ring) AS r) "
                "SELECT d.id, d.name_ar, d.name_fr, d.gouvernorat_code, coalesce(d.population_2024, 0), "
                "ST_Area(CAST(d.boundary AS geography)), "
                "ST_Area(CAST(ST_Intersection(d.boundary, f.r) AS geography)), "
                "ST_Area(CAST(ST_Intersection(d.boundary, f.c) AS geography)) "
                "FROM geo.delegation d, f WHERE d.boundary IS NOT NULL AND ST_Intersects(d.boundary, f.r)"
            ),
            {"core": core, "ring": ring},
        )
    ).all()
    found = [
        Delegation(int(r[0]), r[1], r[2], int(r[3]), int(r[4]), float(r[5]), float(r[6]), float(r[7])) for r in rows
    ]
    if not found:
        return []
    built = {
        int(r[0]): (int(r[1]), int(r[2]), int(r[3]))
        for r in (
            await session.execute(
                text(
                    "WITH f AS (SELECT ST_GeomFromEWKT(:core) AS c, ST_GeomFromEWKT(:ring) AS r) "  # noqa: S608 (constant SQL fragments, values are bound)
                    "SELECT d.id, count(*), "
                    "count(*) FILTER (WHERE ST_Intersects(CAST(p.location AS geometry), f.r)), "
                    "count(*) FILTER (WHERE ST_Intersects(CAST(p.location AS geometry), f.c)) "
                    "FROM geo.delegation d CROSS JOIN f "
                    "JOIN geo.layer_feature p ON ST_Intersects(CAST(p.location AS geometry), d.boundary) "
                    "JOIN geo.layer l ON l.id = p.layer_id "
                    f"WHERE d.id = ANY(:ids) AND {_LIVE} AND {_STEM} = ANY(:stems) GROUP BY d.id"
                ),
                {"core": core, "ring": ring, "ids": [d.id for d in found], "stems": list(BUILT_STEMS)},
            )
        ).all()
    }
    return [
        Delegation(
            d.id,
            d.name_ar,
            d.name_fr,
            d.gouvernorat_code,
            d.population,
            d.area_m2,
            d.ring_m2,
            d.core_m2,
            *built.get(d.id, (0, 0, 0)),
        )
        for d in found
    ]


async def places(session: AsyncSession, core: str, ring: str) -> tuple[list[Place], list[tuple[str, bool]]]:
    stems = [s for stems, _ in GROUPS.values() for s in stems]
    rows = (
        await session.execute(
            text(
                "WITH f AS (SELECT ST_GeomFromEWKT(:core) AS c, ST_GeomFromEWKT(:ring) AS r) "  # noqa: S608 (constant SQL fragments, values are bound)
                f"SELECT p.name, {_STEM}, ST_Y(CAST(p.location AS geometry)), ST_X(CAST(p.location AS geometry)), "
                "ST_Intersects(CAST(p.location AS geometry), f.c), l.to_verify "
                "FROM geo.layer_feature p JOIN geo.layer l ON l.id = p.layer_id CROSS JOIN f "
                f"WHERE {_LIVE} AND {_STEM} = ANY(:stems) AND ST_Intersects(CAST(p.location AS geometry), f.r) "
                "ORDER BY 5 DESC, p.name LIMIT :n"
            ),
            {"core": core, "ring": ring, "stems": stems, "n": MAX_PLACES},
        )
    ).all()
    found = dedupe(Place(r[0], r[1], float(r[2]), float(r[3]), bool(r[4]), bool(r[5])) for r in rows)
    layers = sorted({(p.stem, p.to_verify) for p in found})
    return found, layers


async def lines(session: AsyncSession, core: str, ring: str) -> list[tuple[str, str, float, bool]]:
    rows = (
        await session.execute(
            text(
                "WITH f AS (SELECT ST_GeomFromEWKT(:core) AS c, ST_GeomFromEWKT(:ring) AS r) "  # noqa: S608 (constant SQL fragments, values are bound)
                f"SELECT {_STEM}, p.name, "
                "ST_Length(CAST(ST_Intersection(CAST(p.shape AS geometry), f.r) AS geography)) / 1000, "
                "ST_Intersects(CAST(p.shape AS geometry), f.c) "
                "FROM geo.layer_feature p JOIN geo.layer l ON l.id = p.layer_id CROSS JOIN f "
                f"WHERE {_LIVE} AND p.shape IS NOT NULL AND {_STEM} = ANY(:stems) "
                "AND ST_Intersects(CAST(p.shape AS geometry), f.r)"
            ),
            {"core": core, "ring": ring, "stems": list(LINE_STEMS)},
        )
    ).all()
    return [(r[0], r[1], float(r[2] or 0), bool(r[3])) for r in rows]


async def compute(session: AsyncSession, axis_ids: Sequence[Any], ring_m: int, at: datetime) -> dict[str, Any] | None:
    """The estimate for the union of the axes' areas, or None when none has an area."""
    shape = await footprint(session, axis_ids, ring_m)
    if shape is None:
        return None
    core, ring, core_km2, ring_km2 = shape
    found, layers = await places(session, core, ring)
    result = summarise(
        await delegations(session, core, ring),
        found,
        await lines(session, core, ring),
        ring_m=ring_m,
        core_km2=core_km2,
        ring_km2=ring_km2,
        layers=layers,
        at=at,
    )
    result["ring"] = await _ring_geojson(session, ring)
    return result


async def _ring_geojson(session: AsyncSession, ring: str) -> Any:
    """The footprint outline for the maps, simplified to about 20 m."""
    raw = await session.scalar(
        text("SELECT ST_AsGeoJSON(ST_Multi(ST_SimplifyPreserveTopology(ST_GeomFromEWKT(:r), 0.0002)), 5)"), {"r": ring}
    )
    return json.loads(raw) if raw else None
