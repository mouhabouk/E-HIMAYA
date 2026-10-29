"""The model cards (docs/phase-l/design-l5.md §4.1, item 9): one card of the same shape for every model.

Each card gathers what is known of a model: what it is for, its limits, its data and licences, its figures with their
date and sample (a sample under 30 is flagged), its thresholds as they stand, and the committee's decisions about them
(AI-01). The figures come from the declared evaluation sets (measures/*.json, copied from the services' evaluation
scripts) or, where no such set exists, from the review people actually made (plan reading, written summary).
"""

import json
import math
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import as_system
from app.core.security import Principal, Role
from app.modules.ai import settings as ai_settings
from app.modules.ai.models import Analysis, ModelDecision
from app.modules.audit.models import AuditLog
from app.modules.checklist.models import ChecklistTask
from app.modules.coastal import shadow
from app.modules.modelcards import schemas as s
from app.modules.modelcards.texts import CARDS, LABELS, Lang

MEASURES = Path(__file__).resolve().parent / "measures"
SMALL = 30
# The detectors of the vision service (services/vision/models/fetch_models.py): checked by a test.
FIRE_SMOKE_VERSION = "ehimaya-fire-smoke-yolox-tiny 2.0.0"
PERSON_VERSION = "yolox-tiny-coco-person 0.1.1rc0"
ORDER = ("fire_smoke", "person", "report_reading", "written_summary", "plan_reading", "drowning")
FAMILY = {
    "fire_smoke": "vision",
    "person": "vision",
    "report_reading": "language",
    "written_summary": "language",
    "plan_reading": "language",
    "drowning": "tabular",
}
LICENCES = {
    "fire_smoke": ["Apache-2.0 (YOLOX)", "CC BY 2.0 / CC BY 4.0 (Open Images V7)", "MIT (FireNET)", "CC0-1.0 (FURG)"],
    "person": ["Apache-2.0 (YOLOX)", "CC BY 4.0 (COCO 2017)"],
    "report_reading": ["Apache-2.0 (Qwen3)", "MIT (Ollama)"],
    "written_summary": ["Apache-2.0 (Qwen3)", "MIT (Ollama)"],
    "plan_reading": ["Apache-2.0 (Qwen3)", "MIT (Ollama)", "BSD-3-Clause (pypdf)"],
    "drowning": ["BSD-3-Clause (scikit-learn)"],
}


class UnknownModel(LookupError):
    pass


def readers(principal: Principal) -> bool:
    return principal.is_national and bool(principal.roles & {Role.AI_ADMIN, Role.CENTRAL_COMMITTEE})


def deciders(principal: Principal) -> bool:
    """The committee decides (AI-01); the AI administrator prepares and trains, but does not approve."""
    return principal.is_national and Role.CENTRAL_COMMITTEE in principal.roles


def _load(name: str) -> dict[str, Any] | None:
    path = MEASURES / name
    return json.loads(path.read_text()) if path.exists() else None


def _pct(lang: Lang, value: float | None) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return f"{round(value * 100)}{'٪' if lang == 'ar' else ' %' if lang == 'fr' else '%'}"


def _num(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _count(lang: Lang, k: int, n: int) -> str:
    return f"{k}/{n} ({_pct(lang, k / n)})" if n else "—"


def _interval(lang: Lang, bounds: list[float] | None) -> str:
    return f"{_pct(lang, bounds[0])}–{_pct(lang, bounds[1])}" if bounds else "—"


# ---------------------------------------------------------------- figures of each model


def _vision_tables(lang: Lang, labels: tuple[str, ...]) -> list[s.Table]:
    t = LABELS[lang]
    overall = _load("vision.json")
    tables: list[s.Table] = []
    if overall is None:
        return tables
    rows: list[list[str]] = []
    for label in labels:
        figures = overall["labels"][label]
        for threshold in ("0.45", "0.6"):
            f = figures[threshold]
            missed = f"{f['fn']}/{figures['positives']}" if f.get("fn") is not None else "—"
            rows.append([t[f"r.{label}"], threshold, _num(f["precision"]), _num(f["recall"]), missed])
    tables.append(
        s.Table(
            key="overall",
            title=t["m.overall"],
            measured_on=date.fromisoformat(overall["measured_on"]),
            columns=[t["c.label"], t["c.threshold"], t["c.precision"], t["c.recall"], t["c.missed"]],
            rows=rows,
            note=f"{overall['sample']} · {overall['source']}",
        )
    )
    if "fire" not in labels:
        return tables
    conditions = _load("vision_conditions.json")
    if conditions is not None:
        for label in ("fire", "smoke"):
            data = conditions["labels"][label]
            groups = [("r.all", data["all"])] + [
                (f"r.{dimension}.{value}", figures)
                for dimension, values in data["conditions"].items()
                for value, figures in values.items()
            ]
            table_rows: list[list[str]] = []
            small: list[int] = []
            for key, figures in groups:
                at = figures["0.45"]
                if figures["images"] == 0:
                    continue
                if figures["small"]:
                    small.append(len(table_rows))
                table_rows.append(
                    [
                        t[key],
                        str(figures["images"]),
                        _count(lang, at["missed"], figures["images"]),
                        _interval(lang, at["interval"]),
                    ]
                )
            tables.append(
                s.Table(
                    key=f"conditions_{label}",
                    title=t[f"m.conditions_{label}"],
                    measured_on=date.fromisoformat(conditions["measured_on"]),
                    columns=[t["c.condition"], t["c.images"], t["c.missed"], t["c.interval"]],
                    rows=table_rows,
                    small_rows=small,
                    note=t["small"] if small else None,
                )
            )
    hard = overall["hard_negatives"]
    tables.append(
        s.Table(
            key="hard_negatives",
            title=t["m.hard_negatives"],
            measured_on=date.fromisoformat(overall["measured_on"]),
            columns=[t["c.label"], "0.45", "0.6"],
            rows=[
                [t[f"r.{label}"], _pct(lang, hard[label]["0.45"]), _pct(lang, hard[label]["0.6"])] for label in labels
            ],
            note=str(hard["images"]),
        )
    )
    return tables


def _report_tables(lang: Lang) -> list[s.Table]:
    t = LABELS[lang]
    measured = _load("reports.json")
    columns = [
        t["c.variety"],
        t["c.reports"],
        t["c.lives_missed"],
        t["c.interval"],
        t["c.category_missed"],
        t["c.invalid"],
    ]
    if measured is None:
        return [s.Table(key="reports", title=t["m.reports"], columns=columns, rows=[], note=t["not_measured"])]
    rows: list[list[str]] = []
    small: list[int] = []
    for name, figures in [("all", measured["all"]), *measured["varieties"].items()]:
        lives, category, invalid = figures["lives_missed"], figures["category_missed"], figures["invalid"]
        if lives["small"]:
            small.append(len(rows))
        rows.append(
            [
                t[f"r.{name}"],
                str(figures["reports"]),
                _count(lang, lives["count"], lives["of"]),
                _interval(lang, lives["interval"]),
                _count(lang, category["count"], category["of"]),
                _count(lang, invalid["count"], invalid["of"]),
            ]
        )
    return [
        s.Table(
            key="reports",
            title=t["m.reports"],
            measured_on=date.fromisoformat(measured["measured_on"]),
            simulated=True,
            columns=columns,
            rows=rows,
            small_rows=small,
            note=f"{measured['model']}" + (f" · {t['small']}" if small else ""),
        )
    ]


async def _summary_tables(session: AsyncSession, lang: Lang, now: datetime) -> list[s.Table]:
    t = LABELS[lang]
    supported = AuditLog.details["supported"].as_boolean()
    async with as_system(session):
        shown, refused = (
            await session.execute(
                select(func.count().filter(supported.is_(True)), func.count().filter(supported.is_(False))).where(
                    AuditLog.action == "window.summary", AuditLog.at >= now - timedelta(days=90)
                )
            )
        ).one()
    counts = {True: int(shown), False: int(refused)}
    total = sum(counts.values())
    return [
        s.Table(
            key="summary",
            title=t["m.summary"],
            measured_on=now.date(),
            columns=[t["c.measure"], t["c.value"]],
            rows=[
                [t["r.supported"], _count(lang, counts.get(True, 0), total)],
                [t["r.refused"], _count(lang, counts.get(False, 0), total)],
            ],
            small_rows=[0, 1] if total < SMALL else [],
            note=t["small"] if total < SMALL else None,
        )
    ]


async def _plan_tables(session: AsyncSession, lang: Lang, now: datetime) -> list[s.Table]:
    t = LABELS[lang]
    async with as_system(session):
        by_review = dict(
            (
                await session.execute(
                    select(ChecklistTask.review, func.count())
                    .where(ChecklistTask.origin == "ai")
                    .group_by(ChecklistTask.review)
                )
            ).all()
        )
        found = int(
            await session.scalar(
                select(func.count()).where(ChecklistTask.origin == "ai", ChecklistTask.quote_found.is_(True))
            )
            or 0
        )
        added = int(await session.scalar(select(func.count()).where(ChecklistTask.origin == "manual")) or 0)
    suggested = sum(int(n) for n in by_review.values())
    rows = [[t["r.suggested"], str(suggested)]]
    for review, key in (("accepted", "r.accepted"), ("edited", "r.edited"), ("deleted", "r.deleted")):
        rows.append([t[key], _count(lang, int(by_review.get(review, 0)), suggested)])
    rows += [
        [t["r.waiting"], str(int(by_review.get("suggested", 0)))],
        [t["r.quote_found"], _count(lang, found, suggested)],
        [t["r.added"], str(added)],
    ]
    return [
        s.Table(
            key="plan",
            title=t["m.plan"],
            measured_on=now.date(),
            columns=[t["c.measure"], t["c.value"]],
            rows=rows,
            small_rows=list(range(len(rows))) if suggested < SMALL else [],
            note=t["small"] if suggested < SMALL else None,
        )
    ]


async def _drowning_tables(session: AsyncSession, lang: Lang, model: Any, now: datetime) -> list[s.Table]:
    t = LABELS[lang]
    if model is None:
        return [s.Table(key="drowning", title=t["m.drowning"], columns=[], rows=[], note=t["not_measured"])]
    m = model.metrics

    def flagged(levels: dict[str, float]) -> float:
        return levels["yellow"] + levels["red"]

    tables = [
        s.Table(
            key="drowning",
            title=t["m.drowning"],
            measured_on=model.trained_at.date(),
            simulated=True,
            columns=[t["c.measure"], t["c.model"], t["c.rules"]],
            rows=[
                [t["r.auc"], _num(m["auc"]["model"]), _num(m["auc"]["rules"])],
                [
                    t["r.missed_rate"],
                    _count(lang, m["caught"]["model"]["missed"], m["caught"]["model"]["drowning_days"]),
                    _count(lang, m["caught"]["rules"]["missed"], m["caught"]["rules"]["drowning_days"]),
                ],
                [
                    t["r.flagged"],
                    _pct(lang, flagged(m["flagged"]["model"])),
                    _pct(lang, flagged(m["flagged"]["rules"])),
                ],
                [t["r.agreement"], _pct(lang, m["agreement"]), ""],
            ],
            note=f"{m['test_days']} · {t['sim']}",
        )
    ]
    compared = await shadow.comparison(session, now.date() - timedelta(days=30))
    rows = [
        [d["day"], str(d["beaches"]), str(d["same"]), str(d["model_higher"]), str(d["model_lower"])]
        for d in compared["days"][-14:]
    ]
    total = compared["total"]
    if total["beaches"]:
        rows.append(
            [
                t["r.all"],
                str(total["beaches"]),
                str(total["same"]),
                str(total["model_higher"]),
                str(total["model_lower"]),
            ]
        )
    tables.append(
        s.Table(
            key="shadow",
            title=t["m.shadow"],
            measured_on=now.date(),
            simulated=True,
            columns=[t["c.day"], t["c.beaches"], t["c.same"], t["c.higher"], t["c.lower"]],
            rows=rows,
            note=None if rows else t["not_measured"],
        )
    )
    return tables


# ---------------------------------------------------------------- versions, thresholds, decisions


async def _llm_of_reports(session: AsyncSession) -> str:
    async with as_system(session):
        model = await session.scalar(
            select(Analysis.models["extract"].as_string())
            .where(Analysis.models["extract"].as_string().is_not(None))
            .order_by(Analysis.completed_at.desc().nulls_last())
            .limit(1)
        )
    measured = _load("reports.json")
    return str(model or (measured or {}).get("model") or "qwen3")


async def _versions(session: AsyncSession, model: Any) -> dict[str, str]:
    assistant = get_settings().assistant_model
    return {
        "fire_smoke": FIRE_SMOKE_VERSION,
        "person": PERSON_VERSION,
        "report_reading": await _llm_of_reports(session),
        "written_summary": assistant,
        "plan_reading": assistant,
        "drowning": f"v{model.version}" if model is not None else "—",
    }


def _thresholds(lang: Lang, card: str, ai: ai_settings.AiSettings, model: Any) -> list[s.Threshold]:
    t = LABELS[lang]
    config = get_settings()
    values: dict[str, float | bool | None]
    if card == "fire_smoke":
        values = {
            "vision_min_confidence": config.vision_min_confidence,
            "vision_alert_confidence": config.vision_alert_confidence,
        }
    elif card == "person":
        values = {"vision_min_confidence": config.vision_min_confidence}
    elif card == "report_reading":
        values = {"suggestion_min_confidence": ai.priority.suggestion_min_confidence}
    elif card == "plan_reading":
        values = {"plan_reading": ai.assist.plan_reading}
    elif card == "drowning":
        cutoffs = model.params["cutoffs"] if model is not None else {}
        values = {"yellow": cutoffs.get("yellow"), "red": cutoffs.get("red")}
    else:
        values = {"none": None}
    return [s.Threshold(key=key, label=t[f"t.{key}"], value=value) for key, value in values.items()]


def _status(card: str, version: str, thresholds: list[s.Threshold], decisions: list[ModelDecision]) -> s.Status:
    if not decisions:
        return "shadow" if card == "drowning" else "pending"
    latest = decisions[0]
    if latest.decision == "withdrawn":
        return "shadow" if card == "drowning" else "withdrawn"
    current = {th.key: th.value for th in thresholds}
    return "approved" if latest.version == version and latest.thresholds == current else "changed"


async def cards(session: AsyncSession, principal: Principal, lang: Lang) -> s.CardsOut:
    now = datetime.now(UTC)
    ai = await ai_settings.load(session)
    model = await shadow.latest(session)
    versions = await _versions(session, model)
    history: dict[str, list[ModelDecision]] = {}
    for row in (await session.scalars(select(ModelDecision).order_by(ModelDecision.decided_at.desc()))).all():
        history.setdefault(row.model, []).append(row)
    items = []
    for card in ORDER:
        text = CARDS[card][lang]
        thresholds = _thresholds(lang, card, ai, model)
        decisions = history.get(card, [])[:10]
        status = _status(card, versions[card], thresholds, decisions)
        if card in ("fire_smoke", "person"):
            measures = _vision_tables(lang, ("fire", "smoke") if card == "fire_smoke" else ("person",))
        elif card == "report_reading":
            measures = _report_tables(lang)
        elif card == "written_summary":
            measures = await _summary_tables(session, lang, now)
        elif card == "plan_reading":
            measures = await _plan_tables(session, lang, now)
        else:
            measures = await _drowning_tables(session, lang, model, now)
        items.append(
            s.CardOut(
                id=card,
                name=text["name"],
                family=FAMILY[card],
                version=versions[card],
                licences=LICENCES[card],
                simulated=card == "drowning",
                status=status,
                status_label=LABELS[lang][f"status.{status}"],
                use=text["use"],
                limits=text["limits"],
                data=text["data"],
                measures=measures,
                thresholds=thresholds,
                decisions=[
                    s.DecisionOut(
                        decision=d.decision,
                        version=d.version,
                        thresholds=d.thresholds,
                        reference=d.reference,
                        note=d.note,
                        decided_by_name=d.decided_by_name,
                        decided_at=d.decided_at,
                    )
                    for d in decisions
                ],
                can_decide=deciders(principal) and (card != "drowning" or model is not None),
                can_train=card == "drowning" and readers(principal),
            )
        )
    return s.CardsOut(items=items, generated_at=now)


async def card(session: AsyncSession, principal: Principal, card_id: str, lang: Lang) -> s.CardOut:
    if card_id not in ORDER:
        raise UnknownModel(card_id)
    return next(c for c in (await cards(session, principal, lang)).items if c.id == card_id)


async def decide(
    session: AsyncSession, principal: Principal, card_id: str, body: s.DecisionIn, name: str
) -> ModelDecision:
    current = await card(session, principal, card_id, "en")
    row = ModelDecision(
        model=card_id,
        decision=body.decision,
        thresholds={th.key: th.value for th in current.thresholds},
        version=current.version,
        reference=body.reference.strip(),
        note=body.note.strip(),
        decided_by_name=name,
    )
    session.add(row)
    await session.flush()
    return row
