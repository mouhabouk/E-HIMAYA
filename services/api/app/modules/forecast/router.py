"""Spread forecast endpoints of an incident (docs/api/phase-7-contract.md §2). Geographic scope like incidents
(404 out of scope); every run is audited and stored with its inputs and assumptions."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.ratelimit import enforce, opaque
from app.core.security import Principal, require_roles
from app.modules.audit import service as audit
from app.modules.forecast import schemas, service
from app.modules.ops import service as incidents
from app.modules.reports.staff_router import READ_ROLES

router = APIRouter(prefix="/api/v1/staff/incidents", tags=["staff", "forecast"])
Session = Annotated[AsyncSession, Depends(get_session)]
StaffReader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
RUNS_LIMIT, RUNS_WINDOW_S = 30, 600


async def _limit(principal: Principal) -> None:
    await enforce(f"forecast:{opaque(principal.subject)}", RUNS_LIMIT, RUNS_WINDOW_S)


@router.post(
    "/{incident_id}/forecast/fire", response_model=schemas.FireForecastOut, status_code=status.HTTP_201_CREATED
)
async def fire_forecast(
    principal: StaffReader, session: Session, incident_id: uuid.UUID, body: schemas.FireForecastIn | None = None
) -> schemas.FireForecastOut:
    await _limit(principal)
    incident = await incidents.get_in_scope(session, principal, incident_id)
    actor = audit.actor_of(principal)
    out = await service.fire(session, incident, body or schemas.FireForecastIn(), actor)
    await audit.record(
        session,
        actor=actor,
        action="forecast.fire",
        target=f"incident:{incident_id}",
        details={
            "forecast_id": str(out.forecast_id),
            "fuel": out.inputs["fuel"]["key"],
            "rate_of_spread_m_min": out.rate_of_spread_m_min,
        },
    )
    await session.commit()
    return out


@router.post(
    "/{incident_id}/forecast/flood", response_model=schemas.FloodForecastOut, status_code=status.HTTP_201_CREATED
)
async def flood_forecast(principal: StaffReader, session: Session, incident_id: uuid.UUID) -> schemas.FloodForecastOut:
    await _limit(principal)
    incident = await incidents.get_in_scope(session, principal, incident_id)
    actor = audit.actor_of(principal)
    out = await service.flood_advisory(session, incident, actor)
    await audit.record(
        session,
        actor=actor,
        action="forecast.flood",
        target=f"incident:{incident_id}",
        details={"forecast_id": str(out.forecast_id), "level": out.level},
    )
    await session.commit()
    return out


@router.get("/{incident_id}/forecasts")
async def list_forecasts(
    principal: StaffReader,
    session: Session,
    incident_id: uuid.UUID,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> dict[str, Any]:
    """The latest runs of the incident, newest first (the map shows them; POST again to refresh)."""
    incident = await incidents.get_in_scope(session, principal, incident_id)
    return {"items": await service.runs(session, incident, limit)}
