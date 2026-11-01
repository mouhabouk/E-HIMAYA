"""The camera bridge (Yamen, 2026-11-01): a camera that detects fire on its own (a thermal camera's temperature alarm,
a camera's built-in fire or smoke detection) sends its alarm through a small bridge on the institution's network
(``services/camera-bridge``, guide ``docs/guides/camera-bridge.md``).

The bridge reaches the system over the internet like the camera's video already does (MediaMTX), so the endpoint is
public, and every alarm is signed by the camera's own key: HMAC-SHA256 in lower-case hex over
``"<camera>|<at>|<label>|<confidence>|<temperature>|<frame_sha256>"`` (the strings as sent; ``temperature`` and
``frame_sha256`` empty when absent). A heartbeat is signed over ``"<camera>|<at>|heartbeat"``.

* An alarm dated more than 10 minutes ahead of the server's clock, or a replay of the same (camera, at, label), is
  refused. One older than 10 minutes (kept by the bridge while the line was down) is stored but raises nothing.
* A fresh alarm goes through the same path as a fire the vision service confirmed (``detections.raise_alert``): the
  institution's staged pre-alert, or the room at once for a device the Civil Protection follows; one alert per
  label and camera every ``VISION_ALERT_COOLDOWN_S`` at most.
* The key is shown once to the staff member who registers the camera or renews its key, and is kept encrypted.
"""

import hashlib
import hmac
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import get_cipher
from app.core.db import get_session, get_system_session
from app.core.ratelimit import enforce, opaque
from app.core.security import Principal, require_roles
from app.modules.audit import service as audit
from app.modules.audit.service import actor_of
from app.modules.streams import detections
from app.modules.streams.domain import Source
from app.modules.streams.models import CameraEvent, LiveStream
from app.modules.streams.staff_router import REGISTER_ROLES

log = structlog.get_logger()

router = APIRouter(prefix="/api/v1/camera-events", tags=["camera-bridge"])
staff_router = APIRouter(prefix="/api/v1/staff/streams", tags=["staff-streams"])

KEY_CONTEXT = "reports.live_stream.event_key"
KEY_BYTES = 32
CLOCK_SKEW = timedelta(minutes=10)
MAX_AGE = timedelta(hours=48)
# A bridge posts a heartbeat every 5 minutes and an alarm now and then: 120 calls a minute per camera is ample.
RATE_LIMIT, RATE_WINDOW_S = 120, 60
_SIG = re.compile(r"^[0-9a-f]{64}$")
_NUMBER = re.compile(r"^-?\d{1,4}(\.\d{1,4})?$")

SystemSession = Annotated[AsyncSession, Depends(get_system_session)]
Session = Annotated[AsyncSession, Depends(get_session)]


def new_key() -> str:
    return secrets.token_hex(KEY_BYTES)


def seal(key: str) -> bytes:
    return get_cipher().encrypt(key, context=KEY_CONTEXT)


def key_of(stream: LiveStream) -> str | None:
    if stream.event_key_enc is None:
        return None
    return get_cipher().decrypt(stream.event_key_enc, context=KEY_CONTEXT)


def sign(key: str, *parts: str) -> str:
    return hmac.new(bytes.fromhex(key), "|".join(parts).encode(), hashlib.sha256).hexdigest()


def valid(key: str, signature: str, *parts: str) -> bool:
    return bool(_SIG.match(signature)) and hmac.compare_digest(sign(key, *parts), signature)


class EventIn(BaseModel):
    camera: uuid.UUID
    # ISO 8601 with its offset, exactly as signed.
    at: str = Field(max_length=40)
    label: Literal["fire", "smoke"]
    # Decimal strings, as signed: the camera's confidence (1 for a thermal threshold) and the temperature if any.
    confidence: str = Field(max_length=8)
    temperature: str = Field(default="", max_length=10)
    # What the camera called it (fireDetection, TMA, FireWarning…), for the history; not signed, not shown.
    vendor_event: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_.:-]*$")
    frame_jpeg_b64: str | None = Field(default=None, max_length=3_000_000)
    sig: str = Field(max_length=64)


class HeartbeatIn(BaseModel):
    camera: uuid.UUID
    at: str = Field(max_length=40)
    sig: str = Field(max_length=64)


class EventOut(BaseModel):
    accepted: bool
    alerted: bool


class EventKeyOut(BaseModel):
    camera: uuid.UUID
    key: str


def _parse_at(raw: str, now: datetime) -> datetime:
    try:
        at = datetime.fromisoformat(raw)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_at") from None
    if at.tzinfo is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_at")
    if at - now > CLOCK_SKEW or now - at > MAX_AGE:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "clock_skew")
    return at


async def _camera(session: AsyncSession, camera: uuid.UUID, signature: str, *parts: str) -> LiveStream:
    """The camera, once its signature checks out. Unknown camera and wrong signature answer the same 401."""
    await enforce(f"camera-bridge:{opaque(str(camera))}", RATE_LIMIT, RATE_WINDOW_S)
    stream = await session.get(LiveStream, camera, with_for_update=True)
    key = key_of(stream) if stream is not None and stream.source == Source.CAMERA.value else None
    if stream is None or key is None or not valid(key, signature, str(camera), *parts):
        log.info("camera_bridge.refused", camera=str(camera))
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_signature")
    return stream


@router.post("", response_model=EventOut, status_code=status.HTTP_202_ACCEPTED)
async def receive_event(body: EventIn, session: SystemSession) -> EventOut:
    """An alarm of the camera itself, relayed by its bridge."""
    now = datetime.now(UTC)
    frame = detections.decode_frame(body.frame_jpeg_b64)
    if body.frame_jpeg_b64 and frame is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_frame")
    frame_sha = hashlib.sha256(frame).hexdigest() if frame else ""
    stream = await _camera(
        session, body.camera, body.sig, body.at, body.label, body.confidence, body.temperature, frame_sha
    )
    at = _parse_at(body.at, now)
    if not _NUMBER.match(body.confidence) or not 0 <= float(body.confidence) <= 1:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_confidence")
    if body.temperature and not _NUMBER.match(body.temperature):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_temperature")
    confidence = float(body.confidence)
    stream.bridge_seen_at = now
    event = CameraEvent(
        stream_id=stream.id,
        at=at,
        label=body.label,
        confidence=confidence,
        temperature_c=float(body.temperature) if body.temperature else None,
        vendor_event=body.vendor_event,
    )
    try:
        async with session.begin_nested():
            session.add(event)
            await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "replay") from None
    fresh = now - at <= CLOCK_SKEW
    cooled = detections.cooled_down(stream, body.label, at, get_settings().vision_alert_cooldown_s)
    if fresh and cooled:
        media = (
            await detections.store_frame(session, stream, frame, body.label, confidence, "camera-bridge")
            if frame
            else None
        )
        event.alerted, event.media_id = True, media.id if media else None
        await detections.raise_alert(session, stream, body.label, confidence, at, media)
    await session.commit()
    log.info("camera_bridge.event", camera=str(stream.id), label=body.label, alerted=event.alerted, fresh=fresh)
    return EventOut(accepted=True, alerted=event.alerted)


@router.post("/heartbeat", status_code=status.HTTP_204_NO_CONTENT)
async def heartbeat(body: HeartbeatIn, session: SystemSession) -> Response:
    """The bridge is alive (every 5 minutes by default)."""
    stream = await _camera(session, body.camera, body.sig, body.at, "heartbeat")
    now = datetime.now(UTC)
    at = _parse_at(body.at, now)
    if now - at > CLOCK_SKEW:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "clock_skew")
    stream.bridge_seen_at = now
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@staff_router.post("/{stream_id}/event-key", response_model=EventKeyOut)
async def renew_event_key(
    stream_id: uuid.UUID,
    session: Session,
    principal: Annotated[Principal, Depends(require_roles(*REGISTER_ROLES))],
) -> EventKeyOut:
    """A new signing key for the camera's bridge, shown once (the old one stops working at once)."""
    stream = await session.scalar(select(LiveStream).where(LiveStream.id == stream_id).with_for_update())
    if stream is None or stream.source != Source.CAMERA.value:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if not principal.is_national and stream.gouvernorat_code != principal.gouvernorat_code:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
    key = new_key()
    stream.event_key_enc = seal(key)
    await audit.record(session, actor=actor_of(principal), action="stream.event_key", target=f"stream:{stream.id}")
    await session.commit()
    return EventKeyOut(camera=stream.id, key=key)
