"""Volunteer network of the dashboard (FR-C-04): register, review, readiness map."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.reports.staff_router import READ_ROLES, _bbox
from app.modules.volunteers import schemas, service

router = APIRouter(prefix="/api/v1/staff/volunteers", tags=["staff-volunteers"])
Session = Annotated[AsyncSession, Depends(get_session)]
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
Reviewer = Annotated[Principal, Depends(require_roles(Role.OPS_MANAGER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE))]
STATUSES = ("pending", "approved", "rejected", "suspended", "withdrawn")
SKILLS = schemas.Skill.__args__  # type: ignore[attr-defined]


@router.get("", response_model=schemas.StaffVolunteerPage)
async def list_volunteers(
    principal: Reader,
    session: Session,
    status_: Annotated[str | None, Query(alias="status")] = None,
    skill: str | None = None,
    gouvernorat_code: int | None = None,
    ready: bool | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> schemas.StaffVolunteerPage:
    statuses = [s.strip() for s in (status_ or "").split(",") if s.strip()]
    if any(s not in STATUSES for s in statuses):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_status")
    if skill is not None and skill not in SKILLS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_skill")
    items, next_cursor = await service.staff_list(
        session,
        principal,
        statuses=statuses,
        skill=skill,
        gouvernorat_code=gouvernorat_code,
        ready=ready,
        q=q.strip() if q and q.strip() else None,
        limit=limit,
        cursor=cursor,
    )
    return schemas.StaffVolunteerPage(items=items, next_cursor=next_cursor)


@router.get("/map")
async def volunteers_map(
    principal: Reader, session: Session, bbox: str | None = None, skill: str | None = None
) -> dict[str, Any]:
    if skill is not None and skill not in SKILLS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_skill")
    return await service.map_features(session, principal, _bbox(bbox), skill)


@router.get("/{volunteer_id}", response_model=schemas.StaffVolunteerDetail)
async def get_volunteer(principal: Reader, session: Session, volunteer_id: uuid.UUID) -> schemas.StaffVolunteerDetail:
    volunteer = await service.get_in_scope(session, principal, volunteer_id)
    detail = await service.staff_detail(session, volunteer)
    # NFR-06: the file shows personal data (phone, e-mail) and is audited.
    await audit.record(
        session, actor=audit.actor_of(principal), action="volunteer.view", target=f"volunteer:{volunteer_id}"
    )
    await session.commit()
    return detail


@router.post("/{volunteer_id}/review", response_model=schemas.StaffVolunteerDetail)
async def review_volunteer(
    principal: Reviewer, session: Session, volunteer_id: uuid.UUID, body: schemas.VolunteerReviewIn
) -> schemas.StaffVolunteerDetail:
    volunteer = await service.get_in_scope(session, principal, volunteer_id, lock=True)
    previous = await service.review(session, principal, volunteer, body)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="volunteer.review",
        target=f"volunteer:{volunteer_id}",
        reason=body.reason,
        details={"decision": body.decision, "from": previous, "to": volunteer.status},
    )
    detail = await service.staff_detail(session, volunteer)
    await session.commit()
    return detail
