"""Repositioning orders to the crew (OS3-1, docs/phase-os3/design-os3b.md §1; Yamen 2026-11-13).

When a room sends a vehicle to another unit as reinforcement, or ends a reinforcement (back to its own unit), the crew
holding the vehicle on the staff app gets the order: a content-free push rings the leader's phone, and the app fetches
the order. The crew says it saw it, left, arrived; the room follows the steps and sees an order nobody opened after
``coverage.order_ack_minutes``. A newer order, a breakdown, the workshop or the decommissioning closes an open one.

Routes:

* ``GET /api/v1/staff/coverage/orders``: the rooms (the vehicle's gouvernorat and the other end of the move);
* ``GET /api/v1/crew/repositions``: the crew of the vehicle on shift (leader and agents);
* ``POST /api/v1/crew/repositions/{id}/{seen|departed|arrived}``: the leader. Each step is set once; a later step sets
  the earlier ones it implies.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from geoalchemy2 import Geometry
from sqlalchemy import ColumnElement, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.db import as_system, get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.inventory import schemas
from app.modules.notify import outbox
from app.modules.ops import crew, shifts
from app.modules.ops.models import RepositionOrder, Resource, Shift, StaffDevice, Unit, VehicleEvent
from app.modules.reports.staff_router import READ_ROLES
from app.modules.settings import service as settings

staff_router = APIRouter(prefix="/api/v1/staff", tags=["staff", "decision"])
crew_router = APIRouter(prefix="/api/v1/crew", tags=["crew"])
Session = Annotated[AsyncSession, Depends(get_session)]
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES, Role.MAINTENANCE_OFFICER))]
Leader = Annotated[Principal, Depends(require_roles(Role.TEAM_LEADER))]
FieldStaff = Annotated[Principal, Depends(require_roles(*crew.FIELD_ROLES))]
DeviceId = Annotated[uuid.UUID | None, Header(alias="X-Staff-Device")]

#: Arrived or closed orders stay on the phone and in the room's list this long.
RECENT = timedelta(hours=12)
#: A step sent by a phone that was offline keeps the phone's time up to this late (as the missions, crew.LATE_WRITE).
LATE = timedelta(hours=12)

TITLE = outbox.localized("أمر تمركز", "Ordre de repositionnement", "Repositioning order")
BODY = outbox.localized(
    "افتح التطبيق لقراءة الأمر.", "Ouvrez l'application pour lire l'ordre.", "Open the app to read the order."
)
CloseReason = Literal["replaced", "state", "maintenance", "retired"]


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------- from the rooms' decisions (inventory.fleet)


async def close_open(session: AsyncSession, resource_id: uuid.UUID, reason: CloseReason) -> None:
    """A newer decision about the vehicle closes the order it was still carrying out."""
    async with as_system(session):
        rows = await session.scalars(
            select(RepositionOrder).where(
                RepositionOrder.resource_id == resource_id,
                RepositionOrder.arrived_at.is_(None),
                RepositionOrder.closed_at.is_(None),
            )
        )
        for order in rows:
            order.closed_at, order.close_reason = _now(), reason


async def send(
    session: AsyncSession,
    principal: Principal,
    r: Resource,
    owner: Unit,
    kind: Literal["reinforce", "return"],
    from_unit: Unit,
    to_unit: Unit,
    event: VehicleEvent,
    note: str | None,
    gain: int | None,
) -> RepositionOrder:
    """Write the order and ring the phone of the leader holding the vehicle on shift (if any)."""
    await close_open(session, r.id, "replaced")
    other = to_unit if kind == "reinforce" else from_unit
    order = RepositionOrder(
        resource_id=r.id,
        vehicle_event_id=event.id,
        kind=kind,
        from_unit_id=from_unit.id,
        to_unit_id=to_unit.id,
        gouvernorat_code=owner.gouvernorat_code,
        host_gouvernorat_code=other.gouvernorat_code,
        note=note,
        gain_population=gain,
        created_by=audit.actor_of(principal),
        created_by_name=audit.name_of(principal),
    )
    # The shift and the phone belong to the vehicle's gouvernorat: a host room or the central room reaches them here.
    async with as_system(session):
        shift = await shifts.open_shift_of_resource(session, r.id)
        device = await session.get(StaffDevice, shift.device_id) if shift is not None else None
    if shift is not None:
        order.shift_id, order.leader_name = shift.id, shift.leader_name
    session.add(order)
    await session.flush()
    if device is not None and device.revoked_at is None and device.push_token:
        outbox.staff_push(
            session,
            device.push_token,
            device.platform,
            "reposition",
            {"order_id": str(order.id)},
            title=TITLE,
            body=BODY,
        )
        order.pushed = True
    return order


# ---------------------------------------------------------------- answers


def _state(o: RepositionOrder) -> schemas.OrderState:
    if o.closed_at is not None:
        return "closed"
    if o.arrived_at is not None:
        return "arrived"
    if o.departed_at is not None:
        return "departed"
    return "seen" if o.seen_at is not None else "sent"


def _point(lat: float | None, lon: float | None) -> list[float] | None:
    return [float(lon), float(lat)] if lat is not None and lon is not None else None


async def _orders(
    session: AsyncSession, where: list[ColumnElement[bool]], ack_minutes: int, limit: int = 200
) -> list[schemas.RepositionOrderOut]:
    src, dst = aliased(Unit), aliased(Unit)
    gs, gd = cast(src.location, Geometry), cast(dst.location, Geometry)
    rows = (
        await session.execute(
            select(
                RepositionOrder,
                Resource,
                src,
                dst,
                func.ST_Y(gs),
                func.ST_X(gs),
                func.ST_Y(gd),
                func.ST_X(gd),
            )
            .join(Resource, Resource.id == RepositionOrder.resource_id)
            .join(src, src.id == RepositionOrder.from_unit_id)
            .join(dst, dst.id == RepositionOrder.to_unit_id)
            .where(*where)
            .order_by(RepositionOrder.created_at.desc())
            .limit(limit)
        )
    ).all()
    now = _now()
    late = timedelta(minutes=ack_minutes)
    return [
        schemas.RepositionOrderOut(
            id=o.id,
            resource_id=r.id,
            label=r.label,
            plate=r.plate,
            kind=o.kind,
            from_unit_id=a.id,
            from_unit=a.name_ar,
            to_unit_id=b.id,
            to_unit=b.name_ar,
            from_point=_point(alat, alon),
            to_point=_point(blat, blon),
            gouvernorat_code=o.gouvernorat_code,
            host_gouvernorat_code=o.host_gouvernorat_code,
            note=o.note,
            gain_population=o.gain_population,
            leader_name=o.leader_name,
            pushed=o.pushed,
            created_by_name=o.created_by_name,
            created_at=o.created_at,
            seen_at=o.seen_at,
            seen_by_name=o.seen_by_name,
            departed_at=o.departed_at,
            arrived_at=o.arrived_at,
            closed_at=o.closed_at,
            close_reason=o.close_reason,
            state=_state(o),
            overdue=o.seen_at is None and o.closed_at is None and now - o.created_at > late,
        )
        for o, r, a, b, alat, alon, blat, blon in rows
    ]


@staff_router.get("/coverage/orders", response_model=schemas.RepositionOrdersOut)
async def room_orders(
    principal: Reader,
    session: Session,
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
    open_only: Annotated[bool, Query(alias="open")] = False,
) -> schemas.RepositionOrdersOut:
    """The orders of the last hours the room sees (its vehicles and those sent to or from it), and every open one."""
    ack = await settings.threshold(session, "coverage.order_ack_minutes")
    where: list[ColumnElement[bool]] = [
        or_(
            RepositionOrder.arrived_at.is_(None) & RepositionOrder.closed_at.is_(None),
            RepositionOrder.created_at >= _now() - RECENT,
        )
    ]
    if open_only:
        where.append(RepositionOrder.arrived_at.is_(None) & RepositionOrder.closed_at.is_(None))
    if not principal.is_national:
        code = principal.gouvernorat_code
        where.append(or_(RepositionOrder.gouvernorat_code == code, RepositionOrder.host_gouvernorat_code == code))
    if gouvernorat is not None:
        where.append(
            or_(RepositionOrder.gouvernorat_code == gouvernorat, RepositionOrder.host_gouvernorat_code == gouvernorat)
        )
    items = await _orders(session, where, ack)
    await session.commit()
    return schemas.RepositionOrdersOut(items=items, ack_minutes=ack)


# ---------------------------------------------------------------- the staff app


async def _shift(session: AsyncSession, principal: Principal, device_id: uuid.UUID | None) -> Shift:
    await crew.current_device(session, principal, device_id)
    shift = await crew.open_shift(session, principal)
    if shift is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no_open_shift")
    return shift


@crew_router.get("/repositions", response_model=schemas.RepositionOrdersOut)
async def crew_orders(
    principal: FieldStaff, session: Session, device_id: DeviceId = None
) -> schemas.RepositionOrdersOut:
    """The orders of the vehicle on shift: the open ones and those of the last hours."""
    shift = await _shift(session, principal, device_id)
    ack = await settings.threshold(session, "coverage.order_ack_minutes")
    items = await _orders(
        session,
        [
            RepositionOrder.resource_id == shift.resource_id,
            or_(
                RepositionOrder.arrived_at.is_(None) & RepositionOrder.closed_at.is_(None),
                RepositionOrder.created_at >= _now() - RECENT,
            ),
        ],
        ack,
        limit=20,
    )
    await session.commit()
    return schemas.RepositionOrdersOut(items=items, ack_minutes=ack)


def _at(body: schemas.RepositionStepIn, order: RepositionOrder) -> datetime:
    now = _now()
    at = body.at
    if at is None or at.tzinfo is None or at > now or now - at > LATE or at < order.created_at:
        return now
    return at


@crew_router.post("/repositions/{order_id}/{step}", response_model=schemas.RepositionOrderOut)
async def crew_step(
    principal: Leader,
    session: Session,
    order_id: uuid.UUID,
    step: Literal["seen", "departed", "arrived"],
    body: schemas.RepositionStepIn,
    device_id: DeviceId = None,
) -> schemas.RepositionOrderOut:
    """The leader says the crew saw the order, left, or arrived. Set once; later steps fill the earlier ones."""
    shift = await _shift(session, principal, device_id)
    order = await session.get(RepositionOrder, order_id, with_for_update=True)
    if order is None or order.resource_id != shift.resource_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if order.closed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "order_closed")
    at = _at(body, order)
    changed = False
    if order.seen_at is None:
        order.seen_at, order.seen_by_name, changed = at, audit.name_of(principal), True
    if step in ("departed", "arrived") and order.departed_at is None:
        order.departed_at, changed = max(at, order.seen_at), True
    if step == "arrived" and order.arrived_at is None:
        order.arrived_at, changed = max(at, order.departed_at or at), True
    if changed:
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action=f"crew.reposition_{step}",
            target=f"reposition_order:{order.id}",
            details={"resource_id": str(order.resource_id), "kind": order.kind},
            gouvernorats=sorted({order.gouvernorat_code, order.host_gouvernorat_code or order.gouvernorat_code}),
        )
    await session.flush()
    ack = await settings.threshold(session, "coverage.order_ack_minutes")
    out = (await _orders(session, [RepositionOrder.id == order.id], ack))[0]
    await session.commit()
    return out
