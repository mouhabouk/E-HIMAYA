"""Worker loop ``evidence`` (phase 10 §4.3): seals an anchor every hour, and once more when the worker stops.

Safe in several processes at once: sealing takes a transaction-level advisory lock, time-stamping skips locked rows.
"""

import asyncio
import contextlib

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.evidence import service

log = structlog.get_logger()

INTERVAL_S = 3600.0


async def run_once(sessionmaker: async_sessionmaker[AsyncSession]) -> int | None:
    """Seal (when something is new), then time-stamp what still needs it. Returns the new anchor's seq."""
    async with sessionmaker() as session, session.begin():
        anchor = await service.seal(session)
        seq = anchor.seq if anchor is not None else None
        if anchor is not None:
            log.info("evidence.sealed", seq=anchor.seq, media=anchor.media_count, audit_seq=anchor.audit_seq)
    async with sessionmaker() as session, session.begin():
        await service.stamp_pending(session)
    return seq


async def evidence_forever(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    try:
        while True:
            try:
                await run_once(sessionmaker)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("evidence.failed")
            await asyncio.sleep(INTERVAL_S)
    except asyncio.CancelledError:
        # The worker stops: seal what came in since the last hour so nothing waits for the next start.
        with contextlib.suppress(Exception):
            async with sessionmaker() as session, session.begin():
                await service.seal(session)
        raise
