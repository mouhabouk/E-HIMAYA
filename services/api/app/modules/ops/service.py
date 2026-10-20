"""Incidents: one field event grouping several reports (FR-C-02, BR-10, BR-11).

The AI suggests which reports belong together; operators confirm, link, split (detach) and merge.
Every change is written to the incident timeline and the audit log, and the scores of the reports
involved are refreshed (the number of reporters is a priority component, BR-20).

Phase 9 (§5): an incident has one **lead** gouvernorat, fixed at creation from its first report's trusted location
and changed only by an audited transfer (``POST /incidents/{id}/lead``), and participating gouvernorats: linking a
report of another gouvernorat makes that gouvernorat a participant, never the owner. A cross-border event therefore
stays one incident file; ``action: new`` next to an open incident of a compatible type answers
``409 possible_duplicate`` unless the operator gives a reason. The command level (regional or central) follows the
severity, the participants and the lead's operational level unless central command set it by hand.
"""

import base64
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from geoalchemy2 import Geography, Geometry
from sqlalchemy import and_, cast, exists, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, ApiError
from app.core.events import emit
from app.core.security import Principal
from app.modules.access.grants import active_grants
from app.modules.ai import pipeline
from app.modules.ai.models import Analysis
from app.modules.ai.settings import load as load_ai_settings
from app.modules.ops import schemas, scope
from app.modules.ops.domain import ACTIVE_ASSIGNMENT
from app.modules.ops.levels import level_of
from app.modules.ops.models import (
    Assignment,
    Callout,
    Incident,
    IncidentGouvernorat,
    OpLevel,
    Resource,
    TimelineEvent,
    Unit,
)
from app.modules.reports.domain import Category, Status
from app.modules.reports.models import Report

FINAL_REPORT_STATUSES = (Status.CLOSED.value, Status.REJECTED.value)
COMMAND_LEVELS = ("regional", "central")
# Default lower bound of the critical SLA band (platform setting ``sla.bands``) when the setting cannot be read.
DEFAULT_CRITICAL_BAND = 85


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "not_found")


async def incident_gouvernorats(session: AsyncSession, incident_id: uuid.UUID) -> tuple[int | None, frozenset[int]]:
    """(lead gouvernorat, participating gouvernorats) of an incident (frozen interface, §11)."""
    return await scope.gouvernorats_of(session, incident_id)


async def all_gouvernorats(session: AsyncSession, incident_id: uuid.UUID) -> list[int]:
    """Lead and participants together, sorted (live payloads, audit scope, knowledge)."""
    lead, participants = await incident_gouvernorats(session, incident_id)
    return sorted(participants | ({lead} if lead is not None else set()))


async def visible_ids_filter(session: AsyncSession, principal: Principal) -> Any:
    """SQL condition on ``Incident`` for the incidents a staff member may read: national all; a region those it leads
    or participates in, and those an active break-glass grant covers."""
    if principal.is_national:
        return True
    code = principal.gouvernorat_code
    conditions: list[Any] = [
        Incident.gouvernorat_code == code,
        exists().where(IncidentGouvernorat.incident_id == Incident.id, IncidentGouvernorat.gouvernorat_code == code),
    ]
    grants = await active_grants(session, principal.subject)
    incident_ids = [g.target_id for g in grants if g.target_kind == "incident" and g.target_id is not None]
    report_ids = [g.target_id for g in grants if g.target_kind == "report" and g.target_id is not None]
    codes = [g.gouvernorat_code for g in grants if g.target_kind == "gouvernorat" and g.gouvernorat_code is not None]
    if incident_ids:
        conditions.append(Incident.id.in_(incident_ids))
    if report_ids:
        conditions.append(Incident.id.in_(select(Report.incident_id).where(Report.id.in_(report_ids))))
    if codes:
        conditions.append(Incident.gouvernorat_code.in_(codes))
    return or_(*conditions)


async def _members(session: AsyncSession, incident_id: uuid.UUID) -> list[Report]:
    return list(
        await session.scalars(select(Report).where(Report.incident_id == incident_id).order_by(Report.received_at))
    )


async def summary(session: AsyncSession, incident: Incident) -> schemas.IncidentSummary:
    members = await _members(session, incident.id)
    point = None
    if incident.centroid is not None:
        row = (
            await session.execute(
                select(
                    func.ST_Y(cast(Incident.centroid, Geometry)), func.ST_X(cast(Incident.centroid, Geometry))
                ).where(Incident.id == incident.id)
            )
        ).one()
        point = schemas.Point(lat=float(row[0]), lon=float(row[1]))
    active = await session.scalar(
        select(func.count()).where(Assignment.incident_id == incident.id, Assignment.status.in_(ACTIVE_ASSIGNMENT))
    )
    callouts = await session.scalar(
        select(func.count()).where(Callout.incident_id == incident.id, Callout.status == "open")
    )
    _, participants = await incident_gouvernorats(session, incident.id)
    return schemas.IncidentSummary(
        title=incident.title,
        classification=incident.classification,
        op_level=incident.op_level,
        assignments_active=int(active or 0),
        callouts_open=int(callouts or 0),
        id=incident.id,
        category=Category(incident.category),
        status=incident.status,
        gouvernorat_code=incident.gouvernorat_code,
        lead_gouvernorat_code=incident.gouvernorat_code,
        participating_gouvernorats=sorted(participants),
        command_level=incident.command_level,
        command_level_manual=incident.command_level_manual,
        centroid=point,
        severity=incident.severity,
        report_count=len(members),
        reporter_count=len({m.user_id for m in members}),
        opened_at=incident.opened_at,
        updated_at=incident.updated_at,
        closed_at=incident.closed_at,
        merged_into=incident.merged_into,
    )


def add_timeline(
    session: AsyncSession,
    incident_id: uuid.UUID,
    kind: str,
    actor: str,
    /,
    actor_name: str | None = None,
    **payload: Any,
) -> TimelineEvent:
    """Append a timeline entry (frozen interface, §5.5). The entry shows the actor's display name when known; the
    technical actor id is kept in the payload. ``reason`` goes in the payload when there is one."""
    if actor_name:
        payload["actor_id"] = actor
    event = TimelineEvent(incident_id=incident_id, kind=kind, actor=actor_name or actor, payload=payload)
    session.add(event)
    return event


async def _timeline(session: AsyncSession, incident: Incident, kind: str, actor: str, /, **payload: Any) -> None:
    add_timeline(session, incident.id, kind, actor, **payload)


# ---------------------------------------------------------------- lead, participants and command level


async def add_participant(
    session: AsyncSession,
    incident: Incident,
    code: int,
    actor: str,
    reason: str,
    actor_name: str | None = None,
) -> bool:
    """Make ``code`` a participating gouvernorat (no-op for the lead or an existing participant)."""
    if code == incident.gouvernorat_code:
        return False
    inserted = await session.execute(
        insert(IncidentGouvernorat)
        .values(incident_id=incident.id, gouvernorat_code=code, role="participating", added_by=actor, reason=reason)
        .on_conflict_do_nothing()
        .returning(IncidentGouvernorat.gouvernorat_code)
    )
    if inserted.first() is None:
        return False
    add_timeline(session, incident.id, "participant_added", actor, actor_name, gouvernorat_code=code, reason=reason)
    return True


async def _has_activity(session: AsyncSession, incident_id: uuid.UUID, code: int) -> bool:
    """Member reports of the gouvernorat, or active assignments of its units."""
    reports = await session.scalar(
        select(func.count()).where(Report.incident_id == incident_id, Report.gouvernorat_code == code)
    )
    assignments = await session.scalar(
        select(func.count())
        .select_from(Assignment)
        .join(Resource, Resource.id == Assignment.resource_id)
        .join(Unit, Unit.id == Resource.unit_id)
        .where(
            Assignment.incident_id == incident_id,
            Assignment.status.in_(ACTIVE_ASSIGNMENT),
            Unit.gouvernorat_code == code,
        )
    )
    return bool(reports or assignments)


async def remove_participant(
    session: AsyncSession, incident: Incident, code: int, actor: str, actor_name: str | None, reason: str
) -> None:
    row = await session.get(IncidentGouvernorat, (incident.id, code), with_for_update=True)
    if row is None or row.role != "participating":
        raise _not_found()
    if await _has_activity(session, incident.id, code):
        raise HTTPException(status.HTTP_409_CONFLICT, "participant_active")
    await session.delete(row)
    add_timeline(session, incident.id, "participant_removed", actor, actor_name, gouvernorat_code=code, reason=reason)
    await session.flush()


async def valid_gouvernorat(session: AsyncSession, code: int) -> None:
    found = await session.scalar(text("SELECT count(*) FROM geo.gouvernorat WHERE code = :c"), {"c": code})
    if not found:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_gouvernorat")


async def transfer_lead(
    session: AsyncSession, incident: Incident, code: int, actor: str, actor_name: str | None, reason: str
) -> None:
    """Central command moves the lead; the previous lead keeps participating (database trigger)."""
    await valid_gouvernorat(session, code)
    previous = incident.gouvernorat_code
    if previous == code:
        return
    incident.gouvernorat_code = code
    incident.lead_set_by, incident.lead_set_at = actor, datetime.now(UTC)
    incident.updated_at = datetime.now(UTC)
    await session.flush()
    session.expire(incident)
    await session.refresh(incident)
    add_timeline(
        session, incident.id, "lead_transferred", actor, actor_name, **{"from": previous, "to": code}, reason=reason
    )
    if incident.status == "open":
        incident.op_level = await level_of(session, code)
    await update_command_level(session, incident, actor)


async def critical_band(session: AsyncSession) -> int:
    """Lower bound of the critical SLA band (platform setting ``sla.bands``, phase 9 §2)."""
    from app.modules.settings import service as settings

    bands = await settings.get(session, "sla.bands")
    try:
        return int(bands["critical"])
    except (KeyError, TypeError, ValueError):
        return DEFAULT_CRITICAL_BAND


async def automatic_level(session: AsyncSession, incident: Incident) -> tuple[str, str]:
    """(level, reason) of the §5.3 rule."""
    _, participants = await incident_gouvernorats(session, incident.id)
    if incident.gouvernorat_code is None:
        return "central", "no_lead"
    if participants:
        return "central", "multi_gouvernorat"
    if await level_of(session, incident.gouvernorat_code) in (OpLevel.CRISIS, OpLevel.DISASTER):
        return "central", "lead_level"
    if incident.severity is not None and incident.severity >= await critical_band(session):
        return "central", "severity"
    return "regional", "automatic"


async def update_command_level(session: AsyncSession, incident: Incident, actor: str) -> bool:
    """Recompute the automatic command level (not while it is set by hand). Returns True when it changed."""
    if incident.command_level_manual or incident.status not in ("open", "closed"):
        return False
    level, reason = await automatic_level(session, incident)
    if level == incident.command_level:
        return False
    previous = incident.command_level
    incident.command_level, incident.command_level_reason = level, reason
    add_timeline(session, incident.id, "command_level_changed", actor, **{"from": previous, "to": level}, reason=reason)
    await session.flush()
    return True


async def set_command_level(
    session: AsyncSession, incident: Incident, level: str | None, actor: str, actor_name: str | None, reason: str
) -> None:
    """Central command sets the level by hand; ``None`` returns to the automatic rule."""
    previous = incident.command_level
    if level is None:
        incident.command_level_manual = False
        new_level, _ = await automatic_level(session, incident)
    else:
        incident.command_level_manual = True
        new_level = level
    incident.command_level, incident.command_level_reason = new_level, reason
    incident.updated_at = datetime.now(UTC)
    add_timeline(
        session,
        incident.id,
        "command_level_changed",
        actor,
        actor_name,
        **{"from": previous, "to": new_level},
        manual=level is not None,
        reason=reason,
    )
    await session.flush()


async def after_geo_verified(session: AsyncSession, report: Report, actor: str) -> None:
    """A report's location was verified (§4.5): an incident still without lead takes it; another one gains it as a
    participant. Called by the reports module after ``geo-verify``."""
    if report.incident_id is None or report.gouvernorat_code is None:
        return
    incident = await session.get(Incident, report.incident_id, with_for_update=True)
    if incident is not None:
        await refresh(session, incident, actor)


# ---------------------------------------------------------------- grouping


async def refresh(session: AsyncSession, incident: Incident, actor: str = "system") -> None:
    """Recompute what derives from the member reports: place, type, severity, open or closed; participants.

    The lead gouvernorat is **not** recomputed (phase 9): it is set once, from the first located report when the
    incident had none, and changed only by a transfer."""
    await session.flush()
    members = await _members(session, incident.id)
    now = datetime.now(UTC)
    incident.updated_at = now
    if incident.status == "merged":
        return
    if not members:
        incident.status, incident.closed_at = "dissolved", now
        await _timeline(session, incident, "dissolved", actor)
        return
    categories = Counter(m.category for m in members if m.category != Category.SOS.value)
    incident.category = categories.most_common(1)[0][0] if categories else Category.SOS.value
    located = [m.gouvernorat_code for m in members if m.gouvernorat_code is not None]
    if incident.gouvernorat_code is None and located:
        incident.gouvernorat_code = located[0]
        incident.lead_set_by, incident.lead_set_at = actor, now
        await session.flush()
        payload: dict[str, Any] = {"from": None, "to": located[0]}
        add_timeline(session, incident.id, "lead_transferred", actor, **payload)
    for code in dict.fromkeys(located):
        await add_participant(session, incident, code, actor, "report_linked")
    incident.severity = max((m.priority_score or 0) for m in members)
    if incident.status == "open":
        incident.op_level = await level_of(session, incident.gouvernorat_code)
    incident.centroid = (
        select(cast(func.ST_Centroid(func.ST_Collect(cast(Report.location, Geometry))), Geography(srid=4326)))
        .where(Report.incident_id == incident.id)
        .scalar_subquery()
    )
    if all(m.status in FINAL_REPORT_STATUSES for m in members):
        if incident.status == "open":
            incident.status, incident.closed_at = "closed", now
            await _timeline(session, incident, "closed", actor)
    elif incident.status in ("closed", "dissolved"):
        incident.status, incident.closed_at = "open", None
        await _timeline(session, incident, "reopened", actor)
    await session.flush()
    await session.refresh(incident)
    await update_command_level(session, incident, actor)


async def announce_incident(session: AsyncSession, incident: Incident) -> None:
    """``incident.updated`` with the gouvernorats of the incident (lead and participants) for live routing."""
    out = await summary(session, incident)
    await emit(
        session,
        "incident.updated",
        {"incident": out.model_dump(mode="json"), "gouvernorat_codes": await all_gouvernorats(session, incident.id)},
    )


async def _announce(session: AsyncSession, incidents: list[Incident], report_ids: list[uuid.UUID]) -> None:
    # Scores depend on the reporters grouped together: refresh them, then tell the dashboards.
    await pipeline.rescore(session, report_ids)
    for incident in incidents:
        await announce_incident(session, incident)


async def can_read(session: AsyncSession, principal: Principal, incident: Incident) -> bool:
    """The caller may read the incident (lead, participant, break-glass, national)."""
    try:
        await scope.check_incident(session, principal, incident, Action.INCIDENT_READ)
    except HTTPException:
        return False
    return True


async def get_in_scope(
    session: AsyncSession,
    principal: Principal | None,
    incident_id: uuid.UUID,
    lock: bool = False,
    action: Action = Action.INCIDENT_READ,
) -> Incident:
    """The incident, after the policy check of ``action`` (404 out of scope, 403 forbidden).

    ``principal=None`` is the platform itself (automatic grouping at disaster level)."""
    incident = await session.get(Incident, incident_id, with_for_update=lock)
    if incident is None:
        raise _not_found()
    if principal is not None:
        await scope.check_incident(session, principal, incident, action)
    return incident


async def _create(session: AsyncSession, first: Report, actor: str) -> Incident:
    incident = Incident(
        category=first.category,
        gouvernorat_code=first.gouvernorat_code,
        status="open",
        lead_set_by=actor,
        lead_set_at=datetime.now(UTC),
        # Without a verified location only central command follows the incident until the lead is known.
        command_level="regional" if first.gouvernorat_code is not None else "central",
        command_level_reason=None if first.gouvernorat_code is not None else "no_lead",
    )
    session.add(incident)
    await session.flush()
    await _timeline(session, incident, "created", actor, report_id=str(first.id))
    return incident


async def _attach(session: AsyncSession, report: Report, incident: Incident, actor: str, via: str) -> list[Incident]:
    """Move a report into an incident. Returns every incident whose content changed."""
    if incident.status != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "incident_not_open")
    changed = [incident]
    previous = await session.get(Incident, report.incident_id, with_for_update=True) if report.incident_id else None
    if previous is not None and previous.id == incident.id:
        return []
    report.incident_id = incident.id
    report.updated_at = datetime.now(UTC)
    analysis = await session.get(Analysis, report.id)
    if analysis is not None:
        analysis.suggestion = None
    await _timeline(session, incident, "report_linked", actor, report_id=str(report.id), via=via)
    if previous is not None:
        await _timeline(
            session, previous, "report_unlinked", actor, report_id=str(report.id), moved_to=str(incident.id)
        )
        await refresh(session, previous, actor)
        changed.append(previous)
    await refresh(session, incident, actor)
    return changed


async def nearby_incident_ids(session: AsyncSession, report: Report) -> list[uuid.UUID]:
    """Open incidents a report could belong to (duplicate guard and cross-border linking, §5.2)."""
    settings = (await load_ai_settings(session)).grouping
    radii = {category.value: meters for category, meters in settings.radius_m.items()}
    own = radii.get(report.category, max(radii.values()))
    rows = await session.execute(
        text(
            """
            WITH x AS (SELECT id, location, received_at, category, incident_id FROM reports.report WHERE id = :id)
            SELECT i.id, i.category, min(ST_Distance(r.location, x.location)) AS distance_m
            FROM x
            JOIN reports.report r ON r.id <> x.id
             AND ST_DWithin(r.location, x.location, :radius)
             AND r.received_at BETWEEN x.received_at - make_interval(mins => :window)
                                   AND x.received_at + make_interval(mins => :window)
            JOIN ops.incident i ON i.id = r.incident_id AND i.status = 'open'
            WHERE (x.incident_id IS NULL OR i.id <> x.incident_id)
              AND (i.category = x.category OR 'sos' IN (i.category, x.category))
            GROUP BY i.id, i.category
            ORDER BY distance_m
            LIMIT 20
            """
        ),
        {"id": report.id, "radius": max(radii.values()), "window": settings.window_min},
    )
    return [
        incident_id
        for incident_id, category, distance in rows.all()
        if float(distance) <= max(own, radii.get(category, own))
    ]


async def nearby(session: AsyncSession, report: Report) -> list[schemas.NearbyIncident]:
    ids = await nearby_incident_ids(session, report)
    incidents = {i.id: i for i in await session.scalars(select(Incident).where(Incident.id.in_(ids)))}
    out: list[schemas.NearbyIncident] = []
    for incident_id in ids:
        s = await summary(session, incidents[incident_id])
        out.append(
            schemas.NearbyIncident(
                id=s.id,
                category=s.category,
                lead_gouvernorat_code=s.lead_gouvernorat_code,
                participating_gouvernorats=s.participating_gouvernorats,
                centroid=s.centroid,
                severity=s.severity,
                opened_at=s.opened_at,
                report_count=s.report_count,
            )
        )
    return out


def _suggested_incident(analysis: Analysis | None) -> uuid.UUID | None:
    suggestion = analysis.suggestion if analysis is not None else None
    if suggestion and suggestion.get("kind") == "incident" and suggestion.get("incident_id"):
        return uuid.UUID(suggestion["incident_id"])
    return None


async def link_target(session: AsyncSession, principal: Principal, report: Report, incident_id: uuid.UUID) -> Incident:
    """Target of a manual link: an incident the caller can read, or — across a border — one returned by the
    nearby-incidents search for this report or suggested by the AI (§5.2). Anything else is not disclosed (404)."""
    incident = await session.get(Incident, incident_id, with_for_update=True)
    if incident is None:
        raise _not_found()
    if await can_read(session, principal, incident):
        return incident
    if incident_id == _suggested_incident(await session.get(Analysis, report.id)):
        return incident
    if incident_id in await nearby_incident_ids(session, report):
        return incident
    raise _not_found()


async def link(
    session: AsyncSession, principal: Principal, report: Report, body: schemas.IncidentLinkIn, actor: str
) -> list[uuid.UUID]:
    """Apply an operator's grouping decision for a report. Returns the reports whose scores changed."""
    affected: list[uuid.UUID] = [report.id]
    old = report.incident_id
    if body.action == "new":
        if report.gouvernorat_code is None and not principal.is_national:
            # A report whose location is not verified is grouped by central staff only (§5.2).
            raise scope.forbidden("action_not_allowed")
        duplicates = await nearby_incident_ids(session, report)
        if duplicates and not body.override_reason:
            raise ApiError(status.HTTP_409_CONFLICT, "possible_duplicate", incident_ids=[str(i) for i in duplicates])
        incident = await _create(session, report, actor)
        if duplicates:
            add_timeline(
                session,
                incident.id,
                "duplicate_override",
                actor,
                incident_ids=[str(i) for i in duplicates],
                reason=body.override_reason,
            )
        changed = await _attach(session, report, incident, actor, via="new")
    elif body.action == "link":
        if body.incident_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "incident_id_required")
        incident = await link_target(session, principal, report, body.incident_id)
        changed = await _attach(session, report, incident, actor, via="manual")
    else:
        changed = await _accept(session, report, actor)
    for incident in changed:
        affected += [m.id for m in await _members(session, incident.id)]
    if old is not None:
        affected += [m.id for m in await _members(session, old)]
    await _announce(session, changed, affected)
    return affected


async def _accept(session: AsyncSession, report: Report, actor: str, via: str = "suggestion") -> list[Incident]:
    """Follow the AI suggestion. The suggestion is the authorisation: its incident may be led by another gouvernorat,
    which the report's gouvernorat then joins as a participant (phase 9 replaces the phase 3 404)."""
    analysis = await session.get(Analysis, report.id, with_for_update=True)
    suggestion = analysis.suggestion if analysis is not None else None
    if not suggestion:
        raise HTTPException(status.HTTP_409_CONFLICT, "no_suggestion")
    if suggestion["kind"] == "incident":
        incident = await get_in_scope(session, None, uuid.UUID(suggestion["incident_id"]), lock=True)
        return await _attach(session, report, incident, actor, via=via)
    other = await session.get(Report, uuid.UUID(suggestion["report_id"]), with_for_update=True)
    if other is None or other.status == Status.REJECTED.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "suggestion_outdated")
    if other.incident_id is not None:
        # The other report was grouped meanwhile: join its incident.
        incident = await get_in_scope(session, None, other.incident_id, lock=True)
        return await _attach(session, report, incident, actor, via=via)
    incident = await _create(session, other, actor)
    changed = await _attach(session, other, incident, actor, via=via)
    changed += await _attach(session, report, incident, actor, via=via)
    return list({i.id: i for i in changed}.values())


async def detach(session: AsyncSession, report: Report, actor: str) -> None:
    """Split: take a report out of its incident (it can then be grouped again)."""
    if report.incident_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_in_incident")
    incident = await session.get(Incident, report.incident_id, with_for_update=True)
    assert incident is not None
    report.incident_id = None
    report.updated_at = datetime.now(UTC)
    await _timeline(session, incident, "report_unlinked", actor, report_id=str(report.id))
    await refresh(session, incident, actor)
    affected = [report.id] + [m.id for m in await _members(session, incident.id)]
    await _announce(session, [incident], affected)


async def dismiss(session: AsyncSession, report: Report) -> None:
    """The operator turns the suggestion down: it is not proposed again for this report."""
    analysis = await session.get(Analysis, report.id, with_for_update=True)
    if analysis is None or not analysis.suggestion:
        raise HTTPException(status.HTTP_409_CONFLICT, "no_suggestion")
    analysis.dismissed = [*(analysis.dismissed or []), analysis.suggestion["target"]]
    analysis.suggestion = None
    await session.flush()
    await pipeline.rescore(session, [report.id])


async def merge(session: AsyncSession, target: Incident, source: Incident, actor: str) -> None:
    """The source's reports move to the target; its lead and participants become participants of the target."""
    if target.id == source.id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "same_incident")
    if target.status != "open" or source.status != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "incident_not_open")
    moved = await _members(session, source.id)
    now = datetime.now(UTC)
    for report in moved:
        report.incident_id = target.id
        report.updated_at = now
    source.status, source.merged_into, source.closed_at, source.updated_at = "merged", target.id, now, now
    await _timeline(session, target, "merged_from", actor, incident_id=str(source.id), reports=len(moved))
    await _timeline(session, source, "merged_into", actor, incident_id=str(target.id))
    for code in await all_gouvernorats(session, source.id):
        await add_participant(session, target, code, actor, "merged")
    await refresh(session, target, actor)
    affected = [m.id for m in await _members(session, target.id)]
    await _announce(session, [target, source], affected)


async def after_status_change(session: AsyncSession, report: Report, actor: str) -> None:
    """A member closed or rejected: close the incident when all its reports are final."""
    if report.incident_id is None:
        return
    incident = await session.get(Incident, report.incident_id, with_for_update=True)
    if incident is None:
        return
    before = incident.status
    await refresh(session, incident, actor)
    if incident.status != before:
        await announce_incident(session, incident)


# ---------------------------------------------------------------- queries


def _encode(at: datetime, incident_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{at.isoformat()}|{incident_id}".encode()).decode().rstrip("=")


def _decode(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        at, iid = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode().split("|", 1)
        return datetime.fromisoformat(at), uuid.UUID(iid)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc


async def list_incidents(
    session: AsyncSession, principal: Principal, statuses: list[str], limit: int, cursor: str | None
) -> tuple[list[schemas.IncidentSummary], str | None]:
    query = select(Incident).where(await visible_ids_filter(session, principal))
    if statuses:
        query = query.where(Incident.status.in_(statuses))
    if cursor:
        at, iid = _decode(cursor)
        query = query.where(or_(Incident.updated_at < at, and_(Incident.updated_at == at, Incident.id < iid)))
    rows = list(await session.scalars(query.order_by(Incident.updated_at.desc(), Incident.id.desc()).limit(limit)))
    items = [await summary(session, i) for i in rows]
    next_cursor = _encode(rows[-1].updated_at, rows[-1].id) if len(rows) == limit else None
    return items, next_cursor


async def timeline(session: AsyncSession, incident_id: uuid.UUID) -> list[schemas.TimelineEntry]:
    rows = await session.scalars(
        select(TimelineEvent)
        .where(TimelineEvent.incident_id == incident_id)
        .order_by(TimelineEvent.at, TimelineEvent.id)
    )
    return [schemas.TimelineEntry(at=e.at, kind=e.kind, actor=e.actor, payload=e.payload) for e in rows]


AUTO_ACTOR = "system:auto_grouping"


async def auto_group(session: AsyncSession, report: Report) -> bool:
    """BR-11: at disaster level the AI grouping suggestion is applied without waiting for an operator.

    Operators can still split (detach) or merge afterwards; the timeline marks the link ``via: auto``. An incident led
    by another gouvernorat gains the report's gouvernorat as a participant (§10, phase 3 row).
    """
    analysis = await session.get(Analysis, report.id)
    if analysis is None or not analysis.suggestion or report.incident_id is not None:
        return False
    if await level_of(session, report.gouvernorat_code) is not OpLevel.DISASTER:
        return False
    old = report.incident_id
    changed = await _accept(session, report, AUTO_ACTOR, via="auto")
    affected = [report.id]
    for incident in changed:
        affected += [m.id for m in await _members(session, incident.id)]
    if old is not None:
        affected += [m.id for m in await _members(session, old)]
    from app.modules.audit import service as audit

    await audit.record(
        session,
        actor=AUTO_ACTOR,
        action="incident.link",
        target=f"report:{report.id}",
        details={"action": "auto", "incident_id": str(report.incident_id)},
        gouvernorats=await all_gouvernorats(session, report.incident_id) if report.incident_id else None,
    )
    await _announce(session, changed, affected)
    return True
