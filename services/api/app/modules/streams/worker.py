"""Background loops of live streaming, run by the worker role (``WORKER_LOOPS`` in app/main.py).

* ``ingest_forever`` — recording segments announced by MediaMTX (``reports.stream_segment``): SHA-256 of the local
  fMP4 file, upload to S3 ``recordings/<stream_id>/<n>.mp4``, ``reports.media(kind=recording)``, local file deleted.
  Idempotent: the queue row is locked (SKIP LOCKED) and the object key is fixed, so a crash between the upload and
  the commit only re-uploads the same object. Segments no hook announced are picked up from the directory.
* ``streams_forever`` — expires citizen streams never started within their window, ends (and kicks) streams past
  their maximum duration, and keeps the vision service's watch list in line with the live streams.
* ``vision_images_forever`` — runs the detector on uploaded report images (``media.analysis.vision``).

Each loop is safe in several processes at once (row locks with SKIP LOCKED). The vision service being down never
blocks anything: work is retried with back-off.
"""

import asyncio
import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import structlog
from anyio import to_thread
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.events import emit
from app.core.storage import ObjectStore, get_store
from app.modules.ai import pipeline
from app.modules.reports.models import Media
from app.modules.streams import detections, mediamtx, service
from app.modules.streams.domain import EndReason, Source, StreamStatus, stream_id_of
from app.modules.streams.models import LiveStream, StreamSegment
from app.modules.streams.vision import VisionClient, VisionRejected, VisionUnavailable, get_vision_client

log = structlog.get_logger()

RECORDING_PREFIX = "recordings/"
SEGMENT_MAX_ATTEMPTS = 10
IMAGE_LOOKBACK = timedelta(days=7)
IMAGE_MAX_BYTES = 20 * 1024 * 1024


def _backoff(attempts: int, base_s: float = 5.0, cap_s: float = 600.0) -> timedelta:
    return timedelta(seconds=min(base_s * 2 ** max(attempts - 1, 0), cap_s))


# ---------------------------------------------------------------- recording segments


def segment_file(segment_path: str, stream_id: uuid.UUID) -> Path | None:
    """The local file of a segment, only when it is an .mp4 inside ``<recordings>/live/<stream_id>/``."""
    root = get_settings().stream_recordings_dir.resolve()
    try:
        candidate = Path(segment_path).resolve()
    except (OSError, RuntimeError):
        return None
    expected_dir = root / "live" / str(stream_id)
    if candidate.parent != expected_dir or candidate.suffix != ".mp4":
        return None
    return candidate


def _read_file(path: Path) -> bytes:
    return path.read_bytes()


async def ingest_one(sessionmaker: async_sessionmaker[AsyncSession], store: ObjectStore) -> bool:
    """Ingest one pending segment. Returns False when nothing was waiting."""
    async with sessionmaker() as session, session.begin():
        segment = await session.scalar(
            select(StreamSegment)
            .where(StreamSegment.state == "pending", StreamSegment.next_attempt_at <= datetime.now(UTC))
            .order_by(StreamSegment.next_attempt_at, StreamSegment.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if segment is None:
            return False
        stream = await session.get(LiveStream, segment.stream_id)
        path = segment_file(segment.segment_path, segment.stream_id)
        now = datetime.now(UTC)
        if stream is None or path is None:
            segment.state, segment.last_error = "failed", "invalid_path"
            return True
        if not await to_thread.run_sync(path.is_file):
            segment.state, segment.last_error, segment.done_at = "missing", "file_not_found", now
            log.warning("streams.segment_missing", stream_id=str(stream.id), seq=segment.seq)
            return True
        key = f"{RECORDING_PREFIX}{stream.id}/{segment.seq}.mp4"
        try:
            # The bytes hashed are the bytes uploaded (evidence integrity, NFR-07). A 60 s segment is a few MB to
            # a few tens of MB; segments are ingested one at a time per worker.
            data = await to_thread.run_sync(_read_file, path)
            digest, size = hashlib.sha256(data).hexdigest(), len(data)
            await store.put(key, data, "video/mp4")
        except Exception as exc:
            segment.attempts += 1
            segment.last_error = type(exc).__name__
            if segment.attempts >= SEGMENT_MAX_ATTEMPTS:
                segment.state = "failed"
                log.error("streams.segment_failed", stream_id=str(stream.id), seq=segment.seq, error=segment.last_error)
            else:
                segment.next_attempt_at = now + _backoff(segment.attempts)
            return True
        media = await session.scalar(select(Media).where(Media.object_key == key))
        if media is None:
            media = Media(
                report_id=stream.report_id,
                stream_id=stream.id,
                kind="recording",
                object_key=key,
                sha256=digest,
                bytes=size,
                duration_s=segment.duration_s,
                content_type="video/mp4",
                verified_type="video/mp4",
                status="stored",
                stored_at=now,
            )
            session.add(media)
            await session.flush()
        segment.state, segment.media_id, segment.done_at, segment.last_error = "done", media.id, now, None
        await emit(
            session,
            "stream.recording",
            {
                "stream_id": str(stream.id),
                "media_id": str(media.id),
                "report_id": str(stream.report_id) if stream.report_id else None,
                "gouvernorat_code": stream.gouvernorat_code,
                "sha256": digest,
                "duration_s": segment.duration_s,
            },
        )
    # Only once the row is committed: a failed commit leaves the file for the next attempt.
    try:
        await to_thread.run_sync(path.unlink)
    except FileNotFoundError:
        pass
    except OSError as exc:
        log.warning("streams.segment_unlink_failed", seq=segment.seq, error=type(exc).__name__)
    return True


def _orphans(root: Path, older_than: float) -> list[tuple[uuid.UUID, str]]:
    found: list[tuple[uuid.UUID, str]] = []
    base = root / "live"
    if not base.is_dir():
        return found
    for directory in base.iterdir():
        stream_id = stream_id_of(f"live/{directory.name}")
        if stream_id is None or not directory.is_dir():
            continue
        for file in directory.glob("*.mp4"):
            try:
                if file.stat().st_mtime < older_than:
                    found.append((stream_id, str(file)))
            except FileNotFoundError:
                continue
    return found


async def queue_orphans(sessionmaker: async_sessionmaker[AsyncSession]) -> int:
    """Queue segments left on disk without a hook (MediaMTX or the API restarted). Returns how many were queued."""
    settings = get_settings()
    older_than = datetime.now(UTC).timestamp() - settings.stream_segment_orphan_after_s
    files = await to_thread.run_sync(_orphans, settings.stream_recordings_dir.resolve(), older_than)
    queued = 0
    for stream_id, file in files:
        async with sessionmaker() as session, session.begin():
            stream = await session.get(LiveStream, stream_id, with_for_update=True)
            if stream is not None and await service.enqueue_segment(session, stream, file, None):
                queued += 1
                log.info("streams.segment_orphan_queued", stream_id=str(stream_id))
    return queued


async def ingest_forever(sessionmaker: async_sessionmaker[AsyncSession], idle_s: float = 1.0) -> None:
    last_scan = 0.0
    while True:
        try:
            worked = await ingest_one(sessionmaker, get_store())
            loop_time = asyncio.get_running_loop().time()
            if not worked and loop_time - last_scan > 60:
                last_scan = loop_time
                await queue_orphans(sessionmaker)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("streams.ingest_failed")
            worked = False
        if not worked:
            await asyncio.sleep(idle_s)


# ---------------------------------------------------------------- stream life cycle and vision watch list


async def sweep(sessionmaker: async_sessionmaker[AsyncSession], now: datetime | None = None) -> list[str]:
    """Expire unused citizen tokens and end streams past their maximum duration. Returns the paths to kick."""
    settings = get_settings()
    now = now or datetime.now(UTC)
    kick: list[str] = []
    async with sessionmaker() as session, session.begin():
        expired = list(
            await session.scalars(
                select(LiveStream)
                .where(LiveStream.status == StreamStatus.PENDING, LiveStream.expires_at <= now)
                .limit(200)
                .with_for_update(skip_locked=True)
            )
        )
        for stream in expired:
            await service.expire(session, stream, now)
        too_long = list(
            await session.scalars(
                select(LiveStream)
                .where(
                    LiveStream.status == StreamStatus.LIVE,
                    LiveStream.source.in_((Source.APP, Source.CREW)),
                    LiveStream.started_at <= now - timedelta(seconds=settings.stream_max_duration_s),
                )
                .limit(200)
                .with_for_update(skip_locked=True)
            )
        )
        for stream in too_long:
            await service.end(session, stream, EndReason.MAX_DURATION, now)
            kick.append(stream.path)
    for path in kick:
        await mediamtx.kick(path)
    return kick


async def sync_vision(sessionmaker: async_sessionmaker[AsyncSession], client: VisionClient | None) -> int:
    """Ask the vision service to watch new live streams and to stop ended ones. Returns the calls made."""
    settings = get_settings()
    now = datetime.now(UTC)
    calls = 0
    async with sessionmaker() as session, session.begin():
        rows = list(
            await session.scalars(
                select(LiveStream)
                .where(LiveStream.vision_state.in_(("requested", "stopping")), LiveStream.vision_next_attempt_at <= now)
                .order_by(LiveStream.vision_next_attempt_at)
                .limit(20)
                .with_for_update(skip_locked=True)
            )
        )
        for stream in rows:
            if client is None:
                stream.vision_state = "disabled" if stream.vision_state == "requested" else "idle"
                continue
            calls += 1
            try:
                if stream.vision_state == "requested":
                    if stream.status != StreamStatus.LIVE:
                        stream.vision_state = "idle"
                        continue
                    await client.watch(
                        str(stream.id),
                        f"{settings.stream_internal_rtsp_url}/{stream.path}",
                        settings.vision_callback_url,
                    )
                    stream.vision_state, stream.vision_attempts = "watching", 0
                else:
                    await client.unwatch(str(stream.id))
                    stream.vision_state, stream.vision_attempts = "idle", 0
            except VisionUnavailable as exc:
                stream.vision_attempts += 1
                stream.vision_next_attempt_at = now + _backoff(stream.vision_attempts, base_s=5, cap_s=60)
                if stream.vision_state == "stopping" and stream.vision_attempts >= settings.vision_max_attempts:
                    # The service forgets streams it can no longer read anyway; stop trying.
                    stream.vision_state = "idle"
                log.info(
                    "vision.watch_retry", stream_id=str(stream.id), error=str(exc), attempts=stream.vision_attempts
                )
    return calls


async def streams_forever(sessionmaker: async_sessionmaker[AsyncSession], idle_s: float = 2.0) -> None:
    while True:
        try:
            await sweep(sessionmaker)
            await sync_vision(sessionmaker, get_vision_client())
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("streams.sweep_failed")
        await asyncio.sleep(idle_s)


# ---------------------------------------------------------------- uploaded images


_IMAGE_CLAIM = text(
    """
    SELECT id FROM reports.media
    WHERE kind = 'image' AND status = 'stored' AND stream_id IS NULL AND report_id IS NOT NULL
      AND created_at >= :since
      AND (analysis IS NULL OR NOT analysis ? 'vision'
           OR (analysis->'vision'->>'state' = 'retry'
               AND CAST(analysis->'vision'->>'next_attempt_at' AS timestamptz) <= now()))
    ORDER BY created_at
    LIMIT 1
    FOR UPDATE SKIP LOCKED
    """
)


async def analyse_image(
    sessionmaker: async_sessionmaker[AsyncSession], client: VisionClient, store: ObjectStore
) -> bool:
    """Run the detector on one stored report image. Returns False when nothing was waiting."""
    settings = get_settings()
    async with sessionmaker() as session, session.begin():
        media_id = await session.scalar(_IMAGE_CLAIM, {"since": datetime.now(UTC) - IMAGE_LOOKBACK})
        if media_id is None:
            return False
        media = await session.get(Media, media_id)
        assert media is not None
        previous = (media.analysis or {}).get("vision") or {}
        attempts = int(previous.get("attempts") or 0) + 1
        now = datetime.now(UTC)
        try:
            if not media.bytes or media.bytes > IMAGE_MAX_BYTES:
                raise VisionRejected("image_too_large")
            try:
                image = await store.head(media.object_key, media.bytes)
            except Exception as exc:  # object store hiccup or missing object: retried, then given up
                raise VisionUnavailable(f"storage:{type(exc).__name__}") from exc
            result = await client.detect(image, media.verified_type or media.content_type or "image/jpeg")
        except VisionUnavailable as exc:
            state = "retry" if attempts < settings.vision_max_attempts else "failed"
            media.analysis = {
                **(media.analysis or {}),
                "vision": {
                    "state": state,
                    "attempts": attempts,
                    "error": str(exc)[:100],
                    "next_attempt_at": (now + _backoff(attempts, base_s=30, cap_s=3600)).isoformat(),
                },
            }
            return True
        except VisionRejected as exc:
            media.analysis = {**(media.analysis or {}), "vision": {"state": "failed", "error": exc.code[:100]}}
            return True
        confirmed = await detections.record_image(session, media, result)
        if confirmed and media.report_id is not None:
            await pipeline.rescore(session, [media.report_id], wait=False)
            log.info("vision.image_confirmed", media_id=str(media.id))
    return True


async def vision_images_forever(sessionmaker: async_sessionmaker[AsyncSession], idle_s: float = 5.0) -> None:
    while True:
        worked = False
        try:
            client = get_vision_client()
            if client is not None:
                worked = await analyse_image(sessionmaker, client, get_store())
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("vision.image_failed")
        if not worked:
            await asyncio.sleep(idle_s)
