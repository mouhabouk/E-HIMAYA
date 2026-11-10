"""A team streams from the staff app (phase D, review point 17, docs/phase-d/design-d.md §4).

The leader opens a stream of a mission his vehicle holds; the app publishes with WHIP and ``Bearer <publish_token>``
as the citizen app does (WebRTC only, one publish session per token, ``stream_max_duration_s``). The room sees it
in the wall and on the incident page (``incident_id``), recordings and the vision watch included.

News from the field (Yamen 2026-11-09): any agent on shift, the leader or a member of the crew, opens a stream from
the home of the app without a mission (``POST /crew/streams``, ``news``). The room sees it on the wall as «news from
the field», with the vehicle's name and the agent's position. Only the agent who opened it reads or stops it.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.ops import crew
from app.modules.ops import service as incidents
from app.modules.ops.models import Assignment, Incident, Resource, StaffDevice
from app.modules.streams import mediamtx
from app.modules.streams import schemas as stream_schemas
from app.modules.streams import service as streams
from app.modules.streams.domain import EndReason, Source
from app.modules.streams.models import LiveStream

router = APIRouter(prefix="/api/v1/crew", tags=["crew"])
Leader = Annotated[Principal, Depends(require_roles(Role.TEAM_LEADER))]
# News from the field: the leader and the agents of the crew.
Agent = Annotated[Principal, Depends(require_roles(Role.TEAM_LEADER, Role.FIELD_AGENT))]
Session = Annotated[AsyncSession, Depends(get_session)]
DeviceId = Annotated[uuid.UUID | None, Header(alias="X-Staff-Device")]


async def _device(principal: Agent, session: Session, device_id: DeviceId = None) -> StaffDevice:
    return await crew.current_device(session, principal, device_id)


Device = Annotated[StaffDevice, Depends(_device)]

# A mission released or cancelled no longer streams.
CLOSED = ("released", "cancelled")


async def _owned(
    session: AsyncSession, principal: Principal, stream_id: uuid.UUID, *, lock: bool = False
) -> LiveStream:
    """A stream of a mission of the vehicle the leader holds on shift, or the agent's own news from the field;
    anything else is not found."""
    stream = await session.get(LiveStream, stream_id, with_for_update=lock)
    if stream is None or stream.source != Source.CREW:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if stream.news:
        if stream.created_by != audit.actor_of(principal):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        return stream
    if stream.assignment_id is None or Role.TEAM_LEADER not in principal.roles:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    shift = await crew.open_shift(session, principal)
    assignment = await session.get(Assignment, stream.assignment_id)
    if shift is None or assignment is None or assignment.resource_id != shift.resource_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return stream


async def _audit(session: AsyncSession, principal: Principal, action: str, stream: LiveStream) -> None:
    if stream.news:
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action=action,
            target=f"stream:{stream.id}",
            details={"news": True, "label": stream.label},
            gouvernorats=[stream.gouvernorat_code] if stream.gouvernorat_code is not None else None,
        )
        return
    assert stream.incident_id is not None
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action=action,
        target=f"stream:{stream.id}",
        details={"assignment_id": str(stream.assignment_id), "incident_id": str(stream.incident_id)},
        gouvernorats=await incidents.all_gouvernorats(session, stream.incident_id),
    )


@router.post(
    "/missions/{assignment_id}/stream",
    response_model=stream_schemas.StreamCreated,
    status_code=status.HTTP_201_CREATED,
)
async def open_stream(
    principal: Leader, session: Session, _device: Device, assignment_id: uuid.UUID
) -> stream_schemas.StreamCreated:
    """Open the live stream of a mission: ``409 mission_closed`` once released, ``409 stream_already_active``."""
    assignment, _shift = await crew._mission(session, principal, assignment_id)
    if assignment.status in CLOSED:
        raise HTTPException(status.HTTP_409_CONFLICT, "mission_closed")
    incident = await session.get(Incident, assignment.incident_id)
    assert incident is not None
    stream, token = await streams.create_for_crew(
        session, assignment.id, incident.id, incident.gouvernorat_code, audit.actor_of(principal)
    )
    stream.label = (incident.title or "")[:100] or None
    await _audit(session, principal, "crew.stream", stream)
    out = streams.created_out(stream, token)
    await session.commit()
    return out


@router.post("/streams", response_model=stream_schemas.StreamCreated, status_code=status.HTTP_201_CREATED)
async def open_news_stream(principal: Agent, session: Session, _device: Device) -> stream_schemas.StreamCreated:
    """News from the field: stream what the agent sees, without a mission. ``409 no_open_shift`` off shift,
    ``409 stream_already_active`` while their previous news stream is still on."""
    shift = await crew.open_shift(session, principal)
    if shift is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no_open_shift")
    resource = await session.get(Resource, shift.resource_id)
    label = resource.label[:100] if resource is not None and resource.label else None
    stream, token = await streams.create_news(session, audit.actor_of(principal), shift.gouvernorat_code, label)
    await _audit(session, principal, "crew.news_stream", stream)
    out = streams.created_out(stream, token)
    await session.commit()
    return out


@router.post("/streams/{stream_id}/location", status_code=status.HTTP_204_NO_CONTENT)
async def stream_location(
    principal: Agent, session: Session, _device: Device, stream_id: uuid.UUID, body: stream_schemas.LocationIn
) -> Response:
    stream = await _owned(session, principal, stream_id, lock=True)
    await streams.record_location(session, stream, body)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/streams/{stream_id}/stop", response_model=stream_schemas.StreamSummary)
async def stop_stream(
    principal: Agent, session: Session, _device: Device, stream_id: uuid.UUID
) -> stream_schemas.StreamSummary:
    stream = await _owned(session, principal, stream_id, lock=True)
    changed = await streams.end(session, stream, EndReason.PUBLISHER_STOPPED)
    if changed:
        await _audit(session, principal, "crew.stream_stop", stream)
    out = streams.summary(stream)
    await session.commit()
    if changed:
        await mediamtx.kick(stream.path)
    return out


@router.get("/streams/{stream_id}", response_model=stream_schemas.StreamSummary)
async def get_stream(
    principal: Agent, session: Session, _device: Device, stream_id: uuid.UUID
) -> stream_schemas.StreamSummary:
    """The app polls it to show «stream ended by the room»."""
    return streams.summary(await _owned(session, principal, stream_id))
