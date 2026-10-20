"""Civil protection units and their resources (FR-C-09 «العتاد واللوجستيك», FR-C-10 map layer).

A resource is ``available``, ``assigned`` (an active assignment holds it: set by assignments only) or
``out_of_service``. Units and resources are restricted to the staff member's gouvernorat scope.
"""

import base64
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from geoalchemy2 import Geometry
from sqlalchemy import and_, cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Ctx, authorize, require
from app.core.events import emit
from app.core.security import Principal
from app.modules.ops import schemas
from app.modules.ops.domain import ACTIVE_ASSIGNMENT
from app.modules.ops.models import Assignment, Resource, Unit


def _point_wkt(p: schemas.LatLon) -> str:
    return f"SRID=4326;POINT({p.lon} {p.lat})"


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "not_found")


def unit_scope(principal: Principal) -> Any:
    return True if principal.is_national else Unit.gouvernorat_code == principal.gouvernorat_code


def _check_gouvernorat(principal: Principal, code: int) -> None:
    if not principal.can_access_gouvernorat(code):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")


def _lat(col: Any) -> Any:
    return func.ST_Y(cast(col, Geometry))


def _lon(col: Any) -> Any:
    return func.ST_X(cast(col, Geometry))


# ---------------------------------------------------------------- units


async def list_units(session: AsyncSession, principal: Principal) -> list[schemas.UnitOut]:
    counts = select(Resource.unit_id, func.count().label("n")).group_by(Resource.unit_id).subquery()
    rows = (
        await session.execute(
            select(Unit, _lat(Unit.location), _lon(Unit.location), func.coalesce(counts.c.n, 0))
            .outerjoin(counts, counts.c.unit_id == Unit.id)
            .where(unit_scope(principal))
            .order_by(Unit.gouvernorat_code, Unit.name_ar)
        )
    ).all()
    return [_unit_out(u, la, lo, n) for u, la, lo, n in rows]


def _unit_out(unit: Unit, lat: float, lon: float, resources: int) -> schemas.UnitOut:
    return schemas.UnitOut(
        id=unit.id,
        name_ar=unit.name_ar,
        name_fr=unit.name_fr,
        kind=unit.kind,
        gouvernorat_code=unit.gouvernorat_code,
        location=schemas.Point(lat=float(lat), lon=float(lon)),
        phone=unit.phone,
        resources=int(resources),
        version=unit.version,
    )


async def get_unit(session: AsyncSession, principal: Principal, unit_id: uuid.UUID, lock: bool = False) -> Unit:
    unit = await session.get(Unit, unit_id, with_for_update=lock)
    if unit is None or not principal.can_access_gouvernorat(unit.gouvernorat_code):
        raise _not_found()
    return unit


async def unit_out(session: AsyncSession, unit: Unit) -> schemas.UnitOut:
    lat, lon = (await session.execute(select(_lat(Unit.location), _lon(Unit.location)).where(Unit.id == unit.id))).one()
    n = await session.scalar(select(func.count()).where(Resource.unit_id == unit.id))
    return _unit_out(unit, lat, lon, int(n or 0))


async def _check_write(session: AsyncSession, principal: Principal, action: Action, gouvernorat_code: int) -> None:
    """Policy check of a unit or resource write: the ops manager of the object's gouvernorat (national: all)."""
    require(await authorize(session, principal, action, Ctx(lead=gouvernorat_code)))


async def save_unit(
    session: AsyncSession, principal: Principal, body: schemas.UnitIn, unit_id: uuid.UUID | None = None
) -> Unit:
    _check_gouvernorat(principal, body.gouvernorat_code)
    await _check_write(session, principal, Action.UNITS_WRITE, body.gouvernorat_code)
    if unit_id is None:
        unit = Unit()
        session.add(unit)
    else:
        unit = await get_unit(session, principal, unit_id, lock=True)
        if body.version is not None and body.version != unit.version:
            raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
        unit.version += 1
    unit.name_ar, unit.name_fr, unit.kind = body.name_ar, body.name_fr, body.kind
    unit.gouvernorat_code, unit.phone = body.gouvernorat_code, body.phone
    unit.location = _point_wkt(body.location)
    unit.updated_at = datetime.now(UTC)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_gouvernorat") from exc
    await session.refresh(unit)
    return unit


async def delete_unit(session: AsyncSession, principal: Principal, unit_id: uuid.UUID) -> None:
    unit = await get_unit(session, principal, unit_id, lock=True)
    await _check_write(session, principal, Action.UNITS_WRITE, unit.gouvernorat_code)
    if await session.scalar(select(func.count()).where(Resource.unit_id == unit.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "unit_in_use")
    await session.delete(unit)
    await session.flush()


# ---------------------------------------------------------------- resources


def _resource_select() -> Any:
    active = (
        select(Assignment.id, Assignment.incident_id, Assignment.status, Assignment.resource_id)
        .where(Assignment.status.in_(ACTIVE_ASSIGNMENT))
        .subquery()
    )
    location = func.coalesce(Resource.location, Unit.location)
    return (
        select(
            Resource,
            Unit,
            _lat(location),
            _lon(location),
            active.c.id,
            active.c.incident_id,
            active.c.status,
        )
        .join(Unit, Unit.id == Resource.unit_id)
        .outerjoin(active, active.c.resource_id == Resource.id)
    )


def _resource_out(row: Any) -> schemas.ResourceOut:
    resource, unit, lat, lon, assignment_id, incident_id, assignment_status = row
    return schemas.ResourceOut(
        id=resource.id,
        unit_id=unit.id,
        unit_name=unit.name_ar,
        kind=resource.kind,
        label=resource.label,
        status=resource.status,
        notes=resource.notes,
        location=schemas.Point(lat=float(lat), lon=float(lon)) if lat is not None else None,
        gouvernorat_code=unit.gouvernorat_code,
        assignment=(
            schemas.ResourceAssignmentRef(id=assignment_id, incident_id=incident_id, status=assignment_status)
            if assignment_id
            else None
        ),
        version=resource.version,
        updated_at=resource.updated_at,
    )


def _encode(*parts: object) -> str:
    return base64.urlsafe_b64encode("|".join(str(p) for p in parts).encode()).decode().rstrip("=")


def _decode(cursor: str) -> list[str]:
    try:
        return base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode().split("|")
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc


async def list_resources(
    session: AsyncSession,
    principal: Principal,
    *,
    statuses: list[str],
    kinds: list[str],
    unit_id: uuid.UUID | None,
    gouvernorat_code: int | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[schemas.ResourceOut], str | None]:
    query = _resource_select().where(unit_scope(principal))
    if statuses:
        query = query.where(Resource.status.in_(statuses))
    if kinds:
        query = query.where(Resource.kind.in_(kinds))
    if unit_id:
        query = query.where(Resource.unit_id == unit_id)
    if gouvernorat_code:
        query = query.where(Unit.gouvernorat_code == gouvernorat_code)
    if cursor:
        try:
            label, rid = _decode(cursor)
            last = uuid.UUID(rid)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc
        query = query.where(or_(Resource.label > label, and_(Resource.label == label, Resource.id > last)))
    rows = (await session.execute(query.order_by(Resource.label, Resource.id).limit(limit))).all()
    items = [_resource_out(r) for r in rows]
    next_cursor = _encode(items[-1].label, items[-1].id) if len(items) == limit else None
    return items, next_cursor


async def resource_out(session: AsyncSession, resource_id: uuid.UUID) -> schemas.ResourceOut:
    row = (await session.execute(_resource_select().where(Resource.id == resource_id))).one()
    return _resource_out(row)


async def get_resource(
    session: AsyncSession, principal: Principal, resource_id: uuid.UUID, lock: bool = False
) -> Resource:
    resource = await session.get(Resource, resource_id, with_for_update=lock)
    if resource is None:
        raise _not_found()
    unit = await session.get(Unit, resource.unit_id)
    if unit is None or not principal.can_access_gouvernorat(unit.gouvernorat_code):
        raise _not_found()
    return resource


async def save_resource(
    session: AsyncSession, principal: Principal, body: schemas.ResourceIn, resource_id: uuid.UUID | None = None
) -> Resource:
    unit = await get_unit(session, principal, body.unit_id)
    await _check_write(session, principal, Action.RESOURCES_WRITE, unit.gouvernorat_code)
    if resource_id is None:
        resource = Resource(status=body.status)
        session.add(resource)
    else:
        resource = await get_resource(session, principal, resource_id, lock=True)
        if body.version is not None and body.version != resource.version:
            raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
        if resource.status == "assigned" and (body.status != "available" or body.unit_id != resource.unit_id):
            # An engaged resource changes state only through its assignment.
            raise HTTPException(status.HTTP_409_CONFLICT, "resource_busy")
        if resource.status != "assigned":
            resource.status = body.status
        resource.version += 1
    resource.unit_id, resource.kind, resource.label, resource.notes = body.unit_id, body.kind, body.label, body.notes
    resource.location = _point_wkt(body.location) if body.location else None
    resource.updated_at = datetime.now(UTC)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "label_taken") from exc
    await session.refresh(resource)
    return resource


async def delete_resource(session: AsyncSession, principal: Principal, resource_id: uuid.UUID) -> None:
    resource = await get_resource(session, principal, resource_id, lock=True)
    unit = await session.get(Unit, resource.unit_id)
    assert unit is not None
    await _check_write(session, principal, Action.RESOURCES_WRITE, unit.gouvernorat_code)
    if resource.status == "assigned":
        raise HTTPException(status.HTTP_409_CONFLICT, "resource_busy")
    used = await session.scalar(select(func.count()).where(Assignment.resource_id == resource.id))
    if used:
        # Kept for the history of past interventions: taken out of service instead.
        raise HTTPException(status.HTTP_409_CONFLICT, "resource_in_history")
    await session.delete(resource)
    await session.flush()


async def announce(session: AsyncSession, resource_id: uuid.UUID) -> None:
    """``resource.updated`` for the owning gouvernorat and, while engaged, the gouvernorats of its incident."""
    from app.modules.ops.service import all_gouvernorats

    out = await resource_out(session, resource_id)
    codes = {out.gouvernorat_code}
    if out.assignment is not None:
        codes |= set(await all_gouvernorats(session, out.assignment.incident_id))
    await emit(
        session, "resource.updated", {"resource": out.model_dump(mode="json"), "gouvernorat_codes": sorted(codes)}
    )


async def summary(session: AsyncSession, principal: Principal) -> schemas.ResourceSummary:
    rows = (
        await session.execute(
            select(Resource.kind, Resource.status, func.count())
            .join(Unit, Unit.id == Resource.unit_id)
            .where(unit_scope(principal))
            .group_by(Resource.kind, Resource.status)
        )
    ).all()
    by_kind: dict[str, dict[str, int]] = {}
    for kind, state, n in rows:
        by_kind.setdefault(kind, {"available": 0, "assigned": 0, "out_of_service": 0})[state] = int(n)
    return schemas.ResourceSummary(by_kind=by_kind)


async def map_features(
    session: AsyncSession, principal: Principal, bbox: tuple[float, float, float, float] | None
) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    units_query = select(Unit, _lat(Unit.location), _lon(Unit.location)).where(unit_scope(principal))
    if bbox:
        units_query = units_query.where(
            func.ST_Intersects(cast(Unit.location, Geometry), func.ST_MakeEnvelope(*bbox, 4326))
        )
    for unit, lat, lon in (await session.execute(units_query)).all():
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
                "properties": {
                    "layer": "unit",
                    "id": str(unit.id),
                    "name": unit.name_ar,
                    "name_fr": unit.name_fr,
                    "kind": unit.kind,
                    "phone": unit.phone,
                },
            }
        )
    rows = (await session.execute(_resource_select().where(unit_scope(principal)))).all()
    for row in rows:
        out = _resource_out(row)
        if out.location is None:
            continue
        if bbox and not (bbox[0] <= out.location.lon <= bbox[2] and bbox[1] <= out.location.lat <= bbox[3]):
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [out.location.lon, out.location.lat]},
                "properties": {
                    "layer": "resource",
                    "id": str(out.id),
                    "label": out.label,
                    "kind": out.kind,
                    "status": out.status,
                    "unit_name": out.unit_name,
                    "incident_id": str(out.assignment.incident_id) if out.assignment else None,
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}
