"""Situation reports and decision deadlines of the open axes (``WORKER_LOOPS`` in app/main.py, worker role).

Every minute: a situation report draft when one is due, a reminder an hour before a decision's deadline and an alert
to its issuer when the deadline passes (app/modules/crisis/service.py, design §5).
"""

import asyncio

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.crisis import service

log = structlog.get_logger()
INTERVAL_S = 60


async def crisis_forever(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    while True:
        try:
            async with sessionmaker() as session:
                result = await service.tick(session)
                await session.commit()
            if any(result.values()):
                log.info("crisis.tick", **result)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("crisis.tick_failed")
        await asyncio.sleep(INTERVAL_S)
