"""The calendar rules of the programmes (phase PL2, docs/phase-pl/design-plans.md §3): the bounds of a day, a week
(from Monday) or a month, the days a repeated activity falls on, the shift of a copied programme, and the approval
path each gouvernorat chooses. Nothing here touches the database."""

import calendar
from datetime import date, timedelta
from typing import Literal

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
ITEM_STATUSES = ("planned", "done", "postponed", "cancelled")
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


def shift(span: Span, day: date, old_start: date, new_start: date) -> date | None:
    """Where a day of a copied programme lands in the new period: the same place in the day or week, the same day of
    the month (none when the new month is shorter)."""
    if span != "month":
        return new_start + (day - old_start)
    last = calendar.monthrange(new_start.year, new_start.month)[1]
    return new_start.replace(day=day.day) if day.day <= last else None


def after_submit(approval: Approval) -> str:
    return "approved" if approval == "direct" else "submitted"


def after_head(approval: Approval) -> str:
    return "awaiting_centre" if approval == "head_and_centre" else "approved"
