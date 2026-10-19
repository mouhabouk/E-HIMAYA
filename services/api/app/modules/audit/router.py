from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service
from app.modules.audit.models import AuditLog

router = APIRouter(prefix="/api/v1/admin/audit", tags=["audit"])

SysAdmin = Annotated[Principal, Depends(require_roles(Role.SYSADMIN))]


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


@router.get("", response_model=list[AuditEntryOut])
async def list_entries(
    principal: SysAdmin,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: str | None = None,
    target: str | None = None,
    before_seq: int | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AuditLog]:
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


@router.get("/verify", response_model=ChainStatus)
async def verify(principal: SysAdmin, session: Annotated[AsyncSession, Depends(get_session)]) -> ChainStatus:
    broken = await service.verify_chain(session)
    return ChainStatus(intact=broken is None, first_broken_seq=broken)
