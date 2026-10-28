"""The calendar of the events library at six levels (L4a, docs/phase-l/design-l4.md §2).

A level shows the period that contains a day, cut into cells: a day into its hours, a week (Monday to Sunday) and a
month into their days, a quarter into its weeks, a half-year and a year into their months. Each cell counts the
library items of its span, with the search filters kept; hours, days and weeks are those of Africa/Tunis.
"""

from datetime import date, datetime, time, timedelta
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.modules.analytics.domain import TUNIS_TZ
from app.modules.knowledge import schemas as s
from app.modules.knowledge import search

Level = Literal["day", "week", "month", "quarter", "half", "year"]
LEVELS: tuple[Level, ...] = ("day", "week", "month", "quarter", "half", "year")
STEP: dict[Level, Literal["hour", "day", "week", "month"]] = {
    "day": "hour",
    "week": "day",
    "month": "day",
    "quarter": "week",
    "half": "month",
    "year": "month",
}


def _month_start(year: int, month: int) -> date:
    return date(year + (month - 1) // 12, (month - 1) % 12 + 1, 1)


def bounds(level: Level, on: date) -> tuple[date, date]:
    """The first and last day of the period of ``level`` that contains ``on``."""
    if level == "day":
        return on, on
    if level == "week":
        start = on - timedelta(days=on.weekday())
        return start, start + timedelta(days=6)
    months = {"month": 1, "quarter": 3, "half": 6, "year": 12}[level]
    first_month = (on.month - 1) // months * months + 1
    start = date(on.year, first_month, 1)
    return start, _month_start(on.year, first_month + months) - timedelta(days=1)


def cells(level: Level, start: date, end: date) -> list[tuple[date | datetime, date]]:
    """Each cell's first moment (an hour on the day level) and the last day it covers."""
    step = STEP[level]
    if step == "hour":
        return [(datetime.combine(start, time(h), tzinfo=TUNIS_TZ), start) for h in range(24)]
    out: list[tuple[date | datetime, date]] = []
    if step == "day":
        day = start
        while day <= end:
            out.append((day, day))
            day += timedelta(days=1)
    elif step == "week":
        # The weeks that meet the period, from its first Monday (on or before its first day), cut at its bounds.
        monday = start - timedelta(days=start.weekday())
        while monday <= end:
            out.append((max(monday, start), min(monday + timedelta(days=6), end)))
            monday += timedelta(days=7)
    else:
        month = start
        while month <= end:
            following = _month_start(month.year, month.month + 1)
            out.append((month, following - timedelta(days=1)))
            month = following
    return out


async def grid(
    session: AsyncSession, principal: Principal, filters: search.Filters, level: Level, on: date
) -> s.CalendarGrid:
    start, end = bounds(level, on)
    span = search.Filters(
        kinds=filters.kinds,
        date_from=start,
        date_to=end,
        gouvernorat=filters.gouvernorat,
        category=filters.category,
    )
    where, params = search.where(principal, span)
    step = STEP[level]
    local = "(d.date AT TIME ZONE 'Africa/Tunis')"
    key = f"to_char(date_trunc('{step}', {local}), 'YYYY-MM-DD\"T\"HH24')"
    rows = await session.execute(
        text(
            f"SELECT {key} AS k, count(*) AS n FROM knowledge.search_doc d "  # noqa: S608 (constant SQL fragments, values are bound)
            f"WHERE {where} AND d.date IS NOT NULL GROUP BY k"
        ),
        params,
    )
    counts = {str(r.k): int(r.n) for r in rows}
    out = []
    for first, last in cells(level, start, end):
        if isinstance(first, datetime):
            k = first.strftime("%Y-%m-%dT%H")
        elif step == "week":
            k = (first - timedelta(days=first.weekday())).strftime("%Y-%m-%dT00")
        else:
            k = first.strftime("%Y-%m-%dT00")
        out.append(s.CalendarCell(start=first.isoformat(), end=last, count=counts.get(k, 0)))
    return s.CalendarGrid(level=level, step=step, start=start, end=end, cells=out)
