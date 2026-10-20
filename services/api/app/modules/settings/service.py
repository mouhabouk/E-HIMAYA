"""National settings store (``platform.setting``) with a short in-process cache.

``get`` is read on hot paths (report creation, the SLA worker): values are cached ``CACHE_TTL_S`` seconds and the cache
is dropped on the ``settings.changed`` event (every instance listens on the bus) and right after a local change.
"""

import time
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import ACTION_NOT_ALLOWED, NATIONAL_SCOPE_REQUIRED
from app.core.events import emit
from app.core.security import Principal
from app.modules.audit import service as audit
from app.modules.settings import domain
from app.modules.settings.models import PlatformSetting

CACHE_TTL_S = 10.0
_cache: dict[str, tuple[float, Any]] = {}


def invalidate(key: str | None = None) -> None:
    if key is None:
        _cache.clear()
    else:
        _cache.pop(key, None)


async def on_event(subject: str, payload: dict[str, Any]) -> None:
    """Bus listener: another instance changed a setting."""
    if subject == "settings.changed":
        invalidate(payload.get("key"))


async def get(session: AsyncSession, key: str) -> Any:
    """Current value of ``key`` (its default when the row is missing)."""
    cached = _cache.get(key)
    now = time.monotonic()
    if cached is not None and cached[0] > now:
        return cached[1]
    value = await session.scalar(select(PlatformSetting.value).where(PlatformSetting.key == key))
    if value is None:
        value = domain.DEFAULTS[key]
    _cache[key] = (now + CACHE_TTL_S, value)
    return value


async def enforced_since(session: AsyncSession) -> datetime | None:
    raw = await get(session, domain.SLA_ENFORCED_SINCE)
    return datetime.fromisoformat(raw) if isinstance(raw, str) else None


def editable(principal: Principal, key: str) -> bool:
    return principal.is_national and bool(principal.roles & domain.EDITORS.get(key, frozenset()))


async def rows(session: AsyncSession) -> list[PlatformSetting]:
    stored = {row.key: row for row in await session.scalars(select(PlatformSetting))}
    return [
        stored.get(key) or PlatformSetting(key=key, value=value, version=0) for key, value in domain.DEFAULTS.items()
    ]


async def update(
    session: AsyncSession, principal: Principal, key: str, value: Any, version: int, reason: str
) -> PlatformSetting:
    """Change one setting (§2): checks, optimistic version, audit with before/after, ``settings.changed``."""
    if key not in domain.DEFAULTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if key in domain.FORMAL_APPROVAL:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "requires_formal_approval")
    editors = domain.EDITORS.get(key, frozenset())
    if not principal.roles & editors:
        raise HTTPException(status.HTTP_403_FORBIDDEN, ACTION_NOT_ALLOWED)
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, NATIONAL_SCOPE_REQUIRED)
    row = await session.get(PlatformSetting, key, with_for_update=True)
    current = row.version if row is not None else 0
    if version != current:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
    try:
        normalised = domain.validate(key, value)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_setting") from exc
    before = row.value if row is not None else domain.DEFAULTS[key]
    actor = audit.actor_of(principal)
    now = datetime.now(UTC)
    if row is None:
        row = PlatformSetting(key=key, value=normalised, version=1)
        session.add(row)
    else:
        row.value = normalised
        row.version = current + 1
    row.updated_by, row.updated_by_name, row.updated_at = actor, audit.name_of(principal), now
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action="settings.update",
        target=f"setting:{key}",
        reason=reason,
        details={"key": key, "before": before, "after": normalised, "version": row.version},
    )
    await emit(session, "settings.changed", {"key": key})
    return row
