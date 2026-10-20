"""Analysis pipeline of a report (architecture §6.1, FR-A-044, FR-A-045, BR-10, BR-20).

    report created ──► baseline: rules-only priority, credibility, grouping suggestion (same transaction)
          │
          └──► ai.analysis queued ──► worker: transcribe audio/video ─► extract (language model)
                                       ─► translate fr/en → ar ─► embed ─► rules again ─► report.enriched

The queue is a table, written in the same transaction as the report or media that needs analysis, so a
model or bus outage never loses work: the report stays visible as "awaiting analysis" and is retried
with back-off. Inference runs outside any database transaction; results are written only if no newer
input arrived meanwhile (generation check).
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.events import emit
from app.core.storage import ObjectStore, get_store
from app.modules.ai import grouping, lexicon, scoring
from app.modules.ai import settings as ai_settings
from app.modules.ai.client import AiClient, AiRejected, AiUnavailable, get_ai_client
from app.modules.ai.models import Analysis
from app.modules.identity.models import Account
from app.modules.ops import levels
from app.modules.orgs import sites
from app.modules.reports.domain import Category, Status
from app.modules.reports.models import Media, Report, StatusHistory
from app.modules.streams import signals

log = structlog.get_logger()

SPEECH_KINDS = ("audio", "video")
TRANSLATABLE = ("fr", "en")
_CLAIM = text(
    """
    UPDATE ai.analysis SET state = 'running', attempts = attempts + 1, updated_at = now(),
           lease_until = now() + make_interval(secs => :lease)
    WHERE report_id = (
        SELECT a.report_id FROM ai.analysis a JOIN reports.report r ON r.id = a.report_id
        WHERE ((a.state = 'pending' AND a.next_attempt_at <= now())
           OR (a.state = 'running' AND a.lease_until < now()))
          AND (CAST(:only AS uuid) IS NULL OR a.report_id = CAST(:only AS uuid))
        ORDER BY r.priority_score DESC NULLS LAST, a.next_attempt_at
        LIMIT 1
        FOR UPDATE OF a SKIP LOCKED)
    RETURNING report_id, generation, attempts
    """
)


async def enqueue(session: AsyncSession, report_id: uuid.UUID) -> None:
    """(Re)queue the analysis of a report in the caller's transaction."""
    await session.execute(
        text(
            "INSERT INTO ai.analysis (report_id) VALUES (:id) ON CONFLICT (report_id) DO UPDATE SET "
            "state = 'pending', generation = ai.analysis.generation + 1, attempts = 0, "
            "next_attempt_at = now(), updated_at = now()"
        ),
        {"id": report_id},
    )


# ---------------------------------------------------------------- rules (always available)


def report_texts(report: Report, media: list[Media]) -> list[str]:
    texts = [report.text_original] if report.text_original else []
    texts += [m.transcript for m in media if m.transcript]
    texts += [m.translation_ar for m in media if m.translation_ar]
    if report.text_ar:
        texts.append(report.text_ar)
    return texts


async def _stored_media(session: AsyncSession, report_id: uuid.UUID) -> list[Media]:
    rows = await session.scalars(
        select(Media).where(Media.report_id == report_id, Media.status == "stored").order_by(Media.created_at)
    )
    return list(rows)


async def _useful_reports(session: AsyncSession, user_id: uuid.UUID, exclude: uuid.UUID) -> int:
    count = await session.scalar(
        select(func.count(func.distinct(StatusHistory.report_id)))
        .join(Report, Report.id == StatusHistory.report_id)
        .where(Report.user_id == user_id, Report.id != exclude, StatusHistory.status == Status.INTERVENED.value)
    )
    return int(count or 0)


async def _incident_reporters(session: AsyncSession, report: Report) -> set[uuid.UUID]:
    if report.incident_id is None:
        return set()
    rows = await session.scalars(
        select(Report.user_id).where(
            Report.incident_id == report.incident_id, Report.id != report.id, Report.status != Status.REJECTED.value
        )
    )
    return set(rows)


async def score(session: AsyncSession, report: Report, analysis: Analysis) -> list[grouping.Match]:
    """Recompute credibility, priority and the grouping suggestion of a report from what is known now."""
    settings = await ai_settings.load(session)
    category = Category(report.category)
    matches = await grouping.find_matches(session, report.id, category, settings.grouping)
    account = await session.get(Account, report.user_id)
    media = await _stored_media(session, report.id)
    corroborating = ({m.user_id for m in matches} | await _incident_reporters(session, report)) - {report.user_id}
    facts = scoring.Facts(
        category=category,
        reporter_kind=account.kind.value if account else "anonymous",
        false_reports=account.false_report_count if account else 0,
        useful_reports=await _useful_reports(session, report.user_id, report.id),
        stored_media=len(media),
        accuracy_m=report.location_accuracy_m,
        corroborating_reporters=len(corroborating),
        extraction=analysis.extraction,
        keywords=lexicon.signals("\n".join(report_texts(report, media))),
        organization_id=str(report.organization_id) if report.organization_id else None,
        sensitive_site=await sites.nearest(
            session, select(Report.location).where(Report.id == report.id).scalar_subquery()
        ),
        op_level=(await levels.level_of(session, report.gouvernorat_code)).value,
        vision_fire=await signals.vision_signal(session, report.id),
    )
    credibility = scoring.credibility(facts)
    priority = scoring.priority(facts, credibility["score"], settings.priority)
    if report.needs_verification:
        priority = scoring.pending_verification(priority, report.verification_reason)
    analysis.credibility = credibility
    analysis.priority = priority
    analysis.suggestion = grouping.suggestion(matches, report.incident_id, list(analysis.dismissed or []))
    analysis.updated_at = datetime.now(UTC)
    report.credibility_score = credibility["score"]
    report.priority_score = priority["score"]
    return matches


async def baseline(session: AsyncSession, report: Report) -> None:
    """Immediate rules-only scores of a new report, so it is ranked on the dashboard at once (NFR-01)."""
    analysis = Analysis(report_id=report.id, state="pending", steps={}, dismissed=[], models={})
    session.add(analysis)
    await session.flush()
    await score(session, report, analysis)
    await session.flush()
    await auto_group(session, report)


async def auto_group(session: AsyncSession, report: Report) -> None:
    """At disaster level the grouping suggestion is applied at once (BR-11); never blocks a report."""
    from fastapi import HTTPException

    from app.modules.ops import service as incidents

    try:
        async with session.begin_nested():
            await incidents.auto_group(session, report)
    except HTTPException:
        log.info("ai.auto_group_skipped", report_id=str(report.id))


async def emit_enriched(session: AsyncSession, report_ids: list[uuid.UUID]) -> None:
    from app.modules.reports import service as reports

    for report_id in report_ids:
        found = await reports.staff_summary(session, report_id)
        if found is not None:
            await emit(session, "report.enriched", {"report": found[0].model_dump(mode="json")})


async def rescore(session: AsyncSession, report_ids: list[uuid.UUID], *, wait: bool = True) -> None:
    """Re-apply the rules to reports whose context changed (new corroborating report, incident change).

    Workers pass ``wait=False``: a report locked by another worker is skipped (it is being scored with
    fresh context anyway), so two workers never wait on each other.
    """
    lock: dict[str, bool] | bool = True if wait else {"skip_locked": True}
    done: list[uuid.UUID] = []
    for report_id in dict.fromkeys(report_ids):
        report = await session.get(Report, report_id, with_for_update=lock)
        analysis = await session.get(Analysis, report_id, with_for_update=lock) if report is not None else None
        if report is None or analysis is None:
            continue
        await score(session, report, analysis)
        done.append(report_id)
    await session.flush()
    await emit_enriched(session, done)


# ---------------------------------------------------------------- models (when the AI service is up)


@dataclass
class Outcome:
    steps: dict[str, str] = field(default_factory=dict)
    models: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    transcripts: dict[uuid.UUID, dict[str, Any]] = field(default_factory=dict)
    extraction: dict[str, Any] | None = None
    language: str | None = None
    text_ar: str | None = None
    embedding: list[float] | None = None

    @property
    def retry(self) -> bool:
        return "unavailable" in self.steps.values()

    def mark(self, step: str, status: str, error: str | None = None) -> None:
        # The worst status of a step wins: unavailable (retry) > failed > done > skipped.
        order = ["skipped", "done", "failed", "unavailable"]
        if order.index(status) >= order.index(self.steps.get(step, "skipped")):
            self.steps[step] = status
        if error:
            self.errors.append(f"{step}:{error}")


@dataclass(frozen=True, slots=True)
class Snapshot:
    report_id: uuid.UUID
    category: str
    text: str | None
    speech: list[tuple[uuid.UUID, str, str | None]]  # media id, object key, content type (to transcribe)
    transcripts: list[tuple[uuid.UUID, str, str | None]]  # media id, text, language (already done)


async def _run_models(client: AiClient, store: ObjectStore, snap: Snapshot) -> Outcome:
    out = Outcome()
    transcripts = list(snap.transcripts)

    for media_id, key, _content_type in snap.speech:
        try:
            result = await client.transcribe(store.presign_get(key, expires_s=1800, internal=True))
        except AiUnavailable as exc:
            out.mark("transcribe", "unavailable", str(exc))
            continue
        except AiRejected as exc:
            out.transcripts[media_id] = {"error": exc.code}
            out.mark("transcribe", "failed", exc.code)
            continue
        out.transcripts[media_id] = result
        out.models["transcribe"] = str(result.get("model"))
        out.mark("transcribe", "done")
        if result.get("text"):
            transcripts.append((media_id, str(result["text"]), result.get("language")))

    pieces: list[tuple[str, str, str]] = []  # owner ("report" or media id), text, language
    if snap.text:
        pieces.append(("report", snap.text, lexicon.detect_language(snap.text)))
    pieces += [(str(mid), body, lang or lexicon.detect_language(body)) for mid, body, lang in transcripts]
    if not pieces:
        for step in ("extract", "translate", "embed"):
            out.mark(step, "skipped")
        return out
    out.language = max(pieces, key=lambda p: len(p[1]))[2]
    combined = "\n".join(body for _, body, _ in pieces)[:8000]

    try:
        extraction = await client.extract(combined, snap.category)
        out.models["extract"] = str(extraction.pop("model", ""))
        out.extraction = extraction
        out.mark("extract", "done")
    except AiUnavailable as exc:
        out.mark("extract", "unavailable", str(exc))
    except AiRejected as exc:
        out.mark("extract", "failed", exc.code)

    for owner, body, language in pieces:
        if language not in TRANSLATABLE:
            continue
        try:
            translated = await client.translate([body], language)
        except AiUnavailable as exc:
            out.mark("translate", "unavailable", str(exc))
            continue
        except AiRejected as exc:
            out.mark("translate", "failed", exc.code)
            continue
        out.models[f"translate_{language}"] = str(translated.get("model"))
        out.mark("translate", "done")
        if owner == "report":
            out.text_ar = translated["texts"][0]
        else:
            out.transcripts.setdefault(uuid.UUID(owner), {})["translation_ar"] = translated["texts"][0]
    out.mark("translate", "skipped")

    try:
        embedded = await client.embed([combined])
        vector = embedded["vectors"][0]
        if len(vector) != 768:
            raise AiRejected("embedding_dimension")
        out.embedding = vector
        out.models["embed"] = str(embedded.get("model"))
        out.mark("embed", "done")
    except AiUnavailable as exc:
        out.mark("embed", "unavailable", str(exc))
    except AiRejected as exc:
        out.mark("embed", "failed", exc.code)
    return out


async def _snapshot(session: AsyncSession, report_id: uuid.UUID) -> Snapshot | None:
    report = await session.get(Report, report_id)
    if report is None:
        return None
    media = await _stored_media(session, report_id)
    speech = [(m.id, m.object_key, m.content_type) for m in media if m.kind in SPEECH_KINDS and m.transcript is None]
    speech = [s for s in speech if not (next(m for m in media if m.id == s[0]).analysis or {}).get("error")]
    done = [
        (m.id, m.transcript, (m.analysis or {}).get("language"))
        for m in media
        if m.kind in SPEECH_KINDS and m.transcript
    ]
    return Snapshot(report_id, report.category, report.text_original, speech, done)


def _backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(30 * 2 ** max(attempts - 1, 0), 3600))


async def _save(session: AsyncSession, report_id: uuid.UUID, generation: int, attempts: int, out: Outcome) -> None:
    analysis = await session.get(Analysis, report_id, with_for_update=True)
    report = await session.get(Report, report_id, with_for_update=True)
    if analysis is None or report is None:
        return
    now = datetime.now(UTC)
    for media_id, result in out.transcripts.items():
        media = await session.get(Media, media_id)
        if media is None:
            continue
        info = dict(media.analysis or {})
        if "text" in result:
            media.transcript = result["text"] or ""
            media.duration_s = result.get("duration_s")
            info.update(
                language=result.get("language"),
                language_probability=result.get("language_probability"),
                model=result.get("model"),
                segments=len(result.get("segments") or []),
            )
        if "translation_ar" in result:
            media.translation_ar = result["translation_ar"]
        if "error" in result:
            info["error"] = result["error"]
        media.analysis = info

    if out.extraction is not None:
        analysis.extraction = out.extraction
    if out.language:
        analysis.language = out.language
    if out.text_ar:
        report.text_ar = out.text_ar
    if out.embedding is not None:
        report.embedding = out.embedding
    analysis.steps = {**(analysis.steps or {}), **out.steps}
    analysis.models = {**(analysis.models or {}), **out.models}
    analysis.last_error = "; ".join(out.errors)[:500] or None

    if analysis.generation != generation:
        # New media arrived during the analysis: run again with everything.
        analysis.state, analysis.next_attempt_at = "pending", now
    elif out.retry and attempts < get_settings().ai_max_attempts:
        analysis.state, analysis.next_attempt_at = "pending", now + _backoff(attempts)
    else:
        analysis.state = "failed" if out.retry else "done"
        analysis.completed_at = now
    analysis.lease_until = None
    await session.flush()

    matches = await score(session, report, analysis)
    await session.flush()
    await auto_group(session, report)
    await emit_enriched(session, [report_id])
    # Reports describing the same event gain a corroborating reporter: refresh their scores too.
    others = [m.report_id for m in matches[:20]]
    if others:
        await rescore(session, others, wait=False)


def _disabled() -> Outcome:
    return Outcome(steps={s: "disabled" for s in ("transcribe", "extract", "translate", "embed")})


async def analyze_one(
    sessionmaker: async_sessionmaker[AsyncSession],
    client: AiClient | None,
    store: ObjectStore,
    only: uuid.UUID | None = None,
) -> bool:
    """Analyse the most urgent queued report (or ``only`` that one). Returns False when nothing was waiting."""
    lease = get_settings().ai_request_timeout_s + 300
    async with sessionmaker() as session, session.begin():
        claimed = (await session.execute(_CLAIM, {"lease": lease, "only": only})).first()
        if claimed is None:
            return False
        report_id, generation, attempts = claimed.report_id, claimed.generation, claimed.attempts
        snap = await _snapshot(session, report_id)
    if snap is None:
        return True
    started = datetime.now(UTC)
    try:
        out = await _run_models(client, store, snap) if client is not None else _disabled()
    except Exception:
        log.exception("ai.models_failed", report_id=str(report_id))
        out = Outcome()
        out.mark("pipeline", "unavailable", "internal_error")
    async with sessionmaker() as session, session.begin():
        await _save(session, report_id, generation, attempts, out)
    log.info(
        "ai.analysed",
        report_id=str(report_id),
        steps=out.steps,
        seconds=round((datetime.now(UTC) - started).total_seconds(), 2),
    )
    return True


async def analyze_forever(sessionmaker: async_sessionmaker[AsyncSession], idle_s: float = 1.0) -> None:
    async def loop() -> None:
        while True:
            try:
                worked = await analyze_one(sessionmaker, get_ai_client(), get_store())
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("ai.analysis_failed")
                worked = False
            if not worked:
                await asyncio.sleep(idle_s)

    await asyncio.gather(*(loop() for _ in range(get_settings().ai_concurrency)))
