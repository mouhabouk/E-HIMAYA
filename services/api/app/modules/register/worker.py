"""Expiry of temporary instructions in the register (``WORKER_LOOPS`` in app/main.py, worker role).

Every hour: a document whose end date has passed goes from "in force" to "expired" (design-l3b §2).
"""

import asyncio

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.register import service

log = structlog.get_logger()
INTERVAL_S = 3600


async def register_forever(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    while True:
        try:
            async with sessionmaker() as session:
                expired = await service.tick(session)
                await session.commit()
            if expired:
                log.info("register.tick", expired=expired)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("register.tick_failed")
        await asyncio.sleep(INTERVAL_S)
