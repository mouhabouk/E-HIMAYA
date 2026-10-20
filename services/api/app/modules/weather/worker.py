"""Background refresh of the weather grid (``WORKER_LOOPS`` in app/main.py, worker role).

Every WEATHER_REFRESH_INTERVAL_S the points that are due are fetched, the derived indices stored and the alert
rules evaluated (app/modules/weather/service.py). Safe in several processes at once (SKIP LOCKED claims, advisory
lock around the rules); a provider outage only delays the next values, it never blocks reports.
"""

import asyncio

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.modules.weather import service

log = structlog.get_logger()


async def weather_forever(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    interval = get_settings().weather_refresh_interval_s
    while True:
        try:
            await service.refresh(sessionmaker)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("weather.refresh_failed")
        await asyncio.sleep(interval)
