"""Personnel management endpoints, phase H1 (docs/phase-h/design-h.md).

The personnel department (``personnel_officer``) of a gouvernorat keeps the administrative file of its staff: identity,
category (intervention, room, administrative), rank, function, unit, transfers, sanctions, rewards, leave and
absences. The central department does the same for every gouvernorat and alone transfers a member of staff to another
gouvernorat. Row level security (migration 0096) holds the same rule in the database.

The operations rooms (``operator``, ``ops_manager``) read the staff with their rank, function and the kind and dates of
their absence of the day ("on leave", "on a mission"), and the general strength. They never see the file's events
(sanctions, rewards), the references or the notes, and they record nothing here.
"""

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.db import get_session, get_system_sessionmaker
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.inventory.models import Agent
from app.modules.ops.models import Unit
from app.modules.personnel import schemas
from app.modules.personnel.models import Absence, Event

router = APIRouter(prefix="/api/v1/staff/personnel", tags=["staff", "personnel"])
Session = Annotated[AsyncSession, Depends(get_session)]
OFFICER = Role.PERSONNEL_OFFICER
ROOM_ROLES = frozenset({Role.OPERATOR, Role.OPS_MANAGER})
Reader = Annotated[Principal, Depends(require_roles(OFFICER, *ROOM_ROLES))]
Officer = Annotated[Principal, Depends(require_roles(OFFICER))]
# The events that change the current rank, function or unit; cancelling the latest one puts the previous value back.
STATE_KINDS = frozenset({"rank", "appointment", "transfer"})
MAX_RANGE_DAYS = 400


def _now() -> datetime:
    return datetime.now(UTC)


def _today() -> date:
    return _now().date()


def is_officer(principal: Principal) -> bool:
    return OFFICER in principal.roles


def _scope(principal: Principal, column: Any) -> Any:
    return True if principal.is_national else column == principal.gouvernorat_code


def _require_scope(principal: Principal, gouvernorat: int) -> None:
    if not principal.can_access_gouvernorat(gouvernorat):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


async def _audit(
    session: AsyncSession, principal: Principal, action: str, target: str, gouvernorats: list[int], **details: Any
) -> None:
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action=f"personnel.{action}",
        target=target,
        details=details,
        gouvernorats=gouvernorats,
    )


# ---------------------------------------------------------------- staff


async def _unit(session: AsyncSession, unit_id: uuid.UUID) -> Unit:
    found = await session.get(Unit, unit_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unit_not_found")
    return found


async def _any_unit(unit_id: uuid.UUID) -> Unit:
    """A unit of any gouvernorat (a transfer may name one the caller cannot see): read with the system scope, so a
    regional department is told the transfer is the central department's rather than that the unit does not exist.
    Units are not personal data."""
    async with get_system_sessionmaker()() as system:
        found = await system.get(Unit, unit_id)
        if found is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "unit_not_found")
        system.expunge(found)
        return found


async def _agent(session: AsyncSession, agent_id: uuid.UUID, *, lock: bool = False) -> tuple[Agent, Unit]:
    query = select(Agent, Unit).join(Unit, Unit.id == Agent.unit_id).where(Agent.id == agent_id)
    if lock:
        query = query.with_for_update(of=Agent)
    row = (await session.execute(query)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "agent_not_found")
    return row[0], row[1]


async def _matricule_taken(matricule: str, own: uuid.UUID | None) -> bool:
    """A matricule is unique in the whole country; a regional department cannot see the others, so the check runs
    with the system scope and returns a yes or no only."""
    async with get_system_sessionmaker()() as system:
        query = select(Agent.id).where(Agent.matricule == matricule)
        if own is not None:
            query = query.where(Agent.id != own)
        return (await system.scalar(query.limit(1))) is not None


def _brief(a: Absence | None) -> schemas.AbsenceBrief | None:
    if a is None:
        return None
    return schemas.AbsenceBrief(id=a.id, kind=a.kind, starts_on=a.starts_on, ends_on=a.ends_on)


def _row(a: Agent, unit: Unit, absence: Absence | None, officer: bool) -> schemas.AgentRow:
    return schemas.AgentRow(
        id=a.id,
        matricule=a.matricule,
        full_name=a.full_name,
        rank=a.rank,
        post=a.post,
        category=a.category,
        unit_id=unit.id,
        unit_name=unit.name_ar,
        gouvernorat_code=a.gouvernorat_code,
        phone=a.phone if officer else None,
        absence=_brief(absence),
        version=a.version,
    )


async def _absences_on(session: AsyncSession, ids: list[uuid.UUID], day: date) -> dict[uuid.UUID, Absence]:
    out: dict[uuid.UUID, Absence] = {}
    if ids:
        rows = await session.scalars(
            select(Absence)
            .where(
                Absence.agent_id.in_(ids),
                Absence.cancelled_at.is_(None),
                Absence.starts_on <= day,
                Absence.ends_on >= day,
            )
            .order_by(Absence.starts_on)
        )
        for a in rows.all():
            out.setdefault(a.agent_id, a)
    return out


@router.get("/units", response_model=list[schemas.UnitOut])
async def list_units(
    principal: Reader, session: Session, gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None
) -> list[schemas.UnitOut]:
    """The units a department or a room may choose from (theirs; the central ones: every gouvernorat)."""
    query = select(Unit).where(_scope(principal, Unit.gouvernorat_code))
    if gouvernorat is not None:
        query = query.where(Unit.gouvernorat_code == gouvernorat)
    units = (await session.scalars(query.order_by(Unit.gouvernorat_code, Unit.name_ar))).all()
    return [schemas.UnitOut(id=u.id, name=u.name_ar, gouvernorat_code=u.gouvernorat_code) for u in units]


@router.get("/agents", response_model=schemas.AgentsOut)
async def list_agents(
    principal: Reader,
    session: Session,
    on: Annotated[date | None, Query()] = None,
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
    unit_id: Annotated[uuid.UUID | None, Query()] = None,
    category: Annotated[schemas.Category | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=60)] = None,
) -> schemas.AgentsOut:
    day = on or _today()
    query = select(Agent, Unit).join(Unit, Unit.id == Agent.unit_id).where(_scope(principal, Agent.gouvernorat_code))
    if gouvernorat is not None:
        query = query.where(Agent.gouvernorat_code == gouvernorat)
    if unit_id is not None:
        query = query.where(Agent.unit_id == unit_id)
    if category is not None:
        query = query.where(Agent.category == category)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.where(or_(Agent.full_name.ilike(like), Agent.matricule.ilike(like)))
    rows = (await session.execute(query.order_by(Agent.gouvernorat_code, Unit.name_ar, Agent.full_name))).all()
    absences = await _absences_on(session, [a.id for a, _ in rows], day)
    officer = is_officer(principal)
    return schemas.AgentsOut(on=day, items=[_row(a, u, absences.get(a.id), officer) for a, u in rows], can_edit=officer)


@router.post("/agents", response_model=schemas.AgentRow, status_code=status.HTTP_201_CREATED)
async def create_agent(principal: Officer, session: Session, body: schemas.AgentIn) -> schemas.AgentRow:
    unit = await _unit(session, body.unit_id)
    _require_scope(principal, unit.gouvernorat_code)
    matricule = body.matricule.strip()
    if await _matricule_taken(matricule, None):
        raise HTTPException(status.HTTP_409_CONFLICT, "matricule_taken")
    agent = Agent(
        unit_id=unit.id,
        gouvernorat_code=unit.gouvernorat_code,
        matricule=matricule,
        full_name=body.full_name.strip(),
        rank=_clean(body.rank),
        post=_clean(body.post),
        category=body.category,
        phone=_clean(body.phone),
        updated_by=audit.actor_of(principal),
    )
    session.add(agent)
    await session.flush()
    await session.refresh(agent)
    await _audit(session, principal, "agent.create", f"agent:{agent.id}", [unit.gouvernorat_code])
    out = _row(agent, unit, None, True)
    await session.commit()
    return out


@router.patch("/agents/{agent_id}", response_model=schemas.AgentRow)
async def update_agent(
    principal: Officer, session: Session, agent_id: uuid.UUID, body: schemas.AgentEdit
) -> schemas.AgentRow:
    agent, unit = await _agent(session, agent_id, lock=True)
    _require_scope(principal, agent.gouvernorat_code)
    if body.version != agent.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
    matricule = body.matricule.strip()
    if matricule != agent.matricule and await _matricule_taken(matricule, agent.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "matricule_taken")
    changed = [
        f
        for f, new in (
            ("matricule", matricule),
            ("full_name", body.full_name.strip()),
            ("category", body.category),
            ("phone", _clean(body.phone)),
        )
        if getattr(agent, f) != new
    ]
    agent.matricule, agent.full_name = matricule, body.full_name.strip()
    agent.category, agent.phone = body.category, _clean(body.phone)
    _touch(agent, principal)
    await session.flush()
    await _audit(session, principal, "agent.update", f"agent:{agent.id}", [agent.gouvernorat_code], fields=changed)
    out = _row(agent, unit, (await _absences_on(session, [agent.id], _today())).get(agent.id), True)
    await session.commit()
    return out


def _touch(agent: Agent, principal: Principal) -> None:
    agent.version += 1
    agent.updated_at = _now()
    agent.updated_by = audit.actor_of(principal)


# ---------------------------------------------------------------- the administrative file


def _event_out(e: Event, units: dict[uuid.UUID, str]) -> schemas.EventOut:
    return schemas.EventOut(
        id=e.id,
        kind=e.kind,
        effective_on=e.effective_on,
        title=e.title,
        unit_id=e.unit_id,
        unit_name=units.get(e.unit_id) if e.unit_id else None,
        from_unit_id=e.from_unit_id,
        from_unit_name=units.get(e.from_unit_id) if e.from_unit_id else None,
        reference=e.reference,
        note=e.note,
        created_by_name=e.created_by_name,
        created_at=e.created_at,
        cancelled_at=e.cancelled_at,
        cancelled_by_name=e.cancelled_by_name,
        cancel_reason=e.cancel_reason,
    )


async def _unit_names(session: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    # Unit names are not personal data; a transfer may name a unit of another gouvernorat.
    async with get_system_sessionmaker()() as system:
        rows = await system.execute(select(Unit.id, Unit.name_ar).where(Unit.id.in_(ids)))
        return {i: n for i, n in rows.all()}


@router.get("/agents/{agent_id}", response_model=schemas.AgentFile)
async def agent_file(principal: Officer, session: Session, agent_id: uuid.UUID) -> schemas.AgentFile:
    agent, unit = await _agent(session, agent_id)
    _require_scope(principal, agent.gouvernorat_code)
    events = list(
        (
            await session.scalars(
                select(Event)
                .where(Event.agent_id == agent.id)
                .order_by(Event.effective_on.desc(), Event.created_at.desc())
            )
        ).all()
    )
    absences = list(
        (
            await session.scalars(
                select(Absence).where(Absence.agent_id == agent.id).order_by(Absence.starts_on.desc())
            )
        ).all()
    )
    units = await _unit_names(session, {u for e in events for u in (e.unit_id, e.from_unit_id) if u})
    today = _today()
    current = next((a for a in absences if a.cancelled_at is None and a.starts_on <= today <= a.ends_on), None)
    await _audit(session, principal, "file.view", f"agent:{agent.id}", [agent.gouvernorat_code])
    out = schemas.AgentFile(
        agent=_row(agent, unit, current, True),
        events=[_event_out(e, units) for e in events],
        absences=[_absence_out(a, agent, unit, True) for a in absences],
    )
    await session.commit()
    return out


@router.post("/agents/{agent_id}/events", response_model=schemas.EventOut, status_code=status.HTTP_201_CREATED)
async def add_event(
    principal: Officer, session: Session, agent_id: uuid.UUID, body: schemas.EventIn
) -> schemas.EventOut:
    agent, _ = await _agent(session, agent_id, lock=True)
    _require_scope(principal, agent.gouvernorat_code)
    if body.effective_on > _today():
        # Recorded when it takes effect: the current rank and unit follow the file.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "effective_in_future")
    title = _clean(body.title)
    if body.kind != "transfer" and title is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "title_required")
    event = Event(
        agent_id=agent.id,
        gouvernorat_code=agent.gouvernorat_code,
        kind=body.kind,
        effective_on=body.effective_on,
        title=title if body.kind != "transfer" else None,
        reference=_clean(body.reference),
        note=_clean(body.note),
        created_by=audit.actor_of(principal),
        created_by_name=audit.name_of(principal),
    )
    moved_to: int | None = None
    if body.kind in STATE_KINDS and await _later_state_event(session, agent.id, body.kind, body.effective_on):
        # An older decision recorded late goes into the file without changing the current value.
        pass
    elif body.kind == "rank":
        event.previous = {"rank": agent.rank}
        agent.rank = title
    elif body.kind == "appointment":
        event.previous = {"post": agent.post}
        agent.post = title
        if body.unit_id is not None and body.unit_id != agent.unit_id:
            target = await _any_unit(body.unit_id)
            if target.gouvernorat_code != agent.gouvernorat_code:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "use_transfer")
            event.previous["unit_id"] = str(agent.unit_id)
            event.unit_id, event.from_unit_id = target.id, agent.unit_id
            agent.unit_id = target.id
    elif body.kind == "transfer":
        if body.unit_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unit_required")
        if body.unit_id == agent.unit_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "same_unit")
        target = await _any_unit(body.unit_id)
        if target.gouvernorat_code != agent.gouvernorat_code:
            # Between gouvernorats: the central department only.
            if not principal.is_national:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "central_only")
            moved_to = target.gouvernorat_code
        event.previous = {"unit_id": str(agent.unit_id), "gouvernorat_code": agent.gouvernorat_code}
        event.unit_id, event.from_unit_id = target.id, agent.unit_id
        agent.unit_id, agent.gouvernorat_code = target.id, target.gouvernorat_code
    if body.kind == "transfer" and event.unit_id is None:
        # A late transfer that does not change the current unit still names the unit.
        if body.unit_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unit_required")
        event.unit_id = (await _any_unit(body.unit_id)).id
    if body.kind in STATE_KINDS:
        _touch(agent, principal)
    session.add(event)
    gouvernorats = [event.gouvernorat_code]
    if moved_to is not None:
        await session.flush()
        await _move_file(session, agent.id, moved_to)
        gouvernorats.append(moved_to)
    await session.flush()
    await session.refresh(event)
    await _audit(
        session, principal, "event.create", f"agent:{agent.id}", gouvernorats, kind=body.kind, event=str(event.id)
    )
    units = await _unit_names(session, {u for u in (event.unit_id, event.from_unit_id) if u})
    out = _event_out(event, units)
    await session.commit()
    return out


async def _later_state_event(session: AsyncSession, agent_id: uuid.UUID, kind: str, effective_on: date) -> bool:
    found = await session.scalar(
        select(Event.id)
        .where(
            Event.agent_id == agent_id,
            Event.kind == kind,
            Event.cancelled_at.is_(None),
            Event.effective_on > effective_on,
        )
        .limit(1)
    )
    return found is not None


async def _move_file(session: AsyncSession, agent_id: uuid.UUID, gouvernorat: int) -> None:
    """The file follows the member of staff to their new gouvernorat (the central department moves it)."""
    for model in (Event, Absence):
        await session.execute(update(model).where(model.agent_id == agent_id).values(gouvernorat_code=gouvernorat))


@router.post("/events/{event_id}/cancel", response_model=schemas.EventOut)
async def cancel_event(
    principal: Officer, session: Session, event_id: uuid.UUID, body: schemas.ReasonIn
) -> schemas.EventOut:
    event = await session.scalar(select(Event).where(Event.id == event_id).with_for_update())
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "event_not_found")
    _require_scope(principal, event.gouvernorat_code)
    if event.cancelled_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_cancelled")
    agent, _ = await _agent(session, event.agent_id, lock=True)
    gouvernorats = [agent.gouvernorat_code]
    if event.kind in STATE_KINDS and event.previous and await _is_latest(session, event):
        prev = event.previous
        if event.kind == "rank":
            agent.rank = prev.get("rank")
        elif event.kind == "appointment":
            agent.post = prev.get("post")
            if prev.get("unit_id"):
                agent.unit_id = uuid.UUID(prev["unit_id"])
        else:
            back = int(prev["gouvernorat_code"])
            if back != agent.gouvernorat_code:
                if not principal.is_national:
                    raise HTTPException(status.HTTP_403_FORBIDDEN, "central_only")
                await _move_file(session, agent.id, back)
                gouvernorats.append(back)
            agent.unit_id, agent.gouvernorat_code = uuid.UUID(prev["unit_id"]), back
        _touch(agent, principal)
    event.cancelled_at = _now()
    event.cancelled_by_name = audit.name_of(principal)
    event.cancel_reason = body.reason.strip()
    await session.flush()
    await session.refresh(event)
    await _audit(
        session, principal, "event.cancel", f"agent:{agent.id}", gouvernorats, kind=event.kind, event=str(event.id)
    )
    units = await _unit_names(session, {u for u in (event.unit_id, event.from_unit_id) if u})
    out = _event_out(event, units)
    await session.commit()
    return out


async def _is_latest(session: AsyncSession, event: Event) -> bool:
    later = await session.scalar(
        select(Event.id)
        .where(
            Event.agent_id == event.agent_id,
            Event.kind == event.kind,
            Event.cancelled_at.is_(None),
            Event.id != event.id,
            or_(
                Event.effective_on > event.effective_on,
                and_(Event.effective_on == event.effective_on, Event.created_at > event.created_at),
            ),
        )
        .limit(1)
    )
    return later is None


# ---------------------------------------------------------------- absences


def _absence_out(a: Absence, agent: Agent, unit: Unit, officer: bool) -> schemas.AbsenceOut:
    return schemas.AbsenceOut(
        id=a.id,
        agent_id=agent.id,
        matricule=agent.matricule,
        full_name=agent.full_name,
        unit_id=unit.id,
        unit_name=unit.name_ar,
        gouvernorat_code=a.gouvernorat_code,
        kind=a.kind,
        starts_on=a.starts_on,
        ends_on=a.ends_on,
        days=(a.ends_on - a.starts_on).days + 1,
        reference=a.reference if officer else None,
        note=a.note if officer else None,
        created_by_name=a.created_by_name if officer else None,
        created_at=a.created_at if officer else None,
        cancelled_at=a.cancelled_at,
        cancel_reason=a.cancel_reason if officer else None,
        version=a.version,
    )


def _range(start: date | None, end: date | None) -> tuple[date, date]:
    today = _today()
    start = start or today.replace(day=1)
    end = end or (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    if end < start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "range_invalid")
    if (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "range_too_long")
    return start, end


@router.get("/absences", response_model=schemas.AbsencesOut)
async def list_absences(
    principal: Reader,
    session: Session,
    start: Annotated[date | None, Query()] = None,
    end: Annotated[date | None, Query()] = None,
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
    unit_id: Annotated[uuid.UUID | None, Query()] = None,
    agent_id: Annotated[uuid.UUID | None, Query()] = None,
    kind: Annotated[schemas.AbsenceKind | None, Query()] = None,
    cancelled: Annotated[bool, Query()] = False,
) -> schemas.AbsencesOut:
    start, end = _range(start, end)
    officer = is_officer(principal)
    query = (
        select(Absence, Agent, Unit)
        .join(Agent, Agent.id == Absence.agent_id)
        .join(Unit, Unit.id == Agent.unit_id)
        .where(_scope(principal, Absence.gouvernorat_code), Absence.starts_on <= end, Absence.ends_on >= start)
    )
    if not (cancelled and officer):
        query = query.where(Absence.cancelled_at.is_(None))
    if gouvernorat is not None:
        query = query.where(Absence.gouvernorat_code == gouvernorat)
    if unit_id is not None:
        query = query.where(Agent.unit_id == unit_id)
    if agent_id is not None:
        query = query.where(Absence.agent_id == agent_id)
    if kind is not None:
        query = query.where(Absence.kind == kind)
    rows = (await session.execute(query.order_by(Absence.starts_on, Agent.full_name))).all()
    return schemas.AbsencesOut(
        start=start, end=end, items=[_absence_out(a, g, u, officer) for a, g, u in rows], can_edit=officer
    )


async def _check_overlap(
    session: AsyncSession, agent_id: uuid.UUID, start: date, end: date, own: uuid.UUID | None
) -> None:
    query = select(Absence.id).where(
        Absence.agent_id == agent_id,
        Absence.cancelled_at.is_(None),
        Absence.starts_on <= end,
        Absence.ends_on >= start,
    )
    if own is not None:
        query = query.where(Absence.id != own)
    if await session.scalar(query.limit(1)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "absence_overlap")


def _check_dates(body: schemas.AbsenceIn) -> None:
    if body.ends_on < body.starts_on:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "range_invalid")
    if (body.ends_on - body.starts_on).days > 730:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "range_too_long")


@router.post("/absences", response_model=schemas.AbsenceOut, status_code=status.HTTP_201_CREATED)
async def create_absence(principal: Officer, session: Session, body: schemas.AbsenceIn) -> schemas.AbsenceOut:
    _check_dates(body)
    agent, unit = await _agent(session, body.agent_id, lock=True)
    _require_scope(principal, agent.gouvernorat_code)
    await _check_overlap(session, agent.id, body.starts_on, body.ends_on, None)
    absence = Absence(
        agent_id=agent.id,
        gouvernorat_code=agent.gouvernorat_code,
        kind=body.kind,
        starts_on=body.starts_on,
        ends_on=body.ends_on,
        reference=_clean(body.reference),
        note=_clean(body.note),
        created_by=audit.actor_of(principal),
        created_by_name=audit.name_of(principal),
    )
    session.add(absence)
    await session.flush()
    await session.refresh(absence)
    await _audit(
        session, principal, "absence.create", f"agent:{agent.id}", [agent.gouvernorat_code], absence=str(absence.id)
    )
    out = _absence_out(absence, agent, unit, True)
    await session.commit()
    return out


async def _absence(session: AsyncSession, absence_id: uuid.UUID) -> Absence:
    found = await session.scalar(select(Absence).where(Absence.id == absence_id).with_for_update())
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "absence_not_found")
    return found


@router.patch("/absences/{absence_id}", response_model=schemas.AbsenceOut)
async def update_absence(
    principal: Officer, session: Session, absence_id: uuid.UUID, body: schemas.AbsenceIn
) -> schemas.AbsenceOut:
    """Shorten, extend or correct an absence (a return before its end, a leave extended)."""
    _check_dates(body)
    absence = await _absence(session, absence_id)
    _require_scope(principal, absence.gouvernorat_code)
    if absence.cancelled_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_cancelled")
    if body.version is None or body.version != absence.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
    if body.agent_id != absence.agent_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "agent_fixed")
    agent, unit = await _agent(session, absence.agent_id)
    await _check_overlap(session, agent.id, body.starts_on, body.ends_on, absence.id)
    before = {"kind": absence.kind, "starts_on": absence.starts_on.isoformat(), "ends_on": absence.ends_on.isoformat()}
    absence.kind, absence.starts_on, absence.ends_on = body.kind, body.starts_on, body.ends_on
    absence.reference, absence.note = _clean(body.reference), _clean(body.note)
    absence.version += 1
    absence.updated_at = _now()
    absence.updated_by_name = audit.name_of(principal)
    await session.flush()
    await _audit(
        session,
        principal,
        "absence.update",
        f"agent:{agent.id}",
        [absence.gouvernorat_code],
        absence=str(absence.id),
        before=before,
    )
    out = _absence_out(absence, agent, unit, True)
    await session.commit()
    return out


@router.post("/absences/{absence_id}/cancel", response_model=schemas.AbsenceOut)
async def cancel_absence(
    principal: Officer, session: Session, absence_id: uuid.UUID, body: schemas.ReasonIn
) -> schemas.AbsenceOut:
    absence = await _absence(session, absence_id)
    _require_scope(principal, absence.gouvernorat_code)
    if absence.cancelled_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_cancelled")
    agent, unit = await _agent(session, absence.agent_id)
    absence.cancelled_at = _now()
    absence.cancelled_by_name = audit.name_of(principal)
    absence.cancel_reason = body.reason.strip()
    absence.version += 1
    await session.flush()
    await _audit(
        session, principal, "absence.cancel", f"agent:{agent.id}", [absence.gouvernorat_code], absence=str(absence.id)
    )
    out = _absence_out(absence, agent, unit, True)
    await session.commit()
    return out


# ---------------------------------------------------------------- general strength


def _count(total: int, kinds: dict[str, int]) -> schemas.Count:
    absent = sum(kinds.values())
    return schemas.Count(total=total, absent=absent, present=total - absent, by_kind=dict(sorted(kinds.items())))


@router.get("/strength", response_model=schemas.StrengthOut)
async def strength(
    principal: Reader,
    session: Session,
    on: Annotated[date | None, Query()] = None,
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
) -> schemas.StrengthOut:
    """The general strength of a day, unit by unit: every member of staff, the absent ones by kind, the present ones.
    Room (logistics) and administrative staff are counted on their own lines, never among those ready to intervene."""
    day = on or _today()
    current = aliased(Absence)
    absent_kind = (
        select(current.kind)
        .where(
            current.agent_id == Agent.id,
            current.cancelled_at.is_(None),
            current.starts_on <= day,
            current.ends_on >= day,
        )
        .order_by(current.starts_on)
        .limit(1)
        .scalar_subquery()
    )
    query = (
        select(Unit.id, Unit.name_ar, Unit.gouvernorat_code, Agent.category, absent_kind.label("kind"))
        .join(Agent, Agent.unit_id == Unit.id)
        .where(_scope(principal, Agent.gouvernorat_code))
    )
    if gouvernorat is not None:
        query = query.where(Agent.gouvernorat_code == gouvernorat)
    units: dict[uuid.UUID, tuple[str, int]] = {}
    totals: dict[tuple[uuid.UUID | None, str], int] = defaultdict(int)
    kinds: dict[tuple[uuid.UUID | None, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for unit_id, name, code, category, kind in (await session.execute(query)).all():
        units[unit_id] = (name, code)
        for key in ((unit_id, category), (None, category)):
            totals[key] += 1
            if kind is not None:
                kinds[key][kind] += 1

    def row(unit_id: uuid.UUID | None, name: str, code: int | None) -> schemas.StrengthRow:
        return schemas.StrengthRow(
            unit_id=unit_id,
            unit_name=name,
            gouvernorat_code=code,
            **{c: _count(totals[(unit_id, c)], kinds[(unit_id, c)]) for c in ("intervention", "room", "admin")},
        )

    ordered = sorted(units.items(), key=lambda kv: (kv[1][1], kv[1][0]))
    return schemas.StrengthOut(
        on=day,
        units=[row(u, name, code) for u, (name, code) in ordered],
        total=row(None, "", gouvernorat if gouvernorat is not None else principal.gouvernorat_code),
    )
