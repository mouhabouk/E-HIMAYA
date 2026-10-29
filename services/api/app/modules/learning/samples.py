"""Report texts into training samples, and the operator's confirmation of the reading (docs/learning.md §2).

A closed or rejected report becomes one sample: its text and the transcripts of its voice and video messages,
anonymised (anonymize.py) and encrypted. Its labels are read from the system first (weak labels):

* ``category``: the local language model's reading when there is one (its knowledge passes to the small model:
  self-training), else the category the citizen chose;
* ``lives_at_risk``: the language model's reading (none without it);
* ``rejected``: the report was rejected (false, duplicate or not an emergency).

The operator may confirm or correct them when the report ends (``confirm``); a confirmed label is never overwritten by
a weak one and weighs ``OPERATOR_WEIGHT`` times more in training. The commander's labels (AI5c) work the same way.
"""

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Text, cast, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.models import Analysis
from app.modules.identity.models import Profile
from app.modules.learning.anonymize import anonymize
from app.modules.learning.models import Sample
from app.modules.reports.domain import Category, Status
from app.modules.reports.models import Media, Report

SOURCE_REPORT = "report"
LABEL_KEYS = ("category", "lives_at_risk", "rejected")
OPERATOR_WEIGHT = 3.0
HELDOUT_EVERY = 5
BATCH = 500
_FINAL = (Status.CLOSED.value, Status.REJECTED.value)


def split_of(key: str) -> str:
    """Fixed side of a sample: one in HELDOUT_EVERY goes to heldout, from a hash (never changes, never random)."""
    return "heldout" if int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % HELDOUT_EVERY == 0 else "train"


def weak_labels(report: Report, extraction: dict[str, Any] | None) -> dict[str, Any]:
    category = report.category
    lives: bool | None = None
    if extraction:
        if extraction.get("category") in {c.value for c in Category}:
            category = extraction["category"]
        if isinstance(extraction.get("lives_at_risk"), bool):
            lives = extraction["lives_at_risk"]
    return {"category": category, "lives_at_risk": lives, "rejected": report.status == Status.REJECTED.value}


def merged(current: dict[str, Any] | None, weak: dict[str, Any]) -> dict[str, Any]:
    """Weak labels refreshed, the confirmed ones kept."""
    current = current or {}
    confirmed = list(current.get("confirmed") or [])
    out = {k: (current.get(k) if k in confirmed else weak.get(k)) for k in LABEL_KEYS}
    out["confirmed"] = confirmed
    return out


async def _text_of(session: AsyncSession, report: Report) -> str:
    parts = [report.text_original or ""]
    media = await session.scalars(
        select(Media).where(Media.report_id == report.id, Media.kind.in_(("audio", "video"))).order_by(Media.id)
    )
    parts.extend(m.transcript for m in media if m.transcript)
    return "\n".join(p.strip() for p in parts if p and p.strip())


async def _names(session: AsyncSession, report: Report) -> list[str | None]:
    profile = await session.scalar(select(Profile).where(Profile.user_id == report.user_id))
    return [profile.first_name, profile.last_name] if profile is not None else []


async def upsert(session: AsyncSession, report: Report) -> Sample | None:
    """The sample of a final report, created or refreshed; None when the report has no text."""
    text = await _text_of(session, report)
    if not text:
        return None
    analysis = await session.get(Analysis, report.id)
    weak = weak_labels(report, analysis.extraction if analysis is not None else None)
    sample = await session.scalar(
        select(Sample).where(Sample.source == SOURCE_REPORT, Sample.source_id == str(report.id))
    )
    anon = anonymize(text, await _names(session, report))
    group = str(report.incident_id) if report.incident_id else None
    now = datetime.now(UTC)
    if sample is None:
        sample = Sample(
            source=SOURCE_REPORT,
            source_id=str(report.id),
            group_key=group,
            text=anon,
            label=merged(None, weak),
            label_origin="weak",
            split=split_of(group or str(report.id)),
        )
        session.add(sample)
    else:
        sample.text = anon
        sample.label = merged(sample.label, weak)
        sample.updated_at = now
    await session.flush()
    return sample


async def sync(session: AsyncSession, limit: int = BATCH) -> int:
    """Samples for the final reports that have none yet or changed since (a bounded batch per call)."""
    rows = await session.scalars(
        select(Report)
        .outerjoin(Sample, (Sample.source == SOURCE_REPORT) & (Sample.source_id == cast(Report.id, Text)))
        .where(
            Report.status.in_(_FINAL),
            Report.anonymised_at.is_(None),
            or_(
                Report.text_original.is_not(None),
                exists().where(Media.report_id == Report.id, Media.transcript.is_not(None)),
            ),
            or_(Sample.id.is_(None), Sample.updated_at < Report.updated_at),
        )
        .order_by(Report.updated_at)
        .limit(limit)
    )
    count = 0
    for report in rows.all():
        if await upsert(session, report) is not None:
            count += 1
    return count


async def confirm(
    session: AsyncSession, report: Report, labels: dict[str, Any], actor: str, origin: str = "operator"
) -> Sample | None:
    """The operator's (or commander's) labels for a final report: they replace the weak ones for good."""
    sample = await upsert(session, report)
    if sample is None:
        return None
    label = dict(sample.label)
    confirmed = set(label.get("confirmed") or [])
    for key, value in labels.items():
        if key in LABEL_KEYS and value is not None:
            label[key] = value
            confirmed.add(key)
    label["confirmed"] = sorted(confirmed)
    sample.label = label
    sample.label_origin = origin
    sample.labelled_by = actor
    sample.updated_at = datetime.now(UTC)
    await session.flush()
    return sample


async def labels_of(session: AsyncSession, report_id: uuid.UUID) -> dict[str, Any] | None:
    sample = await session.scalar(
        select(Sample).where(Sample.source == SOURCE_REPORT, Sample.source_id == str(report_id))
    )
    return dict(sample.label) if sample is not None else None
