"""Retention and anonymisation jobs (law 2004-63; architecture §5.3: reports 5 years, then anonymised).

Run by the worker role every ``RETENTION_INTERVAL_S``. Each job works in bounded batches, in its own
transaction, under a transaction-level advisory lock, so several worker processes never run the same job
at once and a crash leaves at most one batch to redo. Durations come from the settings (``RETENTION_*``).

| job                 | what                                                                   | default  |
|---------------------|------------------------------------------------------------------------|----------|
| events              | relayed domain events (events.outbox)                                  | 7 days   |
| notify_outbox       | sent/skipped/failed pushes and e-mails (notify.outbox)                 | 30 days  |
| notify_dispatch     | finished fan-out jobs (notify.dispatch)                                | 180 days |
| device_locations    | rounded position of push devices not refreshed                         | 30 days  |
| devices             | push devices not refreshed by the app                                  | 180 days |
| reports             | closed/rejected reports: anonymised (reporter, text, media, precision) | 5 years  |
| consents            | acceptances of a superseded charter version                            | 5 years  |
| anonymous_accounts  | device identities with no report and no device                         | 365 days |
| erasure_requests    | erasure requests once the identity-provider account was disabled       | 30 days  |
"""

import asyncio
import zlib
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.storage import get_store
from app.modules.audit import service as audit
from app.modules.identity.models import DETACHED_ACCOUNT_ID

log = structlog.get_logger()

BATCH = 1000
# Reports are anonymised in smaller batches: each one also deletes media objects.
REPORT_BATCH = 200
# Point precision kept on an anonymised report: 0.01° (about 1 km), enough for statistics by area.
COARSE_GRID_DEG = 0.01

Job = Callable[[AsyncSession, Settings, datetime], Awaitable[int]]


def _cutoff(now: datetime, days: int) -> datetime:
    return now - timedelta(days=days)


async def _delete(session: AsyncSession, table: str, key: str, where: str, params: dict[str, object]) -> int:
    result = await session.execute(
        text(
            f"DELETE FROM {table} WHERE {key} IN (SELECT {key} FROM {table} WHERE {where} "  # noqa: S608 (constant SQL fragments, values are bound)
            f"LIMIT :n FOR UPDATE SKIP LOCKED)"
        ),
        {**params, "n": BATCH},
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


async def purge_events(session: AsyncSession, settings: Settings, now: datetime) -> int:
    cutoff = _cutoff(now, settings.retention_events_days)
    return await _delete(session, "events.outbox", "id", "published_at < :cutoff", {"cutoff": cutoff})


async def purge_notify_outbox(session: AsyncSession, settings: Settings, now: datetime) -> int:
    cutoff = _cutoff(now, settings.retention_notify_outbox_days)
    return await _delete(
        session, "notify.outbox", "id", "status <> 'pending' AND created_at < :cutoff", {"cutoff": cutoff}
    )


async def purge_notify_dispatch(session: AsyncSession, settings: Settings, now: datetime) -> int:
    cutoff = _cutoff(now, settings.retention_notify_dispatch_days)
    result = await session.execute(
        text(
            "DELETE FROM notify.dispatch d USING (SELECT message_id, channel, purpose FROM notify.dispatch "
            "WHERE status IN ('done', 'skipped', 'failed') AND finished_at < :cutoff "
            "LIMIT :n FOR UPDATE SKIP LOCKED) o "
            "WHERE (d.message_id, d.channel, d.purpose) = (o.message_id, o.channel, o.purpose)"
        ),
        {"cutoff": cutoff, "n": BATCH},
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


async def forget_device_locations(session: AsyncSession, settings: Settings, now: datetime) -> int:
    cutoff = _cutoff(now, settings.retention_device_location_days)
    result = await session.execute(
        text(
            "UPDATE notify.device SET location = NULL WHERE token IN (SELECT token FROM notify.device "
            "WHERE location IS NOT NULL AND updated_at < :cutoff LIMIT :n FOR UPDATE SKIP LOCKED)"
        ),
        {"cutoff": cutoff, "n": BATCH},
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


async def purge_devices(session: AsyncSession, settings: Settings, now: datetime) -> int:
    cutoff = _cutoff(now, settings.retention_device_days)
    return await _delete(session, "notify.device", "token", "updated_at < :cutoff", {"cutoff": cutoff})


async def anonymise_reports(session: AsyncSession, settings: Settings, now: datetime) -> int:
    """Closed/rejected reports past retention keep category, times, status, scores and a coarse area only."""
    cutoff = _cutoff(now, settings.retention_report_days)
    ids = list(
        await session.scalars(
            text(
                "SELECT id FROM reports.report WHERE status IN ('closed', 'rejected') AND anonymised_at IS NULL "
                "AND updated_at < :cutoff ORDER BY updated_at LIMIT :n FOR UPDATE SKIP LOCKED"
            ),
            {"cutoff": cutoff, "n": REPORT_BATCH},
        )
    )
    if not ids:
        return 0
    keys = list(
        await session.scalars(text("SELECT object_key FROM reports.media WHERE report_id = ANY(:ids)"), {"ids": ids})
    )
    await session.execute(text("DELETE FROM reports.media WHERE report_id = ANY(:ids)"), {"ids": ids})
    await session.execute(
        text(
            "UPDATE reports.report SET user_id = :detached, client_uuid = NULL, text_original_enc = NULL, "
            "text_ar_enc = NULL, search_tokens = '{}', embedding = NULL, location_accuracy_m = NULL, "
            "location = CAST(ST_SnapToGrid(CAST(location AS geometry), :grid) AS geography), "
            "anonymised_at = :now WHERE id = ANY(:ids)"
        ),
        {"ids": ids, "detached": DETACHED_ACCOUNT_ID, "grid": COARSE_GRID_DEG, "now": now},
    )
    await session.execute(
        text("UPDATE reports.status_history SET note = NULL WHERE report_id = ANY(:ids)"), {"ids": ids}
    )
    await session.execute(
        text("UPDATE ai.analysis SET extraction_enc = NULL, last_error = NULL WHERE report_id = ANY(:ids)"),
        {"ids": ids},
    )
    await audit.record(
        session,
        actor=audit.SYSTEM_ACTOR,
        action="retention.anonymise",
        details={"reports": len(ids), "media_objects": len(keys)},
    )
    # Objects first: if the commit then fails, the batch is redone and deleting a missing object is a no-op.
    if keys:
        await get_store().delete(*keys)
    return len(ids)


async def purge_consents(session: AsyncSession, settings: Settings, now: datetime) -> int:
    cutoff = _cutoff(now, settings.retention_consent_days)
    return await _delete(
        session,
        "identity.consent",
        "id",
        "accepted_at < :cutoff AND EXISTS (SELECT 1 FROM identity.consent newer WHERE newer.user_id = "
        "identity.consent.user_id AND newer.charter_version <> identity.consent.charter_version "
        "AND newer.accepted_at > identity.consent.accepted_at)",
        {"cutoff": cutoff},
    )


async def purge_anonymous_accounts(session: AsyncSession, settings: Settings, now: datetime) -> int:
    cutoff = _cutoff(now, settings.retention_anon_account_days)
    return await _delete(
        session,
        "identity.account",
        "user_id",
        "kind = 'anonymous' AND status = 'active' AND user_id <> :detached AND created_at < :cutoff "
        "AND NOT EXISTS (SELECT 1 FROM reports.report r WHERE r.user_id = identity.account.user_id) "
        "AND NOT EXISTS (SELECT 1 FROM notify.device d WHERE d.user_id = identity.account.user_id)",
        {"cutoff": cutoff, "detached": DETACHED_ACCOUNT_ID},
    )


async def purge_erasure_requests(session: AsyncSession, settings: Settings, now: datetime) -> int:
    cutoff = _cutoff(now, settings.retention_erasure_days)
    return await _delete(session, "identity.erasure_request", "id", "disabled_at < :cutoff", {"cutoff": cutoff})


JOBS: list[tuple[str, Job]] = [
    ("events", purge_events),
    ("notify_outbox", purge_notify_outbox),
    ("notify_dispatch", purge_notify_dispatch),
    ("device_locations", forget_device_locations),
    ("devices", purge_devices),
    ("reports", anonymise_reports),
    ("consents", purge_consents),
    ("anonymous_accounts", purge_anonymous_accounts),
    ("erasure_requests", purge_erasure_requests),
]


def _lock_key(name: str) -> int:
    return zlib.crc32(f"ehimaya.retention.{name}".encode())


async def run_job(
    sessionmaker: async_sessionmaker[AsyncSession], name: str, job: Job, now: datetime | None = None
) -> int:
    """Run one job to completion (batch after batch). Returns the rows handled (0 if another process runs it)."""
    settings = get_settings()
    total = 0
    while True:
        async with sessionmaker() as session, session.begin():
            locked = await session.scalar(text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": _lock_key(name)})
            if not locked:
                return total
            count = await job(session, settings, now or datetime.now(UTC))
        total += count
        if count == 0:
            return total


async def run_all(sessionmaker: async_sessionmaker[AsyncSession], now: datetime | None = None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name, job in JOBS:
        try:
            counts[name] = await run_job(sessionmaker, name, job, now)
        except Exception:
            log.exception("retention.job_failed", job=name)
            counts[name] = -1
    log.info("retention.done", **counts)
    return counts


async def retention_forever(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    while True:
        settings = get_settings()
        if settings.retention_enabled:
            try:
                await run_all(sessionmaker)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("retention.failed")
        await asyncio.sleep(settings.retention_interval_s)
