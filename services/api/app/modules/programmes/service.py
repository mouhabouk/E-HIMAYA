"""Seasonal programmes: versions, the layer each approved programme owns, and the daily life cycle (phase L2,
docs/phase-l/design-l2.md §2.2-2.6).

An approved programme owns a map layer of phase L1a (key ``prog_<code>``): it is published from the first day of
validity to the last, then paused, so the maps, "nearest to me", columns per audience, deletion and revisions all
come from the layers module. The points with a position become the places of the layer (the reference of the point
is the reference of the place); a closed or postponed point is hidden. The supervisor's name and phone are shown to
the operations rooms only, and the counts to the staff only.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import cast, delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import as_system
from app.core.security import Principal
from app.modules.audit import service as audit
from app.modules.geo.models import Gouvernorat, Layer, LayerFeature, LayerRevision
from app.modules.layers import access
from app.modules.layers.service import point as wkt_point
from app.modules.layers.service import sync_columns
from app.modules.programmes import domain
from app.modules.programmes.models import Programme, ProgrammePoint, ProgrammeRevision

LAT = func.ST_Y(cast(ProgrammePoint.location, Geometry))
LON = func.ST_X(cast(ProgrammePoint.location, Geometry))
LIVE = ("approved", "updated")
# A beach is guarded today when an open point of a beach programme in force is this close (design §2.6).
GUARD_RADIUS_M = 1000

LAYER_LOOK: dict[str, tuple[str, str]] = {
    "road": ("ambulance", "#C62828"),
    "seasonal": ("forest", "#2E7D32"),
    "beach": ("pool", "#0277BD"),
    "other": ("flag", "#6A1B9A"),
}
# Who sees a programme layer when it is first approved; the administrator changes it on the layer page.
LAYER_AUDIENCES: dict[str, list[str]] = {
    "road": list(access.AUDIENCES),
    "beach": list(access.AUDIENCES),
    "seasonal": list(access.STAFF_AUDIENCES),
    "other": list(access.STAFF_AUDIENCES),
}
ROOMS = ["room"]
COUNTS = ("staff_count", "supervisors", "lifeguards_planned", "lifeguards_deployed", "staff_composition", "equipment")
LAYER_FIELDS: dict[str, list[str]] = {
    "supervisor_name": ROOMS,
    "supervisor_phone": ROOMS,
    **{column: list(access.STAFF_AUDIENCES) for column in COUNTS},
    "geo_note": list(access.STAFF_AUDIENCES),
    "notes": list(access.STAFF_AUDIENCES),
}
KIND_NAMES = {
    "road": ("نقاط النجدة والإسعاف بالطرقات", "Points de secours routiers", "Road rescue points"),
    "seasonal": ("المراكز الموسمية", "Centres saisonniers", "Seasonal centres"),
    "beach": ("التركز بالشواطئ", "Surveillance des plages", "Beach lifeguard posts"),
    "other": ("برنامج موسمي", "Programme saisonnier", "Seasonal programme"),
}


def layer_key(code: str) -> str:
    return "prog_" + code.lower().replace("-", "_")


TUNIS = timedelta(hours=1)


def today() -> date:
    """Today in Tunisia (UTC+1 all year)."""
    return (datetime.now(UTC) + TUNIS).date()


# ---------------------------------------------------------------- gouvernorats


async def gouvernorat_index(session: AsyncSession) -> dict[str, int]:
    """Arabic and French names, normalised, to the gouvernorat code."""
    rows = (await session.execute(select(Gouvernorat.code, Gouvernorat.name_ar, Gouvernorat.name_fr))).all()
    index: dict[str, int] = {}
    for code, ar, fr in rows:
        index[domain.normalize(ar)] = code
        index[domain.normalize(fr).lower()] = code
    return index


def gouvernorat_of(index: dict[str, int], name: str) -> int | None:
    key = domain.normalize(name)
    return index.get(key) or index.get(key.lower())


# ---------------------------------------------------------------- versions


def _iso(value: Any) -> Any:
    return value.isoformat() if isinstance(value, (date, datetime)) else value


async def snapshot(session: AsyncSession, programme: Programme) -> dict[str, Any]:
    rows = (
        await session.execute(select(ProgrammePoint, LAT, LON).where(ProgrammePoint.programme_id == programme.id))
    ).all()
    points: dict[str, dict[str, Any]] = {}
    for p, lat, lon in rows:
        values = {k: _iso(getattr(p, k)) for k in domain.POINT_FIELDS if k not in ("lat", "lon")}
        values["lat"] = round(lat, 6) if lat is not None else None
        values["lon"] = round(lon, 6) if lon is not None else None
        points[p.ref] = values
    return {
        "programme": {k: _iso(getattr(programme, k)) for k in domain.PROGRAMME_FIELDS},
        "points": points,
    }


async def revise(
    session: AsyncSession, programme: Programme, principal: Principal | None, action: str, reason: str | None
) -> ProgrammeRevision:
    await session.flush()
    number = (
        await session.scalar(
            select(func.max(ProgrammeRevision.number)).where(ProgrammeRevision.programme_id == programme.id)
        )
    ) or 0
    programme.version = number + 1
    programme.updated_at = datetime.now(UTC)
    if principal is not None:
        programme.updated_by = audit.actor_of(principal)
        programme.updated_by_name = audit.name_of(principal)
    revision = ProgrammeRevision(
        programme_id=programme.id,
        number=number + 1,
        action=action,
        reason=reason,
        snapshot=await snapshot(session, programme),
        created_by=audit.actor_of(principal) if principal is not None else "system",
        created_by_name=audit.name_of(principal) if principal is not None else None,
    )
    session.add(revision)
    await session.flush()
    return revision


def point_values(item: dict[str, Any], gouvernorats: dict[str, int]) -> dict[str, Any]:
    """Model columns of a checked point (domain._point)."""
    lat, lon = item.get("lat"), item.get("lon")
    return {
        "ref": item["ref"],
        "gouvernorat_code": gouvernorat_of(gouvernorats, item.get("governorate", "")),
        "place_name": item["place_name"],
        "location": wkt_point(lat, lon) if lat is not None and lon is not None else None,
        **{
            k: item.get(k)
            for k in (
                "sub_points",
                "geo_confidence",
                "geo_note",
                *domain.INTEGERS,
                *domain.TEXTS,
                "opening_date",
                "closing_date",
                "status",
            )
        },
    }


def restore_values(values: dict[str, Any]) -> dict[str, Any]:
    """Model columns of a point kept in a revision."""
    out = {k: values.get(k) for k in domain.POINT_FIELDS if k not in ("lat", "lon")}
    for key in ("opening_date", "closing_date"):
        value = out[key]
        if isinstance(value, str) and value:
            out[key] = date.fromisoformat(value)
    lat, lon = values.get("lat"), values.get("lon")
    out["location"] = wkt_point(lat, lon) if lat is not None and lon is not None else None
    return out


# ---------------------------------------------------------------- the layer


def live_on(programme: Programme, day: date) -> bool:
    return programme.status in LIVE and programme.valid_from <= day <= programme.valid_to


def _feature_props(p: ProgrammePoint, programme: Programme) -> dict[str, Any]:
    props: dict[str, Any] = {
        "programme": programme.code,
        "point_status": p.status,
        "geo_confidence": p.geo_confidence,
    }
    for key in (
        "sub_points",
        "hours",
        "staff_count",
        "staff_composition",
        "supervisors",
        "lifeguards_planned",
        "lifeguards_deployed",
        "equipment",
        "supervisor_name",
        "supervisor_phone",
        "geo_note",
        "notes",
    ):
        value = getattr(p, key)
        if value not in (None, ""):
            props[key] = value
    for key in ("opening_date", "closing_date"):
        value = getattr(p, key)
        if value is not None:
            props[key] = value.isoformat()
    return props


async def _new_layer(session: AsyncSession, programme: Programme, actor: str) -> Layer:
    icon, colour = LAYER_LOOK[programme.kind]
    ar, fr, en = KIND_NAMES[programme.kind]
    layer = Layer(
        key=layer_key(programme.code),
        name={
            "ar": f"{ar} ({programme.season or programme.code})",
            "fr": f"{fr} {programme.code}",
            "en": f"{en} {programme.code}",
        },
        icon=icon,
        colour=colour,
        audience="staff",
        source="الديوان الوطني للحماية المدنية",
        licence="",
        to_verify=False,
        simulated=False,
        staff_only=[],
        editors_allowed=False,
        created_by=actor,
        updated_by=actor,
        status="paused",
        audiences=sorted(LAYER_AUDIENCES[programme.kind]),
        scope=[],
        default_on=programme.kind != "other",
        sensitive=False,
        fields=dict(LAYER_FIELDS),
        actions={"call": True, "directions": True},
    )
    sync_columns(layer)
    session.add(layer)
    await session.flush()
    session.add(
        LayerRevision(
            layer_id=layer.id,
            number=1,
            action="create",
            snapshot={"programme": programme.code},
            reason=f"programme {programme.code}",
            created_by=actor,
        )
    )
    return layer


async def sync_layer(session: AsyncSession, programme: Programme, actor: str, day: date | None = None) -> Layer | None:
    """Create or refresh the layer of an approved programme: its status follows the validity dates, and its places
    the points with a position. A draft has no layer; a cancelled or ended programme keeps its layer paused."""
    day = day or today()
    async with as_system(session):
        layer = await session.get(Layer, programme.layer_id) if programme.layer_id else None
        if layer is None:
            if programme.status not in LIVE:
                return None
            layer = await session.scalar(select(Layer).where(Layer.key == layer_key(programme.code)))
            if layer is None:
                layer = await _new_layer(session, programme, actor)
            programme.layer_id = layer.id
        if layer.deleted_at is not None:
            return layer  # the administrator deleted it (L1a): it stays deleted until restored
        wanted = "published" if live_on(programme, day) else "paused"
        if layer.status != wanted:
            layer.status = wanted
            sync_columns(layer)
        rows = (
            await session.execute(
                select(ProgrammePoint, LAT, LON).where(
                    ProgrammePoint.programme_id == programme.id, ProgrammePoint.location.is_not(None)
                )
            )
        ).all()
        existing = {
            f.ref: f
            for f in (await session.scalars(select(LayerFeature).where(LayerFeature.layer_id == layer.id))).all()
        }
        keep: set[str] = set()
        for p, lat, lon in rows:
            keep.add(p.ref)
            values = {
                "name": p.place_name,
                "kind": programme.kind,
                "phone": None,
                "location": wkt_point(lat, lon),
                "gouvernorat_code": p.gouvernorat_code,
                "props": _feature_props(p, programme),
                "hidden": p.status != "open",
                "updated_by": actor,
                "updated_at": datetime.now(UTC),
            }
            feature = existing.get(p.ref)
            if feature is None:
                session.add(LayerFeature(layer_id=layer.id, ref=p.ref, name_status="official", **values))
            elif feature.deleted_at is None:
                for k, v in values.items():
                    setattr(feature, k, v)
                feature.version += 1
        gone = [f.id for ref, f in existing.items() if ref not in keep]
        if gone:
            await session.execute(delete(LayerFeature).where(LayerFeature.id.in_(gone)))
        layer.data_version += 1
        layer.updated_at = datetime.now(UTC)
        await session.flush()
    return layer


async def lifecycle(session: AsyncSession, day: date | None = None) -> dict[str, int]:
    """Once a day (and after each change): end the programmes past their last day, and publish or pause each layer
    by its dates."""
    day = day or today()
    ended = synced = 0
    async with as_system(session):
        programmes = (
            await session.scalars(select(Programme).where(Programme.status.in_((*LIVE, "ended", "cancelled"))))
        ).all()
        for programme in programmes:
            if programme.status in LIVE and programme.valid_to < day:
                programme.status = "ended"
                await revise(session, programme, None, "end", None)
                ended += 1
            layer = await session.get(Layer, programme.layer_id) if programme.layer_id else None
            if layer is None or layer.deleted_at is not None:
                continue
            wanted = "published" if live_on(programme, day) else "paused"
            if layer.status != wanted:
                layer.status = wanted
                sync_columns(layer)
                layer.data_version += 1
                synced += 1
        await session.flush()
    return {"ended": ended, "layers": synced}


# ---------------------------------------------------------------- figures


async def figures(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, Any]]:
    """Per programme: points, without a position, open, gouvernorats, staff and lifeguards."""
    if not ids:
        return {}
    rows = (
        await session.execute(
            select(
                ProgrammePoint.programme_id,
                func.count(),
                func.count().filter(ProgrammePoint.location.is_(None)),
                func.count().filter(ProgrammePoint.status == "open"),
                func.count(func.distinct(ProgrammePoint.gouvernorat_code)),
                func.coalesce(func.sum(ProgrammePoint.staff_count), 0),
                func.coalesce(func.sum(ProgrammePoint.lifeguards_planned), 0),
                func.coalesce(func.sum(ProgrammePoint.lifeguards_deployed), 0),
            )
            .where(ProgrammePoint.programme_id.in_(ids))
            .group_by(ProgrammePoint.programme_id)
        )
    ).all()
    return {
        r[0]: {
            "points": r[1],
            "unlocated": r[2],
            "open": r[3],
            "gouvernorats": r[4],
            "staff": int(r[5] or 0),
            "lifeguards_planned": int(r[6] or 0),
            "lifeguards_deployed": int(r[7] or 0),
        }
        for r in rows
    }


# ---------------------------------------------------------------- coastal (L1b)


async def guarded_near(session: AsyncSession, lat: float, lon: float, day: date) -> str | None:
    """The beach programme (code and version) with an open point within GUARD_RADIUS_M of a beach on ``day``."""
    async with as_system(session):
        found = await session.execute(
            text(
                """
                SELECT p.code, p.version FROM programme.point pt
                JOIN programme.programme p ON p.id = pt.programme_id
                WHERE p.kind = 'beach' AND p.status IN ('approved', 'updated')
                  AND p.valid_from <= :day AND p.valid_to >= :day
                  AND pt.status = 'open' AND pt.location IS NOT NULL
                  AND (pt.opening_date IS NULL OR pt.opening_date <= :day)
                  AND (pt.closing_date IS NULL OR pt.closing_date >= :day)
                  AND ST_DWithin(pt.location, ST_GeogFromText(:here), :radius)
                ORDER BY ST_Distance(pt.location, ST_GeogFromText(:here)) LIMIT 1
                """
            ),
            {"day": day, "here": wkt_point(lat, lon), "radius": GUARD_RADIUS_M},
        )
        row = found.first()
    return f"{row[0]} v{row[1]}" if row else None
