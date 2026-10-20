from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Ctx, authorize, require
from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service
from app.modules.audit.models import AuditLog

# Full paths: the scoped staff view (phase 9) shares this router, which main.py already registers.
router = APIRouter(tags=["audit"])

# Phase 9 §7.3: the raw log is read by the national security admins only; the chain check stays open to sysadmin.
SecurityAdmin = Annotated[Principal, Depends(require_roles(Role.SECURITY_ADMIN))]
ChainChecker = Annotated[Principal, Depends(require_roles(Role.SECURITY_ADMIN, Role.SYSADMIN))]
ScopedReader = Annotated[Principal, Depends(require_roles(Role.OPS_MANAGER, Role.LOCAL_COMMITTEE, Role.SECURITY_ADMIN))]


class AuditEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int
    at: datetime
    actor: str
    action: str
    target: str | None
    reason: str | None
    details: dict[str, Any]
    hash: str


class ChainStatus(BaseModel):
    intact: bool
    first_broken_seq: int | None


@router.get("/api/v1/admin/audit", response_model=list[AuditEntryOut])
async def list_entries(
    principal: SecurityAdmin,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: str | None = None,
    target: str | None = None,
    before_seq: int | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AuditLog]:
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "national_scope_required")
    query = select(AuditLog).order_by(AuditLog.seq.desc()).limit(limit)
    if actor:
        query = query.where(AuditLog.actor == actor)
    if target:
        query = query.where(AuditLog.target == target)
    if before_seq:
        query = query.where(AuditLog.seq < before_seq)
    rows = list(await session.scalars(query))
    await service.record(
        session,
        actor=service.actor_of(principal),
        action="audit.read",
        details={"actor": actor, "target": target, "count": len(rows)},
    )
    await session.commit()
    return rows


@router.get("/api/v1/admin/audit/verify", response_model=ChainStatus)
async def verify(principal: ChainChecker, session: Annotated[AsyncSession, Depends(get_session)]) -> ChainStatus:
    broken = await service.verify_chain(session)
    return ChainStatus(intact=broken is None, first_broken_seq=broken)


# ---------------------------------------------------------------- scoped, redacted view (phase 9 §7.3)

# Details kept in the scoped view: the ids of the objects acted upon and the few fields that say what happened.
_KEPT_DETAILS = frozenset({"from", "to", "status", "outcome", "kind"})
# Ids that name a person rather than an object of the operation stay out of the regional view.
_PERSONAL_IDS = frozenset({"user_id", "volunteer_id", "account_id", "actor_id", "subject_id", "citizen_id"})
# Actions whose reason is part of the regional record (who escalated or referred, and why; grants; settings).
_REASONED = ("report.escalation", "report.refer", "report.referral", "breakglass.", "settings.")


class ScopedEntryOut(BaseModel):
    seq: int
    at: datetime
    actor: str
    action: str
    target: str | None
    reason: str | None
    details: dict[str, Any]
    gouvernorats: list[int]


class ScopedPage(BaseModel):
    items: list[ScopedEntryOut]
    next_cursor: str | None


def _kept(key: str) -> bool:
    return key in _KEPT_DETAILS or (key.endswith(("_id", "_ids")) and key not in _PERSONAL_IDS)


def redact(entry: AuditLog) -> ScopedEntryOut:
    """The regional view of an entry: no actor identifier, a whitelist of details, no hash."""
    details = entry.details or {}
    actor_name = details.get("actor_name")
    return ScopedEntryOut(
        seq=entry.seq,
        at=entry.at,
        actor=str(actor_name) if actor_name else "system" if entry.actor == service.SYSTEM_ACTOR else "staff",
        action=entry.action,
        target=entry.target if entry.target and not entry.target.startswith(("user:", "account:")) else None,
        reason=entry.reason if entry.action.startswith(_REASONED) else None,
        details={k: v for k, v in details.items() if _kept(k)},
        gouvernorats=list(entry.gouvernorats or []),
    )


@router.get("/api/v1/staff/audit", response_model=ScopedPage)
async def list_scoped(
    principal: ScopedReader,
    session: Annotated[AsyncSession, Depends(get_session)],
    action: Annotated[str | None, Query(max_length=100)] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ScopedPage:
    require(await authorize(session, principal, Action.AUDIT_READ_SCOPED, Ctx(lead=principal.gouvernorat_code)))
    query = select(AuditLog).order_by(AuditLog.seq.desc()).limit(limit)
    code = principal.gouvernorat_code
    if code is not None:
        query = query.where(AuditLog.gouvernorats.any_() == code)
    if action:
        query = query.where(AuditLog.action == action)
    if from_:
        query = query.where(AuditLog.at >= from_)
    if to:
        query = query.where(AuditLog.at < to)
    if cursor:
        if not cursor.isdigit():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor")
        query = query.where(AuditLog.seq < int(cursor))
    rows = list(await session.scalars(query))
    items = [redact(r) for r in rows]
    await service.record(
        session,
        actor=service.actor_of(principal),
        action="audit.read_scoped",
        details={"action": action, "count": len(rows)},
        gouvernorats=[code] if code is not None else None,
    )
    await session.commit()
    return ScopedPage(items=items, next_cursor=str(rows[-1].seq) if len(rows) == limit else None)
