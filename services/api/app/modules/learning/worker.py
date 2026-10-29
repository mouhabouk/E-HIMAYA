"""Background runner of the training centre (``WORKER_LOOPS`` in app/main.py, worker role).

Every LEARNING_INTERVAL_S: queues the scheduled trainings that are due (setting ``learning.schedule``), then runs the
queued ones, one at a time, each in its own transaction. A failed training is recorded and never stops the loop.
"""

import asyncio
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.modules.learning import service

log = structlog.get_logger()


async def learning_once(sessionmaker: async_sessionmaker[AsyncSession]) -> int:
    async with sessionmaker() as session:
        queued = await service.due(session, datetime.now(UTC))
        await session.commit()
    if queued:
        log.info("learning.scheduled", tasks=queued)
    ran = 0
    while True:
        async with sessionmaker() as session:
            job = await service.run_next(session)
            await session.commit()
        if job is None:
            return ran
        ran += 1
        log.info("learning.ran", task=job.task, state=job.state)


async def learning_forever(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    interval = get_settings().learning_interval_s
    while True:
        try:
            await learning_once(sessionmaker)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("learning.loop_failed")
        await asyncio.sleep(interval)
