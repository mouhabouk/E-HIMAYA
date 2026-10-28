"""The calendar rules of the programmes (phase PL2, docs/phase-pl/design-plans.md §3): the bounds of a day, a week
(from Monday) or a month, the days a repeated activity falls on, the day of a copied or templated activity, and the
approval path each gouvernorat chooses. Nothing here touches the database."""

import calendar
from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

Span = Literal["day", "week", "month"]
SPANS: tuple[Span, ...] = ("day", "week", "month")
Approval = Literal["direct", "head", "head_and_centre"]
APPROVALS: tuple[Approval, ...] = ("direct", "head", "head_and_centre")
DEFAULT_APPROVAL: Approval = "head"
Repeat = Literal["none", "daily", "weekdays", "weekly"]
ACTIVITIES = (
    "duty",
    "patrol",
    "exercise",
    "prevention_visit",
    "maintenance",
    "training",
    "awareness",
    "readiness_check",
    "meeting",
    "other",
)
ITEM_STATUSES = ("planned", "in_progress", "done", "not_done", "postponed", "refused", "cancelled")
# Set by hand with a reason; refused and cancelled activities are left out of the completion rate.
WITH_REASON = frozenset({"not_done", "postponed", "refused", "cancelled"})
LEFT_OUT = frozenset({"refused", "cancelled"})
# The hours of an activity are those of Tunisia.
TUNIS = ZoneInfo("Africa/Tunis")
# A programme is written while a draft or sent back; it is locked while it waits for an approval.
EDITABLE = frozenset({"draft", "returned"})
WAITING = frozenset({"submitted", "awaiting_centre"})
MAX_ITEMS = 2000


def bounds(span: Span, on: date) -> tuple[date, date]:
    """The first and last day of the day, week (Monday to Sunday) or month that contains ``on``."""
    if span == "day":
        return on, on
    if span == "week":
        start = on - timedelta(days=on.weekday())
        return start, start + timedelta(days=6)
    last = calendar.monthrange(on.year, on.month)[1]
    return on.replace(day=1), on.replace(day=last)


def previous_start(span: Span, start: date) -> date:
    """The first day of the period before the one starting on ``start``."""
    return bounds(span, start - timedelta(days=1))[0]


def expand(repeat: Repeat, first: date, end: date) -> list[date]:
    """The days an activity falls on, from ``first`` to the end of its period."""
    if repeat == "none":
        return [first]
    step = 7 if repeat == "weekly" else 1
    days = []
    day = first
    while day <= end:
        if repeat != "weekdays" or day.weekday() < 5:
            days.append(day)
        day += timedelta(days=step)
    return days


def place(offset: int, start: date, end: date) -> date | None:
    """The day of a template's activity in a period: ``offset`` days after its first day, none past its end (a
    month template's 31st has no place in a shorter month)."""
    day = start + timedelta(days=offset)
    return day if day <= end else None


def after_submit(approval: Approval) -> str:
    return "approved" if approval == "direct" else "submitted"


def after_head(approval: Approval) -> str:
    return "awaiting_centre" if approval == "head_and_centre" else "approved"


def local_today(now: datetime) -> date:
    return now.astimezone(TUNIS).date()


def follow_up(
    status: str, manual: bool, approved: bool, on: date, starts: time | None, ends: time | None, now: datetime
) -> tuple[str, bool]:
    """The status of an activity and whether the clock set it (docs/phase-l/design-l4.md §6): an activity of an
    approved programme with a start time, never set by hand, is in progress from its start and done at its end (the
    end of its day without an end time). A status set by hand always wins; an activity of the whole day stays by
    hand."""
    if manual or status != "planned" or not approved or starts is None:
        return status, False
    start = datetime.combine(on, starts, TUNIS)
    end = datetime.combine(on, ends, TUNIS) if ends else datetime.combine(on + timedelta(days=1), time(0), TUNIS)
    if now >= end:
        return "done", True
    if now >= start:
        return "in_progress", True
    return "planned", False
