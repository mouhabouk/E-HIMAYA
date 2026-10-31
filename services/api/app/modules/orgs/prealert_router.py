"""Pre-alerts of an institution's cameras (review point 25, docs/phase-d/design-d.md §2).

``router``: the institution's members read them and its administrators and editors answer («false alarm» or
«confirm»). ``staff_router``: the room reads the pre-alerts of its gouvernorat, the cancelled ones included, so a
false alarm called too often is seen.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import as_system, get_session
from app.core.security import Principal, require_roles
from app.core.storage import get_store
from app.modules.audit import service as audit
from app.modules.audit.service import actor_of
from app.modules.orgs import prealert, service
from app.modules.orgs.domain import OrgRole
from app.modules.orgs.models import Organization, Prealert
from app.modules.orgs.service import CurrentUser
from app.modules.orgs.staff_router import ORG_READ_ROLES

router = APIRouter(prefix="/api/v1", tags=["institutions"])
staff_router = APIRouter(prefix="/api/v1/staff", tags=["staff-institutions"])

Session = Annotated[AsyncSession, Depends(get_session)]
OrgReader = Annotated[Principal, Depends(require_roles(*ORG_READ_ROLES))]


class PrealertOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    org_name: str | None = None
    stream_id: uuid.UUID | None
    source: str
    label: str
    confidence: float
    simulated: bool
    state: Literal["pending", "cancelled", "confirmed", "escalated"]
    raised_at: datetime
    deadline_at: datetime
    seconds_left: int
    reason: str | None
    report_id: uuid.UUID | None
    has_frame: bool


class DecisionIn(BaseModel):
    action: Literal["cancel", "confirm"]
    # A false alarm says why (a ready reason or a short text), so the room can follow repeated cancellations.
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)] | None = None


class FrameOut(BaseModel):
    url: str


async def _row(session: AsyncSession, org_id: uuid.UUID, prealert_id: uuid.UUID, *, lock: bool = False) -> Prealert:
    query = select(Prealert).where(Prealert.id == prealert_id, Prealert.org_id == org_id)
    row = await session.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return row


@router.get("/orgs/{org_id}/prealerts", response_model=list[PrealertOut])
async def list_prealerts(
    org_id: uuid.UUID,
    user: CurrentUser,
    session: Session,
    state: Annotated[Literal["pending", "all"], Query()] = "all",
) -> list[PrealertOut]:
    org, _ = await service.membership(session, user, org_id)
    query = select(Prealert).where(Prealert.org_id == org_id)
    if state == "pending":
        query = query.where(Prealert.state == prealert.PENDING)
    rows = await session.scalars(query.order_by(Prealert.raised_at.desc()).limit(50))
    return [PrealertOut.model_validate(prealert.out(r, org.name)) for r in rows]


@router.post("/orgs/{org_id}/prealerts/{prealert_id}/decision", response_model=PrealertOut)
async def decide(
    org_id: uuid.UUID, prealert_id: uuid.UUID, body: DecisionIn, user: CurrentUser, session: Session
) -> PrealertOut:
    """«False alarm» (with a reason) or «confirm» (the report goes to the room at once)."""
    org, _ = await service.membership(session, user, org_id, OrgRole.EDITOR)
    if body.action == "cancel" and not body.reason:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reason_required")
    row = await _row(session, org_id, prealert_id, lock=True)
    # The report is the institution's and reaches the room's tables (row-level security): written as the system.
    async with as_system(session):
        await prealert.decide(session, row, user.user_id, body.action, body.reason)
    await audit.record(
        session,
        actor=user.actor,
        action=f"prealert.{body.action}",
        target=f"prealert:{row.id}",
        reason=body.reason,
        details={"org": str(org_id), "report": str(row.report_id) if row.report_id else None},
    )
    await session.commit()
    return PrealertOut.model_validate(prealert.out(row, org.name))


@router.get("/orgs/{org_id}/prealerts/{prealert_id}/frame", response_model=FrameOut)
async def frame(org_id: uuid.UUID, prealert_id: uuid.UUID, user: CurrentUser, session: Session) -> FrameOut:
    """The camera picture that raised the pre-alert (a short-lived link)."""
    await service.membership(session, user, org_id)
    row = await _row(session, org_id, prealert_id)
    if row.media_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_frame")
    from app.modules.reports.models import Media

    async with as_system(session):
        media = await session.get(Media, row.media_id)
    if media is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_frame")
    return FrameOut(url=get_store().presign_get(media.object_key, content_type="image/jpeg"))


@staff_router.get("/prealerts", response_model=list[PrealertOut])
async def staff_prealerts(
    principal: OrgReader,
    session: Session,
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[PrealertOut]:
    """The pre-alerts of the institutions in scope, the false alarms included (newest first)."""
    query = select(Prealert, Organization).join(Organization, Organization.id == Prealert.org_id)
    if not principal.is_national:
        query = query.where(Organization.gouvernorat_code == principal.gouvernorat_code)
    elif gouvernorat is not None:
        query = query.where(Organization.gouvernorat_code == gouvernorat)
    rows = (await session.execute(query.order_by(Prealert.raised_at.desc()).limit(limit))).all()
    await audit.record(session, actor=actor_of(principal), action="prealert.list", target="prealerts")
    await session.commit()
    return [PrealertOut.model_validate(prealert.out(p, o.name)) for p, o in rows]
