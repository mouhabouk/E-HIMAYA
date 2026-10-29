"""Administrative reference (gouvernorats and délégations) used by every registration and report form, and the
boundaries of every administrative level for the maps (phase M, Map Tunisia, docs/phase-m/design-m.md §3)."""

import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, get_principal
from app.modules.geo import service
from app.modules.geo.models import Delegation, Gouvernorat
from app.modules.geo.schemas import AdminAddressOut, DelegationOut, GouvernoratOut

router = APIRouter(prefix="/api/v1/geo", tags=["geo"])

Lang = Literal["ar", "fr", "en"]
# Reference data changes only through migrations: let clients and the mobile app cache it.
CACHE_HEADER = "public, max-age=86400"


def _localized(name_ar: str, name_fr: str, lang: Lang, name_en: str | None = None) -> str:
    # English uses geo.gouvernorat.name_en; délégations keep the official French transliteration.
    if lang == "ar":
        return name_ar
    return name_en or name_fr if lang == "en" else name_fr


@router.get("/gouvernorats", response_model=list[GouvernoratOut])
async def list_gouvernorats(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    lang: Annotated[Lang, Query()] = "ar",
) -> list[GouvernoratOut]:
    counts = (
        select(Delegation.gouvernorat_code, func.count().label("n")).group_by(Delegation.gouvernorat_code).subquery()
    )
    rows = await session.execute(
        select(Gouvernorat, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.gouvernorat_code == Gouvernorat.code)
        .order_by(Gouvernorat.code)
    )
    response.headers["Cache-Control"] = CACHE_HEADER
    return [
        GouvernoratOut(
            code=g.code,
            iso_code=g.iso_code,
            name=_localized(g.name_ar, g.name_fr, lang, g.name_en),
            name_ar=g.name_ar,
            name_fr=g.name_fr,
            name_en=g.name_en,
            delegation_count=n,
        )
        for g, n in rows.all()
    ]


@router.get("/gouvernorats/{code}/delegations", response_model=list[DelegationOut])
async def list_delegations(
    code: int,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    lang: Annotated[Lang, Query()] = "ar",
) -> list[DelegationOut]:
    if await session.get(Gouvernorat, code) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_gouvernorat")
    rows = await session.scalars(select(Delegation).where(Delegation.gouvernorat_code == code).order_by(Delegation.id))
    response.headers["Cache-Control"] = CACHE_HEADER
    return [
        DelegationOut(
            id=d.id,
            code=d.code,
            gouvernorat_code=d.gouvernorat_code,
            name=_localized(d.name_ar, d.name_fr, lang),
            name_ar=d.name_ar,
            name_fr=d.name_fr,
        )
        for d in rows
    ]


# ---------------------------------------------------------------- boundaries (phase M)

Level = Literal["regions", "districts", "gouvernorats", "delegations", "sectors", "municipalities", "water", "cities"]
Detail = Literal["low", "medium", "high"]
# Simplification in degrees (about 500 m and 100 m); "high" is the stored ~20 m geometry.
TOLERANCE: dict[str, float] = {"low": 0.0045, "medium": 0.0009, "high": 0.0}
ATTRIBUTION = "© OpenStreetMap contributors · Map Tunisia by Alaa Taieb (ODbL 1.0)"

# One query per level; :gov (a gouvernorat code or NULL) narrows it. Regions and districts are unions of gouvernorats.
_QUERIES: dict[str, str] = {
    "regions": (
        "SELECT r.code AS id, r.short, r.name_ar, r.name_fr, r.name_en, sum(g.population_2014) AS population_2014, "
        "sum(g.population_2024) AS population_2024, sum(g.area_km2) AS area_km2, ST_Union(g.boundary) AS geom "
        "FROM geo.economic_region r JOIN geo.gouvernorat g ON g.region = r.code "
        "WHERE CAST(:gov AS smallint) IS NULL OR g.code = :gov GROUP BY r.code ORDER BY r.code"
    ),
    "districts": (
        "SELECT d.number AS id, d.name_ar, d.name_fr, d.name_en, sum(g.population_2014) AS population_2014, "
        "sum(g.population_2024) AS population_2024, sum(g.area_km2) AS area_km2, ST_Union(g.boundary) AS geom "
        "FROM geo.district d JOIN geo.gouvernorat g ON g.district = d.number "
        "WHERE CAST(:gov AS smallint) IS NULL OR g.code = :gov GROUP BY d.number ORDER BY d.number"
    ),
    "gouvernorats": (
        "SELECT code AS id, iso_code, ins_code, name_ar, name_fr, name_en, region, district, "
        "population_2014, population_2024, area_km2, boundary AS geom "
        "FROM geo.gouvernorat WHERE CAST(:gov AS smallint) IS NULL OR code = :gov ORDER BY code"
    ),
    "delegations": (
        "SELECT id, code, ins_code, gouvernorat_code, name_ar, name_fr, name_en, "
        "population_2014, population_2024, area_km2, boundary AS geom FROM geo.delegation "
        "WHERE boundary IS NOT NULL AND (CAST(:gov AS smallint) IS NULL OR gouvernorat_code = :gov) ORDER BY id"
    ),
    "sectors": (
        "SELECT code AS id, delegation_id, gouvernorat_code, name_ar, name_fr, name_en, area_km2, boundary AS geom "
        "FROM geo.sector WHERE CAST(:gov AS smallint) IS NULL OR gouvernorat_code = :gov ORDER BY code"
    ),
    "municipalities": (
        "SELECT id, gouvernorat_code, name_ar, name_fr, name_en, area_km2, boundary AS geom "
        "FROM geo.municipality WHERE CAST(:gov AS smallint) IS NULL OR gouvernorat_code = :gov ORDER BY id"
    ),
    "water": (
        "SELECT id, kind, gouvernorat_codes, name_ar, name_fr, name_en, salt, intermittent, area_km2, boundary AS geom "
        "FROM geo.water_body WHERE CAST(:gov AS smallint) IS NULL OR :gov = ANY(gouvernorat_codes) ORDER BY id"
    ),
    "cities": (
        "SELECT id, kind, gouvernorat_code, delegation_id, municipality_id, name_ar, name_fr, name_en, "
        "location AS geom "
        "FROM geo.city WHERE CAST(:gov AS smallint) IS NULL OR gouvernorat_code = :gov ORDER BY id"
    ),
}
# Reference data changes only through migrations: each answer is built once per process.
_boundaries: dict[tuple[str, int | None, str], bytes] = {}


async def _feature_collection(session: AsyncSession, level: str, gov: int | None, detail: str) -> bytes:
    tolerance = TOLERANCE[detail]
    geometry = "ST_SimplifyPreserveTopology(geom, :tol)" if tolerance and level != "cities" else "geom"
    rows = (
        await session.execute(
            text(f"SELECT q.*, ST_AsGeoJSON({geometry}, 5) AS geojson FROM ({_QUERIES[level]}) q"),  # noqa: S608
            {"gov": gov, "tol": tolerance},
        )
    ).mappings()
    features: list[dict[str, Any]] = []
    for row in rows:
        props = {k: v for k, v in row.items() if k not in ("geom", "geojson")}
        props["name_en"] = props.get("name_en") or props["name_fr"]
        if isinstance(props.get("area_km2"), float):
            props["area_km2"] = round(props["area_km2"], 2)
        features.append(
            {"type": "Feature", "id": props["id"], "properties": props, "geometry": json.loads(row["geojson"])}
        )
    body = {"type": "FeatureCollection", "attribution": ATTRIBUTION, "features": features}
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"), default=float).encode()


@router.get("/boundaries/{level}", response_class=Response, responses={200: {"content": {"application/geo+json": {}}}})
async def boundaries(
    level: Level,
    session: Annotated[AsyncSession, Depends(get_session)],
    gouvernorat: Annotated[int | None, Query(ge=11, le=83)] = None,
    detail: Annotated[Detail, Query()] = "medium",
) -> Response:
    """GeoJSON of one administrative level with its codes, names and census (public reference data, ODbL)."""
    key = (level, gouvernorat, detail)
    if key not in _boundaries:
        _boundaries[key] = await _feature_collection(session, level, gouvernorat, detail)
    return Response(_boundaries[key], media_type="application/geo+json", headers={"Cache-Control": CACHE_HEADER})


@router.get("/locate", response_model=AdminAddressOut)
async def locate(
    principal: Annotated[Principal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    lat: Annotated[float, Query(ge=30.0, le=38.0)],
    lon: Annotated[float, Query(ge=7.0, le=12.0)],
) -> AdminAddressOut:
    """The délégation, imada and municipality containing a point (signed-in users)."""
    address = await service.admin_address(session, lat, lon)
    found = await service.address_out(session, address.delegation_id, address.sector_code, address.municipality_id)
    return found or AdminAddressOut()
