"""The digital dry run (L5a, docs/phase-l/design-l5.md §2): plan, scenario, approval of each gouvernorat, run, stop,
answers with the real resources booked inside the dry run only, evaluation, report and load results.

Every route is dormant in the catalogue: nobody holds it until the system administrator grants it (Yamen
2026-10-28). The stop button is the exception: it cannot be hidden from a participating room during a run (§7).
Rows live in the ``drill`` schema, read and written through the system scope after the checks made here; nothing
becomes a report, an incident or an axis, so a dry run never reaches the statistics, the window or a citizen."""

import random
import statistics
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import ApiError, room_of
from app.core.db import as_system, get_session
from app.core.security import REALM_ROLES, Principal, Realm, require_roles
from app.modules.audit import service as audit
from app.modules.checklist import schemas as checklist_schemas
from app.modules.checklist import service as checklist
from app.modules.drill import schemas
from app.modules.drill.models import Booking, Evaluation, Exercise, Inject, Participant, Response, StressRun
from app.modules.features import service as features
from app.modules.ops.models import Resource, Unit
from app.modules.register import service as register
from app.modules.register.models import Document

router = APIRouter(prefix="/api/v1/staff/drills", tags=["drill"])

Session = Annotated[AsyncSession, Depends(get_session)]
AnyStaff = Annotated[Principal, Depends(require_roles(*REALM_ROLES[Realm.STAFF]))]
MAX_INJECTS = 400
MAX_ACTIVE_PER_ROOM = 3
FREE_LIMIT = 300
FEED_LIMIT = 500

# The generator's reports [SIM], by kind: what a citizen would write, with the resources such a report needs.
GENERATED: dict[str, tuple[tuple[str, ...], dict[str, int]]] = {
    "fire": (
        ("[SIM] دخان كثيف قرب الغابة", "[SIM] حريق في مستودع", "[SIM] نار في أرض فلاحية"),
        {"fire_engine": 1},
    ),
    "traffic_accident": (
        ("[SIM] حادث مرور بين سيارتين", "[SIM] انقلاب شاحنة على الطريق", "[SIM] اصطدام مع جرحى"),
        {"ambulance": 1},
    ),
    "flood": (
        ("[SIM] الماء دخل الديار", "[SIM] واد فاض على الطريق", "[SIM] عائلة محاصرة بالمياه"),
        {"boat": 1},
    ),
    "drowning": (("[SIM] شخص يغرق قرب الشاطئ", "[SIM] طفل مفقود في البحر"), {"ambulance": 1}),
    "medical": (("[SIM] شخص فاقد للوعي", "[SIM] ضيق تنفس حاد"), {"ambulance": 1}),
    "chemical_leak": (("[SIM] رائحة غاز قوية", "[SIM] تسرب مادة كيميائية"), {"fire_engine": 1}),
}


def _now() -> datetime:
    return datetime.now(UTC)


def _refuse(code: str, **extra: object) -> ApiError:
    return ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, code, **extra)


def _conflict(code: str) -> ApiError:
    return ApiError(status.HTTP_409_CONFLICT, code)


def _forbidden(code: str = "action_not_allowed") -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, code)


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "not_found")


# ---------------------------------------------------------------- who is who in a dry run


def _planner(principal: Principal, ex: Exercise) -> bool:
    return room_of(principal) == ex.room


def _participant_code(principal: Principal, ex: Exercise) -> int | None:
    code = principal.gouvernorat_code
    return code if code is not None and code in ex.gouvernorats else None


def _evaluator(principal: Principal, ex: Exercise) -> bool:
    # Independent: never from a participating gouvernorat (§7, question 2).
    return ex.evaluator == principal.subject and _participant_code(principal, ex) is None


def _sees(principal: Principal, ex: Exercise) -> bool:
    return (
        principal.is_national
        or _planner(principal, ex)
        or _participant_code(principal, ex) is not None
        or _evaluator(principal, ex)
    )


async def _granted(principal: Principal, key: str) -> bool:
    return await features.as_for(principal, key) is not None


def _settle(ex: Exercise, now: datetime) -> bool:
    """A run past its duration ends by itself; True when the state changed."""
    if (
        ex.status == "running"
        and ex.started_at is not None
        and now >= ex.started_at + timedelta(minutes=ex.duration_min)
    ):
        ex.status, ex.ended_at, ex.updated_at = "ended", ex.started_at + timedelta(minutes=ex.duration_min), now
        return True
    return False


async def _load(session: AsyncSession, principal: Principal, exercise_id: uuid.UUID) -> Exercise:
    ex = await session.get(Exercise, exercise_id)
    if ex is None or not _sees(principal, ex):
        raise _not_found()
    if _settle(ex, _now()):
        await _release_all(session, ex, ex.ended_at or _now())
    return ex


async def _participants(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, list[Participant]]:
    out: dict[uuid.UUID, list[Participant]] = defaultdict(list)
    if ids:
        rows = await session.scalars(
            select(Participant).where(Participant.exercise_id.in_(ids)).order_by(Participant.gouvernorat_code)
        )
        for p in rows:
            out[p.exercise_id].append(p)
    return out


async def _out(
    session: AsyncSession, principal: Principal, ex: Exercise, parts: list[Participant], injects: int
) -> schemas.ExerciseOut:
    planner = _planner(principal, ex)
    mine = _participant_code(principal, ex)
    running = ex.status == "running"
    return schemas.ExerciseOut(
        id=ex.id,
        title=ex.title,
        objective=ex.objective,
        hazard_key=ex.hazard_key,
        plan_document_id=ex.plan_document_id,
        gouvernorats=list(ex.gouvernorats),
        room=ex.room,
        planned_start=ex.planned_start,
        duration_min=ex.duration_min,
        evaluator=ex.evaluator,
        evaluator_name=ex.evaluator_name,
        status=ex.status,
        started_at=ex.started_at,
        ended_at=ex.ended_at,
        stop_reason=ex.stop_reason,
        stopped_by_name=ex.stopped_by_name,
        conclusion=ex.conclusion,
        created_by_name=ex.created_by_name,
        created_at=ex.created_at,
        participants=[
            schemas.ParticipantOut(
                gouvernorat_code=p.gouvernorat_code,
                decision=p.decision,
                reason=p.reason,
                decided_by_name=p.decided_by_name,
                decided_at=p.decided_at,
            )
            for p in parts
        ],
        injects=injects,
        can_edit=planner and ex.status == "draft" and await _granted(principal, "drill.scenario"),
        can_submit=planner and ex.status == "draft" and await _granted(principal, "drill.plan"),
        can_start=planner and ex.status == "ready" and await _granted(principal, "drill.start"),
        can_stop=running and (planner or mine is not None or principal.is_national),
        can_evaluate=_evaluator(principal, ex)
        and ex.status in {"running", "stopped", "ended"}
        and await _granted(principal, "drill.evaluate"),
        can_close=planner and ex.status in {"stopped", "ended"} and await _granted(principal, "drill.plan"),
        my_approval=mine
        if mine is not None
        and ex.status in {"submitted", "ready", "running"}
        and await _granted(principal, "drill.approve")
        else None,
    )


async def _one(session: AsyncSession, principal: Principal, ex: Exercise) -> schemas.ExerciseOut:
    parts = (await _participants(session, [ex.id]))[ex.id]
    count = await session.scalar(select(func.count()).select_from(Inject).where(Inject.exercise_id == ex.id))
    return await _out(session, principal, ex, parts, int(count or 0))


async def _audit(session: AsyncSession, principal: Principal, action: str, ex: Exercise, **details: Any) -> None:
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action=f"drill.{action}",
        target=f"drill:{ex.id}",
        details={"title": ex.title, **details},
        gouvernorats=list(ex.gouvernorats),
    )


# ---------------------------------------------------------------- planning


@router.get("", response_model=list[schemas.ExerciseOut])
async def list_exercises(principal: AnyStaff, session: Session) -> list[schemas.ExerciseOut]:
    async with as_system(session):
        query = select(Exercise).order_by(Exercise.planned_start.desc()).limit(200)
        if not principal.is_national:
            code = principal.gouvernorat_code
            query = query.where(
                (Exercise.room == room_of(principal))
                | Exercise.gouvernorats.any(code)  # type: ignore[arg-type]
                | (Exercise.evaluator == principal.subject)
            )
        rows = [ex for ex in await session.scalars(query) if _sees(principal, ex)]
        now = _now()
        for ex in rows:
            if _settle(ex, now):
                await _release_all(session, ex, ex.ended_at or now)
        parts = await _participants(session, [ex.id for ex in rows])
        counts = dict(
            (
                await session.execute(
                    select(Inject.exercise_id, func.count())
                    .where(Inject.exercise_id.in_([ex.id for ex in rows]))
                    .group_by(Inject.exercise_id)
                )
            ).all()
        )
        out = [await _out(session, principal, ex, parts[ex.id], int(counts.get(ex.id, 0))) for ex in rows]
        await session.commit()
    return out


@router.post("", response_model=schemas.ExerciseOut, status_code=status.HTTP_201_CREATED)
async def create_exercise(principal: AnyStaff, session: Session, body: schemas.ExerciseIn) -> schemas.ExerciseOut:
    # A regional room plans a dry run of its own gouvernorat; the central room one between gouvernorats (§7, 1).
    if not principal.is_national and body.gouvernorats != [principal.gouvernorat_code]:
        raise _forbidden("out_of_scope")
    now = _now()
    async with as_system(session):
        active = await session.scalar(
            select(func.count())
            .select_from(Exercise)
            .where(Exercise.room == room_of(principal), Exercise.status.in_(("submitted", "ready", "running")))
        )
        if int(active or 0) >= MAX_ACTIVE_PER_ROOM:
            raise _conflict("too_many_active")
        ex = Exercise(
            **body.model_dump(),
            room=room_of(principal),
            created_by=principal.subject,
            created_by_name=audit.name_of(principal),
            created_at=now,
            updated_at=now,
        )
        session.add(ex)
        await session.flush()
        for code in ex.gouvernorats:
            session.add(Participant(exercise_id=ex.id, gouvernorat_code=code))
        await _audit(session, principal, "create", ex)
        await session.flush()
        out = await _one(session, principal, ex)
        await session.commit()
    return out


@router.get("/{exercise_id}", response_model=schemas.ExerciseOut)
async def get_exercise(principal: AnyStaff, session: Session, exercise_id: uuid.UUID) -> schemas.ExerciseOut:
    async with as_system(session):
        ex = await _load(session, principal, exercise_id)
        out = await _one(session, principal, ex)
        await session.commit()
    return out


@router.put("/{exercise_id}", response_model=schemas.ExerciseOut)
async def edit_exercise(
    principal: AnyStaff, session: Session, exercise_id: uuid.UUID, body: schemas.ExerciseIn
) -> schemas.ExerciseOut:
    if not principal.is_national and body.gouvernorats != [principal.gouvernorat_code]:
        raise _forbidden("out_of_scope")
    async with as_system(session):
        ex = await _load(session, principal, exercise_id)
        _draft_of(principal, ex)
        for key, value in body.model_dump().items():
            setattr(ex, key, value)
        ex.updated_at = _now()
        await session.execute(
            delete(Participant).where(
                Participant.exercise_id == ex.id, Participant.gouvernorat_code.not_in(ex.gouvernorats)
            )
        )
        have = {p.gouvernorat_code for p in (await _participants(session, [ex.id]))[ex.id]}
        for code in set(ex.gouvernorats) - have:
            session.add(Participant(exercise_id=ex.id, gouvernorat_code=code))
        await session.execute(
            delete(Inject).where(
                Inject.exercise_id == ex.id,
                Inject.gouvernorat_code.is_not(None),
                Inject.gouvernorat_code.not_in(ex.gouvernorats),
            )
        )
        await _audit(session, principal, "edit", ex)
        await session.flush()
        out = await _one(session, principal, ex)
        await session.commit()
    return out


def _draft_of(principal: Principal, ex: Exercise) -> None:
    if not _planner(principal, ex):
        raise _forbidden()
    if ex.status != "draft":
        raise _conflict("not_a_draft")


# ---------------------------------------------------------------- the scenario


def _inject_out(i: Inject) -> schemas.InjectOut:
    return schemas.InjectOut(
        id=i.id,
        offset_min=i.offset_min,
        gouvernorat_code=i.gouvernorat_code,
        kind=i.kind,
        title=i.title,
        body=i.body,
        needs=i.needs,
        expected=i.expected,
        generated=i.generated,
    )


@router.get("/{exercise_id}/injects", response_model=list[schemas.InjectOut])
async def list_injects(principal: AnyStaff, session: Session, exercise_id: uuid.UUID) -> list[schemas.InjectOut]:
    """The whole scenario: for its planners and its evaluator, never for the rooms that play it."""
    async with as_system(session):
        ex = await _load(session, principal, exercise_id)
        if not (_planner(principal, ex) or _evaluator(principal, ex)):
            raise _forbidden()
        rows = await session.scalars(
            select(Inject).where(Inject.exercise_id == ex.id).order_by(Inject.offset_min, Inject.created_at)
        )
        return [_inject_out(i) for i in rows]


def _check_inject(ex: Exercise, body: schemas.InjectIn) -> None:
    if body.offset_min >= ex.duration_min:
        raise _refuse("offset_after_end")
    if body.gouvernorat_code is not None and body.gouvernorat_code not in ex.gouvernorats:
        raise _refuse("gouvernorat_not_in_drill")


@router.post("/{exercise_id}/injects", response_model=schemas.InjectOut, status_code=status.HTTP_201_CREATED)
async def add_inject(
    principal: AnyStaff, session: Session, exercise_id: uuid.UUID, body: schemas.InjectIn
) -> schemas.InjectOut:
    async with as_system(session):
        ex = await _load(session, principal, exercise_id)
        _draft_of(principal, ex)
        _check_inject(ex, body)
        count = await session.scalar(select(func.count()).select_from(Inject).where(Inject.exercise_id == ex.id))
        if int(count or 0) >= MAX_INJECTS:
            raise _refuse("too_many_injects")
        row = Inject(exercise_id=ex.id, **body.model_dump())
        session.add(row)
        await session.flush()
        out = _inject_out(row)
        await session.commit()
    return out


@router.put("/{exercise_id}/injects/{inject_id}", response_model=schemas.InjectOut)
async def edit_inject(
    principal: AnyStaff, session: Session, exercise_id: uuid.UUID, inject_id: uuid.UUID, body: schemas.InjectIn
) -> schemas.InjectOut:
    async with as_system(session):
        ex = await _load(session, principal, exercise_id)
        _draft_of(principal, ex)
        _check_inject(ex, body)
        row = await session.get(Inject, inject_id)
        if row is None or row.exercise_id != ex.id:
            raise _not_found()
        for key, value in body.model_dump().items():
            setattr(row, key, value)
        await session.flush()
        out = _inject_out(row)
        await session.commit()
    return out


@router.delete("/{exercise_id}/injects/{inject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_inject(principal: AnyStaff, session: Session, exercise_id: uuid.UUID, inject_id: uuid.UUID) -> None:
    async with as_system(session):
        ex = await _load(session, principal, exercise_id)
        _draft_of(principal, ex)
        row = await session.get(Inject, inject_id)
        if row is None or row.exercise_id != ex.id:
            raise _not_found()
        await session.delete(row)
        await session.commit()


@router.post("/{exercise_id}/generate", response_model=list[schemas.InjectOut], status_code=status.HTTP_201_CREATED)
async def generate(
    principal: AnyStaff, session: Session, exercise_id: uuid.UUID, body: schemas.GenerateIn
) -> list[schemas.InjectOut]:
    """Citizens' reports [SIM] spread over the run, in every gouvernorat of the dry run, the same for the same seed.

    The load the rooms face; the maximum load (thousands a minute) runs against the isolated copy only (§2.4)."""
    unknown = sorted(set(body.kinds) - set(GENERATED))
    if unknown:
        raise _refuse("unknown_kind", kinds=unknown)
    async with as_system(session):
        ex = await _load(session, principal, exercise_id)
        _draft_of(principal, ex)
        count = int(
            await session.scalar(select(func.count()).select_from(Inject).where(Inject.exercise_id == ex.id)) or 0
        )
        if count + body.count > MAX_INJECTS:
            raise _refuse("too_many_injects")
        rng = random.Random(body.seed)  # noqa: S311
        # More reports as the run goes on: a rising rhythm (the square root of a uniform draw leans late).
        offsets = sorted(int((rng.random() ** 0.5) * (ex.duration_min - 1)) for _ in range(body.count))
        rows: list[Inject] = []
        for offset in offsets:
            kind = rng.choice(body.kinds)
            titles, needs = GENERATED[kind]
            rows.append(
                Inject(
                    exercise_id=ex.id,
                    offset_min=offset,
                    gouvernorat_code=rng.choice(ex.gouvernorats),
                    kind="report",
                    title=rng.choice(titles),
                    body="",
                    needs=dict(needs),
                    expected="",
                    generated=True,
                )
            )
        session.add_all(rows)
        await _audit(session, principal, "generate", ex, count=body.count, seed=body.seed)
        await session.flush()
        out = [_inject_out(r) for r in rows]
        await session.commit()
    return out


# ---------------------------------------------------------------- approval of each gouvernorat


@router.post("/{exercise_id}/submit", response_model=schemas.ExerciseOut)
async def submit(principal: AnyStaff, session: Session, exercise_id: uuid.UUID) -> schemas.ExerciseOut:
    async with as_system(session):
        ex = await _load(session, principal, exercise_id)
        _draft_of(principal, ex)
        count = await session.scalar(select(func.count()).select_from(Inject).where(Inject.exercise_id == ex.id))
        if not count:
            raise _refuse("no_injects")
        if not ex.evaluator:
            raise _refuse("no_evaluator")
        ex.status, ex.updated_at = "submitted", _now()
        await session.execute(
            update(Participant)
            .where(Participant.exercise_id == ex.id)
            .values(decision="pending", reason=None, decided_by_name=None, decided_at=None)
        )
        await _audit(session, principal, "submit", ex, injects=int(count))
        await session.flush()
        out = await _one(session, principal, ex)
        await session.commit()
    return out


@router.post("/{exercise_id}/approvals", response_model=schemas.ExerciseOut)
async def decide(
    principal: AnyStaff, session: Session, exercise_id: uuid.UUID, body: schemas.ApprovalIn
) -> schemas.ExerciseOut:
    """The room of a participating gouvernorat approves, refuses or withdraws (before or during the run)."""
    if body.decision != "approved" and body.reason is None:
        raise _refuse("reason_required")
    now = _now()
    async with as_system(session):
        ex = await _load(session, principal, exercise_id)
        code = _participant_code(principal, ex)
        if code is None:
            raise _forbidden()
        allowed = {"submitted": {"approved", "refused", "withdrawn"}, "ready": {"refused", "withdrawn"}}
        if body.decision not in allowed.get(ex.status, {"withdrawn"} if ex.status == "running" else set()):
            raise _conflict("not_now")
        part = await session.get(Participant, (ex.id, code))
        assert part is not None
        if part.decision == "withdrawn":
            raise _conflict("already_withdrawn")
        part.decision, part.reason, part.decided_at = body.decision, body.reason, now
        part.decided_by_name = audit.name_of(principal)
        await session.flush()
        parts = (await _participants(session, [ex.id]))[ex.id]
        if ex.status in {"submitted", "ready"}:
            ex.status = "ready" if all(p.decision == "approved" for p in parts) else "submitted"
        elif ex.status == "running" and all(p.decision == "withdrawn" for p in parts):
            ex.status, ex.ended_at, ex.stop_reason = "stopped", now, "all_withdrawn"
            await _release_all(session, ex, now)
        elif ex.status == "running":
            await _release(session, ex, now, code)
        ex.updated_at = now
        await _audit(session, principal, body.decision, ex, gouvernorat=code, reason=body.reason)
        await session.flush()
        out = await _one(session, principal, ex)
        await session.commit()
    return out


# ---------------------------------------------------------------- the run


async def _available(session: AsyncSession, codes: list[int]) -> dict[str, dict[str, int]]:
    rows = await session.execute(
        select(Unit.gouvernorat_code, Resource.kind, func.count())
        .join(Unit, Unit.id == Resource.unit_id)
        .where(Unit.gouvernorat_code.in_(codes), Resource.status == "available")
        .group_by(Unit.gouvernorat_code, Resource.kind)
    )
    out: dict[str, dict[str, int]] = defaultdict(dict)
    for code, kind, count in rows.all():
        out[str(code)][kind] = int(count)
    return dict(out)


@router.post("/{exercise_id}/start", response_model=schemas.ExerciseOut)
async def start(principal: AnyStaff, session: Session, exercise_id: uuid.UUID) -> schemas.ExerciseOut:
    now = _now()
    async with as_system(session):
        ex = await _load(session, principal, exercise_id)
        if not _planner(principal, ex):
            raise _forbidden()
        if ex.status != "ready":
            raise _conflict("not_approved")
        ex.status, ex.started_at, ex.updated_at = "running", now, now
        ex.resources_at_start = await _available(session, list(ex.gouvernorats))
        await _audit(session, principal, "start", ex)
        await session.flush()
        out = await _one(session, principal, ex)
        await session.commit()
    return out


@router.post("/{exercise_id}/stop", response_model=schemas.ExerciseOut)
async def stop(
    principal: AnyStaff, session: Session, exercise_id: uuid.UUID, body: schemas.StopIn
) -> schemas.ExerciseOut:
    """Stop at once: the planner, the central room, or any participating room (a real incident comes first)."""
    now = _now()
    async with as_system(session):
        ex = await _load(session, principal, exercise_id)
        if not (_planner(principal, ex) or _participant_code(principal, ex) is not None or principal.is_national):
            raise _forbidden()
        if ex.status != "running":
            raise _conflict("not_running")
        ex.status, ex.ended_at, ex.updated_at = "stopped", now, now
        ex.stop_reason, ex.stopped_by_name = body.reason, audit.name_of(principal)
        await _release_all(session, ex, now)
        await _audit(session, principal, "stop", ex, reason=body.reason)
        await session.flush()
        out = await _one(session, principal, ex)
        await session.commit()
    return out


async def _release(session: AsyncSession, ex: Exercise, at: datetime, code: int) -> None:
    await session.execute(
        update(Booking)
        .where(Booking.exercise_id == ex.id, Booking.gouvernorat_code == code, Booking.released_at.is_(None))
        .values(released_at=at)
    )


async def _release_all(session: AsyncSession, ex: Exercise, at: datetime) -> None:
    await session.execute(
        update(Booking).where(Booking.exercise_id == ex.id, Booking.released_at.is_(None)).values(released_at=at)
    )


def _elapsed(ex: Exercise, now: datetime) -> int:
    if ex.started_at is None:
        return 0
    end = ex.ended_at or now
    return max(0, int((min(now, end) - ex.started_at).total_seconds() // 60))


async def _responses(session: AsyncSession, inject_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[schemas.ResponseOut]]:
    out: dict[uuid.UUID, list[schemas.ResponseOut]] = defaultdict(list)
    if not inject_ids:
        return out
    rows = list(
        await session.scalars(
            select(Response).where(Response.inject_id.in_(inject_ids)).order_by(Response.responded_at)
        )
    )
    bookings: dict[uuid.UUID, list[schemas.BookingOut]] = defaultdict(list)
    if rows:
        for b, label in (
            await session.execute(
                select(Booking, Resource.label)
                .join(Resource, Resource.id == Booking.resource_id)
                .where(Booking.response_id.in_([r.id for r in rows]))
            )
        ).all():
            bookings[b.response_id].append(
                schemas.BookingOut(
                    resource_id=b.resource_id, label=label, kind=b.kind, released=b.released_at is not None
                )
            )
    for r in rows:
        out[r.inject_id].append(
            schemas.ResponseOut(
                id=r.id,
                gouvernorat_code=r.gouvernorat_code,
                action=r.action,
                text=r.text,
                responded_by_name=r.responded_by_name,
                responded_at=r.responded_at,
                bookings=bookings[r.id],
            )
        )
    return out


async def _free(session: AsyncSession, ex: Exercise, code: int) -> list[schemas.FreeResource]:
    """Real resources of a gouvernorat available now and not booked in this dry run (the room picks among them)."""
    booked = select(Booking.resource_id).where(Booking.exercise_id == ex.id, Booking.released_at.is_(None))
    rows = await session.execute(
        select(Resource.id, Resource.kind, Resource.label, Unit.name_ar)
        .join(Unit, Unit.id == Resource.unit_id)
        .where(Unit.gouvernorat_code == code, Resource.status == "available", Resource.id.not_in(booked))
        .order_by(Resource.kind, Unit.name_ar, Resource.label)
        .limit(FREE_LIMIT)
    )
    return [schemas.FreeResource(id=i, kind=k, label=label, unit=unit) for i, k, label, unit in rows.all()]


@router.get("/{exercise_id}/feed", response_model=schemas.FeedOut)
async def feed(principal: AnyStaff, session: Session, exercise_id: uuid.UUID) -> schemas.FeedOut:
    """The injects due by now, for a participating room (its gouvernorat), the central room or the evaluator."""
    now = _now()
    async with as_system(session):
        ex = await _load(session, principal, exercise_id)
        if ex.status not in {"running", "stopped", "ended", "closed"}:
            raise _conflict("not_started")
        code = _participant_code(principal, ex)
        if code is None and not (principal.is_national or _evaluator(principal, ex) or _planner(principal, ex)):
            raise _forbidden()
        elapsed = _elapsed(ex, now)
        query = (
            select(Inject)
            .where(Inject.exercise_id == ex.id, Inject.offset_min <= elapsed)
            .order_by(Inject.offset_min.desc(), Inject.created_at.desc())
            .limit(FEED_LIMIT)
        )
        if code is not None and not principal.is_national:
            query = query.where((Inject.gouvernorat_code == code) | Inject.gouvernorat_code.is_(None))
        injects = list(await session.scalars(query))
        answers = await _responses(session, [i.id for i in injects])
        free = await _free(session, ex, code) if code is not None and ex.status == "running" else []
        assert ex.started_at is not None
        out = schemas.FeedOut(
            exercise_id=ex.id,
            status=ex.status,
            elapsed_min=elapsed,
            remaining_min=max(0, ex.duration_min - elapsed) if ex.status == "running" else 0,
            items=[
                schemas.FeedItem(
                    inject=_inject_out(i),
                    due_at=ex.started_at + timedelta(minutes=i.offset_min),
                    responses=answers[i.id],
                )
                for i in injects
            ],
            free_resources=free,
            free={k: sum(1 for r in free if r.kind == k) for k in sorted({r.kind for r in free})},
        )
        await session.commit()
    return out


@router.post(
    "/{exercise_id}/injects/{inject_id}/responses",
    response_model=schemas.ResponseOut,
    status_code=status.HTTP_201_CREATED,
)
async def respond(
    principal: AnyStaff, session: Session, exercise_id: uuid.UUID, inject_id: uuid.UUID, body: schemas.ResponseIn
) -> schemas.ResponseOut:
    """A participating room answers a due inject, booking real resources of its gouvernorat inside the dry run."""
    now = _now()
    async with as_system(session):
        ex = await _load(session, principal, exercise_id)
        code = _participant_code(principal, ex)
        if code is None:
            raise _forbidden()
        if ex.status != "running":
            raise _conflict("not_running")
        part = await session.get(Participant, (ex.id, code))
        if part is None or part.decision != "approved":
            raise _conflict("not_participating")
        inject = await session.get(Inject, inject_id)
        if (
            inject is None
            or inject.exercise_id != ex.id
            or inject.offset_min > _elapsed(ex, now)
            or inject.gouvernorat_code not in (None, code)
        ):
            raise _not_found()
        if body.resource_ids and body.action != "dispatched":
            raise _refuse("resources_need_dispatch")
        resources: list[Resource] = []
        if body.resource_ids:
            booked = select(Booking.resource_id).where(Booking.exercise_id == ex.id, Booking.released_at.is_(None))
            resources = list(
                await session.scalars(
                    select(Resource)
                    .join(Unit, Unit.id == Resource.unit_id)
                    .where(
                        Resource.id.in_(body.resource_ids),
                        Unit.gouvernorat_code == code,
                        Resource.status == "available",
                        Resource.id.not_in(booked),
                    )
                )
            )
            if len(resources) != len(set(body.resource_ids)):
                raise _conflict("resource_not_free")
        row = Response(
            inject_id=inject.id,
            gouvernorat_code=code,
            action=body.action,
            text=body.text,
            responded_by=principal.subject,
            responded_by_name=audit.name_of(principal),
            responded_at=now,
        )
        session.add(row)
        await session.flush()
        for r in resources:
            session.add(
                Booking(
                    exercise_id=ex.id,
                    resource_id=r.id,
                    response_id=row.id,
                    kind=r.kind,
                    gouvernorat_code=code,
                    booked_at=now,
                )
            )
        await session.flush()
        out = (await _responses(session, [inject.id]))[inject.id][-1]
        await session.commit()
    return out


@router.post("/{exercise_id}/responses/{response_id}/release", status_code=status.HTTP_204_NO_CONTENT)
async def release(principal: AnyStaff, session: Session, exercise_id: uuid.UUID, response_id: uuid.UUID) -> None:
    """The resources of an answer are back (the intervention of the scenario is over)."""
    async with as_system(session):
        ex = await _load(session, principal, exercise_id)
        code = _participant_code(principal, ex)
        row = await session.get(Response, response_id)
        if code is None or row is None or row.gouvernorat_code != code:
            raise _not_found()
        await session.execute(
            update(Booking)
            .where(Booking.response_id == row.id, Booking.released_at.is_(None))
            .values(released_at=_now())
        )
        await session.commit()


# ---------------------------------------------------------------- the task list read from the plan (AI2)

CHECKLIST_EDITABLE = {"draft", "submitted", "ready"}


async def _checklist_owner(session: AsyncSession, principal: Principal, ex: Exercise) -> checklist.Owner:
    """Inside ``as_system``: the plan is checked against the caller's own scope and access level here."""
    planner = _planner(principal, ex) and ex.status in CHECKLIST_EDITABLE
    code = _participant_code(principal, ex)
    following = False
    if code is not None and ex.status == "running":
        part = await session.get(Participant, (ex.id, code))
        following = part is not None and part.decision == "approved"
    docs: list[Document] = []
    if ex.plan_document_id is not None:
        doc = await session.get(Document, ex.plan_document_id)
        in_scope = doc is not None and (
            principal.is_national or doc.gouvernorat_code in (None, principal.gouvernorat_code)
        )
        if doc is not None and in_scope and register.readable(principal, doc):
            docs.append(doc)
    return checklist.Owner(
        axis_id=None,
        exercise_id=ex.id,
        hazard=ex.hazard_key or "",
        plans=checklist.offered(docs),
        can_request=planner,
        can_review=planner,
        can_follow=following,
        show_names=True,
        gouvernorats=list(ex.gouvernorats),
    )


async def _checklist(
    session: AsyncSession, principal: Principal, exercise_id: uuid.UUID
) -> tuple[Exercise, checklist.Owner]:
    ex = await _load(session, principal, exercise_id)
    return ex, await _checklist_owner(session, principal, ex)


async def _checklist_out(session: AsyncSession, owner: checklist.Owner) -> checklist_schemas.ChecklistOut:
    return await checklist.view(session, owner, await checklist.find(session, owner))


@router.get("/{exercise_id}/checklist", response_model=checklist_schemas.ChecklistOut)
async def get_checklist(
    principal: AnyStaff, session: Session, exercise_id: uuid.UUID
) -> checklist_schemas.ChecklistOut:
    """The plan's tasks: the expected answer the rooms follow during the run and the evaluator compares with."""
    async with as_system(session):
        _, owner = await _checklist(session, principal, exercise_id)
        return await _checklist_out(session, owner)


@router.post("/{exercise_id}/checklist/read", response_model=checklist_schemas.ChecklistOut, status_code=202)
async def read_checklist(
    principal: AnyStaff, session: Session, exercise_id: uuid.UUID, body: checklist_schemas.ReadIn
) -> checklist_schemas.ChecklistOut:
    async with as_system(session):
        _, owner = await _checklist(session, principal, exercise_id)
        await checklist.request_reading(session, principal, owner, body)
        out = await _checklist_out(session, owner)
        await session.commit()
    return out


@router.post("/{exercise_id}/checklist/tasks", response_model=checklist_schemas.ChecklistOut, status_code=201)
async def add_checklist_task(
    principal: AnyStaff, session: Session, exercise_id: uuid.UUID, body: checklist_schemas.TaskIn
) -> checklist_schemas.ChecklistOut:
    async with as_system(session):
        _, owner = await _checklist(session, principal, exercise_id)
        await checklist.add(session, principal, owner, body)
        out = await _checklist_out(session, owner)
        await session.commit()
    return out


@router.post("/{exercise_id}/checklist/tasks/{task_id}/review", response_model=checklist_schemas.ChecklistOut)
async def review_checklist_task(
    principal: AnyStaff,
    session: Session,
    exercise_id: uuid.UUID,
    task_id: uuid.UUID,
    body: checklist_schemas.ReviewIn,
) -> checklist_schemas.ChecklistOut:
    async with as_system(session):
        _, owner = await _checklist(session, principal, exercise_id)
        await checklist.review(session, principal, owner, task_id, body)
        out = await _checklist_out(session, owner)
        await session.commit()
    return out


@router.post("/{exercise_id}/checklist/approve", response_model=checklist_schemas.ChecklistOut)
async def approve_checklist(
    principal: AnyStaff, session: Session, exercise_id: uuid.UUID, body: checklist_schemas.ApproveIn
) -> checklist_schemas.ChecklistOut:
    async with as_system(session):
        _, owner = await _checklist(session, principal, exercise_id)
        await checklist.approve(session, principal, owner, body)
        out = await _checklist_out(session, owner)
        await session.commit()
    return out


@router.post("/{exercise_id}/checklist/tasks/{task_id}/status", response_model=checklist_schemas.ChecklistOut)
async def follow_checklist_task(
    principal: AnyStaff,
    session: Session,
    exercise_id: uuid.UUID,
    task_id: uuid.UUID,
    body: checklist_schemas.FollowIn,
) -> checklist_schemas.ChecklistOut:
    async with as_system(session):
        _, owner = await _checklist(session, principal, exercise_id)
        await checklist.follow(session, principal, owner, task_id, body)
        out = await _checklist_out(session, owner)
        await session.commit()
    return out


# ---------------------------------------------------------------- evaluation, closing, load results


@router.put("/{exercise_id}/injects/{inject_id}/evaluation", response_model=schemas.EvaluationOut)
async def evaluate(
    principal: AnyStaff, session: Session, exercise_id: uuid.UUID, inject_id: uuid.UUID, body: schemas.EvaluationIn
) -> schemas.EvaluationOut:
    async with as_system(session):
        ex = await _load(session, principal, exercise_id)
        if not _evaluator(principal, ex):
            raise _forbidden("not_the_evaluator")
        if ex.status not in {"running", "stopped", "ended"}:
            raise _conflict("not_now")
        inject = await session.get(Inject, inject_id)
        if inject is None or inject.exercise_id != ex.id:
            raise _not_found()
        row = await session.get(Evaluation, inject.id) or Evaluation(inject_id=inject.id)
        row.plan_followed, row.score, row.notes = body.plan_followed, body.score, body.notes
        row.evaluated_by_name, row.evaluated_at = audit.name_of(principal), _now()
        session.add(row)
        await _audit(session, principal, "evaluate", ex, inject=str(inject.id), score=body.score)
        await session.flush()
        out = schemas.EvaluationOut(
            plan_followed=row.plan_followed,
            score=row.score,
            notes=row.notes,
            evaluated_by_name=row.evaluated_by_name,
            evaluated_at=row.evaluated_at,
        )
        await session.commit()
    return out


@router.post("/{exercise_id}/close", response_model=schemas.ExerciseOut)
async def close(
    principal: AnyStaff, session: Session, exercise_id: uuid.UUID, body: schemas.CloseIn
) -> schemas.ExerciseOut:
    async with as_system(session):
        ex = await _load(session, principal, exercise_id)
        if not _planner(principal, ex):
            raise _forbidden()
        if ex.status not in {"stopped", "ended"}:
            raise _conflict("not_over")
        ex.status, ex.conclusion, ex.updated_at = "closed", body.conclusion, _now()
        await _audit(session, principal, "close", ex)
        await session.flush()
        out = await _one(session, principal, ex)
        await session.commit()
    return out


@router.post("/{exercise_id}/stress", response_model=schemas.StressIn, status_code=status.HTTP_201_CREATED)
async def record_stress(
    principal: AnyStaff, session: Session, exercise_id: uuid.UUID, body: schemas.StressIn
) -> schemas.StressIn:
    """The results of a load run made on the isolated copy (infra/loadtest/drill.js), kept with the dry run."""
    if body.reports_accepted + body.reports_refused > body.reports_sent or body.attacks_blocked > body.attacks_sent:
        raise _refuse("inconsistent_results")
    async with as_system(session):
        ex = await _load(session, principal, exercise_id)
        if not _planner(principal, ex):
            raise _forbidden()
        if ex.status == "draft":
            raise _conflict("not_submitted")
        session.add(
            StressRun(
                exercise_id=ex.id,
                environment=body.environment,
                results=body.model_dump(),
                recorded_by_name=audit.name_of(principal),
            )
        )
        await _audit(session, principal, "stress", ex, sent=body.reports_sent, attacks=body.attacks_sent)
        await session.commit()
    return body


def _peaks(bookings: list[Booking], until: datetime) -> dict[tuple[int, str], int]:
    """The most resources of each kind booked at the same time, per gouvernorat."""
    events: dict[tuple[int, str], list[tuple[datetime, int]]] = defaultdict(list)
    for b in bookings:
        key = (b.gouvernorat_code, b.kind)
        events[key].append((b.booked_at, 1))
        events[key].append((b.released_at or until, -1))
    out: dict[tuple[int, str], int] = {}
    for key, evs in events.items():
        current = peak = 0
        for _, step in sorted(evs, key=lambda e: (e[0], e[1])):
            current += step
            peak = max(peak, current)
        out[key] = peak
    return out


@router.get("/{exercise_id}/report", response_model=schemas.ReportOut)
async def report(principal: AnyStaff, session: Session, exercise_id: uuid.UUID) -> schemas.ReportOut:
    async with as_system(session):
        ex = await _load(session, principal, exercise_id)
        if ex.status in {"draft", "submitted", "ready"}:
            raise _conflict("not_started")
        exercise = await _one(session, principal, ex)
        injects = list(
            await session.scalars(
                select(Inject).where(Inject.exercise_id == ex.id).order_by(Inject.offset_min, Inject.created_at)
            )
        )
        responses = list(
            await session.scalars(
                select(Response).where(Response.inject_id.in_([i.id for i in injects])).order_by(Response.responded_at)
            )
        )
        bookings = list(await session.scalars(select(Booking).where(Booking.exercise_id == ex.id)))
        evaluations = {
            e.inject_id: e
            for e in await session.scalars(select(Evaluation).where(Evaluation.inject_id.in_([i.id for i in injects])))
        }
        stress = [
            schemas.StressIn.model_validate(s.results)
            for s in await session.scalars(
                select(StressRun).where(StressRun.exercise_id == ex.id).order_by(StressRun.recorded_at)
            )
        ]
        plan_tasks = await checklist.coverage(session, exercise_id=ex.id)
        await session.commit()

    assert ex.started_at is not None
    end = ex.ended_at or _now()
    first: dict[uuid.UUID, datetime] = {}
    for r in responses:
        first.setdefault(r.inject_id, r.responded_at)
    by_response = {r.id: r.inject_id for r in responses}
    booked: dict[uuid.UUID, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for b in bookings:
        booked[by_response[b.response_id]][b.kind] += 1

    lines: list[schemas.InjectReport] = []
    delays: list[float] = []
    played = _elapsed(ex, end)
    for i in injects:
        if i.offset_min > played:
            continue
        due = ex.started_at + timedelta(minutes=i.offset_min)
        answered = i.id in first
        delay = round((first[i.id] - due).total_seconds() / 60, 1) if answered else None
        if delay is not None:
            delays.append(delay)
        got = dict(booked[i.id])
        ev = evaluations.get(i.id)
        lines.append(
            schemas.InjectReport(
                inject=_inject_out(i),
                due_at=due,
                answered=answered,
                first_answer_min=delay,
                booked=got,
                shortfall={k: n - got.get(k, 0) for k, n in i.needs.items() if n > got.get(k, 0)},
                evaluation=schemas.EvaluationOut(
                    plan_followed=ev.plan_followed,
                    score=ev.score,
                    notes=ev.notes,
                    evaluated_by_name=ev.evaluated_by_name,
                    evaluated_at=ev.evaluated_at,
                )
                if ev
                else None,
            )
        )

    peaks = _peaks(bookings, end)
    short: dict[tuple[int, str], int] = defaultdict(int)
    for line in lines:
        code = line.inject.gouvernorat_code
        for kind, n in line.shortfall.items():
            if code is not None:
                short[(code, kind)] += n
    keys = {(int(c), k) for c, kinds in ex.resources_at_start.items() for k in kinds} | set(peaks) | set(short)
    resources = [
        schemas.ResourceLine(
            gouvernorat_code=code,
            kind=kind,
            available_at_start=int(ex.resources_at_start.get(str(code), {}).get(kind, 0)),
            peak_booked=peaks.get((code, kind), 0),
            short=short.get((code, kind), 0),
        )
        for code, kind in sorted(keys)
    ]
    marks = [line.evaluation for line in lines if line.evaluation is not None]
    followed: dict[str, int] = defaultdict(int)
    for m in marks:
        followed[m.plan_followed] += 1
    return schemas.ReportOut(
        exercise=exercise,
        injects=lines,
        answered=sum(1 for line in lines if line.answered),
        unanswered=sum(1 for line in lines if not line.answered),
        median_answer_min=round(statistics.median(delays), 1) if delays else None,
        plan_followed=dict(followed),
        mean_score=round(statistics.mean(m.score for m in marks), 2) if marks else None,
        resources=resources,
        stress=stress,
        plan_tasks=plan_tasks,
    )
