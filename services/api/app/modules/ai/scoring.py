"""Explained scores: priority (BR-20) and reporter credibility (BR-06).

Pure functions. Each score is returned with its components so the operator sees why a report ranks
where it does. The AI only suggests: no score ever changes a report's status (BR-03, BR-06).
"""

import math
from dataclasses import dataclass, field
from typing import Any

from app.modules.ai.settings import PRIORITY_COMPONENTS, PrioritySettings
from app.modules.reports.domain import Category


@dataclass(frozen=True, slots=True)
class Facts:
    """Everything the rules know about one report."""

    category: Category
    reporter_kind: str  # citizen | organization | anonymous
    false_reports: int = 0  # confirmed false reports of this reporter (BR-03, BR-04)
    useful_reports: int = 0  # earlier reports of this reporter that led to an intervention
    stored_media: int = 0
    accuracy_m: float | None = None
    corroborating_reporters: int = 0  # other distinct reporters describing the same event
    extraction: dict[str, Any] | None = None  # language model output, when available
    keywords: dict[str, Any] = field(default_factory=dict)  # lexicon.signals() of all the report's text


def _component(key: str, value: float | None, detail: dict[str, Any]) -> dict[str, Any]:
    return {"key": key, "value": None if value is None else round(min(max(value, 0.0), 1.0), 3), "detail": detail}


def credibility(facts: Facts) -> dict[str, Any]:
    """0 to 100, starting from 50. A suggestion for the operator, never a reason to reject (BR-06)."""
    parts: list[tuple[str, int, dict[str, Any]]] = [("base", 50, {})]
    if facts.reporter_kind != "anonymous":
        parts.append(("registered", 15, {"kind": facts.reporter_kind}))
    if facts.false_reports:
        parts.append(("confirmed_false_reports", -min(15 * facts.false_reports, 45), {"count": facts.false_reports}))
    if facts.useful_reports:
        parts.append(("useful_reports", min(5 * facts.useful_reports, 15), {"count": facts.useful_reports}))
    if facts.stored_media:
        parts.append(("media", 10, {"count": facts.stored_media}))
    if facts.accuracy_m is not None and facts.accuracy_m <= 50:
        parts.append(("precise_location", 5, {"accuracy_m": facts.accuracy_m}))
    elif facts.accuracy_m is not None and facts.accuracy_m > 1000:
        parts.append(("imprecise_location", -5, {"accuracy_m": facts.accuracy_m}))
    if facts.corroborating_reporters:
        parts.append(
            ("corroborated", min(10 * facts.corroborating_reporters, 20), {"reporters": facts.corroborating_reporters})
        )
    score = max(0, min(100, sum(points for _, points, _ in parts)))
    return {"score": score, "components": [{"key": k, "points": p, "detail": d} for k, p, d in parts]}


def _severity(facts: Facts, settings: PrioritySettings) -> tuple[float, dict[str, Any]]:
    table = settings.category_severity
    value = table[facts.category]
    detail: dict[str, Any] = {"category": facts.category.value}
    ex = facts.extraction
    if ex and ex.get("confidence", 0) >= settings.suggestion_min_confidence and ex.get("category") in table:
        suggested = Category(ex["category"])
        if table[suggested] > value:
            # The model may raise the gravity (e.g. "other" that is a fire), never lower what the citizen chose.
            value, detail = table[suggested], {"category": suggested.value, "suggested_by_model": True}
    hazards = sorted(set((ex or {}).get("hazards") or []) | set(facts.keywords.get("hazards") or []))
    if hazards:
        value = min(1.0, value + 0.1 * len(hazards))
        detail["hazards"] = hazards
    return value, detail


def _lives(facts: Facts) -> tuple[float, dict[str, Any]]:
    ex = facts.extraction
    if ex is not None:
        at_risk = bool(ex.get("lives_at_risk") or ex.get("people_trapped") or ex.get("deaths_reported"))
        if at_risk:
            return 1.0, {"source": "model", "people_trapped": bool(ex.get("people_trapped"))}
    if facts.keywords.get("lives_at_risk"):
        return 1.0, {"source": "keywords", "matched": facts.keywords.get("matched", [])}
    if facts.category in (Category.SOS, Category.DROWNING) and ex is None:
        # A one-touch SOS or a drowning without details is presumed to involve a life.
        return 0.7, {"source": "category"}
    return 0.0, {"source": "model" if ex is not None else "keywords"}


def _casualties(facts: Facts) -> tuple[float, dict[str, Any]]:
    ex = facts.extraction
    if ex is not None and (ex.get("injured_count") or ex.get("deaths_reported")):
        count = int(ex.get("injured_count") or 0)
        value = 1.0 if ex.get("deaths_reported") else min(count / 5, 1.0)
        return value, {"source": "model", "injured": count, "deaths": bool(ex.get("deaths_reported"))}
    if facts.keywords.get("deaths"):
        return 1.0, {"source": "keywords", "deaths": True}
    if facts.keywords.get("injured"):
        return 0.4, {"source": "keywords", "injured": True}
    return 0.0, {"source": "model" if ex is not None else "keywords"}


def _reporters(facts: Facts) -> tuple[float, dict[str, Any]]:
    total = 1 + facts.corroborating_reporters
    # 1 reporter → 0, 2 → 0.3, 5 → 0.7, 10 or more → 1.
    return min(math.log10(total), 1.0), {"reporters": total}


def priority(facts: Facts, credibility_score: int, settings: PrioritySettings) -> dict[str, Any]:
    """0 to 100: weighted sum of the BR-20 components that have data, rescaled to the available weights."""
    values: dict[str, tuple[float | None, dict[str, Any]]] = {
        "severity": _severity(facts, settings),
        "lives": _lives(facts),
        "casualties": _casualties(facts),
        "reporters": _reporters(facts),
        "credibility": (credibility_score / 100, {"score": credibility_score}),
        # No data source yet: sensitive sites (later phase) and weather layer (FR-C-08, later phase).
        "sensitive_sites": (None, {"reason": "no_data_yet"}),
        "weather": (None, {"reason": "no_data_yet"}),
    }
    weights = settings.weights
    available = sum(weights[k] for k in PRIORITY_COMPONENTS if values[k][0] is not None) or 1
    components = []
    total = 0.0
    for key in PRIORITY_COMPONENTS:
        value, detail = values[key]
        component = _component(key, value, detail)
        component["weight"] = weights[key]
        points = 0.0 if value is None else 100 * weights[key] * component["value"] / available
        component["points"] = round(points, 1)
        total += points
        components.append(component)
    return {"score": round(min(total, 100)), "components": components}
