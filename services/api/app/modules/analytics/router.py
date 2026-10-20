"""Dashboard analytics (docs/api/phase-8-contract.md §1, FR-C-01, FR-C-12): overview, trends, hotspots, what-if.

Scope first: a regional staff member's queries cover their own gouvernorat only (403 ``out_of_scope`` for another),
national roles see all. Aggregates only, never a person.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import ratelimit
from app.core.config import get_settings
from app.core.db import get_session
from app.core.security import Principal, require_roles
from app.modules.analytics import domain, scenario, schemas, service
from app.modules.analytics.models import Notification, Scenario
from app.modules.audit import service as audit
from app.modules.reports.domain import Category

router = APIRouter(prefix="/api/v1/staff/analytics", tags=["staff", "analytics"])
Session = Annotated[AsyncSession, Depends(get_session)]
Reader = Annotated[Principal, Depends(require_roles(*domain.READ_ROLES))]
Planner = Annotated[Principal, Depends(require_roles(*domain.PLANNER_ROLES))]
HOUR_S = 3600


def _codes(gouvernorat: int | None) -> list[int] | None:
    return [gouvernorat] if gouvernorat is not None else None


@router.get("/overview", response_model=schemas.Overview, response_model_by_alias=True)
async def overview(
    principal: Reader,
    session: Session,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
    category: Category | None = None,
) -> schemas.Overview:
    codes = service.resolve_scope(principal, _codes(gouvernorat))
    start, end = service.period(from_, to, service.DEFAULT_SPAN["day"])
    return await service.overview(session, codes, category.value if category else None, start, end)


@router.get("/trends", response_model=schemas.Trend, response_model_by_alias=True)
async def trends(
    principal: Reader,
    session: Session,
    metric: service.Metric = "reports",
    interval: service.Interval = "day",
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
    category: Category | None = None,
) -> schemas.Trend:
    codes = service.resolve_scope(principal, _codes(gouvernorat))
    start, end = service.period(from_, to, service.DEFAULT_SPAN[interval])
    return await service.trends(session, codes, category.value if category else None, metric, interval, start, end)


@router.get("/hotspots")
async def hotspots(
    principal: Reader,
    session: Session,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
    category: Category | None = None,
    size_km: Annotated[float, Query(ge=service.HEX_MIN_KM, le=service.HEX_MAX_KM)] = 5.0,
) -> dict[str, Any]:
    """GeoJSON hexagon grid with report counts (never single points)."""
    codes = service.resolve_scope(principal, _codes(gouvernorat))
    start, end = service.period(from_, to, service.DEFAULT_SPAN["day"])
    return await service.hotspots(session, codes, category.value if category else None, start, end, size_km)


# ---------------------------------------------------------------- what-if scenarios


def _scenario_out(row: Scenario, full: bool = True) -> schemas.ScenarioOut:
    result = row.result
    if result is not None and not full:
        result = {k: v for k, v in result.items() if k != "hours"}
    return schemas.ScenarioOut(
        id=row.id,
        name=row.name,
        status=row.status,
        seed=row.seed,
        runs=row.runs,
        gouvernorats=list(row.gouvernorats),
        category=row.category,
        params=row.params,
        result=result,
        error=row.error,
        created_by=row.created_by,
        created_at=row.created_at,
    )


def _scenario_visible(principal: Principal) -> Any:
    if principal.is_national:
        return True
    return and_(
        func.cardinality(Scenario.gouvernorats) > 0, Scenario.gouvernorats.contained_by([principal.gouvernorat_code])
    )


@router.post("/scenarios", response_model=schemas.ScenarioOut, status_code=status.HTTP_201_CREATED)
async def create_scenario(principal: Planner, session: Session, body: schemas.ScenarioIn) -> schemas.ScenarioOut:
    """Run a what-if scenario now (seeded Monte Carlo, at least 200 runs) and keep it."""
    settings = get_settings()
    await ratelimit.enforce(f"an-scn:{principal.subject}", settings.analytics_scenarios_per_hour, HOUR_S)
    codes = service.resolve_scope(principal, body.gouvernorats)
    body.gouvernorats = codes
    names = await service.gouvernorat_names(session)
    if any(c not in names for c in codes):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown_gouvernorat")
    runs = settings.analytics_scenario_runs
    seed, result = await scenario.run(session, body, runs, names)
    params = body.model_dump(mode="json")
    params["seed"] = seed
    row = Scenario(
        name=body.name,
        gouvernorats=codes,
        category=body.category.value if body.category else None,
        params=params,
        seed=seed,
        runs=runs,
        status="done",
        result=result,
        creator_scope=principal.gouvernorat_code,
        created_by=audit.actor_of(principal),
    )
    session.add(row)
    await session.flush()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="analytics.scenario.run",
        target=f"analytics_scenario:{row.id}",
        details={"gouvernorats": codes, "category": row.category, "seed": seed, "runs": runs},
    )
    await session.refresh(row)
    out = _scenario_out(row)
    await session.commit()
    return out


@router.get("/scenarios", response_model=schemas.ScenarioPage)
async def scenarios(
    principal: Planner,
    session: Session,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> schemas.ScenarioPage:
    query = select(Scenario).where(_scenario_visible(principal))
    if cursor:
        at, raw_id = service.decode_cursor(cursor)
        try:
            sid = uuid.UUID(raw_id)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc
        query = query.where(or_(Scenario.created_at < at, and_(Scenario.created_at == at, Scenario.id < sid)))
    rows = list(await session.scalars(query.order_by(Scenario.created_at.desc(), Scenario.id.desc()).limit(limit)))
    next_cursor = service.encode_cursor(rows[-1].created_at, rows[-1].id) if len(rows) == limit else None
    return schemas.ScenarioPage(items=[_scenario_out(r, full=False) for r in rows], next_cursor=next_cursor)


@router.get("/scenarios/{scenario_id}", response_model=schemas.ScenarioOut)
async def get_scenario(principal: Planner, session: Session, scenario_id: uuid.UUID) -> schemas.ScenarioOut:
    row = await session.scalar(select(Scenario).where(Scenario.id == scenario_id, _scenario_visible(principal)))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return _scenario_out(row)


# ---------------------------------------------------------------- in-app notifications of staff members


@router.get("/notifications", response_model=schemas.NotificationPage)
async def notifications(
    principal: Reader,
    session: Session,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> schemas.NotificationPage:
    """The caller's notifications (reports of the repository that are ready or failed), newest first."""
    query = select(Notification).where(Notification.recipient == principal.subject)
    if cursor:
        try:
            query = query.where(Notification.id < int(cursor))
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc
    rows = list(await session.scalars(query.order_by(Notification.id.desc()).limit(limit)))
    unread = await session.scalar(
        select(func.count()).where(Notification.recipient == principal.subject, Notification.read_at.is_(None))
    )
    return schemas.NotificationPage(
        items=[schemas.NotificationOut.model_validate(n, from_attributes=True) for n in rows],
        next_cursor=str(rows[-1].id) if len(rows) == limit else None,
        unread=int(unread or 0),
    )


@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(principal: Reader, session: Session, notification_id: int) -> None:
    result = await session.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.recipient == principal.subject)
        .values(read_at=func.coalesce(Notification.read_at, datetime.now(UTC)))
        .returning(Notification.id)
    )
    if result.scalar() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await session.commit()
