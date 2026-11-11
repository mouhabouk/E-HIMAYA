"""The state of a vehicle, its maintenance and its decommissioning (OS3, docs/phase-os3/design-os3.md §2).

One register, three hands (Yamen 2026-11-11):

* the operations rooms (``operator``, ``ops_manager``) of the gouvernorat, or the central room for every gouvernorat,
  set the operational state only: at its unit (``ready``), waiting at another unit as reinforcement, ``broken``;
  "on a mission" is set by the interventions;
* the maintenance department (``maintenance_officer``) keeps the card (``router``), sends a vehicle to the workshop,
  takes it back and decommissions it after the decision; "in maintenance" and "decommissioned" follow from there;
* everything is logged in ``ops.vehicle_event``, read with the vehicle.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import as_system, get_session
from app.core.security import Principal
from app.modules.audit import service as audit
from app.modules.inventory import domain, schemas
from app.modules.inventory.router import (
    Reader,
    _now,
    _require_fleet,
    _scope,
    _vehicle_out,
    can_set_state,
)
from app.modules.ops import resources
from app.modules.ops.models import Resource, Unit, VehicleEvent

router = APIRouter(prefix="/api/v1/staff/inventory", tags=["staff", "inventory"])
Session = Annotated[AsyncSession, Depends(get_session)]


async def _load(session: AsyncSession, vehicle_id: uuid.UUID) -> tuple[Resource, Unit, Unit | None]:
    resource = await session.get(Resource, vehicle_id, with_for_update=True)
    if resource is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "vehicle_not_found")
    unit = await session.get(Unit, resource.unit_id)
    if unit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "vehicle_not_found")
    host = await session.get(Unit, resource.stationed_unit_id) if resource.stationed_unit_id else None
    return resource, unit, host


def _state(r: Resource) -> str:
    return domain.vehicle_state(r.status, r.out_reason, r.stationed_unit_id is not None)


def _check_version(r: Resource, version: int | None) -> None:
    if version is not None and version != r.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")


def _log(
    session: AsyncSession,
    principal: Principal,
    r: Resource,
    unit: Unit,
    host: Unit | None,
    kind: str,
    before: str,
    details: dict[str, Any],
) -> None:
    session.add(
        VehicleEvent(
            resource_id=r.id,
            gouvernorat_code=unit.gouvernorat_code,
            host_gouvernorat_code=host.gouvernorat_code if host is not None else None,
            kind=kind,
            from_state=before,
            to_state=_state(r),
            details={k: v for k, v in details.items() if v is not None},
            created_by=audit.actor_of(principal),
            created_by_name=audit.name_of(principal),
        )
    )


def _touch(r: Resource, principal: Principal) -> None:
    r.version += 1
    r.updated_at = _now()
    r.updated_by = audit.actor_of(principal)


def _release(r: Resource) -> None:
    r.stationed_unit_id = None
    r.stationed_since = None


async def _finish(
    session: AsyncSession, principal: Principal, r: Resource, unit: Unit, action: str, details: dict[str, Any]
) -> schemas.VehicleOut:
    await session.flush()
    host = await session.get(Unit, r.stationed_unit_id) if r.stationed_unit_id else None
    codes = sorted({unit.gouvernorat_code} | ({host.gouvernorat_code} if host is not None else set()))
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action=action,
        target=f"resource:{r.id}",
        details={"state": _state(r), **{k: v for k, v in details.items() if v is not None}},
        gouvernorats=codes,
    )
    # The vehicle may have left the caller's sight (a host room ending a reinforcement): announced as the system.
    async with as_system(session):
        await resources.announce(session, r.id)
    out = _vehicle_out(r, unit, host)
    await session.commit()
    return out


# ---------------------------------------------------------------- the rooms


@router.post("/vehicles/{vehicle_id}/state", response_model=schemas.VehicleOut)
async def set_state(
    principal: Reader, session: Session, vehicle_id: uuid.UUID, body: schemas.VehicleStateIn
) -> schemas.VehicleOut:
    """At its unit, reinforcement at another unit, broken. The room of the vehicle's gouvernorat or of the unit where
    it waits as reinforcement (the central room: all)."""
    r, unit, host = await _load(session, vehicle_id)
    if not (
        can_set_state(principal, unit.gouvernorat_code)
        or (host is not None and can_set_state(principal, host.gouvernorat_code))
    ):
        code = "out_of_scope" if can_set_state(principal) else "insufficient_role"
        raise HTTPException(status.HTTP_403_FORBIDDEN, code)
    _check_version(r, body.version)
    before = _state(r)
    if before == "assigned":
        raise HTTPException(status.HTTP_409_CONFLICT, "resource_busy")
    if before in domain.WORKSHOP_STATES:
        # In the workshop or decommissioned: the maintenance department's.
        raise HTTPException(status.HTTP_409_CONFLICT, f"vehicle_{before}")
    kind = "state"
    details: dict[str, Any] = {"note": body.note, "suggested_gain": body.suggested_gain}
    if body.state == "reinforcement":
        if body.host_unit_id is None or body.host_unit_id == r.unit_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "host_unit_required")
        target = await session.get(Unit, body.host_unit_id)
        if target is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "unit_not_found")
        if not principal.can_access_gouvernorat(target.gouvernorat_code) or not principal.can_access_gouvernorat(
            unit.gouvernorat_code
        ):
            # Between two gouvernorats: the central room decides (a regional room asks it, phase 4).
            raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
        r.status, r.out_reason, r.fault = "available", None, None
        r.stationed_unit_id, r.stationed_since = target.id, _now()
        kind, host = "reinforce", target
        details |= {"host_unit_id": str(target.id), "host_unit_name": target.name_ar}
    elif body.state == "broken":
        fault = (body.fault or "").strip()
        if len(fault) < 3:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "fault_required")
        if host is not None:
            kind = "reinforce_end"
        r.status, r.out_reason, r.fault = "out_of_service", "broken", fault
        details["fault"] = fault
    else:
        if host is not None:
            kind = "reinforce_end"
            details["host_unit_name"] = host.name_ar
        r.status, r.out_reason, r.fault = "available", None, None
    if body.state != "reinforcement":
        _release(r)
    _touch(r, principal)
    _log(session, principal, r, unit, host, kind, before, details)
    return await _finish(session, principal, r, unit, f"vehicle.{kind}", details)


# ---------------------------------------------------------------- the maintenance department


@router.post("/vehicles/{vehicle_id}/maintenance", response_model=schemas.VehicleOut)
async def start_maintenance(
    principal: Reader, session: Session, vehicle_id: uuid.UUID, body: schemas.MaintenanceIn
) -> schemas.VehicleOut:
    """Into the workshop: dispatch and the coverage leave it out until the department takes it back."""
    r, unit, host = await _load(session, vehicle_id)
    _require_fleet(principal, unit.gouvernorat_code)
    _check_version(r, body.version)
    before = _state(r)
    if before == "assigned":
        raise HTTPException(status.HTTP_409_CONFLICT, "resource_busy")
    if before in domain.WORKSHOP_STATES:
        raise HTTPException(status.HTTP_409_CONFLICT, f"vehicle_{before}")
    if body.until is not None and body.until < _now().date():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "until_in_past")
    _release(r)
    r.status, r.out_reason = "out_of_service", "maintenance"
    r.workshop, r.maint_reason, r.maint_since, r.maint_until = body.workshop, body.reason, _now(), body.until
    _touch(r, principal)
    details = {
        "workshop": body.workshop,
        "reason": body.reason,
        "until": body.until.isoformat() if body.until else None,
        "fault": r.fault,
    }
    _log(session, principal, r, unit, host, "maintenance_start", before, details)
    return await _finish(session, principal, r, unit, "vehicle.maintenance_start", details)


@router.post("/vehicles/{vehicle_id}/maintenance/end", response_model=schemas.VehicleOut)
async def end_maintenance(
    principal: Reader, session: Session, vehicle_id: uuid.UUID, body: schemas.MaintenanceEndIn
) -> schemas.VehicleOut:
    """Back from the workshop, ready at its unit."""
    r, unit, _ = await _load(session, vehicle_id)
    _require_fleet(principal, unit.gouvernorat_code)
    _check_version(r, body.version)
    before = _state(r)
    if before != "maintenance":
        raise HTTPException(status.HTTP_409_CONFLICT, "not_in_maintenance")
    if body.odometer_km is not None:
        if r.odometer_km is not None and body.odometer_km < r.odometer_km:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "odometer_decrease")
        r.odometer_km = body.odometer_km
    details = {
        "workshop": r.workshop,
        "reason": r.maint_reason,
        "since": r.maint_since.isoformat() if r.maint_since else None,
        "days": (_now() - r.maint_since).days if r.maint_since else None,
        "note": body.note,
        "odometer_km": body.odometer_km,
    }
    r.status, r.out_reason, r.fault = "available", None, None
    r.workshop = r.maint_reason = None
    r.maint_since = None
    r.maint_until = None
    _touch(r, principal)
    _log(session, principal, r, unit, None, "maintenance_end", before, details)
    return await _finish(session, principal, r, unit, "vehicle.maintenance_end", details)


@router.post("/vehicles/{vehicle_id}/retire", response_model=schemas.VehicleOut)
async def retire(
    principal: Reader, session: Session, vehicle_id: uuid.UUID, body: schemas.RetireIn
) -> schemas.VehicleOut:
    """Decommissioned (طرح) after the decision: kept in the archive with its history, never dispatched again."""
    r, unit, host = await _load(session, vehicle_id)
    _require_fleet(principal, unit.gouvernorat_code)
    _check_version(r, body.version)
    before = _state(r)
    if before == "assigned":
        raise HTTPException(status.HTTP_409_CONFLICT, "resource_busy")
    if before == "retired":
        raise HTTPException(status.HTTP_409_CONFLICT, "vehicle_retired")
    if body.retired_on > _now().date():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "retired_in_future")
    _release(r)
    r.status, r.out_reason = "out_of_service", "retired"
    r.retired_on, r.retire_decision, r.retire_reason = body.retired_on, body.decision, body.reason
    r.workshop = r.maint_reason = None
    r.maint_since = None
    r.maint_until = None
    _touch(r, principal)
    details = {"decision": body.decision, "retired_on": body.retired_on.isoformat(), "reason": body.reason}
    _log(session, principal, r, unit, host, "retire", before, details)
    return await _finish(session, principal, r, unit, "vehicle.retire", details)


# ---------------------------------------------------------------- the log


@router.get("/vehicle-events", response_model=schemas.VehicleEventsOut)
async def vehicle_events(
    principal: Reader,
    session: Session,
    vehicle_id: Annotated[uuid.UUID | None, Query()] = None,
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
    kind: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> schemas.VehicleEventsOut:
    """What happened to the vehicles the caller sees, newest first."""
    query = (
        select(VehicleEvent, Resource, Unit)
        .join(Resource, Resource.id == VehicleEvent.resource_id)
        .join(Unit, Unit.id == Resource.unit_id)
        .where(
            or_(
                _scope(principal, VehicleEvent.gouvernorat_code),
                _scope(principal, VehicleEvent.host_gouvernorat_code),
            )
        )
    )
    if vehicle_id is not None:
        query = query.where(VehicleEvent.resource_id == vehicle_id)
    if gouvernorat is not None:
        query = query.where(
            or_(VehicleEvent.gouvernorat_code == gouvernorat, VehicleEvent.host_gouvernorat_code == gouvernorat)
        )
    if kind:
        query = query.where(VehicleEvent.kind.in_(kind.split(",")))
    rows = (await session.execute(query.order_by(VehicleEvent.created_at.desc()).limit(limit))).all()
    return schemas.VehicleEventsOut(
        items=[
            schemas.VehicleEventOut(
                id=e.id,
                resource_id=r.id,
                label=r.label,
                plate=r.plate,
                unit_name=u.name_ar,
                gouvernorat_code=e.gouvernorat_code,
                kind=e.kind,
                from_state=e.from_state,
                to_state=e.to_state,
                details=e.details or {},
                created_by_name=e.created_by_name,
                created_at=e.created_at,
            )
            for e, r, u in rows
        ]
    )
