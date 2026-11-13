"""The monthly report of the fleet (OS3-3, docs/phase-os3/design-os3b.md §3; Yamen 2026-11-13): readiness and the cost
of maintenance, per gouvernorat and month.

* **Readiness** = the vehicle-days a vehicle was neither broken nor in the workshop, over the vehicle-days it was in
  the fleet (from its entry in the register, until its decommissioning). The state over time comes from the vehicle's
  log (``ops.vehicle_event``): before its first event a vehicle was in the state that event started from; without
  any event, in its current state. A mission is not a breakdown: it counts as ready.
* **Cost** = parts, labour and outside workshop entered on the stays that ended in the month (``maintenance_end``).
* Workshop entries and decommissionings of the month; the costliest vehicles of the month.

Months follow Tunisia's time. A regional caller reads its gouvernorat; the central room and the national maintenance
department read every one.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.geo.models import Gouvernorat
from app.modules.inventory import domain, schemas
from app.modules.inventory.router import Reader, _scope
from app.modules.ops.models import Resource, Unit, VehicleEvent
from app.modules.settings import service as settings

router = APIRouter(prefix="/api/v1/staff/inventory", tags=["staff", "inventory"])
Session = Annotated[AsyncSession, Depends(get_session)]
TUNIS = ZoneInfo("Africa/Tunis")
DOWN = frozenset({"broken", "maintenance"})
OUT = "retired"
DAY_S = 86_400.0
ZERO = Decimal("0.000")


# ---------------------------------------------------------------- the computation (no database)


@dataclass(frozen=True, slots=True)
class Change:
    at: datetime
    before: str
    after: str


def month_bounds(month: str) -> tuple[datetime, datetime]:
    """«2026-10» → its first instant and the first of the next month, in Tunisia's time (as UTC)."""
    year, mon = (int(x) for x in month.split("-"))
    start = datetime(year, mon, 1, tzinfo=TUNIS)
    end = datetime(year + (mon == 12), mon % 12 + 1, 1, tzinfo=TUNIS)
    return start.astimezone(UTC), end.astimezone(UTC)


def months_back(month: str, count: int) -> list[str]:
    year, mon = (int(x) for x in month.split("-"))
    out: list[str] = []
    for _ in range(count):
        out.append(f"{year:04d}-{mon:02d}")
        year, mon = (year - 1, 12) if mon == 1 else (year, mon - 1)
    return out[::-1]


def days_in_states(
    changes: list[Change], current: str, entered: datetime, start: datetime, end: datetime
) -> tuple[float, float]:
    """(days in the fleet, days down) of one vehicle between ``start`` and ``end``; ``changes`` oldest first."""
    lo = max(start, entered)
    if end <= lo:
        return 0.0, 0.0
    before = [c for c in changes if c.at < lo]
    after = [c for c in changes if c.at >= lo]
    state = before[-1].after if before else (after[0].before if after else current)
    fleet = down = 0.0
    t = lo
    for c in after:
        if c.at >= end:
            break
        span = (c.at - t).total_seconds()
        if state != OUT:
            fleet += span
            down += span if state in DOWN else 0.0
        t, state = c.at, c.after
    span = (end - t).total_seconds()
    if state != OUT:
        fleet += span
        down += span if state in DOWN else 0.0
    return fleet / DAY_S, down / DAY_S


def readiness(fleet_days: float, down_days: float) -> float | None:
    return round(100 * (fleet_days - down_days) / fleet_days, 1) if fleet_days > 0 else None


# ---------------------------------------------------------------- the route


def _money(*values: Decimal | None) -> Decimal:
    return sum((v for v in values if v is not None), ZERO)


@router.get("/fleet-report", response_model=schemas.FleetReportOut)
async def fleet_report(
    principal: Reader,
    session: Session,
    month: Annotated[str | None, Query(pattern=r"^20\d\d-(0[1-9]|1[0-2])$")] = None,
    months: Annotated[int, Query(ge=1, le=12)] = 6,
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
) -> schemas.FleetReportOut:
    now = datetime.now(UTC)
    current = now.astimezone(TUNIS).strftime("%Y-%m")
    month = month or current
    if month > current:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "month_in_future")
    if gouvernorat is not None and not principal.can_access_gouvernorat(gouvernorat):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
    span = months_back(month, months)
    bounds = {m: month_bounds(m) for m in span}
    last = min(bounds[month][1], now)

    where = [_scope(principal, Unit.gouvernorat_code)]
    if gouvernorat is not None:
        where.append(Unit.gouvernorat_code == gouvernorat)
    vehicles = (
        await session.execute(
            select(Resource, Unit.gouvernorat_code).join(Unit, Unit.id == Resource.unit_id).where(*where)
        )
    ).all()
    owner = {r.id: code for r, code in vehicles}
    events = (
        await session.execute(
            select(VehicleEvent)
            .where(VehicleEvent.resource_id.in_(list(owner)), VehicleEvent.created_at < last)
            .order_by(VehicleEvent.created_at)
        )
    ).scalars()
    changes: dict[uuid.UUID, list[Change]] = defaultdict(list)
    # Per (gouvernorat, month): workshop entries, decommissionings, the three costs; per vehicle of the month.
    counts: dict[tuple[int, str], list[int]] = defaultdict(lambda: [0, 0])
    costs: dict[tuple[int, str], list[Decimal]] = defaultdict(lambda: [ZERO, ZERO, ZERO])
    per_vehicle: dict[uuid.UUID, list[Decimal | int]] = defaultdict(lambda: [ZERO, 0])
    for e in events:
        if e.from_state != e.to_state:
            changes[e.resource_id].append(Change(e.created_at, e.from_state, e.to_state))
        at = e.created_at.astimezone(TUNIS).strftime("%Y-%m")
        if at not in bounds:
            continue
        key = (owner[e.resource_id], at)
        if e.kind == "maintenance_start":
            counts[key][0] += 1
        elif e.kind == "retire":
            counts[key][1] += 1
        elif e.kind == "maintenance_end":
            c = costs[key]
            c[0] += e.cost_parts or ZERO
            c[1] += e.cost_labour or ZERO
            c[2] += e.cost_external or ZERO
            if at == month:
                total = _money(e.cost_parts, e.cost_labour, e.cost_external)
                pv = per_vehicle[e.resource_id]
                pv[0] = Decimal(pv[0]) + total
                pv[1] = int(pv[1]) + 1

    days: dict[tuple[int, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
    present: dict[int, int] = defaultdict(int)
    m_start, m_end = bounds[month][0], min(bounds[month][1], now)
    for r, code in vehicles:
        state = domain.vehicle_state(r.status, r.out_reason, r.stationed_unit_id is not None)
        log = changes.get(r.id, [])
        for m in span:
            lo, hi = bounds[m][0], min(bounds[m][1], now)
            fleet, down = days_in_states(log, state, r.created_at, lo, hi)
            d = days[(code, m)]
            d[0] += fleet
            d[1] += down
        if days_in_states(log, state, r.created_at, m_start, m_end)[0] > 0:
            present[code] += 1

    codes = sorted({code for code, _ in days} | {code for code, _ in costs})
    point = func.ST_PointOnSurface(Gouvernorat.boundary)
    places = {
        code: (ar, fr, lat, lon)
        for code, ar, fr, lat, lon in (
            await session.execute(
                select(
                    Gouvernorat.code, Gouvernorat.name_ar, Gouvernorat.name_fr, func.ST_Y(point), func.ST_X(point)
                ).where(Gouvernorat.code.in_(codes))
            )
        ).all()
    }

    def row(code: int, name: tuple[str, str], pt: list[float] | None, keys: list[int]) -> schemas.FleetReportRow:
        def at(m: str) -> tuple[list[float], list[Decimal], list[int]]:
            fl = [sum(days[(k, m)][0] for k in keys), sum(days[(k, m)][1] for k in keys)]
            co = [sum((costs[(k, m)][i] for k in keys), ZERO) for i in range(3)]
            cn = [sum(counts[(k, m)][i] for k in keys) for i in range(2)]
            return fl, co, cn

        fl, co, cn = at(month)
        total = _money(*co)
        n = sum(present[k] for k in keys)
        series = []
        for m in span:
            mf, mc, _ = at(m)
            series.append(schemas.FleetMonth(month=m, readiness_pct=readiness(*mf), cost_total=_money(*mc)))
        return schemas.FleetReportRow(
            gouvernorat_code=code,
            name_ar=name[0],
            name_fr=name[1],
            point=pt,
            vehicles=n,
            vehicle_days=round(fl[0], 1),
            down_days=round(fl[1], 1),
            readiness_pct=readiness(*fl),
            workshop_entries=cn[0],
            retired=cn[1],
            cost_parts=co[0],
            cost_labour=co[1],
            cost_external=co[2],
            cost_total=total,
            cost_per_vehicle=(total / n).quantize(Decimal("0.001")) if n else None,
            series=series,
        )

    rows = []
    for code in codes:
        ar, fr, lat, lon = places.get(code, (str(code), str(code), None, None))
        rows.append(row(code, (ar, fr), [float(lon), float(lat)] if lat is not None else None, [code]))
    total_row = row(0, ("المجموع", "Total"), None, codes) if len(codes) > 1 else None

    costly = sorted(per_vehicle.items(), key=lambda kv: -Decimal(kv[1][0]))[:5]
    names = {r.id: r for r, _ in vehicles}
    red = await settings.threshold(session, "fleet.readiness_red")
    amber = await settings.threshold(session, "fleet.readiness_amber")
    await session.commit()
    return schemas.FleetReportOut(
        month=month,
        months=span,
        rows=rows,
        total=total_row,
        costly=[
            schemas.FleetCostlyVehicle(
                resource_id=rid,
                label=names[rid].label,
                plate=names[rid].plate,
                gouvernorat_code=owner[rid],
                cost_total=Decimal(v[0]),
                stays=int(v[1]),
            )
            for rid, v in costly
            if Decimal(v[0]) > 0
        ],
        red_below=red,
        amber_below=amber,
        computed_at=now,
    )
