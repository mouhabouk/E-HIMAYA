"""Who handles a report (phase 9 §4): claim and release, the SLA worker, central response, referrals, geo-verification.

* A room claims a report before acting on it (explicitly, or implicitly with its first status change). The regional
  room of the report's gouvernorat claims it; the central room only when the report is late, its location is not
  verified yet or its incident is at central command level.
* The ``sla-escalation`` worker marks unclaimed reports late once their claim delay is over; the central room sees
  them on the late list, may answer the citizen itself, refer the report to a region (optionally with a directive)
  and the region accepts or refuses.
* Reports whose location is not trusted wait in the geo-verification queue; a verifier sets the gouvernorat, and a
  report already claimed by another candidate room is referred to the verified one.

Every step is an ``reports.escalation`` row (actor, time, reason), an audit entry for staff actions, a timeline entry
on the report's incident and a ``report.*`` event.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy import and_, case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.access import ACTION_NOT_ALLOWED, CENTRAL_ROOM, Action, ApiError, Ctx, authorize, require, room_of
from app.core.config import get_settings
from app.core.db import as_system
from app.core.events import emit
from app.core.security import Principal, Role
from app.modules.audit import service as audit
from app.modules.geo.models import Gouvernorat
from app.modules.ops.service import add_timeline
from app.modules.reports import schemas, service, sla
from app.modules.reports.domain import Category, Status
from app.modules.reports.geo import OPEN_GEO_STATES
from app.modules.reports.models import Escalation, Report
from app.modules.settings import service as settings

log = structlog.get_logger()

SLA_ACTOR = "system:sla"
SLA_BATCH = 200
# On the national late list until the central room or a region answers.
LATE_LIST_STATES = ("late", "central_responding", "referred", "referral_refused")
# Timeline kinds (phase 9 §5.5) of the escalation steps.
_TIMELINE_KIND = {
    "late": "report_late",
    "central_claim": "report_central_claim",
    "referral": "report_referred",
    "referral_accepted": "report_referral_accepted",
    "referral_refused": "report_referral_refused",
    "geo_verified": "report_geo_verified",
}
_RELEASERS = frozenset({Role.OPERATOR, Role.OPS_MANAGER, Role.CENTRAL_COMMITTEE})


def _room(code: int | None) -> str:
    return CENTRAL_ROOM if code is None else f"g:{code}"


async def load(session: AsyncSession, principal: Principal, report_id: uuid.UUID) -> tuple[Report, Ctx]:
    """Lock a report the caller may read (404 otherwise) and return it with its access context."""
    report = await session.get(Report, report_id, with_for_update=True)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    ctx = await service.report_ctx(session, report)
    require(await authorize(session, principal, Action.REPORT_READ, ctx))
    return report, ctx


async def _gouvernorats(session: AsyncSession, report: Report, *extra: int | None) -> list[int]:
    codes = set(await service.gouvernorat_codes(session, report))
    codes |= {c for c in extra if c is not None}
    return sorted(codes)


async def _audit(
    session: AsyncSession,
    principal: Principal,
    action: str,
    report: Report,
    gouvernorats: list[int],
    *,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Audit a staff action on a report, tagged with the gouvernorats it concerns (regional audit view, §7)."""
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action=action,
        target=f"report:{report.id}",
        reason=reason,
        details=details,
        gouvernorats=gouvernorats,
    )


async def _step(
    session: AsyncSession,
    report: Report,
    kind: str,
    *,
    actor: str,
    actor_name: str | None,
    from_room: str | None,
    to_room: str | None,
    reason: str | None = None,
    payload: dict[str, Any] | None = None,
) -> Escalation:
    """Record one escalation step and mirror it on the incident timeline."""
    row = Escalation(
        report_id=report.id,
        incident_id=report.incident_id,
        kind=kind,
        from_room=from_room,
        to_room=to_room,
        actor=actor,
        actor_name=actor_name,
        at=datetime.now(UTC),
        reason=reason,
        payload=payload or {},
    )
    session.add(row)
    if report.incident_id is not None and kind in _TIMELINE_KIND:
        add_timeline(
            session,
            report.incident_id,
            _TIMELINE_KIND[kind],
            actor,
            actor_name,
            report_id=str(report.id),
            tracking_code=report.tracking_code,
            from_room=from_room,
            to_room=to_room,
            reason=reason,
        )
    await session.flush()
    return row


async def _announce(session: AsyncSession, subject: str, report: Report, **extra: Any) -> None:
    await session.flush()
    found = await service.staff_summary(session, report.id)
    assert found is not None
    await emit(
        session,
        subject,
        {
            "report": found[0].model_dump(mode="json"),
            "gouvernorat_codes": await service.gouvernorat_codes(session, report),
            **extra,
        },
    )


async def escalations_of(session: AsyncSession, report_id: uuid.UUID) -> list[schemas.EscalationOut]:
    rows = await session.scalars(
        select(Escalation).where(Escalation.report_id == report_id).order_by(Escalation.at, Escalation.id)
    )
    return [
        schemas.EscalationOut(
            kind=r.kind,
            from_room=r.from_room,
            to_room=r.to_room,
            actor_name=r.actor_name,
            at=r.at,
            reason=r.reason,
        )
        for r in rows
    ]


# ---------------------------------------------------------------- claim


async def claim(
    session: AsyncSession, principal: Principal, report: Report, ctx: Ctx, *, implicit: bool = False
) -> bool:
    """Claim ``report`` for the caller's room; False when the room already holds it.

    ``implicit`` (first status change): a room that may not claim gets ``409 claim_required``."""
    room = room_of(principal)
    if report.claimed_room == room:
        return False
    if report.claimed_room is not None:
        raise ApiError(
            status.HTTP_409_CONFLICT,
            "already_claimed",
            claimed_room=report.claimed_room,
            claimed_by_name=report.claimed_by_name,
        )
    decision = await authorize(session, principal, Action.REPORT_CLAIM, ctx)
    if not decision.allowed and implicit and decision.code != ACTION_NOT_ALLOWED:
        raise HTTPException(status.HTTP_409_CONFLICT, "claim_required")
    require(decision)
    now = datetime.now(UTC)
    actor, name = audit.actor_of(principal), audit.name_of(principal)
    report.claimed_room, report.claimed_by, report.claimed_by_name, report.claimed_at = room, actor, name, now
    central = room == CENTRAL_ROOM and report.escalation_state in ("late", "referral_refused")
    if central:
        # The central room takes over the answer to a late report (§4.4).
        report.escalation_state = "central_responding"
        await _step(
            session,
            report,
            "central_claim",
            actor=actor,
            actor_name=name,
            from_room=_room(report.gouvernorat_code),
            to_room=CENTRAL_ROOM,
        )
    gouvernorats = await _gouvernorats(session, report)
    await _audit(
        session,
        principal,
        "report.claim",
        report,
        gouvernorats,
        details={"room": room, "implicit": implicit, "escalation_state": report.escalation_state},
    )
    await _announce(session, "report.claimed", report)
    if central:
        await _announce(session, "report.escalation", report, kind="central_claim", from_room=None, to_room=room)
    return True


async def release(session: AsyncSession, principal: Principal, report_id: uuid.UUID, reason: str) -> None:
    """Give a claim back (ops manager of the claiming room, or national staff). The SLA clock does not restart."""
    report, _ = await load(session, principal, report_id)
    room = report.claimed_room
    if room is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_claimed")
    own_manager = Role.OPS_MANAGER in principal.roles and room == room_of(principal)
    national = principal.is_national and bool(principal.roles & _RELEASERS)
    if not (own_manager or national):
        raise HTTPException(status.HTTP_403_FORBIDDEN, ACTION_NOT_ALLOWED)
    # Releasing may take the report out of the releasing room's view (a candidate room's claim): system scope.
    async with as_system(session):
        actor, name = audit.actor_of(principal), audit.name_of(principal)
        report.claimed_room = report.claimed_by = report.claimed_by_name = None
        report.claimed_at = None
        if report.escalation_state in ("central_responding", "referral_accepted"):
            report.escalation_state = "late"
        await _step(
            session, report, "claim_released", actor=actor, actor_name=name, from_room=room, to_room=None, reason=reason
        )
        await _audit(
            session,
            principal,
            "report.release",
            report,
            await _gouvernorats(session, report),
            reason=reason,
            details={"room": room},
        )
        await _announce(session, "report.escalation", report, kind="claim_released", from_room=room, to_room=None)


async def before_status_change(session: AsyncSession, principal: Principal, report: Report, ctx: Ctx) -> None:
    """A status change needs the caller's room to hold the claim; an unclaimed report is claimed on the way (§4.3)."""
    if report.claimed_room is None:
        await claim(session, principal, report, ctx, implicit=True)
        ctx = await service.report_ctx(session, report)
    elif report.claimed_room != room_of(principal):
        raise ApiError(
            status.HTTP_409_CONFLICT,
            "already_claimed",
            claimed_room=report.claimed_room,
            claimed_by_name=report.claimed_by_name,
        )
    require(await authorize(session, principal, Action.REPORT_STATUS, ctx))


# ---------------------------------------------------------------- referral


async def _check_gouvernorat(session: AsyncSession, code: int) -> None:
    if await session.get(Gouvernorat, code) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_gouvernorat")


async def _directive(
    session: AsyncSession, principal: Principal, code: int, spec: schemas.DirectiveSpec, report: Report
) -> uuid.UUID:
    """A phase 5 directive from the central room to the region a late report is referred to."""
    from app.modules.ops.committee import directive_out
    from app.modules.ops.models import Directive

    directive = Directive(
        title=spec.title,
        body=spec.body,
        urgency=spec.urgency,
        from_level="central",
        gouvernorat_codes=[code],
        issuer_scope=None,
        issued_by=audit.actor_of(principal),
        issued_by_name=audit.name_of(principal),
    )
    session.add(directive)
    await session.flush()
    await session.refresh(directive)
    all_codes = [int(c) for c in await session.scalars(select(Gouvernorat.code).order_by(Gouvernorat.code))]
    out = await directive_out(session, directive, all_codes)
    await audit.record(
        session,
        actor=directive.issued_by,
        action="directive.issue",
        target=f"directive:{directive.id}",
        details={"gouvernorat_codes": [code], "urgency": spec.urgency, "report_id": str(report.id)},
    )
    await emit(session, "directive.issued", {"directive": out.model_dump(mode="json")})
    return directive.id


async def _refer(
    session: AsyncSession,
    principal: Principal,
    report: Report,
    code: int,
    reason: str,
    payload: dict[str, Any] | None = None,
) -> None:
    from_room = report.claimed_room or _room(report.gouvernorat_code)
    report.escalation_state = "referred"
    report.referred_to = code
    report.escalated_at = report.escalated_at or datetime.now(UTC)
    await _step(
        session,
        report,
        "referral",
        actor=audit.actor_of(principal),
        actor_name=audit.name_of(principal),
        from_room=from_room,
        to_room=_room(code),
        reason=reason,
        payload=payload,
    )
    await _audit(
        session,
        principal,
        "report.refer",
        report,
        await _gouvernorats(session, report, code),
        reason=reason,
        details={"from": from_room, "to": _room(code), **(payload or {})},
    )
    await _announce(session, "report.escalation", report, kind="referral", from_room=from_room, to_room=_room(code))


async def refer(session: AsyncSession, principal: Principal, report_id: uuid.UUID, body: schemas.ReferIn) -> None:
    report, ctx = await load(session, principal, report_id)
    require(await authorize(session, principal, Action.REPORT_REFER, ctx))
    await _check_gouvernorat(session, body.to_gouvernorat_code)
    if report.escalation_state == "referred":
        raise HTTPException(status.HTTP_409_CONFLICT, "referral_pending")
    payload: dict[str, Any] = {}
    if body.directive is not None:
        directive_id = await _directive(session, principal, body.to_gouvernorat_code, body.directive, report)
        payload["directive_id"] = str(directive_id)
    await _refer(session, principal, report, body.to_gouvernorat_code, body.reason, payload)


async def decide_referral(
    session: AsyncSession, principal: Principal, report_id: uuid.UUID, *, accept: bool, text_: str | None
) -> None:
    """The referred region accepts (it takes the claim) or refuses (the report stays on the late list)."""
    report, ctx = await load(session, principal, report_id)
    if report.escalation_state != "referred" or report.referred_to is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "referral_not_pending")
    require(await authorize(session, principal, Action.REPORT_REFERRAL_DECIDE, ctx))
    # A refusal hands the report back to central: written with the system scope (row-level security), the row
    # leaving the refusing room's view on purpose.
    async with as_system(session):
        room = _room(report.referred_to)
        actor, name = audit.actor_of(principal), audit.name_of(principal)
        gouvernorats = await _gouvernorats(session, report, report.referred_to)
        if accept:
            kind = "referral_accepted"
            from_room = report.claimed_room or _room(report.gouvernorat_code)
            report.escalation_state = kind
            report.claimed_room, report.claimed_by, report.claimed_by_name = room, actor, name
            report.claimed_at = datetime.now(UTC)
            await _step(
                session, report, kind, actor=actor, actor_name=name, from_room=from_room, to_room=room, reason=text_
            )
        else:
            kind = "referral_refused"
            report.escalation_state = kind
            report.referred_to = None
            await _step(
                session, report, kind, actor=actor, actor_name=name, from_room=room, to_room=CENTRAL_ROOM, reason=text_
            )
        await _audit(session, principal, f"report.{kind}", report, gouvernorats, reason=text_, details={"room": room})
        await _announce(session, "report.escalation", report, kind=kind, from_room=room, to_room=report.claimed_room)


# ---------------------------------------------------------------- geo-verification


async def geo_verify(
    session: AsyncSession, principal: Principal, report_id: uuid.UUID, body: schemas.GeoVerifyIn
) -> None:
    report, ctx = await load(session, principal, report_id)
    require(await authorize(session, principal, Action.REPORT_GEO_VERIFY, ctx))
    if report.geo_state not in OPEN_GEO_STATES:
        raise HTTPException(status.HTTP_409_CONFLICT, "geo_not_pending")
    await _check_gouvernorat(session, body.gouvernorat_code)
    actor, name = audit.actor_of(principal), audit.name_of(principal)
    candidates = list(report.geo_candidates or [])
    report.geo_state = "verified"
    report.gouvernorat_code = body.gouvernorat_code
    report.geo_verified_by, report.geo_verified_at = actor, datetime.now(UTC)
    room = _room(body.gouvernorat_code)
    await _step(
        session,
        report,
        "geo_verified",
        actor=actor,
        actor_name=name,
        from_room=None,
        to_room=room,
        reason=body.reason,
        payload={"candidates": candidates},
    )
    await _audit(
        session,
        principal,
        "report.geo_verify",
        report,
        await _gouvernorats(session, report, *candidates),
        reason=body.reason,
        details={"gouvernorat_code": body.gouvernorat_code, "candidates": candidates},
    )
    await _announce(session, "report.escalation", report, kind="geo_verified", from_room=None, to_room=room)
    claimed = report.claimed_room
    if claimed is not None and claimed not in (room, CENTRAL_ROOM):
        # A candidate room started on it: hand it over to the verified room through a referral.
        await _refer(session, principal, report, body.gouvernorat_code, body.reason, {"after": "geo_verified"})


# ---------------------------------------------------------------- national lists


def _require_national(principal: Principal) -> None:
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "national_scope_required")


async def late_list(
    session: AsyncSession, principal: Principal, gouvernorat: int | None, limit: int, cursor: str | None
) -> tuple[list[schemas.StaffReport], str | None]:
    """Late reports for the central room (§4.4), oldest deadline first."""
    _require_national(principal)
    query = service.staff_query().where(Report.escalation_state.in_(LATE_LIST_STATES))
    if gouvernorat is not None:
        query = query.where(Report.gouvernorat_code == gouvernorat)
    if cursor:
        at, rid, _ = service.decode_cursor(cursor)
        query = query.where(or_(Report.sla_due_at > at, and_(Report.sla_due_at == at, Report.id > rid)))
    rows = (await session.execute(query.order_by(Report.sla_due_at, Report.id).limit(limit))).all()
    items = [service.staff_item(r) for r in rows]
    last = rows[-1][0] if len(rows) == limit else None
    next_cursor = service.encode_cursor(last.sla_due_at, last.id) if last is not None and last.sla_due_at else None
    return items, next_cursor


async def geo_queue(
    session: AsyncSession, principal: Principal, limit: int, cursor: str | None
) -> tuple[list[schemas.StaffReport], str | None]:
    """Open reports whose location waits for a verifier (§4.5): critical first, then by reception."""
    _require_national(principal)
    rank = case((or_(Report.sla_band == "critical", Report.category == Category.SOS.value), 1), else_=0)
    query = service.staff_query().where(Report.geo_state.in_(OPEN_GEO_STATES), Report.status.in_(service.OPEN_STATUSES))
    if cursor:
        at, rid, last_rank = service.decode_cursor(cursor)
        if last_rank is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor")
        later = or_(Report.received_at > at, and_(Report.received_at == at, Report.id > rid))
        query = query.where(or_(rank < last_rank, and_(rank == last_rank, later)))
    rows = (await session.execute(query.order_by(rank.desc(), Report.received_at, Report.id).limit(limit))).all()
    items = [service.staff_item(r) for r in rows]
    next_cursor = None
    if len(rows) == limit:
        last = rows[-1][0]
        next_cursor = service.encode_cursor(last.received_at, last.id, 1 if sla.is_critical(last) else 0)
    return items, next_cursor


# ---------------------------------------------------------------- SLA worker (loop "sla-escalation")


async def refresh_bands(session: AsyncSession, now: datetime) -> int:
    """Follow priority changes of reports still waiting for a claim (AI rescoring) — band and due time."""
    bands, delays = await sla.thresholds(session)
    rows = list(
        await session.scalars(
            select(Report)
            .where(
                Report.status == Status.RECEIVED.value,
                Report.claimed_room.is_(None),
                Report.escalation_state == "none",
            )
            .order_by(Report.sla_due_at)
            .limit(SLA_BATCH * 5)
            .with_for_update(skip_locked=True)
        )
    )
    return sum(1 for report in rows if sla.recompute(report, bands, delays, now))


async def escalate_due(session: AsyncSession, now: datetime | None = None) -> int:
    """One pass: mark late every unclaimed report past its claim deadline (received since ``sla.enforced_since``)."""
    now = now or datetime.now(UTC)
    await refresh_bands(session, now)
    await session.flush()
    since = await settings.enforced_since(session)
    query = (
        select(Report)
        .where(
            Report.status == Status.RECEIVED.value,
            Report.claimed_room.is_(None),
            Report.escalation_state == "none",
            Report.sla_due_at <= now,
        )
        .order_by(Report.sla_due_at)
        .limit(SLA_BATCH)
        .with_for_update(skip_locked=True)
    )
    if since is not None:
        query = query.where(Report.received_at >= since)
    reports = list(await session.scalars(query))
    for report in reports:
        report.escalation_state, report.escalated_at = "late", now
        await _step(
            session,
            report,
            "late",
            actor=SLA_ACTOR,
            actor_name=None,
            from_room=_room(report.gouvernorat_code),
            to_room=CENTRAL_ROOM,
            payload={
                "sla_band": report.sla_band,
                "due_at": report.sla_due_at.isoformat() if report.sla_due_at else None,
            },
        )
        await _announce(session, "report.late", report)
    return len(reports)


async def sla_forever(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    while True:
        try:
            async with sessionmaker() as session, session.begin():
                late = await escalate_due(session)
            if late:
                log.info("sla.late", count=late)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("sla.loop_failed")
        await asyncio.sleep(get_settings().sla_interval_s)
