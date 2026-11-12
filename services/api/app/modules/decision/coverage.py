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
"""

import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2 import Geometry
from pydantic import BaseModel
from sqlalchemy import cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.decision import routing
from app.modules.geo.models import Delegation
from app.modules.ops.models import Resource, Unit
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


class UnitOut(BaseModel):
    id: uuid.UUID
    name_ar: str
    name_fr: str
    lat: float
    lon: float
    ready: dict[str, int]
    hosted: int


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


class CoverageOut(BaseModel):
    gouvernorat_code: int
    engine: str
    turnout_minutes: int
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


async def _grid(units: dict[uuid.UUID, tuple[float, float]], places: list[Place], turnout_s: float) -> tuple[Grid, str]:
    """Road time from every unit to every délégation (one matrix per délégation), kept ten minutes."""
    key = (tuple(sorted((str(k), v) for k, v in units.items())), tuple(p.id for p in places), turnout_s)
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
            grid.seconds[(unit, p.id)] = turnout_s + leg.duration_s
    engine = "fallback" if not engines or "fallback" in engines else engines.pop()
    if len(_grid_cache) > 64:
        _grid_cache.clear()
    _grid_cache[key] = (time.monotonic(), grid, engine)
    return grid, engine


async def _targets(session: AsyncSession) -> dict[str, dict[str, int]]:
    return {
        f: {z: await settings.threshold(session, f"snacr.target.{f}.{z}") for z in snacr.ZONES} for f in snacr.FAMILIES
    }


async def compute(session: AsyncSession, principal: Principal, code: int) -> CoverageOut:
    urban = await settings.threshold(session, "snacr.density.urban")
    periurban = await settings.threshold(session, "snacr.density.periurban")
    turnout = await settings.threshold(session, "coverage.turnout_minutes")
    limit = await settings.threshold(session, "coverage.suggestions_max")
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
    unit_rows = (
        await session.execute(
            select(Unit, func.ST_Y(geometry), func.ST_X(geometry))
            .where(Unit.gouvernorat_code == code)
            .order_by(Unit.name_ar)
        )
    ).all()
    units = {u.id: u for u, _, _ in unit_rows}
    where = {u.id: (float(la), float(lo)) for u, la, lo in unit_rows}

    host = aliased(Unit)
    kinds = frozenset().union(*FAMILY_KINDS.values())
    kind = func.coalesce(Resource.category_key, Resource.kind)
    rows = (
        await session.execute(
            select(Resource, kind)
            .join(Unit, Unit.id == Resource.unit_id)
            .outerjoin(host, host.id == Resource.stationed_unit_id)
            .where(or_(Unit.gouvernorat_code == code, host.gouvernorat_code == code), kind.in_(kinds))
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

    grid, engine = await _grid(where, places, turnout * 60.0)
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
        for p in places:
            t, unit = grid.best(ready_units, p.id)
            bt, _ = grid.best(base_units, p.id)
            cells[p.id][fam] = FamilyCell(
                minutes=round(t / 60, 1) if t is not None else None,
                target=targets[fam][p.zone],
                covered=p.id in now,
                baseline_covered=p.id in base,
                unit_name=units[unit].name_ar if unit is not None else None,
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
            )
        )
        family_vehicles = [Vehicle(v.id, v.label, v.family, v.home, v.at, v.ready, v.in_fleet) for v in mine if v.ready]
        for move in suggest(grid, family_vehicles, list(units), places, target_s, limit):
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
    return CoverageOut(
        gouvernorat_code=code,
        engine=engine,
        turnout_minutes=turnout,
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
            )
            for u in units.values()
        ],
        alerts=alerts,
        suggestions=suggestions,
        computed_at=datetime.now(UTC),
        assumptions=[
            f"turnout {turnout} min, then the road time ({engine})",
            "targets of the SNACR plan by family and zone (2024 density)",
            "demand point: the label point of each délégation, weighted by its 2024 population",
            "units of the gouvernorat only; a reinforcement counts at its host unit",
        ],
    )


@router.get("/coverage", response_model=CoverageOut)
async def coverage(
    principal: Reader, session: Session, gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None
) -> CoverageOut:
    """The live coverage of a gouvernorat: the caller's own, or the one the central room names."""
    if principal.is_national:
        if gouvernorat is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "gouvernorat_required")
        code = gouvernorat
    else:
        if gouvernorat is not None and gouvernorat != principal.gouvernorat_code:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
        assert principal.gouvernorat_code is not None
        code = principal.gouvernorat_code
    return await compute(session, principal, code)
