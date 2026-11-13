"""Live coverage and repositioning (OS3, docs/phase-os3/design-os3.md §3; Yamen 2026-11-11: «تغطية حية وإعادة تمركز
عندما تخرج الوحدات»).

For the gouvernorat of a room: each délégation (its 2024 population, its label point) and each family of vehicles of
the SNACR plan (medical, road, fire, rescue), the time the quickest ready vehicle needs to get there (turnout plus the
road time of ``routing.travel``) against the SNACR target of its zone (urban, periurban, rural). Three answers:

* the coverage now, with the ready vehicles where they are (a reinforcement counts at its host unit);
* the planned coverage, every vehicle of the register (decommissioned ones aside) at its own unit: a délégation the
  plan covers and the ready vehicles do not is an alert, with its population (vehicles on a mission, broken, in the
  workshop or sent elsewhere);
* repositioning suggestions: the move of one ready vehicle to another unit that brings the most population back within
  the target (net of what its own unit loses), greedily, a few per family. Accepting one sends the vehicle as
  reinforcement (``POST /inventory/vehicles/{id}/state``); the log keeps the decision and its gain.

Only what the room sees: the units of its gouvernorat (row-level security), never a neighbour's.

Follow-ups (OS3-2 and OS3-4, docs/phase-os3/design-os3b.md §2 and §4; Yamen 2026-11-13):

* the turnout of each unit is measured on its missions (median of the call to «on the way» over
  ``coverage.turnout_days``) when it has at least ``coverage.turnout_min_missions``; otherwise, or when
  ``coverage.turnout_measured`` is 0, the default ``coverage.turnout_minutes``. The road time is the routing engine's
  (Valhalla, set by default in production), a straight-line estimate when it is down;
* the central room may count the units of the neighbouring gouvernorats within ``coverage.neighbour_m`` of a
  délégation (``neighbours=true``): the coverage then says which délégation a neighbour covers, and a suggestion may
  bring a neighbour's ready vehicle to a unit of the gouvernorat (sent by the central room, which decides between two
  gouvernorats).
"""

import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2 import Geography, Geometry
from pydantic import BaseModel
from sqlalchemy import cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.db import as_system, get_session
from app.core.security import Principal, Role, require_roles
from app.modules.decision import routing
from app.modules.geo.models import Delegation
from app.modules.ops.models import Assignment, Resource, Unit
from app.modules.reports.staff_router import READ_ROLES
from app.modules.settings import service as settings
from app.modules.snacr import domain as snacr

router = APIRouter(prefix="/api/v1/staff", tags=["staff", "decision"])
Session = Annotated[AsyncSession, Depends(get_session)]
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES, Role.MAINTENANCE_OFFICER))]

Family = Literal["medical", "road", "fire", "rescue"]
# The vehicle types (catalogue key, or the older kind) that answer each SNACR family.
FAMILY_KINDS: dict[str, frozenset[str]] = {
    "medical": frozenset({"ambulance"}),
    "road": frozenset({"rescue_vehicle"}),
    "fire": frozenset({"fire_engine", "water_tanker", "large_extinguisher", "aerial_ladder"}),
    "rescue": frozenset({"rescue_vehicle", "hazmat_vehicle", "boat"}),
}
CACHE_S = 600


# ---------------------------------------------------------------- the computation (no database)


@dataclass(frozen=True, slots=True)
class Place:
    id: int
    name_ar: str
    name_fr: str
    population: int
    zone: str
    lat: float
    lon: float


@dataclass(slots=True)
class Vehicle:
    id: uuid.UUID
    label: str
    family: frozenset[str]
    home: uuid.UUID
    # Where it is now: its host unit while in reinforcement.
    at: uuid.UUID
    ready: bool
    in_fleet: bool


@dataclass(slots=True)
class Grid:
    """Seconds from each unit to each délégation (turnout included)."""

    seconds: dict[tuple[uuid.UUID, int], float] = field(default_factory=dict)

    def best(self, units: Iterable[uuid.UUID], place: int) -> tuple[float | None, uuid.UUID | None]:
        found: tuple[float | None, uuid.UUID | None] = (None, None)
        for unit in units:
            t = self.seconds.get((unit, place))
            if t is not None and (found[0] is None or t < found[0]):
                found = (t, unit)
        return found


def covered(grid: Grid, units: set[uuid.UUID], places: list[Place], targets: dict[str, float]) -> set[int]:
    out: set[int] = set()
    for p in places:
        t, _ = grid.best(units, p.id)
        if t is not None and t <= targets[p.zone]:
            out.add(p.id)
    return out


def population(places: list[Place], ids: set[int]) -> int:
    return sum(p.population for p in places if p.id in ids)


def suggest(
    grid: Grid,
    vehicles: list[Vehicle],
    unit_ids: list[uuid.UUID],
    places: list[Place],
    targets: dict[str, float],
    limit: int,
) -> list[dict[str, Any]]:
    """Greedy moves of one ready vehicle of the family each: the best net gain of population first."""
    ready = [v for v in vehicles if v.ready]
    moves: list[dict[str, Any]] = []
    moved: set[uuid.UUID] = set()
    for _ in range(limit):
        stationed = [v.at for v in ready]
        now = covered(grid, set(stationed), places, targets)
        best: dict[str, Any] | None = None
        for i, v in enumerate(ready):
            if v.id in moved:
                continue
            others = stationed[:i] + stationed[i + 1 :]
            for unit in unit_ids:
                if unit == v.at:
                    continue
                after = covered(grid, {*others, unit}, places, targets)
                gain = population(places, after) - population(places, now)
                if gain > 0 and (best is None or gain > best["gain"]):
                    best = {
                        "vehicle": v,
                        "to": unit,
                        "gain": gain,
                        "newly": sorted(after - now),
                        "lost": sorted(now - after),
                    }
        if best is None:
            break
        moves.append(best)
        best["vehicle"].at = best["to"]
        moved.add(best["vehicle"].id)
    return moves


# ---------------------------------------------------------------- answers


class FamilyCell(BaseModel):
    minutes: float | None
    target: int
    covered: bool
    baseline_covered: bool
    unit_name: str | None
    # OS3-4: the quickest unit belongs to a neighbouring gouvernorat.
    neighbour: bool = False


class PlaceOut(BaseModel):
    id: int
    name_ar: str
    name_fr: str
    population: int
    zone: str
    lat: float
    lon: float
    families: dict[str, FamilyCell]


class FamilyOut(BaseModel):
    family: Family
    population: int
    covered_population: int
    covered_pct: float
    baseline_pct: float
    ready: int
    fleet: int
    out: int
    # OS3-4: the coverage now with the gouvernorat's own units only (equal to ``covered_pct`` without neighbours).
    own_pct: float


class UnitOut(BaseModel):
    id: uuid.UUID
    name_ar: str
    name_fr: str
    lat: float
    lon: float
    ready: dict[str, int]
    hosted: int
    gouvernorat_code: int
    neighbour: bool = False
    # OS3-2: the turnout used for this unit, measured on its missions or the default.
    turnout_minutes: float
    turnout_source: Literal["measured", "default"]
    turnout_missions: int
    turnout_p90_minutes: float | None


class AlertOut(BaseModel):
    family: Family
    delegation_id: int
    delegation: str
    population: int
    minutes: float | None
    target: int
    baseline_minutes: float | None


class SuggestionOut(BaseModel):
    family: Family
    vehicle_id: uuid.UUID
    label: str
    from_unit_id: uuid.UUID
    from_unit: str
    to_unit_id: uuid.UUID
    to_unit: str
    gain_population: int
    newly_covered: list[str]
    lost: list[str]
    version: int
    from_gouvernorat_code: int


class CoverageOut(BaseModel):
    gouvernorat_code: int
    engine: str
    turnout_minutes: int
    turnout_mode: Literal["measured", "uniform"]
    neighbours: bool
    neighbour_m: int
    targets: dict[str, dict[str, int]]
    families: list[FamilyOut]
    delegations: list[PlaceOut]
    units: list[UnitOut]
    alerts: list[AlertOut]
    suggestions: list[SuggestionOut]
    computed_at: datetime
    assumptions: list[str]


# ---------------------------------------------------------------- loading

_grid_cache: dict[tuple[Any, ...], tuple[float, Grid, str]] = {}


async def _grid(
    units: dict[uuid.UUID, tuple[float, float]], places: list[Place], turnout_s: dict[uuid.UUID, float]
) -> tuple[Grid, str]:
    """Road time from every unit to every délégation (one matrix per délégation), kept ten minutes."""
    key = (
        tuple(sorted((str(k), v, turnout_s[k]) for k, v in units.items())),
        tuple(p.id for p in places),
    )
    hit = _grid_cache.get(key)
    if hit is not None and time.monotonic() - hit[0] < CACHE_S:
        return hit[1], hit[2]
    grid = Grid()
    ids = list(units)
    sources = [routing.Point(*units[u]) for u in ids]
    engines: set[str] = set()
    for p in places:
        legs, engine = await routing.travel(sources, routing.Point(p.lat, p.lon), "truck")
        engines.add(engine)
        for unit, leg in zip(ids, legs, strict=True):
            grid.seconds[(unit, p.id)] = turnout_s[unit] + leg.duration_s
    engine = "fallback" if not engines or "fallback" in engines else engines.pop()
    if len(_grid_cache) > 64:
        _grid_cache.clear()
    _grid_cache[key] = (time.monotonic(), grid, engine)
    return grid, engine


async def _targets(session: AsyncSession) -> dict[str, dict[str, int]]:
    return {
        f: {z: await settings.threshold(session, f"snacr.target.{f}.{z}") for z in snacr.ZONES} for f in snacr.FAMILIES
    }


@dataclass(frozen=True, slots=True)
class Turnout:
    seconds: float
    source: Literal["measured", "default"]
    missions: int
    p90_s: float | None


async def turnouts(
    session: AsyncSession, unit_ids: list[uuid.UUID], default_s: float, *, measured: bool, days: int, least: int
) -> dict[uuid.UUID, Turnout]:
    """OS3-2: the median time from the order to «on the way» of each unit's vehicles over the last days (missions
    with both times, between a second and half an hour), when the unit has enough of them; the default otherwise."""
    out = {u: Turnout(default_s, "default", 0, None) for u in unit_ids}
    if not unit_ids:
        return out
    secs = func.extract("epoch", Assignment.en_route_at - Assignment.created_at)
    # Aggregates of the caller's own units only (listed above), whatever gouvernorat their missions were in.
    async with as_system(session):
        rows = (
            await session.execute(
                select(
                    Resource.unit_id,
                    func.count(),
                    func.percentile_cont(0.5).within_group(secs),
                    func.percentile_cont(0.9).within_group(secs),
                )
                .join(Resource, Resource.id == Assignment.resource_id)
                .where(
                    Resource.unit_id.in_(unit_ids),
                    Assignment.en_route_at.is_not(None),
                    Assignment.created_at >= datetime.now(UTC) - timedelta(days=days),
                    secs >= 1,
                    secs <= 1800,
                )
                .group_by(Resource.unit_id)
            )
        ).all()
    for unit, n, median, p90 in rows:
        if measured and n >= least:
            out[unit] = Turnout(float(median), "measured", int(n), float(p90))
        else:
            out[unit] = Turnout(default_s, "default", int(n), float(p90) if n >= least else None)
    return out


async def compute(session: AsyncSession, principal: Principal, code: int, neighbours: bool = False) -> CoverageOut:
    urban = await settings.threshold(session, "snacr.density.urban")
    periurban = await settings.threshold(session, "snacr.density.periurban")
    turnout = await settings.threshold(session, "coverage.turnout_minutes")
    limit = await settings.threshold(session, "coverage.suggestions_max")
    measured = await settings.threshold(session, "coverage.turnout_measured") == 1
    turnout_days = await settings.threshold(session, "coverage.turnout_days")
    least = await settings.threshold(session, "coverage.turnout_min_missions")
    reach = await settings.threshold(session, "coverage.neighbour_m")
    targets = await _targets(session)

    point = func.coalesce(Delegation.label, func.ST_PointOnSurface(Delegation.boundary))
    places = [
        Place(d, ar, fr, int(pop or 0), snacr.zone_of(pop, area, urban, periurban), float(la), float(lo))
        for d, ar, fr, pop, area, la, lo in (
            await session.execute(
                select(
                    Delegation.id,
                    Delegation.name_ar,
                    Delegation.name_fr,
                    Delegation.population_2024,
                    Delegation.area_km2,
                    func.ST_Y(point),
                    func.ST_X(point),
                )
                .where(Delegation.gouvernorat_code == code, point.is_not(None))
                .order_by(Delegation.name_ar)
            )
        ).all()
    ]
    geometry = cast(Unit.location, Geometry)
    within = Unit.gouvernorat_code == code
    if neighbours:
        # OS3-4: a neighbour's unit near enough to one of the gouvernorat's délégations.
        near = (
            select(Delegation.id)
            .where(Delegation.gouvernorat_code == code, func.ST_DWithin(Unit.location, cast(point, Geography), reach))
            .exists()
        )
        within = within | near
    unit_rows = (
        await session.execute(
            select(Unit, func.ST_Y(geometry), func.ST_X(geometry))
            .where(within, Unit.location.is_not(None))
            .order_by(Unit.name_ar)
        )
    ).all()
    units = {u.id: u for u, _, _ in unit_rows}
    own = [u.id for u in units.values() if u.gouvernorat_code == code]
    where = {u.id: (float(la), float(lo)) for u, la, lo in unit_rows}

    host = aliased(Unit)
    kinds = frozenset().union(*FAMILY_KINDS.values())
    kind = func.coalesce(Resource.category_key, Resource.kind)
    rows = (
        await session.execute(
            select(Resource, kind)
            .join(Unit, Unit.id == Resource.unit_id)
            .outerjoin(host, host.id == Resource.stationed_unit_id)
            .where(
                or_(Unit.gouvernorat_code == code, host.gouvernorat_code == code, Unit.id.in_(list(units))),
                kind.in_(kinds),
            )
        )
    ).all()
    vehicles: list[Vehicle] = []
    for r, k in rows:
        families = frozenset(f for f, ks in FAMILY_KINDS.items() if k in ks)
        at = r.stationed_unit_id or r.unit_id
        if at not in units and r.unit_id not in units:
            continue
        vehicles.append(
            Vehicle(
                id=r.id,
                label=r.label,
                family=families,
                home=r.unit_id,
                at=at if at in units else r.unit_id,
                ready=r.status == "available" and at in units,
                # The planned coverage: every vehicle not decommissioned, at its own unit.
                in_fleet=r.out_reason != "retired" and r.unit_id in units,
            )
        )
    versions = {r.id: r.version for r, _ in rows}

    timing = await turnouts(session, list(units), turnout * 60.0, measured=measured, days=turnout_days, least=least)
    grid, engine = await _grid(where, places, {u: t.seconds for u, t in timing.items()})
    own_set = set(own)
    seconds = {z: 0.0 for z in snacr.ZONES}
    out_families: list[FamilyOut] = []
    cells: dict[int, dict[str, FamilyCell]] = {p.id: {} for p in places}
    alerts: list[AlertOut] = []
    suggestions: list[SuggestionOut] = []
    total = sum(p.population for p in places)
    names = {p.id: p.name_ar for p in places}
    for fam in snacr.FAMILIES:
        target_s: dict[str, float] = {z: targets[fam][z] * 60.0 for z in seconds}
        mine = [v for v in vehicles if fam in v.family]
        ready_units = {v.at for v in mine if v.ready}
        base_units = {v.home for v in mine if v.in_fleet}
        now = covered(grid, ready_units, places, target_s)
        base = covered(grid, base_units, places, target_s)
        own_now = covered(grid, ready_units & own_set, places, target_s) if neighbours else now
        for p in places:
            t, unit = grid.best(ready_units, p.id)
            bt, _ = grid.best(base_units, p.id)
            cells[p.id][fam] = FamilyCell(
                minutes=round(t / 60, 1) if t is not None else None,
                target=targets[fam][p.zone],
                covered=p.id in now,
                baseline_covered=p.id in base,
                unit_name=units[unit].name_ar if unit is not None else None,
                neighbour=unit is not None and unit not in own_set,
            )
            if p.id in base and p.id not in now:
                alerts.append(
                    AlertOut(
                        family=fam,
                        delegation_id=p.id,
                        delegation=p.name_ar,
                        population=p.population,
                        minutes=round(t / 60, 1) if t is not None else None,
                        target=targets[fam][p.zone],
                        baseline_minutes=round(bt / 60, 1) if bt is not None else None,
                    )
                )
        out_families.append(
            FamilyOut(
                family=fam,
                population=total,
                covered_population=population(places, now),
                covered_pct=round(100 * population(places, now) / total, 1) if total else 0.0,
                baseline_pct=round(100 * population(places, base) / total, 1) if total else 0.0,
                ready=sum(v.ready for v in mine),
                fleet=len(mine),
                out=sum(not v.ready for v in mine),
                own_pct=round(100 * population(places, own_now) / total, 1) if total else 0.0,
            )
        )
        family_vehicles = [Vehicle(v.id, v.label, v.family, v.home, v.at, v.ready, v.in_fleet) for v in mine if v.ready]
        # The moves go to the gouvernorat's own units (from a neighbour's too, with ``neighbours``).
        for move in suggest(grid, family_vehicles, own, places, target_s, limit):
            v = move["vehicle"]
            origin = next(x.at for x in mine if x.id == v.id)
            suggestions.append(
                SuggestionOut(
                    family=fam,
                    vehicle_id=v.id,
                    label=v.label,
                    from_unit_id=origin,
                    from_unit=units[origin].name_ar,
                    to_unit_id=move["to"],
                    to_unit=units[move["to"]].name_ar,
                    gain_population=move["gain"],
                    newly_covered=[names[i] for i in move["newly"]],
                    lost=[names[i] for i in move["lost"]],
                    version=versions[v.id],
                    from_gouvernorat_code=units[origin].gouvernorat_code,
                )
            )
    alerts.sort(key=lambda a: -a.population)
    ready_by_unit: dict[uuid.UUID, dict[str, int]] = {u: {f: 0 for f in snacr.FAMILIES} for u in units}
    hosted: dict[uuid.UUID, int] = {u: 0 for u in units}
    for v in vehicles:
        if v.ready:
            for name in v.family:
                ready_by_unit[v.at][name] += 1
            if v.at != v.home:
                hosted[v.at] += 1
    mode: Literal["measured", "uniform"] = "measured" if measured else "uniform"
    return CoverageOut(
        gouvernorat_code=code,
        engine=engine,
        turnout_minutes=turnout,
        turnout_mode=mode,
        neighbours=neighbours,
        neighbour_m=reach,
        targets=targets,
        families=out_families,
        delegations=[
            PlaceOut(
                id=p.id,
                name_ar=p.name_ar,
                name_fr=p.name_fr,
                population=p.population,
                zone=p.zone,
                lat=p.lat,
                lon=p.lon,
                families=cells[p.id],
            )
            for p in places
        ],
        units=[
            UnitOut(
                id=u.id,
                name_ar=u.name_ar,
                name_fr=u.name_fr,
                lat=where[u.id][0],
                lon=where[u.id][1],
                ready=ready_by_unit[u.id],
                hosted=hosted[u.id],
                gouvernorat_code=u.gouvernorat_code,
                neighbour=u.id not in own_set,
                turnout_minutes=round(timing[u.id].seconds / 60, 1),
                turnout_source=timing[u.id].source,
                turnout_missions=timing[u.id].missions,
                turnout_p90_minutes=round(p90 / 60, 1) if (p90 := timing[u.id].p90_s) is not None else None,
            )
            for u in units.values()
        ],
        alerts=alerts,
        suggestions=suggestions,
        computed_at=datetime.now(UTC),
        assumptions=[
            (
                f"turnout measured per unit over {turnout_days} days (at least {least} missions), else {turnout} min"
                if measured
                else f"turnout {turnout} min"
            )
            + f", then the road time ({engine})",
            "targets of the SNACR plan by family and zone (2024 density)",
            "demand point: the label point of each délégation, weighted by its 2024 population",
            (
                f"units of the gouvernorat and of its neighbours within {reach // 1000} km"
                if neighbours
                else "units of the gouvernorat only"
            )
            + "; a reinforcement counts at its host unit",
        ],
    )


@router.get("/coverage", response_model=CoverageOut)
async def coverage(
    principal: Reader,
    session: Session,
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
    neighbours: bool = False,
) -> CoverageOut:
    """The live coverage of a gouvernorat: the caller's own, or the one the central room names (which may count the
    units of the neighbouring gouvernorats, OS3-4)."""
    if neighbours and not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "national_only")
    if principal.is_national:
        if gouvernorat is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "gouvernorat_required")
        code = gouvernorat
    else:
        if gouvernorat is not None and gouvernorat != principal.gouvernorat_code:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
        assert principal.gouvernorat_code is not None
        code = principal.gouvernorat_code
    return await compute(session, principal, code, neighbours)
