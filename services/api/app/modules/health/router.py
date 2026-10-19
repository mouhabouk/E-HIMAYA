"""Liveness and readiness probes."""

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


async def _check_valkey(url: str) -> None:
    from redis.asyncio import from_url

    client = from_url(url, socket_timeout=2)
    try:
        await client.ping()
    finally:
        await client.aclose()


async def _check_nats(url: str) -> None:
    import nats

    nc = await nats.connect(url, connect_timeout=2, max_reconnect_attempts=0, allow_reconnect=False)
    await nc.close()


@router.get("/ready")
async def ready(response: Response, session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, Any]:
    settings = get_settings()
    checks: dict[str, str] = {}

    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"

    optional = {"valkey": (settings.valkey_url, _check_valkey), "nats": (settings.nats_url, _check_nats)}
    for name, (url, check) in optional.items():
        if not url:
            checks[name] = "not configured"
            continue
        try:
            await asyncio.wait_for(check(url), timeout=3)
            checks[name] = "ok"
        except Exception as exc:
            checks[name] = f"error: {type(exc).__name__}"

    healthy = all(v in ("ok", "not configured") for v in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if healthy else "degraded", "checks": checks}
