"""Fixed-window rate limiting shared by all API instances through Valkey.

Without Valkey (local development, tests) an in-process limiter is used. Keys never contain raw
personal data or IP addresses: callers pass an opaque identifier (account id or a keyed hash).
"""

import hashlib
import math
import time
from typing import Protocol

from fastapi import HTTPException, status
from redis.asyncio import Redis, from_url

from app.core.config import get_settings


class Limiter(Protocol):
    async def hit(self, key: str, limit: int, window_s: int) -> int | None:
        """Count one hit; return seconds to wait when the limit is exceeded, else None."""
        ...


class MemoryLimiter:
    def __init__(self) -> None:
        self._windows: dict[str, tuple[int, int]] = {}

    async def hit(self, key: str, limit: int, window_s: int) -> int | None:
        now = time.time()
        window = int(now // window_s)
        current_window, count = self._windows.get(key, (window, 0))
        if current_window != window:
            count = 0
        count += 1
        self._windows[key] = (window, count)
        if len(self._windows) > 100_000:  # bound memory in long-running dev servers
            self._windows.clear()
        return None if count <= limit else max(1, math.ceil((window + 1) * window_s - now))


class ValkeyLimiter:
    def __init__(self, client: Redis) -> None:
        self._client = client

    async def hit(self, key: str, limit: int, window_s: int) -> int | None:
        now = time.time()
        window = int(now // window_s)
        full_key = f"rl:{key}:{window}"
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.incr(full_key)
            pipe.expire(full_key, window_s + 1)
            count, _ = await pipe.execute()
        return None if int(count) <= limit else max(1, math.ceil((window + 1) * window_s - now))


_limiter: Limiter | None = None


def get_limiter() -> Limiter:
    global _limiter
    if _limiter is None:
        url = get_settings().valkey_url
        _limiter = ValkeyLimiter(from_url(url, socket_timeout=2)) if url else MemoryLimiter()
    return _limiter


def set_limiter(limiter: Limiter | None) -> None:
    global _limiter
    _limiter = limiter


def opaque(value: str) -> str:
    """Short keyed digest so limiter keys do not store identifiers such as IP addresses."""
    secret = get_settings().anon_pseudonym_secret.get_secret_value()
    return hashlib.blake2b(value.encode(), key=secret.encode()[:64], digest_size=12).hexdigest()


async def enforce(key: str, limit: int, window_s: int) -> None:
    try:
        retry_after = await get_limiter().hit(key, limit, window_s)
    except Exception:  # a limiter outage must never block an emergency report
        return
    if retry_after is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited", headers={"Retry-After": str(retry_after)}
        )
