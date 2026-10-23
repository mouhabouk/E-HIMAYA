"""Location history for 72 hours (phase B2, docs/phase-b/design-b2.md §6, addition 7b §2).

Off by default for each person, and off for the whole platform (setting ``safety.location_history``) until the
Office's legal service approves the 7b text and the processing is declared to the INPDP. When a person turns it on,
with its own consent, the phone sends a position every 5 or 15 minutes; each point is deleted 72 hours after it was
taken, and all of them at once when the person turns it off. An operator reads them only for a missing-person report
they can see, with a reason; each search is audited and the person is told.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, authorize, require
from app.core.config import Settings
from app.core.db import as_system, get_session
from app.core.ratelimit import enforce
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.audit.service import actor_of
from app.modules.identity.models import AccountKind, Consent, Profile, phone_index
from app.modules.identity.service import CurrentReporter, Reporter
from app.modules.notify import outbox
from app.modules.reports import service as reports
from app.modules.reports.schemas import LocationIn
from app.modules.safety.models import LocationHistory, LocationPoint
from app.modules.safety.service import point
from app.modules.settings import domain as settings_domain
from app.modules.settings import service as settings
from app.modules.telephony.domain import normalize_tn_number

router = APIRouter(prefix="/api/v1", tags=["safety"])
staff_router = APIRouter(prefix="/api/v1/staff/safety", tags=["safety"])
Session = Annotated[AsyncSession, Depends(get_session)]
Searcher = Annotated[Principal, Depends(require_roles(Role.OPERATOR, Role.OPS_MANAGER))]

KEEP = timedelta(hours=72)
NOTICE_VERSION = "7b-2026-10"
PURPOSE = "location_history"
MAX_BATCH = 100
_BATCH = 1000


def _now() -> datetime:
    return datetime.now(UTC)


async def available(session: AsyncSession) -> bool:
    return bool(await settings.get(session, settings_domain.SAFETY_LOCATION_HISTORY))


async def _feature_on(session: AsyncSession) -> None:
    if not await available(session):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "feature_off")


def _registered(reporter: Reporter) -> uuid.UUID:
    if reporter.principal is None or reporter.kind is AccountKind.ANONYMOUS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "registration_required")
    return reporter.user_id


class HistoryOut(BaseModel):
    # False: the platform has not turned the feature on yet (the app hides it).
    available: bool
    enabled: bool
    until: datetime | None
    notice_version: str = NOTICE_VERSION


class HistoryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    hours: int = Field(default=72, ge=1, le=72)
    # Required to turn it on: the version of the 7b consent text the person accepted.
    notice_version: str | None = None
    locale: str = Field(default="ar", pattern="^(ar|fr|en)$")
    platform: str = Field(default="android", pattern="^(android|ios)$")


class PointIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: LocationIn
    at: datetime


class PointsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    points: list[PointIn] = Field(min_length=1, max_length=MAX_BATCH)


class PointsOut(BaseModel):
    stored: int


class SearchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=20)]
    report_id: uuid.UUID
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=500)]


class StaffPoint(BaseModel):
    lat: float
    lon: float
    accuracy_m: float | None
    at: datetime


class SearchOut(BaseModel):
    found: bool
    enabled: bool
    points: list[StaffPoint]


async def _state(session: AsyncSession, me: uuid.UUID) -> LocationHistory | None:
    state = await session.get(LocationHistory, me)
    return state if state is not None and state.until > _now() else None


async def _turn_off(session: AsyncSession, me: uuid.UUID) -> None:
    await session.execute(delete(LocationPoint).where(LocationPoint.owner_id == me))
    await session.execute(delete(LocationHistory).where(LocationHistory.owner_id == me))
    consent = await session.scalar(
        select(Consent).where(Consent.user_id == me, Consent.purpose == PURPOSE, Consent.withdrawn_at.is_(None))
    )
    if consent is not None:
        consent.withdrawn_at = _now()


@router.get("/safety/history", response_model=HistoryOut)
async def my_history(reporter: CurrentReporter, session: Session) -> HistoryOut:
    me = _registered(reporter)
    state = await _state(session, me)
    return HistoryOut(available=await available(session), enabled=state is not None, until=state and state.until)


@router.put("/safety/history", response_model=HistoryOut)
async def set_history(reporter: CurrentReporter, session: Session, body: HistoryIn) -> HistoryOut:
    me = _registered(reporter)
    if not body.enabled:
        # Turning it off always works (even with the feature off): every point goes at once.
        await _turn_off(session, me)
        await audit.record(session, actor=reporter.actor, action="safety.history_off", target=f"account:{me}")
        await session.commit()
        return HistoryOut(available=await available(session), enabled=False, until=None)
    await _feature_on(session)
    if body.notice_version != NOTICE_VERSION:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "consent_required")
    until = _now() + timedelta(hours=body.hours)
    state = await session.get(LocationHistory, me)
    if state is None:
        session.add(LocationHistory(owner_id=me, until=until))
    else:
        state.until = until
    consent = await session.scalar(
        select(Consent).where(Consent.user_id == me, Consent.purpose == PURPOSE, Consent.withdrawn_at.is_(None))
    )
    if consent is None:
        session.add(
            Consent(
                user_id=me,
                purpose=PURPOSE,
                charter_version=NOTICE_VERSION,
                locale=body.locale,
                platform=body.platform,
            )
        )
    await audit.record(
        session, actor=reporter.actor, action="safety.history_on", target=f"account:{me}", details={"hours": body.hours}
    )
    await session.commit()
    return HistoryOut(available=True, enabled=True, until=until)


@router.post("/safety/history/points", response_model=PointsOut)
async def add_points(reporter: CurrentReporter, session: Session, body: PointsIn) -> PointsOut:
    me = _registered(reporter)
    await _feature_on(session)
    await enforce(f"safety-history:{me}", 30, 3600)
    state = await _state(session, me)
    if state is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "history_off")
    now = _now()
    stored = 0
    for p in body.points:
        at = p.at if p.at.tzinfo else p.at.replace(tzinfo=UTC)
        # Only points from the period it was on, never in the future and never older than 72 h.
        if at < max(state.started_at, now - KEEP) or at > now + timedelta(minutes=5):
            continue
        session.add(
            LocationPoint(
                owner_id=me,
                at=min(at, now),
                position=point(p.location.lat, p.location.lon, p.location.accuracy_m, min(at, now)),
            )
        )
        stored += 1
    await session.commit()
    return PointsOut(stored=stored)


@router.delete("/safety/history", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history(reporter: CurrentReporter, session: Session) -> Response:
    me = _registered(reporter)
    await _turn_off(session, me)
    await audit.record(session, actor=reporter.actor, action="safety.history_off", target=f"account:{me}")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@staff_router.post("/history/search", response_model=SearchOut)
async def search_history(principal: Searcher, session: Session, body: SearchIn) -> SearchOut:
    """A missing person: the operator gives their phone, the report they handle and a reason. The search is audited
    (even when nothing is found) and the person is told through the app."""
    await _feature_on(session)
    found = await reports.staff_summary(session, body.report_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    _, report = found
    require(await authorize(session, principal, Action.REPORT_READ, await reports.report_ctx(session, report)))
    phone = normalize_tn_number(body.phone)
    if phone is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_phone")
    points: list[StaffPoint] = []
    owner: uuid.UUID | None = None
    enabled = False
    async with as_system(session) as system:
        profile = await system.scalar(select(Profile).where(Profile.phone_hash == phone_index(phone)))
        if profile is not None:
            owner = profile.user_id
            enabled = await _state(system, owner) is not None
            rows = await system.scalars(
                select(LocationPoint)
                .where(LocationPoint.owner_id == owner, LocationPoint.at > _now() - KEEP)
                .order_by(LocationPoint.at)
            )
            points = [StaffPoint.model_validate(r.position) for r in rows]
            if points:
                outbox.push(system, owner, "safety_history_viewed", {"report_id": str(report.id)})
    await audit.record(
        session,
        actor=actor_of(principal),
        action="safety.history_search",
        target=f"account:{owner}" if owner else None,
        reason=body.reason,
        details={"report": str(report.id), "points": len(points), "found": owner is not None},
        gouvernorats=await reports.gouvernorat_codes(session, report),
    )
    await session.commit()
    return SearchOut(found=owner is not None, enabled=enabled, points=points)


# ---------------------------------------------------------------- retention and erasure


async def purge_points(session: AsyncSession, settings_: Settings, now: datetime) -> int:
    """Points older than 72 hours; ended histories (their points went with the 72 h rule or at turn-off)."""
    ids = list(await session.scalars(select(LocationPoint.id).where(LocationPoint.at < now - KEEP).limit(_BATCH)))
    if ids:
        await session.execute(delete(LocationPoint).where(LocationPoint.id.in_(ids)))
    ended = (await session.execute(delete(LocationHistory).where(LocationHistory.until < now - KEEP))).rowcount  # type: ignore[attr-defined]
    return len(ids) + int(ended or 0)


async def forget(session: AsyncSession, user_id: uuid.UUID) -> int:
    await session.execute(delete(LocationHistory).where(LocationHistory.owner_id == user_id))
    return int((await session.execute(delete(LocationPoint).where(LocationPoint.owner_id == user_id))).rowcount)  # type: ignore[attr-defined]
