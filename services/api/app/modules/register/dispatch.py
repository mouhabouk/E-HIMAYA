"""Directives of the centre to the gouvernorats and notices of a gouvernorat to the centre, with one thread of replies
per gouvernorat and the attached files (phase L3b, docs/phase-l/design-l3b.md §8).

The row-level security keeps a gouvernorat to the directives sent to it (to all or to it alone), its own notices and its
own thread; the centre reads everything. ``register.dispatch_target`` follows the receiving side of each gouvernorat:
the gouvernorat for a directive (seen, replied), the centre for a notice.
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import emit
from app.core.security import Principal
from app.core.storage import get_store
from app.modules.audit import service as audit
from app.modules.crisis.models import Axis
from app.modules.geo.models import Gouvernorat
from app.modules.knowledge import text as kt
from app.modules.ops.models import Incident
from app.modules.register import domain, schemas
from app.modules.register.models import Attachment, Dispatch, DispatchTarget, Reply
from app.modules.register.service import gouvernorat_names, next_number, now

PAGE_MAX = 100


def _err(code: int, detail: str) -> HTTPException:
    return HTTPException(code, detail)


def _gov(code: int | None) -> list[int] | None:
    return [code] if code else None


async def get(session: AsyncSession, dispatch_id: uuid.UUID, *, lock: bool = False) -> Dispatch:
    """The dispatch, if the caller's scope reads it (404 otherwise: its existence is not disclosed)."""
    query = select(Dispatch).where(Dispatch.id == dispatch_id)
    found = await session.scalar(query.with_for_update() if lock else query)
    if found is None:
        raise _err(status.HTTP_404_NOT_FOUND, "dispatch_not_found")
    return found


def overdue(d: Dispatch, t: DispatchTarget | None, at: datetime) -> bool:
    return (
        d.status == "open"
        and d.reply_required
        and d.reply_due_at is not None
        and d.reply_due_at < at
        and (t is None or t.replied_at is None)
    )


async def create(session: AsyncSession, principal: Principal, body: schemas.DispatchIn) -> Dispatch:
    if body.kind == "directive":
        if not domain.centre_writes(principal):
            raise _err(status.HTTP_403_FORBIDDEN, "centre_only")
        every = list(await session.scalars(select(Gouvernorat.code).order_by(Gouvernorat.code)))
        if body.audience == "targeted":
            targets = sorted(set(body.gouvernorats))
            if not targets:
                raise _err(status.HTTP_422_UNPROCESSABLE_CONTENT, "gouvernorats_required")
            if any(code not in every for code in targets):
                raise _err(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown_gouvernorat")
        else:
            targets = every
        audience: str = body.audience
        origin, series = None, "DIR"
    else:
        if not domain.room_writes(principal) or principal.gouvernorat_code is None:
            raise _err(status.HTTP_403_FORBIDDEN, "regional_room_only")
        targets, audience, series = [principal.gouvernorat_code], "centre", "NOT"
        origin = principal.gouvernorat_code
    if body.reply_due_at is not None and body.reply_due_at <= now():
        raise _err(status.HTTP_422_UNPROCESSABLE_CONTENT, "due_in_the_past")
    if body.incident_id is not None and await session.get(Incident, body.incident_id) is None:
        raise _err(status.HTTP_404_NOT_FOUND, "incident_not_found")
    if body.axis_id is not None and await session.get(Axis, body.axis_id) is None:
        raise _err(status.HTTP_404_NOT_FOUND, "axis_not_found")
    actor, name, at = audit.actor_of(principal), audit.name_of(principal), now()
    d = Dispatch(
        id=uuid.uuid4(),
        number=await next_number(session, at.year, series),
        kind=body.kind,
        audience=audience,
        origin_gouvernorat=origin,
        urgency=body.urgency,
        subject=body.subject,
        body=body.body,
        topics=list(dict.fromkeys(body.topics)),
        incident_id=body.incident_id,
        axis_id=body.axis_id,
        reply_required=body.reply_required,
        reply_due_at=body.reply_due_at,
        status="open",
        created_by=actor,
        created_by_name=name,
        created_at=at,
    )
    d.norm = domain.norm_text([d.number, d.subject, d.body, " ".join(d.topics)])
    session.add(d)
    await session.flush()
    session.add_all(DispatchTarget(dispatch_id=d.id, gouvernorat_code=code, replies=0) for code in targets)
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action=f"register.{body.kind}_sent",
        target=str(d.id),
        details={"number": d.number, "audience": audience, "urgency": d.urgency, "gouvernorats": len(targets)},
        gouvernorats=targets if audience != "all" else None,
    )
    await emit(
        session,
        f"register.{body.kind}_sent",
        {
            "id": str(d.id),
            "number": d.number,
            "urgency": d.urgency,
            "subject": d.subject,
            "gouvernorats": targets,
            "to": domain.receiving_side(d.kind),
        },
    )
    return d


# --- Reading --------------------------------------------------------------------------------------------------------


@dataclass(slots=True)
class Filters:
    # inbox: what the caller's side receives; sent: what it sends; all.
    box: str = "all"
    kinds: list[str] | None = None
    urgencies: list[str] | None = None
    state: str | None = None
    gouvernorat_code: int | None = None
    q: str = ""
    date_from: date | None = None
    date_to: date | None = None
    unread_only: bool = False
    limit: int = 30
    offset: int = 0


def _side(principal: Principal) -> str:
    return "centre" if principal.is_national else "regional"


def _where(principal: Principal, f: Filters, params: dict[str, Any]) -> list[str]:
    side = _side(principal)
    where = ["true"]
    receives = "directive" if side == "regional" else "notice"
    sends = "notice" if side == "regional" else "directive"
    if f.box == "inbox":
        where.append(f"d.kind = '{receives}'")
    elif f.box == "sent":
        where.append(f"d.kind = '{sends}'")
    if f.kinds:
        params["kinds"] = f.kinds
        where.append("d.kind = ANY(CAST(:kinds AS text[]))")
    if f.urgencies:
        params["urgencies"] = f.urgencies
        where.append("d.urgency = ANY(CAST(:urgencies AS text[]))")
    if f.state in ("open", "closed"):
        params["state"] = f.state
        where.append("d.status = :state")
    if f.gouvernorat_code is not None:
        params["g"] = f.gouvernorat_code
        where.append(
            "EXISTS (SELECT 1 FROM register.dispatch_target t WHERE t.dispatch_id = d.id AND t.gouvernorat_code = :g)"
        )
    terms = kt.query_terms(f.q) if f.q else []
    if terms:
        params["tsq"] = " & ".join(f"{t}:*" for t in terms)
        where.append("d.search @@ to_tsquery('simple', :tsq)")
    if f.date_from is not None:
        params["date_from"] = datetime.combine(f.date_from, time.min)
        where.append("d.created_at >= CAST(:date_from AS timestamp)")
    if f.date_to is not None:
        params["date_to"] = datetime.combine(f.date_to, time.max)
        where.append("d.created_at <= CAST(:date_to AS timestamp)")
    if f.unread_only:
        params["receives"] = receives
        where.append(
            "d.kind = :receives AND EXISTS (SELECT 1 FROM register.dispatch_target t "
            "WHERE t.dispatch_id = d.id AND t.seen_at IS NULL)"
        )
    return where


async def unread_count(session: AsyncSession, principal: Principal) -> int:
    """Directives a gouvernorat has not opened yet; for the centre, notices not opened yet."""
    receives = "directive" if _side(principal) == "regional" else "notice"
    return int(
        await session.scalar(
            select(func.count(func.distinct(Dispatch.id)))
            .join(DispatchTarget, DispatchTarget.dispatch_id == Dispatch.id)
            .where(Dispatch.kind == receives, Dispatch.status == "open", DispatchTarget.seen_at.is_(None))
        )
        or 0
    )


async def search(session: AsyncSession, principal: Principal, f: Filters) -> tuple[list[Dispatch], int, list[str]]:
    params: dict[str, Any] = {"limit": min(f.limit, PAGE_MAX), "offset": f.offset}
    clause = " AND ".join(_where(principal, f, params))
    sql = f"SELECT d.id FROM register.dispatch d WHERE {clause} ORDER BY d.created_at DESC LIMIT :limit OFFSET :offset"  # noqa: S608 (constant SQL fragments, values are bound)
    ids = [row[0] for row in (await session.execute(text(sql), params)).all()]
    count_sql = f"SELECT count(*) FROM register.dispatch d WHERE {clause}"  # noqa: S608 (constant SQL fragments, values are bound)
    total = int(await session.scalar(text(count_sql), params) or 0)
    found = {d.id: d for d in await session.scalars(select(Dispatch).where(Dispatch.id.in_(ids)))} if ids else {}
    return [found[i] for i in ids if i in found], total, (kt.query_terms(f.q) if f.q else [])


async def targets_of(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, list[DispatchTarget]]:
    """The target rows the caller's scope reads (all for the centre, its own for a gouvernorat)."""
    out: dict[uuid.UUID, list[DispatchTarget]] = {i: [] for i in ids}
    if ids:
        rows = await session.scalars(
            select(DispatchTarget).where(DispatchTarget.dispatch_id.in_(ids)).order_by(DispatchTarget.gouvernorat_code)
        )
        for t in rows:
            out[t.dispatch_id].append(t)
    return out


async def attachment_counts(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not ids:
        return {}
    rows = await session.execute(
        select(Attachment.dispatch_id, func.count())
        .where(Attachment.dispatch_id.in_(ids), Attachment.reply_id.is_(None))
        .group_by(Attachment.dispatch_id)
    )
    return {r[0]: int(r[1]) for r in rows.all()}


def dispatch_out(
    principal: Principal,
    d: Dispatch,
    targets: list[DispatchTarget],
    names: dict[int, str],
    files: int,
    terms: list[str] | None = None,
) -> schemas.DispatchOut:
    at = now()
    receiving = domain.receiving_side(d.kind) == _side(principal)
    return schemas.DispatchOut(
        id=str(d.id),
        number=d.number,
        kind=d.kind,
        audience=d.audience,
        origin_gouvernorat=d.origin_gouvernorat,
        origin_name=names.get(d.origin_gouvernorat) if d.origin_gouvernorat else None,
        urgency=d.urgency,
        subject=d.subject,
        body=d.body,
        topics=list(d.topics),
        incident_id=str(d.incident_id) if d.incident_id else None,
        axis_id=str(d.axis_id) if d.axis_id else None,
        reply_required=d.reply_required,
        reply_due_at=d.reply_due_at,
        status=d.status,
        closed_at=d.closed_at,
        created_by_name=d.created_by_name,
        created_at=d.created_at,
        targets=len(targets),
        seen=sum(1 for t in targets if t.seen_at is not None),
        replied=sum(1 for t in targets if t.replied_at is not None),
        unread=receiving and d.status == "open" and any(t.seen_at is None for t in targets),
        overdue=any(overdue(d, t, at) for t in targets) if targets else overdue(d, None, at),
        attachments=files,
        excerpt=(kt.excerpt(d.body, terms) or None) if terms else None,
    )


def attachment_out(a: Attachment) -> schemas.AttachmentOut:
    return schemas.AttachmentOut(
        id=str(a.id),
        file_name=a.file_name,
        content_type=a.content_type,
        size=a.size,
        sha256=a.sha256,
        created_at=a.created_at,
    )


async def mark_seen(session: AsyncSession, principal: Principal, d: Dispatch) -> None:
    """The receiving side opened it: a gouvernorat its directive, the centre a notice (every row it reads)."""
    if domain.receiving_side(d.kind) != _side(principal) or d.created_by == audit.actor_of(principal):
        return
    rows = await session.scalars(
        select(DispatchTarget).where(DispatchTarget.dispatch_id == d.id, DispatchTarget.seen_at.is_(None))
    )
    at = now()
    for t in rows:
        if principal.is_national or t.gouvernorat_code == principal.gouvernorat_code:
            t.seen_at, t.seen_by_name = at, audit.name_of(principal)
    await session.flush()


def can_reply(principal: Principal, d: Dispatch) -> bool:
    if d.status != "open":
        return False
    return domain.centre_writes(principal) or domain.room_writes(principal)


def can_close(principal: Principal, d: Dispatch) -> bool:
    return d.status == "open" and (d.created_by == audit.actor_of(principal) or domain.centre_writes(principal))


async def detail(session: AsyncSession, principal: Principal, d: Dispatch) -> schemas.DispatchDetail:
    names = await gouvernorat_names(session)
    targets = (await targets_of(session, [d.id]))[d.id]
    files = list(
        await session.scalars(select(Attachment).where(Attachment.dispatch_id == d.id).order_by(Attachment.created_at))
    )
    replies = list(
        await session.scalars(select(Reply).where(Reply.dispatch_id == d.id).order_by(Reply.created_at, Reply.id))
    )
    by_reply: dict[uuid.UUID, list[schemas.AttachmentOut]] = {}
    for a in files:
        if a.reply_id is not None:
            by_reply.setdefault(a.reply_id, []).append(attachment_out(a))
    threads: dict[int, list[schemas.ReplyOut]] = {t.gouvernorat_code: [] for t in targets}
    actor = audit.actor_of(principal)
    for r in replies:
        threads.setdefault(r.gouvernorat_code, []).append(
            schemas.ReplyOut(
                id=str(r.id),
                gouvernorat_code=r.gouvernorat_code,
                side=r.side,
                body=r.body,
                created_by_name=r.created_by_name,
                created_at=r.created_at,
                attachments=by_reply.get(r.id, []),
                mine=r.created_by == actor,
            )
        )
    at = now()
    return schemas.DispatchDetail(
        dispatch=dispatch_out(principal, d, targets, names, sum(1 for a in files if a.reply_id is None)),
        attachments=[attachment_out(a) for a in files if a.reply_id is None],
        targets=[
            schemas.TargetOut(
                gouvernorat_code=t.gouvernorat_code,
                gouvernorat_name=names.get(t.gouvernorat_code),
                seen_at=t.seen_at,
                seen_by_name=t.seen_by_name,
                replied_at=t.replied_at,
                replies=t.replies,
                overdue=overdue(d, t, at),
            )
            for t in targets
        ],
        # Threads with replies first, then by gouvernorat; a gouvernorat sees only its own.
        threads=[
            schemas.ThreadOut(gouvernorat_code=code, gouvernorat_name=names.get(code), replies=items)
            for code, items in sorted(threads.items(), key=lambda kv: (not kv[1], kv[0]))
            if items or not principal.is_national
        ],
        can_reply=can_reply(principal, d),
        can_close=can_close(principal, d),
        can_attach=d.status == "open" and d.created_by == actor,
    )


# --- Writing --------------------------------------------------------------------------------------------------------


async def reply(session: AsyncSession, principal: Principal, d: Dispatch, body: schemas.ReplyIn) -> Reply:
    if d.status != "open":
        raise _err(status.HTTP_409_CONFLICT, "dispatch_closed")
    if domain.centre_writes(principal):
        side, code = "centre", body.gouvernorat_code
        if code is None:
            raise _err(status.HTTP_422_UNPROCESSABLE_CONTENT, "gouvernorat_required")
    elif domain.room_writes(principal):
        side, code = "regional", principal.gouvernorat_code
    else:
        raise _err(status.HTTP_403_FORBIDDEN, "cannot_reply")
    target = await session.get(DispatchTarget, (d.id, code), with_for_update=True)
    if target is None:
        raise _err(status.HTTP_404_NOT_FOUND, "thread_not_found")
    at = now()
    r = Reply(
        id=uuid.uuid4(),
        dispatch_id=d.id,
        gouvernorat_code=code,
        side=side,
        body=body.body,
        created_by=audit.actor_of(principal),
        created_by_name=audit.name_of(principal),
        created_at=at,
    )
    session.add(r)
    if side == domain.receiving_side(d.kind):
        target.replied_at = target.replied_at or at
        target.replies += 1
        if target.seen_at is None:
            target.seen_at, target.seen_by_name = at, audit.name_of(principal)
    await session.flush()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="register.reply_sent",
        target=str(d.id),
        details={"number": d.number, "gouvernorat": code, "side": side},
        gouvernorats=_gov(code),
    )
    await emit(
        session,
        "register.reply_sent",
        {"id": str(d.id), "number": d.number, "gouvernorat": code, "side": side, "urgency": d.urgency},
    )
    return r


async def attach(
    session: AsyncSession, principal: Principal, d: Dispatch, reply_id: uuid.UUID | None, name: str, data: bytes
) -> Attachment:
    if d.status != "open":
        raise _err(status.HTTP_409_CONFLICT, "dispatch_closed")
    actor = audit.actor_of(principal)
    code: int | None = None
    if reply_id is None:
        if d.created_by != actor:
            raise _err(status.HTTP_403_FORBIDDEN, "not_the_author")
    else:
        r = await session.get(Reply, reply_id)
        if r is None or r.dispatch_id != d.id:
            raise _err(status.HTTP_404_NOT_FOUND, "reply_not_found")
        if r.created_by != actor:
            raise _err(status.HTTP_403_FORBIDDEN, "not_the_author")
        code = r.gouvernorat_code
    if not data:
        raise _err(status.HTTP_422_UNPROCESSABLE_CONTENT, "file_empty")
    found = domain.attachment_type(data, name)
    if found is None:
        raise _err(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "file_type_not_allowed")
    owner = Attachment.reply_id == reply_id if reply_id is not None else Attachment.reply_id.is_(None)
    count = int(await session.scalar(select(func.count()).where(Attachment.dispatch_id == d.id, owner)) or 0)
    if count >= domain.MAX_ATTACHMENTS:
        raise _err(status.HTTP_409_CONFLICT, "too_many_files")
    content_type, ext = found
    key = f"register/dispatch/{d.id}/{uuid.uuid4().hex}{ext}"
    await get_store().put(key, data, content_type)
    a = Attachment(
        id=uuid.uuid4(),
        dispatch_id=d.id,
        reply_id=reply_id,
        gouvernorat_code=code,
        file_key=key,
        file_name=name[:200],
        content_type=content_type,
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        created_by=actor,
        created_at=now(),
    )
    session.add(a)
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action="register.attachment_added",
        target=str(d.id),
        details={"number": d.number, "sha256": a.sha256, "size": a.size, "type": content_type},
        gouvernorats=_gov(code),
    )
    return a


async def close(session: AsyncSession, principal: Principal, d: Dispatch) -> None:
    if not can_close(principal, d):
        raise _err(status.HTTP_403_FORBIDDEN, "cannot_close")
    d.status, d.closed_at, d.closed_by_name = "closed", now(), audit.name_of(principal)
    await session.flush()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="register.dispatch_closed",
        target=str(d.id),
        details={"number": d.number},
    )
