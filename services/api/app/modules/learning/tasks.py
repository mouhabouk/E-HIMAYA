"""The trainings of the training centre (docs/learning.md §3). Each one is a ``Task``: what it learns, from what, and
how it runs. The system administrator launches them, or schedules them (setting ``learning.schedule``).

| task            | learns                                     | from                                       | runs    |
|-----------------|--------------------------------------------|--------------------------------------------|---------|
| report_category | the type of incident from the text         | report samples (weak + operator)           | worker  |
| report_lives    | "lives at risk" from the text              | report samples (LLM + operator)            | worker  |
| report_rejected | reports the room rejects (false, duplicate)  | report samples (final status + operator) | worker  |
| derja_words     | new Derja words and spellings to review    | the training texts                         | worker  |
| fire_smoke      | the fire and smoke detector                | photos and frames of the media library     | trainer |

A text model is promoted (``current``) only when it beats the current one on the same heldout samples; it then runs
in shadow (AI-01). The fire and smoke detector needs a GPU: the job prepares the image set (``vision_dataset``) and
waits for the trainer (services/vision/training), which reports its figures back.
"""

import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai import lexicon
from app.modules.learning import textmodel
from app.modules.learning.models import LearnedModel, Sample
from app.modules.learning.samples import OPERATOR_WEIGHT, SOURCE_REPORT
from app.modules.moderation.normalize import tokens
from app.modules.moderation.terms import BUILT_IN
from app.modules.reports.models import Media
from app.modules.streams.models import StreamDetection

Runner = Literal["worker", "trainer"]
# Fewer samples than this, or a single class: nothing is learnt, the job ends "skipped".
MIN_TRAIN = 30
MIN_HELDOUT = 10
# The heldout figures use only the confirmed labels when there are at least this many.
MIN_CONFIRMED_HELDOUT = 20


@dataclass(frozen=True)
class Task:
    key: str
    runner: Runner
    label_key: str | None = None
    primary_metric: str = "macro_f1"


TASKS: dict[str, Task] = {
    t.key: t
    for t in (
        Task("report_category", "worker", "category"),
        Task("report_lives", "worker", "lives_at_risk"),
        Task("report_rejected", "worker", "rejected"),
        Task("derja_words", "worker", primary_metric="candidates"),
        Task("fire_smoke", "trainer", primary_metric="map50"),
    )
}


def _value(label: dict[str, Any], key: str) -> str | None:
    value = label.get(key)
    if value is None:
        return None
    return ("yes" if value else "no") if isinstance(value, bool) else str(value)


async def _rows(session: AsyncSession, key: str) -> list[tuple[str, str, str, bool]]:
    """(split, text, label, confirmed) of the report samples that carry ``key``."""
    out = []
    for sample in await session.scalars(select(Sample).where(Sample.source == SOURCE_REPORT)):
        value = _value(sample.label, key)
        if value is not None:
            out.append((sample.split, sample.text, value, key in (sample.label.get("confirmed") or [])))
    return out


async def current_model(session: AsyncSession, task: str) -> LearnedModel | None:
    return await session.scalar(select(LearnedModel).where(LearnedModel.task == task, LearnedModel.state == "current"))


def _baseline(task: Task, texts: list[str]) -> list[str] | None:
    """What the system answers today without the model: the keyword lexicon for lives at risk."""
    if task.key == "report_lives":
        return ["yes" if lexicon.signals(t)["lives_at_risk"] else "no" for t in texts]
    return None


async def train_text(session: AsyncSession, task: Task, actor_name: str) -> tuple[dict[str, Any], LearnedModel | None]:
    """Fits a new version, measures it and the current one on the same heldout samples, keeps the better."""
    assert task.label_key is not None
    rows = await _rows(session, task.label_key)
    train = [r for r in rows if r[0] == "train"]
    heldout = [r for r in rows if r[0] == "heldout"]
    confirmed_heldout = [r for r in heldout if r[3]]
    evaluation = confirmed_heldout if len(confirmed_heldout) >= MIN_CONFIRMED_HELDOUT else heldout
    counts = {
        "train": len(train),
        "train_confirmed": sum(r[3] for r in train),
        "heldout": len(heldout),
        "heldout_confirmed": len(confirmed_heldout),
        "evaluated_on": "confirmed" if evaluation is confirmed_heldout else "all",
    }
    if len(train) < MIN_TRAIN or len(evaluation) < MIN_HELDOUT or len({r[2] for r in train}) < 2:
        return {"skipped": "too_few_samples", **counts, "needed": {"train": MIN_TRAIN, "heldout": MIN_HELDOUT}}, None

    params = textmodel.fit(
        [r[1] for r in train], [r[2] for r in train], [OPERATOR_WEIGHT if r[3] else 1.0 for r in train]
    )
    texts, truth = [r[1] for r in evaluation], [r[2] for r in evaluation]
    new = textmodel.scores(truth, [textmodel.Classifier(params).predict(t) for t in texts])
    current = await current_model(session, task.key)
    old = textmodel.scores(truth, [textmodel.Classifier(current.params).predict(t) for t in texts]) if current else None
    baseline_predictions = _baseline(task, texts)
    metrics: dict[str, Any] = {
        **counts,
        "model": new,
        "current": old,
        "current_version": current.version if current else None,
        "baseline": textmodel.scores(truth, baseline_predictions) if baseline_predictions else None,
    }
    better = old is None or new[task.primary_metric] > old[task.primary_metric]
    version = int(
        await session.scalar(
            select(func.coalesce(func.max(LearnedModel.version), 0)).where(LearnedModel.task == task.key)
        )
        or 0
    )
    if better and current is not None:
        current.state = "retired"
        await session.flush()
    row = LearnedModel(
        task=task.key,
        version=version + 1,
        algorithm=textmodel.ALGORITHM,
        params=params,
        metrics=metrics,
        primary_metric=task.primary_metric,
        state="current" if better else "rejected",
        train_samples=len(train),
        heldout_samples=len(evaluation),
        trained_by_name=actor_name,
    )
    session.add(row)
    await session.flush()
    return {"promoted": better, "version": row.version, "primary": new[task.primary_metric], **counts}, row


# ---------------------------------------------------------------- new Derja words


def _known() -> set[str]:
    known: set[str] = set()
    groups = (lexicon.LIVES, lexicon.INJURED, lexicon.DEATHS, *lexicon.HAZARDS.values(), BUILT_IN)
    for group in groups:
        for term in group:
            known.update(tokens(term))
    return known


# Short and very common words (Derja, MSA, French, English) never worth a review.
_STOP = set(
    tokens(
        "في من على و او ما لا هو هي انا احنا فما فيه فيها عند الي اللي متاع هذا هاذا هذي برشا توا كان اما مش موش "
        "fi men 3la w ou ma la howa hiya ana a7na fama fih fiha 3and eli mta3 hedha tawa ken amma mouch "
        "le la les de des du un une et est dans pour sur pas au aux il elle on nous vous ils "
        "the a an of to in on is are"
    )
)
_TAGS = {"phone", "email", "url", "plate", "number", "name"}
MIN_WORD_COUNT = 3
MAX_CANDIDATES = 150


async def derja_words(session: AsyncSession) -> dict[str, Any]:
    """Words the report texts use often that no list knows yet, with the category they come with most: candidates for
    the Derja lexicon (synonyms, new spellings), the respectful-language list or the keyword signals. Reviewed by a
    person; nothing is added on its own."""
    known = _known() | _STOP | _TAGS
    counts: Counter[str] = Counter()
    by_category: dict[str, Counter[str]] = {}
    texts = 0
    for sample in await session.scalars(select(Sample).where(Sample.source == SOURCE_REPORT)):
        texts += 1
        words = {w for w in tokens(sample.text) if len(w) >= 3 and not w.isdigit() and w not in known}
        counts.update(words)
        category = str(sample.label.get("category") or "other")
        for word in words:
            by_category.setdefault(word, Counter())[category] += 1
    candidates = [
        {
            "word": word,
            "count": n,
            "script": "latn" if word.isascii() else "ar",
            "category": by_category[word].most_common(1)[0][0],
        }
        for word, n in counts.most_common()
        if n >= MIN_WORD_COUNT
    ][:MAX_CANDIDATES]
    return {"texts": texts, "candidates": candidates, "count": len(candidates)}


# ---------------------------------------------------------------- fire and smoke image set


async def vision_dataset(session: AsyncSession, store_link: Any, limit: int = 5000) -> dict[str, Any]:
    """The images of the media library with the boxes the detector drew (pseudo-labels for the next detector) and
    whether the 3-of-5 confirmation held: a manifest the GPU trainer downloads (short-lived links)."""
    rows = (
        await session.execute(
            select(Media.id, Media.object_key, StreamDetection.label, StreamDetection.boxes, StreamDetection.confirmed)
            .join(StreamDetection, StreamDetection.media_id == Media.id)
            .where(Media.kind == "image", Media.status == "verified")
            .order_by(Media.id)
            .limit(limit)
        )
    ).all()
    images: dict[uuid.UUID, dict[str, Any]] = {}
    for media_id, key, label, boxes, confirmed in rows:
        item = images.setdefault(
            media_id, {"id": str(media_id), "url": store_link(key), "boxes": [], "confirmed": False}
        )
        item["boxes"].extend({"label": label, "box": [round(float(v), 4) for v in b[:4]]} for b in boxes or [])
        item["confirmed"] = item["confirmed"] or bool(confirmed)
    listed = list(images.values())
    return {
        "images": len(listed),
        "confirmed": sum(i["confirmed"] for i in listed),
        "boxes": {name: sum(1 for i in listed for b in i["boxes"] if b["label"] == name) for name in ("fire", "smoke")},
        "manifest": listed,
    }
