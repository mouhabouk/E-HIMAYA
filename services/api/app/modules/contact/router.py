"""Contact us (phase B1, docs/phase-b/design.md §2ter): requests with a number and a status.

The app sends a request (access to information under law 2016-22, non-urgent hazard, question, suggestion, app problem,
partnership); the citizen follows its status and reads the answer. The Office handles them in one inbox by kind and
gouvernorat. Contact details and texts are encrypted; internal notes never reach the citizen. Every staff change and
every opening of a request is audited. This is not an emergency channel: the form says "for an emergency call 198".
"""

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import as_system, get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.contact.models import ContactEvent, ContactRequest
from app.modules.geo.models import Gouvernorat
from app.modules.identity.service import CurrentReporter, limit_reporter
from app.modules.moderation import service as moderation
from app.modules.settings import domain as settings_domain
from app.modules.settings import service as settings
from app.modules.telephony.domain import normalize_tn_number

router = APIRouter(prefix="/api/v1", tags=["contact"])
staff_router = APIRouter(prefix="/api/v1/staff/contact", tags=["contact"])
Session = Annotated[AsyncSession, Depends(get_session)]
Handler = Annotated[
    Principal,
    Depends(require_roles(Role.OPS_MANAGER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE, Role.CONTENT_EDITOR)),
]

Kind = Literal["access_info", "hazard", "question", "suggestion", "app_problem", "partnership"]
Status = Literal["received", "in_progress", "answered", "closed", "rejected"]
KINDS: tuple[str, ...] = Kind.__args__  # type: ignore[attr-defined]
STATUSES: tuple[str, ...] = Status.__args__  # type: ignore[attr-defined]
StatusFilter = Literal["open", "all", "received", "in_progress", "answered", "closed", "rejected"]
OPEN = ("received", "in_progress")

PER_ACCOUNT_PER_DAY = 5
PER_IP_PER_DAY = 10
DAY_S = 86_400
MAX_STAFF_LIST = 500

Subject = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)]
Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=3000)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=3000)]
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ContactIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Kind
    subject: Subject
    message: Message
    gouvernorat_code: int | None = Field(default=None, ge=1, le=99)
    name: Name | None = None
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=200)
    locale: Literal["ar", "fr", "en"] = "ar"
    platform: Literal["android", "ios", "web"] | None = None

    @model_validator(mode="after")
    def _rules(self) -> "ContactIn":
        # Law 2016-22 asks who requests the information; a hazard needs a place to be handled.
        if self.kind == "access_info" and not self.name:
            raise ValueError("name_required")
        if self.kind == "hazard" and self.gouvernorat_code is None:
            raise ValueError("gouvernorat_required")
        return self


class EventOut(BaseModel):
    action: str
    status: str | None
    gouvernorat_code: int | None
    at: datetime


class MineOut(BaseModel):
    id: uuid.UUID
    number: str
    kind: str
    status: str
    subject: str
    message: str
    gouvernorat_code: int | None
    created_at: datetime
    due_at: datetime | None
    answer: str | None
    answered_at: datetime | None
    history: list[EventOut]


class MineList(BaseModel):
    items: list[MineOut]


class StaffEventOut(EventOut):
    id: uuid.UUID
    note: str | None
    visible: bool
    actor_name: str | None


class SummaryOut(BaseModel):
    id: uuid.UUID
    number: str
    kind: str
    status: str
    subject: str
    gouvernorat_code: int | None
    created_at: datetime
    updated_at: datetime
    due_at: datetime | None
    overdue: bool
    assigned_name: str | None
    anonymous: bool
    version: int


class InboxOut(BaseModel):
    items: list[SummaryOut]
    truncated: bool
    # Open requests per kind and overdue ones, in the caller's scope (badges of the inbox).
    open_by_kind: dict[str, int]
    overdue: int


class DetailOut(SummaryOut):
    name: str | None
    phone: str | None
    email: str | None
    message: str
    answer: str | None
    answered_at: datetime | None
    closed_at: datetime | None
    locale: str
    platform: str | None
    events: list[StaffEventOut]


class ActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    action: Literal["take", "answer", "note", "move", "close", "reject", "reopen"]
    # The answer, the note or the reason of a rejection (shown to the citizen except for a note).
    text: Text | None = None
    gouvernorat_code: int | None = Field(default=None, ge=1, le=99)


def _overdue(r: ContactRequest, now: datetime) -> bool:
    return r.due_at is not None and r.status in OPEN and r.due_at < now


async def _check_gouvernorat(session: AsyncSession, code: int | None) -> None:
    if code is not None and await session.get(Gouvernorat, code) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown_gouvernorat")


async def _events(session: AsyncSession, request_id: uuid.UUID) -> list[ContactEvent]:
    return list(
        await session.scalars(
            select(ContactEvent).where(ContactEvent.request_id == request_id).order_by(ContactEvent.at, ContactEvent.id)
        )
    )


async def _mine_out(session: AsyncSession, r: ContactRequest) -> MineOut:
    # Row-level security keeps the internal notes out; `visible` is checked here too.
    events = [e for e in await _events(session, r.id) if e.visible]
    return MineOut(
        id=r.id,
        number=r.number,
        kind=r.kind,
        status=r.status,
        subject=r.subject,
        message=r.message,
        gouvernorat_code=r.gouvernorat_code,
        created_at=r.created_at,
        due_at=r.due_at,
        answer=r.answer,
        answered_at=r.answered_at,
        history=[
            EventOut(action=e.action, status=e.status, gouvernorat_code=e.gouvernorat_code, at=e.at) for e in events
        ],
    )


@router.post("/contact", response_model=MineOut, status_code=status.HTTP_201_CREATED)
async def send_request(request: Request, reporter: CurrentReporter, session: Session, body: ContactIn) -> MineOut:
    await limit_reporter(
        request, reporter, "contact", per_account=PER_ACCOUNT_PER_DAY, per_ip=PER_IP_PER_DAY, window_s=DAY_S
    )
    await _check_gouvernorat(session, body.gouvernorat_code)
    phone = None
    if body.phone and body.phone.strip():
        phone = normalize_tn_number(body.phone)
        if phone is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_phone")
    email = body.email.strip() if body.email and body.email.strip() else None
    if email is not None and not _EMAIL.match(email):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_email")
    # Not emergency text: the respectful-language filter applies (rule 4).
    await moderation.check(session, body.subject, body.message, body.name)
    now = datetime.now(UTC)
    due = None
    if body.kind == "access_info":
        days = int(await settings.get(session, settings_domain.CONTACT_ACCESS_INFO_DAYS))
        due = now + timedelta(days=days)
    row = ContactRequest(
        kind=body.kind,
        user_id=reporter.user_id,
        gouvernorat_code=body.gouvernorat_code,
        subject=body.subject,
        name=body.name,
        phone=phone,
        email=email,
        message=body.message,
        locale=body.locale,
        platform=body.platform,
        due_at=due,
    )
    session.add(row)
    await session.flush()
    session.add(
        ContactEvent(
            request_id=row.id,
            action="created",
            status="received",
            gouvernorat_code=row.gouvernorat_code,
            visible=True,
            actor=reporter.actor,
        )
    )
    await session.flush()
    await audit.record(
        session,
        actor=reporter.actor,
        action="contact.create",
        target=f"contact:{row.number}",
        details={"kind": row.kind, "gouvernorat": row.gouvernorat_code},
    )
    out = await _mine_out(session, row)
    await session.commit()
    return out


@router.get("/me/contact", response_model=MineList)
async def my_requests(reporter: CurrentReporter, session: Session) -> MineList:
    rows = await session.scalars(
        select(ContactRequest)
        .where(ContactRequest.user_id == reporter.user_id)
        .order_by(ContactRequest.created_at.desc())
        .limit(100)
    )
    return MineList(items=[await _mine_out(session, r) for r in rows.all()])


def _summary(r: ContactRequest, now: datetime) -> dict[str, object]:
    return {
        "id": r.id,
        "number": r.number,
        "kind": r.kind,
        "status": r.status,
        "subject": r.subject,
        "gouvernorat_code": r.gouvernorat_code,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
        "due_at": r.due_at,
        "overdue": _overdue(r, now),
        "assigned_name": r.assigned_name,
        "anonymous": r.name is None and r.phone is None and r.email is None,
        "version": r.version,
    }


def _scoped(principal: Principal) -> Select[ContactRequest]:
    """The API's own copy of the scope rule (row-level security is the second layer)."""
    query = select(ContactRequest)
    if not principal.is_national:
        query = query.where(ContactRequest.gouvernorat_code == principal.gouvernorat_code)
    return query


@staff_router.get("", response_model=InboxOut)
async def inbox(
    principal: Handler,
    session: Session,
    kind: Annotated[Kind | None, Query()] = None,
    state: Annotated[StatusFilter, Query(alias="status")] = "open",
    gouvernorat: Annotated[int | None, Query(ge=0, le=99, description="0: requests without a gouvernorat")] = None,
    overdue: bool = False,
) -> InboxOut:
    now = datetime.now(UTC)
    query = _scoped(principal)
    if kind is not None:
        query = query.where(ContactRequest.kind == kind)
    if state == "open":
        query = query.where(ContactRequest.status.in_(OPEN))
    elif state != "all":
        query = query.where(ContactRequest.status == state)
    if gouvernorat == 0:
        query = query.where(ContactRequest.gouvernorat_code.is_(None))
    elif gouvernorat is not None:
        query = query.where(ContactRequest.gouvernorat_code == gouvernorat)
    if overdue:
        query = query.where(ContactRequest.status.in_(OPEN), ContactRequest.due_at < now)
    rows = list(
        await session.scalars(
            query.order_by(ContactRequest.due_at.asc().nulls_last(), ContactRequest.created_at.desc()).limit(
                MAX_STAFF_LIST + 1
            )
        )
    )
    open_rows = _scoped(principal).where(ContactRequest.status.in_(OPEN)).subquery()
    by_kind: dict[str, int] = dict(
        (await session.execute(select(open_rows.c.kind, func.count()).group_by(open_rows.c.kind))).all()
    )
    late = await session.scalar(select(func.count()).select_from(open_rows).where(open_rows.c.due_at < now))
    return InboxOut(
        items=[SummaryOut.model_validate(_summary(r, now)) for r in rows[:MAX_STAFF_LIST]],
        truncated=len(rows) > MAX_STAFF_LIST,
        open_by_kind={k: int(by_kind.get(k, 0)) for k in KINDS},
        overdue=int(late or 0),
    )


async def _get(
    session: AsyncSession, principal: Principal, request_id: uuid.UUID, *, lock: bool = False
) -> ContactRequest:
    query = _scoped(principal).where(ContactRequest.id == request_id)
    row = await session.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return row


async def _detail(session: AsyncSession, r: ContactRequest) -> DetailOut:
    now = datetime.now(UTC)
    return DetailOut(
        **_summary(r, now),
        name=r.name,
        phone=r.phone,
        email=r.email,
        message=r.message,
        answer=r.answer,
        answered_at=r.answered_at,
        closed_at=r.closed_at,
        locale=r.locale,
        platform=r.platform,
        events=[
            StaffEventOut(
                id=e.id,
                action=e.action,
                status=e.status,
                gouvernorat_code=e.gouvernorat_code,
                at=e.at,
                note=e.note,
                visible=e.visible,
                actor_name=e.actor_name,
            )
            for e in await _events(session, r.id)
        ],
    )


@staff_router.get("/{request_id}", response_model=DetailOut)
async def get_request(principal: Handler, session: Session, request_id: uuid.UUID) -> DetailOut:
    """Opening a request shows personal data: audited."""
    row = await _get(session, principal, request_id)
    await audit.record(session, actor=audit.actor_of(principal), action="contact.view", target=f"contact:{row.number}")
    out = await _detail(session, row)
    await session.commit()
    return out


# Status each action leads to, from the statuses it is allowed in (note and move keep the status).
TRANSITIONS: dict[str, tuple[tuple[str, ...], str | None]] = {
    "take": (("received", "in_progress"), "in_progress"),
    "answer": (("received", "in_progress", "answered"), "answered"),
    "note": (STATUSES, None),
    "move": (OPEN, None),
    "close": (("received", "in_progress", "answered"), "closed"),
    "reject": (("received", "in_progress"), "rejected"),
    "reopen": (("answered", "closed", "rejected"), "in_progress"),
}


@staff_router.post("/{request_id}/actions", response_model=DetailOut)
async def act(principal: Handler, session: Session, request_id: uuid.UUID, body: ActionIn) -> DetailOut:
    row = await _get(session, principal, request_id, lock=True)
    if row.version != body.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
    allowed, target = TRANSITIONS[body.action]
    if row.status not in allowed:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    if body.action in ("answer", "note", "reject") and not body.text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "text_required")
    now = datetime.now(UTC)
    actor, name = audit.actor_of(principal), audit.name_of(principal)
    event = ContactEvent(request_id=row.id, action="status", actor=actor, actor_name=name, at=now, visible=True)
    details: dict[str, object] = {"from": row.status}
    if body.action == "take":
        row.assigned_to, row.assigned_name = actor, name
    elif body.action == "answer":
        assert body.text is not None
        row.answer, row.answered_at = body.text, now
        event.action, event.note = "answer", body.text
    elif body.action == "note":
        event.action, event.note, event.visible = "note", body.text, False
    elif body.action == "move":
        if body.gouvernorat_code == row.gouvernorat_code:
            raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
        await _check_gouvernorat(session, body.gouvernorat_code)
        details["gouvernorat_from"] = row.gouvernorat_code
        row.gouvernorat_code = body.gouvernorat_code
        row.assigned_to = row.assigned_name = None
        event.action, event.gouvernorat_code = "move", body.gouvernorat_code
        details["gouvernorat_to"] = body.gouvernorat_code
    elif body.action == "reject":
        row.answer, row.answered_at = body.text, now
        event.note = body.text
    if body.action in ("close", "reject"):
        row.closed_at = now
    elif body.action == "reopen":
        row.closed_at = None
    if target is not None:
        row.status = target
        event.status = target
    row.version += 1
    row.updated_at = now
    session.add(event)
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action=f"contact.{body.action}",
        target=f"contact:{row.number}",
        details={**details, "to": row.status},
    )
    # A move out of the caller's gouvernorat takes the request out of their sight: answer from the national view.
    out = await _detail(session, row)
    await session.commit()
    return out


# ---------------------------------------------------------------- rights of the person (export, erasure)


class ExportContact(MineOut):
    name: str | None
    phone: str | None
    email: str | None


async def export(session: AsyncSession, user_id: uuid.UUID) -> list[ExportContact]:
    rows = await session.scalars(
        select(ContactRequest).where(ContactRequest.user_id == user_id).order_by(ContactRequest.created_at)
    )
    return [
        ExportContact(**(await _mine_out(session, r)).model_dump(), name=r.name, phone=r.phone, email=r.email)
        for r in rows.all()
    ]


async def forget(session: AsyncSession, user_id: uuid.UUID) -> int:
    """Requests stay for the Office's records, without the link to the account or the contact details. Only staff
    may update requests: this step runs with the system scope, after the account owner's own request."""
    async with as_system(session) as system:
        result = await system.execute(
            update(ContactRequest)
            .where(ContactRequest.user_id == user_id)
            .values(user_id=None, name=None, phone=None, email=None, updated_at=func.now())
        )
    return int(result.rowcount)  # type: ignore[attr-defined]
