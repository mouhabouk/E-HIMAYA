"""Library documents: what each kind of item looks like in the index, built from its source table.

``build`` reads the source and returns the searchable form of one item, or None when it is gone or must not be
searched (rejected or anonymised report, draft or archived memory entry, dissolved incident…). ``refresh`` writes the
result to ``knowledge.search_doc`` (upsert, or a tombstone that wipes the text at once) and flags the row for the
OpenSearch push. Every function is idempotent: the indexer may run it as often as it likes.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import SEARCH_TOKEN_BYTES, get_cipher
from app.modules.decision.domain import CATEGORY_LABELS
from app.modules.decision.models import ProcedureChunk
from app.modules.knowledge import text as kt
from app.modules.knowledge.domain import MEMORY_ACCESS, SENSITIVE_KINDS, Access, Kind
from app.modules.knowledge.models import MemoryEntry, MemoryEntryVersion, SearchDoc
from app.modules.ops.models import Incident, TimelineEvent
from app.modules.ops.service import all_gouvernorats
from app.modules.register.models import Document as RegisterDocument
from app.modules.reports.domain import Status
from app.modules.reports.models import Media, Report
from app.modules.streams.models import LiveStream
from app.modules.telephony.models import Call

BLIND_INDEX_CONTEXT = "knowledge.search_doc.search"
MAX_BODY_CHARS = 200_000
MAX_TOKENS = 3000
SECTIONS = ("summary", "strengths", "weaknesses", "lessons", "recommendations")
SECTION_LABELS: dict[str, dict[str, str]] = {
    "summary": {"ar": "الملخص", "fr": "Résumé"},
    "strengths": {"ar": "نقاط القوة", "fr": "Points forts"},
    "weaknesses": {"ar": "نقاط الضعف", "fr": "Points faibles"},
    "lessons": {"ar": "الدروس المستخلصة", "fr": "Enseignements"},
    "recommendations": {"ar": "التوصيات", "fr": "Recommandations"},
}
MEDIA_LABELS: dict[str, dict[str, str]] = {
    "call_recording": {"ar": "تسجيل مكالمة", "fr": "Enregistrement d'appel"},
    "video": {"ar": "فيديو", "fr": "Vidéo"},
    "audio": {"ar": "تسجيل صوتي", "fr": "Audio"},
    "recording": {"ar": "تسجيل بث مباشر", "fr": "Enregistrement de direct"},
}
# Timeline entries whose payload text is shown (notes typed by staff); the others are listed by kind only.
_NOTE_KINDS = ("note",)


@dataclass(slots=True)
class Doc:
    kind: Kind
    ref_id: str
    title: str
    body: str
    date: datetime | None
    gouvernorats: list[int]
    access: Access
    categories: list[str] = field(default_factory=list)
    incident_id: uuid.UUID | None = None
    lang: str | None = None
    # Vector already computed at the source (report texts, procedure passages); None = computed by the indexer.
    vector: list[float] | None = None

    @property
    def sensitive(self) -> bool:
        return self.kind in SENSITIVE_KINDS

    def checksum(self) -> str:
        data = [
            self.title,
            self.body,
            self.date.isoformat() if self.date else None,
            sorted(self.gouvernorats),
            self.access.value,
            self.categories,
            str(self.incident_id) if self.incident_id else None,
            self.lang,
        ]
        return hashlib.sha256(json.dumps(data, ensure_ascii=False).encode()).hexdigest()

    def source(self) -> dict[str, Any]:
        """The OpenSearch document."""
        return {
            "kind": self.kind.value,
            "ref_id": self.ref_id,
            "title": self.title,
            "body": self.body,
            "lang": self.lang,
            "date": self.date.isoformat() if self.date else None,
            "gouvernorats": sorted(self.gouvernorats),
            "access": self.access.value,
            "categories": self.categories,
            "incident_id": str(self.incident_id) if self.incident_id else None,
        }


def blind_tokens(body: str) -> list[bytes]:
    """Blind-index tokens of every folded word of an encrypted text, plus its form without the Arabic article."""
    cipher = get_cipher()
    words: dict[str, None] = {}
    for word in kt.normalise(body).split():
        for variant in kt.query_terms(word) or [word]:
            words[variant] = None
        if len(words) >= MAX_TOKENS:
            break
    return [cipher.blind_index(w, context=BLIND_INDEX_CONTEXT)[:SEARCH_TOKEN_BYTES] for w in list(words)[:MAX_TOKENS]]


def query_tokens(terms: list[str]) -> list[bytes]:
    cipher = get_cipher()
    return [cipher.blind_index(t, context=BLIND_INDEX_CONTEXT)[:SEARCH_TOKEN_BYTES] for t in terms]


def _label(category: str | None) -> dict[str, str]:
    return CATEGORY_LABELS.get(category or "other", CATEGORY_LABELS["other"])


def _day(value: date | None) -> datetime | None:
    return datetime.combine(value, time(), tzinfo=UTC) if value is not None else None


def bilingual_title(title: dict[str, str]) -> str:
    ar, fr = (title.get("ar") or "").strip(), (title.get("fr") or "").strip()
    return f"{ar} / {fr}" if ar and fr and ar != fr else ar or fr


def memory_body(snapshot: dict[str, Any]) -> str:
    parts: list[str] = []
    for name in SECTIONS:
        section = snapshot.get(name) or {}
        for lang in ("ar", "fr"):
            value = (section.get(lang) or "").strip()
            if value:
                parts.append(f"{SECTION_LABELS[name][lang]}\n{value}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------- builders, one per kind


async def published_snapshot(session: AsyncSession, entry: MemoryEntry) -> dict[str, Any] | None:
    if entry.published_version is None or entry.status == "archived":
        return None
    version = await session.get(MemoryEntryVersion, (entry.id, entry.published_version))
    return dict(version.snapshot) if version is not None else None


async def _memory(session: AsyncSession, ref_id: str) -> Doc | None:
    entry = await session.get(MemoryEntry, uuid.UUID(ref_id))
    if entry is None:
        return None
    snapshot = await published_snapshot(session, entry)
    if snapshot is None:
        return None
    incidents = snapshot.get("incident_ids") or []
    return Doc(
        kind=Kind.MEMORY,
        ref_id=ref_id,
        title=bilingual_title(snapshot["title"]),
        body=memory_body(snapshot),
        date=datetime.fromisoformat(snapshot["started_at"]),
        gouvernorats=list(snapshot.get("gouvernorats") or []),
        access=MEMORY_ACCESS[snapshot.get("access", "national")],
        categories=[snapshot["event_type"]],
        incident_id=uuid.UUID(incidents[0]) if incidents else None,
    )


async def analytics_available(session: AsyncSession) -> bool:
    return bool(await session.scalar(text("SELECT to_regclass('analytics.report') IS NOT NULL")))


async def _report_doc(session: AsyncSession, ref_id: str) -> Doc | None:
    # Owned by modules/analytics (0015): read as plain SQL so this module does not depend on its code.
    if not await analytics_available(session):
        return None
    row = (
        (
            await session.execute(
                text(
                    "SELECT id, kind, title, period_from, period_to, gouvernorats, filters, format, created_at "
                    "FROM analytics.report WHERE id = :id AND status = 'ready'"
                ),
                {"id": uuid.UUID(ref_id)},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    filters: dict[str, Any] = dict(row["filters"] or {})
    category = filters.get("category")
    incident = filters.get("incident_id")
    words = [str(v) for v in filters.values() if isinstance(v, str | int | float)]
    body = "\n".join(
        part
        for part in (
            row["title"],
            str(row["kind"]).replace("_", " "),
            f"{row['period_from']} → {row['period_to']}",
            " ".join(words),
        )
        if part
    )
    try:
        incident_id = uuid.UUID(str(incident)) if incident else None
    except ValueError:
        incident_id = None
    return Doc(
        kind=Kind.REPORT_DOC,
        ref_id=ref_id,
        title=str(row["title"]),
        body=body,
        date=_day(row["period_from"]) or row["created_at"],
        gouvernorats=list(row["gouvernorats"] or []),
        access=Access.GOUVERNORAT,
        categories=[str(category)] if isinstance(category, str) and category else [],
        incident_id=incident_id,
    )


def _incident_title(incident: Incident) -> str:
    if incident.title:
        return incident.title
    label = _label(incident.category)
    return f"{label['ar']} / {label['fr']} — {incident.opened_at.date().isoformat()}"


async def _incident(session: AsyncSession, ref_id: str) -> Doc | None:
    incident = await session.get(Incident, uuid.UUID(ref_id))
    if incident is None or incident.status in ("dissolved", "merged"):
        return None
    events = list(
        await session.scalars(
            select(TimelineEvent)
            .where(TimelineEvent.incident_id == incident.id, TimelineEvent.kind != "assistant")
            .order_by(TimelineEvent.at, TimelineEvent.id)
        )
    )
    lines = [incident.classification or ""]
    evaluation = incident.evaluation or {}
    for key in ("outcome", "summary", "lessons"):
        if evaluation.get(key):
            lines.append(str(evaluation[key]))
    for event in events:
        note = event.payload.get("text") if event.kind in _NOTE_KINDS else None
        lines.append(f"{event.at.strftime('%Y-%m-%d %H:%M')} {event.kind}" + (f": {note}" if note else ""))
    return Doc(
        kind=Kind.INCIDENT,
        ref_id=ref_id,
        title=_incident_title(incident),
        body="\n".join(line for line in lines if line),
        date=incident.opened_at,
        # Lead and participating gouvernorats (phase 9 §5.6).
        gouvernorats=await all_gouvernorats(session, incident.id),
        access=Access.GOUVERNORAT,
        categories=[incident.category],
        incident_id=incident.id,
    )


def _searchable_report(report: Report | None) -> bool:
    return report is not None and report.anonymised_at is None and report.status != Status.REJECTED.value


async def _report(session: AsyncSession, ref_id: str) -> Doc | None:
    report = await session.get(Report, uuid.UUID(ref_id))
    if report is None or not _searchable_report(report):
        return None
    texts = [t for t in (report.text_ar, report.text_original) if t]
    if not texts:
        return None
    if len(texts) == 2 and texts[0].strip() == texts[1].strip():
        texts = texts[:1]
    vector = await session.scalar(select(Report.embedding).where(Report.id == report.id))
    label = _label(report.category)
    return Doc(
        kind=Kind.REPORT,
        ref_id=ref_id,
        title=f"{report.tracking_code} — {label['ar']} / {label['fr']}",
        body="\n".join(texts),
        date=report.received_at,
        gouvernorats=[report.gouvernorat_code] if report.gouvernorat_code else [],
        access=Access.GOUVERNORAT,
        categories=[report.category],
        incident_id=report.incident_id,
        vector=[float(x) for x in vector] if vector is not None else None,
    )


async def media_context(session: AsyncSession, media: Media) -> tuple[Report | None, Call | None, bool]:
    """The report and call a medium belongs to, and whether it may be searched at all."""
    report = await session.get(Report, media.report_id) if media.report_id else None
    if report is None and media.stream_id is not None:
        stream = await session.get(LiveStream, media.stream_id)
        if stream is not None and stream.report_id is not None:
            report = await session.get(Report, stream.report_id)
    call = await session.scalar(select(Call).where(Call.recording_media_id == media.id))
    if report is not None and not _searchable_report(report):
        return report, call, False
    return report, call, True


async def _transcript(session: AsyncSession, ref_id: str) -> Doc | None:
    media = await session.get(Media, uuid.UUID(ref_id))
    if media is None or media.status != "stored" or not media.transcript:
        return None
    report, call, searchable = await media_context(session, media)
    if not searchable:
        return None
    gouvernorat = (report.gouvernorat_code if report else None) or (call.gouvernorat_code if call else None)
    if gouvernorat is None and media.stream_id is not None:
        stream = await session.get(LiveStream, media.stream_id)
        gouvernorat = stream.gouvernorat_code if stream is not None else None
    label = MEDIA_LABELS.get(media.kind, MEDIA_LABELS["audio"])
    when = (call.started_at if call else None) or media.created_at
    body = "\n".join(t for t in (media.transcript, media.translation_ar) if t)
    return Doc(
        kind=Kind.TRANSCRIPT,
        ref_id=ref_id,
        title=f"{label['ar']} / {label['fr']} — {when.strftime('%Y-%m-%d %H:%M')}",
        body=body,
        date=when,
        gouvernorats=[gouvernorat] if gouvernorat else [],
        access=Access.GOUVERNORAT,
        categories=[report.category] if report else [],
        incident_id=(report.incident_id if report else None) or (call.incident_id if call else None),
        lang=(media.analysis or {}).get("language"),
    )


async def _procedure(session: AsyncSession, ref_id: str) -> Doc | None:
    chunk = await session.get(ProcedureChunk, ref_id)
    if chunk is None:
        return None
    vector = await session.scalar(select(ProcedureChunk.embedding).where(ProcedureChunk.id == ref_id))
    return Doc(
        kind=Kind.PROCEDURE,
        ref_id=ref_id,
        title=f"{chunk.title} — {chunk.heading}",
        body=chunk.body,
        date=None,
        gouvernorats=[],
        access=Access.ALL,
        categories=list(chunk.categories),
        lang=chunk.lang,
        vector=[float(x) for x in vector] if vector is not None else None,
    )


async def _register(session: AsyncSession, ref_id: str) -> Doc | None:
    """A document of the register (phase L3b): only those open to every staff member of their scope; the command and
    restricted ones, and drafts, stay in the register's own search."""
    doc = await session.get(RegisterDocument, uuid.UUID(ref_id))
    if doc is None or doc.status == "draft" or doc.access not in ("all", "gouvernorat"):
        return None
    regional = doc.gouvernorat_code is not None
    head = " · ".join(p for p in (doc.number, doc.reference, doc.issuer) if p)
    return Doc(
        kind=Kind.REGISTER,
        ref_id=ref_id,
        title=f"{doc.title} — {head}",
        body="\n\n".join(p for p in (doc.summary, doc.body) if p),
        date=_day(doc.effective_from or doc.issued_on),
        gouvernorats=[doc.gouvernorat_code] if regional and doc.gouvernorat_code else [],
        access=Access.GOUVERNORAT if regional else Access.ALL,
        categories=[doc.kind, *doc.topics],
        lang="ar",
    )


_BUILDERS = {
    Kind.MEMORY: _memory,
    Kind.REPORT_DOC: _report_doc,
    Kind.INCIDENT: _incident,
    Kind.REPORT: _report,
    Kind.TRANSCRIPT: _transcript,
    Kind.PROCEDURE: _procedure,
    Kind.REGISTER: _register,
}


async def build(session: AsyncSession, kind: Kind, ref_id: str) -> Doc | None:
    """The searchable form of one item from its source, or None (gone, not searchable, malformed id)."""
    if kind is not Kind.PROCEDURE:
        try:
            ref_id = str(uuid.UUID(ref_id))
        except ValueError:
            return None
    return await _BUILDERS[kind](session, ref_id)


# ---------------------------------------------------------------- writing knowledge.search_doc


async def find_row(session: AsyncSession, kind: str, ref_id: str, *, lock: bool = False) -> SearchDoc | None:
    query = select(SearchDoc).where(SearchDoc.kind == kind, SearchDoc.ref_id == ref_id)
    return await session.scalar(query.with_for_update() if lock else query)


async def refresh(session: AsyncSession, kind: Kind, ref_id: str) -> str:
    """Bring the row of one item in line with its source. Returns "upserted", "deleted" or "unchanged"."""
    doc = await build(session, kind, ref_id)
    if doc is not None:
        ref_id = doc.ref_id
    row = await find_row(session, kind.value, ref_id, lock=True)
    if doc is None:
        if row is None or row.deleted:
            return "unchanged"
        row.deleted, row.os_dirty, row.updated_at = True, True, datetime.now(UTC)
        # The text leaves the index at once; only the keys remain until OpenSearch forgot the item.
        row.body = row.body_enc = row.norm = None
        row.tokens, row.embedding, row.embedding_model = [], None, None
        await session.flush()
        return "deleted"
    checksum = doc.checksum()
    if row is not None and not row.deleted and row.checksum == checksum:
        if doc.vector is not None:
            row.embedding, row.embedding_model = doc.vector, "source"
            await session.flush()
        return "unchanged"
    body = doc.body[:MAX_BODY_CHARS]
    values: dict[str, Any] = {
        "title": doc.title[:1000],
        "body": None if doc.sensitive else body,
        "body_enc": body if doc.sensitive else None,
        "norm": None if doc.sensitive else kt.normalise(f"{doc.title}\n{body}"),
        "tokens": blind_tokens(f"{doc.title}\n{body}") if doc.sensitive else [],
        "lang": doc.lang,
        "date": doc.date,
        "gouvernorats": sorted(doc.gouvernorats),
        "access": doc.access.value,
        "categories": doc.categories,
        "incident_id": doc.incident_id,
        "checksum": checksum,
        "deleted": False,
        "os_dirty": True,
        "updated_at": datetime.now(UTC),
        "embedding": doc.vector,
        "embedding_model": "source" if doc.vector is not None else None,
    }
    if row is None:
        session.add(SearchDoc(kind=kind.value, ref_id=ref_id, **values))
    else:
        for name, value in values.items():
            setattr(row, name, value)
    await session.flush()
    return "upserted"


def stored_body(row: SearchDoc) -> str:
    return (row.body_enc if row.body is None else row.body) or ""
