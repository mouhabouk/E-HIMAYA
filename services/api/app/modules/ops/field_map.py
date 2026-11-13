"""The field layers of the interactive map (Yamen 2026-11-13, docs/phase-ml/design-ml.md §7).

* ``GET /api/v1/staff/field-map/inspections``: the places of the periodic inspections with their last report and
  their next mission, for the general inspectorate (``inspector_general``).
* ``GET /api/v1/staff/field-map/vehicles``: the last known position of each vehicle (the leader's phone during a
  mission), for the inspector general, the head of the room (``ops_manager``) and the field commander only.
* ``GET /api/v1/staff/field-map/par``: the teams inside a danger zone (OS7), at their vehicle's last position, with the
  state of their check, for the same three roles.

Nothing is copied: each layer reads the tables its own screen reads (the inspections' places, the resources, the PAR
board). The system administrator reveals or hides each layer from the permissions screen (the features catalogue:
``map.inspections``, ``map.vehicles``, ``map.par``), per role, per account or per gouvernorat. A regional account sees
its own gouvernorat (row level security, and the units' scope here).
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from geoalchemy2 import Geometry
from pydantic import BaseModel
from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.features import service as features
from app.modules.inspections import service as inspections
from app.modules.inspections.models import Inspection, MissionSite
from app.modules.ops.models import Assignment, CrewPosition, Incident, Resource, Unit
from app.modules.ops.resources import unit_scope
from app.modules.par import schemas as par_schemas
from app.modules.par import service as par
from app.modules.par.models import Closure, Missing, Team

router = APIRouter(prefix="/api/v1/staff/field-map", tags=["staff", "map"])

Session = Annotated[AsyncSession, Depends(get_session)]
#: Who reads each layer by default; the administrator grants it to others or hides it (features catalogue).
INSPECTION_ROLES = (Role.INSPECTOR_GENERAL,)
FIELD_ROLES = (Role.INSPECTOR_GENERAL, Role.OPS_MANAGER, Role.FIELD_COMMANDER)
VEHICLES_FEATURE = "map.vehicles"
Inspectorate = Annotated[Principal, Depends(require_roles(*INSPECTION_ROLES))]
Field = Annotated[Principal, Depends(require_roles(*FIELD_ROLES))]


class Point(BaseModel):
    lat: float
    lon: float


class InspectionSiteOut(BaseModel):
    key: str
    target: Literal["room", "unit"]
    room: str | None
    unit_kind: str | None
    name: str
    gouvernorat_code: int | None
    # Where the place is drawn: the unit's own position, else where the inspector arrived, else where the report was
    # signed; a regional room at its regional directorate.
    location: Point | None
    location_source: Literal["unit", "arrived", "report", "directorate"] | None
    last_inspection_id: uuid.UUID | None
    last_on: datetime | None
    last_score: int | None
    last_verdict: str | None
    next_on: date | None


class InspectionSitesOut(BaseModel):
    items: list[InspectionSiteOut]
    # The places with no position known yet (listed on the inspections screen, not drawn).
    unplaced: int


class VehicleOut(BaseModel):
    id: uuid.UUID
    label: str
    kind: str
    status: str
    unit_name: str
    gouvernorat_code: int
    location: Point
    at: datetime | None
    incident_id: uuid.UUID | None


class VehiclesOut(BaseModel):
    items: list[VehicleOut]
    # The vehicles whose phone never gave a position: at their unit, on the units and resources layer.
    unplaced: int


class ParTeamOut(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    gouvernorat_code: int | None
    label: str
    zone: str
    leader_name: str | None
    members: int
    status: str
    entered_at: datetime
    last_confirmed_at: datetime
    location: Point | None
    # «crew»: the vehicle's last position from the leader's phone; «incident»: the incident's place.
    location_source: Literal["crew", "incident"] | None
    at: datetime | None


class ParTeamsOut(BaseModel):
    items: list[ParTeamOut]


def _lat(col: Any) -> Any:
    return func.ST_Y(cast(col, Geometry))


def _lon(col: Any) -> Any:
    return func.ST_X(cast(col, Geometry))


def _key(r: MissionSite | Inspection) -> str:
    """One key per place, as the inspections' screen keys them."""
    return inspections.place_key(r.target, r.room, r.gouvernorat_code, r.unit_kind, r.unit_name)


async def sees_vehicles(principal: Principal) -> bool:
    """The caller may see where the vehicles are now: one of the three roles, or granted it, and not hidden from it.
    The units and resources layer (and the operations room's map) draw a vehicle at its unit for anyone else."""
    seen_as = await features.as_for(principal, VEHICLES_FEATURE)
    return seen_as is not None and bool(seen_as.roles & frozenset(FIELD_ROLES))


# ---------------------------------------------------------------- the places of the inspections


async def inspection_sites(session: AsyncSession, principal: Principal) -> InspectionSitesOut:
    code = principal.gouvernorat_code
    places = await inspections.unit_status(session, code)
    unit_of: dict[str, uuid.UUID] = {}
    arrived: dict[str, Point] = {}
    reported: dict[str, Point] = {}
    sites = select(MissionSite, _lat(MissionSite.arrived_location), _lon(MissionSite.arrived_location)).order_by(
        MissionSite.arrived_at.desc().nulls_last()
    )
    if code is not None:
        sites = sites.where(MissionSite.gouvernorat_code == code)
    for site, lat, lon in await session.execute(sites):
        key = _key(site)
        if site.unit_id is not None:
            unit_of.setdefault(key, site.unit_id)
        if lat is not None:
            arrived.setdefault(key, Point(lat=float(lat), lon=float(lon)))
    reports = (
        select(Inspection, _lat(Inspection.location), _lon(Inspection.location))
        .where(Inspection.deleted_at.is_(None))
        .order_by(Inspection.submitted_at.desc().nulls_last())
    )
    if code is not None:
        reports = reports.where(Inspection.gouvernorat_code == code)
    for report, lat, lon in await session.execute(reports):
        key = _key(report)
        if report.unit_id is not None:
            unit_of.setdefault(key, report.unit_id)
        if lat is not None:
            reported.setdefault(key, Point(lat=float(lat), lon=float(lon)))
    units: dict[uuid.UUID, Point] = {}
    directorates: dict[int, Point] = {}
    query = select(Unit.id, Unit.kind, Unit.gouvernorat_code, _lat(Unit.location), _lon(Unit.location)).order_by(
        Unit.name_ar
    )
    if code is not None:
        query = query.where(Unit.gouvernorat_code == code)
    for unit_id, kind, gouvernorat, lat, lon in await session.execute(query):
        units[unit_id] = Point(lat=float(lat), lon=float(lon))
        if kind == "directorate":
            directorates.setdefault(gouvernorat, units[unit_id])
    items: list[InspectionSiteOut] = []
    unplaced = 0
    for p in places:
        key = inspections.place_key(p.target, p.room, p.gouvernorat_code, p.unit_kind, p.unit_name)
        location: Point | None = None
        source: Literal["unit", "arrived", "report", "directorate"] | None = None
        unit_id = unit_of.get(key)
        if unit_id is not None and unit_id in units:
            location, source = units[unit_id], "unit"
        elif key in arrived:
            location, source = arrived[key], "arrived"
        elif key in reported:
            location, source = reported[key], "report"
        elif p.target == "room" and p.room == "regional" and p.gouvernorat_code in directorates:
            location, source = directorates[p.gouvernorat_code], "directorate"
        if location is None:
            unplaced += 1
            continue
        items.append(
            InspectionSiteOut(
                key=key,
                target=p.target,
                room=p.room,
                unit_kind=p.unit_kind,
                name=p.name,
                gouvernorat_code=p.gouvernorat_code,
                location=location,
                location_source=source,
                last_inspection_id=p.last_inspection_id,
                last_on=p.last_on,
                last_score=p.last_score,
                last_verdict=p.last_verdict,
                next_on=p.next_on,
            )
        )
    return InspectionSitesOut(items=items, unplaced=unplaced)


# ---------------------------------------------------------------- the vehicles


async def vehicles(session: AsyncSession, principal: Principal) -> VehiclesOut:
    active = (
        select(Assignment.resource_id, Assignment.incident_id)
        .where(Assignment.status.in_(("en_route", "on_scene")))
        .subquery()
    )
    rows = await session.execute(
        select(Resource, Unit.name_ar, Unit.gouvernorat_code, _lat(Resource.location), _lon(Resource.location))
        .add_columns(active.c.incident_id)
        .join(Unit, Unit.id == Resource.unit_id)
        .outerjoin(active, active.c.resource_id == Resource.id)
        .where(unit_scope(principal), Resource.retired_on.is_(None))
        .order_by(Unit.gouvernorat_code, Resource.label)
    )
    items: list[VehicleOut] = []
    unplaced = 0
    seen: set[uuid.UUID] = set()
    for resource, unit_name, gouvernorat, lat, lon, incident_id in rows:
        if resource.id in seen:
            continue
        seen.add(resource.id)
        if lat is None:
            unplaced += 1
            continue
        items.append(
            VehicleOut(
                id=resource.id,
                label=resource.label,
                kind=resource.kind,
                status=resource.status,
                unit_name=unit_name,
                gouvernorat_code=gouvernorat,
                location=Point(lat=float(lat), lon=float(lon)),
                at=resource.location_at,
                incident_id=incident_id,
            )
        )
    return VehiclesOut(items=items, unplaced=unplaced)


# ---------------------------------------------------------------- the PAR teams


async def par_teams(session: AsyncSession) -> ParTeamsOut:
    """The teams still inside a danger zone of an incident whose check is not closed (row level security keeps a
    regional account to its own gouvernorat)."""
    closed = select(Closure.incident_id)
    teams = list(
        await session.scalars(
            select(Team).where(Team.out_at.is_(None), Team.incident_id.not_in(closed)).order_by(Team.entered_at)
        )
    )
    if not teams:
        return ParTeamsOut(items=[])
    last = {
        r.assignment_id: r
        for r in await session.execute(
            select(
                CrewPosition.assignment_id,
                CrewPosition.at,
                _lat(CrewPosition.location).label("lat"),
                _lon(CrewPosition.location).label("lon"),
            )
            .where(CrewPosition.assignment_id.in_({t.assignment_id for t in teams}))
            .order_by(CrewPosition.assignment_id, CrewPosition.at.desc())
            .ext(distinct_on(CrewPosition.assignment_id))
        )
    }
    places = {
        r.id: r
        for r in await session.execute(
            select(Incident.id, _lat(Incident.centroid).label("lat"), _lon(Incident.centroid).label("lon")).where(
                Incident.id.in_({t.incident_id for t in teams})
            )
        )
    }
    missing = set(
        await session.scalars(
            select(Missing.team_id).where(Missing.team_id.in_({t.id for t in teams}), Missing.recovered_at.is_(None))
        )
    )
    settings: dict[int | None, par_schemas.SettingOut] = {}
    now = par.now()
    items: list[ParTeamOut] = []
    for team in teams:
        if team.gouvernorat_code not in settings:
            settings[team.gouvernorat_code] = await par.setting(session, team.gouvernorat_code)
        s = settings[team.gouvernorat_code]
        location: Point | None = None
        source: Literal["crew", "incident"] | None = None
        at: datetime | None = None
        fix = last.get(team.assignment_id)
        place = places.get(team.incident_id)
        if fix is not None:
            location, source, at = Point(lat=float(fix.lat), lon=float(fix.lon)), "crew", fix.at
        elif place is not None and place.lat is not None:
            location, source = Point(lat=float(place.lat), lon=float(place.lon)), "incident"
        items.append(
            ParTeamOut(
                id=team.id,
                incident_id=team.incident_id,
                gouvernorat_code=team.gouvernorat_code,
                label=team.label,
                zone=team.zone,
                leader_name=team.leader_name,
                members=len(team.members or []),
                status=par.team_status(team, s, now, team.id in missing),
                entered_at=team.entered_at,
                last_confirmed_at=team.last_confirmed_at,
                location=location,
                location_source=source,
                at=at,
            )
        )
    return ParTeamsOut(items=items)


# ---------------------------------------------------------------- routes


@router.get("/inspections", response_model=InspectionSitesOut)
async def get_inspection_sites(principal: Inspectorate, session: Session) -> InspectionSitesOut:
    return await inspection_sites(session, principal)


@router.get("/vehicles", response_model=VehiclesOut)
async def get_vehicles(principal: Field, session: Session) -> VehiclesOut:
    return await vehicles(session, principal)


@router.get("/par", response_model=ParTeamsOut)
async def get_par_teams(_: Field, session: Session) -> ParTeamsOut:
    return await par_teams(session)
