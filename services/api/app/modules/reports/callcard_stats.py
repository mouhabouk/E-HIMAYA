"""Statistics of the guided call-taking cards (OS2-3, Yamen 2026-11-13; docs/phase-os2b/design-os2b.md §2).

Over the reports the rooms wrote down in a period: how many were entered with a card, how long the call lasted with
and without one, per room; and per card how callers answered each question, how often the team changed an answer
from the scene, which instructions were read, and what the team found compared with the card (``callcards.compare``).

* The call time is the phone's own (answered to ended) when the report was written from a call of the dashboard's
  phone; otherwise the time from opening the intake form to saving it (radio, walk-in). Times outside 0 s – 2 h are
  left out.
* A regional room sees its own row and the national figures beside it; the national scope sees every room. No agent
  is named: the figures are there to improve the cards, not to rate people.
"""

import statistics
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import room_of
from app.core.db import as_system
from app.core.security import Principal
from app.modules.reports import callcards as cc
from app.modules.reports.domain import Category

Channel = Literal["phone", "radio", "in_person", "other"]
CHECKS = ("confirmed", "nature_differs", "lives_not_on_card", "injured_not_on_card", "band_below_toll")
MAX_DURATION_S = 2 * 3600

_ROWS = text(
    """
    SELECT r.id, r.category, COALESCE(r.entered_room, r.claimed_room) AS room, r.intake_channel AS channel,
           r.incident_id,
           EXTRACT(EPOCH FROM (r.received_at - r.entry_started_at)) AS form_s,
           (SELECT EXTRACT(EPOCH FROM (c.ended_at - c.answered_at)) FROM telephony.call c
             WHERE c.report_id = r.id AND c.answered_at IS NOT NULL AND c.ended_at IS NOT NULL
             ORDER BY c.answered_at LIMIT 1) AS call_s,
           a.card_id, a.answers, a.outcome, a.field_answers, a.field_outcome
      FROM reports.report r
      LEFT JOIN reports.call_card_answer a ON a.report_id = r.id
     WHERE r.source = 'room' AND r.received_at >= :since AND r.intake_channel = ANY(:channels)
    """
)

_NATURES = text(
    """
    SELECT DISTINCT ON (incident_id) incident_id, crew_nature FROM ops.assignment
     WHERE incident_id IN :ids AND crew_nature IS NOT NULL ORDER BY incident_id, created_at DESC
    """
).bindparams(bindparam("ids", expanding=True))

_COUNTS = text(
    """
    SELECT incident_id, injured_light, injured_serious, deceased, trapped FROM ops.casualty_count
     WHERE incident_id IN :ids
    """
).bindparams(bindparam("ids", expanding=True))


class Figures(BaseModel):
    entered: int = 0
    with_card: int = 0
    median_with_s: int | None = None
    median_without_s: int | None = None
    #: Nine calls out of ten (with or without a card) last less than this.
    p90_s: int | None = None
    #: Reports entered with a card whose team reported what it found, and those where it matched the card.
    field_checked: int = 0
    field_confirmed: int = 0


class RoomFigures(Figures):
    room: str


class QuestionFigures(BaseModel):
    id: str
    text: str
    key: bool
    yes: int = 0
    no: int = 0
    unknown: int = 0
    #: Times the team answered this question differently from the caller.
    field_changed: int = 0
    field_answered: int = 0


class CardFigures(BaseModel):
    category: Category
    title: str
    used: int = 0
    median_s: int | None = None
    #: Answers «doesn't know» to the decisive questions, over all answers to them.
    key_unknown: int = 0
    key_answered: int = 0
    field_checked: int = 0
    checks: dict[str, int]
    questions: list[QuestionFigures]
    #: Instruction key → times it was read to the caller.
    read: dict[str, int]
    instruction_titles: dict[str, str]


class StatsOut(BaseModel):
    days: int
    since: datetime
    #: ``None`` for every room (national scope); the regional caller's room otherwise.
    room: str | None
    total: Figures
    #: The national figures, for a regional room to compare with (the same as ``total`` for the national scope).
    national: Figures
    rooms: list[RoomFigures]
    cards: list[CardFigures]


@dataclass
class _Acc:
    entered: int = 0
    with_card: int = 0
    with_s: list[float] = field(default_factory=list)
    without_s: list[float] = field(default_factory=list)
    field_checked: int = 0
    field_confirmed: int = 0

    def add(self, carded: bool, duration: float | None, checks: list[str] | None) -> None:
        self.entered += 1
        if carded:
            self.with_card += 1
        if duration is not None:
            (self.with_s if carded else self.without_s).append(duration)
        if checks:
            self.field_checked += 1
            if checks == ["confirmed"]:
                self.field_confirmed += 1

    def out(self) -> dict[str, Any]:
        both = self.with_s + self.without_s
        return {
            "entered": self.entered,
            "with_card": self.with_card,
            "median_with_s": _median(self.with_s),
            "median_without_s": _median(self.without_s),
            "p90_s": _p90(both),
            "field_checked": self.field_checked,
            "field_confirmed": self.field_confirmed,
        }


def _median(xs: list[float]) -> int | None:
    return round(statistics.median(xs)) if xs else None


def _p90(xs: list[float]) -> int | None:
    if not xs:
        return None
    if len(xs) == 1:
        return round(xs[0])
    return round(statistics.quantiles(xs, n=10, method="inclusive")[-1])


def duration(call_s: float | None, form_s: float | None) -> float | None:
    """The phone's call time when there is one, otherwise the form's; ``None`` outside 0 s – 2 h."""
    for value in (call_s, form_s):
        if value is not None:
            v = float(value)
            return v if 0 <= v <= MAX_DURATION_S else None
    return None


async def _scenes(session: AsyncSession, incidents: set[uuid.UUID]) -> dict[uuid.UUID, cc.Scene]:
    if not incidents:
        return {}
    ids = list(incidents)
    scenes = {i: cc.Scene() for i in ids}
    for incident_id, nature in (await session.execute(_NATURES, {"ids": ids})).all():
        scenes[incident_id].nature = nature
    for incident_id, light, serious, deceased, trapped in (await session.execute(_COUNTS, {"ids": ids})).all():
        s = scenes[incident_id]
        s.injured, s.serious, s.deceased, s.trapped = light + serious, serious, deceased, trapped
    return scenes


async def compute(
    session: AsyncSession,
    principal: Principal,
    days: int,
    channels: list[str],
    room: str | None,
    cards: dict[str, cc.CardContent],
) -> StatsOut:
    """``cards``: the content shown for each category (its approved version), for the question texts."""
    since = datetime.now(UTC) - timedelta(days=days)
    if not principal.is_national:
        room = room_of(principal)
    async with as_system(session):
        rows = (await session.execute(_ROWS, {"since": since, "channels": list(channels)})).mappings().all()
        scenes = await _scenes(session, {r["incident_id"] for r in rows if r["incident_id"] and r["card_id"]})

    national, total = _Acc(), _Acc()
    per_room: dict[str, _Acc] = defaultdict(_Acc)
    per_card: dict[str, dict[str, Any]] = {}
    for r in rows:
        carded = r["card_id"] is not None
        took = duration(r["call_s"], r["form_s"])
        checks: list[str] | None = None
        if carded and r["incident_id"] in scenes:
            outcome = cc.Outcome.model_validate(r["field_outcome"] or r["outcome"])
            checks = cc.compare(r["category"], outcome, scenes[r["incident_id"]])
        national.add(carded, took, checks)
        row_room = r["room"] or "central"
        if room is not None and row_room != room:
            continue
        total.add(carded, took, checks)
        per_room[row_room].add(carded, took, checks)
        if carded:
            _card_row(per_card, r, took, checks)

    out_cards: list[CardFigures] = []
    for category in Category:
        content = cards.get(category.value)
        acc = per_card.get(category.value)
        if content is None:
            continue
        questions = [
            QuestionFigures(id=q.id, text=q.text, key=q.key, **(acc["questions"].get(q.id, {}) if acc else {}))
            for q in content.questions
        ]
        out_cards.append(
            CardFigures(
                category=category,
                title=content.title,
                used=acc["used"] if acc else 0,
                median_s=_median(acc["durations"]) if acc else None,
                key_unknown=sum(q.unknown for q in questions if q.key),
                key_answered=sum(q.yes + q.no + q.unknown for q in questions if q.key),
                field_checked=acc["field_checked"] if acc else 0,
                checks={c: (acc["checks"][c] if acc else 0) for c in CHECKS},
                questions=questions,
                read={k: (acc["read"][k] if acc else 0) for k in content.instructions},
                instruction_titles={k: i.title for k, i in content.instructions.items()},
            )
        )
    rooms = sorted(
        (RoomFigures(room=k, **v.out()) for k, v in per_room.items()),
        key=lambda f: (f.room != "central", -f.entered, f.room),
    )
    return StatsOut(
        days=days,
        since=since,
        room=room,
        total=Figures(**total.out()),
        national=Figures(**national.out()),
        rooms=rooms,
        cards=out_cards,
    )


def _card_row(per_card: dict[str, dict[str, Any]], r: Any, took: float | None, checks: list[str] | None) -> None:
    acc = per_card.setdefault(
        r["category"],
        {
            "used": 0,
            "durations": [],
            "field_checked": 0,
            "checks": Counter(),
            "questions": defaultdict(lambda: defaultdict(int)),
            "read": Counter(),
        },
    )
    acc["used"] += 1
    if took is not None:
        acc["durations"].append(took)
    if checks:
        acc["field_checked"] += 1
        acc["checks"].update(checks)
    answers: dict[str, str] = r["answers"] or {}
    field_answers: dict[str, str] = r["field_answers"] or {}
    for qid, answer in answers.items():
        acc["questions"][qid][answer] += 1
    for qid, answer in field_answers.items():
        acc["questions"][qid]["field_answered"] += 1
        if answers.get(qid) != answer:
            acc["questions"][qid]["field_changed"] += 1
    acc["read"].update((r["outcome"] or {}).get("read", []))
