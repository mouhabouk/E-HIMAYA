"""Worker loop ``rewards``: reads the domain events of the transactional outbox and books the points they earn.

The consumer keeps its own position (``rewards.consumer_cursor``) in ``events.outbox`` and reads rows by id, so it
does not depend on the bus (NATS) being up. Outbox ids come from a sequence: a transaction can commit a lower id
after a higher one is visible. A hole in the ids is therefore waited for during ``GAP_GRACE`` before the cursor
moves past it (a rolled-back insert leaves a permanent hole). Events only name what changed; the award is decided
from the current rows (report, incident, assignment), and every award is idempotent (``dedup_key``), so reading an
event twice is harmless.

| event                    | award                                                              |
|--------------------------|--------------------------------------------------------------------|
| ``report.status_changed`` | status ``closed``: report_verified (+ accurate_category)          |
| ``assignment.updated``    | volunteer assignment ``released`` after being on scene: mission   |
| ``oplevel.changed``       | (any level) awards queued at level disaster are re-examined        |

Relayed outbox rows are deleted after ``RETENTION_EVENTS_DAYS`` (7 days): a consumer stopped longer than that misses
the events in between (points can then be booked by hand, reason ``manual``).
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.events import open_payload
from app.modules.rewards import service
from app.modules.rewards.models import ConsumerCursor

log = structlog.get_logger()

CURSOR = "outbox"
BATCH = 500
GAP_GRACE = timedelta(seconds=60)
SUBJECTS = frozenset({"report.status_changed", "assignment.updated", "oplevel.changed"})

# First time this process saw each hole in the outbox ids (outbox id → when).
_gaps: dict[int, datetime] = {}


def _id_of(payload: dict[str, Any], key: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(payload[key]["id"]))
    except (KeyError, TypeError, ValueError):
        return None


async def handle(session: AsyncSession, subject: str, payload: dict[str, Any], now: datetime) -> None:
    if subject == "report.status_changed":
        if payload.get("report", {}).get("status") == "closed" and (report_id := _id_of(payload, "report")):
            await service.award_report(session, report_id, now)
    elif subject == "assignment.updated":
        assignment = payload.get("assignment", {})
        if assignment.get("kind") == "volunteer" and assignment.get("status") == "released":
            if assignment_id := _id_of(payload, "assignment"):
                await service.award_mission(session, assignment_id, now)
    # oplevel.changed: release_pending runs after every batch.


async def consume_once(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    gap_grace: timedelta = GAP_GRACE,
    now: datetime | None = None,
    batch: int = BATCH,
) -> int:
    """Handle one batch of outbox rows after the cursor. Returns how many rows the cursor moved past."""
    now = now or service.now_utc()
    async with sessionmaker() as session, session.begin():
        cursor = await session.scalar(
            select(ConsumerCursor).where(ConsumerCursor.name == CURSOR).with_for_update(skip_locked=True)
        )
        if cursor is None:  # another process holds it
            return 0
        rows = (
            await session.execute(
                text("SELECT id, subject, payload FROM events.outbox WHERE id > :last ORDER BY id LIMIT :batch"),
                {"last": cursor.last_id, "batch": batch},
            )
        ).all()
        last = cursor.last_id
        for row in rows:
            if row.id != last + 1:
                first_seen = _gaps.setdefault(last + 1, now)
                if now - first_seen < gap_grace:
                    break
                _gaps.pop(last + 1, None)
            last = row.id
            if row.subject not in SUBJECTS:
                continue
            try:
                async with session.begin_nested():
                    await handle(session, row.subject, open_payload(row.payload), now)
            except Exception:
                # A malformed or unreadable event must not stop the consumer; the next events still count.
                log.exception("rewards.event_failed", outbox_id=row.id, subject=row.subject)
        moved = last - cursor.last_id
        if moved:
            cursor.last_id, cursor.updated_at = last, now
        return moved


async def release_once(sessionmaker: async_sessionmaker[AsyncSession], now: datetime | None = None) -> int:
    async with sessionmaker() as session, session.begin():
        return await service.release_pending(session, now)


async def run_until_idle(
    sessionmaker: async_sessionmaker[AsyncSession], *, gap_grace: timedelta = GAP_GRACE, now: datetime | None = None
) -> None:
    """Drain the outbox and the queue (used by the loop and by tests)."""
    while await consume_once(sessionmaker, gap_grace=gap_grace, now=now):
        pass
    while await release_once(sessionmaker, now):
        pass


async def rewards_forever(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    while True:
        try:
            await run_until_idle(sessionmaker)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("rewards.loop_failed")
        await asyncio.sleep(get_settings().rewards_interval_s)
