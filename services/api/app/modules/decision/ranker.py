"""The learned ranking of the commander's proposals (AI5c, docs/phase-ai5/design-ai5.md §7.3), in shadow.

It learns, from the decided proposals of ``decision.command_decision``, how likely a commander is to adopt a proposal
in a given situation: the proposal (its kind, its subject, its confidence, its rank among the rules, whether the
commander typed it) and the anonymous snapshot of the situation it was made in (``features``: category, level,
reports, lives at risk, injured, weather, resources engaged…). The label is the commander's decision, corrected by
what happened next (outcomes.py): a rejected proposal of resources followed by the same resources counts as needed.
A rejection because the proposal was "already done" says nothing about its rank and is left out.

Logistic regression (scikit-learn, to fit only) on one-hot and log-scaled features, stored as plain numbers and
applied in pure Python (as learning/textmodel.py). The incidents are split once and for all (``split_of``): a model
is measured on incidents it never saw. The measure is the one the commander feels, **the first proposal**: over the
held-out incidents where the commander adopted some proposals and rejected others, how often the proposal ranked
first was one they adopted, for the model and for the rules' own order. The model never reorders the board: it runs
in shadow, and its figures are compared with the rules' in the training centre and the commander's model card, until
the committee decides (AI-01).
"""

import math
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.decision.models import CommandDecision
from app.modules.learning import textmodel
from app.modules.learning.models import LearnedModel
from app.modules.learning.samples import split_of

TASK = "command_ranker"
ALGORITHM = "one-hot + log-scaled situation features + scikit-learn LogisticRegression"
MIN_TRAIN = 30
MIN_HELDOUT = 10
# Held-out incidents with both an adopted and a rejected proposal, at least, to measure the first proposal.
MIN_RANKED_INCIDENTS = 5
MIN_COUNT = 2
CONFIDENCE = {"high": 0, "medium": 1, "low": 2}
# Not learnt from: the hour is kept as a part of the day, the identifiers never.
_SKIP = {"hour", "gouvernorat_code"}


@dataclass(frozen=True)
class Example:
    incident: str
    split: str
    origin: str
    rule_rank: int
    confidence: str
    created_at: datetime
    x: dict[str, float]
    y: int


def label_of(row: CommandDecision) -> int | None:
    if row.status in ("adopted", "modified"):
        return 1
    if row.status != "rejected" or row.reason_code == "already_done":
        return None
    return 1 if (row.outcome or {}).get("needed_later") else 0


def _part_of_day(hour: Any) -> str | None:
    if not isinstance(hour, int):
        return None
    return "night" if hour < 6 else "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"


def features_of(row: CommandDecision) -> dict[str, float]:
    """The proposal and its situation as named numbers: one-hot for words, log1p for counts."""
    f = row.features or {}
    x: dict[str, float] = {
        f"origin={row.origin}": 1.0,
        f"kind={row.kind}": 1.0,
        f"key={row.key}": 1.0,
        f"confidence={row.confidence}": 1.0,
        f"key={row.key}|category={f.get('category')}": 1.0,
    }
    part = _part_of_day(f.get("hour"))
    if part:
        x[f"day={part}"] = 1.0
    for name, value in f.items():
        if name in _SKIP or value is None:
            continue
        if isinstance(value, bool):
            if value:
                x[name] = 1.0
        elif isinstance(value, int | float):
            x[name] = math.log1p(max(float(value), 0.0))
        elif isinstance(value, str):
            x[f"{name}={value}"] = 1.0
        elif isinstance(value, list):
            for item in value:
                x[f"{name}={item}"] = 1.0
        elif isinstance(value, dict):
            for item, n in value.items():
                if isinstance(n, int | float) and not isinstance(n, bool):
                    x[f"{name}.{item}"] = math.log1p(max(float(n), 0.0))
    return x


def example(row: CommandDecision) -> Example | None:
    y = label_of(row)
    if y is None:
        return None
    incident = str(row.incident_id)
    rank = row.features.get("rule_rank") if row.features else None
    return Example(
        incident=incident,
        split=split_of(incident),
        origin=row.origin,
        rule_rank=rank if isinstance(rank, int) else 99,
        confidence=row.confidence,
        created_at=row.created_at,
        x=features_of(row),
        y=y,
    )


def fit(examples: Sequence[Example]) -> dict[str, Any]:
    """Fits the ranker; its parameters as plain numbers (names seen in at least MIN_COUNT examples)."""
    from scipy.sparse import csr_matrix
    from sklearn.linear_model import LogisticRegression

    counts: dict[str, int] = defaultdict(int)
    for e in examples:
        for name in e.x:
            counts[name] += 1
    vocabulary = sorted(n for n, c in counts.items() if c >= MIN_COUNT)
    index = {n: i for i, n in enumerate(vocabulary)}
    rows, cols, values = [], [], []
    for r, e in enumerate(examples):
        for name, v in e.x.items():
            if name in index:
                rows.append(r)
                cols.append(index[name])
                values.append(v)
    matrix = csr_matrix((values, (rows, cols)), shape=(len(examples), len(vocabulary)))
    model = LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced")
    model.fit(matrix, [e.y for e in examples])
    return {
        "vocabulary": vocabulary,
        "coef": [round(float(c), 5) for c in model.coef_[0]],
        "intercept": round(float(model.intercept_[0]), 5),
    }


class Ranker:
    """A stored ranker ready to apply."""

    def __init__(self, params: dict[str, Any]) -> None:
        self._weights = dict(zip(params["vocabulary"], params["coef"], strict=True))
        self._intercept = float(params["intercept"])

    def probability(self, x: dict[str, float]) -> float:
        z = self._intercept + sum(self._weights.get(n, 0.0) * v for n, v in x.items())
        return 1.0 / (1.0 + math.exp(-max(min(z, 30.0), -30.0)))


def rules_order(e: Example) -> tuple[int, int, int, float]:
    """The board's own order: the commander's orders first, then the rules in their order, then by confidence."""
    return (0 if e.origin == "order" else 1, e.rule_rank, CONFIDENCE.get(e.confidence, 3), e.created_at.timestamp())


def first_proposal(examples: Iterable[Example], ranker: Ranker | None) -> dict[str, int]:
    """Over the incidents with both an adopted and a rejected proposal: how often the one ranked first was adopted,
    by the rules' order and by the model (``model`` absent without a ranker)."""
    by_incident: dict[str, list[Example]] = defaultdict(list)
    for e in examples:
        by_incident[e.incident].append(e)
    out = {"incidents": 0, "rules": 0, "model": 0}
    for group in by_incident.values():
        if len({e.y for e in group}) < 2:
            continue
        out["incidents"] += 1
        out["rules"] += min(group, key=rules_order).y
        if ranker is not None:
            # Ties keep the rules' order.
            out["model"] += min(group, key=lambda e: (-ranker.probability(e.x), rules_order(e))).y
    if ranker is None:
        del out["model"]
    return out


def _rate(k: int, n: int) -> float:
    return round(k / n, 4) if n else 0.0


async def examples_of(session: AsyncSession, since: datetime | None = None) -> list[Example]:
    query = select(CommandDecision).where(CommandDecision.decided_at.is_not(None))
    if since is not None:
        query = query.where(CommandDecision.decided_at > since)
    out = []
    for row in await session.scalars(query.order_by(CommandDecision.decided_at)):
        e = example(row)
        if e is not None:
            out.append(e)
    return out


async def current(session: AsyncSession) -> LearnedModel | None:
    return await session.scalar(select(LearnedModel).where(LearnedModel.task == TASK, LearnedModel.state == "current"))


async def train(session: AsyncSession, actor_name: str) -> tuple[dict[str, Any], LearnedModel | None]:
    """Fits a new version, measures it, the current one and the rules on the same held-out incidents, keeps the
    better model (shadow either way)."""
    examples = await examples_of(session)
    train_set = [e for e in examples if e.split == "train"]
    heldout = [e for e in examples if e.split == "heldout"]
    rules_only = first_proposal(heldout, None)
    counts = {
        "train": len(train_set),
        "heldout": len(heldout),
        "ranked_incidents": rules_only["incidents"],
        "adopted_share": _rate(sum(e.y for e in examples), len(examples)),
    }
    if (
        len(train_set) < MIN_TRAIN
        or len(heldout) < MIN_HELDOUT
        or len({e.y for e in train_set}) < 2
        or rules_only["incidents"] < MIN_RANKED_INCIDENTS
    ):
        needed = {"train": MIN_TRAIN, "heldout": MIN_HELDOUT, "ranked_incidents": MIN_RANKED_INCIDENTS}
        return {"skipped": "too_few_samples", **counts, "needed": needed}, None

    params = fit(train_set)
    ranker = Ranker(params)
    truth = ["yes" if e.y else "no" for e in heldout]
    new = first_proposal(heldout, ranker)
    old_model = await current(session)
    old = first_proposal(heldout, Ranker(old_model.params)) if old_model is not None else None
    n = new["incidents"]
    metrics: dict[str, Any] = {
        **counts,
        "model": textmodel.scores(truth, ["yes" if ranker.probability(e.x) >= 0.5 else "no" for e in heldout]),
        "ranking": {
            "incidents": n,
            "model": new["model"],
            "rules": new["rules"],
            "current": old["model"] if old else None,
            "top1": _rate(new["model"], n),
            "rules_top1": _rate(new["rules"], n),
            "current_top1": _rate(old["model"], n) if old else None,
        },
        "current_version": old_model.version if old_model else None,
    }
    metrics["top1"] = metrics["ranking"]["top1"]
    better = old is None or new["model"] > old["model"]
    version = int(
        await session.scalar(select(func.coalesce(func.max(LearnedModel.version), 0)).where(LearnedModel.task == TASK))
        or 0
    )
    if better and old_model is not None:
        old_model.state = "retired"
        await session.flush()
    row = LearnedModel(
        task=TASK,
        version=version + 1,
        algorithm=ALGORITHM,
        params=params,
        metrics=metrics,
        primary_metric="top1",
        state="current" if better else "rejected",
        train_samples=len(train_set),
        heldout_samples=len(heldout),
        trained_by_name=actor_name,
    )
    session.add(row)
    await session.flush()
    result = {"promoted": better, "version": row.version, "primary": metrics["top1"], **counts}
    return {**result, "rules_top1": metrics["ranking"]["rules_top1"]}, row


async def since_training(session: AsyncSession, model: LearnedModel) -> dict[str, int]:
    """The shadow on the decisions taken after the model was trained (never seen by it): first proposal adopted, by
    the model and by the rules."""
    return first_proposal(await examples_of(session, model.trained_at), Ranker(model.params))
