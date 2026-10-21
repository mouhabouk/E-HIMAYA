"""Internal endpoints of live streaming (docs/api/phase-6-contract.md §3), never routed by Caddy.

* ``POST /internal/mediamtx/auth``  — MediaMTX ``authHTTPAddress``: 200 allows, 401 denies (decision table below).
* ``POST /internal/mediamtx/hooks`` — MediaMTX hook script (``X-Hook-Token``): ready, not_ready, segment_complete.
* ``POST /internal/vision/detections`` — vision service callback (``X-Vision-Token``).
* SIMULATION ``POST /internal/sim/streams`` and ``GET /internal/sim/streams/{id}`` — stream-sim (``X-Sim-Token``),
  answering 404 unless STREAM_SIM_TOKEN is set (never in production).

Auth decision table (anything not listed is denied; every denial is logged without any token):

| action                 | allowed when                                                                            |
|------------------------|-----------------------------------------------------------------------------------------|
| publish                | path ``live/<id>`` of a stream that may publish now (pending and within its window, or   |
|                        | a fixed source reconnecting) and the token (``token``, ``password`` or query ``token=``) |
|                        | matches its hash; citizen streams only over WebRTC (WHIP)                                |
| read, playback         | user ``vision`` with VISION_READ_PASSWORD on any ``live/<id>`` path, or a valid viewer   |
|                        | token of that exact path while the stream is pending or live                            |
| api, metrics, pprof    | user MEDIAMTX_API_USER with MEDIAMTX_API_PASSWORD                                        |
"""

import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import parse_qs

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_system_session
from app.core.ratelimit import opaque
from app.modules.reports.models import Media
from app.modules.streams import detections, mediamtx, schemas, service
from app.modules.streams.domain import (
    ACTIVE,
    EndReason,
    Source,
    path_of,
    publish_token_matches,
    stream_id_of,
    viewer_token_valid,
)
from app.modules.streams.models import LiveStream

log = structlog.get_logger()
router = APIRouter(include_in_schema=False)
Session = Annotated[AsyncSession, Depends(get_system_session)]

VISION_USER = "vision"
SIM_LABEL_PREFIX = "[SIM] "


def _secret_matches(presented: str, expected: SecretStr | None) -> bool:
    return (
        expected is not None
        and bool(presented)
        and hmac.compare_digest(presented.encode(), expected.get_secret_value().encode())
    )


def _query_token(query: str) -> str:
    values = parse_qs(query, keep_blank_values=False).get("token") or []
    return values[0] if len(values) == 1 else ""


def presented_token(body: schemas.MediamtxAuthIn) -> str:
    return body.token or body.password or _query_token(body.query)


@dataclass(frozen=True, slots=True)
class Decision:
    allowed: bool
    reason: str


async def decide(session: AsyncSession, body: schemas.MediamtxAuthIn, now: datetime | None = None) -> Decision:
    """The MediaMTX authorization decision (pure apart from reading the stream)."""
    settings = get_settings()
    now = now or datetime.now(UTC)
    action = body.action
    if action in ("api", "metrics", "pprof"):
        ok = body.user == settings.mediamtx_api_user and _secret_matches(body.password, settings.mediamtx_api_password)
        return Decision(ok, "internal_api_user" if ok else "bad_api_credentials")
    if action not in ("publish", "read", "playback"):
        return Decision(False, "unknown_action")
    stream_id = stream_id_of(body.path)
    if stream_id is None:
        return Decision(False, "unknown_path")
    if action != "publish" and body.user == VISION_USER:
        ok = _secret_matches(body.password, settings.vision_read_password)
        return Decision(ok, "vision_reader" if ok else "bad_vision_credentials")
    stream = await session.get(LiveStream, stream_id)
    if stream is None:
        return Decision(False, "unknown_stream")
    token = presented_token(body)
    if not token:
        return Decision(False, "no_token")
    if action == "publish":
        if not service.may_publish(stream, now):
            return Decision(False, f"not_publishable_{stream.status}")
        if stream.source == Source.APP and body.protocol != "webrtc":
            return Decision(False, "protocol_not_allowed")
        ok = publish_token_matches(token, stream.publish_token_hash)
        return Decision(ok, "publish_token" if ok else "bad_publish_token")
    if stream.status not in ACTIVE:
        return Decision(False, f"not_readable_{stream.status}")
    ok = viewer_token_valid(token, path_of(stream.id), now.timestamp())
    return Decision(ok, "viewer_token" if ok else "bad_viewer_token")


@router.post("/internal/mediamtx/auth")
async def mediamtx_auth(body: schemas.MediamtxAuthIn, session: Session) -> Response:
    decision = await decide(session, body)
    if decision.allowed:
        return Response(status_code=status.HTTP_200_OK)
    # RTSP and HLS clients first try without credentials (then answer the challenge): "no_token" is routine.
    log.info(
        "mediamtx.auth_denied",
        action=body.action,
        path=body.path[:80],
        protocol=body.protocol,
        reason=decision.reason,
        client=opaque(body.ip) if body.ip else None,
    )
    return JSONResponse({"detail": "denied"}, status_code=status.HTTP_401_UNAUTHORIZED)


def _require(expected: SecretStr | None, presented: str | None) -> None:
    if not _secret_matches(presented or "", expected):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")


@router.post("/internal/mediamtx/hooks", status_code=status.HTTP_204_NO_CONTENT)
async def mediamtx_hook(
    body: schemas.HookIn,
    session: Session,
    x_hook_token: Annotated[str | None, Header(max_length=512)] = None,
) -> Response:
    _require(get_settings().mediamtx_hook_token, x_hook_token)
    stream_id = stream_id_of(body.path)
    stream = await session.get(LiveStream, stream_id, with_for_update=True) if stream_id else None
    if stream is None:
        log.warning("mediamtx.hook_unknown_path", hook=body.event, path=body.path[:80])
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    now = datetime.now(UTC)
    kick = False
    if body.event == "ready":
        kick = not await service.mark_live(session, stream, now)
        if kick:
            log.warning("mediamtx.ready_refused", stream_id=str(stream.id), status=stream.status)
    elif body.event == "not_ready":
        await service.end(session, stream, EndReason.PUBLISHER_STOPPED, now)
    elif body.segment_path:
        if await service.enqueue_segment(session, stream, body.segment_path, body.segment_duration_s):
            log.info("streams.segment_queued", stream_id=str(stream.id), duration_s=body.segment_duration_s)
    await session.commit()
    if kick:
        await mediamtx.kick(stream.path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/internal/vision/detections", status_code=status.HTTP_204_NO_CONTENT)
async def vision_detections(
    body: schemas.DetectionsIn,
    session: Session,
    x_vision_token: Annotated[str | None, Header(max_length=512)] = None,
) -> Response:
    _require(get_settings().vision_callback_token, x_vision_token)
    stream = await detections.live_stream_for_callback(session, body.stream_id)
    if stream is None:
        # Ended meanwhile (the watch list catches up) or unknown: nothing to record.
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    await detections.record_frame(session, stream, body)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- simulation
# ┏━━ SIMULATION ━━ stream-sim (compose profile "sim") registers a source=sim stream here at start-up, then publishes
# ┃   a looped sample clip over RTSP with the returned token. Every stream it creates carries "simulated": true.
# ┃ PRODUCTION: leave STREAM_SIM_TOKEN empty (APP_ENV=production refuses it) and these endpoints answer 404; real
# ┃   drones and cameras are registered by staff with POST /api/v1/staff/streams (docs/streaming.md).
# ┗━━━━━━━━━━━━━━━━


def _sim_enabled(x_sim_token: str | None) -> None:
    settings = get_settings()
    if settings.app_env == "production":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    _require(settings.stream_sim_token, x_sim_token)


@router.post("/internal/sim/streams", response_model=schemas.SimStreamOut, status_code=status.HTTP_201_CREATED)
async def sim_register(
    body: schemas.SimStreamIn,
    session: Session,
    x_sim_token: Annotated[str | None, Header(max_length=512)] = None,
) -> schemas.SimStreamOut:
    _sim_enabled(x_sim_token)
    label = body.label if body.label.startswith(SIM_LABEL_PREFIX) else f"{SIM_LABEL_PREFIX}{body.label}"[:100]
    # A restarted simulator replaces its previous stream of the same label.
    previous = list(
        await session.scalars(
            select(LiveStream)
            .where(LiveStream.source == Source.SIM, LiveStream.label == label, LiveStream.status.in_(ACTIVE))
            .with_for_update()
        )
    )
    for old in previous:
        await service.end(session, old, EndReason.STAFF_STOPPED)
    kick = [old.path for old in previous]
    spec = service.FixedSource(Source.SIM, label, body.gouvernorat_code, body.lat, body.lon)
    stream, token = await service.register_fixed(session, spec, "system:stream-sim")
    await session.commit()
    for path in kick:
        await mediamtx.kick(path)
    log.info("[SIM] stream registered", stream_id=str(stream.id), label=label)
    return schemas.SimStreamOut(
        id=stream.id, path=stream.path, publish_token=token, rtsp_url=service.rtsp_publish_url(stream)
    )


@router.get("/internal/sim/streams/{stream_id}", response_model=schemas.SimStreamStatus)
async def sim_status(
    stream_id: uuid.UUID,
    session: Session,
    x_sim_token: Annotated[str | None, Header(max_length=512)] = None,
) -> schemas.SimStreamStatus:
    _sim_enabled(x_sim_token)
    stream = await session.get(LiveStream, stream_id)
    if stream is None or stream.source != Source.SIM:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    recordings = await session.scalar(
        select(func.count(Media.id)).where(Media.stream_id == stream_id, Media.kind == "recording")
    )
    return schemas.SimStreamStatus(
        id=stream.id, status=stream.status, recordings_count=int(recordings or 0), simulated=True
    )
