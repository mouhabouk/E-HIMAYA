"""Citizen endpoints of live streaming (docs/api/phase-6-contract.md §2): bearer of the public realm or X-Device-Key."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.modules.identity.service import CurrentReporter, limit_reporter
from app.modules.streams import mediamtx, schemas, service
from app.modules.streams.domain import EndReason

router = APIRouter(prefix="/api/v1", tags=["streams"])
Session = Annotated[AsyncSession, Depends(get_session)]

HOUR_S = 3600
# Anonymous device identities are free to mint: the client address bounds them too (A1).
CREATE_PER_IP = 30


@router.post("/reports/{report_id}/streams", response_model=schemas.StreamCreated, status_code=status.HTTP_201_CREATED)
async def create_stream(
    request: Request, report_id: uuid.UUID, reporter: CurrentReporter, session: Session
) -> schemas.StreamCreated:
    """Open a live stream of the caller's report: the app then publishes with WHIP and ``Bearer <publish_token>``."""
    await limit_reporter(
        request,
        reporter,
        "stream-create",
        per_account=get_settings().stream_create_per_hour,
        per_ip=CREATE_PER_IP,
        window_s=HOUR_S,
    )
    stream, token = await service.create_for_report(session, reporter.user_id, report_id)
    out = service.created_out(stream, token)
    await session.commit()
    return out


@router.post("/streams/{stream_id}/location", status_code=status.HTTP_204_NO_CONTENT)
async def stream_location(
    stream_id: uuid.UUID, body: schemas.LocationIn, reporter: CurrentReporter, session: Session
) -> Response:
    """Position of the phone while streaming (every ``location_interval_s``; closer calls are ignored)."""
    stream = await service.owned_stream(session, reporter.user_id, stream_id, lock=True)
    await service.record_location(session, stream, body)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/streams/{stream_id}/stop", response_model=schemas.StreamSummary)
async def stop_stream(stream_id: uuid.UUID, reporter: CurrentReporter, session: Session) -> schemas.StreamSummary:
    """End the caller's stream (idempotent) and disconnect the publisher."""
    stream = await service.owned_stream(session, reporter.user_id, stream_id, lock=True)
    changed = await service.end(session, stream, EndReason.PUBLISHER_STOPPED)
    out = service.summary(stream)
    await session.commit()
    if changed:
        await mediamtx.kick(stream.path)
    return out


@router.get("/streams/{stream_id}", response_model=schemas.StreamSummary)
async def get_stream(stream_id: uuid.UUID, reporter: CurrentReporter, session: Session) -> schemas.StreamSummary:
    """State of the caller's stream (the app polls it to show "stream ended by the operator")."""
    return service.summary(await service.owned_stream(session, reporter.user_id, stream_id))
