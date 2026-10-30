"""The availability calendar in the app (the person's own) and for the staff who read volunteers and doctors."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.audit import service as audit
from app.modules.availability import schemas, service
from app.modules.identity.service import CurrentReporter

router = APIRouter(prefix="/api/v1/me", tags=["availability"])
Session = Annotated[AsyncSession, Depends(get_session)]
RoleQuery = Annotated[schemas.Role, Query()]


@router.get("/availability", response_model=schemas.SlotsOut)
async def mine(reporter: CurrentReporter, session: Session, role: RoleQuery) -> schemas.SlotsOut:
    await service.require_role(session, reporter.user_id, role)
    return service.out(role, await service.slots_of(session, reporter.user_id, role))


@router.put("/availability", response_model=schemas.SlotsOut)
async def replace(
    reporter: CurrentReporter, session: Session, role: RoleQuery, body: schemas.SlotsIn
) -> schemas.SlotsOut:
    """The whole calendar at once: the app sends every slot the person keeps."""
    await service.require_role(session, reporter.user_id, role)
    slots = await service.replace(session, reporter.user_id, role, body)
    await audit.record(
        session,
        actor=reporter.actor,
        action="availability.replace",
        target=f"{role}:{reporter.user_id}",
        details={"slots": len(slots)},
    )
    result = service.out(role, slots)
    await session.commit()
    return result
