"""Interventions (FR-C-09): incident card, assignment orders, volunteer call-outs (UC-05), closing evaluation.

Reporters follow the intervention through their tracking code without staff having to update each
report: the first assignment moves the incident's reports to «قيد المعالجة», a resource or volunteer on
scene to «تم التدخل», the closing evaluation to «أُغلق التدخل» (actor ``system:operations``).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from geoalchemy2 import Geometry
from sqlalchemy import any_, cast, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import emit
from app.core.security import Principal
from app.modules.audit import service as audit
from app.modules.identity.models import Profile
from app.modules.identity.service import Reporter
from app.modules.notify import outbox, templates
from app.modules.ops import resources, schemas
from app.modules.ops import service as incidents
from app.modules.ops.domain import ACTIVE_ASSIGNMENT, ASSIGNMENT_TRANSITIONS, classification_allowed
from app.modules.ops.models import Assignment, Callout, CalloutTarget, Incident, Resource, TimelineEvent, Unit
from app.modules.reports import service as reports
from app.modules.reports.domain import Category, Status, can_transition
from app.modules.reports.models import Report
from app.modules.volunteers import service as volunteers
from app.modules.volunteers.models import Volunteer
from app.modules.volunteers.presence import get_presence
from app.modules.volunteers.schemas import Skill

SYSTEM_ACTOR = "system:operations"
TARGET_TIMEOUT = timedelta(minutes=30)
SKILLS = frozenset(Skill.__args__)  # type: ignore[attr-defined]


def _now() -> datetime:
    return datetime.now(UTC)


def _who(principal: Principal) -> str:
    return audit.name_of(principal) or audit.actor_of(principal)


def _timeline(session: AsyncSession, incident_id: uuid.UUID, kind: str, actor: str, **payload: Any) -> None:
    session.add(TimelineEvent(incident_id=incident_id, kind=kind, actor=actor, payload=payload))


async def _announce_incident(session: AsyncSession, incident: Incident) -> None:
    incident.updated_at = _now()
    await session.flush()
    await emit(
        session, "incident.updated", {"incident": (await incidents.summary(session, incident)).model_dump(mode="json")}
    )


# ---------------------------------------------------------------- reporters' tracking codes


async def _move_report(session: AsyncSession, report: Report, path: list[Status], actor: str) -> bool:
    moved = False
    for target in path:
        if Status(report.status) is target:
            continue
        if not can_transition(Status(report.status), target):
            break
        await reports.change_status(session, report, target, actor, None)
        moved = True
    if moved:
        found = await reports.staff_summary(session, report.id)
        if found is not None:
            await emit(session, "report.status_changed", {"report": found[0].model_dump(mode="json")})
    return moved


async def advance_reports(
    session: AsyncSession, incident_id: uuid.UUID, stage: Status, actor: str = SYSTEM_ACTOR
) -> None:
    paths = {
        Status.IN_PROGRESS: {Status.RECEIVED: [Status.IN_PROGRESS]},
        Status.INTERVENED: {
            Status.RECEIVED: [Status.IN_PROGRESS, Status.INTERVENED],
            Status.IN_PROGRESS: [Status.INTERVENED],
        },
        Status.CLOSED: {
            Status.RECEIVED: [Status.IN_PROGRESS, Status.CLOSED],
            Status.IN_PROGRESS: [Status.CLOSED],
            Status.INTERVENED: [Status.CLOSED],
            Status.ONGOING: [Status.CLOSED],
        },
    }[stage]
    members = await session.scalars(
        select(Report).where(Report.incident_id == incident_id).order_by(Report.received_at).with_for_update()
    )
    for report in members:
        path = paths.get(Status(report.status))
        if path:
            await _move_report(session, report, path, actor)


# ---------------------------------------------------------------- outputs


async def assignments_of(session: AsyncSession, incident_id: uuid.UUID) -> list[schemas.AssignmentOut]:
    rows = (
        await session.execute(
            select(Assignment, Resource, Unit, Volunteer, Profile)
            .outerjoin(Resource, Resource.id == Assignment.resource_id)
            .outerjoin(Unit, Unit.id == Resource.unit_id)
            .outerjoin(Volunteer, Volunteer.user_id == Assignment.volunteer_id)
            .outerjoin(Profile, Profile.user_id == Assignment.volunteer_id)
            .where(Assignment.incident_id == incident_id)
            .order_by(Assignment.created_at)
        )
    ).all()
    return [_assignment_out(*row) for row in rows]


def _assignment_out(
    a: Assignment, r: Resource | None, u: Unit | None, v: Volunteer | None, p: Profile | None
) -> schemas.AssignmentOut:
    return schemas.AssignmentOut(
        id=a.id,
        incident_id=a.incident_id,
        kind=a.kind,
        resource=(
            schemas.ResourceRef(id=r.id, label=r.label, kind=r.kind, unit_name=u.name_ar)
            if r is not None and u is not None
            else None
        ),
        volunteer=(
            schemas.VolunteerRef(
                id=v.user_id, full_name=volunteers.full_name(p), phone=p.phone if p else None, skills=list(v.skills)
            )
            if v is not None
            else None
        ),
        order=a.order,
        status=a.status,
        created_by=a.created_by,
        created_at=a.created_at,
        en_route_at=a.en_route_at,
        on_scene_at=a.on_scene_at,
        released_at=a.released_at,
        cancelled_at=a.cancelled_at,
    )


async def assignment_out(session: AsyncSession, assignment_id: uuid.UUID) -> schemas.AssignmentOut:
    row = (
        await session.execute(
            select(Assignment, Resource, Unit, Volunteer, Profile)
            .outerjoin(Resource, Resource.id == Assignment.resource_id)
            .outerjoin(Unit, Unit.id == Resource.unit_id)
            .outerjoin(Volunteer, Volunteer.user_id == Assignment.volunteer_id)
            .outerjoin(Profile, Profile.user_id == Assignment.volunteer_id)
            .where(Assignment.id == assignment_id)
        )
    ).one()
    return _assignment_out(*row)


async def callout_out(session: AsyncSession, callout: Callout) -> schemas.CalloutOut:
    rows = (
        await session.execute(
            select(CalloutTarget, Profile)
            .outerjoin(Profile, Profile.user_id == CalloutTarget.volunteer_id)
            .where(CalloutTarget.callout_id == callout.id)
            .order_by(CalloutTarget.distance_m.nulls_last(), CalloutTarget.volunteer_id)
        )
    ).all()
    tracked = [t.volunteer_id for t, _ in rows if t.status in ("accepted", "arrived")]
    fixes = await get_presence().get_many(tracked) if tracked else {}
    targets = []
    for target, profile in rows:
        fix = fixes.get(target.volunteer_id)
        targets.append(
            schemas.CalloutTargetOut(
                volunteer_id=target.volunteer_id,
                full_name=volunteers.full_name(profile),
                phone=profile.phone if profile else None,
                distance_m=target.distance_m,
                status=target.status,
                eta_minutes=target.eta_minutes,
                responded_at=target.responded_at,
                arrived_at=target.arrived_at,
                position=schemas.Position(lat=fix.lat, lon=fix.lon, at=fix.at) if fix else None,
            )
        )
    return schemas.CalloutOut(
        id=callout.id,
        incident_id=callout.incident_id,
        skill=callout.skill,
        requested=callout.requested,
        radius_km=callout.radius_km,
        message=callout.message,
        status=callout.status,
        created_by=callout.created_by,
        created_at=callout.created_at,
        accepted=sum(1 for t in targets if t.status in ("accepted", "arrived")),
        targets=targets,
    )


async def callouts_of(session: AsyncSession, incident_id: uuid.UUID) -> list[schemas.CalloutOut]:
    rows = await session.scalars(
        select(Callout).where(Callout.incident_id == incident_id).order_by(Callout.created_at.desc())
    )
    return [await callout_out(session, c) for c in rows]


async def announce_callout(session: AsyncSession, callout: Callout, gouvernorat_code: int | None) -> None:
    out = await callout_out(session, callout)
    await emit(
        session, "callout.updated", {"callout": out.model_dump(mode="json"), "gouvernorat_code": gouvernorat_code}
    )


async def _announce_assignment(session: AsyncSession, assignment: Assignment, gouvernorat_code: int | None) -> None:
    out = await assignment_out(session, assignment.id)
    await emit(
        session, "assignment.updated", {"assignment": out.model_dump(mode="json"), "gouvernorat_code": gouvernorat_code}
    )


def evaluation_of(incident: Incident) -> schemas.Evaluation | None:
    return schemas.Evaluation.model_validate(incident.evaluation) if incident.evaluation else None


# ---------------------------------------------------------------- incident card


async def update_card(
    session: AsyncSession, principal: Principal, incident: Incident, body: schemas.IncidentCardIn
) -> None:
    fields = body.model_fields_set
    if "classification" in fields and body.classification is not None:
        if not classification_allowed(Category(incident.category), body.classification):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_classification")
    changes: dict[str, Any] = {}
    if "title" in fields:
        incident.title = body.title or None
        changes["title"] = incident.title
    if "classification" in fields:
        incident.classification = body.classification
        changes["classification"] = incident.classification
    if changes:
        _timeline(session, incident.id, "card_updated", _who(principal), **changes)
        await _announce_incident(session, incident)


async def add_note(session: AsyncSession, principal: Principal, incident: Incident, text: str) -> schemas.TimelineEntry:
    event = TimelineEvent(incident_id=incident.id, kind="note", actor=_who(principal), payload={"text": text})
    session.add(event)
    await session.flush()
    await session.refresh(event)
    return schemas.TimelineEntry(at=event.at, kind=event.kind, actor=event.actor, payload=event.payload)


# ---------------------------------------------------------------- assignments


async def create_assignment(
    session: AsyncSession, principal: Principal, incident: Incident, body: schemas.AssignmentIn
) -> Assignment:
    if incident.status != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "incident_not_open")
    resource = await resources.get_resource(session, principal, body.resource_id, lock=True)
    if resource.status != "available":
        raise HTTPException(status.HTTP_409_CONFLICT, "resource_busy")
    first = not await session.scalar(select(func.count()).where(Assignment.incident_id == incident.id))
    assignment = Assignment(
        incident_id=incident.id,
        kind="resource",
        resource_id=resource.id,
        order=body.order,
        status="ordered",
        created_by=_who(principal),
    )
    session.add(assignment)
    resource.status, resource.updated_at = "assigned", _now()
    await session.flush()
    await session.refresh(assignment)
    _timeline(
        session,
        incident.id,
        "assignment_created",
        _who(principal),
        assignment_id=str(assignment.id),
        resource=resource.label,
        resource_kind=resource.kind,
    )
    if first:
        await advance_reports(session, incident.id, Status.IN_PROGRESS)
    await _announce_assignment(session, assignment, incident.gouvernorat_code)
    await resources.announce(session, resource.id)
    await _announce_incident(session, incident)
    return assignment


async def _set_assignment_status(session: AsyncSession, assignment: Assignment, target: str, actor: str) -> None:
    if target not in ASSIGNMENT_TRANSITIONS[assignment.status]:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    now = _now()
    assignment.status = target
    if target == "en_route":
        assignment.en_route_at = now
    elif target == "on_scene":
        assignment.on_scene_at = now
        assignment.en_route_at = assignment.en_route_at or now
    elif target == "released":
        assignment.released_at = now
    elif target == "cancelled":
        assignment.cancelled_at = now
    if target in ("released", "cancelled") and assignment.resource_id is not None:
        resource = await session.get(Resource, assignment.resource_id, with_for_update=True)
        if resource is not None and resource.status == "assigned":
            resource.status, resource.updated_at = "available", now
    _timeline(
        session, assignment.incident_id, "assignment_status", actor, assignment_id=str(assignment.id), status=target
    )
    await session.flush()


async def update_assignment(
    session: AsyncSession, principal: Principal, assignment_id: uuid.UUID, body: schemas.AssignmentStatusIn
) -> Assignment:
    assignment = await session.get(Assignment, assignment_id, with_for_update=True)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    incident = await incidents.get_in_scope(session, principal, assignment.incident_id)
    await _set_assignment_status(session, assignment, body.status, _who(principal))
    if body.note:
        _timeline(session, incident.id, "note", _who(principal), text=body.note, assignment_id=str(assignment.id))
    if assignment.volunteer_id is not None and body.status == "on_scene":
        await session.execute(
            update(CalloutTarget)
            .where(CalloutTarget.assignment_id == assignment.id, CalloutTarget.status == "accepted")
            .values(status="arrived", arrived_at=_now())
        )
    if body.status == "on_scene":
        await advance_reports(session, incident.id, Status.INTERVENED)
    await _announce_assignment(session, assignment, incident.gouvernorat_code)
    if assignment.resource_id is not None:
        await resources.announce(session, assignment.resource_id)
    await _announce_incident(session, incident)
    return assignment


# ---------------------------------------------------------------- volunteer call-outs (UC-05)


async def _centroid(session: AsyncSession, incident: Incident) -> tuple[float, float]:
    row = (
        await session.execute(
            select(func.ST_Y(cast(Incident.centroid, Geometry)), func.ST_X(cast(Incident.centroid, Geometry))).where(
                Incident.id == incident.id
            )
        )
    ).one()
    if row[0] is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "incident_without_location")
    return float(row[0]), float(row[1])


async def _busy(session: AsyncSession, volunteer_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not volunteer_ids:
        return set()
    rows = await session.scalars(
        select(Assignment.volunteer_id).where(
            Assignment.volunteer_id.in_(volunteer_ids), Assignment.status.in_(ACTIVE_ASSIGNMENT)
        )
    )
    return {r for r in rows if r is not None}


async def suggestions(
    session: AsyncSession, principal: Principal, incident: Incident, skill: str | None, radius_km: int, limit: int
) -> list[schemas.VolunteerSuggestion]:
    """Ready, approved volunteers within their period, with the skill, nearest first (UC-05)."""
    if skill is not None and skill not in SKILLS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_skill")
    lat, lon = await _centroid(session, incident)
    nearby = await get_presence().nearby(lat, lon, radius_km * 1000, max(limit * 5, 50))
    if not nearby:
        return []
    distances = dict(nearby)
    today = _now().date()
    query = (
        select(Volunteer, Profile)
        .outerjoin(Profile, Profile.user_id == Volunteer.user_id)
        .where(
            Volunteer.user_id.in_(list(distances)),
            Volunteer.status == "approved",
            Volunteer.ready_until > func.now(),
            Volunteer.period_from <= today,
            (Volunteer.period_to.is_(None)) | (Volunteer.period_to >= today),
            volunteers.scope_filter(principal),
        )
    )
    if skill:
        query = query.where(any_(Volunteer.skills) == skill)
    rows = (await session.execute(query)).all()
    busy = await _busy(session, [v.user_id for v, _ in rows])
    found = [
        schemas.VolunteerSuggestion(
            volunteer_id=v.user_id,
            full_name=volunteers.full_name(p),
            phone=p.phone if p else None,
            skills=list(v.skills),
            distance_m=round(distances[v.user_id]),
            busy=v.user_id in busy,
        )
        for v, p in rows
    ]
    return sorted(found, key=lambda s: (s.busy, s.distance_m))[:limit]


def _callout_push(session: AsyncSession, user_id: uuid.UUID, callout: Callout, distance_m: int) -> None:
    skill = templates.SKILLS.get(callout.skill, templates.SKILLS["other"])
    body = {
        lang: text.format(skill=skill[lang], km=max(1, round(distance_m / 1000)))
        for lang, text in templates.CALLOUT_BODY.items()
    }
    outbox.push(session, user_id, "callout", templates.CALLOUT_TITLE, body, {"callout_id": str(callout.id)}, alert=True)


async def create_callout(
    session: AsyncSession, principal: Principal, incident: Incident, body: schemas.CalloutIn
) -> Callout:
    if incident.status != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "incident_not_open")
    candidates = await suggestions(session, principal, incident, body.skill, body.radius_km, 100)
    if body.volunteer_ids is not None:
        wanted = set(body.volunteer_ids)
        chosen = [c for c in candidates if c.volunteer_id in wanted]
    else:
        chosen = [c for c in candidates if not c.busy][: min(body.requested * 2, 100)]
    if not chosen:
        raise HTTPException(status.HTTP_409_CONFLICT, "no_volunteer_available")
    callout = Callout(
        incident_id=incident.id,
        skill=body.skill,
        requested=body.requested,
        radius_km=body.radius_km,
        message=body.message,
        status="open",
        created_by=_who(principal),
    )
    session.add(callout)
    await session.flush()
    await session.refresh(callout)
    for candidate in chosen:
        session.add(
            CalloutTarget(callout_id=callout.id, volunteer_id=candidate.volunteer_id, distance_m=candidate.distance_m)
        )
        _callout_push(session, candidate.volunteer_id, callout, candidate.distance_m)
    _timeline(
        session,
        incident.id,
        "callout_sent",
        _who(principal),
        callout_id=str(callout.id),
        skill=body.skill,
        requested=body.requested,
        sent=len(chosen),
    )
    await session.flush()
    await announce_callout(session, callout, incident.gouvernorat_code)
    await _announce_incident(session, incident)
    return callout


async def get_callout(
    session: AsyncSession, principal: Principal, callout_id: uuid.UUID, lock: bool = False
) -> tuple[Callout, Incident]:
    callout = await session.get(Callout, callout_id, with_for_update=lock)
    if callout is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    incident = await incidents.get_in_scope(session, principal, callout.incident_id)
    return callout, incident


async def _close_callout(session: AsyncSession, callout: Callout, final: str) -> None:
    callout.status, callout.closed_at = final, _now()
    await session.execute(
        update(CalloutTarget)
        .where(CalloutTarget.callout_id == callout.id, CalloutTarget.status == "sent")
        .values(status="expired")
    )


async def cancel_callout(session: AsyncSession, principal: Principal, callout_id: uuid.UUID) -> Callout:
    callout, incident = await get_callout(session, principal, callout_id, lock=True)
    if callout.status not in ("open", "filled"):
        raise HTTPException(status.HTTP_409_CONFLICT, "callout_closed")
    await _close_callout(session, callout, "cancelled")
    engaged = await session.scalars(
        select(Assignment).where(Assignment.callout_id == callout.id, Assignment.status.in_(("ordered", "en_route")))
    )
    for assignment in engaged:
        await _set_assignment_status(session, assignment, "cancelled", _who(principal))
    _timeline(session, incident.id, "callout_cancelled", _who(principal), callout_id=str(callout.id))
    await session.flush()
    await announce_callout(session, callout, incident.gouvernorat_code)
    await _announce_incident(session, incident)
    return callout


async def _target(session: AsyncSession, callout_id: uuid.UUID, volunteer_id: uuid.UUID) -> CalloutTarget:
    target = await session.get(CalloutTarget, (callout_id, volunteer_id), with_for_update=True)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return target


async def respond(
    session: AsyncSession, reporter: Reporter, callout_id: uuid.UUID, response: str, eta_minutes: int | None
) -> Callout:
    volunteer = await volunteers.get_mine(session, reporter)
    callout = await session.get(Callout, callout_id, with_for_update=True)
    if callout is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    target = await _target(session, callout_id, volunteer.user_id)
    incident = await session.get(Incident, callout.incident_id)
    assert incident is not None
    now = _now()
    if response == "accept":
        if eta_minutes is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "eta_required")
        if callout.status != "open" or target.status not in ("sent", "declined", "expired"):
            if target.status in ("accepted", "arrived"):
                target.eta_minutes = eta_minutes
                await session.flush()
                await announce_callout(session, callout, incident.gouvernorat_code)
                return callout
            raise HTTPException(status.HTTP_409_CONFLICT, "callout_closed")
        if volunteer.status != "approved":
            raise HTTPException(status.HTTP_409_CONFLICT, "volunteer_not_approved")
        assignment = Assignment(
            incident_id=callout.incident_id,
            kind="volunteer",
            volunteer_id=volunteer.user_id,
            callout_id=callout.id,
            order=callout.message,
            status="en_route",
            en_route_at=now,
            created_by=SYSTEM_ACTOR,
        )
        session.add(assignment)
        await session.flush()
        target.status, target.eta_minutes, target.responded_at, target.assignment_id = (
            "accepted",
            eta_minutes,
            now,
            assignment.id,
        )
        _timeline(
            session,
            incident.id,
            "callout_accepted",
            reporter.actor,
            callout_id=str(callout.id),
            volunteer_id=str(volunteer.user_id),
            eta_minutes=eta_minutes,
        )
        accepted = await session.scalar(
            select(func.count()).where(
                CalloutTarget.callout_id == callout.id, CalloutTarget.status.in_(("accepted", "arrived"))
            )
        )
        if (accepted or 0) >= callout.requested:
            await _close_callout(session, callout, "filled")
        await advance_reports(session, incident.id, Status.IN_PROGRESS)
        await _announce_assignment(session, assignment, incident.gouvernorat_code)
    else:
        if target.status == "arrived":
            raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
        if target.status == "accepted" and target.assignment_id is not None:
            # Withdrawing after accepting frees the place for another volunteer.
            assignment_obj = await session.get(Assignment, target.assignment_id, with_for_update=True)
            if assignment_obj is not None and assignment_obj.status in ("ordered", "en_route"):
                await _set_assignment_status(session, assignment_obj, "cancelled", reporter.actor)
            if callout.status == "filled":
                callout.status, callout.closed_at = "open", None
        target.status, target.responded_at = "declined", now
        _timeline(
            session,
            incident.id,
            "callout_declined",
            reporter.actor,
            callout_id=str(callout.id),
            volunteer_id=str(volunteer.user_id),
        )
    await session.flush()
    await announce_callout(session, callout, incident.gouvernorat_code)
    await _announce_incident(session, incident)
    return callout


async def mark_arrived(session: AsyncSession, callout: Callout, volunteer_id: uuid.UUID, actor: str) -> None:
    target = await _target(session, callout.id, volunteer_id)
    if target.status != "accepted":
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    target.status, target.arrived_at = "arrived", _now()
    if target.assignment_id is not None:
        assignment = await session.get(Assignment, target.assignment_id, with_for_update=True)
        if assignment is not None and assignment.status in ("ordered", "en_route"):
            await _set_assignment_status(session, assignment, "on_scene", actor)
            incident = await session.get(Incident, callout.incident_id)
            assert incident is not None
            await advance_reports(session, incident.id, Status.INTERVENED)
            await _announce_assignment(session, assignment, incident.gouvernorat_code)
    await session.flush()


async def my_callouts(session: AsyncSession, reporter: Reporter, active: bool) -> list[Any]:
    from app.modules.volunteers.schemas import MyCallout

    volunteer = await volunteers.get_mine(session, reporter)
    query = (
        select(
            CalloutTarget,
            Callout,
            Incident.category,
            func.ST_Y(cast(Incident.centroid, Geometry)),
            func.ST_X(cast(Incident.centroid, Geometry)),
        )
        .join(Callout, Callout.id == CalloutTarget.callout_id)
        .join(Incident, Incident.id == Callout.incident_id)
        .where(CalloutTarget.volunteer_id == volunteer.user_id)
    )
    if active:
        query = query.where(
            (Callout.status == "open") & (CalloutTarget.status == "sent")
            | CalloutTarget.status.in_(("accepted", "arrived")) & Callout.status.in_(("open", "filled"))
        )
    rows = (await session.execute(query.order_by(CalloutTarget.sent_at.desc()).limit(50))).all()
    return [
        MyCallout(
            id=c.id,
            incident_category=category,
            message=c.message,
            skill=c.skill,
            distance_m=t.distance_m,
            location={"lat": float(lat), "lon": float(lon)} if lat is not None else None,
            status=c.status,
            my_status=t.status,
            eta_minutes=t.eta_minutes,
            created_at=c.created_at,
        )
        for t, c, category, lat, lon in rows
    ]


async def expire_targets(session: AsyncSession) -> int:
    """Call-out targets without an answer after 30 minutes stop waiting for one."""
    result = await session.execute(
        update(CalloutTarget)
        .where(CalloutTarget.status == "sent", CalloutTarget.sent_at < func.now() - TARGET_TIMEOUT)
        .values(status="expired")
        .returning(CalloutTarget.callout_id)
    )
    return len(result.all())


# ---------------------------------------------------------------- closing evaluation


async def close(session: AsyncSession, principal: Principal, incident: Incident, body: schemas.CloseIn) -> None:
    if incident.status not in ("open", "closed") or (incident.status == "closed" and incident.evaluation):
        raise HTTPException(status.HTTP_409_CONFLICT, "incident_not_open")
    active = await session.scalar(
        select(func.count()).where(Assignment.incident_id == incident.id, Assignment.status.in_(ACTIVE_ASSIGNMENT))
    )
    if active:
        raise HTTPException(status.HTTP_409_CONFLICT, "assignments_active")
    callouts = await session.scalars(
        select(Callout)
        .where(Callout.incident_id == incident.id, Callout.status.in_(("open", "filled")))
        .with_for_update()
    )
    for callout in callouts:
        await _close_callout(session, callout, "closed")
    who = _who(principal)
    incident.evaluation = schemas.Evaluation(**body.model_dump(), closed_by=who, closed_at=_now()).model_dump(
        mode="json"
    )
    _timeline(session, incident.id, "evaluated", who, outcome=body.outcome, casualties=body.casualties.model_dump())
    await advance_reports(session, incident.id, Status.CLOSED, audit.actor_of(principal))
    await incidents.refresh(session, incident, who)
    await _announce_incident(session, incident)
