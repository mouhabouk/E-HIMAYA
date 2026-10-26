"""The staff app of team leaders (phase P4a, docs/phase-p4/design-staff.md §4): device, shift, missions, steps,
first field report and casualties.

A team leader sees only the assignments of the vehicle they hold on shift. Every write carries the id the phone
generated (``ops.crew_event``): sent twice, it is applied once and answered with the current state. Steps go through
the room's own rules (``interventions._set_assignment_status``), so the vehicle is freed at the end and the reporters'
tracking moves on («تم التدخل») exactly as when the room presses the button.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from geoalchemy2 import Geography, Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.modules.audit import service as audit
from app.modules.geo.models import Delegation
from app.modules.ops import interventions, resources, schemas
from app.modules.ops import service as incidents
from app.modules.ops.domain import ACTIVE_ASSIGNMENT, classification_allowed
from app.modules.ops.models import (
    Assignment,
    CasualtyCount,
    CasualtyTransport,
    CrewEvent,
    FieldReport,
    Incident,
    Resource,
    Shift,
    StaffDevice,
    TimelineEvent,
    Unit,
)
from app.modules.reports.domain import Status

DEVICE_REVOKED = "device_revoked"
SEEN_EVERY = timedelta(minutes=1)
#: Released missions stay on the phone for a while, to add a person taken to hospital after the end.
RECENT = timedelta(hours=6)


def _now() -> datetime:
    return datetime.now(UTC)


def _who(principal: Principal) -> str:
    return audit.name_of(principal) or audit.actor_of(principal)


def gouvernorat_of(principal: Principal) -> int:
    """Team leaders work for one gouvernorat; an account without one is refused."""
    if principal.gouvernorat_code is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "regional_account_required")
    return principal.gouvernorat_code


# ---------------------------------------------------------------- device


async def register_device(session: AsyncSession, principal: Principal, body: schemas.DeviceIn) -> StaffDevice:
    device = StaffDevice(
        subject=principal.subject,
        holder_name=audit.name_of(principal),
        gouvernorat_code=gouvernorat_of(principal),
        label=body.label,
        platform=body.platform,
        app_build=body.app_build,
        push_token=body.push_token,
    )
    session.add(device)
    await session.flush()
    await session.refresh(device)
    return device


async def current_device(session: AsyncSession, principal: Principal, device_id: uuid.UUID | None) -> StaffDevice:
    """The phone making the request (``X-Staff-Device``). A revoked phone gets ``410 device_revoked``: the app
    erases everything it holds (remote wipe)."""
    if device_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "device_required")
    device = await session.get(StaffDevice, device_id)
    if device is None or device.subject != principal.subject:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "device_unknown")
    if device.revoked_at is not None:
        raise HTTPException(status.HTTP_410_GONE, DEVICE_REVOKED)
    if _now() - device.last_seen_at > SEEN_EVERY:
        device.last_seen_at = _now()
    return device


def device_out(device: StaffDevice, on_shift: bool = False) -> schemas.DeviceOut:
    return schemas.DeviceOut(
        id=device.id,
        holder_name=device.holder_name,
        label=device.label,
        platform=device.platform,
        app_build=device.app_build,
        created_at=device.created_at,
        last_seen_at=device.last_seen_at,
        revoked_at=device.revoked_at,
        on_shift=on_shift,
    )


# ---------------------------------------------------------------- shift


async def open_shift(session: AsyncSession, principal: Principal) -> Shift | None:
    return await session.scalar(select(Shift).where(Shift.subject == principal.subject, Shift.ended_at.is_(None)))


async def shift_out(session: AsyncSession, shift: Shift) -> schemas.ShiftOut:
    resource, unit = (
        await session.execute(
            select(Resource, Unit).join(Unit, Unit.id == Resource.unit_id).where(Resource.id == shift.resource_id)
        )
    ).one()
    return schemas.ShiftOut(
        id=shift.id,
        resource=schemas.ResourceRef(id=resource.id, label=resource.label, kind=resource.kind, unit_name=unit.name_ar),
        crew_size=shift.crew_size,
        crew_names=shift.crew_names,
        started_at=shift.started_at,
        ended_at=shift.ended_at,
    )


async def vehicles(session: AsyncSession, principal: Principal) -> list[schemas.CrewResource]:
    """The vehicles of the leader's gouvernorat, with the ones already on another shift marked."""
    own = gouvernorat_of(principal)
    taken = select(Shift.resource_id).where(Shift.ended_at.is_(None)).scalar_subquery()
    rows = (
        await session.execute(
            select(Resource, Unit, Resource.id.in_(taken))
            .join(Unit, Unit.id == Resource.unit_id)
            .where(Unit.gouvernorat_code == own, Resource.status != "out_of_service")
            .order_by(Unit.name_ar, Resource.label)
        )
    ).all()
    return [
        schemas.CrewResource(
            id=r.id, label=r.label, kind=r.kind, unit_name=u.name_ar, status=r.status, on_shift=bool(on_shift)
        )
        for r, u, on_shift in rows
    ]


async def start_shift(session: AsyncSession, principal: Principal, device: StaffDevice, body: schemas.ShiftIn) -> Shift:
    own = gouvernorat_of(principal)
    if await open_shift(session, principal) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "shift_open")
    row = (
        await session.execute(
            select(Resource, Unit).join(Unit, Unit.id == Resource.unit_id).where(Resource.id == body.resource_id)
        )
    ).first()
    if row is None or row[1].gouvernorat_code != own:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if row[0].status == "out_of_service":
        raise HTTPException(status.HTTP_409_CONFLICT, "resource_out_of_service")
    shift = Shift(
        subject=principal.subject,
        leader_name=audit.name_of(principal),
        device_id=device.id,
        resource_id=body.resource_id,
        gouvernorat_code=own,
        crew_size=body.crew_size,
        crew_names=body.crew_names,
    )
    session.add(shift)
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "resource_on_shift") from exc
    # Missions already given to this vehicle and still running belong to the new shift.
    for a in await session.scalars(
        select(Assignment).where(Assignment.resource_id == body.resource_id, Assignment.status.in_(ACTIVE_ASSIGNMENT))
    ):
        a.shift_id = shift.id
    await session.refresh(shift)
    return shift


async def end_shift(session: AsyncSession, principal: Principal) -> Shift:
    shift = await open_shift(session, principal)
    if shift is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_open_shift")
    active = await session.scalar(
        select(func.count()).where(
            Assignment.resource_id == shift.resource_id, Assignment.status.in_(ACTIVE_ASSIGNMENT)
        )
    )
    if active:
        raise HTTPException(status.HTTP_409_CONFLICT, "mission_active")
    shift.ended_at = _now()
    await session.flush()
    return shift


# ---------------------------------------------------------------- missions


async def _casualties(session: AsyncSession, incident_id: uuid.UUID) -> schemas.CasualtiesOut:
    row = await session.get(CasualtyCount, incident_id)
    if row is None:
        return schemas.CasualtiesOut()
    return schemas.CasualtiesOut(
        injured=row.injured,
        deceased=row.deceased,
        rescued=row.rescued,
        trapped=row.trapped,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


def _report_out(r: FieldReport, label: str | None = None) -> schemas.FieldReportOut:
    return schemas.FieldReportOut(
        id=r.id,
        assignment_id=r.assignment_id,
        resource_label=label,
        category=r.category,
        classification=r.classification,
        severity=r.severity,
        backup_needed=r.backup_needed,
        backup_note=r.backup_note,
        crew_danger=r.crew_danger,
        author_name=r.author_name,
        device_at=r.device_at,
        created_at=r.created_at,
    )


def _transport_out(t: CasualtyTransport) -> schemas.TransportOut:
    return schemas.TransportOut(
        id=t.id,
        assignment_id=t.assignment_id,
        triage=t.triage,
        age_band=t.age_band,
        sex=t.sex,
        hospital=t.hospital,
        created_by_name=t.created_by_name,
        device_at=t.device_at,
        created_at=t.created_at,
    )


async def mission_out(session: AsyncSession, assignment: Assignment) -> schemas.MissionOut:
    lat = func.ST_Y(cast(Incident.centroid, Geometry))
    lon = func.ST_X(cast(Incident.centroid, Geometry))
    incident, y, x, d = (
        await session.execute(
            select(Incident, lat, lon, Delegation)
            .outerjoin(Delegation, Delegation.id == Incident.delegation_id)
            .where(Incident.id == assignment.incident_id)
        )
    ).one()
    report = await session.scalar(
        select(FieldReport)
        .where(FieldReport.assignment_id == assignment.id)
        .order_by(FieldReport.created_at.desc())
        .limit(1)
    )
    transports = await session.scalars(
        select(CasualtyTransport)
        .where(CasualtyTransport.assignment_id == assignment.id)
        .order_by(CasualtyTransport.created_at)
    )
    last_distance = await session.scalar(
        select(CrewEvent.payload["distance_m"].as_integer())
        .where(CrewEvent.assignment_id == assignment.id, CrewEvent.payload.has_key("distance_m"))
        .order_by(CrewEvent.received_at.desc())
        .limit(1)
    )
    return schemas.MissionOut(
        id=assignment.id,
        status=assignment.status,
        order=assignment.order,
        created_at=assignment.created_at,
        acknowledged_at=assignment.acknowledged_at,
        en_route_at=assignment.en_route_at,
        on_scene_at=assignment.on_scene_at,
        released_at=assignment.released_at,
        cancelled_at=assignment.cancelled_at,
        incident=schemas.MissionIncident(
            id=incident.id,
            category=incident.category,
            classification=incident.classification,
            title=incident.title,
            location=schemas.Point(lat=y, lon=x) if y is not None and x is not None else None,
            gouvernorat_code=incident.gouvernorat_code,
            delegation_ar=d.name_ar if d is not None else None,
            delegation_fr=d.name_fr if d is not None else None,
            op_level=incident.op_level,
            status=incident.status,
        ),
        field_report=_report_out(report) if report is not None else None,
        casualties=await _casualties(session, incident.id),
        transports=[_transport_out(t) for t in transports],
        distance_m=last_distance,
    )


async def missions(session: AsyncSession, principal: Principal) -> list[schemas.MissionOut]:
    """Running missions of the vehicle on shift, then the ones it ended in the last hours (newest first)."""
    shift = await open_shift(session, principal)
    if shift is None:
        return []
    since = max(shift.started_at, _now() - RECENT)
    rows = await session.scalars(
        select(Assignment)
        .where(
            Assignment.resource_id == shift.resource_id,
            (Assignment.status.in_(ACTIVE_ASSIGNMENT))
            | (func.coalesce(Assignment.released_at, Assignment.cancelled_at) >= since),
        )
        .order_by(Assignment.status.in_(ACTIVE_ASSIGNMENT).desc(), Assignment.created_at.desc())
    )
    return [await mission_out(session, a) for a in rows]


async def _mission(session: AsyncSession, principal: Principal, assignment_id: uuid.UUID) -> tuple[Assignment, Shift]:
    """An assignment of the vehicle the leader holds on shift; anything else is not found."""
    shift = await open_shift(session, principal)
    if shift is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no_open_shift")
    assignment = await session.get(Assignment, assignment_id, with_for_update=True)
    if assignment is None or assignment.resource_id != shift.resource_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if assignment.shift_id is None:
        assignment.shift_id = shift.id
    return assignment, shift


async def _seen(session: AsyncSession, client_id: uuid.UUID) -> CrewEvent | None:
    return await session.get(CrewEvent, client_id)


def _event(
    session: AsyncSession,
    principal: Principal,
    body: schemas.CrewWrite,
    kind: str,
    assignment: Assignment,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        CrewEvent(
            client_id=body.client_id,
            assignment_id=assignment.id,
            shift_id=assignment.shift_id,
            kind=kind,
            payload=payload or {},
            subject=principal.subject,
            device_at=body.device_at,
        )
    )


def _timeline(session: AsyncSession, assignment: Assignment, kind: str, actor: str, **payload: Any) -> None:
    session.add(
        TimelineEvent(
            incident_id=assignment.incident_id,
            kind=kind,
            actor=actor,
            payload={"assignment_id": str(assignment.id), **payload},
        )
    )


async def _announce(session: AsyncSession, assignment: Assignment) -> None:
    await session.flush()
    await interventions.announce_assignment(session, assignment)
    incident = await session.get(Incident, assignment.incident_id)
    if incident is not None:
        await interventions.announce_incident(session, incident)


async def acknowledge(
    session: AsyncSession, principal: Principal, assignment_id: uuid.UUID, body: schemas.CrewWrite
) -> Assignment:
    assignment, _ = await _mission(session, principal, assignment_id)
    if await _seen(session, body.client_id) is not None:
        return assignment
    _event(session, principal, body, "ack", assignment)
    if assignment.acknowledged_at is None:
        assignment.acknowledged_at = _now()
        _timeline(session, assignment, "crew_ack", _who(principal))
        await _announce(session, assignment)
    return assignment


async def _distance_m(session: AsyncSession, incident_id: uuid.UUID, lat: float, lon: float) -> int | None:
    incident = await session.get(Incident, incident_id)
    if incident is None or incident.centroid is None:
        return None
    point = cast(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), Geography)
    meters = await session.scalar(select(func.ST_Distance(Incident.centroid, point)).where(Incident.id == incident_id))
    return round(meters) if meters is not None else None


async def step(
    session: AsyncSession, principal: Principal, assignment_id: uuid.UUID, body: schemas.StepIn
) -> Assignment:
    assignment, _ = await _mission(session, principal, assignment_id)
    if await _seen(session, body.client_id) is not None:
        return assignment
    payload: dict[str, Any] = {"status": body.status}
    if body.lat is not None and body.lon is not None:
        distance = await _distance_m(session, assignment.incident_id, body.lat, body.lon)
        if distance is not None:
            payload["distance_m"] = distance
    _event(session, principal, body, "status", assignment, payload)
    if assignment.acknowledged_at is None:
        assignment.acknowledged_at = _now()
    await interventions._set_assignment_status(session, assignment, body.status, _who(principal))
    if body.status == "on_scene":
        await interventions.advance_reports(session, assignment.incident_id, Status.INTERVENED)
    await _announce(session, assignment)
    if assignment.resource_id is not None:
        await resources.announce(session, assignment.resource_id)
    return assignment


async def first_report(
    session: AsyncSession, principal: Principal, assignment_id: uuid.UUID, body: schemas.FirstReportIn
) -> Assignment:
    assignment, _ = await _mission(session, principal, assignment_id)
    if await _seen(session, body.client_id) is not None:
        return assignment
    if assignment.status not in ("on_scene", "released"):
        raise HTTPException(status.HTTP_409_CONFLICT, "not_on_scene")
    if body.classification is not None and not classification_allowed(body.category, body.classification):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_classification")
    _event(session, principal, body, "first_report", assignment)
    session.add(
        FieldReport(
            incident_id=assignment.incident_id,
            assignment_id=assignment.id,
            category=body.category,
            classification=body.classification,
            severity=body.severity,
            backup_needed=body.backup_needed,
            backup_note=body.backup_note if body.backup_needed else None,
            crew_danger=body.crew_danger,
            author=principal.subject,
            author_name=audit.name_of(principal),
            device_at=body.device_at,
        )
    )
    _timeline(
        session,
        assignment,
        "field_report",
        _who(principal),
        category=body.category,
        severity=body.severity,
        backup_needed=body.backup_needed,
        crew_danger=body.crew_danger,
    )
    await _announce(session, assignment)
    return assignment


async def casualties(
    session: AsyncSession, principal: Principal, assignment_id: uuid.UUID, body: schemas.CasualtiesIn
) -> Assignment:
    assignment, _ = await _mission(session, principal, assignment_id)
    if await _seen(session, body.client_id) is not None:
        return assignment
    deltas = {k: getattr(body, k) for k in schemas.COUNTERS if getattr(body, k)}
    _event(session, principal, body, "casualties", assignment, deltas)
    if not deltas:
        return assignment
    row = await session.get(CasualtyCount, assignment.incident_id, with_for_update=True)
    if row is None:
        row = CasualtyCount(incident_id=assignment.incident_id, injured=0, deceased=0, rescued=0, trapped=0)
        session.add(row)
    for key, delta in deltas.items():
        setattr(row, key, max(0, min(10_000, getattr(row, key) + delta)))
    row.updated_by, row.updated_at = _who(principal), _now()
    _timeline(session, assignment, "casualties", _who(principal), **{k: getattr(row, k) for k in schemas.COUNTERS})
    await _announce(session, assignment)
    return assignment


async def transport(
    session: AsyncSession, principal: Principal, assignment_id: uuid.UUID, body: schemas.TransportIn
) -> Assignment:
    assignment, _ = await _mission(session, principal, assignment_id)
    if await _seen(session, body.client_id) is not None:
        return assignment
    if assignment.status not in ("on_scene", "released"):
        raise HTTPException(status.HTTP_409_CONFLICT, "not_on_scene")
    _event(session, principal, body, "transport", assignment)
    session.add(
        CasualtyTransport(
            incident_id=assignment.incident_id,
            assignment_id=assignment.id,
            triage=body.triage,
            age_band=body.age_band,
            sex=body.sex,
            hospital=body.hospital,
            created_by=principal.subject,
            created_by_name=audit.name_of(principal),
            device_at=body.device_at,
        )
    )
    _timeline(session, assignment, "transport", _who(principal), triage=body.triage, hospital=body.hospital)
    await _announce(session, assignment)
    return assignment


# ---------------------------------------------------------------- the room's view (incident card)


async def incident_field(
    session: AsyncSession, incident_id: uuid.UUID
) -> tuple[list[schemas.FieldReportOut], schemas.CasualtiesOut | None, list[schemas.TransportOut]]:
    rows = (
        await session.execute(
            select(FieldReport, Resource.label)
            .join(Assignment, Assignment.id == FieldReport.assignment_id)
            .outerjoin(Resource, Resource.id == Assignment.resource_id)
            .where(FieldReport.incident_id == incident_id)
            .order_by(FieldReport.created_at.desc())
        )
    ).all()
    counts = await session.get(CasualtyCount, incident_id)
    transports = await session.scalars(
        select(CasualtyTransport)
        .where(CasualtyTransport.incident_id == incident_id)
        .order_by(CasualtyTransport.created_at)
    )
    return (
        [_report_out(r, label) for r, label in rows],
        await _casualties(session, incident_id) if counts is not None else None,
        [_transport_out(t) for t in transports],
    )


async def audit_write(session: AsyncSession, principal: Principal, action: str, assignment: Assignment) -> None:
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action=action,
        target=f"incident:{assignment.incident_id}",
        details={"assignment_id": str(assignment.id)},
        gouvernorats=await incidents.all_gouvernorats(session, assignment.incident_id),
    )
