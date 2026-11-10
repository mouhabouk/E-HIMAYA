"""Guided call-taking cards (OS2, Yamen 2026-11-10; docs/phase-os2/design-os2.md).

When a room writes down a call, the card of the report's category asks a few questions; each answer can raise the
claim band (never lower it), flag a danger, suggest resources and give instructions the agent reads to the caller.
The rules are pure functions (``evaluate``, ``summary``); the content is written and approved by the Office from the
dashboard, one version at a time, and every report keeps the version it was entered with.

* Answers are ``yes``, ``no`` or ``unknown``. A decisive question (``key``) left at ``unknown`` keeps the band at
  ``high`` at least: not knowing never lowers it.
* A question with ``when`` is asked only after the given answer to another question.
* ``lives`` and ``injured`` feed the ``lives`` and ``casualties`` components of the priority (``ai.scoring``); the band
  becomes the report's ``call_card_floor`` (``reports.sla``).
* The suggested resources are a suggestion: the room manager decides (BR-03).
"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.modules.reports.domain import Category

Band = Literal["critical", "high", "normal", "low"]
Answer = Literal["yes", "no", "unknown"]
BANDS: tuple[Band, ...] = ("low", "normal", "high", "critical")
BAND_LABELS: dict[str, str] = {"critical": "حرج", "high": "عالٍ", "normal": "عادي", "low": "منخفض"}
ANSWER_LABELS: dict[str, str] = {"yes": "نعم", "no": "لا", "unknown": "لا يعرف"}
# Cards whose instructions are medical gestures: approved only after the medical staff validated the version.
MEDICAL_CATEGORIES = frozenset({Category.MEDICAL.value, Category.DROWNING.value})
UNKNOWN_KEY_FLOOR: Band = "high"

Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Line = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
Ident = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,39}$")]


def higher(a: Band, b: Band | None) -> Band:
    return a if b is None or BANDS.index(a) >= BANDS.index(b) else b


class Effect(BaseModel):
    """What one answer does. Nothing here can lower the band."""

    model_config = ConfigDict(extra="forbid")

    why: Short
    band: Band | None = None
    flag: Short | None = None
    means: list[Short] = Field(default_factory=list, max_length=8)
    instruction: Ident | None = None
    lives: bool = False
    injured: bool = False


class When(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: Ident
    answer: Answer


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Ident
    text: Line
    help: Short | None = None
    key: bool = False
    when: When | None = None
    effects: dict[Answer, Effect] = Field(default_factory=dict)


class Instruction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Short
    steps: list[Line] = Field(min_length=1, max_length=12)
    medical: bool = False
    # Compressions per minute the dashboard beats for the agent to count aloud (CPR); None = no metronome.
    metronome: int | None = Field(default=None, ge=60, le=140)


class CardContent(BaseModel):
    """The JSON of a card version, as stored in ``reports.call_card.content``."""

    model_config = ConfigDict(extra="forbid")

    title: Short
    base_band: Band = "normal"
    base_means: list[Short] = Field(default_factory=list, max_length=8)
    questions: list[Question] = Field(min_length=1, max_length=20)
    instructions: dict[Ident, Instruction] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _consistent(self) -> "CardContent":
        ids = [q.id for q in self.questions]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate_question")
        seen: set[str] = set()
        for q in self.questions:
            # A follow-up question comes after the question it follows, so the card reads top to bottom.
            if q.when is not None and q.when.question not in seen:
                raise ValueError(f"follow_up_before_question:{q.id}")
            seen.add(q.id)
            for effect in q.effects.values():
                if effect.instruction is not None and effect.instruction not in self.instructions:
                    raise ValueError(f"unknown_instruction:{effect.instruction}")
        return self

    @property
    def medical_instructions(self) -> bool:
        return any(i.medical for i in self.instructions.values())


class Outcome(BaseModel):
    band: Band
    flags: list[str]
    reasons: list[str]
    means: list[str]
    instructions: list[str]
    lives: bool
    injured: bool
    answered: int
    asked: int


def asked(content: CardContent, answers: dict[str, Answer]) -> list[Question]:
    """The questions shown for these answers: a follow-up only once the question it follows got its answer."""
    return [q for q in content.questions if q.when is None or answers.get(q.when.question) == q.when.answer]


def evaluate(content: CardContent, answers: dict[str, Answer]) -> Outcome:
    band: Band = content.base_band
    reasons = [f"نقطة البداية لبطاقة «{content.title}»: {BAND_LABELS[band]}"]
    flags: list[str] = []
    means = list(content.base_means)
    instructions: list[str] = []
    lives = injured = False
    shown = asked(content, answers)
    for q in shown:
        answer = answers.get(q.id)
        if answer is None:
            continue
        effect = q.effects.get(answer)
        if effect is None:
            continue
        band = higher(band, effect.band)
        reasons.append(effect.why + (f" ← {BAND_LABELS[effect.band]}" if effect.band else ""))
        if effect.flag and effect.flag not in flags:
            flags.append(effect.flag)
        means += [m for m in effect.means if m not in means]
        if effect.instruction and effect.instruction not in instructions:
            instructions.append(effect.instruction)
        lives = lives or effect.lives
        injured = injured or effect.injured
    if any(q.key and answers.get(q.id) == "unknown" for q in shown) and higher(band, UNKNOWN_KEY_FLOOR) != band:
        band = UNKNOWN_KEY_FLOOR
        reasons.append(f"سؤال حاسم دون جواب («لا يعرف»): لا يقل عن {BAND_LABELS[UNKNOWN_KEY_FLOOR]}")
    return Outcome(
        band=band,
        flags=flags,
        reasons=reasons,
        means=means,
        instructions=instructions,
        lives=lives,
        injured=injured,
        answered=sum(1 for q in shown if q.id in answers),
        asked=len(shown),
    )


def clean_answers(content: CardContent, answers: dict[str, Answer]) -> dict[str, Answer]:
    """The answers to questions of the card that are shown; ``ValueError`` for a question the card does not have."""
    ids = {q.id for q in content.questions}
    unknown = sorted(set(answers) - ids)
    if unknown:
        raise ValueError(unknown[0])
    shown = {q.id for q in asked(content, answers)}
    return {k: v for k, v in answers.items() if k in shown}


def summary(
    content: CardContent, version: int, sim: bool, answers: dict[str, Answer], outcome: Outcome, read: list[str]
) -> str:
    """The lines written at the top of the report's text: every reader of the report in the dashboard (the room,
    the committees) sees what was asked and answered. The team reads the card on its mission (``on_scene``)."""
    head = f"[بطاقة الاستقبال: {content.title} · النسخة {version}{' [SIM]' if sim else ''}]"
    lines = [f"{head} المستوى: {BAND_LABELS[outcome.band]}"]
    if outcome.flags:
        lines.append("علامات: " + "، ".join(outcome.flags))
    lines += [f"• {q.text} {ANSWER_LABELS[answers[q.id]]}" for q in asked(content, answers) if q.id in answers]
    titles = [content.instructions[k].title for k in read if k in content.instructions]
    if titles:
        lines.append("تعليمات قُرئت على المتصل: " + "، ".join(titles))
    return "\n".join(lines)


def on_scene(
    content: CardContent, call: dict[str, Answer], field: dict[str, Answer], call_outcome: Outcome
) -> tuple[dict[str, Answer], Outcome]:
    """The card once the team answered from the scene: the team's answers replace the caller's question by question
    (the caller's stay stored), and the result never goes below what the call gave (Yamen, 2026-11-10: the field
    raises the band, it does not lower it; lowering stays the room's decision)."""
    merged = clean_answers(content, {**call, **field})
    outcome = evaluate(content, merged)
    if higher(outcome.band, call_outcome.band) != outcome.band:
        outcome.band = call_outcome.band
        outcome.reasons.append(f"لا ينزل عن مستوى المكالمة: {BAND_LABELS[call_outcome.band]}")
    outcome.lives = outcome.lives or call_outcome.lives
    outcome.injured = outcome.injured or call_outcome.injured
    outcome.flags += [f for f in call_outcome.flags if f not in outcome.flags]
    return merged, outcome


def card_facts(outcome: dict[str, Any] | None) -> dict[str, Any] | None:
    """What the priority reads from a report's card answers (``ai.scoring.Facts.call_card``)."""
    if not outcome:
        return None
    return {"lives": bool(outcome.get("lives")), "injured": bool(outcome.get("injured")), "band": outcome.get("band")}


class Scene(BaseModel):
    """What the teams found, beside what the card gave: the nature they confirmed and the incident's casualties."""

    nature: str | None = None
    injured: int = 0
    serious: int = 0
    deceased: int = 0
    trapped: int = 0
    #: ``nature_differs``, ``lives_not_on_card``, ``injured_not_on_card``, ``band_below_toll`` or ``confirmed``.
    checks: list[str] = []


def compare(category: str, outcome: Outcome, scene: Scene) -> list[str]:
    """Where the card (with the team's answers when there are some) and the team's findings disagree. A general
    call (``sos``, ``other``) has no nature to contradict."""
    checks: list[str] = []
    if scene.nature and category not in ("sos", "other") and scene.nature != category:
        checks.append("nature_differs")
    if not outcome.lives and (scene.deceased or scene.trapped):
        checks.append("lives_not_on_card")
    if not outcome.injured and scene.injured:
        checks.append("injured_not_on_card")
    if outcome.band in ("low", "normal") and (scene.deceased or scene.trapped or scene.serious):
        checks.append("band_below_toll")
    if not checks and (scene.nature or scene.injured or scene.deceased or scene.trapped):
        checks.append("confirmed")
    return checks


class AnswerOut(BaseModel):
    report_id: uuid.UUID
    card_id: uuid.UUID
    category: Category
    card_version: int
    sim: bool
    title: str
    #: The caller's answers and what they gave, with the instructions read to the caller.
    answers: dict[str, Answer]
    outcome: Outcome
    read: list[str] = []
    #: The team's answers from the scene, and what the card gives with them (never below the call's band).
    field_answers: dict[str, Answer] | None = None
    field_outcome: Outcome | None = None
    field_by_name: str | None = None
    field_at: datetime | None = None
    #: What the teams found on the incident, compared with the card (the report page only).
    scene: Scene | None = None
    #: The questions shown for the answers known so far (the team's over the caller's), in the card's order.
    questions: list[Question]
    instructions: dict[str, Instruction]
    created_at: datetime


class CallCardIn(BaseModel):
    """The card answered while the room wrote the call down (``RoomReportIn.call_card``)."""

    model_config = ConfigDict(extra="forbid")

    card_id: uuid.UUID
    version: int
    answers: dict[str, Answer] = Field(default_factory=dict, max_length=20)
    # Instructions the agent read to the caller (keys among those the answers offered).
    read: list[str] = Field(default_factory=list, max_length=12)
