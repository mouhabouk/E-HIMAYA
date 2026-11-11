"""Guided call-taking cards: reading them in the rooms, writing and approving them (OS2, design-os2.md §3).

* The rooms (operator, room manager) read the approved card of each category when they write a call down.
* The Office writes a new version as a draft (national content editor or national room manager); editing a draft
  withdraws its medical validation.
* A card with medical instructions is approved only after its medical validation is recorded (national medical
  coordinator, or the content editor naming the doctor who validated it, as for the emergency guide).
* A national room manager approves a draft: it replaces the approved version, which is retired (kept, as every
  report keeps the version it was entered with).
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import NATIONAL_SCOPE_REQUIRED, Action, authorize, require
from app.core.db import as_system, get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.reports import callcards as cc
from app.modules.reports import service
from app.modules.reports.callcards import AnswerOut
from app.modules.reports.domain import Category
from app.modules.reports.models import CallCard, CallCardAnswer, Report

router = APIRouter(prefix="/api/v1/staff", tags=["staff", "call-cards"])
Session = Annotated[AsyncSession, Depends(get_session)]
Reader = Annotated[
    Principal,
    Depends(require_roles(Role.OPERATOR, Role.OPS_MANAGER, Role.CONTENT_EDITOR, Role.MEDICAL_COORDINATOR)),
]
Editor = Annotated[Principal, Depends(require_roles(Role.CONTENT_EDITOR, Role.OPS_MANAGER))]
MedicalValidator = Annotated[Principal, Depends(require_roles(Role.MEDICAL_COORDINATOR, Role.CONTENT_EDITOR))]
Approver = Annotated[Principal, Depends(require_roles(Role.OPS_MANAGER))]
ReportReader = Annotated[
    Principal,
    Depends(
        require_roles(
            Role.OPERATOR, Role.OPS_MANAGER, Role.FIELD_COMMANDER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE
        )
    ),
]

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class CardOut(BaseModel):
    id: uuid.UUID
    category: Category
    version: int
    status: str
    content: cc.CardContent
    sim: bool
    medical: bool
    medical_validated_by: str | None
    medical_validated_at: datetime | None
    medical_reason: str | None
    approved_by: str | None
    approved_at: datetime | None
    approval_reason: str | None
    created_by_name: str | None
    updated_by_name: str | None
    updated_at: datetime
    used: int = 0


class CardsOut(BaseModel):
    cards: list[CardOut]


class DraftIn(BaseModel):
    content: cc.CardContent
    reason: Reason


class DraftUpdateIn(DraftIn):
    # The version of the draft the person edited (its updated_at): a change made meanwhile answers 409.
    updated_at: datetime


class ReasonIn(BaseModel):
    reason: Reason
    # The version of the row the person read (its updated_at): a change made meanwhile answers 409.
    updated_at: datetime


def answer_out(card: CallCard, row: CallCardAnswer) -> AnswerOut:
    content = cc.CardContent.model_validate(card.content)
    merged = {**row.answers, **(row.field_answers or {})}
    read = [k for k in row.outcome.get("read", []) if k in content.instructions]
    offered = row.field_outcome["instructions"] if row.field_outcome else row.outcome.get("instructions", [])
    keys = list(dict.fromkeys([*read, *offered]))
    return AnswerOut(
        report_id=row.report_id,
        card_id=card.id,
        category=Category(row.category),
        card_version=row.card_version,
        sim=card.sim,
        title=content.title,
        answers=row.answers,
        outcome=cc.Outcome.model_validate(row.outcome),
        read=read,
        field_answers=row.field_answers,
        field_outcome=cc.Outcome.model_validate(row.field_outcome) if row.field_outcome else None,
        field_by_name=row.field_by_name,
        field_at=row.field_at,
        questions=cc.asked(content, merged),
        instructions={k: content.instructions[k] for k in keys if k in content.instructions},
        created_at=row.created_at,
    )


def _national(principal: Principal) -> None:
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, NATIONAL_SCOPE_REQUIRED)


def _out(card: CallCard, used: int = 0) -> CardOut:
    return CardOut(
        id=card.id,
        category=Category(card.category),
        version=card.version,
        status=card.status,
        content=cc.CardContent.model_validate(card.content),
        sim=card.sim,
        medical=card.medical,
        medical_validated_by=card.medical_validated_by,
        medical_validated_at=card.medical_validated_at,
        medical_reason=card.medical_reason,
        approved_by=card.approved_by,
        approved_at=card.approved_at,
        approval_reason=card.approval_reason,
        created_by_name=card.created_by_name,
        updated_by_name=card.updated_by_name,
        updated_at=card.updated_at,
        used=used,
    )


async def _card(session: AsyncSession, card_id: uuid.UUID, lock: bool = False) -> CallCard:
    card = await session.get(CallCard, card_id, with_for_update=lock)
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return card


def _is_medical(category: str, content: cc.CardContent) -> bool:
    return category in cc.MEDICAL_CATEGORIES or content.medical_instructions


async def approved(session: AsyncSession, category: str) -> CallCard | None:
    return await session.scalar(select(CallCard).where(CallCard.category == category, CallCard.status == "approved"))


@router.get("/call-cards", response_model=CardsOut)
async def list_cards(principal: Reader, session: Session, include: str = "current") -> CardsOut:
    """``current``: the approved card and the draft of each category; ``all``: every version (the history)."""
    query = select(CallCard).order_by(CallCard.category, CallCard.version.desc())
    if include != "all":
        query = query.where(CallCard.status != "retired")
    cards = list(await session.scalars(query))
    used = dict(
        (await session.execute(select(CallCardAnswer.card_id, func.count()).group_by(CallCardAnswer.card_id))).all()
    )
    return CardsOut(cards=[_out(c, used.get(c.id, 0)) for c in cards])


@router.post("/call-cards/{category}/draft", response_model=CardOut, status_code=status.HTTP_201_CREATED)
async def create_draft(principal: Editor, session: Session, category: Category, body: DraftIn) -> CardOut:
    """A new version of the card of ``category``, written as a draft (one draft per category at a time)."""
    _national(principal)
    if await session.scalar(select(CallCard.id).where(CallCard.category == category, CallCard.status == "draft")):
        raise HTTPException(status.HTTP_409_CONFLICT, "draft_exists")
    last = await session.scalar(select(func.max(CallCard.version)).where(CallCard.category == category))
    now = datetime.now(UTC)
    card = CallCard(
        category=category.value,
        version=(last or 0) + 1,
        status="draft",
        content=body.content.model_dump(mode="json"),
        sim=False,
        medical=_is_medical(category.value, body.content),
        created_by=audit.actor_of(principal),
        created_by_name=audit.name_of(principal),
        updated_by_name=audit.name_of(principal),
        created_at=now,
        updated_at=now,
    )
    session.add(card)
    await session.flush()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="call_card.draft",
        target=f"call_card:{card.id}",
        reason=body.reason,
        details={"category": category.value, "version": card.version},
    )
    await session.commit()
    return _out(card)


@router.put("/call-cards/{card_id}", response_model=CardOut)
async def update_draft(principal: Editor, session: Session, card_id: uuid.UUID, body: DraftUpdateIn) -> CardOut:
    """Change a draft. Its medical validation, if any, is withdrawn: the text changed."""
    _national(principal)
    card = await _card(session, card_id, lock=True)
    if card.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "call_card_not_draft")
    if card.updated_at != body.updated_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
    card.content = body.content.model_dump(mode="json")
    card.medical = _is_medical(card.category, body.content)
    card.medical_validated_by = card.medical_validated_at = card.medical_reason = None
    card.updated_by_name = audit.name_of(principal)
    card.updated_at = datetime.now(UTC)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="call_card.update",
        target=f"call_card:{card.id}",
        reason=body.reason,
        details={"category": card.category, "version": card.version},
    )
    await session.commit()
    return _out(card)


@router.delete("/call-cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def discard_draft(principal: Editor, session: Session, card_id: uuid.UUID) -> Response:
    _national(principal)
    card = await _card(session, card_id, lock=True)
    if card.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "call_card_not_draft")
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="call_card.discard",
        target=f"call_card:{card.id}",
        details={"category": card.category, "version": card.version},
    )
    await session.delete(card)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/call-cards/{card_id}/medical-validation", response_model=CardOut)
async def validate_medical(
    principal: MedicalValidator, session: Session, card_id: uuid.UUID, body: ReasonIn
) -> CardOut:
    """Record that the medical staff validated this draft's text (the reason names who, as for the guide)."""
    _national(principal)
    card = await _card(session, card_id, lock=True)
    if card.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "call_card_not_draft")
    if card.updated_at != body.updated_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
    now = datetime.now(UTC)
    card.medical_validated_by = audit.name_of(principal) or audit.actor_of(principal)
    card.medical_validated_at = now
    card.medical_reason = body.reason
    card.updated_at = now
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="call_card.medical_validation",
        target=f"call_card:{card.id}",
        reason=body.reason,
        details={"category": card.category, "version": card.version},
    )
    await session.commit()
    return _out(card)


@router.post("/call-cards/{card_id}/approve", response_model=CardOut)
async def approve(principal: Approver, session: Session, card_id: uuid.UUID, body: ReasonIn) -> CardOut:
    """The draft becomes the card the rooms use; the version it replaces is retired."""
    _national(principal)
    card = await _card(session, card_id, lock=True)
    if card.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "call_card_not_draft")
    if card.updated_at != body.updated_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
    if card.medical and card.medical_validated_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "medical_validation_required")
    now = datetime.now(UTC)
    previous = await session.scalar(
        select(CallCard).where(CallCard.category == card.category, CallCard.status == "approved").with_for_update()
    )
    if previous is not None:
        previous.status = "retired"
        previous.retired_at = now
        await session.flush()
    card.status = "approved"
    card.approved_by = audit.name_of(principal) or audit.actor_of(principal)
    card.approved_at = now
    card.approval_reason = body.reason
    card.updated_at = now
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="call_card.approve",
        target=f"call_card:{card.id}",
        reason=body.reason,
        details={
            "category": card.category,
            "version": card.version,
            "replaces": previous.version if previous is not None else None,
        },
    )
    await session.commit()
    return _out(card)


@router.get("/reports/{report_id}/call-card", response_model=AnswerOut)
async def report_answers(principal: ReportReader, session: Session, report_id: uuid.UUID) -> AnswerOut:
    """The card answered when the room wrote this report down; 404 when it was entered without one."""
    report = await session.get(Report, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    require(await authorize(session, principal, Action.REPORT_READ, await service.report_ctx(session, report)))
    row = await session.get(CallCardAnswer, report_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_call_card")
    out = answer_out(await _card(session, row.card_id), row)
    if report.incident_id is not None:
        out.scene = await scene_of(session, report.incident_id, row.category, out.field_outcome or out.outcome)
    return out


async def scene_of(session: AsyncSession, incident_id: uuid.UUID, category: str, outcome: cc.Outcome) -> cc.Scene:
    """The nature the teams confirmed (the latest one) and the incident's casualty counters, against the card."""
    from app.modules.ops.models import Assignment, CasualtyCount

    async with as_system(session):
        nature = await session.scalar(
            select(Assignment.crew_nature)
            .where(Assignment.incident_id == incident_id, Assignment.crew_nature.is_not(None))
            .order_by(Assignment.created_at.desc())
            .limit(1)
        )
        counts = await session.get(CasualtyCount, incident_id)
    scene = cc.Scene(nature=nature)
    if counts is not None:
        scene.injured = counts.injured_light + counts.injured_serious
        scene.serious = counts.injured_serious
        scene.deceased = counts.deceased
        scene.trapped = counts.trapped
    scene.checks = cc.compare(category, outcome, scene)
    return scene


# ---------------------------------------------------------------- at intake (reports.intake)


async def record(
    session: AsyncSession, principal: Principal, report: Report, category: str, body: cc.CallCardIn
) -> str:
    """Check the answers against the approved card, store them and set the report's floor; return the summary."""
    card = await session.get(CallCard, body.card_id)
    if card is None or card.category != category:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "call_card_category")
    if card.status != "approved" or card.version != body.version:
        # The Office approved a newer version while the call was being taken: the room reloads the card.
        raise HTTPException(status.HTTP_409_CONFLICT, "call_card_changed")
    content = cc.CardContent.model_validate(card.content)
    try:
        answers = cc.clean_answers(content, body.answers)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "call_card_question") from exc
    outcome = cc.evaluate(content, answers)
    read = [k for k in body.read if k in outcome.instructions]
    stored: dict[str, Any] = {**outcome.model_dump(), "read": read}
    session.add(
        CallCardAnswer(
            report_id=report.id,
            card_id=card.id,
            category=category,
            card_version=card.version,
            answers=answers,
            outcome=stored,
            entered_by=audit.actor_of(principal),
        )
    )
    report.call_card_floor = outcome.band
    await session.flush()
    return cc.summary(content, card.version, card.sim, answers, outcome, read)


# ---------------------------------------------------------------- on the team's mission (ops.crew)


async def of_incident(session: AsyncSession, incident_id: uuid.UUID) -> CallCardAnswer | None:
    """The card answered on the first report of an incident that was entered with one (read as the system: the team
    reaches it through its mission, which the caller already checked)."""
    async with as_system(session):
        return await session.scalar(
            select(CallCardAnswer)
            .join(Report, Report.id == CallCardAnswer.report_id)
            .where(Report.incident_id == incident_id)
            .order_by(CallCardAnswer.created_at)
            .limit(1)
        )


async def mission_card(session: AsyncSession, incident_id: uuid.UUID) -> AnswerOut | None:
    row = await of_incident(session, incident_id)
    if row is None:
        return None
    async with as_system(session):
        card = await _card(session, row.card_id)
    return answer_out(card, row)


async def record_field(
    session: AsyncSession, principal: Principal, incident_id: uuid.UUID, answers: dict[str, cc.Answer]
) -> cc.Outcome:
    """The team leader's answers from the scene (the caller's are kept); the report's floor rises with them."""
    row = await of_incident(session, incident_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_call_card")
    async with as_system(session):
        card = await _card(session, row.card_id)
        content = cc.CardContent.model_validate(card.content)
        try:
            merged, outcome = cc.on_scene(content, row.answers, answers, cc.Outcome.model_validate(row.outcome))
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "call_card_question") from exc
        field = {k: v for k, v in merged.items() if k in answers}
        row.field_answers = field
        row.field_outcome = outcome.model_dump()
        row.field_by = audit.actor_of(principal)
        row.field_by_name = audit.name_of(principal)
        row.field_at = datetime.now(UTC)
        report = await session.get(Report, row.report_id, with_for_update=True)
        if report is not None:
            floor = report.call_card_floor if report.call_card_floor in cc.BANDS else None
            report.call_card_floor = cc.higher(outcome.band, floor)
        await session.flush()
    return outcome
