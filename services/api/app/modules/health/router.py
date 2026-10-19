"""Liveness and readiness probes, and the Prometheus scrape endpoint."""

import asyncio
import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import metrics, ratelimit
from app.core.config import get_settings
from app.core.db import get_session

router = APIRouter(prefix="/health", tags=["health"])
metrics_router = APIRouter(include_in_schema=False)


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

    # Without Valkey the limiter runs on its in-process fallback; without NATS events wait in the outbox.
    # Both keep SOS reports flowing, so only the database takes an instance out of rotation.
    checks["rate_limiter"] = "degraded: in-process fallback" if ratelimit.is_degraded() else "ok"
    healthy = all(v in ("ok", "not configured") for v in checks.values())
    if checks["database"] != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if healthy else "degraded",
        "process_role": settings.process_role,
        "checks": checks,
    }


@metrics_router.get("/metrics")
async def prometheus_metrics(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    """Prometheus exposition, for a scraper sending ``Authorization: Bearer <METRICS_TOKEN>``.

    Answers 404 while METRICS_TOKEN is unset or the token is wrong, so the endpoint is not advertised."""
    token = get_settings().metrics_token
    presented = authorization[7:].strip() if authorization and authorization.lower().startswith("bearer ") else ""
    if token is None or not hmac.compare_digest(presented.encode(), token.get_secret_value().encode()):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    try:
        await metrics.refresh_queues(session)
    except Exception:  # the process metrics stay useful while the database is down
        await session.rollback()
    return Response(generate_latest(metrics.REGISTRY), media_type=CONTENT_TYPE_LATEST)
