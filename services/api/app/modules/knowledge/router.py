"""National memory and events library endpoints (docs/api/phase-8-contract.md §2).

Memory entries are read by every library role within their access level; drafts and reviews by authors and reviewers
whose scope covers the entry. Every write and transition is audited. Library hits, calendar and tree counts and items
are restricted to the caller's role and gouvernorat before anything is returned.
"""

import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.ratelimit import enforce, opaque
from app.core.security import Principal, require_roles
from app.modules.analytics.domain import READ_ROLES as ANALYTICS_ROLES
from app.modules.knowledge import calendar, items, memory, search
from app.modules.knowledge import schemas as s
from app.modules.knowledge.domain import AUTHOR_ROLES, LIBRARY_ROLES, REVIEW_ROLES, Kind
from app.modules.reports.domain import Category
from app.modules.window import service as window_service
from app.modules.window.access import Viewer, codes_of
from app.modules.window.schemas import Filters as WindowFilters

router = APIRouter(prefix="/api/v1/staff", tags=["staff", "knowledge"])
Session = Annotated[AsyncSession, Depends(get_session)]
Reader = Annotated[Principal, Depends(require_roles(*LIBRARY_ROLES, *AUTHOR_ROLES))]
Author = Annotated[Principal, Depends(require_roles(*AUTHOR_ROLES, *REVIEW_ROLES))]
SEARCH_WINDOW_S = 60


def _csv_kinds(raw: str | None) -> list[Kind]:
    if not raw:
        return []
    try:
        return [Kind(item.strip()) for item in raw.split(",") if item.strip()]
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_kind") from exc


def _filters(
    kinds: str | None, from_: date | None, to: date | None, gouvernorat: int | None, category: Category | None
) -> search.Filters:
    if from_ and to and to < from_:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_period")
    return search.Filters(
        kinds=_csv_kinds(kinds),
        date_from=from_,
        date_to=to,
        gouvernorat=gouvernorat,
        category=category.value if category else None,
    )


# ---------------------------------------------------------------- national memory


@router.get("/memory", response_model=s.EntryPage)
async def list_memory(
    principal: Reader,
    session: Session,
    q: Annotated[str | None, Query(max_length=200)] = None,
    status_: Annotated[
        str | None, Query(alias="status", description="csv of draft,in_review,published,archived")
    ] = None,
    access: Literal["national", "gouvernorat", "committee"] | None = None,
    event_type: Category | None = None,
    gouvernorat: Annotated[int | None, Query(ge=11, le=83)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: str | None = None,
) -> s.EntryPage:
    statuses = [v.strip() for v in (status_ or "").split(",") if v.strip()]
    if any(v not in ("draft", "in_review", "published", "archived") for v in statuses):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_status")
    return await memory.list_entries(
        session,
        principal,
        q=q.strip() if q else None,
        statuses=statuses,
        access=access,
        event_type=event_type.value if event_type else None,
        gouvernorat=gouvernorat,
        limit=limit,
        cursor=cursor,
    )


@router.post("/memory", response_model=s.EntryOut, status_code=status.HTTP_201_CREATED)
async def create_memory(principal: Author, session: Session, body: s.EntryIn) -> s.EntryOut:
    if not principal.roles & frozenset(AUTHOR_ROLES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient_role")
    entry = await memory.create(session, principal, body)
    out = await memory.entry_out(session, principal, entry)
    await session.commit()
    return out


@router.post("/memory/from-incident/{incident_id}", response_model=s.EntryOut, status_code=status.HTTP_201_CREATED)
async def memory_from_incident(principal: Author, session: Session, incident_id: uuid.UUID) -> s.EntryOut:
    if not principal.roles & frozenset(AUTHOR_ROLES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient_role")
    entry = await memory.prefill_from_incident(session, principal, incident_id)
    out = await memory.entry_out(session, principal, entry)
    await session.commit()
    return out


@router.get("/memory/{entry_id}", response_model=s.EntryOut)
async def get_memory(principal: Reader, session: Session, entry_id: uuid.UUID) -> s.EntryOut:
    entry = await memory.get_visible(session, principal, entry_id)
    return await memory.entry_out(session, principal, entry)


@router.patch("/memory/{entry_id}", response_model=s.EntryOut)
async def update_memory(principal: Author, session: Session, entry_id: uuid.UUID, body: s.EntryPatch) -> s.EntryOut:
    entry = await memory.update(session, principal, entry_id, body)
    out = await memory.entry_out(session, principal, entry)
    await session.commit()
    return out


@router.post("/memory/{entry_id}/transition", response_model=s.EntryOut)
async def transition_memory(
    principal: Author, session: Session, entry_id: uuid.UUID, body: s.TransitionIn
) -> s.EntryOut:
    entry = await memory.transition(session, principal, entry_id, body)
    out = await memory.entry_out(session, principal, entry)
    await session.commit()
    return out


@router.delete("/memory/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(principal: Author, session: Session, entry_id: uuid.UUID) -> Response:
    await memory.remove(session, principal, entry_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/memory/{entry_id}/versions", response_model=s.VersionList)
async def memory_versions(principal: Reader, session: Session, entry_id: uuid.UUID) -> s.VersionList:
    return await memory.versions(session, principal, entry_id)


@router.get("/memory/{entry_id}/versions/{number}", response_model=s.VersionOut)
async def memory_version(
    principal: Reader, session: Session, entry_id: uuid.UUID, number: Annotated[int, Path(ge=1)]
) -> s.VersionOut:
    return await memory.version(session, principal, entry_id, number)


# ---------------------------------------------------------------- events library


@router.get("/library/search", response_model=s.SearchOut)
async def library_search(
    principal: Reader,
    session: Session,
    q: Annotated[str, Query(max_length=200)] = "",
    kinds: Annotated[
        str | None, Query(description="csv of memory,report_doc,incident,report,transcript,procedure")
    ] = None,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
    gouvernorat: Annotated[int | None, Query(ge=11, le=83)] = None,
    category: Category | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: str | None = None,
) -> s.SearchOut:
    await enforce(f"library:{opaque(principal.subject)}", get_settings().library_search_per_minute, SEARCH_WINDOW_S)
    filters = _filters(kinds, from_, to, gouvernorat, category)
    return await search.search(session, principal, q, filters, limit, cursor)


@router.get("/library/calendar", response_model=s.CalendarOut)
async def library_calendar(
    principal: Reader,
    session: Session,
    year: Annotated[int, Query(ge=1990, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
    kinds: str | None = None,
    gouvernorat: Annotated[int | None, Query(ge=11, le=83)] = None,
    category: Category | None = None,
) -> s.CalendarOut:
    filters = _filters(kinds, None, None, gouvernorat, category)
    return await search.calendar_counts(session, principal, filters, year, month)


@router.get("/library/calendar/grid", response_model=s.CalendarGrid)
async def library_calendar_grid(
    principal: Reader,
    session: Session,
    level: calendar.Level,
    on: date,
    kinds: str | None = None,
    gouvernorat: Annotated[int | None, Query(ge=11, le=83)] = None,
    category: Category | None = None,
) -> s.CalendarGrid:
    """One of the six levels of the calendar (L4a): the period of ``level`` that contains ``on``, cut into cells."""
    filters = _filters(kinds, None, None, gouvernorat, category)
    return await calendar.grid(session, principal, filters, level, on)


@router.get("/library/calendar/figures", response_model=s.PeriodFigures)
async def library_calendar_figures(
    principal: Annotated[Principal, Depends(require_roles(*ANALYTICS_ROLES))],
    session: Session,
    from_: Annotated[date, Query(alias="from")],
    to: date,
    gouvernorat: Annotated[int | None, Query(ge=11, le=83)] = None,
    category: Category | None = None,
) -> s.PeriodFigures:
    """The indicators of the period shown (L4a): those of the decision window, within the caller's scope."""
    if to < from_ or (to - from_).days > 366:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_period")
    f = WindowFilters(
        from_=from_,
        to=to,
        gouvernorats=[gouvernorat] if gouvernorat else [],
        category=[category.value] if category else [],
    )
    q = window_service.build(Viewer(principal, True, codes_of(principal)), f, from_, to)
    return s.PeriodFigures(
        from_=from_,
        to=to,
        gouvernorats=q.codes,
        figures=await window_service.figures(session, q),
        min_cell=window_service.min_cell(),
    )


@router.get("/library/tree", response_model=s.TreeOut)
async def library_tree(
    principal: Reader,
    session: Session,
    by: Literal["period", "type", "gouvernorat"] = "period",
    kinds: str | None = None,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
    gouvernorat: Annotated[int | None, Query(ge=11, le=83)] = None,
    category: Category | None = None,
) -> s.TreeOut:
    filters = _filters(kinds, from_, to, gouvernorat, category)
    return await search.tree(session, principal, filters, by)


@router.get("/library/items/{kind}/{item_id}", response_model=s.ItemOut)
async def library_item(principal: Reader, session: Session, kind: Kind, item_id: str) -> s.ItemOut:
    if len(item_id) > 200:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    out = await items.get_item(session, principal, kind, item_id)
    await session.commit()
    return out
