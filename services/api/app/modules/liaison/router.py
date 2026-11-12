"""Informing the partner bodies by phone, OS20 (docs/phase-os20/design-os20.md).

``/api/v1/staff/liaison``: the operations rooms.

* ``/bodies``, ``/officials``: the contact system, central and regional (a regional room reads its gouvernorat and the
  national bodies and keeps its own; the central room reads every body and keeps the national ones).
* ``/incidents/{id}``: the level of a report, its parties with their calls, and the engine's suggestions;
  ``/incidents/{id}/picker``: suggestions, bodies used in earlier reports of the same kind and the reports' history.
* ``/follow-ups``, ``/calls``, ``/history``: the reminders to call back, the log of the calls and the history of the
  reports with the bodies informed.
"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, require_roles
from app.modules.liaison import schemas, service
from app.modules.ops import service as incidents
from app.modules.reports.staff_router import READ_ROLES, WRITE_ROLES

router = APIRouter(prefix="/api/v1/staff/liaison", tags=["staff", "liaison"])

Session = Annotated[AsyncSession, Depends(get_session)]
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
Writer = Annotated[Principal, Depends(require_roles(*WRITE_ROLES))]


# ---------------------------------------------------------------- the contact system


@router.get("/bodies", response_model=list[schemas.BodyOut])
async def list_bodies(
    principal: Reader,
    session: Session,
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
    national: bool = False,
    category: schemas.Category | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    archived: bool = False,
) -> list[schemas.BodyOut]:
    return await service.list_bodies(
        session, principal, gouvernorat=gouvernorat, national=national, category=category, q=q, archived=archived
    )


@router.post("/bodies", response_model=schemas.BodyOut, status_code=status.HTTP_201_CREATED)
async def create_body(principal: Writer, session: Session, body: schemas.BodyIn) -> schemas.BodyOut:
    out = await service.create_body(session, principal, body)
    await session.commit()
    return out


@router.get("/bodies/{body_id}", response_model=schemas.BodyOut)
async def get_body(principal: Reader, session: Session, body_id: uuid.UUID) -> schemas.BodyOut:
    return await service.get_body(session, principal, body_id)


@router.patch("/bodies/{body_id}", response_model=schemas.BodyOut)
async def patch_body(
    principal: Writer, session: Session, body_id: uuid.UUID, body: schemas.BodyPatch
) -> schemas.BodyOut:
    out = await service.patch_body(session, principal, body_id, body)
    await session.commit()
    return out


@router.post("/bodies/{body_id}/archive", response_model=schemas.BodyOut)
async def archive_body(principal: Writer, session: Session, body_id: uuid.UUID) -> schemas.BodyOut:
    out = await service.archive_body(session, principal, body_id)
    await session.commit()
    return out


@router.post("/bodies/{body_id}/officials", response_model=schemas.OfficialOut, status_code=status.HTTP_201_CREATED)
async def add_official(
    principal: Writer, session: Session, body_id: uuid.UUID, body: schemas.OfficialIn
) -> schemas.OfficialOut:
    out = await service.add_official(session, principal, body_id, body)
    await session.commit()
    return out


@router.patch("/officials/{official_id}", response_model=schemas.OfficialOut)
async def patch_official(
    principal: Writer, session: Session, official_id: uuid.UUID, body: schemas.OfficialPatch
) -> schemas.OfficialOut:
    out = await service.patch_official(session, principal, official_id, body)
    await session.commit()
    return out


@router.delete("/officials/{official_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_official(principal: Writer, session: Session, official_id: uuid.UUID) -> Response:
    await service.archive_official(session, principal, official_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- a report


@router.get("/incidents/{incident_id}", response_model=schemas.IncidentLiaison)
async def incident_view(principal: Reader, session: Session, incident_id: uuid.UUID) -> schemas.IncidentLiaison:
    incident = await incidents.get_in_scope(session, principal, incident_id)
    return await service.incident_view(session, incident)


@router.put("/incidents/{incident_id}/level", response_model=schemas.IncidentLiaison)
async def set_level(
    principal: Writer, session: Session, incident_id: uuid.UUID, body: schemas.LevelIn
) -> schemas.IncidentLiaison:
    incident = await incidents.get_in_scope(session, principal, incident_id)
    out = await service.set_level(session, principal, incident, body)
    await session.commit()
    return out


@router.get("/incidents/{incident_id}/picker", response_model=schemas.PickerOut)
async def picker(principal: Reader, session: Session, incident_id: uuid.UUID) -> schemas.PickerOut:
    incident = await incidents.get_in_scope(session, principal, incident_id)
    return await service.picker(session, incident)


@router.post("/incidents/{incident_id}/parties", response_model=schemas.IncidentLiaison)
async def add_parties(
    principal: Writer, session: Session, incident_id: uuid.UUID, body: schemas.PartiesIn
) -> schemas.IncidentLiaison:
    incident = await incidents.get_in_scope(session, principal, incident_id)
    out = await service.add_parties(session, principal, incident, body)
    await session.commit()
    return out


@router.patch("/incidents/{incident_id}/parties/{party_id}", response_model=schemas.IncidentLiaison)
async def patch_party(
    principal: Writer, session: Session, incident_id: uuid.UUID, party_id: uuid.UUID, body: schemas.PartyPatch
) -> schemas.IncidentLiaison:
    incident = await incidents.get_in_scope(session, principal, incident_id)
    out = await service.patch_party(session, principal, incident, party_id, body)
    await session.commit()
    return out


@router.delete("/incidents/{incident_id}/parties/{party_id}", response_model=schemas.IncidentLiaison)
async def remove_party(
    principal: Writer, session: Session, incident_id: uuid.UUID, party_id: uuid.UUID
) -> schemas.IncidentLiaison:
    incident = await incidents.get_in_scope(session, principal, incident_id)
    out = await service.remove_party(session, principal, incident, party_id)
    await session.commit()
    return out


@router.post(
    "/incidents/{incident_id}/parties/{party_id}/calls",
    response_model=schemas.CallOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_call(
    principal: Writer, session: Session, incident_id: uuid.UUID, party_id: uuid.UUID, body: schemas.CallIn
) -> schemas.CallOut:
    incident = await incidents.get_in_scope(session, principal, incident_id)
    out = await service.add_call(session, principal, incident, party_id, body)
    await session.commit()
    return out


# ---------------------------------------------------------------- follow-ups, log, history


@router.get("/follow-ups", response_model=list[schemas.CallOut])
async def follow_ups(_: Reader, session: Session, incident_id: uuid.UUID | None = None) -> list[schemas.CallOut]:
    return await service.follow_ups(session, incident_id)


@router.post("/calls/{call_id}/follow-up-done", response_model=schemas.CallOut)
async def follow_up_done(principal: Writer, session: Session, call_id: uuid.UUID) -> schemas.CallOut:
    out = await service.follow_up_done(session, principal, call_id)
    await session.commit()
    return out


@router.get("/calls", response_model=list[schemas.CallOut])
async def call_log(
    _: Reader,
    session: Session,
    incident_id: uuid.UUID | None = None,
    result: Literal["answered", "no_answer", "busy", "wrong_number"] | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[schemas.CallOut]:
    return await service.call_log(session, incident_id=incident_id, result=result, limit=limit)


@router.get("/history", response_model=list[schemas.HistoryRow])
async def history(
    _: Reader,
    session: Session,
    category: Annotated[str | None, Query(max_length=40)] = None,
    level: Annotated[int | None, Query(ge=1, le=2)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[schemas.HistoryRow]:
    return await service.history(session, category=category, level=level, limit=limit)
