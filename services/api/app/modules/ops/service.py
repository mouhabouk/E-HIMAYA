"""Incidents: one field event grouping several reports (FR-C-02, BR-10, BR-11).

The AI suggests which reports belong together; operators confirm, link, split (detach) and merge.
Every change is written to the incident timeline and the audit log, and the scores of the reports
involved are refreshed (the number of reporters is a priority component, BR-20).
"""

import base64
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from geoalchemy2 import Geography, Geometry
from sqlalchemy import and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import emit
from app.core.security import Principal
from app.modules.ai import pipeline
from app.modules.ai.models import Analysis
from app.modules.ops import schemas
from app.modules.ops.domain import ACTIVE_ASSIGNMENT
from app.modules.ops.levels import level_of
from app.modules.ops.models import Assignment, Callout, Incident, OpLevel, TimelineEvent
from app.modules.reports.domain import Category, Status
from app.modules.reports.models import Report

FINAL_REPORT_STATUSES = (Status.CLOSED.value, Status.REJECTED.value)


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "not_found")


def in_scope(principal: Principal, incident: Incident) -> bool:
    return principal.is_national or (
        incident.gouvernorat_code is not None and principal.can_access_gouvernorat(incident.gouvernorat_code)
    )


def _scope(principal: Principal) -> Any:
    return True if principal.is_national else Incident.gouvernorat_code == principal.gouvernorat_code


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
        centroid=point,
        severity=incident.severity,
        report_count=len(members),
        reporter_count=len({m.user_id for m in members}),
        opened_at=incident.opened_at,
        updated_at=incident.updated_at,
        closed_at=incident.closed_at,
        merged_into=incident.merged_into,
    )


async def _timeline(session: AsyncSession, incident: Incident, kind: str, actor: str, **payload: Any) -> None:
    session.add(TimelineEvent(incident_id=incident.id, kind=kind, actor=actor, payload=payload))


async def refresh(session: AsyncSession, incident: Incident, actor: str = "system") -> None:
    """Recompute what derives from the member reports: place, type, severity, scope, open or closed."""
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
    governorates = Counter(m.gouvernorat_code for m in members if m.gouvernorat_code is not None)
    incident.gouvernorat_code = governorates.most_common(1)[0][0] if governorates else None
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


async def _announce(session: AsyncSession, incidents: list[Incident], report_ids: list[uuid.UUID]) -> None:
    # Scores depend on the reporters grouped together: refresh them, then tell the dashboards.
    await pipeline.rescore(session, report_ids)
    for incident in incidents:
        await emit(
            session, "incident.updated", {"incident": (await summary(session, incident)).model_dump(mode="json")}
        )


async def get_in_scope(
    session: AsyncSession, principal: Principal | None, incident_id: uuid.UUID, lock: bool = False
) -> Incident:
    """``principal=None`` is the platform itself (automatic grouping at disaster level)."""
    incident = await session.get(Incident, incident_id, with_for_update=lock)
    if incident is None or (principal is not None and not in_scope(principal, incident)):
        raise _not_found()
    return incident


async def _create(session: AsyncSession, first: Report, actor: str) -> Incident:
    incident = Incident(category=first.category, gouvernorat_code=first.gouvernorat_code, status="open")
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


async def link(
    session: AsyncSession, principal: Principal, report: Report, body: schemas.IncidentLinkIn, actor: str
) -> list[uuid.UUID]:
    """Apply an operator's grouping decision for a report. Returns the reports whose scores changed."""
    affected: list[uuid.UUID] = [report.id]
    if body.action == "new":
        old = report.incident_id
        incident = await _create(session, report, actor)
        changed = await _attach(session, report, incident, actor, via="new")
    elif body.action == "link":
        if body.incident_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "incident_id_required")
        old = report.incident_id
        incident = await get_in_scope(session, principal, body.incident_id, lock=True)
        changed = await _attach(session, report, incident, actor, via="manual")
    else:
        old = report.incident_id
        changed = await _accept(session, principal, report, actor)
    for incident in changed:
        affected += [m.id for m in await _members(session, incident.id)]
    if old is not None:
        affected += [m.id for m in await _members(session, old)]
    await _announce(session, changed, affected)
    return affected


async def _accept(
    session: AsyncSession, principal: Principal | None, report: Report, actor: str, via: str = "suggestion"
) -> list[Incident]:
    analysis = await session.get(Analysis, report.id, with_for_update=True)
    suggestion = analysis.suggestion if analysis is not None else None
    if not suggestion:
        raise HTTPException(status.HTTP_409_CONFLICT, "no_suggestion")
    if suggestion["kind"] == "incident":
        incident = await get_in_scope(session, principal, uuid.UUID(suggestion["incident_id"]), lock=True)
        return await _attach(session, report, incident, actor, via=via)
    other = await session.get(Report, uuid.UUID(suggestion["report_id"]), with_for_update=True)
    if other is None or other.status == Status.REJECTED.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "suggestion_outdated")
    if other.incident_id is not None:
        # The other report was grouped meanwhile: join its incident.
        incident = await get_in_scope(session, principal, other.incident_id, lock=True)
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
        await emit(
            session, "incident.updated", {"incident": (await summary(session, incident)).model_dump(mode="json")}
        )


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
    query = select(Incident).where(_scope(principal))
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

    Operators can still split (detach) or merge afterwards; the timeline marks the link ``via: auto``.
    """
    analysis = await session.get(Analysis, report.id)
    if analysis is None or not analysis.suggestion or report.incident_id is not None:
        return False
    if await level_of(session, report.gouvernorat_code) is not OpLevel.DISASTER:
        return False
    old = report.incident_id
    changed = await _accept(session, None, report, AUTO_ACTOR, via="auto")
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
    )
    await _announce(session, changed, affected)
    return True
