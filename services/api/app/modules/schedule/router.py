"""Daily, weekly and monthly programmes endpoints (phase PL2, docs/phase-pl/design-plans.md §3).

Each gouvernorat writes its programmes (duty rosters, patrols, exercises, prevention visits, maintenance…) and approves
them the way it chose: published when sent, approved by the head of the room, or by the head of the room then the
central room. The central room reads and helps every gouvernorat. Row level security (migration 0062) holds the same
rule in the database. The governor and the minister see the progress only: the activities name the people in charge.
"""

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.geo.models import Gouvernorat
from app.modules.inventory.models import Category
from app.modules.ops.models import Unit
from app.modules.register import service as register
from app.modules.register.models import Document
from app.modules.reports.staff_router import READ_ROLES
from app.modules.schedule import domain, schemas
from app.modules.schedule.models import Item, Period, Setting

router = APIRouter(prefix="/api/v1/staff/schedule", tags=["staff", "schedule"])
Session = Annotated[AsyncSession, Depends(get_session)]
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
Viewer = Annotated[Principal, Depends(require_roles(*READ_ROLES, Role.GOVERNOR, Role.MINISTER))]
WRITERS = frozenset({Role.OPERATOR, Role.OPS_MANAGER})
CENTRE = frozenset({Role.OPS_MANAGER, Role.CENTRAL_COMMITTEE})


# ---------------------------------------------------------------- who may do what


def reads_lists(p: Principal) -> bool:
    return bool(set(READ_ROLES) & set(p.roles))


def writes(p: Principal, gouvernorat: int) -> bool:
    """The room of the gouvernorat (operators and the head of the room), and the central room for any."""
    return bool(WRITERS & set(p.roles)) and p.can_access_gouvernorat(gouvernorat)


def heads(p: Principal, gouvernorat: int) -> bool:
    """The head of the room of the gouvernorat (the operations manager); the central one stands in for any."""
    return Role.OPS_MANAGER in p.roles and p.can_access_gouvernorat(gouvernorat)


def approves_centre(p: Principal) -> bool:
    return p.is_national and bool(CENTRE & set(p.roles))


def _now() -> datetime:
    return datetime.now(UTC)


def _forbidden(code: str = "insufficient_role") -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, code)


def _unprocessable(code: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, code)


def _gouvernorat(p: Principal, wanted: int | None) -> int:
    if not p.is_national:
        if wanted is not None and wanted != p.gouvernorat_code:
            raise _forbidden("out_of_scope")
        assert p.gouvernorat_code is not None
        return p.gouvernorat_code
    if wanted is None:
        raise _unprocessable("gouvernorat_required")
    return wanted


async def _approval(session: AsyncSession, gouvernorat: int) -> domain.Approval:
    setting = await session.get(Setting, gouvernorat)
    return setting.approval if setting else domain.DEFAULT_APPROVAL  # type: ignore[return-value]


async def _period(session: AsyncSession, period_id: uuid.UUID) -> Period:
    # Row level security hides the programmes of other gouvernorats.
    period = await session.get(Period, period_id)
    if period is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "period_not_found")
    return period


def _check_version(period: Period, version: int) -> None:
    if period.version != version:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")


def _touch(period: Period, p: Principal, now: datetime) -> None:
    period.version += 1
    period.updated_by_name = audit.name_of(p)
    period.updated_at = now


async def _record(session: AsyncSession, p: Principal, action: str, period: Period, **details: Any) -> None:
    await audit.record(
        session,
        actor=audit.actor_of(p),
        action=f"schedule.{action}",
        target=str(period.id),
        details={"span": period.span, "starts_on": period.starts_on.isoformat(), **details},
        gouvernorats=[period.gouvernorat_code],
    )


# ---------------------------------------------------------------- reading


def _counts(items: list[Item], today: date) -> schemas.Counts:
    c = schemas.Counts(items=len(items))
    for i in items:
        if i.status == "done":
            c.done += 1
        elif i.status == "postponed":
            c.postponed += 1
        elif i.status == "cancelled":
            c.cancelled += 1
        if i.on_date <= today and i.status != "cancelled":
            c.due += 1
    done_due = sum(1 for i in items if i.on_date <= today and i.status == "done")
    c.rate = round(done_due / c.due, 3) if c.due else None
    return c


def _period_out(period: Period, names: dict[int, str], items: list[Item], today: date) -> schemas.PeriodOut:
    return schemas.PeriodOut(
        id=period.id,
        gouvernorat_code=period.gouvernorat_code,
        gouvernorat_name=names.get(period.gouvernorat_code),
        span=period.span,
        starts_on=period.starts_on,
        ends_on=period.ends_on,
        status=period.status,
        approval=period.approval or domain.DEFAULT_APPROVAL,
        notes=period.notes,
        return_reason=period.return_reason,
        submitted_by_name=period.submitted_by_name,
        submitted_at=period.submitted_at,
        approved_by_name=period.approved_by_name,
        approved_at=period.approved_at,
        centre_approved_by_name=period.centre_approved_by_name,
        centre_approved_at=period.centre_approved_at,
        version=period.version,
        created_by_name=period.created_by_name,
        updated_by_name=period.updated_by_name,
        updated_at=period.updated_at,
        counts=_counts(items, today),
    )


async def _items(session: AsyncSession, period_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[Item]]:
    out: dict[uuid.UUID, list[Item]] = defaultdict(list)
    if period_ids:
        rows = await session.scalars(
            select(Item).where(Item.period_id.in_(period_ids)).order_by(Item.on_date, Item.starts_at, Item.created_at)
        )
        for i in rows:
            out[i.period_id].append(i)
    return out


async def _detail(session: AsyncSession, p: Principal, period: Period) -> schemas.PeriodDetail:
    items = (await _items(session, [period.id]))[period.id]
    names = await register.gouvernorat_names(session)
    units = {
        u.id: u.name_ar
        for u in await session.scalars(select(Unit).where(Unit.gouvernorat_code == period.gouvernorat_code))
    }
    keys = {r["category_key"] for i in items for r in i.resources}
    categories = (
        {c.key: dict(c.name) for c in await session.scalars(select(Category).where(Category.key.in_(keys)))}
        if keys
        else {}
    )
    plan_ids = {i.plan_document_id for i in items if i.plan_document_id}
    plans = (
        {
            d.id: d.title
            for d in await session.scalars(select(Document).where(Document.id.in_(plan_ids)))
            if register.readable(p, d)
        }
        if plan_ids
        else {}
    )
    previous = await session.scalar(
        select(Period.id).where(
            Period.gouvernorat_code == period.gouvernorat_code,
            Period.span == period.span,
            Period.starts_on == domain.previous_start(period.span, period.starts_on),  # type: ignore[arg-type]
        )
    )
    g = period.gouvernorat_code
    editable = period.status in domain.EDITABLE
    return schemas.PeriodDetail(
        period=_period_out(period, names, items, register.today()),
        items=[
            schemas.ItemOut(
                id=i.id,
                series_id=i.series_id,
                activity=i.activity,
                title=i.title,
                on_date=i.on_date,
                starts_at=i.starts_at,
                ends_at=i.ends_at,
                unit_id=i.unit_id,
                unit_name=units.get(i.unit_id) if i.unit_id else None,
                place=i.place,
                responsible=i.responsible,
                staff_count=i.staff_count,
                resources=[
                    schemas.ResourceOut(
                        category_key=r["category_key"], name=categories.get(r["category_key"], {}), qty=r["qty"]
                    )
                    for r in i.resources
                ],
                plan_document_id=i.plan_document_id,
                plan_title=plans.get(i.plan_document_id) if i.plan_document_id else None,
                notes=i.notes,
                status=i.status,
                status_reason=i.status_reason,
                status_by_name=i.status_by_name,
                status_at=i.status_at,
            )
            for i in items
        ],
        can_edit=(editable and writes(p, g)) or (period.status == "approved" and heads(p, g)),
        can_submit=editable and writes(p, g) and bool(items),
        can_approve=(period.status == "submitted" and heads(p, g))
        or (period.status == "awaiting_centre" and approves_centre(p)),
        can_return=(period.status == "submitted" and heads(p, g))
        or (period.status == "awaiting_centre" and approves_centre(p))
        or (period.status == "approved" and heads(p, g)),
        can_follow_up=period.status == "approved" and writes(p, g),
        can_delete=period.status == "draft" and writes(p, g),
        previous_id=previous,
    )


@router.get("/settings", response_model=list[schemas.SettingOut])
async def list_settings(principal: Reader, session: Session) -> list[schemas.SettingOut]:
    """How each gouvernorat the reader sees approves its programmes."""
    query = select(Gouvernorat.code, Gouvernorat.name_ar).order_by(Gouvernorat.code)
    if not principal.is_national:
        query = query.where(Gouvernorat.code == principal.gouvernorat_code)
    settings = {s.gouvernorat_code: s for s in await session.scalars(select(Setting))}
    out = []
    for code, name in (await session.execute(query)).all():
        s = settings.get(code)
        out.append(
            schemas.SettingOut(
                gouvernorat_code=code,
                gouvernorat_name=name,
                approval=s.approval if s else domain.DEFAULT_APPROVAL,
                updated_by_name=s.updated_by_name if s else None,
                updated_at=s.updated_at if s else None,
                can_edit=heads(principal, code),
            )
        )
    return out


@router.put("/settings/{gouvernorat_code}", response_model=schemas.SettingOut)
async def put_setting(
    principal: Reader, session: Session, gouvernorat_code: schemas.Code, body: schemas.SettingIn
) -> schemas.SettingOut:
    """Each gouvernorat chooses how its programmes are approved (the head of its room decides)."""
    if not heads(principal, gouvernorat_code):
        raise _forbidden("out_of_scope" if Role.OPS_MANAGER in principal.roles else "insufficient_role")
    setting = await session.get(Setting, gouvernorat_code)
    before = setting.approval if setting else None
    if setting is None:
        setting = Setting(gouvernorat_code=gouvernorat_code)
        session.add(setting)
    setting.approval = body.approval
    setting.updated_by, setting.updated_by_name, setting.updated_at = (
        audit.actor_of(principal),
        audit.name_of(principal),
        _now(),
    )
    await session.flush()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="schedule.setting_saved",
        target=str(gouvernorat_code),
        details={"before": before, "approval": body.approval},
        gouvernorats=[gouvernorat_code],
    )
    await session.commit()
    names = await register.gouvernorat_names(session)
    return schemas.SettingOut(
        gouvernorat_code=gouvernorat_code,
        gouvernorat_name=names.get(gouvernorat_code),
        approval=body.approval,
        updated_by_name=setting.updated_by_name,
        updated_at=setting.updated_at,
        can_edit=True,
    )


@router.get("/slot", response_model=schemas.PeriodSlot)
async def get_slot(
    principal: Reader,
    session: Session,
    span: domain.Span,
    on: date,
    gouvernorat: Annotated[schemas.Code | None, Query()] = None,
) -> schemas.PeriodSlot:
    """The programme of a gouvernorat for the day, week or month that contains ``on``, if it is recorded."""
    g = _gouvernorat(principal, gouvernorat)
    start, end = domain.bounds(span, on)
    period = await session.scalar(
        select(Period).where(Period.gouvernorat_code == g, Period.span == span, Period.starts_on == start)
    )
    return schemas.PeriodSlot(
        gouvernorat_code=g,
        span=span,
        starts_on=start,
        ends_on=end,
        period=await _detail(session, principal, period) if period else None,
        can_create=period is None and writes(principal, g),
    )


@router.get("/periods/{period_id}", response_model=schemas.PeriodDetail)
async def get_period(principal: Reader, session: Session, period_id: uuid.UUID) -> schemas.PeriodDetail:
    return await _detail(session, principal, await _period(session, period_id))


@router.get("/options", response_model=schemas.Options)
async def get_options(
    principal: Reader, session: Session, gouvernorat: Annotated[schemas.Code | None, Query()] = None
) -> schemas.Options:
    """What an activity may name: the units of the gouvernorat, the resource types, the plans in force."""
    g = _gouvernorat(principal, gouvernorat)
    units = await session.scalars(select(Unit).where(Unit.gouvernorat_code == g).order_by(Unit.name_ar))
    categories = await session.scalars(
        select(Category)
        .where(Category.active.is_(True), Category.kind.in_(("vehicle", "equipment")))
        .order_by(Category.position, Category.key)
    )
    plans = await session.scalars(
        select(Document)
        .where(Document.kind == "plan", Document.status == "in_force")
        .where((Document.gouvernorat_code.is_(None)) | (Document.gouvernorat_code == g))
        .order_by(Document.gouvernorat_code.nulls_first(), Document.title)
    )
    return schemas.Options(
        units=[schemas.UnitOption(id=u.id, name=u.name_ar) for u in units],
        categories=[schemas.CategoryOption(key=c.key, kind=c.kind, name=dict(c.name)) for c in categories],
        plans=[
            schemas.PlanOption(id=d.id, title=d.title, hazard_key=d.hazard_key)
            for d in plans
            if register.readable(principal, d)
        ],
    )


@router.get("/progress", response_model=schemas.ProgressOut)
async def get_progress(principal: Viewer, session: Session, span: domain.Span, on: date) -> schemas.ProgressOut:
    """For each gouvernorat the reader sees: its programme of the period and the share of activities done."""
    start, end = domain.bounds(span, on)
    query = select(Gouvernorat.code, Gouvernorat.name_ar).order_by(Gouvernorat.code)
    if not principal.is_national:
        query = query.where(Gouvernorat.code == principal.gouvernorat_code)
    gouvernorats = (await session.execute(query)).all()
    periods = {
        p.gouvernorat_code: p
        for p in await session.scalars(select(Period).where(Period.span == span, Period.starts_on == start))
    }
    items = await _items(session, [p.id for p in periods.values()])
    settings = {s.gouvernorat_code: s.approval for s in await session.scalars(select(Setting))}
    today = register.today()
    rows = []
    for code, name in gouvernorats:
        period = periods.get(code)
        rows.append(
            schemas.ProgressRow(
                gouvernorat_code=code,
                gouvernorat_name=name,
                approval=settings.get(code, domain.DEFAULT_APPROVAL),
                period_id=period.id if period else None,
                status=period.status if period else None,
                counts=_counts(items[period.id], today) if period else schemas.Counts(),
            )
        )
    return schemas.ProgressOut(span=span, starts_on=start, ends_on=end, rows=rows, lists=reads_lists(principal))


# ---------------------------------------------------------------- the programme and its approval


@router.post("/periods", response_model=schemas.PeriodDetail, status_code=status.HTTP_201_CREATED)
async def create_period(principal: Reader, session: Session, body: schemas.PeriodIn) -> schemas.PeriodDetail:
    g = _gouvernorat(principal, body.gouvernorat_code)
    if not writes(principal, g):
        raise _forbidden()
    start, end = domain.bounds(body.span, body.on)
    exists = await session.scalar(
        select(Period.id).where(Period.gouvernorat_code == g, Period.span == body.span, Period.starts_on == start)
    )
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "period_exists")
    now = _now()
    period = Period(
        gouvernorat_code=g,
        span=body.span,
        starts_on=start,
        ends_on=end,
        status="draft",
        notes="",
        version=1,
        created_by=audit.actor_of(principal),
        created_by_name=audit.name_of(principal),
        created_at=now,
        updated_by_name=audit.name_of(principal),
        updated_at=now,
    )
    session.add(period)
    await session.flush()
    await _record(session, principal, "period_created", period)
    await session.commit()
    return await _detail(session, principal, period)


@router.patch("/periods/{period_id}", response_model=schemas.PeriodDetail)
async def patch_period(
    principal: Reader, session: Session, period_id: uuid.UUID, body: schemas.PeriodNotes
) -> schemas.PeriodDetail:
    period = await _period(session, period_id)
    _check_version(period, body.version)
    _require_edit(principal, period)
    period.notes = body.notes
    _touch(period, principal, _now())
    await session.commit()
    return await _detail(session, principal, period)


@router.delete("/periods/{period_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_period(principal: Reader, session: Session, period_id: uuid.UUID) -> Response:
    period = await _period(session, period_id)
    if period.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "period_not_draft")
    if not writes(principal, period.gouvernorat_code):
        raise _forbidden()
    await _record(session, principal, "period_deleted", period)
    await session.delete(period)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/periods/{period_id}/submit", response_model=schemas.PeriodDetail)
async def submit_period(
    principal: Reader, session: Session, period_id: uuid.UUID, body: schemas.Step
) -> schemas.PeriodDetail:
    """Sends the programme for approval along the path its gouvernorat chose (or publishes it, if it chose so)."""
    period = await _period(session, period_id)
    _check_version(period, body.version)
    if period.status not in domain.EDITABLE:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    if not writes(principal, period.gouvernorat_code):
        raise _forbidden()
    if not await session.scalar(select(func.count()).select_from(Item).where(Item.period_id == period.id)):
        raise _unprocessable("no_items")
    now = _now()
    approval = await _approval(session, period.gouvernorat_code)
    period.approval = approval
    period.status = domain.after_submit(approval)
    period.return_reason = None
    period.submitted_by_name, period.submitted_at = audit.name_of(principal), now
    period.approved_by_name = period.approved_at = None
    period.centre_approved_by_name = period.centre_approved_at = None
    if period.status == "approved":
        period.approved_by_name, period.approved_at = audit.name_of(principal), now
    _touch(period, principal, now)
    await _record(session, principal, "period_submitted", period, approval=approval, status=period.status)
    await session.commit()
    return await _detail(session, principal, period)


@router.post("/periods/{period_id}/approve", response_model=schemas.PeriodDetail)
async def approve_period(
    principal: Reader, session: Session, period_id: uuid.UUID, body: schemas.Step
) -> schemas.PeriodDetail:
    period = await _period(session, period_id)
    _check_version(period, body.version)
    now = _now()
    approval: domain.Approval = period.approval or domain.DEFAULT_APPROVAL  # type: ignore[assignment]
    if period.status == "submitted":
        if not heads(principal, period.gouvernorat_code):
            raise _forbidden()
        period.status = domain.after_head(approval)
        period.approved_by_name, period.approved_at = audit.name_of(principal), now
    elif period.status == "awaiting_centre":
        if not approves_centre(principal):
            raise _forbidden()
        period.status = "approved"
        period.centre_approved_by_name, period.centre_approved_at = audit.name_of(principal), now
    else:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    _touch(period, principal, now)
    await _record(session, principal, "period_approved", period, status=period.status)
    await session.commit()
    return await _detail(session, principal, period)


@router.post("/periods/{period_id}/return", response_model=schemas.PeriodDetail)
async def return_period(
    principal: Reader, session: Session, period_id: uuid.UUID, body: schemas.ReturnIn
) -> schemas.PeriodDetail:
    """Sends the programme back to its room with the reason; it can be changed and sent again."""
    period = await _period(session, period_id)
    _check_version(period, body.version)
    g = period.gouvernorat_code
    allowed = (period.status in {"submitted", "approved"} and heads(principal, g)) or (
        period.status == "awaiting_centre" and approves_centre(principal)
    )
    if period.status not in {"submitted", "awaiting_centre", "approved"}:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    if not allowed:
        raise _forbidden()
    before = period.status
    period.status = "returned"
    period.return_reason = body.reason
    _touch(period, principal, _now())
    await _record(session, principal, "period_returned", period, before=before, reason=body.reason)
    await session.commit()
    return await _detail(session, principal, period)


@router.post("/periods/{period_id}/copy-previous", response_model=schemas.PeriodDetail)
async def copy_previous(
    principal: Reader, session: Session, period_id: uuid.UUID, body: schemas.Step
) -> schemas.PeriodDetail:
    """Copies the activities of the previous day, week or month into this programme, at the same place in the period;
    their follow-up starts again."""
    period = await _period(session, period_id)
    _check_version(period, body.version)
    if period.status not in domain.EDITABLE:
        raise HTTPException(status.HTTP_409_CONFLICT, "period_locked")
    if not writes(principal, period.gouvernorat_code):
        raise _forbidden()
    span: domain.Span = period.span  # type: ignore[assignment]
    previous = await session.scalar(
        select(Period).where(
            Period.gouvernorat_code == period.gouvernorat_code,
            Period.span == span,
            Period.starts_on == domain.previous_start(span, period.starts_on),
        )
    )
    if previous is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_previous_period")
    source = (await _items(session, [previous.id]))[previous.id]
    existing = await session.scalar(select(func.count()).select_from(Item).where(Item.period_id == period.id)) or 0
    if existing + len(source) > domain.MAX_ITEMS:
        raise _unprocessable("too_many_items")
    series: dict[uuid.UUID, uuid.UUID] = {}
    copied = 0
    for i in source:
        day = domain.shift(span, i.on_date, previous.starts_on, period.starts_on)
        if day is None or day > period.ends_on:
            continue
        sid = series.setdefault(i.series_id, uuid.uuid4()) if i.series_id else None
        session.add(
            Item(
                period_id=period.id,
                gouvernorat_code=period.gouvernorat_code,
                series_id=sid,
                activity=i.activity,
                title=i.title,
                on_date=day,
                starts_at=i.starts_at,
                ends_at=i.ends_at,
                unit_id=i.unit_id,
                place=i.place,
                responsible=i.responsible,
                staff_count=i.staff_count,
                resources=i.resources,
                plan_document_id=i.plan_document_id,
                notes=i.notes,
                status="planned",
                created_by_name=audit.name_of(principal),
            )
        )
        copied += 1
    _touch(period, principal, _now())
    await _record(session, principal, "period_copied", period, source=str(previous.id), items=copied)
    await session.commit()
    return await _detail(session, principal, period)


# ---------------------------------------------------------------- activities


def _require_edit(p: Principal, period: Period) -> None:
    """A draft or a returned programme is written by its room; an approved one is updated by the head of the room."""
    g = period.gouvernorat_code
    if period.status in domain.EDITABLE:
        if not writes(p, g):
            raise _forbidden()
    elif period.status == "approved":
        if not heads(p, g):
            raise _forbidden("approved_head_only")
    else:
        raise HTTPException(status.HTTP_409_CONFLICT, "period_locked")


async def _check_item(session: AsyncSession, p: Principal, period: Period, body: schemas.ItemIn) -> None:
    if not period.starts_on <= body.on_date <= period.ends_on:
        raise _unprocessable("date_outside_period")
    if body.starts_at and body.ends_at and body.ends_at <= body.starts_at:
        raise _unprocessable("hours_reversed")
    if body.unit_id:
        unit = await session.get(Unit, body.unit_id)
        if unit is None or unit.gouvernorat_code != period.gouvernorat_code:
            raise _unprocessable("unit_not_found")
    keys = {r.category_key for r in body.resources}
    if keys:
        found = set(
            await session.scalars(select(Category.key).where(Category.key.in_(keys), Category.active.is_(True)))
        )
        if found != keys:
            raise _unprocessable("category_unknown")
    if body.plan_document_id:
        doc = await session.get(Document, body.plan_document_id)
        if doc is None or doc.kind != "plan" or not register.readable(p, doc):
            raise _unprocessable("plan_not_found")


def _apply(item: Item, body: schemas.ItemIn) -> None:
    item.activity = body.activity
    item.title = body.title
    item.on_date = body.on_date
    item.starts_at = body.starts_at
    item.ends_at = body.ends_at
    item.unit_id = body.unit_id
    item.place = body.place
    item.responsible = body.responsible
    item.staff_count = body.staff_count
    item.resources = [r.model_dump() for r in body.resources]
    item.plan_document_id = body.plan_document_id
    item.notes = body.notes


async def _changed(session: AsyncSession, p: Principal, period: Period, action: str, **details: Any) -> None:
    """Changing an approved programme is an update of record."""
    _touch(period, p, _now())
    if period.status == "approved":
        await _record(session, p, action, period, **details)


@router.post("/periods/{period_id}/items", response_model=schemas.PeriodDetail, status_code=status.HTTP_201_CREATED)
async def add_item(
    principal: Reader, session: Session, period_id: uuid.UUID, body: schemas.ItemCreate
) -> schemas.PeriodDetail:
    """Adds an activity, or the same activity every day, every working day or every week until the end of the
    period (one series)."""
    period = await _period(session, period_id)
    _require_edit(principal, period)
    await _check_item(session, principal, period, body)
    days = domain.expand(body.repeat, body.on_date, period.ends_on)
    existing = await session.scalar(select(func.count()).select_from(Item).where(Item.period_id == period.id)) or 0
    if existing + len(days) > domain.MAX_ITEMS:
        raise _unprocessable("too_many_items")
    series = uuid.uuid4() if len(days) > 1 else None
    for day in days:
        item = Item(period_id=period.id, gouvernorat_code=period.gouvernorat_code, series_id=series, status="planned")
        _apply(item, body)
        item.on_date = day
        item.created_by_name = audit.name_of(principal)
        session.add(item)
    await session.flush()
    await _changed(session, principal, period, "item_added", title=body.title, days=len(days))
    await session.commit()
    return await _detail(session, principal, period)


async def _item(session: AsyncSession, item_id: uuid.UUID) -> tuple[Item, Period]:
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "item_not_found")
    return item, await _period(session, item.period_id)


@router.put("/items/{item_id}", response_model=schemas.PeriodDetail)
async def update_item(
    principal: Reader, session: Session, item_id: uuid.UUID, body: schemas.ItemIn
) -> schemas.PeriodDetail:
    item, period = await _item(session, item_id)
    _require_edit(principal, period)
    await _check_item(session, principal, period, body)
    _apply(item, body)
    item.updated_at = _now()
    await _changed(session, principal, period, "item_updated", item=str(item.id), title=body.title)
    await session.commit()
    return await _detail(session, principal, period)


@router.delete("/items/{item_id}", response_model=schemas.PeriodDetail)
async def delete_item(
    principal: Reader, session: Session, item_id: uuid.UUID, series: Annotated[bool, Query()] = False
) -> schemas.PeriodDetail:
    """Removes an activity, or every activity of its series."""
    item, period = await _item(session, item_id)
    _require_edit(principal, period)
    title = item.title
    if series and item.series_id:
        result = await session.execute(
            delete(Item).where(Item.period_id == period.id, Item.series_id == item.series_id)
        )
        removed = result.rowcount  # type: ignore[attr-defined]
    else:
        await session.delete(item)
        removed = 1
    await session.flush()
    await _changed(session, principal, period, "item_removed", title=title, items=removed)
    await session.commit()
    return await _detail(session, principal, period)


@router.post("/items/{item_id}/status", response_model=schemas.PeriodDetail)
async def item_status(
    principal: Reader, session: Session, item_id: uuid.UUID, body: schemas.ItemStatusIn
) -> schemas.PeriodDetail:
    """The follow-up of an approved programme: done, postponed or cancelled (with the reason), or planned again."""
    item, period = await _item(session, item_id)
    if period.status != "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, "period_not_approved")
    if not writes(principal, period.gouvernorat_code):
        raise _forbidden()
    if body.status in {"postponed", "cancelled"} and len(body.reason) < 5:
        raise _unprocessable("reason_required")
    if body.status == "done" and item.on_date > register.today():
        raise _unprocessable("not_due_yet")
    item.status = body.status
    item.status_reason = body.reason or None
    item.status_by_name, item.status_at = audit.name_of(principal), _now()
    await session.commit()
    return await _detail(session, principal, period)
