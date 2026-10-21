"""Session revocation (phase 10 §1.2): a per-subject "not before" time checked on every authenticated request.

Keycloak ends its own sessions when an account is disabled or signed out, but access tokens already issued stay
valid until they expire. ``revoke`` records the time from which a subject's tokens are accepted again; a token
issued at or before it is refused with ``401 session_revoked``.

The time is kept in Valkey (``auth:nbf:<sub>``, expiring after a day, longer than any access token) so every API
instance sees it, or in process memory when no Valkey is configured (development, tests). When Valkey cannot be
reached the check is skipped rather than refusing every staff request during an outage; the skip is counted in
``ehimaya_session_check_degraded_total`` and logged. Access tokens live five minutes, which bounds the exposure.
"""

import time
from typing import Protocol

import structlog
from redis.asyncio import Redis, from_url

from app.core import metrics
from app.core.config import get_settings

log = structlog.get_logger()

# Longer than any access token (staff 5 min, public 15 min): past it the record has no effect.
TTL_S = 86_400


def _key(subject: str) -> str:
    return f"auth:nbf:{subject}"


class RevocationStore(Protocol):
    async def set(self, subject: str, not_before: int) -> None: ...

    async def get(self, subject: str) -> int | None: ...


class MemoryRevocations:
    def __init__(self) -> None:
        self._times: dict[str, tuple[int, float]] = {}

    async def set(self, subject: str, not_before: int) -> None:
        now = time.time()
        for stale in [s for s, (_, until) in self._times.items() if until <= now]:
            del self._times[stale]
        self._times[subject] = (not_before, now + TTL_S)

    async def get(self, subject: str) -> int | None:
        entry = self._times.get(subject)
        return entry[0] if entry and entry[1] > time.time() else None


class ValkeyRevocations:
    def __init__(self, client: Redis) -> None:
        self._client = client

    async def set(self, subject: str, not_before: int) -> None:
        await self._client.set(_key(subject), str(not_before), ex=TTL_S)

    async def get(self, subject: str) -> int | None:
        raw = await self._client.get(_key(subject))
        return int(raw) if raw is not None else None


_store: RevocationStore | None = None


def get_store() -> RevocationStore:
    global _store
    if _store is None:
        url = get_settings().valkey_url
        _store = (
            ValkeyRevocations(from_url(url, socket_timeout=1, socket_connect_timeout=1)) if url else MemoryRevocations()
        )
    return _store


def set_store(store: RevocationStore | None) -> None:
    """Replace the shared store (tests)."""
    global _store
    _store = store


async def revoke(subject: str, at: float | None = None) -> None:
    """Refuse every token of ``subject`` issued at or before ``at`` (default: now)."""
    await get_store().set(subject, int(at if at is not None else time.time()))
    log.info("session.revoked", subject=subject)


async def is_revoked(subject: str, issued_at: int) -> bool:
    """True when the token was issued at or before the subject's revocation time. Never raises."""
    try:
        not_before = await get_store().get(subject)
    except Exception as exc:  # Valkey down or slow: skip the check, never stop the emergency room
        metrics.SESSION_CHECK_DEGRADED.inc()
        log.warning("session.check_degraded", error=type(exc).__name__)
        return False
    return not_before is not None and issued_at <= not_before
