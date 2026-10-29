"""The task list of a crisis axis or a dry run, read from its intervention plan (docs/phase-l/design-l5.md §2.3, AI2).

    room manager: "read the plan" ──► queued ──► worker: PDF text ─► local model, window by window ─► review
                                                     (plan unreadable, model down too long ─► failed)
    review: accept, edit or delete each suggestion, add what it missed ──► approve ──► followed task by task

The model only suggests (AI-01): each task keeps its origin and what the reviewer did with it, the list is followed
only once a person approved it, and the reading can be switched off in the AI settings. The reading runs in the
worker, outside any transaction; its result is written only if nobody asked for a new reading meanwhile (version).
The caller (router) decides who may do what and passes an ``Owner``; a dry run's list is reached through the system
scope like every row of a dry run.
"""

import asyncio
import uuid
from collections import Counter as Tally
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from anyio import to_thread
from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.access import ApiError
from app.core.security import Principal
from app.core.storage import ObjectStore, get_store
from app.modules.ai import settings as ai_settings
from app.modules.audit import service as audit
from app.modules.checklist import pdftext, reader
from app.modules.checklist import schemas as s
from app.modules.checklist.models import Checklist, ChecklistTask
from app.modules.decision.llm import LlmClient, LlmUnavailable, get_llm
from app.modules.register.models import Document

log = structlog.get_logger()

MAX_ATTEMPTS = 6
LEASE = timedelta(hours=2)
MAX_TASKS = 300
# Plans whose access level lets every reader of the axis see what was read from them.
OPEN_ACCESS = ("all", "gouvernorat")
KEPT = ("accepted", "edited", "added")


@dataclass(frozen=True)
class Owner:
    """The axis or dry run a list belongs to, as the router resolved it for the caller."""

    axis_id: uuid.UUID | None
    exercise_id: uuid.UUID | None
    hazard: str
    # The plans the list may be read from, readable by the caller (plan in force first).
    plans: list[Document]
    can_request: bool
    can_review: bool
    can_follow: bool
    show_names: bool
    gouvernorats: list[int]

    @property
    def target(self) -> str:
        return f"axis:{self.axis_id}" if self.axis_id else f"exercise:{self.exercise_id}"


def now() -> datetime:
    return datetime.now(UTC)


def readable_plan(doc: Document) -> bool:
    return doc.kind == "plan" and doc.file_type == "application/pdf" and bool(doc.file_key and doc.file_sha256)


def offered(docs: list[Document]) -> list[Document]:
    out: list[Document] = []
    for doc in docs:
        if readable_plan(doc) and doc.access in OPEN_ACCESS and doc.id not in {d.id for d in out}:
            out.append(doc)
    return out


async def reading_available(session: AsyncSession) -> bool:
    return (await ai_settings.load(session)).assist.plan_reading and get_llm() is not None


async def find(session: AsyncSession, owner: Owner, *, lock: bool = False) -> Checklist | None:
    query = select(Checklist).where(
        Checklist.axis_id == owner.axis_id if owner.axis_id else Checklist.exercise_id == owner.exercise_id
    )
    return await session.scalar(query.with_for_update() if lock else query)


def _forbidden() -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, "insufficient_role")


def _conflict(code: str) -> ApiError:
    return ApiError(status.HTTP_409_CONFLICT, code)


async def _tasks(session: AsyncSession, checklist_id: uuid.UUID) -> list[ChecklistTask]:
    rows = await session.scalars(
        select(ChecklistTask).where(ChecklistTask.checklist_id == checklist_id).order_by(ChecklistTask.position)
    )
    return list(rows)


def counts(tasks: list[ChecklistTask]) -> s.Counts:
    out = s.Counts()
    for t in tasks:
        if t.review == "suggested":
            out.suggested += 1
        elif t.review == "deleted":
            out.deleted += 1
        else:
            out.kept += 1
            setattr(out, t.status, getattr(out, t.status) + 1)
    return out


def _plan_ref(doc: Document) -> s.PlanRef:
    return s.PlanRef(id=str(doc.id), number=doc.number, title=doc.title)


def _task_out(t: ChecklistTask, names: bool) -> s.TaskOut:
    return s.TaskOut(
        id=str(t.id),
        position=t.position,
        action=t.action,
        owner=t.owner,
        resource=t.resource,
        page=t.page,
        quote=t.quote,
        quote_found=t.quote_found,
        origin=t.origin,
        review=t.review,
        suggested=t.suggested,
        status=t.status,
        note=t.note,
        status_by_name=t.status_by_name if names else None,
        status_at=t.status_at,
    )


async def view(session: AsyncSession, owner: Owner, cl: Checklist | None) -> s.ChecklistOut:
    available = owner.can_request and await reading_available(session)
    plans = [_plan_ref(d) for d in owner.plans]
    if cl is None:
        return s.ChecklistOut(
            id=None,
            state=None,
            error=None,
            plan=None,
            plans=plans,
            model=None,
            pages=None,
            pages_read=None,
            requested_by_name=None,
            requested_at=None,
            read_at=None,
            approved_by_name=None,
            approved_at=None,
            version=0,
            tasks=[],
            counts=s.Counts(),
            reading_available=available,
            can_review=False,
            can_follow=False,
        )
    tasks = await _tasks(session, cl.id)
    doc = await session.get(Document, cl.document_id)
    names = owner.show_names
    return s.ChecklistOut(
        id=str(cl.id),
        state=cl.state,
        error=cl.error,
        plan=_plan_ref(doc) if doc is not None else None,
        plans=plans,
        model=cl.model,
        pages=cl.pages,
        pages_read=cl.pages_read,
        requested_by_name=cl.requested_by_name if names else None,
        requested_at=cl.requested_at,
        read_at=cl.read_at,
        approved_by_name=cl.approved_by_name if names else None,
        approved_at=cl.approved_at,
        version=cl.version,
        tasks=[_task_out(t, names) for t in tasks],
        counts=counts(tasks),
        reading_available=available,
        can_review=owner.can_review and cl.state in ("review", "approved"),
        can_follow=owner.can_follow and cl.state == "approved",
    )


async def _record(
    session: AsyncSession, principal: Principal | None, owner: Owner, action: str, **details: object
) -> None:
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action=action,
        target=owner.target,
        details=dict(details),
        gouvernorats=owner.gouvernorats or None,
    )


async def request_reading(session: AsyncSession, principal: Principal, owner: Owner, body: s.ReadIn) -> Checklist:
    if not owner.can_request:
        raise _forbidden()
    if not (await ai_settings.load(session)).assist.plan_reading:
        raise _conflict("plan_reading_off")
    if get_llm() is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "assistant_unavailable")
    doc = next((d for d in owner.plans if d.id == body.document_id), None)
    if doc is None:
        raise ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, "plan_not_offered")
    at = now()
    cl = await find(session, owner, lock=True)
    if cl is None:
        cl = Checklist(axis_id=owner.axis_id, exercise_id=owner.exercise_id, version=1)
        session.add(cl)
    else:
        if body.version != cl.version:
            raise _conflict("version_conflict")
        if cl.state == "approved":
            # The list is being followed: what was done must not disappear. Tasks are added by hand instead.
            raise _conflict("checklist_approved")
        if cl.state == "reading":
            raise _conflict("reading_in_progress")
        await session.execute(delete(ChecklistTask).where(ChecklistTask.checklist_id == cl.id))
        cl.version += 1
    cl.document_id, cl.file_sha256 = doc.id, doc.file_sha256 or ""
    cl.state, cl.error, cl.attempts, cl.next_attempt_at, cl.lease_until = "queued", None, 0, at, None
    cl.model = cl.pages = cl.pages_read = cl.read_at = None
    cl.requested_by, cl.requested_by_name, cl.requested_at = audit.actor_of(principal), audit.name_of(principal), at
    cl.updated_at = at
    await session.flush()
    await _record(session, principal, owner, "checklist.read_requested", document=doc.number)
    return cl


async def _locked_task(session: AsyncSession, cl: Checklist, task_id: uuid.UUID) -> ChecklistTask:
    task = await session.scalar(
        select(ChecklistTask).where(ChecklistTask.id == task_id, ChecklistTask.checklist_id == cl.id).with_for_update()
    )
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task_not_found")
    return task


def _as_dict(t: ChecklistTask) -> dict[str, str | int | None]:
    return {"action": t.action, "owner": t.owner, "resource": t.resource, "page": t.page}


async def _reviewable(session: AsyncSession, owner: Owner, *, approved_too: bool = False) -> Checklist:
    if not owner.can_review:
        raise _forbidden()
    cl = await find(session, owner, lock=True)
    states = ("review", "approved") if approved_too else ("review",)
    if cl is None or cl.state not in states:
        raise _conflict("checklist_not_in_review")
    return cl


async def review(
    session: AsyncSession, principal: Principal, owner: Owner, task_id: uuid.UUID, body: s.ReviewIn
) -> Checklist:
    cl = await _reviewable(session, owner)
    task = await _locked_task(session, cl, task_id)
    before = _as_dict(task)
    if body.decision == "edit":
        if body.task is None:
            raise ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, "task_required")
        if task.origin == "ai" and task.suggested is None:
            task.suggested = before
        task.action, task.owner, task.resource, task.page = (
            body.task.action.strip(),
            body.task.owner.strip(),
            body.task.resource.strip(),
            body.task.page,
        )
        task.review = "edited" if task.origin == "ai" else "added"
    else:
        task.review = "deleted" if body.decision == "delete" else ("accepted" if task.origin == "ai" else "added")
    task.reviewed_by_name, task.reviewed_at = audit.name_of(principal), now()
    cl.version += 1
    cl.updated_at = now()
    await session.flush()
    await _record(
        session,
        principal,
        owner,
        "checklist.task_reviewed",
        task=str(task.id),
        decision=body.decision,
        before=before,
        after=_as_dict(task),
    )
    return cl


async def add(session: AsyncSession, principal: Principal, owner: Owner, body: s.TaskIn) -> Checklist:
    cl = await _reviewable(session, owner, approved_too=True)
    count, last = (
        await session.execute(
            select(func.count(), func.coalesce(func.max(ChecklistTask.position), 0)).where(
                ChecklistTask.checklist_id == cl.id
            )
        )
    ).one()
    if count >= MAX_TASKS:
        raise ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, "too_many_tasks", limit=MAX_TASKS)
    at = now()
    session.add(
        ChecklistTask(
            checklist_id=cl.id,
            position=last + 1,
            action=body.action.strip(),
            owner=body.owner.strip(),
            resource=body.resource.strip(),
            page=body.page,
            origin="manual",
            review="added",
            reviewed_by_name=audit.name_of(principal),
            reviewed_at=at,
            created_at=at,
        )
    )
    cl.version += 1
    cl.updated_at = at
    await session.flush()
    await _record(session, principal, owner, "checklist.task_added", task_action=body.action[:120])
    return cl


async def approve(session: AsyncSession, principal: Principal, owner: Owner, body: s.ApproveIn) -> Checklist:
    cl = await _reviewable(session, owner)
    if body.version != cl.version:
        raise _conflict("version_conflict")
    tally = counts(await _tasks(session, cl.id))
    if tally.suggested:
        raise ApiError(status.HTTP_409_CONFLICT, "tasks_not_reviewed", remaining=tally.suggested)
    if not tally.kept:
        raise ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, "checklist_empty")
    at = now()
    cl.state, cl.approved_by, cl.approved_by_name, cl.approved_at = (
        "approved",
        audit.actor_of(principal),
        audit.name_of(principal),
        at,
    )
    cl.version += 1
    cl.updated_at = at
    reviews = Tally(t.review for t in await _tasks(session, cl.id))
    await session.flush()
    await _record(session, principal, owner, "checklist.approved", reviews=dict(reviews), model=cl.model)
    return cl


async def follow(
    session: AsyncSession, principal: Principal, owner: Owner, task_id: uuid.UUID, body: s.FollowIn
) -> ChecklistTask:
    if not owner.can_follow:
        raise _forbidden()
    cl = await find(session, owner)
    if cl is None or cl.state != "approved":
        raise _conflict("checklist_not_approved")
    task = await _locked_task(session, cl, task_id)
    if task.review not in KEPT:
        raise _conflict("task_deleted")
    before = task.status
    task.status, task.note = body.status, body.note.strip()
    task.status_by_name, task.status_at = audit.name_of(principal), now()
    await session.flush()
    await _record(
        session, principal, owner, "checklist.task_status", task=str(task.id), before=before, after=body.status
    )
    return task


async def coverage(session: AsyncSession, *, exercise_id: uuid.UUID) -> s.Counts | None:
    """How far the approved list of a dry run was followed (its report)."""
    cl = await session.scalar(select(Checklist).where(Checklist.exercise_id == exercise_id))
    if cl is None or cl.state != "approved":
        return None
    return counts(await _tasks(session, cl.id))


# ---------------------------------------------------------------- the worker


@dataclass(frozen=True)
class _Claim:
    id: uuid.UUID
    version: int
    attempts: int
    document_id: uuid.UUID
    hazard: str


async def _hazard(session: AsyncSession, cl: Checklist) -> str:
    doc = await session.get(Document, cl.document_id)
    return (doc.hazard_key if doc is not None and doc.hazard_key else "") or "civil protection"


async def _claim(session: AsyncSession, only: uuid.UUID | None) -> _Claim | None:
    at = now()
    query = (
        select(Checklist)
        .where(
            or_(
                (Checklist.state == "queued") & (Checklist.next_attempt_at <= at),
                (Checklist.state == "reading") & (Checklist.lease_until < at),
            )
        )
        .order_by(Checklist.next_attempt_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if only is not None:
        query = query.where(Checklist.id == only)
    cl = await session.scalar(query)
    if cl is None:
        return None
    cl.state, cl.attempts, cl.lease_until, cl.updated_at = "reading", cl.attempts + 1, at + LEASE, at
    await session.flush()
    return _Claim(cl.id, cl.version, cl.attempts, cl.document_id, await _hazard(session, cl))


async def _current(session: AsyncSession, claim: _Claim) -> Checklist | None:
    cl = await session.scalar(select(Checklist).where(Checklist.id == claim.id).with_for_update())
    # A new reading was asked for meanwhile: this one is dropped.
    return cl if cl is not None and cl.version == claim.version and cl.state == "reading" else None


async def _fail(session: AsyncSession, claim: _Claim, code: str) -> None:
    cl = await _current(session, claim)
    if cl is not None:
        cl.state, cl.error, cl.lease_until, cl.updated_at = "failed", code, None, now()
        await audit.record(
            session,
            actor=audit.actor_of(None),
            action="checklist.read_failed",
            target=str(cl.id),
            details={"code": code},
        )


async def read_next(
    sessionmaker: async_sessionmaker[AsyncSession],
    llm: LlmClient | None,
    store: ObjectStore,
    *,
    only: uuid.UUID | None = None,
) -> bool:
    """Read one queued plan; False when there was nothing to do."""
    if llm is None:
        return False
    async with sessionmaker() as session, session.begin():
        if not (await ai_settings.load(session)).assist.plan_reading:
            return False
        claim = await _claim(session, only)
        if claim is None:
            return False
        doc = await session.get(Document, claim.document_id)
        key, size = (doc.file_key, doc.file_size) if doc is not None else (None, None)
    if not key or not size:
        async with sessionmaker() as session, session.begin():
            await _fail(session, claim, "plan_file_missing")
        return True
    try:
        text = await to_thread.run_sync(pdftext.extract, await store.head(key, size))
        result = await reader.read(llm, text.pages, claim.hazard)
    except pdftext.PlanUnreadable as exc:
        async with sessionmaker() as session, session.begin():
            await _fail(session, claim, exc.code)
        return True
    except LlmUnavailable as exc:
        log.warning("checklist.model_unavailable", error=str(exc), attempt=claim.attempts)
        async with sessionmaker() as session, session.begin():
            if claim.attempts >= MAX_ATTEMPTS:
                await _fail(session, claim, "model_unavailable")
            elif (cl := await _current(session, claim)) is not None:
                cl.state, cl.lease_until = "queued", None
                cl.next_attempt_at = now() + timedelta(minutes=min(2**claim.attempts, 60))
        return True
    if result.windows and result.rejected_windows == result.windows:
        async with sessionmaker() as session, session.begin():
            await _fail(session, claim, "model_output_invalid")
        return True
    async with sessionmaker() as session, session.begin():
        cl = await _current(session, claim)
        if cl is None:
            return True
        at = now()
        for position, task in enumerate(result.tasks, start=1):
            session.add(
                ChecklistTask(
                    checklist_id=cl.id,
                    position=position,
                    action=task.action,
                    owner=task.owner,
                    resource=task.resource,
                    page=task.page,
                    quote=task.quote,
                    quote_found=task.quote_found,
                    origin="ai",
                    review="suggested",
                    created_at=at,
                )
            )
        cl.state, cl.error, cl.lease_until, cl.read_at, cl.updated_at = "review", None, None, at, at
        cl.model, cl.pages, cl.pages_read = getattr(llm, "model", None), text.total_pages, result.pages_read
        cl.version += 1
        await audit.record(
            session,
            actor=audit.actor_of(None),
            action="checklist.read",
            target=str(cl.id),
            details={
                "model": cl.model,
                "tasks": len(result.tasks),
                "quotes_found": sum(t.quote_found for t in result.tasks),
                "pages": text.total_pages,
                "pages_read": result.pages_read,
                "windows_rejected": result.rejected_windows,
            },
        )
    log.info("checklist.read", checklist=str(claim.id), tasks=len(result.tasks))
    return True


async def checklist_forever(sessionmaker: async_sessionmaker[AsyncSession], idle_s: float = 15.0) -> None:
    while True:
        try:
            worked = await read_next(sessionmaker, get_llm(), get_store())
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("checklist.read_failed")
            worked = False
        if not worked:
            await asyncio.sleep(idle_s)
