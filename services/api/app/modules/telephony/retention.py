"""Retention of telephony data (phase 7), run as jobs of ``app.modules.privacy.retention``.

| job          | what                                                                        | default |
|--------------|-----------------------------------------------------------------------------|---------|
| calls        | calls ended (or started, when never ended) past retention, with their       | 2 years |
|              | recordings (reports.media kind=call_recording and the S3 object)            |         |
| sms_inbound  | received emergency SMS (sender number, dedup data); the reports they         | 2 years |
|              | created follow the report retention                                         |         |
| endpoints    | operator endpoints removed from Asterisk (credential history)               | 2 years |
"""

from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.storage import get_store
from app.modules.audit import service as audit

BATCH = 200


async def purge_calls(session: AsyncSession, settings: Settings, now: datetime) -> int:
    cutoff = now - timedelta(days=settings.retention_call_days)
    rows = (
        await session.execute(
            text(
                "SELECT id, recording_media_id FROM telephony.call "
                "WHERE COALESCE(ended_at, started_at) < :cutoff "
                "ORDER BY COALESCE(ended_at, started_at) LIMIT :n FOR UPDATE SKIP LOCKED"
            ),
            {"cutoff": cutoff, "n": BATCH},
        )
    ).all()
    if not rows:
        return 0
    ids = [r[0] for r in rows]
    media_ids = [r[1] for r in rows if r[1] is not None]
    keys: list[str] = []
    await session.execute(text("DELETE FROM telephony.call WHERE id = ANY(:ids)"), {"ids": ids})
    if media_ids:
        keys = list(
            await session.scalars(
                text("DELETE FROM reports.media WHERE id = ANY(:ids) RETURNING object_key"), {"ids": media_ids}
            )
        )
    await audit.record(
        session,
        actor=audit.SYSTEM_ACTOR,
        action="retention.calls",
        details={"calls": len(ids), "recordings": len(keys)},
    )
    # Objects last: if the commit then fails, the batch is redone and deleting a missing object is a no-op.
    if keys:
        await get_store().delete(*keys)
    return len(ids)


async def purge_sms_inbound(session: AsyncSession, settings: Settings, now: datetime) -> int:
    cutoff = now - timedelta(days=settings.retention_call_days)
    result = await session.execute(
        text(
            "DELETE FROM telephony.sms_inbound WHERE id IN (SELECT id FROM telephony.sms_inbound "
            "WHERE received_at < :cutoff LIMIT :n FOR UPDATE SKIP LOCKED)"
        ),
        {"cutoff": cutoff, "n": BATCH * 5},
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


async def purge_endpoints(session: AsyncSession, settings: Settings, now: datetime) -> int:
    cutoff = now - timedelta(days=settings.retention_call_days)
    result = await session.execute(
        text(
            "DELETE FROM telephony.operator_endpoint WHERE endpoint IN (SELECT endpoint FROM "
            "telephony.operator_endpoint WHERE removed_at < :cutoff LIMIT :n FOR UPDATE SKIP LOCKED)"
        ),
        {"cutoff": cutoff, "n": BATCH * 5},
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]
