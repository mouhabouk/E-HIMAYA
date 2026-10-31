"""Live-stream life cycle (docs/api/phase-6-contract.md, architecture §7).

    citizen: POST /reports/{id}/streams ─► pending ──(MediaMTX ready hook)──► live ──(not_ready / stop / max)──► ended
                                             └──(start window passed)──► expired
    staff:   POST /staff/streams (drone, camera) ─► pending ─► live ─► ended(publisher_stopped) ─► live …

Every change of state writes its domain event (outbox) in the same transaction. Kicking a publisher through the
MediaMTX API happens after the commit, best effort (``mediamtx.kick``).
"""

import base64
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from geoalchemy2 import Geography, Geometry
from sqlalchemy import Select, and_, cast, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.events import emit
from app.core.security import Principal
from app.modules.reports.domain import Status
from app.modules.reports.models import Media, Report
from app.modules.reports.service import in_scope
from app.modules.streams import schemas
from app.modules.streams.domain import (
    ACTIVE,
    FIXED_SOURCES,
    LOCATION_EVENT_INTERVAL_S,
    LOCATION_MIN_INTERVAL_S,
    RECONNECTABLE,
    EndReason,
    Source,
    StreamStatus,
    new_publish_token,
    path_of,
    publish_token_hash,
)
from app.modules.streams.models import LiveStream, StreamDetection, StreamLocation, StreamSegment

DETAIL_DETECTIONS = 200
DETAIL_TRACK_POINTS = 2000


def _point(lat: float, lon: float) -> Any:
    return cast(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), Geography)


# ---------------------------------------------------------------- views

_LAT = func.ST_Y(cast(LiveStream.last_location, Geometry))
_LON = func.ST_X(cast(LiveStream.last_location, Geometry))
_RECORDINGS = (
    select(func.count(Media.id))
    .where(Media.stream_id == LiveStream.id, Media.kind == "recording")
    .correlate(LiveStream)
    .scalar_subquery()
)


def _staff_select() -> Select[Any]:
    return select(LiveStream, Report.tracking_code, _LAT, _LON, _RECORDINGS).outerjoin(
        Report, Report.id == LiveStream.report_id
    )


def _duration(stream: LiveStream, now: datetime) -> float | None:
    if stream.started_at is None:
        return None
    end = stream.ended_at or (now if stream.status == StreamStatus.LIVE else stream.started_at)
    return round(max((end - stream.started_at).total_seconds(), 0.0), 1)


def staff_stream(row: Any, now: datetime | None = None) -> schemas.StaffStream:
    stream, tracking_code, lat, lon, recordings = row
    return schemas.StaffStream(
        id=stream.id,
        report_id=stream.report_id,
        tracking_code=tracking_code,
        source=stream.source,
        label=stream.label,
        status=stream.status,
        started_at=stream.started_at,
        ended_at=stream.ended_at,
        duration_s=_duration(stream, now or datetime.now(UTC)),
        gouvernorat_code=stream.gouvernorat_code,
        last_location=schemas.Point(lat=float(lat), lon=float(lon)) if lat is not None else None,
        max_fire_confidence=stream.max_fire_confidence,
        max_smoke_confidence=stream.max_smoke_confidence,
        recordings_count=int(recordings or 0),
        simulated=stream.source == Source.SIM,
    )


async def staff_view(session: AsyncSession, stream_id: uuid.UUID) -> schemas.StaffStream | None:
    row = (await session.execute(_staff_select().where(LiveStream.id == stream_id))).first()
    return staff_stream(row) if row is not None else None


def summary(stream: LiveStream) -> schemas.StreamSummary:
    return schemas.StreamSummary(
        stream_id=stream.id,
        status=stream.status,
        started_at=stream.started_at,
        ended_at=stream.ended_at,
        end_reason=stream.end_reason,
    )


def scope_filter(principal: Principal) -> Any:
    if principal.is_national:
        return True
    return LiveStream.gouvernorat_code == principal.gouvernorat_code


def visible(principal: Principal, stream: LiveStream) -> bool:
    return in_scope(principal, stream.gouvernorat_code)


def encode_cursor(created_at: datetime, stream_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{created_at.isoformat()}|{stream_id}".encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        at, sid = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode().split("|")
        return datetime.fromisoformat(at), uuid.UUID(sid)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc


async def staff_list(
    session: AsyncSession,
    principal: Principal,
    status_filter: str,
    gouvernorat: int | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[schemas.StaffStream], str | None]:
    query = _staff_select().where(scope_filter(principal))
    if status_filter != "all":
        query = query.where(LiveStream.status == status_filter)
    if gouvernorat is not None:
        query = query.where(LiveStream.gouvernorat_code == gouvernorat)
    if cursor:
        at, sid = decode_cursor(cursor)
        query = query.where(or_(LiveStream.created_at < at, and_(LiveStream.created_at == at, LiveStream.id < sid)))
    rows = (
        await session.execute(query.order_by(LiveStream.created_at.desc(), LiveStream.id.desc()).limit(limit))
    ).all()
    now = datetime.now(UTC)
    items = [staff_stream(r, now) for r in rows]
    next_cursor = encode_cursor(rows[-1][0].created_at, rows[-1][0].id) if len(rows) == limit else None
    return items, next_cursor


async def staff_detail(session: AsyncSession, row: Any) -> schemas.StaffStreamDetail:
    stream: LiveStream = row[0]
    recordings = await session.scalars(
        select(Media)
        .where(Media.stream_id == stream.id, Media.kind == "recording")
        .order_by(Media.created_at, Media.object_key)
    )
    detections = await session.scalars(
        select(StreamDetection)
        .where(StreamDetection.stream_id == stream.id)
        .order_by(StreamDetection.at.desc(), StreamDetection.id.desc())
        .limit(DETAIL_DETECTIONS)
    )
    point = cast(StreamLocation.location, Geometry)
    track = (
        await session.execute(
            select(StreamLocation.at, func.ST_Y(point), func.ST_X(point))
            .where(StreamLocation.stream_id == stream.id)
            .order_by(StreamLocation.at.desc(), StreamLocation.id.desc())
            .limit(DETAIL_TRACK_POINTS)
        )
    ).all()
    return schemas.StaffStreamDetail(
        **staff_stream(row).model_dump(),
        recordings=[
            schemas.RecordingOut(
                media_id=m.id, sha256=m.sha256, bytes=m.bytes, duration_s=m.duration_s, created_at=m.created_at
            )
            for m in recordings
        ],
        detections=[
            schemas.DetectionOut(at=d.at, label=d.label, confidence=d.confidence, boxes=d.boxes or [])
            for d in detections
        ],
        track=[schemas.TrackPoint(at=at, lat=float(lat), lon=float(lon)) for at, lat, lon in reversed(track)],
    )


# ---------------------------------------------------------------- events


async def emit_state(session: AsyncSession, subject: str, stream_id: uuid.UUID) -> None:
    """stream.started / stream.ended: the dashboard item, routed by the stream's gouvernorat."""
    await session.flush()
    view = await staff_view(session, stream_id)
    if view is not None:
        await emit(
            session,
            subject,
            {"stream_id": str(stream_id), "gouvernorat_code": view.gouvernorat_code, "stream": schemas.as_json(view)},
        )


# ---------------------------------------------------------------- citizen streams


async def create_for_report(session: AsyncSession, user_id: uuid.UUID, report_id: uuid.UUID) -> tuple[LiveStream, str]:
    settings = get_settings()
    report = await session.get(Report, report_id, with_for_update=True)
    if report is None or report.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report_not_found")
    if report.status in (Status.CLOSED.value, Status.REJECTED.value):
        raise HTTPException(status.HTTP_409_CONFLICT, "report_closed")
    now = datetime.now(UTC)
    active = await session.scalar(
        select(LiveStream).where(LiveStream.report_id == report_id, LiveStream.status.in_(ACTIVE)).with_for_update()
    )
    if active is not None:
        if active.status == StreamStatus.PENDING and active.expires_at is not None and active.expires_at <= now:
            # Never published within its start window: expire it now rather than wait for the worker.
            await expire(session, active, now)
        else:
            raise HTTPException(status.HTTP_409_CONFLICT, "stream_already_active")
    token = new_publish_token()
    stream_id = uuid.uuid4()
    stream = LiveStream(
        id=stream_id,
        report_id=report_id,
        user_id=user_id,
        source=Source.APP.value,
        path=path_of(stream_id),
        publish_token_hash=publish_token_hash(token),
        status=StreamStatus.PENDING.value,
        created_at=now,
        expires_at=now + timedelta(seconds=settings.stream_start_window_s),
        gouvernorat_code=report.gouvernorat_code,
    )
    session.add(stream)
    try:
        await session.flush()
    except IntegrityError:
        # A concurrent request created the report's stream first (unique partial index).
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "stream_already_active") from None
    return stream, token


def created_out(stream: LiveStream, token: str) -> schemas.StreamCreated:
    settings = get_settings()
    assert stream.expires_at is not None
    return schemas.StreamCreated(
        stream_id=stream.id,
        path=stream.path,
        whip_url=f"{settings.stream_webrtc_public_url}/{stream.path}/whip",
        publish_token=token,
        expires_at=stream.expires_at,
        max_duration_s=settings.stream_max_duration_s,
        location_interval_s=settings.stream_location_interval_s,
        simulated=stream.source == Source.SIM,
    )


async def owned_stream(
    session: AsyncSession, user_id: uuid.UUID, stream_id: uuid.UUID, *, lock: bool = False
) -> LiveStream:
    stream = await session.get(LiveStream, stream_id, with_for_update=lock)
    if stream is None or stream.user_id != user_id or stream.source != Source.APP:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return stream


async def record_location(session: AsyncSession, stream: LiveStream, body: schemas.LocationIn) -> bool:
    """Store a position of a pending/live stream. False when ignored (closer than 3 s to the previous one)."""
    if stream.status not in ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, "stream_not_active")
    now = datetime.now(UTC)
    if stream.last_location_at is not None and now - stream.last_location_at < timedelta(
        seconds=LOCATION_MIN_INTERVAL_S
    ):
        return False
    session.add(
        StreamLocation(stream_id=stream.id, at=now, location=_point(body.lat, body.lon), accuracy_m=body.accuracy_m)
    )
    stream.last_location = _point(body.lat, body.lon)
    stream.last_location_at = now
    if stream.location_event_at is None or now - stream.location_event_at >= timedelta(
        seconds=LOCATION_EVENT_INTERVAL_S
    ):
        stream.location_event_at = now
        await emit(
            session,
            "stream.location",
            {
                "stream_id": str(stream.id),
                "report_id": str(stream.report_id) if stream.report_id else None,
                "gouvernorat_code": stream.gouvernorat_code,
                "lat": body.lat,
                "lon": body.lon,
                "accuracy_m": body.accuracy_m,
                "at": now.isoformat(),
            },
        )
    return True


# ---------------------------------------------------------------- state changes


async def end(session: AsyncSession, stream: LiveStream, reason: EndReason, now: datetime | None = None) -> bool:
    """End a pending or live stream (idempotent). Returns True when the state changed."""
    if stream.status not in ACTIVE:
        return False
    now = now or datetime.now(UTC)
    stream.status = StreamStatus.ENDED.value
    stream.ended_at = now
    stream.end_reason = reason.value
    if reason is EndReason.STAFF_STOPPED or Source(stream.source) not in FIXED_SOURCES:
        # One publish session per citizen token; a fixed source stopped by staff is retired for good.
        stream.publish_token_hash = None
    _stop_vision(stream, now)
    await emit_state(session, "stream.ended", stream.id)
    return True


async def expire(session: AsyncSession, stream: LiveStream, now: datetime) -> None:
    stream.status = StreamStatus.EXPIRED.value
    stream.ended_at = now
    stream.end_reason = EndReason.TOKEN_EXPIRED.value
    stream.publish_token_hash = None
    await session.flush()


def _stop_vision(stream: LiveStream, now: datetime) -> None:
    if stream.vision_state in ("requested", "watching"):
        stream.vision_state = "stopping"
        stream.vision_attempts = 0
        stream.vision_next_attempt_at = now


def may_publish(stream: LiveStream, now: datetime) -> bool:
    """Whether the stream's path may be published to now (the token is checked separately)."""
    if stream.publish_token_hash is None:
        return False
    if stream.status == StreamStatus.PENDING:
        return stream.expires_at is None or stream.expires_at > now
    return (
        Source(stream.source) in FIXED_SOURCES
        and stream.status == StreamStatus.ENDED
        and stream.end_reason in RECONNECTABLE
    )


async def mark_live(session: AsyncSession, stream: LiveStream, now: datetime) -> bool:
    """MediaMTX ready hook. Returns False when the stream may not be live (the caller kicks the publisher)."""
    if stream.status == StreamStatus.LIVE:
        return True
    if not may_publish(stream, now):
        return False
    stream.status = StreamStatus.LIVE.value
    stream.started_at = stream.started_at or now
    stream.ended_at = None
    stream.end_reason = None
    stream.vision_state = "requested"
    stream.vision_attempts = 0
    stream.vision_next_attempt_at = now
    stream.vision_frames = []
    await emit_state(session, "stream.started", stream.id)
    return True


async def enqueue_segment(
    session: AsyncSession, stream: LiveStream, segment_path: str, duration_s: float | None
) -> bool:
    """Queue a finished recording segment once (repeated hooks are no-ops). True when newly queued."""
    exists = await session.scalar(select(StreamSegment.id).where(StreamSegment.segment_path == segment_path))
    if exists is not None:
        return False
    seq = await session.scalar(
        text("UPDATE reports.live_stream SET segment_seq = segment_seq + 1 WHERE id = :id RETURNING segment_seq"),
        {"id": stream.id},
    )
    await session.execute(
        text(
            "INSERT INTO reports.stream_segment (stream_id, segment_path, seq, duration_s) "
            "VALUES (:sid, :path, :seq, :duration) ON CONFLICT (segment_path) DO NOTHING"
        ),
        {"sid": stream.id, "path": segment_path, "seq": int(seq or 0), "duration": duration_s},
    )
    return True


# ---------------------------------------------------------------- fixed sources


@dataclass(frozen=True, slots=True)
class FixedSource:
    source: Source
    label: str
    gouvernorat_code: int
    lat: float | None
    lon: float | None
    # The institution whose camera this is (review point 25): its detections go to the owner first.
    org_id: uuid.UUID | None = None


async def register_fixed(session: AsyncSession, spec: FixedSource, actor: str) -> tuple[LiveStream, str]:
    from app.modules.geo.models import Gouvernorat

    if await session.get(Gouvernorat, spec.gouvernorat_code) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_gouvernorat")
    token = new_publish_token()
    stream_id = uuid.uuid4()
    now = datetime.now(UTC)
    stream = LiveStream(
        id=stream_id,
        source=spec.source.value,
        label=spec.label,
        path=path_of(stream_id),
        publish_token_hash=publish_token_hash(token),
        status=StreamStatus.PENDING.value,
        created_at=now,
        created_by=actor,
        gouvernorat_code=spec.gouvernorat_code,
        org_id=spec.org_id,
    )
    if spec.lat is not None and spec.lon is not None:
        stream.last_location = _point(spec.lat, spec.lon)
        stream.last_location_at = now
    session.add(stream)
    await session.flush()
    return stream, token


def rtsp_publish_url(stream: LiveStream) -> str:
    settings = get_settings()
    return f"rtsp://{settings.stream_ingest_host}:{settings.stream_rtsp_port}/{stream.path}"


def rtmp_publish_url(stream: LiveStream) -> str:
    settings = get_settings()
    return f"rtmp://{settings.stream_ingest_host}:{settings.stream_rtmp_port}/{stream.path}"
