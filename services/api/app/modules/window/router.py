"""The decision window (L4 §3) and its delegations (§5): the situation now, the search, the comparison, the reports,
the saved searches, the dictionary of the quick search, and who opens the window to whom."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import ApiError, room_of
from app.core.db import as_system, get_session
from app.core.security import REALM_ROLES, Principal, Realm, Role, require_roles
from app.modules.access.keycloak import DirectoryError, StaffAccount
from app.modules.access.keycloak import get_directory as _get_directory
from app.modules.analytics import documents
from app.modules.analytics import service as analytics
from app.modules.audit import service as audit
from app.modules.window import access, exports, schemas, service, summary
from app.modules.window.access import Viewer
from app.modules.window.models import SavedSearch, Synonym, WindowDelegation, WindowEvent

router = APIRouter(prefix="/api/v1/staff/window", tags=["window"])

Session = Annotated[AsyncSession, Depends(get_session)]
AnyStaff = Annotated[Principal, Depends(require_roles(*REALM_ROLES[Realm.STAFF]))]
MAX_DELEGATION = timedelta(days=366)
MAX_SAVED = 50
DELEGATES_PAGE = 50


def _refuse(code: str, **extra: object) -> ApiError:
    return ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, code, **extra)


def _forbidden(code: str = "action_not_allowed") -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, code)


async def _viewer(session: AsyncSession, principal: Principal, view: str) -> Viewer:
    """The caller's view; every look of a delegate is audited (§5)."""
    viewer = await access.viewer(session, principal)
    if viewer.delegated:
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action="window.delegate_view",
            target=f"window:{view}",
            details={"delegations": [str(i) for i in viewer.delegation_ids], "events": len(viewer.incident_ids or [])},
            gouvernorats=viewer.codes or None,
        )
        await session.commit()
    return viewer


def _ints(raw: str | None) -> list[int]:
    try:
        return [int(x) for x in (raw or "").split(",") if x.strip()]
    except ValueError as exc:
        raise _refuse("invalid_filter") from exc


def _strs(raw: str | None) -> list[str]:
    return [x.strip() for x in (raw or "").split(",") if x.strip()][:40]


def filters(
    q: Annotated[str | None, Query(max_length=200)] = None,
    from_: Annotated[str | None, Query(alias="from")] = None,
    to: str | None = None,
    gouvernorats: str | None = None,
    delegation: int | None = None,
    category: str | None = None,
    classification: str | None = None,
    severity: str | None = None,
    status_: Annotated[str | None, Query(alias="status")] = None,
    source: str | None = None,
    unit: uuid.UUID | None = None,
    org: uuid.UUID | None = None,
) -> schemas.Filters:
    """The criteria in the query string, lists separated by commas."""
    try:
        return schemas.Filters.model_validate(
            {
                "q": q,
                "from": from_ or None,
                "to": to or None,
                "gouvernorats": _ints(gouvernorats),
                "delegation": delegation,
                "category": _strs(category),
                "classification": _strs(classification),
                "severity": _ints(severity),
                "status": _strs(status_),
                "source": _strs(source),
                "unit": unit,
                "org": org,
            }
        )
    except ValueError as exc:
        raise _refuse("invalid_filter") from exc


Criteria = Annotated[schemas.Filters, Depends(filters)]


# ---------------------------------------------------------------- the window


@router.get("/access", response_model=schemas.AccessOut)
async def my_access(principal: AnyStaff, session: Session) -> schemas.AccessOut:
    """What the caller may do with the window, and the delegations in force for them."""
    mine = [] if access.full_view(principal) else await access.in_force(session, principal.subject, _now())
    return schemas.AccessOut(
        full=access.full_view(principal),
        delegated=bool(mine),
        may_delegate=access.may_delegate(principal),
        keeps_dictionary=access.keeps_dictionary(principal),
        delegations=await _delegations_out(session, mine),
    )


@router.get("/now", response_model=schemas.NowOut)
async def now(principal: AnyStaff, session: Session) -> schemas.NowOut:
    viewer = await _viewer(session, principal, "now")
    return await service.now(session, viewer)


@router.get("/search", response_model=schemas.SearchOut)
async def search(principal: AnyStaff, session: Session, f: Criteria) -> schemas.SearchOut:
    viewer = await _viewer(session, principal, "search")
    return await service.search(session, viewer, f)


@router.get("/compare", response_model=schemas.CompareOut)
async def compare(
    principal: AnyStaff,
    session: Session,
    f: Criteria,
    mode: str = "periods",
    a_from: str | None = None,
    a_to: str | None = None,
    b_from: str | None = None,
    b_to: str | None = None,
    a_gouvernorat: int | None = None,
    b_gouvernorat: int | None = None,
) -> schemas.CompareOut:
    try:
        body = schemas.CompareIn(
            filters=f,
            mode=mode,
            a_from=a_from or None,
            a_to=a_to or None,
            b_from=b_from or None,
            b_to=b_to or None,
            a_gouvernorat=a_gouvernorat,
            b_gouvernorat=b_gouvernorat,
        )
    except ValueError as exc:
        raise _refuse("invalid_filter") from exc
    viewer = await _viewer(session, principal, "compare")
    return await service.compare(session, viewer, body)


_MEDIA = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@router.post("/export")
async def export(principal: AnyStaff, session: Session, body: schemas.ExportIn) -> Response:
    """The report of a search or of a comparison, in the reader's language; every export is audited (§3.4)."""
    viewer = await _viewer(session, principal, "export")
    names = await analytics.gouvernorat_names(session)
    by = audit.name_of(principal) or principal.subject
    if body.kind == "search":
        out = await service.search(session, viewer, body.filters)
        content = exports.search_content(out, body.filters, body.lang, by, names)
        details: dict[str, Any] = {"items": len(out.items)}
    else:
        compare_in = body.compare or schemas.CompareIn(filters=body.filters)
        result = await service.compare(session, viewer, compare_in)
        content = exports.compare_content(result, compare_in.filters, body.lang, by, names)
        details = {"mode": compare_in.mode}
    data = documents.render(content, body.format)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="window.export",
        target=f"window:{body.kind}",
        details={
            "format": body.format,
            "lang": body.lang,
            "filters": body.filters.model_dump(mode="json", by_alias=True, exclude_defaults=True),
            "delegated": viewer.delegated,
            **details,
        },
        gouvernorats=viewer.codes or None,
    )
    await session.commit()
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    return Response(
        data,
        media_type=_MEDIA[body.format],
        headers={"Content-Disposition": f'attachment; filename="e-himaya-window-{body.kind}-{stamp}.{body.format}"'},
    )


@router.post("/summary", response_model=schemas.SummaryOut)
async def write_summary(principal: AnyStaff, session: Session, body: schemas.SummaryIn) -> schemas.SummaryOut:
    """The advisory written summary of a search or a comparison (§9, item 1), from the aggregates only; audited."""
    viewer = await _viewer(session, principal, "summary")
    names = await analytics.gouvernorat_names(session)
    if body.kind == "search":
        out = await service.search(session, viewer, body.filters)
        facts, min_cell = summary.search_facts(out, body.lang, names), out.min_cell
    else:
        result = await service.compare(session, viewer, body.compare or schemas.CompareIn(filters=body.filters))
        facts, min_cell = summary.compare_facts(result, body.lang, names), result.min_cell
    text_out, supported, model = await summary.write(facts, body.lang, min_cell)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="window.summary",
        target=f"window:{body.kind}",
        details={"lang": body.lang, "supported": supported, "model": model, "delegated": viewer.delegated},
        gouvernorats=viewer.codes or None,
    )
    await session.commit()
    return schemas.SummaryOut(
        text=text_out, supported=supported, model=model, notice=summary.NOTICE[body.lang], generated_at=_now()
    )


# ---------------------------------------------------------------- saved searches


def _saved_out(row: SavedSearch) -> schemas.SavedOut:
    return schemas.SavedOut(id=row.id, name=row.name, kind=row.kind, query=row.query, created_at=row.created_at)


@router.get("/searches", response_model=list[schemas.SavedOut])
async def list_saved(principal: AnyStaff, session: Session) -> list[schemas.SavedOut]:
    await access.viewer(session, principal)
    async with as_system(session):
        rows = await session.scalars(
            select(SavedSearch).where(SavedSearch.owner == principal.subject).order_by(SavedSearch.name)
        )
        return [_saved_out(r) for r in rows]


@router.post("/searches", response_model=schemas.SavedOut, status_code=status.HTTP_201_CREATED)
async def save_search(principal: AnyStaff, session: Session, body: schemas.SavedIn) -> schemas.SavedOut:
    await access.viewer(session, principal)
    if len(str(body.query)) > 4000:
        raise _refuse("query_too_long")
    async with as_system(session):
        count = await session.scalar(
            select(func.count()).select_from(SavedSearch).where(SavedSearch.owner == principal.subject)
        )
        if int(count or 0) >= MAX_SAVED:
            raise _refuse("too_many_saved")
        existing = await session.scalar(
            select(SavedSearch).where(SavedSearch.owner == principal.subject, SavedSearch.name == body.name)
        )
        row = existing or SavedSearch(owner=principal.subject, name=body.name, created_at=_now())
        row.kind, row.query = body.kind, body.query
        if existing is None:
            session.add(row)
        await session.flush()
        out = _saved_out(row)
        await session.commit()
    return out


@router.delete("/searches/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_search(principal: AnyStaff, session: Session, search_id: uuid.UUID) -> Response:
    async with as_system(session):
        row = await session.get(SavedSearch, search_id)
        if row is None or row.owner != principal.subject:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        await session.delete(row)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- the dictionary of the quick search


def _synonym_out(row: Synonym) -> schemas.SynonymOut:
    return schemas.SynonymOut(
        id=row.id, meaning=row.meaning, words=row.words, updated_by_name=row.updated_by_name, updated_at=row.updated_at
    )


@router.get("/synonyms", response_model=list[schemas.SynonymOut])
async def list_synonyms(principal: AnyStaff, session: Session) -> list[schemas.SynonymOut]:
    await access.viewer(session, principal)
    async with as_system(session):
        return [_synonym_out(r) for r in await session.scalars(select(Synonym).order_by(Synonym.meaning))]


@router.post("/synonyms", response_model=schemas.SynonymOut)
async def put_synonym(principal: AnyStaff, session: Session, body: schemas.SynonymIn) -> schemas.SynonymOut:
    """Add or replace the words of one meaning (the central room keeps the dictionary)."""
    if not access.keeps_dictionary(principal):
        raise _forbidden()
    words = sorted({w.strip() for w in body.words if w.strip() and len(w.strip()) <= 60})
    if not words:
        raise _refuse("no_words")
    meaning = body.meaning.strip()
    async with as_system(session):
        row = await session.scalar(select(Synonym).where(Synonym.meaning == meaning))
        if row is None:
            row = Synonym(meaning=meaning)
            session.add(row)
        row.words, row.updated_by_name, row.updated_at = words, audit.name_of(principal), _now()
        await session.flush()
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action="window.synonyms",
            target=f"synonym:{row.id}",
            details={"meaning": meaning, "words": words},
        )
        out = _synonym_out(row)
        await session.commit()
    return out


@router.delete("/synonyms/{synonym_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_synonym(principal: AnyStaff, session: Session, synonym_id: uuid.UUID) -> Response:
    if not access.keeps_dictionary(principal):
        raise _forbidden()
    async with as_system(session):
        row = await session.get(Synonym, synonym_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action="window.synonyms",
            target=f"synonym:{row.id}",
            details={"meaning": row.meaning, "deleted": True},
        )
        await session.delete(row)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- delegations


def _now() -> datetime:
    return datetime.now(UTC)


def _state(row: WindowDelegation, now: datetime) -> str:
    if row.revoked_at is not None:
        return "revoked"
    if row.ends_at <= now:
        return "ended"
    if row.starts_at > now:
        return "scheduled"
    return "active"


async def _delegations_out(session: AsyncSession, rows: list[WindowDelegation]) -> list[schemas.DelegationOut]:
    if not rows:
        return []
    now = _now()
    async with as_system(session):
        events = list(
            await session.scalars(
                select(WindowEvent)
                .where(WindowEvent.delegation_id.in_([r.id for r in rows]))
                .order_by(WindowEvent.added_at)
            )
        )
    return [
        schemas.DelegationOut(
            id=r.id,
            grantee=r.grantee,
            grantee_name=r.grantee_name,
            grantee_roles=r.grantee_roles,
            grantee_gouvernorat=r.grantee_gouvernorat,
            reason=r.reason,
            starts_at=r.starts_at,
            ends_at=r.ends_at,
            granted_by_name=r.granted_by_name,
            granted_room=r.granted_room,
            created_at=r.created_at,
            revoked_at=r.revoked_at,
            revoked_by_name=r.revoked_by_name,
            revoke_reason=r.revoke_reason,
            state=_state(r, now),
            events=[
                schemas.EventOut(
                    kind=e.kind,
                    id=e.target_id,
                    label=e.label,
                    gouvernorat_code=e.gouvernorat_code,
                    added_by_name=e.added_by_name,
                    added_at=e.added_at,
                )
                for e in events
                if e.delegation_id == r.id
            ],
        )
        for r in rows
    ]


def _grantor(principal: Principal) -> Principal:
    if not access.may_delegate(principal):
        raise _forbidden()
    return principal


def _name(account: StaffAccount) -> str:
    return " ".join(p for p in (account.first_name, account.last_name) if p) or account.username


def _may_receive(grantor: Principal, account: StaffAccount) -> bool:
    """A national ops manager delegates to any staff account; a regional one to its governor and local committee."""
    if grantor.is_national:
        return True
    return account.gouvernorat_code == grantor.gouvernorat_code and bool(
        {r.value for r in access.REGIONAL_DELEGATES} & account.roles
    )


async def _account(account_id: str) -> StaffAccount:
    directory = _get_directory()
    if directory is None:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "identity_provider_error")
    try:
        account = await directory.get_account(account_id)
    except DirectoryError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "identity_provider_error") from exc
    if account is None or not account.enabled:
        raise _refuse("account_not_found")
    return account


async def _event(
    session: AsyncSession, grantor: Principal, grantee_code: int | None, ref: schemas.EventRef
) -> tuple[str, list[int]]:
    """The label and the gouvernorats of a delegated event, refused outside the grantor's or the grantee's scope."""
    async with as_system(session):
        if ref.kind == "axis":
            row = (
                await session.execute(
                    text("SELECT number, name, gouvernorat_code FROM crisis.axis WHERE id = :id"), {"id": ref.id}
                )
            ).one_or_none()
            if row is None:
                raise _refuse("unknown_event", id=str(ref.id))
            label, codes = f"{row[0]} · {row[1]}", [row[2]] if row[2] is not None else []
        else:
            row = (
                await session.execute(
                    text(
                        "SELECT i.category, i.gouvernorat_code, array(SELECT ig.gouvernorat_code "
                        "FROM ops.incident_gouvernorat ig WHERE ig.incident_id = i.id) FROM ops.incident i "
                        "WHERE i.id = :id AND i.status NOT IN ('merged', 'dissolved')"
                    ),
                    {"id": ref.id},
                )
            ).one_or_none()
            if row is None:
                raise _refuse("unknown_event", id=str(ref.id))
            label = f"{ref.id.hex[:8]} · {row[0]}"
            codes = sorted({c for c in [row[1], *row[2]] if c is not None})
    for code in (grantor.gouvernorat_code, grantee_code):
        # A national axis or an intervention without a gouvernorat goes to national accounts only.
        if code is not None and code not in codes:
            raise _refuse("event_out_of_scope", id=str(ref.id))
    return label, codes


async def _add_events(
    session: AsyncSession, principal: Principal, row: WindowDelegation, refs: list[schemas.EventRef]
) -> list[str]:
    existing = {
        (k, t)
        for k, t in (
            await session.execute(
                select(WindowEvent.kind, WindowEvent.target_id).where(WindowEvent.delegation_id == row.id)
            )
        ).all()
    }
    added = []
    for ref in refs:
        if (ref.kind, ref.id) in existing:
            continue
        label, codes = await _event(session, principal, row.grantee_gouvernorat, ref)
        session.add(
            WindowEvent(
                delegation_id=row.id,
                kind=ref.kind,
                target_id=ref.id,
                label=label,
                gouvernorat_code=codes[0] if len(codes) == 1 else None,
                added_by_name=audit.name_of(principal),
                added_at=_now(),
            )
        )
        existing.add((ref.kind, ref.id))
        added.append(f"{ref.kind}:{ref.id}")
    return added


async def _owned(session: AsyncSession, principal: Principal, delegation_id: uuid.UUID) -> WindowDelegation:
    """A delegation the caller manages: the central room every one, a gouvernorat's room those it granted."""
    row = await session.get(WindowDelegation, delegation_id)
    if row is None or (not principal.is_national and row.granted_room != room_of(principal)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return row


@router.get("/delegates", response_model=list[schemas.Delegate])
async def delegates(
    principal: AnyStaff, q: Annotated[str | None, Query(max_length=100)] = None
) -> list[schemas.Delegate]:
    """The accounts the caller may open the window to."""
    _grantor(principal)
    directory = _get_directory()
    if directory is None:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "identity_provider_error")
    try:
        found = await directory.list_accounts(
            gouvernorat_code=principal.gouvernorat_code, q=q, first=0, max_results=DELEGATES_PAGE
        )
    except DirectoryError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "identity_provider_error") from exc
    staff = {r.value for r in REALM_ROLES[Realm.STAFF]}
    return [
        schemas.Delegate(id=a.id, name=_name(a), roles=sorted(a.roles & staff), gouvernorat_code=a.gouvernorat_code)
        for a in found
        if a.enabled
        and a.id != principal.subject
        and _may_receive(principal, a)
        and not access.full_view(_as_principal(a))
        and (q is None or q.lower() in f"{a.username} {_name(a)}".lower())
    ]


def _as_principal(account: StaffAccount) -> Principal:
    return Principal(
        subject=account.id,
        realm=Realm.STAFF,
        roles=frozenset(Role(r) for r in account.roles if r in {x.value for x in REALM_ROLES[Realm.STAFF]}),
        gouvernorat_code=None if account.scope_level == "national" else account.gouvernorat_code,
    )


@router.get("/delegations", response_model=list[schemas.DelegationOut])
async def list_delegations(
    principal: AnyStaff, session: Session, include_ended: bool = False
) -> list[schemas.DelegationOut]:
    _grantor(principal)
    async with as_system(session):
        query = select(WindowDelegation).order_by(WindowDelegation.created_at.desc()).limit(500)
        if not principal.is_national:
            query = query.where(WindowDelegation.granted_room == room_of(principal))
        if not include_ended:
            query = query.where(WindowDelegation.revoked_at.is_(None), WindowDelegation.ends_at > _now())
        rows = list(await session.scalars(query))
    return await _delegations_out(session, rows)


@router.post("/delegations", response_model=schemas.DelegationOut, status_code=status.HTTP_201_CREATED)
async def grant(principal: AnyStaff, session: Session, body: schemas.DelegationIn) -> schemas.DelegationOut:
    _grantor(principal)
    if body.grantee == principal.subject:
        raise _refuse("self_delegation")
    account = await _account(body.grantee)
    if not _may_receive(principal, account):
        raise _refuse("delegate_not_allowed")
    grantee = _as_principal(account)
    if access.full_view(grantee):
        raise _refuse("already_full_view")
    now = _now()
    starts = body.starts_at or now
    if body.ends_at <= max(starts, now) or body.ends_at - starts > MAX_DELEGATION:
        raise _refuse("invalid_period")
    async with as_system(session):
        row = WindowDelegation(
            grantee=account.id,
            grantee_name=_name(account),
            grantee_roles=sorted(r.value for r in grantee.roles),
            grantee_gouvernorat=grantee.gouvernorat_code,
            reason=body.reason,
            starts_at=starts,
            ends_at=body.ends_at,
            granted_by=audit.actor_of(principal),
            granted_by_name=audit.name_of(principal),
            granted_room=room_of(principal),
            created_at=now,
        )
        session.add(row)
        await session.flush()
        added = await _add_events(session, principal, row, body.events)
        await session.flush()
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action="window.delegation_grant",
            target=f"delegation:{row.id}",
            reason=body.reason,
            details={
                "grantee": account.id,
                "grantee_roles": row.grantee_roles,
                "starts_at": starts.isoformat(),
                "ends_at": body.ends_at.isoformat(),
                "events": added,
            },
            gouvernorats=[grantee.gouvernorat_code] if grantee.gouvernorat_code is not None else None,
        )
        out = (await _delegations_out(session, [row]))[0]
        await session.commit()
    return out


@router.post("/delegations/{delegation_id}/events", response_model=schemas.DelegationOut)
async def add_events(
    principal: AnyStaff, session: Session, delegation_id: uuid.UUID, body: schemas.EventsIn
) -> schemas.DelegationOut:
    _grantor(principal)
    async with as_system(session):
        row = await _owned(session, principal, delegation_id)
        if _state(row, _now()) in ("revoked", "ended"):
            raise HTTPException(status.HTTP_409_CONFLICT, "delegation_closed")
        added = await _add_events(session, principal, row, body.events)
        await session.flush()
        if added:
            await audit.record(
                session,
                actor=audit.actor_of(principal),
                action="window.delegation_add",
                target=f"delegation:{row.id}",
                details={"grantee": row.grantee, "events": added},
                gouvernorats=[row.grantee_gouvernorat] if row.grantee_gouvernorat is not None else None,
            )
        out = (await _delegations_out(session, [row]))[0]
        await session.commit()
    return out


@router.post("/delegations/{delegation_id}/revoke", response_model=schemas.DelegationOut)
async def revoke(
    principal: AnyStaff, session: Session, delegation_id: uuid.UUID, body: schemas.RevokeIn
) -> schemas.DelegationOut:
    _grantor(principal)
    async with as_system(session):
        row = await _owned(session, principal, delegation_id)
        if row.revoked_at is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "already_revoked")
        row.revoked_at, row.revoked_by_name, row.revoke_reason = _now(), audit.name_of(principal), body.reason
        await session.flush()
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action="window.delegation_revoke",
            target=f"delegation:{row.id}",
            reason=body.reason,
            details={"grantee": row.grantee},
            gouvernorats=[row.grantee_gouvernorat] if row.grantee_gouvernorat is not None else None,
        )
        out = (await _delegations_out(session, [row]))[0]
        await session.commit()
    return out
