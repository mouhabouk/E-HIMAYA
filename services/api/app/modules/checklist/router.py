"""The task list of a crisis axis, read from its intervention plan (docs/phase-l/design-l5.md §2.3, AI2).

Every reader of the axis sees the list; the room manager of the axis (the commander for every axis) asks the local
model to read a plan, reviews each suggestion and approves the list; the operations rooms of the axis follow it.
The dry run's list has the same routes under /drills (app/modules/drill/router.py).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal
from app.modules.checklist import schemas as s
from app.modules.checklist import service
from app.modules.crisis import domain as crisis
from app.modules.crisis import service as axes
from app.modules.crisis.router import Reader
from app.modules.register import plans as register_plans
from app.modules.register import service as register
from app.modules.register.models import Document

router = APIRouter(prefix="/api/v1/staff/crisis/axes/{axis_id}/checklist", tags=["staff", "crisis"])
Session = Annotated[AsyncSession, Depends(get_session)]


async def owner_of(session: AsyncSession, principal: Principal, axis_id: uuid.UUID) -> service.Owner:
    axis = await axes.get_axis(session, axis_id)
    codes = await axes.codes_of(session, axis)
    is_open = axis.status == "open"
    manages = is_open and crisis.can_manage_axis(principal, axis.gouvernorat_code)
    room = crisis.is_room(principal)
    docs: list[Document] = []
    if axis.plan_document_id is not None:
        doc = await session.get(Document, axis.plan_document_id)
        if doc is not None and register.readable(principal, doc):
            docs.append(doc)
    docs += await register_plans.for_axis(session, principal, axis.kind, codes)
    return service.Owner(
        axis_id=axis.id,
        exercise_id=None,
        hazard=axis.kind,
        plans=service.offered(docs),
        can_request=manages,
        can_review=manages,
        can_follow=is_open and room and (principal.is_national or principal.gouvernorat_code in codes),
        # Governors and ministers read the list without the names of the agents (as on the axis).
        show_names=room,
        gouvernorats=codes,
    )


async def _answer(session: AsyncSession, principal: Principal, axis_id: uuid.UUID) -> s.ChecklistOut:
    owner = await owner_of(session, principal, axis_id)
    out = await service.view(session, owner, await service.find(session, owner))
    await session.commit()
    return out


@router.get("", response_model=s.ChecklistOut)
async def get_checklist(principal: Reader, session: Session, axis_id: uuid.UUID) -> s.ChecklistOut:
    owner = await owner_of(session, principal, axis_id)
    return await service.view(session, owner, await service.find(session, owner))


@router.post("/read", response_model=s.ChecklistOut, status_code=202)
async def read_plan(principal: Reader, session: Session, axis_id: uuid.UUID, body: s.ReadIn) -> s.ChecklistOut:
    """The local model reads the plan in the background; the list shows "reading" until its suggestions arrive."""
    await service.request_reading(session, principal, await owner_of(session, principal, axis_id), body)
    return await _answer(session, principal, axis_id)


@router.post("/tasks", response_model=s.ChecklistOut, status_code=201)
async def add_task(principal: Reader, session: Session, axis_id: uuid.UUID, body: s.TaskIn) -> s.ChecklistOut:
    await service.add(session, principal, await owner_of(session, principal, axis_id), body)
    return await _answer(session, principal, axis_id)


@router.post("/tasks/{task_id}/review", response_model=s.ChecklistOut)
async def review_task(
    principal: Reader, session: Session, axis_id: uuid.UUID, task_id: uuid.UUID, body: s.ReviewIn
) -> s.ChecklistOut:
    await service.review(session, principal, await owner_of(session, principal, axis_id), task_id, body)
    return await _answer(session, principal, axis_id)


@router.post("/approve", response_model=s.ChecklistOut)
async def approve(principal: Reader, session: Session, axis_id: uuid.UUID, body: s.ApproveIn) -> s.ChecklistOut:
    await service.approve(session, principal, await owner_of(session, principal, axis_id), body)
    return await _answer(session, principal, axis_id)


@router.post("/tasks/{task_id}/status", response_model=s.ChecklistOut)
async def follow_task(
    principal: Reader, session: Session, axis_id: uuid.UUID, task_id: uuid.UUID, body: s.FollowIn
) -> s.ChecklistOut:
    await service.follow(session, principal, await owner_of(session, principal, axis_id), task_id, body)
    return await _answer(session, principal, axis_id)
