"""Audit trail writer. Every access to personal data and every decision goes through ``record``."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, current_principal
from app.modules.audit.models import AuditLog

SYSTEM_ACTOR = "system"


def actor_of(principal: Principal | None) -> str:
    return f"{principal.realm.value}:{principal.subject}" if principal else SYSTEM_ACTOR


def name_of(principal: Principal | None) -> str | None:
    """Display name of a signed-in user (shown next to decisions, e.g. who raised a level)."""
    if principal is None:
        return None
    claims = principal.claims
    name = claims.get("name") or " ".join(p for p in (claims.get("given_name"), claims.get("family_name")) if p)
    return str(name or claims.get("preferred_username") or "")[:200] or None


async def record(
    session: AsyncSession,
    *,
    actor: str,
    action: str,
    target: str | None = None,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
    gouvernorats: list[int] | None = None,
) -> AuditLog:
    """Append an entry inside the caller's transaction (the caller commits).

    ``gouvernorats`` are the gouvernorats the action concerns (phase 9 §7.1): stored as ``details["gouvernorats"]``,
    inside the hash chain, and exposed by the generated column ``audit.log.gouvernorats`` to the regional audit view.
    Omitted: a national-only entry."""
    payload = dict(details or {})
    principal = current_principal.get()
    if "actor_name" not in payload and principal is not None and actor == actor_of(principal):
        name = name_of(principal)
        if name:
            payload["actor_name"] = name
    if gouvernorats:
        payload["gouvernorats"] = sorted({int(code) for code in gouvernorats})
    entry = AuditLog(actor=actor, action=action, target=target, reason=reason, details=payload)
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return entry


async def verify_chain(session: AsyncSession) -> int | None:
    """Return the seq of the first tampered entry, or None if the whole chain is intact."""
    result: int | None = await session.scalar(select(func.audit.verify_chain()))
    return result
