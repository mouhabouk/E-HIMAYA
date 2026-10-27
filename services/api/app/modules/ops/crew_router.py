"""Staff app endpoints (phases P4a and P4b, docs/phase-p4/design-staff.md §4 and §5), the room's view of devices,
shifts and alerts, and the Office's report templates.

``/api/v1/crew/*`` is for team leaders (staff realm, second factor, a gouvernorat); since phase P4c inspectors
(``org_auditor``) register their phone the same way for prevention visits (``/api/v1/crew/prevention/*``). Every call
but the device registration names the phone in ``X-Staff-Device``; a revoked phone gets ``410 device_revoked``.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.ops import crew, schemas, templates
from app.modules.ops import service as incidents
from app.modules.ops.models import Assignment, CrewAlert, Shift, StaffDevice
from app.modules.reports.staff_router import READ_ROLES, WRITE_ROLES

router = APIRouter(prefix="/api/v1/crew", tags=["crew"])
staff_router = APIRouter(prefix="/api/v1/staff", tags=["crew"])

Leader = Annotated[Principal, Depends(require_roles(Role.TEAM_LEADER))]
# Who may hold a staff phone: team leaders, and inspectors for prevention visits (P4c).
FieldStaff = Annotated[Principal, Depends(require_roles(*crew.FIELD_ROLES))]
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
DeviceAdmin = Annotated[Principal, Depends(require_roles(Role.REGIONAL_ACCOUNT_ADMIN, Role.SECURITY_ADMIN))]
# The room marks a team's alert seen (operations, field command, central command).
AlertReader = Annotated[Principal, Depends(require_roles(*WRITE_ROLES, Role.CENTRAL_COMMITTEE))]
TemplateReader = Annotated[Principal, Depends(require_roles(*READ_ROLES, Role.TEAM_LEADER))]
Session = Annotated[AsyncSession, Depends(get_session)]
DeviceId = Annotated[uuid.UUID | None, Header(alias="X-Staff-Device")]


async def _device(principal: Leader, session: Session, device_id: DeviceId = None) -> StaffDevice:
    return await crew.current_device(session, principal, device_id)


async def _field_device(principal: FieldStaff, session: Session, device_id: DeviceId = None) -> StaffDevice:
    return await crew.current_device(session, principal, device_id)


Device = Annotated[StaffDevice, Depends(_device)]
FieldDevice = Annotated[StaffDevice, Depends(_field_device)]


@router.post("/devices", response_model=schemas.DeviceOut, status_code=status.HTTP_201_CREATED)
async def register_device(principal: FieldStaff, session: Session, body: schemas.DeviceIn) -> schemas.DeviceOut:
    device = await crew.register_device(session, principal, body)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="crew.device_register",
        target=f"staff_device:{device.id}",
        details={"platform": body.platform, "label": body.label},
        gouvernorats=[device.gouvernorat_code],
    )
    await session.commit()
    return crew.device_out(device)


@router.patch("/devices/current", response_model=schemas.DeviceOut)
async def update_device(
    principal: FieldStaff, session: Session, device: FieldDevice, body: schemas.DevicePatch
) -> schemas.DeviceOut:
    if body.push_token is not None:
        device.push_token = body.push_token
    if body.app_build is not None:
        device.app_build = body.app_build
    await session.commit()
    return crew.device_out(device)


@router.get("/me", response_model=schemas.CrewMe)
async def me(principal: FieldStaff, session: Session, device: FieldDevice) -> schemas.CrewMe:
    shift = await crew.open_shift(session, principal)
    out = schemas.CrewMe(
        name=audit.name_of(principal),
        roles=[r.value for r in crew.FIELD_ROLES if r in principal.roles],
        gouvernorat_code=crew.gouvernorat_of(principal),
        device=crew.device_out(device, on_shift=shift is not None and shift.device_id == device.id),
        shift=await crew.shift_out(session, shift) if shift is not None else None,
    )
    await session.commit()
    return out


@router.get("/resources", response_model=list[schemas.CrewResource])
async def vehicles(principal: Leader, session: Session, _device: Device) -> list[schemas.CrewResource]:
    return await crew.vehicles(session, principal)


@router.post("/shifts", response_model=schemas.ShiftOut, status_code=status.HTTP_201_CREATED)
async def start_shift(principal: Leader, session: Session, device: Device, body: schemas.ShiftIn) -> schemas.ShiftOut:
    shift = await crew.start_shift(session, principal, device, body)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="crew.shift_start",
        target=f"shift:{shift.id}",
        details={"resource_id": str(body.resource_id), "crew_size": body.crew_size},
        gouvernorats=[shift.gouvernorat_code],
    )
    await session.commit()
    return await crew.shift_out(session, shift)


@router.post("/shifts/current/end", response_model=schemas.ShiftOut)
async def end_shift(principal: Leader, session: Session, _device: Device) -> schemas.ShiftOut:
    shift = await crew.end_shift(session, principal)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="crew.shift_end",
        target=f"shift:{shift.id}",
        gouvernorats=[shift.gouvernorat_code],
    )
    await session.commit()
    return await crew.shift_out(session, shift)


@router.get("/missions", response_model=schemas.MissionPage)
async def missions(principal: Leader, session: Session, _device: Device) -> schemas.MissionPage:
    items = await crew.missions(session, principal)
    await session.commit()
    return schemas.MissionPage(items=items)


async def _answer(
    session: AsyncSession, principal: Principal, action: str, assignment: Assignment
) -> schemas.MissionOut:
    await crew.audit_write(session, principal, action, assignment)
    await session.commit()
    return await crew.mission_out(session, assignment)


@router.post("/missions/{assignment_id}/ack", response_model=schemas.MissionOut)
async def acknowledge(
    principal: Leader, session: Session, _device: Device, assignment_id: uuid.UUID, body: schemas.CrewWrite
) -> schemas.MissionOut:
    assignment = await crew.acknowledge(session, principal, assignment_id, body)
    return await _answer(session, principal, "crew.ack", assignment)


@router.post("/missions/{assignment_id}/status", response_model=schemas.MissionOut)
async def step(
    principal: Leader, session: Session, _device: Device, assignment_id: uuid.UUID, body: schemas.StepIn
) -> schemas.MissionOut:
    assignment = await crew.step(session, principal, assignment_id, body)
    return await _answer(session, principal, "crew.status", assignment)


@router.post("/missions/{assignment_id}/first-report", response_model=schemas.MissionOut)
async def first_report(
    principal: Leader, session: Session, _device: Device, assignment_id: uuid.UUID, body: schemas.FirstReportIn
) -> schemas.MissionOut:
    assignment = await crew.first_report(session, principal, assignment_id, body)
    return await _answer(session, principal, "crew.first_report", assignment)


@router.post("/missions/{assignment_id}/situation", response_model=schemas.MissionOut)
async def situation(
    principal: Leader, session: Session, _device: Device, assignment_id: uuid.UUID, body: schemas.FirstReportIn
) -> schemas.MissionOut:
    """A situation report (phase P4b): the first one, then updates. ``/first-report`` is the same call."""
    assignment = await crew.first_report(session, principal, assignment_id, body)
    return await _answer(session, principal, "crew.situation", assignment)


@router.post("/missions/{assignment_id}/casualties", response_model=schemas.MissionOut)
async def casualties(
    principal: Leader, session: Session, _device: Device, assignment_id: uuid.UUID, body: schemas.CasualtiesIn
) -> schemas.MissionOut:
    assignment = await crew.casualties(session, principal, assignment_id, body)
    return await _answer(session, principal, "crew.casualties", assignment)


@router.post("/missions/{assignment_id}/transports", response_model=schemas.MissionOut)
async def transport(
    principal: Leader, session: Session, _device: Device, assignment_id: uuid.UUID, body: schemas.TransportIn
) -> schemas.MissionOut:
    assignment = await crew.transport(session, principal, assignment_id, body)
    return await _answer(session, principal, "crew.transport", assignment)


@router.post("/missions/{assignment_id}/alerts", response_model=schemas.MissionOut)
async def alert(
    principal: Leader, session: Session, _device: Device, assignment_id: uuid.UUID, body: schemas.AlertIn
) -> schemas.MissionOut:
    assignment = await crew.alert(session, principal, assignment_id, body)
    return await _answer(session, principal, f"crew.alert_{body.kind}", assignment)


@router.post("/missions/{assignment_id}/notes", response_model=schemas.MissionOut)
async def text_note(
    principal: Leader, session: Session, _device: Device, assignment_id: uuid.UUID, body: schemas.TextNoteIn
) -> schemas.MissionOut:
    assignment = await crew.text_note(session, principal, assignment_id, body)
    return await _answer(session, principal, "crew.note", assignment)


async def _body(request: Request, limit: int) -> bytes:
    """The request body, refused as soon as it grows past ``limit``."""
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "media_too_large")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/missions/{assignment_id}/attachments",
    response_model=schemas.MissionOut,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                t: {"schema": {"type": "string", "format": "binary"}}
                for t in sorted(crew.ATTACHMENT_TYPES["photo"] | crew.ATTACHMENT_TYPES["voice"])
            },
        }
    },
)
async def upload(
    principal: Leader,
    session: Session,
    _device: Device,
    request: Request,
    assignment_id: uuid.UUID,
    kind: Annotated[str, Query(pattern="^(photo|voice)$")],
    client_id: uuid.UUID,
    device_at: datetime | None = None,
    duration_s: Annotated[float | None, Query(gt=0, le=crew.VOICE_MAX_S)] = None,
) -> schemas.MissionOut:
    """A photo or a voice note as the raw request body, with its type in ``Content-Type`` (phase P4b)."""
    content_type = (request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    data = await _body(request, crew.ATTACHMENT_MAX_BYTES[kind])
    write = schemas.CrewWrite(client_id=client_id, device_at=device_at)
    assignment = await crew.upload(session, principal, assignment_id, write, kind, content_type, data, duration_s)
    return await _answer(session, principal, f"crew.{kind}", assignment)


@router.post("/missions/{assignment_id}/detailed-report", response_model=schemas.MissionOut)
async def detailed_report(
    principal: Leader, session: Session, _device: Device, assignment_id: uuid.UUID, body: schemas.DetailedReportIn
) -> schemas.MissionOut:
    assignment = await crew.detailed_report(session, principal, assignment_id, body)
    return await _answer(session, principal, "crew.detailed_report", assignment)


@router.get("/missions/{assignment_id}/hospitals", response_model=list[schemas.Hospital])
async def hospitals(
    principal: Leader, session: Session, _device: Device, assignment_id: uuid.UUID
) -> list[schemas.Hospital]:
    out = await crew.hospitals(session, principal, assignment_id)
    await session.commit()
    return out


# ---------------------------------------------------------------- the room and the account administrators


class ShiftRow(schemas.ShiftOut):
    leader_name: str | None
    gouvernorat_code: int
    #: Backup and danger alerts of the team the room has not marked as seen yet (phase P4b).
    unseen_alerts: int = 0


@staff_router.get("/shifts", response_model=list[ShiftRow])
async def open_shifts(principal: Reader, session: Session) -> list[ShiftRow]:
    """Teams on duty (vehicle, leader, crew) in the caller's scope."""
    query = select(Shift).where(Shift.ended_at.is_(None)).order_by(Shift.started_at)
    if principal.gouvernorat_code is not None:
        query = query.where(Shift.gouvernorat_code == principal.gouvernorat_code)
    out = []
    for shift in await session.scalars(query):
        base = await crew.shift_out(session, shift)
        unseen = await session.scalar(
            select(func.count(CrewAlert.id))
            .join(Assignment, Assignment.id == CrewAlert.assignment_id)
            .where(Assignment.shift_id == shift.id, CrewAlert.seen_at.is_(None))
        )
        out.append(
            ShiftRow(
                **base.model_dump(),
                leader_name=shift.leader_name,
                gouvernorat_code=shift.gouvernorat_code,
                unseen_alerts=unseen or 0,
            )
        )
    return out


class DeviceRow(schemas.DeviceOut):
    gouvernorat_code: int


@staff_router.get("/crew-devices", response_model=list[DeviceRow])
async def crew_devices(
    principal: DeviceAdmin, session: Session, revoked: Annotated[bool, Query()] = False
) -> list[DeviceRow]:
    """Team leaders' phones of the caller's gouvernorat (all of them for the national security administrator)."""
    query = select(StaffDevice).order_by(StaffDevice.last_seen_at.desc()).limit(500)
    if not revoked:
        query = query.where(StaffDevice.revoked_at.is_(None))
    if principal.gouvernorat_code is not None:
        query = query.where(StaffDevice.gouvernorat_code == principal.gouvernorat_code)
    on_shift = set(await session.scalars(select(Shift.device_id).where(Shift.ended_at.is_(None))))
    return [
        DeviceRow(**crew.device_out(d, d.id in on_shift).model_dump(), gouvernorat_code=d.gouvernorat_code)
        for d in await session.scalars(query)
    ]


@staff_router.post("/crew-devices/{device_id}/revoke", response_model=DeviceRow)
async def revoke_device(principal: DeviceAdmin, session: Session, device_id: uuid.UUID) -> DeviceRow:
    """Remote wipe: the phone erases everything at its next call. An open shift on it is ended."""
    device = await session.get(StaffDevice, device_id, with_for_update=True)
    if device is None or not principal.can_access_gouvernorat(device.gouvernorat_code):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if device.revoked_at is None:
        device.revoked_at, device.revoked_by = datetime.now(UTC), audit.actor_of(principal)
        for shift in await session.scalars(select(Shift).where(Shift.device_id == device.id, Shift.ended_at.is_(None))):
            shift.ended_at = device.revoked_at
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action="crew.device_revoke",
            target=f"staff_device:{device.id}",
            gouvernorats=[device.gouvernorat_code],
        )
        await session.commit()
    return DeviceRow(**crew.device_out(device).model_dump(), gouvernorat_code=device.gouvernorat_code)


@staff_router.post("/crew-alerts/{alert_id}/seen", response_model=schemas.AlertOut)
async def alert_seen(principal: AlertReader, session: Session, alert_id: uuid.UUID) -> schemas.AlertOut:
    row = await crew.mark_seen(session, principal, alert_id)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="crew.alert_seen",
        target=f"incident:{row.incident_id}",
        details={"alert_id": str(row.id), "kind": row.kind},
        gouvernorats=await incidents.all_gouvernorats(session, row.incident_id),
    )
    await session.commit()
    return crew.alert_out(row)


# ---------------------------------------------------------------- report templates (F-STF-05)


def _office(
    principal: Annotated[Principal, Depends(require_roles(Role.CENTRAL_COMMITTEE, Role.OPS_MANAGER))],
) -> Principal:
    """Templates are the Office's: central command or a national operations manager."""
    allowed = Role.CENTRAL_COMMITTEE in principal.roles or (
        Role.OPS_MANAGER in principal.roles and principal.gouvernorat_code is None
    )
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "office_only")
    return principal


TemplateAdmin = Annotated[Principal, Depends(_office)]


@staff_router.get("/report-templates", response_model=list[schemas.TemplateOut])
async def list_templates(
    _principal: TemplateReader, session: Session, retired: Annotated[bool, Query()] = False
) -> list[schemas.TemplateOut]:
    return [templates.template_out(t) for t in await templates.list_templates(session, retired)]


async def _template_audit(session: AsyncSession, principal: Principal, action: str, template_id: uuid.UUID) -> None:
    await audit.record(session, actor=audit.actor_of(principal), action=action, target=f"report_template:{template_id}")


@staff_router.post("/report-templates", response_model=schemas.TemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(principal: TemplateAdmin, session: Session, body: schemas.TemplateIn) -> schemas.TemplateOut:
    t = await templates.create_draft(session, principal, body)
    await _template_audit(session, principal, "template.draft", t.id)
    await session.commit()
    return templates.template_out(t)


@staff_router.patch("/report-templates/{template_id}", response_model=schemas.TemplateOut)
async def edit_template(
    principal: TemplateAdmin, session: Session, template_id: uuid.UUID, body: schemas.TemplatePatch
) -> schemas.TemplateOut:
    t = await templates.edit_draft(session, await templates.get(session, template_id, lock=True), body)
    await _template_audit(session, principal, "template.edit", t.id)
    await session.commit()
    return templates.template_out(t)


@staff_router.post("/report-templates/{template_id}/approve", response_model=schemas.TemplateOut)
async def approve_template(principal: TemplateAdmin, session: Session, template_id: uuid.UUID) -> schemas.TemplateOut:
    t = await templates.approve(session, principal, await templates.get(session, template_id, lock=True))
    await _template_audit(session, principal, "template.approve", t.id)
    await session.commit()
    return templates.template_out(t)


@staff_router.post("/report-templates/{template_id}/retire", response_model=schemas.TemplateOut)
async def retire_template(principal: TemplateAdmin, session: Session, template_id: uuid.UUID) -> schemas.TemplateOut:
    t = await templates.retire(session, await templates.get(session, template_id, lock=True))
    await _template_audit(session, principal, "template.retire", t.id)
    await session.commit()
    return templates.template_out(t)


@staff_router.delete("/report-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def discard_template(principal: TemplateAdmin, session: Session, template_id: uuid.UUID) -> None:
    await templates.discard_draft(session, await templates.get(session, template_id, lock=True))
    await _template_audit(session, principal, "template.discard", template_id)
    await session.commit()
