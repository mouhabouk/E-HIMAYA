"""Background loops of telephony, run by the worker role (``WORKER_LOOPS`` in app/main.py).

* ``ari_events_forever`` — the ARI WebSocket (``/ari/events?app=ehimaya&subscribeAll=true``): call life cycle from the
  dialplan's ``EhimayaCall`` user events and ``ChannelDestroyed``. One process holds the connection at a time (a
  PostgreSQL advisory lock held on a dedicated connection); it reconnects with back-off and, after every
  (re)connection, ends the calls whose channel disappeared meanwhile.
* ``recordings_forever`` — MixMonitor WAV files of ended calls: SHA-256, upload to S3 ``calls/<call_id>.wav``,
  ``reports.media(kind=call_recording)``, local file deleted (idempotent like phase 6 segments). Files no event
  announced (the API was down during the call) become ``untracked`` calls so no recording is ever lost.
* ``endpoints_forever`` — operator endpoints whose credentials expired leave the queue and Asterisk.

Without TELEPHONY_ARI_URL the loops only ingest recordings already on disk.
"""

import asyncio
import hashlib
import json
import struct
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import structlog
from anyio import to_thread
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.events import emit
from app.core.storage import ObjectStore, get_store
from app.modules.reports.models import Media
from app.modules.telephony import service
from app.modules.telephony.ari import AriUnavailable, HttpAriClient, basic_auth_header, get_ari
from app.modules.telephony.domain import CallStatus, Direction, EndReason, Source, valid_channel_id
from app.modules.telephony.models import Call, OperatorEndpoint

log = structlog.get_logger()

RECORDING_PREFIX = "calls/"
RECORDING_MAX_ATTEMPTS = 8
# A recording file is complete once Asterisk stopped writing it for this long.
FILE_QUIET_S = 2.0
ORPHAN_AFTER = timedelta(minutes=10)
LEADER_LOCK = 0x45485F415249  # "EH_ARI"


def _backoff(attempts: int, base_s: float = 5.0, cap_s: float = 600.0) -> timedelta:
    return timedelta(seconds=min(base_s * 2 ** max(attempts - 1, 0), cap_s))


# ---------------------------------------------------------------- ARI events


async def process(sessionmaker: async_sessionmaker[AsyncSession], raw: str | bytes) -> None:
    try:
        event = json.loads(raw)
    except ValueError:
        log.warning("telephony.bad_event")
        return
    if not isinstance(event, dict):
        return
    async with sessionmaker() as session, session.begin():
        await service.handle_event(session, event)


async def _reconcile(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    client = get_ari()
    if client is None:
        return
    try:
        live = await client.channel_ids()
    except AriUnavailable as exc:
        log.warning("telephony.reconcile_failed", error=str(exc)[:120])
        return
    async with sessionmaker() as session, session.begin():
        ended = await service.reconcile(session, live)
    if ended:
        log.info("telephony.reconciled", ended=ended)


async def _listen(sessionmaker: async_sessionmaker[AsyncSession], url: str) -> None:
    from websockets.asyncio.client import connect

    async with connect(
        url, additional_headers={"Authorization": basic_auth_header()}, open_timeout=10, ping_interval=20
    ) as websocket:
        log.info("telephony.ari_connected")
        await _reconcile(sessionmaker)
        async for message in websocket:
            try:
                await process(sessionmaker, message)
            except Exception:
                # One bad event never stops the stream (the call is reconciled on the next reconnection).
                log.exception("telephony.event_failed")


async def ari_events_forever(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    delay = 1.0
    engine: AsyncEngine = sessionmaker.kw["bind"]
    while True:
        client = get_ari()
        if not isinstance(client, HttpAriClient):
            await asyncio.sleep(30)
            continue
        try:
            # Session-level advisory lock on a connection held for the whole stream (autocommit: no transaction left
            # open); released when the connection closes, process death included.
            async with engine.connect() as raw:
                leader = await raw.execution_options(isolation_level="AUTOCOMMIT")
                if not await leader.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": LEADER_LOCK}):
                    await asyncio.sleep(15)
                    continue
                try:
                    await _listen(sessionmaker, client.events_url())
                    delay = 1.0
                finally:
                    await leader.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LEADER_LOCK})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("telephony.ari_disconnected", error=type(exc).__name__, retry_s=delay)
        await asyncio.sleep(delay)
        delay = min(delay * 2, 30.0)


# ---------------------------------------------------------------- recordings


def recording_file(channel_id: str) -> Path | None:
    """``<recordings>/<channel_id>.wav`` when the id is a plain Asterisk channel id, else None."""
    if not valid_channel_id(channel_id):
        return None
    root = get_settings().telephony_recordings_dir.resolve()
    candidate = (root / f"{channel_id}.wav").resolve()
    return candidate if candidate.parent == root else None


def wav_duration(data: bytes) -> float | None:
    """Duration of a PCM WAV file from its header (fmt and data chunks), None when unreadable."""
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None
    offset, byte_rate, size = 12, 0, None
    while offset + 8 <= len(data):
        chunk, length = data[offset : offset + 4], struct.unpack("<I", data[offset + 4 : offset + 8])[0]
        if chunk == b"fmt " and length >= 16:
            byte_rate = struct.unpack("<I", data[offset + 16 : offset + 20])[0]
        elif chunk == b"data":
            # A header left open by a crash holds 0 or a placeholder: the bytes present are the truth then.
            remaining = len(data) - offset - 8
            size = remaining if length == 0 else min(length, remaining)
            break
        offset += 8 + length + (length & 1)
    if not byte_rate or size is None:
        return None
    return round(size / byte_rate, 1)


def _file_state(path: Path) -> tuple[bool, float]:
    try:
        return True, path.stat().st_mtime
    except FileNotFoundError:
        return False, 0.0


async def ingest_one(sessionmaker: async_sessionmaker[AsyncSession], store: ObjectStore) -> bool:
    """Ingest one ended call's recording. Returns False when nothing was waiting."""
    async with sessionmaker() as session, session.begin():
        call = await session.scalar(
            select(Call)
            .where(
                Call.recording_state == "pending",
                Call.ended_at.is_not(None),
                Call.recording_next_at <= datetime.now(UTC),
            )
            .order_by(Call.recording_next_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if call is None:
            return False
        now = datetime.now(UTC)
        path = recording_file(call.channel_id)
        if path is None:
            call.recording_state, call.recording_error = "failed", "invalid_path"
            return True
        exists, mtime = await to_thread.run_sync(_file_state, path)
        if not exists or now.timestamp() - mtime < FILE_QUIET_S:
            call.recording_attempts += 1
            if call.recording_attempts >= RECORDING_MAX_ATTEMPTS:
                call.recording_state, call.recording_error = "missing", "file_not_found"
            else:
                call.recording_next_at = now + _backoff(call.recording_attempts, base_s=2, cap_s=120)
            return True
        key = f"{RECORDING_PREFIX}{call.id}.wav"
        try:
            # The bytes hashed are the bytes uploaded (evidence integrity, NFR-07); 8 kHz WAV is ~1 MB per minute.
            data = await to_thread.run_sync(path.read_bytes)
            digest, size = hashlib.sha256(data).hexdigest(), len(data)
            await store.put(key, data, "audio/wav")
        except Exception as exc:
            call.recording_attempts += 1
            call.recording_error = type(exc).__name__
            if call.recording_attempts >= RECORDING_MAX_ATTEMPTS:
                call.recording_state = "failed"
                log.error("telephony.recording_failed", call_id=str(call.id), error=call.recording_error)
            else:
                call.recording_next_at = now + _backoff(call.recording_attempts)
            return True
        media = await session.scalar(select(Media).where(Media.object_key == key))
        if media is None:
            # Not attached to the report (reporters never see call recordings); the call references it.
            media = Media(
                kind="call_recording",
                object_key=key,
                sha256=digest,
                bytes=size,
                duration_s=wav_duration(data),
                content_type="audio/wav",
                verified_type="audio/wav",
                status="stored",
                stored_at=now,
            )
            session.add(media)
            await session.flush()
        call.recording_media_id, call.recording_state, call.recording_error = media.id, "done", None
        call.updated_at = now
        await emit(
            session,
            "call.recording",
            {
                "call_id": str(call.id),
                "media_id": str(media.id),
                "gouvernorat_code": call.gouvernorat_code,
                "sha256": digest,
                "duration_s": media.duration_s,
            },
        )
    try:
        await to_thread.run_sync(path.unlink)
    except FileNotFoundError:
        pass
    except OSError as exc:
        log.warning("telephony.recording_unlink_failed", error=type(exc).__name__)
    return True


def _orphans(root: Path, older_than: float) -> list[tuple[str, float]]:
    found: list[tuple[str, float]] = []
    if not root.is_dir():
        return found
    for file in root.glob("*.wav"):
        try:
            mtime = file.stat().st_mtime
        except FileNotFoundError:
            continue
        if mtime < older_than and valid_channel_id(file.stem):
            found.append((file.stem, mtime))
    return found


async def queue_orphans(sessionmaker: async_sessionmaker[AsyncSession]) -> int:
    """Recordings nobody announced (the API was down during the call): queued as ``untracked`` calls."""
    settings = get_settings()
    older_than = (datetime.now(UTC) - ORPHAN_AFTER).timestamp()
    files = await to_thread.run_sync(_orphans, settings.telephony_recordings_dir.resolve(), older_than)
    queued = 0
    for channel_id, mtime in files[:200]:
        async with sessionmaker() as session, session.begin():
            call = await session.scalar(select(Call).where(Call.channel_id == channel_id).with_for_update())
            ended = datetime.fromtimestamp(mtime, UTC)
            if call is None:
                session.add(
                    Call(
                        id=uuid.uuid4(),
                        channel_id=channel_id,
                        direction=Direction.INBOUND.value,
                        source=Source.UNKNOWN.value,
                        started_at=ended,
                        ended_at=ended,
                        status=CallStatus.ENDED.value,
                        end_reason=EndReason.UNTRACKED.value,
                        recording_state="pending",
                    )
                )
                queued += 1
            elif call.recording_state in ("none", "missing") and call.ended_at is not None:
                call.recording_state, call.recording_attempts = "pending", 0
                call.recording_next_at = datetime.now(UTC)
                queued += 1
    if queued:
        log.info("telephony.orphan_recordings", queued=queued)
    return queued


async def recordings_forever(sessionmaker: async_sessionmaker[AsyncSession], idle_s: float = 1.0) -> None:
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
            log.exception("telephony.ingest_failed")
            worked = False
        if not worked:
            await asyncio.sleep(idle_s)


# ---------------------------------------------------------------- operator endpoints


async def retire_expired(sessionmaker: async_sessionmaker[AsyncSession], now: datetime | None = None) -> int:
    client = get_ari()
    if client is None:
        return 0
    now = now or datetime.now(UTC)
    retired = 0
    async with sessionmaker() as session, session.begin():
        rows = list(
            await session.scalars(
                select(OperatorEndpoint)
                .where(OperatorEndpoint.removed_at.is_(None), OperatorEndpoint.expires_at <= now)
                .limit(50)
                .with_for_update(skip_locked=True)
            )
        )
        for row in rows:
            try:
                await service.retire_endpoint(client, row, now)
                retired += 1
            except AriUnavailable as exc:
                log.warning("telephony.retire_failed", endpoint=row.endpoint, error=str(exc)[:120])
                break
    return retired


async def endpoints_forever(sessionmaker: async_sessionmaker[AsyncSession], idle_s: float = 30.0) -> None:
    while True:
        try:
            await retire_expired(sessionmaker)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("telephony.endpoints_failed")
        await asyncio.sleep(idle_s)
