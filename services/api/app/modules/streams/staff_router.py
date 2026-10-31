"""Dashboard endpoints of live streaming (docs/api/phase-6-contract.md §4). Geographic scope applies everywhere:
out-of-scope streams answer 404, like reports."""

import time
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.core.storage import get_store
from app.modules.audit import service as audit
from app.modules.audit.service import actor_of
from app.modules.reports.models import Media
from app.modules.reports.staff_router import READ_ROLES, WRITE_ROLES
from app.modules.streams import mediamtx, schemas, service
from app.modules.streams.domain import EndReason, Source, StreamStatus, viewer_token
from app.modules.streams.models import LiveStream

router = APIRouter(prefix="/api/v1/staff/streams", tags=["staff", "streams"])

# Fixed cameras and drones are operational resources: ops managers only (phase 9 §10; not sysadmin).
REGISTER_ROLES = (Role.OPS_MANAGER,)
StaffReader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
StaffWriter = Annotated[Principal, Depends(require_roles(*WRITE_ROLES))]
StaffRegistrar = Annotated[Principal, Depends(require_roles(*REGISTER_ROLES))]
Session = Annotated[AsyncSession, Depends(get_session)]
RECORDING_LINK_S = 300


async def _visible_row(session: AsyncSession, principal: Principal, stream_id: uuid.UUID, *, lock: bool = False) -> Any:
    query = service._staff_select().where(LiveStream.id == stream_id)
    if lock:
        query = query.with_for_update(of=LiveStream)
    row = (await session.execute(query)).first()
    if row is None or not service.visible(principal, row[0]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return row


@router.get("", response_model=schemas.StaffStreamPage)
async def list_streams(
    principal: StaffReader,
    session: Session,
    status_: Annotated[Literal["live", "ended", "all"], Query(alias="status")] = "live",
    gouvernorat: int | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> schemas.StaffStreamPage:
    items, next_cursor = await service.staff_list(session, principal, status_, gouvernorat, limit, cursor)
    return schemas.StaffStreamPage(items=items, next_cursor=next_cursor)


@router.post("", response_model=schemas.FixedSourceOut, status_code=status.HTTP_201_CREATED)
async def register_source(
    principal: StaffRegistrar, session: Session, body: schemas.FixedSourceIn
) -> schemas.FixedSourceOut:
    """Register a drone or fixed camera; its token is shown once (only a hash is kept)."""
    if not principal.is_national and body.gouvernorat_code != principal.gouvernorat_code:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
    actor = actor_of(principal)
    if body.org_id is not None:
        from app.modules.orgs.models import Organization

        org = await session.get(Organization, body.org_id)
        if body.source != "camera" or org is None or org.gouvernorat_code != body.gouvernorat_code:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_org")
    spec = service.FixedSource(
        Source(body.source), body.label, body.gouvernorat_code, body.lat, body.lon, org_id=body.org_id
    )
    stream, token = await service.register_fixed(session, spec, actor)
    await audit.record(
        session,
        actor=actor,
        action="stream.register",
        target=f"stream:{stream.id}",
        details={
            "source": body.source,
            "label": body.label,
            "gouvernorat_code": body.gouvernorat_code,
            "org": str(body.org_id) if body.org_id else None,
        },
    )
    await session.commit()
    return schemas.FixedSourceOut(
        id=stream.id,
        path=stream.path,
        publish_url_rtsp=service.rtsp_publish_url(stream),
        publish_url_rtmp=service.rtmp_publish_url(stream),
        publish_token=token,
    )


@router.get("/{stream_id}", response_model=schemas.StaffStreamDetail)
async def get_stream(principal: StaffReader, session: Session, stream_id: uuid.UUID) -> schemas.StaffStreamDetail:
    row = await _visible_row(session, principal, stream_id)
    detail = await service.staff_detail(session, row)
    # The track is the reporter's movement (personal data): reading it is audited like opening a report.
    await audit.record(session, actor=actor_of(principal), action="stream.detail", target=f"stream:{stream_id}")
    await session.commit()
    return detail


@router.post("/{stream_id}/viewer", response_model=schemas.ViewerOut)
async def viewer(principal: StaffReader, session: Session, stream_id: uuid.UUID) -> schemas.ViewerOut:
    """A short-lived token opening this stream's WHEP and HLS endpoints only."""
    row = await _visible_row(session, principal, stream_id)
    stream: LiveStream = row[0]
    if stream.status not in (StreamStatus.PENDING, StreamStatus.LIVE):
        raise HTTPException(status.HTTP_409_CONFLICT, "stream_not_active")
    settings = get_settings()
    expires = int(time.time()) + settings.stream_viewer_token_ttl_s
    await audit.record(session, actor=actor_of(principal), action="stream.view", target=f"stream:{stream_id}")
    await session.commit()
    return schemas.ViewerOut(
        whep_url=f"{settings.stream_webrtc_public_url}/{stream.path}/whep",
        hls_url=f"{settings.stream_hls_public_url}/{stream.path}/index.m3u8",
        token=viewer_token(stream.path, expires),
        expires_at=datetime.fromtimestamp(expires, UTC),
    )


@router.post("/{stream_id}/stop", response_model=schemas.StaffStream)
async def stop(principal: StaffWriter, session: Session, stream_id: uuid.UUID) -> schemas.StaffStream:
    """End a stream (a fixed source is retired: its token stops working) and disconnect the publisher."""
    row = await _visible_row(session, principal, stream_id, lock=True)
    stream: LiveStream = row[0]
    previous = stream.status
    changed = await service.end(session, stream, EndReason.STAFF_STOPPED)
    if not changed and Source(stream.source) is not Source.APP and stream.publish_token_hash is not None:
        # A fixed source between two flights (ended, reconnectable) is retired too.
        stream.end_reason = EndReason.STAFF_STOPPED.value
        stream.publish_token_hash = None
        changed = True
    if changed:
        await audit.record(
            session,
            actor=actor_of(principal),
            action="stream.stop",
            target=f"stream:{stream_id}",
            details={"from": previous, "source": stream.source},
        )
    await session.flush()
    view = await service.staff_view(session, stream_id)
    assert view is not None
    await session.commit()
    if changed:
        await mediamtx.kick(stream.path)
    return view


@router.get("/{stream_id}/recordings/{media_id}", status_code=status.HTTP_302_FOUND)
async def recording(
    principal: StaffReader, session: Session, stream_id: uuid.UUID, media_id: uuid.UUID
) -> RedirectResponse:
    await _visible_row(session, principal, stream_id)
    media = await session.scalar(
        select(Media).where(Media.id == media_id, Media.stream_id == stream_id, Media.kind == "recording")
    )
    if media is None or media.status != "stored":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    url = get_store().presign_get(
        media.object_key,
        expires_s=RECORDING_LINK_S,
        content_type="video/mp4",
        disposition=f'attachment; filename="{stream_id}-{media.id}.mp4"',
    )
    await audit.record(
        session,
        actor=actor_of(principal),
        action="stream.recording.download",
        target=f"media:{media_id}",
        details={"stream_id": str(stream_id), "sha256": media.sha256},
    )
    await session.commit()
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND, headers={"Cache-Control": "no-store"})
