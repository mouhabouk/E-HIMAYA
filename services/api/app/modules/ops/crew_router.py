"""Staff app endpoints (phase P4a, docs/phase-p4/design-staff.md §4) and the room's view of devices and shifts.

``/api/v1/crew/*`` is for team leaders only (staff realm, second factor, a gouvernorat). Every call but the device
registration names the phone in ``X-Staff-Device``; a revoked phone gets ``410 device_revoked``.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.ops import crew, schemas
from app.modules.ops.models import Assignment, Shift, StaffDevice
from app.modules.reports.staff_router import READ_ROLES

router = APIRouter(prefix="/api/v1/crew", tags=["crew"])
staff_router = APIRouter(prefix="/api/v1/staff", tags=["crew"])

Leader = Annotated[Principal, Depends(require_roles(Role.TEAM_LEADER))]
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
DeviceAdmin = Annotated[Principal, Depends(require_roles(Role.REGIONAL_ACCOUNT_ADMIN, Role.SECURITY_ADMIN))]
Session = Annotated[AsyncSession, Depends(get_session)]
DeviceId = Annotated[uuid.UUID | None, Header(alias="X-Staff-Device")]


async def _device(principal: Leader, session: Session, device_id: DeviceId = None) -> StaffDevice:
    return await crew.current_device(session, principal, device_id)


Device = Annotated[StaffDevice, Depends(_device)]


@router.post("/devices", response_model=schemas.DeviceOut, status_code=status.HTTP_201_CREATED)
async def register_device(principal: Leader, session: Session, body: schemas.DeviceIn) -> schemas.DeviceOut:
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
    principal: Leader, session: Session, device: Device, body: schemas.DevicePatch
) -> schemas.DeviceOut:
    if body.push_token is not None:
        device.push_token = body.push_token
    if body.app_build is not None:
        device.app_build = body.app_build
    await session.commit()
    return crew.device_out(device)


@router.get("/me", response_model=schemas.CrewMe)
async def me(principal: Leader, session: Session, device: Device) -> schemas.CrewMe:
    shift = await crew.open_shift(session, principal)
    out = schemas.CrewMe(
        name=audit.name_of(principal),
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


# ---------------------------------------------------------------- the room and the account administrators


class ShiftRow(schemas.ShiftOut):
    leader_name: str | None
    gouvernorat_code: int


@staff_router.get("/shifts", response_model=list[ShiftRow])
async def open_shifts(principal: Reader, session: Session) -> list[ShiftRow]:
    """Teams on duty (vehicle, leader, crew) in the caller's scope."""
    query = select(Shift).where(Shift.ended_at.is_(None)).order_by(Shift.started_at)
    if principal.gouvernorat_code is not None:
        query = query.where(Shift.gouvernorat_code == principal.gouvernorat_code)
    out = []
    for shift in await session.scalars(query):
        base = await crew.shift_out(session, shift)
        out.append(
            ShiftRow(**base.model_dump(), leader_name=shift.leader_name, gouvernorat_code=shift.gouvernorat_code)
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
