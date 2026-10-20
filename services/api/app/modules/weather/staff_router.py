"""Dashboard endpoints of the weather layer (docs/api/phase-7-contract.md §1).

Weather values are national (not personal data, any staff role reads them); suggested alerts are scoped by
gouvernorat like alerts. Accepting a suggestion never sends anything: it returns the phase 5 alert form prefilled,
and the alert goes out only through the existing alert endpoints after human review.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.notify import service as notify
from app.modules.notify.schemas import MessageIn
from app.modules.reports.domain import LAT_MAX, LAT_MIN, LON_MAX, LON_MIN
from app.modules.reports.staff_router import READ_ROLES
from app.modules.weather import schemas, service
from app.modules.weather.models import AlertSuggestion, Rule

router = APIRouter(prefix="/api/v1/staff/weather", tags=["staff", "weather"])
Session = Annotated[AsyncSession, Depends(get_session)]
EDITOR_ROLES = (Role.CONTENT_EDITOR, Role.OPS_MANAGER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE)
RULE_ROLES = (Role.OPS_MANAGER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE)
# Technical roles hold no operational data (phase 9 §1.1): sysadmin no longer reads the weather picture.
StaffReader = Annotated[Principal, Depends(require_roles(*READ_ROLES, *EDITOR_ROLES))]
Editor = Annotated[Principal, Depends(require_roles(*EDITOR_ROLES))]
RuleEditor = Annotated[Principal, Depends(require_roles(*RULE_ROLES))]
HOURS_AHEAD = 48


def _parse_bbox(raw: str | None) -> tuple[float, float, float, float] | None:
    if raw is None:
        return None
    try:
        min_lon, min_lat, max_lon, max_lat = (float(v) for v in raw.split(","))
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_bbox") from exc
    if min_lon >= max_lon or min_lat >= max_lat:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_bbox")
    return min_lon, min_lat, max_lon, max_lat


@router.get("/grid")
async def grid(
    principal: StaffReader,
    session: Session,
    bbox: Annotated[str | None, Query(description="min_lon,min_lat,max_lon,max_lat")] = None,
    hour: Annotated[int, Query(ge=-24, le=HOURS_AHEAD, description="hours from the current hour")] = 0,
) -> dict[str, Any]:
    """GeoJSON FeatureCollection of the grid points at one hour (map layer)."""
    at = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=hour)
    features = await service.grid_features(session, _parse_bbox(bbox), at)
    simulated = any(f["properties"]["simulated"] for f in features)
    return {
        "type": "FeatureCollection",
        "hour": at.isoformat(),
        "features": features,
        "attribution": service.attribution(simulated),
        "simulated": simulated,
    }


@router.get("/at", response_model=schemas.PointDetail)
async def at_point(
    principal: StaffReader,
    session: Session,
    lat: Annotated[float, Query(ge=LAT_MIN, le=LAT_MAX)],
    lon: Annotated[float, Query(ge=LON_MIN, le=LON_MAX)],
) -> schemas.PointDetail:
    point = await service.nearest_point(session, lat, lon)
    if point is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_weather_data")
    now = datetime.now(UTC)
    hour = now.replace(minute=0, second=0, microsecond=0)
    rows = await service.series_of(session, point.id, hour - timedelta(hours=24), hour + timedelta(hours=HOURS_AHEAD))
    current = service.current_of(rows, now)
    if current is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_weather_data")
    return schemas.PointDetail(
        point=schemas.PointInfo(
            id=point.id,
            lat=point.lat,
            lon=point.lon,
            gouvernorat_code=point.gouvernorat_code,
            distance_km=service.distance_km(lat, lon, point.lat, point.lon),
        ),
        lat=point.lat,
        lon=point.lon,
        updated_at=point.fetched_at,
        current=service.hour_out(current),
        past=[service.hour_out(o) for o in rows if o.at < current.at],
        hourly=[service.hour_out(o) for o in rows if o.at > current.at],
        alerts=[a for a in await notify.active_alerts(session, lat, lon, None) if a.category == "weather"],
        attribution=service.attribution(point.simulated),
        simulated=point.simulated,
    )


# ---------------------------------------------------------------- suggested alerts


@router.get("/suggestions", response_model=schemas.SuggestionPage)
async def suggestions(
    principal: Editor,
    session: Session,
    status_: Annotated[
        Literal["pending", "accepted", "dismissed", "expired", "all"], Query(alias="status")
    ] = "pending",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> schemas.SuggestionPage:
    query = select(AlertSuggestion).where(service.suggestion_visible(principal))
    if status_ != "all":
        query = query.where(AlertSuggestion.status == status_)
    rows = await session.scalars(query.order_by(AlertSuggestion.created_at.desc()).limit(limit))
    return schemas.SuggestionPage(items=[service.suggestion_out(s) for s in rows])


async def _pending(session: AsyncSession, principal: Principal, suggestion_id: uuid.UUID) -> AlertSuggestion:
    suggestion = await session.scalar(
        select(AlertSuggestion)
        .where(AlertSuggestion.id == suggestion_id, service.suggestion_visible(principal))
        .with_for_update()
    )
    if suggestion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if suggestion.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "suggestion_not_pending")
    return suggestion


@router.post("/suggestions/{suggestion_id}/accept", response_model=schemas.AcceptOut)
async def accept(principal: Editor, session: Session, suggestion_id: uuid.UUID) -> schemas.AcceptOut:
    suggestion = await _pending(session, principal, suggestion_id)
    now = datetime.now(UTC)
    suggestion.status, suggestion.decided_by, suggestion.decided_at = "accepted", audit.actor_of(principal), now
    suggestion.updated_at = now
    codes = list(suggestion.gouvernorat_codes)
    if not principal.is_national:
        # A local editor's alert covers their own gouvernorat only (the alert endpoint enforces it again).
        codes = [c for c in codes if c == principal.gouvernorat_code]
    form = MessageIn.model_validate(
        {
            "kind": "alert",
            "title": suggestion.title,
            "body": suggestion.body,
            "channels": ["push"],
            "severity": suggestion.severity,
            "category": "weather",
            "hazard": suggestion.hazard,
            "expires_at": max(suggestion.valid_until, now + timedelta(hours=1)),
            "area": {"gouvernorat_codes": codes},
        }
    )
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="weather.suggestion.accept",
        target=f"weather_suggestion:{suggestion_id}",
        details={"metric": suggestion.metric, "gouvernorat_codes": codes},
    )
    out = schemas.AcceptOut(suggestion=service.suggestion_out(suggestion), alert_form=form.model_dump(mode="json"))
    await session.commit()
    return out


@router.post("/suggestions/{suggestion_id}/dismiss", response_model=schemas.SuggestionOut)
async def dismiss(
    principal: Editor, session: Session, suggestion_id: uuid.UUID, body: schemas.DismissIn
) -> schemas.SuggestionOut:
    suggestion = await _pending(session, principal, suggestion_id)
    now = datetime.now(UTC)
    suggestion.status, suggestion.decided_by, suggestion.decided_at = "dismissed", audit.actor_of(principal), now
    suggestion.dismiss_reason, suggestion.updated_at = body.reason, now
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="weather.suggestion.dismiss",
        target=f"weather_suggestion:{suggestion_id}",
        reason=body.reason,
        details={"metric": suggestion.metric},
    )
    out = service.suggestion_out(suggestion)
    await session.commit()
    return out


# ---------------------------------------------------------------- threshold rules


def _rule_out(rule: Rule) -> schemas.RuleOut:
    return schemas.RuleOut.model_validate(rule, from_attributes=True)


@router.get("/rules", response_model=list[schemas.RuleOut])
async def rules(principal: StaffReader, session: Session) -> list[schemas.RuleOut]:
    return [_rule_out(r) for r in await service.rules_list(session, principal)]


@router.put("/rules", response_model=list[schemas.RuleOut])
async def set_rules(principal: RuleEditor, session: Session, body: schemas.RulesIn) -> list[schemas.RuleOut]:
    """Replace the rules of one scope: the national rules (national roles) or one gouvernorat's own rules (which
    override the national rule of the same metric there; an empty list returns the gouvernorat to the national
    rules)."""
    if body.gouvernorat_code is None:
        if not principal.is_national or not principal.roles & {Role.CENTRAL_COMMITTEE, Role.OPS_MANAGER}:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
        if {r.metric for r in body.rules} != set(service.METRICS):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "national_rules_incomplete")
    elif not principal.can_access_gouvernorat(body.gouvernorat_code):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
    metrics = [r.metric for r in body.rules]
    if len(set(metrics)) != len(metrics):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "duplicate_metric")
    if any(r.metric == "fire_danger" and (r.threshold > 4 or r.threshold != int(r.threshold)) for r in body.rules):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_threshold")
    scope = (
        Rule.gouvernorat_code.is_(None)
        if body.gouvernorat_code is None
        else (Rule.gouvernorat_code == body.gouvernorat_code)
    )
    actor = audit.actor_of(principal)
    await session.execute(delete(Rule).where(scope))
    for r in body.rules:
        session.add(
            Rule(
                gouvernorat_code=body.gouvernorat_code,
                metric=r.metric,
                threshold=r.threshold,
                severity=r.severity,
                enabled=r.enabled,
                updated_by=actor,
            )
        )
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action="weather.rules.update",
        target=f"weather_rules:{body.gouvernorat_code or 'national'}",
        details={"rules": [r.model_dump() for r in body.rules]},
    )
    out = [_rule_out(r) for r in await service.rules_list(session, principal)]
    await session.commit()
    return out
