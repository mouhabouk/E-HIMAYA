"""The staff app of team leaders (phases P4a and P4b, docs/phase-p4/design-staff.md §4 and §5): device, shift,
missions, steps, situation reports, casualties, alerts from the field, attachments, hospitals and detailed reports.

A team leader sees only the assignments of the vehicle they hold on shift. Every write carries the id the phone
generated (``ops.crew_event``): sent twice, it is applied once and answered with the current state. Steps go through
the room's own rules (``interventions._set_assignment_status``), so the vehicle is freed at the end and the reporters'
tracking moves on («تم التدخل») exactly as when the room presses the button.
"""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from geoalchemy2 import Geography, Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, Role
from app.core.storage import get_store
from app.modules.audit import service as audit
from app.modules.geo.models import Delegation, Layer, LayerFeature
from app.modules.ops import interventions, resources, schemas, templates
from app.modules.ops import service as incidents
from app.modules.ops.domain import ACTIVE_ASSIGNMENT, classification_allowed
from app.modules.ops.models import (
    Assignment,
    CasualtyCount,
    CasualtyTransport,
    CrewAlert,
    CrewEvent,
    FieldAttachment,
    FieldReport,
    Incident,
    Resource,
    Shift,
    StaffDevice,
    TimelineEvent,
    Unit,
)
from app.modules.reports import sniff
from app.modules.reports.domain import Status

DEVICE_REVOKED = "device_revoked"
SEEN_EVERY = timedelta(minutes=1)
#: Released missions stay on the phone for a while, to add a person taken to hospital after the end.
RECENT = timedelta(hours=6)
#: Attachments from the scene (design §5.8): photos compressed on the phone, voice notes of a minute at most.
ATTACHMENT_TYPES = {
    "photo": frozenset({"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}),
    "voice": frozenset({"audio/mp4", "audio/aac", "audio/mpeg", "audio/ogg", "audio/wav", "audio/x-wav", "audio/webm"}),
}
ATTACHMENT_MAX_BYTES = {"photo": 8 * 1024 * 1024, "voice": 4 * 1024 * 1024}
VOICE_MAX_S = 60
ATTACHMENTS_PER_MISSION = 20
HOSPITALS_NEAR = 6
SITUATION_KINDS = ("first", "update")
#: Map layers whose places are offered as hospitals.
HOSPITAL_ICONS = ("hospital", "clinic")


def _now() -> datetime:
    return datetime.now(UTC)


def _who(principal: Principal) -> str:
    return audit.name_of(principal) or audit.actor_of(principal)


# Roles that may hold a staff phone: team leaders, and inspectors for prevention visits (phase P4c).
FIELD_ROLES: tuple[Role, ...] = (Role.TEAM_LEADER, Role.ORG_AUDITOR)


def gouvernorat_of(principal: Principal) -> int:
    """Team leaders and inspectors on a phone work for one gouvernorat; an account without one is refused."""
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
    transported = await session.scalar(
        select(func.count()).select_from(CasualtyTransport).where(CasualtyTransport.incident_id == incident_id)
    )
    if row is None:
        return schemas.CasualtiesOut(transported=transported or 0)
    return schemas.CasualtiesOut(
        injured_light=row.injured_light,
        injured_serious=row.injured_serious,
        deceased=row.deceased,
        rescued=row.rescued,
        trapped=row.trapped,
        transported=transported or 0,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


def _report_out(r: FieldReport, label: str | None = None) -> schemas.FieldReportOut:
    return schemas.FieldReportOut(
        id=r.id,
        assignment_id=r.assignment_id,
        resource_label=label,
        kind=r.kind,
        category=r.category,
        classification=r.classification,
        severity=r.severity,
        backup_needed=r.backup_needed,
        backup_note=r.backup_note,
        backup_kinds=list(r.backup_kinds or []),
        crew_danger=r.crew_danger,
        template_id=r.template_id,
        template_version=r.template_version,
        answers=r.answers,
        note=r.note,
        author_name=r.author_name,
        device_at=r.device_at,
        created_at=r.created_at,
    )


def alert_out(a: CrewAlert, label: str | None = None) -> schemas.AlertOut:
    return schemas.AlertOut(
        id=a.id,
        assignment_id=a.assignment_id,
        resource_label=label,
        kind=a.kind,
        items=list(a.items or []),
        created_by_name=a.created_by_name,
        device_at=a.device_at,
        created_at=a.created_at,
        seen_by_name=a.seen_by_name,
        seen_at=a.seen_at,
    )


def attachment_out(a: FieldAttachment, *, with_url: bool = False) -> schemas.AttachmentOut:
    url = None
    if with_url and a.object_key is not None:
        url = get_store().presign_get(a.object_key, expires_s=600, content_type=a.content_type)
    return schemas.AttachmentOut(
        id=a.id,
        assignment_id=a.assignment_id,
        kind=a.kind,
        body=a.body,
        content_type=a.content_type,
        bytes=a.bytes,
        duration_s=a.duration_s,
        created_by_name=a.created_by_name,
        device_at=a.device_at,
        created_at=a.created_at,
        url=url,
    )


def _transport_out(t: CasualtyTransport) -> schemas.TransportOut:
    return schemas.TransportOut(
        id=t.id,
        assignment_id=t.assignment_id,
        triage=t.triage,
        age_band=t.age_band,
        sex=t.sex,
        hospital=t.hospital,
        hospital_ref=t.hospital_ref,
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
        .where(FieldReport.assignment_id == assignment.id, FieldReport.kind.in_(SITUATION_KINDS))
        .order_by(FieldReport.created_at.desc())
        .limit(1)
    )
    detailed = await session.scalar(
        select(FieldReport)
        .where(FieldReport.assignment_id == assignment.id, FieldReport.kind == "detailed")
        .order_by(FieldReport.created_at.desc())
        .limit(1)
    )
    alerts = await session.scalars(
        select(CrewAlert).where(CrewAlert.assignment_id == assignment.id).order_by(CrewAlert.created_at.desc())
    )
    attachments = await session.scalars(
        select(FieldAttachment)
        .where(FieldAttachment.assignment_id == assignment.id)
        .order_by(FieldAttachment.created_at)
    )
    template = await templates.approved_for(session, incident.category, incident.classification)
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
        detailed_report=_report_out(detailed) if detailed is not None else None,
        casualties=await _casualties(session, incident.id),
        transports=[_transport_out(t) for t in transports],
        alerts=[alert_out(a) for a in alerts],
        attachments=[attachment_out(a) for a in attachments],
        template=templates.template_out(template) if template is not None else None,
        contact_phone=assignment.contact_phone,
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
    """A situation report: the first one of the team, then updates (design §5.5)."""
    assignment, _ = await _mission(session, principal, assignment_id)
    if await _seen(session, body.client_id) is not None:
        return assignment
    if assignment.status not in ("on_scene", "released"):
        raise HTTPException(status.HTTP_409_CONFLICT, "not_on_scene")
    if body.classification is not None and not classification_allowed(body.category, body.classification):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_classification")
    earlier = await session.scalar(
        select(func.count()).where(FieldReport.assignment_id == assignment.id, FieldReport.kind.in_(SITUATION_KINDS))
    )
    kinds = list(dict.fromkeys(body.backup_kinds))
    backup = body.backup_needed or bool(kinds)
    _event(session, principal, body, "first_report", assignment)
    session.add(
        FieldReport(
            incident_id=assignment.incident_id,
            assignment_id=assignment.id,
            kind="update" if earlier else "first",
            category=body.category,
            classification=body.classification,
            severity=body.severity,
            backup_needed=backup,
            backup_kinds=kinds if backup else [],
            backup_note=body.backup_note if backup else None,
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
        report="update" if earlier else "first",
        category=body.category,
        severity=body.severity,
        backup_needed=backup,
        backup_kinds=kinds if backup else [],
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
        row = CasualtyCount(
            incident_id=assignment.incident_id,
            injured_light=0,
            injured_serious=0,
            deceased=0,
            rescued=0,
            trapped=0,
        )
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
    hospital = body.hospital
    if body.hospital_ref is not None:
        place = await session.scalar(
            select(LayerFeature.name)
            .join(Layer, Layer.id == LayerFeature.layer_id)
            .where(LayerFeature.id == body.hospital_ref, Layer.icon.in_(HOSPITAL_ICONS), Layer.enabled.is_(True))
        )
        if place is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown_hospital")
        hospital = place[:120]
    if not hospital:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "hospital_required")
    _event(session, principal, body, "transport", assignment)
    session.add(
        CasualtyTransport(
            incident_id=assignment.incident_id,
            assignment_id=assignment.id,
            triage=body.triage,
            age_band=body.age_band,
            sex=body.sex,
            hospital=hospital,
            hospital_ref=body.hospital_ref,
            created_by=principal.subject,
            created_by_name=audit.name_of(principal),
            device_at=body.device_at,
        )
    )
    _timeline(session, assignment, "transport", _who(principal), triage=body.triage, hospital=hospital)
    await _announce(session, assignment)
    return assignment


async def alert(
    session: AsyncSession, principal: Principal, assignment_id: uuid.UUID, body: schemas.AlertIn
) -> Assignment:
    """ "Backup" or "danger to the crew", at any moment from the order to the end (design §5.4)."""
    assignment, _ = await _mission(session, principal, assignment_id)
    if await _seen(session, body.client_id) is not None:
        return assignment
    allowed = schemas.BACKUP_KINDS if body.kind == "backup" else schemas.DANGER_KINDS
    items = list(dict.fromkeys(body.items))
    if any(i not in allowed for i in items):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_item")
    if assignment.status in ("cancelled",):
        raise HTTPException(status.HTTP_409_CONFLICT, "mission_cancelled")
    _event(session, principal, body, "alert", assignment, {"kind": body.kind, "items": items})
    session.add(
        CrewAlert(
            incident_id=assignment.incident_id,
            assignment_id=assignment.id,
            kind=body.kind,
            items=items,
            created_by=principal.subject,
            created_by_name=audit.name_of(principal),
            device_at=body.device_at,
        )
    )
    _timeline(session, assignment, "crew_alert", _who(principal), alert=body.kind, items=items)
    await _announce(session, assignment)
    return assignment


async def text_note(
    session: AsyncSession, principal: Principal, assignment_id: uuid.UUID, body: schemas.TextNoteIn
) -> Assignment:
    assignment, _ = await _mission(session, principal, assignment_id)
    if await _seen(session, body.client_id) is not None:
        return assignment
    await _room_for_attachment(session, assignment)
    _event(session, principal, body, "attachment", assignment, {"kind": "text"})
    session.add(
        FieldAttachment(
            incident_id=assignment.incident_id,
            assignment_id=assignment.id,
            kind="text",
            body=body.body,
            created_by=principal.subject,
            created_by_name=audit.name_of(principal),
            device_at=body.device_at,
        )
    )
    _timeline(session, assignment, "field_attachment", _who(principal), media="text")
    await _announce(session, assignment)
    return assignment


async def _room_for_attachment(session: AsyncSession, assignment: Assignment) -> None:
    count = await session.scalar(
        select(func.count()).select_from(FieldAttachment).where(FieldAttachment.assignment_id == assignment.id)
    )
    if (count or 0) >= ATTACHMENTS_PER_MISSION:
        raise HTTPException(status.HTTP_409_CONFLICT, "too_many_attachments")


async def upload(
    session: AsyncSession,
    principal: Principal,
    assignment_id: uuid.UUID,
    write: schemas.CrewWrite,
    kind: str,
    content_type: str,
    data: bytes,
    duration_s: float | None,
) -> Assignment:
    """A photo or a voice note sent as the request body; its type is checked from its bytes (design §5.8)."""
    assignment, _ = await _mission(session, principal, assignment_id)
    if await _seen(session, write.client_id) is not None:
        return assignment
    if kind not in ATTACHMENT_TYPES or content_type not in ATTACHMENT_TYPES[kind]:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported_media_type")
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "empty_file")
    if len(data) > ATTACHMENT_MAX_BYTES[kind]:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "media_too_large")
    if kind == "voice" and (duration_s is None or not 0 < duration_s <= VOICE_MAX_S):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_duration")
    if sniff.verify(content_type, data[: sniff.HEAD_BYTES]).reason is not None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "type_mismatch")
    await _room_for_attachment(session, assignment)
    digest = hashlib.sha256(data).hexdigest()
    key = f"field/{assignment.incident_id}/{uuid.uuid4().hex}{sniff.EXTENSIONS.get(content_type, '')}"
    await get_store().put(key, data, content_type)
    _event(session, principal, write, "attachment", assignment, {"kind": kind, "sha256": digest})
    session.add(
        FieldAttachment(
            incident_id=assignment.incident_id,
            assignment_id=assignment.id,
            kind=kind,
            object_key=key,
            content_type=content_type,
            sha256=digest,
            bytes=len(data),
            duration_s=duration_s if kind == "voice" else None,
            created_by=principal.subject,
            created_by_name=audit.name_of(principal),
            device_at=write.device_at,
        )
    )
    _timeline(session, assignment, "field_attachment", _who(principal), media=kind)
    await _announce(session, assignment)
    return assignment


async def detailed_report(
    session: AsyncSession, principal: Principal, assignment_id: uuid.UUID, body: schemas.DetailedReportIn
) -> Assignment:
    """F-STF-05: answers to the approved template of the incident; a new one corrects the previous one."""
    assignment, _ = await _mission(session, principal, assignment_id)
    if await _seen(session, body.client_id) is not None:
        return assignment
    if assignment.status not in ("on_scene", "released"):
        raise HTTPException(status.HTTP_409_CONFLICT, "not_on_scene")
    incident = await session.get(Incident, assignment.incident_id)
    template = await templates.get(session, body.template_id)
    if incident is None or template.status != "approved" or template.category != incident.category:
        raise HTTPException(status.HTTP_409_CONFLICT, "template_not_current")
    answers = templates.check_answers(template.fields, body.answers)
    _event(session, principal, body, "detailed_report", assignment)
    session.add(
        FieldReport(
            incident_id=assignment.incident_id,
            assignment_id=assignment.id,
            kind="detailed",
            category=template.category,
            classification=template.classification or incident.classification,
            template_id=template.id,
            template_version=template.version,
            answers=answers,
            note=body.note,
            author=principal.subject,
            author_name=audit.name_of(principal),
            device_at=body.device_at,
        )
    )
    _timeline(
        session, assignment, "detailed_report", _who(principal), template_version=template.version, answers=len(answers)
    )
    await _announce(session, assignment)
    return assignment


async def hospitals(session: AsyncSession, principal: Principal, assignment_id: uuid.UUID) -> list[schemas.Hospital]:
    """The hospitals of the map layers nearest to the incident (design §5.6)."""
    assignment, _ = await _mission(session, principal, assignment_id)
    incident = await session.get(Incident, assignment.incident_id)
    if incident is None or incident.centroid is None:
        return []
    distance = func.ST_Distance(LayerFeature.location, Incident.centroid)
    rows = (
        await session.execute(
            select(LayerFeature, Layer.simulated, distance)
            .join(Layer, Layer.id == LayerFeature.layer_id)
            .join(Incident, Incident.id == assignment.incident_id)
            .where(Layer.icon.in_(HOSPITAL_ICONS), Layer.enabled.is_(True), LayerFeature.hidden.is_(False))
            .order_by(distance)
            .limit(HOSPITALS_NEAR)
        )
    ).all()
    return [
        schemas.Hospital(id=f.id, name=f.name, phone=f.phone, distance_m=round(d), simulated=bool(sim))
        for f, sim, d in rows
    ]


async def mark_seen(session: AsyncSession, principal: Principal, alert_id: uuid.UUID) -> CrewAlert:
    """The room saw a team's alert; the leader's phone shows it."""
    row = await session.get(CrewAlert, alert_id, with_for_update=True)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await incidents.get_in_scope(session, principal, row.incident_id)
    if row.seen_at is None:
        row.seen_at, row.seen_by, row.seen_by_name = _now(), audit.actor_of(principal), audit.name_of(principal)
        assignment = await session.get(Assignment, row.assignment_id)
        if assignment is not None:
            _timeline(session, assignment, "crew_alert_seen", _who(principal), alert=row.kind)
            await _announce(session, assignment)
    return row


# ---------------------------------------------------------------- the room's view (incident card)


async def incident_field(
    session: AsyncSession, incident_id: uuid.UUID
) -> tuple[
    list[schemas.FieldReportOut],
    schemas.CasualtiesOut | None,
    list[schemas.TransportOut],
    list[schemas.AlertOut],
    list[schemas.AttachmentOut],
]:
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
    transport_list = [_transport_out(t) for t in transports]
    alerts = (
        await session.execute(
            select(CrewAlert, Resource.label)
            .join(Assignment, Assignment.id == CrewAlert.assignment_id)
            .outerjoin(Resource, Resource.id == Assignment.resource_id)
            .where(CrewAlert.incident_id == incident_id)
            .order_by(CrewAlert.created_at.desc())
        )
    ).all()
    attachments = await session.scalars(
        select(FieldAttachment).where(FieldAttachment.incident_id == incident_id).order_by(FieldAttachment.created_at)
    )
    return (
        [_report_out(r, label) for r, label in rows],
        await _casualties(session, incident_id) if counts is not None or transport_list else None,
        transport_list,
        [alert_out(a, label) for a, label in alerts],
        [attachment_out(a, with_url=True) for a in attachments],
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
