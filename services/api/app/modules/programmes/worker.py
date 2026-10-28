"""The daily life cycle of the seasonal programmes (``WORKER_LOOPS`` in app/main.py, worker role).

Every hour: a programme past its last day ends, and each programme layer is published between its validity dates
and paused outside them (app/modules/programmes/service.py). Hourly so a new day is picked up soon after midnight.
"""

import asyncio

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.programmes import service

log = structlog.get_logger()
INTERVAL_S = 3600


async def programmes_forever(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    while True:
        try:
            async with sessionmaker() as session:
                result = await service.lifecycle(session)
                await session.commit()
            if any(result.values()):
                log.info("programmes.lifecycle", **result)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("programmes.lifecycle_failed")
        await asyncio.sleep(INTERVAL_S)
