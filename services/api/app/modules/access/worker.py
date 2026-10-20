"""Worker loop ``breakglass`` (phase 9 §6.1): ends expired grants and flags the reviews still missing 72 h later.

Safe in several processes at once: rows are claimed with ``FOR UPDATE SKIP LOCKED``.
"""

import asyncio

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.access import grants

log = structlog.get_logger()

INTERVAL_S = 30.0


async def run_once(sessionmaker: async_sessionmaker[AsyncSession]) -> tuple[int, int]:
    async with sessionmaker() as session, session.begin():
        ended = await grants.end_expired(session)
        overdue = await grants.flag_overdue_reviews(session)
    return ended, overdue


async def breakglass_forever(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    while True:
        try:
            ended, overdue = await run_once(sessionmaker)
            if ended or overdue:
                log.info("breakglass.swept", ended=ended, overdue=overdue)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("breakglass.failed")
        await asyncio.sleep(INTERVAL_S)
