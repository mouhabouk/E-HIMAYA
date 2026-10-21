"""Resources across gouvernorats (phase 9 §5.4): requests, approval by the owning region, assignments it creates.

Central directs, regions intervene: no room orders another gouvernorat's resources. A room taking part in an incident
(or central command) asks the gouvernorat that owns the resources; that region's ops manager or local committee —
or the central committee when the incident is at central command level — approves with the resources it engages
(one ``ordered`` assignment each, the owning gouvernorat joins the incident) or refuses with a reason. The requesting
room may cancel while the request is pending. Every step is on the timeline, in the audit log and on the live feed.
"""

import base64
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Ctx, room_code
from app.core.events import emit
from app.core.security import Principal
from app.modules.audit import service as audit
from app.modules.ops import interventions, resources, schemas, scope
from app.modules.ops import service as incidents
from app.modules.ops.models import Assignment, Incident, Resource, ResourceRequest, Unit
from app.modules.reports.domain import Status

DIRECTIONS = ("incoming", "outgoing")


def _now() -> datetime:
    return datetime.now(UTC)


def _who(principal: Principal) -> str:
    return audit.name_of(principal) or audit.actor_of(principal)


async def request_out(session: AsyncSession, row: ResourceRequest) -> schemas.ResourceRequestOut:
    assignment_ids = list(
        await session.scalars(
            select(Assignment.id).where(Assignment.request_id == row.id).order_by(Assignment.created_at)
        )
    )
    return schemas.ResourceRequestOut(
        id=row.id,
        incident_id=row.incident_id,
        from_room=row.from_room,
        to_gouvernorat_code=row.to_gouvernorat_code,
        resource_id=row.resource_id,
        resource_kind=row.resource_kind,
        quantity=row.quantity,
        reason=row.reason,
        status=row.status,
        requested_by_name=row.requested_by_name,
        requested_at=row.requested_at,
        decided_by_name=row.decided_by_name,
        decided_at=row.decided_at,
        decision_note=row.decision_note,
        assignment_ids=assignment_ids,
    )


async def requests_of(session: AsyncSession, incident_id: uuid.UUID) -> list[schemas.ResourceRequestOut]:
    rows = await session.scalars(
        select(ResourceRequest)
        .where(ResourceRequest.incident_id == incident_id)
        .order_by(ResourceRequest.requested_at, ResourceRequest.id)
    )
    return [await request_out(session, r) for r in rows]


async def _gouvernorats(session: AsyncSession, row: ResourceRequest) -> list[int]:
    codes = set(await incidents.all_gouvernorats(session, row.incident_id))
    return sorted(codes | {row.to_gouvernorat_code})


async def _announce(session: AsyncSession, row: ResourceRequest) -> None:
    out = await request_out(session, row)
    await emit(
        session,
        "resource_request.updated",
        {"request": out.model_dump(mode="json"), "gouvernorat_codes": await _gouvernorats(session, row)},
    )


async def _audit(
    session: AsyncSession, principal: Principal, action: str, row: ResourceRequest, reason: str | None, **details: Any
) -> None:
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action=action,
        target=f"incident:{row.incident_id}",
        reason=reason,
        details={"request_id": str(row.id), "to": row.to_gouvernorat_code, "from": row.from_room, **details},
        gouvernorats=await _gouvernorats(session, row),
    )


# ---------------------------------------------------------------- create


async def create(
    session: AsyncSession, principal: Principal, incident: Incident, body: schemas.ResourceRequestIn
) -> ResourceRequest:
    await scope.check_incident(session, principal, incident, Action.RESOURCE_REQUEST_CREATE)
    if incident.status != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "incident_not_open")
    await incidents.valid_gouvernorat(session, body.to_gouvernorat_code)
    if body.to_gouvernorat_code == principal.gouvernorat_code:
        # A region orders its own resources directly (POST /incidents/{id}/assignments).
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_gouvernorat")
    kind: str | None = body.resource_kind
    if body.resource_id is not None:
        found = (
            await session.execute(
                select(Resource.kind, Unit.gouvernorat_code)
                .join(Unit, Unit.id == Resource.unit_id)
                .where(Resource.id == body.resource_id)
            )
        ).first()
        if found is None or found[1] != body.to_gouvernorat_code:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_resource")
        kind = found[0]
    if kind is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "resource_kind_required")
    row = ResourceRequest(
        incident_id=incident.id,
        from_room=scope.room_of(principal),
        to_gouvernorat_code=body.to_gouvernorat_code,
        resource_id=body.resource_id,
        resource_kind=kind,
        quantity=body.quantity,
        reason=body.reason,
        status="pending",
        requested_by=audit.actor_of(principal),
        requested_by_name=audit.name_of(principal),
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    incidents.add_timeline(
        session,
        incident.id,
        "resource_requested",
        audit.actor_of(principal),
        audit.name_of(principal),
        request_id=str(row.id),
        to_gouvernorat_code=row.to_gouvernorat_code,
        resource_kind=kind,
        quantity=row.quantity,
        reason=row.reason,
    )
    await _audit(session, principal, "resource_request.create", row, row.reason, kind=kind, quantity=row.quantity)
    await _announce(session, row)
    return row


# ---------------------------------------------------------------- read


def _visible(principal: Principal) -> Any:
    if principal.is_national:
        return True
    return or_(
        ResourceRequest.to_gouvernorat_code == principal.gouvernorat_code,
        ResourceRequest.from_room == scope.room_of(principal),
    )


def _encode(at: datetime, rid: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{at.isoformat()}|{rid}".encode()).decode().rstrip("=")


def _decode(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        at, rid = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode().split("|", 1)
        return datetime.fromisoformat(at), uuid.UUID(rid)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc


async def list_requests(
    session: AsyncSession,
    principal: Principal,
    statuses: list[str],
    direction: str | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[schemas.ResourceRequestOut], str | None]:
    """Incoming = asked of the caller's gouvernorat (national: all); outgoing = asked by the caller's room."""
    query = select(ResourceRequest).where(_visible(principal))
    if direction == "incoming" and not principal.is_national:
        query = query.where(ResourceRequest.to_gouvernorat_code == principal.gouvernorat_code)
    elif direction == "outgoing":
        query = query.where(ResourceRequest.from_room == scope.room_of(principal))
    if statuses:
        query = query.where(ResourceRequest.status.in_(statuses))
    if cursor:
        at, rid = _decode(cursor)
        query = query.where(
            or_(ResourceRequest.requested_at < at, and_(ResourceRequest.requested_at == at, ResourceRequest.id < rid))
        )
    rows = list(
        await session.scalars(
            query.order_by(ResourceRequest.requested_at.desc(), ResourceRequest.id.desc()).limit(limit)
        )
    )
    items = [await request_out(session, r) for r in rows]
    next_cursor = _encode(rows[-1].requested_at, rows[-1].id) if len(rows) == limit else None
    return items, next_cursor


async def get_visible(
    session: AsyncSession, principal: Principal, request_id: uuid.UUID, lock: bool = False
) -> ResourceRequest:
    """A request of the caller's gouvernorat or room, or of an incident the caller reads; 404 otherwise."""
    row = await session.get(ResourceRequest, request_id, with_for_update=lock)
    if row is None:
        raise scope.not_found()
    if principal.is_national or row.to_gouvernorat_code == principal.gouvernorat_code:
        return row
    if row.from_room == scope.room_of(principal):
        return row
    incident = await session.get(Incident, row.incident_id)
    if incident is None or not await incidents.can_read(session, principal, incident):
        raise scope.not_found()
    return row


# ---------------------------------------------------------------- decisions


async def _decidable(session: AsyncSession, principal: Principal, row: ResourceRequest) -> Incident:
    """Owning region (ops manager, local committee), or the central committee at central command level."""
    incident = await session.get(Incident, row.incident_id, with_for_update=True)
    assert incident is not None
    requester = room_code(row.from_room)
    ctx = Ctx(
        lead=row.to_gouvernorat_code,
        # The requesting room sees its request (403 rather than 404 when it tries to decide it).
        participants=frozenset({requester}) if requester is not None else frozenset(),
        candidates=frozenset(),
        claimed_room=None,
        critical=False,
        command_level=incident.command_level,
    )
    await scope.check(session, principal, Action.RESOURCE_REQUEST_DECIDE, ctx)
    if row.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "request_not_pending")
    return incident


def _decide(row: ResourceRequest, principal: Principal, final: str, note: str | None) -> None:
    row.status, row.decided_at, row.decision_note = final, _now(), note
    row.decided_by, row.decided_by_name = audit.actor_of(principal), audit.name_of(principal)


async def approve(
    session: AsyncSession, principal: Principal, request_id: uuid.UUID, body: schemas.ApproveIn
) -> ResourceRequest:
    row = await get_visible(session, principal, request_id, lock=True)
    incident = await _decidable(session, principal, row)
    if incident.status != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "incident_not_open")
    actor, who = audit.actor_of(principal), _who(principal)
    first = not await session.scalar(select(func.count()).where(Assignment.incident_id == incident.id))
    created: list[Assignment] = []
    for resource_id in sorted(set(body.resource_ids)):
        resource = await session.get(Resource, resource_id, with_for_update=True)
        unit = await session.get(Unit, resource.unit_id) if resource is not None else None
        if resource is None or unit is None or unit.gouvernorat_code != row.to_gouvernorat_code:
            raise scope.forbidden("resource_not_owned")
        if resource.status != "available":
            raise HTTPException(status.HTTP_409_CONFLICT, "resource_busy")
        assignment = Assignment(
            incident_id=incident.id,
            kind="resource",
            resource_id=resource.id,
            request_id=row.id,
            order=row.reason,
            status="ordered",
            created_by=who,
        )
        session.add(assignment)
        resource.status, resource.updated_at = "assigned", _now()
        await session.flush()
        await session.refresh(assignment)
        incidents.add_timeline(
            session,
            incident.id,
            "assignment_created",
            who,
            assignment_id=str(assignment.id),
            resource=resource.label,
            resource_kind=resource.kind,
            request_id=str(row.id),
        )
        created.append(assignment)
    _decide(row, principal, "approved", body.note)
    await incidents.add_participant(session, incident, row.to_gouvernorat_code, actor, "resource_request", who)
    incidents.add_timeline(
        session,
        incident.id,
        "resource_request_approved",
        actor,
        audit.name_of(principal),
        request_id=str(row.id),
        assignment_ids=[str(a.id) for a in created],
        reason=body.note,
    )
    await session.flush()
    if first:
        await interventions.advance_reports(session, incident.id, Status.IN_PROGRESS)
    for assignment in created:
        await interventions.announce_assignment(session, assignment)
        assert assignment.resource_id is not None
        await resources.announce(session, assignment.resource_id)
    await incidents.update_command_level(session, incident, actor)
    await interventions.announce_incident(session, incident)
    await _audit(
        session, principal, "resource_request.approve", row, body.note, assignment_ids=[str(a.id) for a in created]
    )
    await _announce(session, row)
    return row


async def refuse(session: AsyncSession, principal: Principal, request_id: uuid.UUID, reason: str) -> ResourceRequest:
    row = await get_visible(session, principal, request_id, lock=True)
    incident = await _decidable(session, principal, row)
    _decide(row, principal, "refused", reason)
    incidents.add_timeline(
        session,
        incident.id,
        "resource_request_refused",
        audit.actor_of(principal),
        audit.name_of(principal),
        request_id=str(row.id),
        reason=reason,
    )
    await session.flush()
    await _audit(session, principal, "resource_request.refuse", row, reason)
    await _announce(session, row)
    return row


async def cancel(session: AsyncSession, principal: Principal, request_id: uuid.UUID) -> ResourceRequest:
    """The requesting room withdraws a pending request."""
    row = await get_visible(session, principal, request_id, lock=True)
    if row.from_room != scope.room_of(principal):
        raise scope.forbidden("action_not_allowed")
    if row.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "request_not_pending")
    _decide(row, principal, "cancelled", None)
    incidents.add_timeline(
        session,
        row.incident_id,
        "resource_request_cancelled",
        audit.actor_of(principal),
        audit.name_of(principal),
        request_id=str(row.id),
    )
    await session.flush()
    await _audit(session, principal, "resource_request.cancel", row, None)
    await _announce(session, row)
    return row
