"""Address warnings, OS8 (docs/phase-os8/design-os8.md).

* ``/api/v1/staff/address-warnings``: the operations rooms. The register of the marks of the gouvernorat (the central
  room: every one), the decisions on them, the categories (national settings), the warnings of an incident, their
  reading and the name of a personal mark's owner (with a reason, kept and shown to the owner).
* ``/api/v1/crew/missions/{assignment_id}/address-warnings``: the team leader's phone. The warnings of the mission
  the team sees, «read», and a mark proposed from the scene (pending until the room approves it).
* ``/api/v1/me/address-warnings``: the citizen's consent from their medical file. Registered accounts only.
"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import as_system, get_session
from app.core.security import Principal, Role, require_roles
from app.modules.address_warnings import schemas, service
from app.modules.identity.models import AccountKind
from app.modules.identity.service import CurrentReporter
from app.modules.ops import crew
from app.modules.ops import service as incidents
from app.modules.ops.models import Assignment, Incident
from app.modules.reports.staff_router import READ_ROLES, WRITE_ROLES

router = APIRouter(prefix="/api/v1/staff/address-warnings", tags=["staff", "address-warnings"])
crew_router = APIRouter(prefix="/api/v1/crew/missions", tags=["crew", "address-warnings"])
me_router = APIRouter(prefix="/api/v1/me/address-warnings", tags=["address-warnings"])

Session = Annotated[AsyncSession, Depends(get_session)]
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
Writer = Annotated[Principal, Depends(require_roles(*WRITE_ROLES))]
Manager = Annotated[Principal, Depends(require_roles(Role.OPS_MANAGER))]
Leader = Annotated[Principal, Depends(require_roles(Role.TEAM_LEADER))]
DeviceId = Annotated[uuid.UUID | None, Header(alias="X-Staff-Device")]


# ---------------------------------------------------------------- categories


@router.get("/categories", response_model=list[schemas.CategoryOut])
async def get_categories(_: Reader, session: Session) -> list[schemas.CategoryOut]:
    return [service.category_out(c) for c in (await service.categories(session)).values()]


@router.put("/categories/{key}", response_model=schemas.CategoryOut)
async def put_category(principal: Manager, session: Session, key: str, body: schemas.CategoryIn) -> schemas.CategoryOut:
    """The central room's settings: circle, review period, team, critical kinds."""
    out = await service.save_category(session, principal, key, body)
    await session.commit()
    return out


# ---------------------------------------------------------------- the register


@router.get("/markers", response_model=schemas.MarkerPage)
async def list_markers(
    principal: Reader,
    session: Session,
    status_: Annotated[
        Literal["pending", "active", "review_due", "archived", "rejected"] | None, Query(alias="status")
    ] = None,
    category: Annotated[str | None, Query(max_length=20)] = None,
    source: Annotated[str | None, Query(max_length=20)] = None,
) -> schemas.MarkerPage:
    return await service.list_markers(session, principal, status_=status_, category=category, source=source)


@router.post("/markers", response_model=schemas.MarkerOut, status_code=status.HTTP_201_CREATED)
async def create_marker(principal: Writer, session: Session, body: schemas.MarkerIn) -> schemas.MarkerOut:
    out = await service.create_marker(session, principal, body)
    await session.commit()
    return out


@router.patch("/markers/{marker_id}", response_model=schemas.MarkerOut)
async def patch_marker(
    principal: Writer, session: Session, marker_id: uuid.UUID, body: schemas.MarkerPatch
) -> schemas.MarkerOut:
    out = await service.patch_marker(session, principal, marker_id, body)
    await session.commit()
    return out


@router.post("/markers/{marker_id}/check", response_model=schemas.MarkerOut)
async def request_check(principal: Writer, session: Session, marker_id: uuid.UUID) -> schemas.MarkerOut:
    """OS8-3: ask a field check of a mark from the review reminder (kept until a confirm or an archive)."""
    out = await service.request_check(session, principal, marker_id)
    await session.commit()
    return out


@router.post("/markers/{marker_id}/{action}", response_model=schemas.MarkerOut)
async def decide(
    principal: Writer,
    session: Session,
    marker_id: uuid.UUID,
    action: Literal["approve", "reject", "archive", "confirm"],
    body: schemas.DecisionIn,
) -> schemas.MarkerOut:
    out = await service.decide(session, principal, marker_id, action, body.reason)
    await session.commit()
    return out


@router.post("/import-orgs", response_model=schemas.ImportOut)
async def import_orgs(principal: Writer, session: Session) -> schemas.ImportOut:
    """Pending marks from the institutions that declared hazardous materials."""
    out = await service.import_orgs(session, principal)
    await session.commit()
    return out


@router.get("/reminders", response_model=schemas.Reminders)
async def reminders(principal: Reader, session: Session) -> schemas.Reminders:
    """OS8-3: the marks past their review date or within the notice, with their level (room, manager, central)."""
    return await service.reminders(session, principal)


@router.get("/reveals", response_model=list[schemas.RevealRow])
async def reveals(principal: Reader, session: Session) -> list[schemas.RevealRow]:
    return await service.reveals(session, principal)


# ---------------------------------------------------------------- the warnings of an incident


@router.get("/incidents/{incident_id}", response_model=schemas.IncidentWarnings)
async def incident_warnings(principal: Reader, session: Session, incident_id: uuid.UUID) -> schemas.IncidentWarnings:
    incident = await incidents.get_in_scope(session, principal, incident_id)
    return await service.warnings(session, incident)


@router.post("/incidents/{incident_id}/ack", response_model=schemas.IncidentWarnings)
async def acknowledge(
    principal: Writer, session: Session, incident_id: uuid.UUID, body: schemas.AckIn
) -> schemas.IncidentWarnings:
    incident = await incidents.get_in_scope(session, principal, incident_id)
    # A participating room's reading is kept under the incident's lead gouvernorat.
    async with as_system(session):
        await service.acknowledge(session, principal, incident, "room", body.marker_ids)
    await session.commit()
    return await service.warnings(session, incident)


@router.post("/incidents/{incident_id}/reveal/{marker_id}", response_model=schemas.RevealOut)
async def reveal(
    principal: Writer, session: Session, incident_id: uuid.UUID, marker_id: uuid.UUID, body: schemas.RevealIn
) -> schemas.RevealOut:
    incident = await incidents.get_in_scope(session, principal, incident_id)
    out = await service.reveal(session, principal, incident, marker_id, body.reason)
    await session.commit()
    return out


# ---------------------------------------------------------------- the team leader's phone


async def _mission_incident(
    session: AsyncSession, principal: Principal, device_id: uuid.UUID | None, assignment_id: uuid.UUID
) -> Incident:
    """The incident of an assignment of the vehicle the leader holds on shift; anything else is not found."""
    await crew.current_device(session, principal, device_id)
    shift = await crew.open_shift(session, principal)
    if shift is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no_open_shift")
    assignment = await session.get(Assignment, assignment_id)
    if assignment is None or assignment.resource_id != shift.resource_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    async with as_system(session):
        incident = await session.get(Incident, assignment.incident_id)
    if incident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return incident


@crew_router.get("/{assignment_id}/address-warnings", response_model=schemas.IncidentWarnings)
async def crew_warnings(
    principal: Leader, session: Session, assignment_id: uuid.UUID, device_id: DeviceId = None
) -> schemas.IncidentWarnings:
    incident = await _mission_incident(session, principal, device_id, assignment_id)
    return await service.warnings(session, incident, team=True)


@crew_router.post("/{assignment_id}/address-warnings/ack", response_model=schemas.IncidentWarnings)
async def crew_ack(
    principal: Leader, session: Session, assignment_id: uuid.UUID, body: schemas.AckIn, device_id: DeviceId = None
) -> schemas.IncidentWarnings:
    incident = await _mission_incident(session, principal, device_id, assignment_id)
    async with as_system(session):
        await service.acknowledge(session, principal, incident, "team", body.marker_ids)
    await session.commit()
    return await service.warnings(session, incident, team=True)


@crew_router.post(
    "/{assignment_id}/address-warnings/propose", response_model=schemas.MarkerOut, status_code=status.HTTP_201_CREATED
)
async def crew_propose(
    principal: Leader, session: Session, assignment_id: uuid.UUID, body: schemas.ProposalIn, device_id: DeviceId = None
) -> schemas.MarkerOut:
    incident = await _mission_incident(session, principal, device_id, assignment_id)
    out = await service.propose(session, principal, incident, body)
    await session.commit()
    return out


# ---------------------------------------------------------------- the citizen


def _registered(reporter: CurrentReporter) -> uuid.UUID:
    # A personal mark needs an accountable identity whose name the room can read: no guest account.
    if reporter.principal is None or reporter.kind is AccountKind.ANONYMOUS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "registration_required")
    return reporter.user_id


@me_router.get("", response_model=schemas.MyWarningsOut)
async def my_warnings(reporter: CurrentReporter, session: Session) -> schemas.MyWarningsOut:
    return await service.my_warnings(session, _registered(reporter))


@me_router.put("", response_model=schemas.MyWarningsOut)
async def save_my_warnings(
    reporter: CurrentReporter, session: Session, body: schemas.MyWarningsIn
) -> schemas.MyWarningsOut:
    out = await service.save_my_warnings(session, _registered(reporter), reporter.actor, body)
    await session.commit()
    return out


@me_router.delete("", response_model=schemas.MyWarningsOut)
async def withdraw_my_warnings(reporter: CurrentReporter, session: Session) -> schemas.MyWarningsOut:
    """Withdraw every need at once: the marks disappear from the rooms and the phones immediately."""
    user_id = _registered(reporter)
    current = await service.my_warnings(session, user_id)
    if current.needs and current.location and current.address:
        body = schemas.MyWarningsIn(
            location=schemas.LocationIn(lat=current.location.lat, lon=current.location.lon),
            address=current.address,
            needs=[],
        )
        out = await service.save_my_warnings(session, user_id, reporter.actor, body)
        await session.commit()
        return out
    return current


@me_router.post("/reveals/{reveal_id}/dispute", status_code=status.HTTP_204_NO_CONTENT)
async def dispute_reveal(reporter: CurrentReporter, session: Session, reveal_id: int, body: schemas.DisputeIn) -> None:
    """OS8-2: «لا علم لي بأي بلاغ عندي». The owner objects to a reading of their name; the central room follows it."""
    await service.dispute(session, _registered(reporter), reporter.actor, reveal_id, body.note)
    await session.commit()
