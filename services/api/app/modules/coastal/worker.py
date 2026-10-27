"""Background refresh of the coastal safety picture (``WORKER_LOOPS`` in app/main.py, worker role).

Every COASTAL_REFRESH_INTERVAL_S: new beaches, their marine weather, the risk of the next four days and today's alerts
(app/modules/coastal/service.py). A provider outage only keeps the last values; it never blocks anything else.
"""

import asyncio

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.modules.coastal import service

log = structlog.get_logger()


async def coastal_forever(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    interval = get_settings().coastal_refresh_interval_s
    while True:
        try:
            result = await service.refresh(sessionmaker)
            log.info("coastal.refreshed", **result)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("coastal.refresh_failed")
        await asyncio.sleep(interval)
