"""Times of a mission read from what was written about it (phase S2, docs/phase-s/design-s2.md §6).

The room's notes on the incident, the team's text notes and a radio log the operator pastes often carry the times
("وصلنا 14:32", "رجعنا للوحدة 16h05", "arrivée sur les lieux 14.32"). They are read here as suggestions: each one is
a step, a time and the words it came from, shown next to the field in the room's editor. Nothing is applied until the
operator presses it, and the saved time then goes through the same rules as a typed one (record.py).

The reading is a set of plain rules (the words of each step in Derja, Arabic and French, and a clock time near them),
not a model: it runs on the platform without the AI service, it says why it proposes a time, and it never invents
one that is not written.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.modules.ops import schemas
from app.modules.ops import service as incidents
from app.modules.ops.models import Assignment, FieldAttachment, TimelineEvent
from app.modules.ops.record import EDITABLE, FUTURE_SKEW, MAX_MISSION, _now, broken_rule, times_of

TUNIS = ZoneInfo("Africa/Tunis")
EXCERPT = 140
#: Characters between a time and the words of its step beyond which the time must be the one closest to them.
NEAR = 3
MAX_SUGGESTIONS = 20

#: The words of each step, the most specific first: "وصلنا للسبيطار" is the hospital, not the arrival on scene.
#: Matched on the text with its letters folded (see ``_fold``).
STEP_WORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "back_at_unit_at",
        (
            "رجعنا للوحده",
            "رجعنا الي الوحده",
            "رجعنا للثكنه",
            "رجعنا للمركز",
            "عدنا الي الوحده",
            "عدنا للوحده",
            "العوده الي الوحده",
            "العوده للوحده",
            "الرجوع للوحده",
            "الرجوع الي الوحده",
            "روحنا للوحده",
            "رجعنا",
            "رجعوا",
            "عدنا",
            "عادوا",
            "retour a la caserne",
            "retour a l'unite",
            "retour au centre",
            "retour base",
            "rentres",
            "rentree",
            "back at unit",
            "back to base",
        ),
    ),
    (
        "at_hospital_at",
        (
            "المستشفي",
            "مستشفي",
            "السبيطار",
            "سبيطار",
            "الاستعجالي",
            "الاستعجالات",
            "hopital",
            "urgences",
            "chu ",
            "hospital",
        ),
    ),
    (
        "left_scene_at",
        (
            "غادرنا المكان",
            "غادرنا مكان",
            "مغادره المكان",
            "مغادره مكان",
            "غادرنا",
            "غادروا",
            "خرجنا من المكان",
            "خرجوا من المكان",
            "كملنا وخرجنا",
            "quitte les lieux",
            "depart des lieux",
            "fin d'intervention",
            "left scene",
            "left the scene",
        ),
    ),
    (
        "on_scene_at",
        (
            "علي عين المكان",
            "عين المكان",
            "وصلنا",
            "وصلوا",
            "وصلت",
            "الوصول",
            "sur les lieux",
            "sur place",
            "arrivee",
            "arrives",
            "on scene",
            "arrived",
        ),
    ),
    (
        "en_route_at",
        (
            "خرجنا",
            "خرجوا",
            "خرجت",
            "انطلقنا",
            "انطلقوا",
            "انطلقت",
            "انطلاق",
            "تحركنا",
            "تحركوا",
            "تحركت",
            "طلعنا",
            "مغادره الوحده",
            "الخروج",
            "depart",
            "parti",
            "en route",
            "left unit",
        ),
    ),
)
#: Where an arrival is, when the words after it name a place other than the scene.
_ARRIVAL_AT = {
    "at_hospital_at": ("مستشفي", "سبيطار", "استعجال", "hopital", "urgences", "hospital"),
    "back_at_unit_at": ("الوحده", "للوحده", "الثكنه", "للثكنه", "للمركز", "caserne", "unite", "base"),
}
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_LETTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي", "é": "e", "è": "e", "ê": "e", "ô": "o"})
_HARAKAT = re.compile(r"[ً-ْـ]")
#: 14:32, 14h32, 14.32, 14:32:05, 9h05; not a part of a longer number (a phone, a date, a quantity).
_CLOCK = re.compile(r"(?<![\d.:/])([01]?\d|2[0-3])\s?[:hH.]\s?([0-5]\d)(?:[:.]([0-5]\d))?(?![\d.:/])")
#: A clause: a line, or a sentence of it (a dot followed by a space, so that "14.32" stays whole).
_CLAUSE = re.compile(r"\n|[،؛;]|\.\s|\s-\s|\s/\s")


@dataclass(frozen=True, slots=True)
class Written:
    """A piece of text about the mission and when it was written."""

    source: schemas.SuggestionSource
    text: str
    at: datetime


def _fold(text: str) -> str:
    return _HARAKAT.sub("", text.translate(_DIGITS).translate(_LETTERS)).lower()


def _gap(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Characters between two spans of a clause (0 when they touch or overlap)."""
    return a[0] - b[1] if b[1] <= a[0] else b[0] - a[1] if b[0] >= a[1] else 0


def _step_at(clause: str, begin: int, end: int) -> tuple[str, tuple[int, int]] | None:
    """The step whose words are closest to a clock time in its clause (the more specific step wins a tie), with the
    span of those words."""
    best: tuple[int, int, str, int, int] | None = None
    for rank, (step, words) in enumerate(STEP_WORDS):
        for word in words:
            start = clause.find(word)
            while start != -1:
                stop = start + len(word)
                candidate = (_gap((begin, end), (start, stop)), rank, step, start, stop)
                if best is None or candidate < best:
                    best = candidate
                start = clause.find(word, start + 1)
    if best is None:
        return None
    _, _, step, start, stop = best
    # "وصلنا للسبيطار" or "وصلنا للوحدة": the arrival is at the hospital or at the unit, not on scene.
    if step == "on_scene_at":
        after = clause[stop : stop + 25]
        for place, words in _ARRIVAL_AT.items():
            if any(w in after for w in words):
                return place, (start, stop)
    return step, (start, stop)


def _date_of(seconds: int, written_at: datetime) -> datetime:
    """The clock time on the day it was written, or the day before when it would be after the writing (a note at
    00:10 about a return at 23:50)."""
    local = written_at.astimezone(TUNIS)
    at = datetime(local.year, local.month, local.day, tzinfo=TUNIS) + timedelta(seconds=seconds)
    if at > local + FUTURE_SKEW:
        at -= timedelta(days=1)
    return at


def read(written: Written) -> list[tuple[str, datetime, str]]:
    """The (step, time, words) a text gives, in the order written."""
    folded = _fold(written.text)
    out: list[tuple[str, datetime, str]] = []
    offset = 0
    for clause in _CLAUSE.split(folded):
        start = folded.find(clause, offset)
        offset = start + len(clause)
        clocks = list(_CLOCK.finditer(clause))
        for match in clocks:
            found = _step_at(clause, match.start(), match.end())
            if found is None:
                continue
            step, word = found
            # A number far from the words that another time sits next to ("رجعنا 15:20، 2.50 م3 ماء") is not theirs.
            nearest = min(clocks, key=lambda c: _gap(word, c.span()))
            if nearest is not match and _gap(word, match.span()) > NEAR:
                continue
            h, m, s = int(match[1]), int(match[2]), int(match[3] or 0)
            original = written.text[start : start + len(clause)].strip()
            out.append((step, _date_of(h * 3600 + m * 60 + s, written.at), original[:EXCERPT]))
    return out


async def _written(session: AsyncSession, assignment: Assignment) -> list[Written]:
    """The room's notes on the incident (those about another team left out) and the team's text notes."""
    notes = await session.scalars(
        select(TimelineEvent)
        .where(TimelineEvent.incident_id == assignment.incident_id, TimelineEvent.kind == "note")
        .order_by(TimelineEvent.at)
    )
    out = [
        Written("room_note", str(e.payload.get("text") or ""), e.at)
        for e in notes
        if e.payload.get("assignment_id") in (None, str(assignment.id))
    ]
    texts = await session.scalars(
        select(FieldAttachment)
        .where(FieldAttachment.assignment_id == assignment.id, FieldAttachment.kind == "text")
        .order_by(FieldAttachment.created_at)
    )
    out += [Written("team_note", t.body or "", t.device_at or t.created_at) for t in texts]
    return out


async def suggestions(
    session: AsyncSession, principal: Principal, assignment_id: uuid.UUID, body: schemas.SuggestIn
) -> list[schemas.TimeSuggestion]:
    """The times the writing about a mission gives, for the operator to apply one by one (nothing is saved here)."""
    assignment = await session.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await incidents.get_in_scope(session, principal, assignment.incident_id)
    now = _now()
    written = await _written(session, assignment)
    if body.text and body.text.strip():
        written.append(Written("pasted", body.text, now))
    times = times_of(assignment)
    start = times["created_at"]
    seen: set[tuple[str, datetime]] = set()
    out: list[schemas.TimeSuggestion] = []
    for w in written:
        for step, at, words in read(w):
            if step not in EDITABLE or (step, at) in seen:
                continue
            seen.add((step, at))
            current = times[step]
            if current is not None and abs((current - at).total_seconds()) < 60:
                continue  # already the recorded time (to the minute)
            if start is not None and not (start - FUTURE_SKEW <= at <= start + MAX_MISSION):
                continue  # a time from another day or another mission
            out.append(
                schemas.TimeSuggestion(
                    step=step,
                    at=at,
                    source=w.source,
                    words=words,
                    written_at=w.at,
                    conflict=broken_rule(times | {step: at}, now),
                )
            )
    return out[-MAX_SUGGESTIONS:]
