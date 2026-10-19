"""Fixed-window rate limiting shared by all API instances through Valkey.

Without Valkey (local development, tests) an in-process limiter is used. Keys never contain raw
personal data or IP addresses: callers pass an opaque identifier (account id or a keyed hash).

When Valkey fails, the limiter degrades to a bounded in-process fallback instead of failing open: the
limits still hold per instance, the degraded state is logged, exposed in ``/health/ready`` and as the
``ehimaya_ratelimit_degraded`` metric, and Valkey is retried after a short pause. Report creation never
rejects on the fallback's verdict (``check`` lets the caller flag the report instead).
"""

import hashlib
import math
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Protocol

import structlog
from fastapi import HTTPException, Request, status
from redis.asyncio import Redis, from_url

from app.core import metrics
from app.core.config import get_settings

log = structlog.get_logger()

# Keys kept by an in-process limiter; the least recently used window is dropped beyond that.
MEMORY_MAX_KEYS = 50_000
# After a Valkey error, requests use the fallback for this long before Valkey is tried again, so an
# outage does not add a connection timeout to every request.
VALKEY_RETRY_S = 5.0


class Limiter(Protocol):
    async def hit(self, key: str, limit: int, window_s: int) -> int | None:
        """Count one hit; return seconds to wait when the limit is exceeded, else None."""
        ...


class MemoryLimiter:
    """Per-process fixed windows with bounded memory (least recently used keys are evicted)."""

    def __init__(self, max_keys: int = MEMORY_MAX_KEYS) -> None:
        self._windows: OrderedDict[str, tuple[int, int]] = OrderedDict()
        self._max_keys = max_keys

    def __len__(self) -> int:
        return len(self._windows)

    async def hit(self, key: str, limit: int, window_s: int) -> int | None:
        now = time.time()
        window = int(now // window_s)
        current_window, count = self._windows.pop(key, (window, 0))
        if current_window != window:
            count = 0
        count += 1
        self._windows[key] = (window, count)
        while len(self._windows) > self._max_keys:
            self._windows.popitem(last=False)
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
_fallback = MemoryLimiter()
_degraded_since: float | None = None
_retry_at = 0.0


def get_limiter() -> Limiter:
    global _limiter
    if _limiter is None:
        url = get_settings().valkey_url
        _limiter = ValkeyLimiter(from_url(url, socket_timeout=1, socket_connect_timeout=1)) if url else MemoryLimiter()
    return _limiter


def set_limiter(limiter: Limiter | None) -> None:
    """Replace the shared limiter (tests); also resets the fallback and the degraded state."""
    global _limiter, _fallback
    _limiter = limiter
    _fallback = MemoryLimiter()
    _set_healthy()


def is_degraded() -> bool:
    return _degraded_since is not None


def _set_degraded(exc: Exception) -> None:
    global _degraded_since, _retry_at
    _retry_at = time.monotonic() + VALKEY_RETRY_S
    metrics.RATELIMIT_BACKEND_ERRORS.inc()
    if _degraded_since is None:
        _degraded_since = time.time()
        metrics.RATELIMIT_DEGRADED.set(1)
        log.warning("ratelimit.degraded", error=type(exc).__name__)


def _set_healthy() -> None:
    global _degraded_since, _retry_at
    _retry_at = 0.0
    if _degraded_since is not None:
        log.info("ratelimit.recovered", degraded_s=round(time.time() - _degraded_since, 1))
    _degraded_since = None
    metrics.RATELIMIT_DEGRADED.set(0)


def opaque(value: str) -> str:
    """Short keyed digest so limiter keys do not store identifiers such as IP addresses."""
    secret = get_settings().anon_pseudonym_secret.get_secret_value()
    return hashlib.blake2b(value.encode(), key=secret.encode()[:64], digest_size=12).hexdigest()


def client_key(request: Request) -> str:
    """Opaque key of the client address. Behind a reverse proxy the address is the forwarded one only when
    uvicorn trusts that proxy (``FORWARDED_ALLOW_IPS``); otherwise every client shares the proxy's address."""
    return opaque(request.client.host if request.client else "unknown")


@dataclass(frozen=True, slots=True)
class Verdict:
    exceeded: bool
    retry_after: int | None
    # The verdict came from the in-process fallback because Valkey failed.
    degraded: bool


async def check(key: str, limit: int, window_s: int) -> Verdict:
    """Count one hit and return the verdict without raising (callers that must never reject use this)."""
    if time.monotonic() >= _retry_at:
        try:
            retry_after = await get_limiter().hit(key, limit, window_s)
        except Exception as exc:  # Valkey down or slow: degrade, never fail open
            _set_degraded(exc)
        else:
            if _degraded_since is not None:
                _set_healthy()
            return Verdict(retry_after is not None, retry_after, False)
    retry_after = await _fallback.hit(key, limit, window_s)
    return Verdict(retry_after is not None, retry_after, True)


def too_many(retry_after: int | None) -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited", headers={"Retry-After": str(retry_after or 1)}
    )


async def enforce(key: str, limit: int, window_s: int) -> None:
    verdict = await check(key, limit, window_s)
    if verdict.exceeded:
        raise too_many(verdict.retry_after)
