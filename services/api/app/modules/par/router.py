"""Crew accountability in danger zones, OS7 (docs/phase-os7/design-os7.md).

* ``/api/v1/staff/par``: the operations commander and the rooms. The incidents with teams inside, the board of one
  (teams, timers, missing resources, the word from the scene, the log), the intervals of the gouvernorat, a time for
  the next check, a pause with its reason and the resumption, a general check, a confirmation or an exit taken by
  radio, a replacement sent, a resource recovered, the end of the check.
* ``/api/v1/crew/missions/{assignment_id}/par``: the team leader's phone. Entering the zone, the confirmation, a member
  out for a while and back, a missing resource, the word from the scene, the exit with the headcount.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action
from app.core.db import as_system, get_session
from app.core.security import Principal, Role, require_roles
from app.modules.ops import crew
from app.modules.ops import service as incidents
from app.modules.ops.models import Assignment, Incident, Shift
from app.modules.par import schemas, service
from app.modules.par.models import Missing, Team
from app.modules.reports.staff_router import READ_ROLES, WRITE_ROLES

router = APIRouter(prefix="/api/v1/staff/par", tags=["staff", "par"])
crew_router = APIRouter(prefix="/api/v1/crew/missions", tags=["crew", "par"])

Session = Annotated[AsyncSession, Depends(get_session)]
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
Writer = Annotated[Principal, Depends(require_roles(*WRITE_ROLES))]
Leader = Annotated[Principal, Depends(require_roles(Role.TEAM_LEADER))]
DeviceId = Annotated[uuid.UUID | None, Header(alias="X-Staff-Device")]


# ---------------------------------------------------------------- the rooms


async def _incident(session: AsyncSession, principal: Principal, incident_id: uuid.UUID, write: bool) -> Incident:
    action = Action.INCIDENT_NOTE if write else Action.INCIDENT_READ
    return await incidents.get_in_scope(session, principal, incident_id, action=action)


async def _board(session: AsyncSession, incident: Incident) -> schemas.Board:
    # The board also logs a late team's alarm once, and ends the check of a closed incident: kept under the
    # incident's gouvernorat, whichever room reads it.
    async with as_system(session):
        out = await service.board(session, incident)
    await session.commit()
    return out


def _gouvernorat(principal: Principal, code: int | None) -> int | None:
    if principal.gouvernorat_code is not None:
        if code is not None and code != principal.gouvernorat_code:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        return principal.gouvernorat_code
    return code


@router.get("/incidents", response_model=list[schemas.IncidentRow])
async def list_incidents(
    principal: Reader, session: Session, closed: Annotated[bool, Query()] = False
) -> list[schemas.IncidentRow]:
    rows = await service.incidents(session, include_closed=closed)
    await session.commit()
    return rows


@router.get("/incidents/{incident_id}", response_model=schemas.Board)
async def get_board(principal: Reader, session: Session, incident_id: uuid.UUID) -> schemas.Board:
    incident = await _incident(session, principal, incident_id, write=False)
    return await _board(session, incident)


@router.get("/settings", response_model=schemas.SettingOut)
async def get_setting(
    principal: Reader, session: Session, gouvernorat: Annotated[int | None, Query()] = None
) -> schemas.SettingOut:
    return await service.setting(session, _gouvernorat(principal, gouvernorat))


@router.put("/settings", response_model=schemas.SettingOut)
async def put_setting(
    principal: Writer,
    session: Session,
    body: schemas.SettingIn,
    gouvernorat: Annotated[int | None, Query()] = None,
) -> schemas.SettingOut:
    code = _gouvernorat(principal, gouvernorat)
    if code is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "gouvernorat_required")
    out = await service.save_setting(session, principal, code, body)
    await session.commit()
    return out


async def _act(session: AsyncSession, principal: Principal, incident_id: uuid.UUID) -> Incident:
    return await _incident(session, principal, incident_id, write=True)


@router.post("/incidents/{incident_id}/next", response_model=schemas.Board)
async def set_next(principal: Writer, session: Session, incident_id: uuid.UUID, body: schemas.NextIn) -> schemas.Board:
    incident = await _act(session, principal, incident_id)
    async with as_system(session):
        await service.set_next(session, principal, incident, body)
    return await _board(session, incident)


@router.post("/incidents/{incident_id}/next/clear", response_model=schemas.Board)
async def clear_next(
    principal: Writer, session: Session, incident_id: uuid.UUID, body: schemas.TeamsIn
) -> schemas.Board:
    incident = await _act(session, principal, incident_id)
    async with as_system(session):
        await service.clear_next(session, principal, incident, body)
    return await _board(session, incident)


@router.post("/incidents/{incident_id}/pause", response_model=schemas.Board)
async def pause(principal: Writer, session: Session, incident_id: uuid.UUID, body: schemas.PauseIn) -> schemas.Board:
    incident = await _act(session, principal, incident_id)
    async with as_system(session):
        await service.pause(session, principal, incident, body)
    return await _board(session, incident)


@router.post("/incidents/{incident_id}/resume", response_model=schemas.Board)
async def resume(principal: Writer, session: Session, incident_id: uuid.UUID, body: schemas.TeamsIn) -> schemas.Board:
    incident = await _act(session, principal, incident_id)
    async with as_system(session):
        await service.resume(session, principal, incident, body)
    return await _board(session, incident)


@router.post("/incidents/{incident_id}/check-all", response_model=schemas.Board)
async def check_all(
    principal: Writer, session: Session, incident_id: uuid.UUID, body: schemas.CheckAllIn
) -> schemas.Board:
    incident = await _act(session, principal, incident_id)
    async with as_system(session):
        await service.check_all(session, principal, incident, body)
    return await _board(session, incident)


async def _team(session: AsyncSession, incident: Incident, team_id: uuid.UUID) -> Team:
    team = await session.get(Team, team_id)
    if team is None or team.incident_id != incident.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return team


@router.post("/incidents/{incident_id}/teams/{team_id}/{action}", response_model=schemas.Board)
async def team_action(
    principal: Writer, session: Session, incident_id: uuid.UUID, team_id: uuid.UUID, action: str
) -> schemas.Board:
    incident = await _act(session, principal, incident_id)
    async with as_system(session):
        team = await _team(session, incident, team_id)
        if action == "radio":
            await service.radio(session, principal, incident, team)
        elif action == "confirm":
            await service.manual_confirm(session, principal, incident, team)
        elif action == "out":
            await service.record_out(session, principal, incident, team)
        else:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return await _board(session, incident)


@router.post("/incidents/{incident_id}/missing/{missing_id}/{action}", response_model=schemas.Board)
async def missing_action(
    principal: Writer, session: Session, incident_id: uuid.UUID, missing_id: uuid.UUID, action: str
) -> schemas.Board:
    incident = await _act(session, principal, incident_id)
    async with as_system(session):
        m = await session.get(Missing, missing_id)
        if m is None or m.incident_id != incident.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        if action == "replacement":
            await service.replacement(session, principal, incident, m)
        elif action == "recovered":
            await service.recovered(session, principal, incident, m)
        else:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return await _board(session, incident)


@router.post("/incidents/{incident_id}/close", response_model=schemas.Board)
async def close(principal: Writer, session: Session, incident_id: uuid.UUID) -> schemas.Board:
    incident = await _act(session, principal, incident_id)
    async with as_system(session):
        await service.close(session, principal, incident)
    return await _board(session, incident)


# ---------------------------------------------------------------- the team leader's phone


async def _mission(
    session: AsyncSession, principal: Principal, device_id: uuid.UUID | None, assignment_id: uuid.UUID
) -> tuple[Incident, Assignment, Shift]:
    """The assignment of the vehicle the leader holds on shift, and its incident; anything else is not found."""
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
    return incident, assignment, shift


async def _phone(session: AsyncSession, incident: Incident, assignment: Assignment) -> schemas.MissionPar:
    async with as_system(session):
        out = await service.mission(session, incident, assignment)
    await session.commit()
    return out


async def _my_team(session: AsyncSession, incident: Incident, assignment: Assignment) -> Team | None:
    team = await service.mission_team(session, assignment)
    if team is not None:
        await service.not_closed(session, incident)
    return team


@crew_router.get("/{assignment_id}/par", response_model=schemas.MissionPar)
async def crew_par(
    principal: Leader, session: Session, assignment_id: uuid.UUID, device_id: DeviceId = None
) -> schemas.MissionPar:
    incident, assignment, _ = await _mission(session, principal, device_id, assignment_id)
    return await _phone(session, incident, assignment)


@crew_router.post("/{assignment_id}/par/enter", response_model=schemas.MissionPar)
async def crew_enter(
    principal: Leader, session: Session, assignment_id: uuid.UUID, body: schemas.EnterIn, device_id: DeviceId = None
) -> schemas.MissionPar:
    incident, assignment, shift = await _mission(session, principal, device_id, assignment_id)
    async with as_system(session):
        await service.enter(session, principal, incident, assignment, shift, body)
    return await _phone(session, incident, assignment)


@crew_router.post("/{assignment_id}/par/confirm", response_model=schemas.MissionPar)
async def crew_confirm(
    principal: Leader, session: Session, assignment_id: uuid.UUID, device_id: DeviceId = None
) -> schemas.MissionPar:
    incident, assignment, _ = await _mission(session, principal, device_id, assignment_id)
    async with as_system(session):
        await service.confirm(session, principal, incident, await _my_team(session, incident, assignment))
    return await _phone(session, incident, assignment)


@crew_router.post("/{assignment_id}/par/away", response_model=schemas.MissionPar)
async def crew_away(
    principal: Leader, session: Session, assignment_id: uuid.UUID, body: schemas.AwayIn, device_id: DeviceId = None
) -> schemas.MissionPar:
    incident, assignment, _ = await _mission(session, principal, device_id, assignment_id)
    async with as_system(session):
        await service.go_away(session, principal, incident, await _my_team(session, incident, assignment), body)
    return await _phone(session, incident, assignment)


@crew_router.post("/{assignment_id}/par/back", response_model=schemas.MissionPar)
async def crew_back(
    principal: Leader, session: Session, assignment_id: uuid.UUID, body: schemas.MemberIn, device_id: DeviceId = None
) -> schemas.MissionPar:
    incident, assignment, _ = await _mission(session, principal, device_id, assignment_id)
    async with as_system(session):
        await service.come_back(session, principal, incident, await _my_team(session, incident, assignment), body)
    return await _phone(session, incident, assignment)


@crew_router.post("/{assignment_id}/par/missing", response_model=schemas.MissionPar)
async def crew_missing(
    principal: Leader, session: Session, assignment_id: uuid.UUID, body: schemas.MissingIn, device_id: DeviceId = None
) -> schemas.MissionPar:
    incident, assignment, _ = await _mission(session, principal, device_id, assignment_id)
    async with as_system(session):
        await service.report_missing(session, principal, incident, await _my_team(session, incident, assignment), body)
    return await _phone(session, incident, assignment)


@crew_router.post("/{assignment_id}/par/sitrep", response_model=schemas.MissionPar)
async def crew_sitrep(
    principal: Leader, session: Session, assignment_id: uuid.UUID, body: schemas.SitrepIn, device_id: DeviceId = None
) -> schemas.MissionPar:
    incident, assignment, _ = await _mission(session, principal, device_id, assignment_id)
    async with as_system(session):
        await service.sitrep(session, principal, incident, await _my_team(session, incident, assignment), body)
    return await _phone(session, incident, assignment)


@crew_router.post("/{assignment_id}/par/exit", response_model=schemas.MissionPar)
async def crew_exit(
    principal: Leader, session: Session, assignment_id: uuid.UUID, body: schemas.ExitIn, device_id: DeviceId = None
) -> schemas.MissionPar:
    incident, assignment, _ = await _mission(session, principal, device_id, assignment_id)
    async with as_system(session):
        await service.exit_zone(session, principal, incident, await _my_team(session, incident, assignment), body)
    return await _phone(session, incident, assignment)
