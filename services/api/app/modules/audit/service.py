"""Audit trail writer. Every access to personal data and every decision goes through ``record``."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.modules.audit.models import AuditLog

SYSTEM_ACTOR = "system"


def actor_of(principal: Principal | None) -> str:
    return f"{principal.realm.value}:{principal.subject}" if principal else SYSTEM_ACTOR


async def record(
    session: AsyncSession,
    *,
    actor: str,
    action: str,
    target: str | None = None,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Append an entry inside the caller's transaction (the caller commits)."""
    entry = AuditLog(actor=actor, action=action, target=target, reason=reason, details=details or {})
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return entry


async def verify_chain(session: AsyncSession) -> int | None:
    """Return the seq of the first tampered entry, or None if the whole chain is intact."""
    result: int | None = await session.scalar(select(func.audit.verify_chain()))
    return result
