"""Worker loop "analytics" (``WORKER_LOOPS`` in app/main.py): scheduled reports and the document queue.

Every ANALYTICS_INTERVAL_S: due schedules queue their document (next run computed in Africa/Tunis), then queued
documents are generated one by one (PDF or XLSX), stored in S3 as ``reports.media`` kind ``analytics_report`` with
their SHA-256, and the creator and recipients get an in-app notification (``analytics.notification`` and the live
event ``analytics.report_ready``). Safe in several processes at once: rows are claimed with SKIP LOCKED and a lease.
"""

import asyncio
import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from anyio import to_thread
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.events import emit
from app.core.security import Realm
from app.core.storage import get_store
from app.modules.analytics import documents, domain
from app.modules.analytics.models import Notification, Report, Schedule
from app.modules.audit import service as audit
from app.modules.reports.models import Media

log = structlog.get_logger()

LEASE = timedelta(minutes=10)
MAX_ATTEMPTS = 3
OBJECT_PREFIX = "analytics/reports/"
SCHEDULES_PER_CYCLE = 50
STAFF_ACTOR = f"{Realm.STAFF.value}:"


def subject_of(actor: str) -> str | None:
    """Staff subject of an audit actor string ("ehimaya-staff:<sub>")."""
    return actor[len(STAFF_ACTOR) :] if actor.startswith(STAFF_ACTOR) else None


def audience_of(report: Report) -> list[str]:
    creator = subject_of(report.created_by)
    return sorted({*report.recipients, *([creator] if creator else [])})


# ---------------------------------------------------------------- schedules


async def run_due_schedules(session: AsyncSession, now: datetime | None = None) -> list[uuid.UUID]:
    """Queue the document of every due schedule and move it to its next run; returns the queued report ids."""
    now = now or datetime.now(UTC)
    due = list(
        await session.scalars(
            select(Schedule)
            .where(Schedule.enabled, Schedule.next_run_at <= now)
            .order_by(Schedule.next_run_at)
            .limit(SCHEDULES_PER_CYCLE)
            .with_for_update(skip_locked=True)
        )
    )
    queued: list[uuid.UUID] = []
    for schedule in due:
        # The period is that of the run that was due (a worker down for a while catches up once, not per missed run).
        run_day = schedule.next_run_at.astimezone(domain.TUNIS_TZ).date()
        start, end = domain.scheduled_period(schedule.frequency, run_day)
        report = Report(
            kind=schedule.kind,
            title=f"{schedule.title} · {start.isoformat()}" + (f" → {end.isoformat()}" if end != start else ""),
            lang=schedule.lang,
            period_from=start,
            period_to=end,
            gouvernorats=list(schedule.gouvernorats),
            filters=dict(schedule.filters),
            format=schedule.format,
            creator_scope=schedule.creator_scope,
            created_by=schedule.created_by,
            schedule_id=schedule.id,
            recipients=list(schedule.recipients),
        )
        session.add(report)
        await session.flush()
        schedule.last_run_at, schedule.last_report_id = now, report.id
        schedule.next_run_at = domain.next_run(
            schedule.frequency, schedule.at_time, schedule.weekday, schedule.day, now
        )
        await audit.record(
            session,
            actor=audit.SYSTEM_ACTOR,
            action="analytics.schedule.run",
            target=f"analytics_schedule:{schedule.id}",
            details={"report_id": str(report.id), "period_from": str(start), "period_to": str(end)},
        )
        queued.append(report.id)
    return queued


# ---------------------------------------------------------------- generation


async def _claim(session: AsyncSession) -> Report | None:
    now = datetime.now(UTC)
    report = await session.scalar(
        select(Report)
        .where(
            (Report.status == "queued") | ((Report.status == "running") & (Report.lease_until < now)),
        )
        .order_by(Report.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if report is None:
        return None
    report.status, report.lease_until = "running", now + LEASE
    report.attempts += 1
    report.updated_at = now
    return report


async def _notify(session: AsyncSession, report: Report, kind: str) -> None:
    audience = audience_of(report)
    if audience:
        await session.execute(
            insert(Notification)
            .values(
                [
                    {
                        "recipient": who,
                        "kind": kind,
                        "report_id": report.id,
                        "schedule_id": report.schedule_id,
                        "title": report.title,
                    }
                    for who in audience
                ]
            )
            .on_conflict_do_nothing(constraint="uq_notification_report")
        )
    subject = "analytics.report_ready" if kind == "report_ready" else "analytics.report_failed"
    await emit(
        session,
        subject,
        {
            "report_id": str(report.id),
            "title": report.title,
            "kind": report.kind,
            "format": report.format,
            "gouvernorats": list(report.gouvernorats),
            "schedule_id": str(report.schedule_id) if report.schedule_id else None,
            "recipients": audience,
        },
    )


async def generate_next(sessionmaker: async_sessionmaker[AsyncSession]) -> bool:
    """Generate one queued document; False when the queue is empty."""
    async with sessionmaker() as session:
        report = await _claim(session)
        if report is None:
            return False
        report_id = report.id
        await session.commit()
    try:
        async with sessionmaker() as session:
            report = await session.get(Report, report_id)
            assert report is not None
            content = await documents.build(session, report)
            fmt = report.format
        data = await to_thread.run_sync(documents.render, content, fmt)
        key = f"{OBJECT_PREFIX}{report_id}.{fmt}"
        content_type = domain.CONTENT_TYPES[fmt]
        await get_store().put(key, data, content_type)
    except Exception as exc:
        code = str(exc) if isinstance(exc, documents.ContentError) else type(exc).__name__
        log.exception("analytics.report_failed", report_id=str(report_id), error=code)
        async with sessionmaker() as session:
            report = await session.get(Report, report_id, with_for_update=True)
            if report is not None and report.status == "running":
                final = isinstance(exc, documents.ContentError) or report.attempts >= MAX_ATTEMPTS
                report.status = "failed" if final else "queued"
                report.error, report.lease_until, report.updated_at = code, None, datetime.now(UTC)
                if final:
                    await _notify(session, report, "report_failed")
            await session.commit()
        return True
    digest = hashlib.sha256(data).hexdigest()
    now = datetime.now(UTC)
    async with sessionmaker() as session:
        report = await session.get(Report, report_id, with_for_update=True)
        if report is None or report.status != "running":
            return True
        media = await session.scalar(select(Media).where(Media.object_key == key))
        if media is None:
            media = Media(
                kind="analytics_report",
                object_key=key,
                sha256=digest,
                bytes=len(data),
                content_type=content_type,
                verified_type=content_type,
                status="stored",
                stored_at=now,
            )
            session.add(media)
        else:
            media.sha256, media.bytes, media.stored_at = digest, len(data), now
        await session.flush()
        report.status, report.media_id, report.sha256, report.bytes = "ready", media.id, digest, len(data)
        report.error, report.lease_until, report.ready_at, report.updated_at = None, None, now, now
        await _notify(session, report, "report_ready")
        await session.commit()
    log.info("analytics.report_ready", report_id=str(report_id), format=fmt, bytes=len(data))
    return True


async def cycle(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    async with sessionmaker() as session:
        await run_due_schedules(session)
        await session.commit()
    while await generate_next(sessionmaker):
        pass


async def analytics_forever(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    interval = get_settings().analytics_interval_s
    while True:
        try:
            await cycle(sessionmaker)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("analytics.cycle_failed")
        await asyncio.sleep(interval)


async def pending_count(session: AsyncSession) -> int:
    return int(await session.scalar(text("SELECT count(*) FROM analytics.report WHERE status = 'queued'")) or 0)
