"""Procedures library (docs/procedures): parsing, indexing into ``decision.procedure_chunk`` and retrieval.

A sheet is ``<procedure>.<ar|fr>.md``: a header between two ``---`` lines (id, lang, title, categories,
classifications, reviewed, sources) and a body split into passages at each ``## `` heading. Indexing is idempotent:
a passage is rewritten only when its checksum changes (its embedding is then recomputed), and passages of removed
sheets are deleted. The worker loop ``procedures-index`` re-syncs the directory and fills missing embeddings through
the AI service's multilingual-e5 endpoint; without the AI service, retrieval falls back to PostgreSQL full-text search.
"""

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.modules.ai.client import AiClient, AiRejected, AiUnavailable, get_ai_client
from app.modules.decision.models import ProcedureChunk
from app.modules.reports.domain import Category

log = structlog.get_logger()

LANGS = ("ar", "fr")
_FILE = re.compile(r"^(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)\.(?P<lang>ar|fr)\.md$")
MAX_PASSAGE_CHARS = 8000
EMBED_BATCH = 16
INDEX_INTERVAL_S = 300
_LOCK_KEY = "ehimaya.decision.procedures"
_CONTAINER_DIR = Path("/app/procedures")


class ProcedureError(ValueError):
    """A sheet does not follow the format of docs/procedures/README.md."""


@dataclass(frozen=True, slots=True)
class Passage:
    id: str
    procedure_id: str
    lang: str
    title: str
    heading: str
    body: str
    position: int
    categories: list[str]
    classifications: list[str]
    sources: list[dict[str, str]]
    path: str
    checksum: str = field(default="")


def default_directory() -> Path | None:
    configured = get_settings().procedures_dir
    if configured is not None:
        return configured
    here = Path(__file__).resolve()
    candidates = [here.parents[4].parent / "docs" / "procedures"] if len(here.parents) > 4 else []
    candidates.append(_CONTAINER_DIR)
    return next((c for c in candidates if c.is_dir()), None)


def _list_value(raw: str) -> list[str]:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [item.strip() for item in raw.split(",") if item.strip()]


def _header(lines: list[str], name: str) -> tuple[dict[str, Any], int]:
    if not lines or lines[0].strip() != "---":
        raise ProcedureError(f"{name}: missing header")
    meta: dict[str, Any] = {"sources": []}
    key: str | None = None
    for index, line in enumerate(lines[1:], start=1):
        stripped = line.strip()
        if stripped == "---":
            return meta, index + 1
        if stripped.startswith("- ") and key == "sources":
            label, _, url = stripped[2:].partition("|")
            if not url.strip().startswith("https://"):
                raise ProcedureError(f"{name}: every source needs '<reference> | https://…'")
            meta["sources"].append({"label": label.strip(), "url": url.strip()})
            continue
        key, sep, value = stripped.partition(":")
        if not sep:
            raise ProcedureError(f"{name}: invalid header line {index + 1}")
        key = key.strip()
        if key != "sources":
            meta[key] = value.strip()
    raise ProcedureError(f"{name}: unterminated header")


def parse(path: Path) -> list[Passage]:
    match = _FILE.match(path.name)
    if match is None:
        raise ProcedureError(f"{path.name}: expected <procedure>.<ar|fr>.md")
    lines = path.read_text(encoding="utf-8").splitlines()
    meta, start = _header(lines, path.name)
    slug, lang = match["slug"], match["lang"]
    if meta.get("id") != slug or meta.get("lang") != lang:
        raise ProcedureError(f"{path.name}: header id/lang must match the file name")
    title = str(meta.get("title") or "").strip()
    categories = _list_value(str(meta.get("categories", "")))
    classifications = _list_value(str(meta.get("classifications", "")))
    if not title or not categories or not meta["sources"]:
        raise ProcedureError(f"{path.name}: title, categories and sources are required")
    known = {c.value for c in Category}
    if unknown := [c for c in categories if c not in known]:
        raise ProcedureError(f"{path.name}: unknown categories {unknown}")

    sections: list[tuple[str, list[str]]] = []
    for line in lines[start:]:
        if line.startswith("## "):
            sections.append((line[3:].strip(), []))
        elif sections:
            sections[-1][1].append(line)
        # Text before the first "## " (the "# " title) is not a passage.
    passages: list[Passage] = []
    for position, (heading, body_lines) in enumerate(sections, start=1):
        body = "\n".join(body_lines).strip()
        if not body or len(body) > MAX_PASSAGE_CHARS:
            raise ProcedureError(f"{path.name}: passage '{heading}' is empty or longer than {MAX_PASSAGE_CHARS}")
        passage = Passage(
            id=f"{slug}.{lang}#{position}",
            procedure_id=slug,
            lang=lang,
            title=title,
            heading=heading,
            body=body,
            position=position,
            categories=categories,
            classifications=classifications,
            sources=list(meta["sources"]),
            path=path.name,
        )
        digest = hashlib.sha256(
            json.dumps(
                [title, heading, body, categories, classifications, meta["sources"]], ensure_ascii=False
            ).encode()
        ).hexdigest()
        passages.append(Passage(**{**_as_dict(passage), "checksum": digest}))
    if not passages:
        raise ProcedureError(f"{path.name}: no '## ' passage")
    return passages


def _as_dict(passage: Passage) -> dict[str, Any]:
    return {name: getattr(passage, name) for name in Passage.__slots__}


def load_directory(directory: Path) -> list[Passage]:
    passages: list[Passage] = []
    for path in sorted(directory.glob("*.md")):
        if _FILE.match(path.name):
            passages.extend(parse(path))
    return passages


async def sync(session: AsyncSession, directory: Path) -> dict[str, int]:
    """Bring the index in line with the sheets of ``directory`` (the caller commits)."""
    passages = load_directory(directory)
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": _LOCK_KEY})
    existing: dict[str, str] = {
        row[0]: row[1] for row in (await session.execute(select(ProcedureChunk.id, ProcedureChunk.checksum))).all()
    }
    counts = {"files": len({p.path for p in passages}), "passages": len(passages), "added": 0, "updated": 0}
    for passage in passages:
        if existing.get(passage.id) == passage.checksum:
            continue
        values = _as_dict(passage)
        if passage.id in existing:
            row = await session.get(ProcedureChunk, passage.id)
            assert row is not None
            for name, value in values.items():
                setattr(row, name, value)
            row.embedding, row.embedding_model, row.indexed_at = None, None, func.now()
            counts["updated"] += 1
        else:
            session.add(ProcedureChunk(**values))
            counts["added"] += 1
    stale = set(existing) - {p.id for p in passages}
    if stale:
        await session.execute(delete(ProcedureChunk).where(ProcedureChunk.id.in_(stale)))
    counts["removed"] = len(stale)
    await session.flush()
    return counts


def passage_text(title: str, heading: str, body: str) -> str:
    return f"{title} — {heading}\n{body}"


async def embed_pending(session: AsyncSession, ai: AiClient, batch: int = EMBED_BATCH) -> int:
    """Embed up to ``batch`` passages that have no vector yet (the caller commits)."""
    rows = list(
        await session.scalars(
            select(ProcedureChunk)
            .where(ProcedureChunk.embedding.is_(None))
            .order_by(ProcedureChunk.indexed_at, ProcedureChunk.id)
            .limit(batch)
            .with_for_update(skip_locked=True)
        )
    )
    if not rows:
        return 0
    answer = await ai.embed([passage_text(r.title, r.heading, r.body) for r in rows])
    vectors = answer.get("vectors") or []
    if len(vectors) != len(rows) or any(len(v) != 768 for v in vectors):
        raise AiRejected("embedding_dimension")
    for row, vector in zip(rows, vectors, strict=True):
        row.embedding, row.embedding_model = vector, str(answer.get("model") or "")
    await session.flush()
    return len(rows)


async def index_once(sessionmaker: async_sessionmaker[AsyncSession], *, embed: bool = True) -> dict[str, int]:
    directory = default_directory()
    counts: dict[str, int] = {}
    if directory is None:
        log.warning("procedures.directory_missing")
    else:
        async with sessionmaker() as session, session.begin():
            counts = await sync(session, directory)
    ai = get_ai_client() if embed else None
    embedded = 0
    while ai is not None:
        async with sessionmaker() as session, session.begin():
            done = await embed_pending(session, ai)
        embedded += done
        if done < EMBED_BATCH:
            break
    counts["embedded"] = embedded
    return counts


async def procedures_forever(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    """Worker loop: keep the index in line with docs/procedures and fill missing embeddings."""
    while True:
        try:
            counts = await index_once(sessionmaker)
            if any(counts.get(k) for k in ("added", "updated", "removed", "embedded")):
                log.info("procedures.indexed", **counts)
        except asyncio.CancelledError:
            raise
        except (AiUnavailable, AiRejected) as exc:
            log.info("procedures.embed_deferred", error=str(exc))
        except Exception:
            log.exception("procedures.index_failed")
        await asyncio.sleep(INDEX_INTERVAL_S)


# ---------------------------------------------------------------- retrieval


@dataclass(slots=True)
class Hit:
    id: str
    procedure_id: str
    lang: str
    title: str
    heading: str
    body: str
    sources: list[dict[str, str]]
    score: float
    matched: list[str]


_WORD = re.compile(r"\w+", re.UNICODE)
_AR_PREFIXES = ("وال", "بال", "فال", "كال", "لل", "ال")
# A passage is a candidate when one of these holds: e5 similarity at least this, a full-text match, or the
# incident's category / classification.
MIN_SIMILARITY = 0.78


def query_terms(question: str, limit: int = 24) -> list[str]:
    terms: list[str] = []
    for word in _WORD.findall(question.lower()):
        if len(word) < 3 or word.isdigit():
            continue
        variants = [word]
        for prefix in _AR_PREFIXES:
            if word.startswith(prefix) and len(word) - len(prefix) >= 3:
                variants.append(word[len(prefix) :])
                break
        for variant in variants:
            if variant not in terms:
                terms.append(variant)
    return terms[:limit]


async def search(
    session: AsyncSession,
    *,
    question: str,
    lang: str,
    category: str | None,
    classification: str | None,
    vector: list[float] | None,
    limit: int = 4,
) -> list[Hit]:
    """Best passages in ``lang`` for the question and the incident, highest score first."""
    terms = query_terms(question)
    tsquery = " | ".join(f"{t}:*" for t in terms)
    params: dict[str, Any] = {
        "lang": lang,
        "q": tsquery or "",
        "category": category or "",
        "classification": classification or "",
        "v": str(vector) if vector is not None else None,
        "min_sim": MIN_SIMILARITY,
    }
    rows = (
        await session.execute(
            text(
                """
                WITH scored AS (
                    SELECT c.id, c.procedure_id, c.lang, c.title, c.heading, c.body, c.sources,
                           CASE WHEN CAST(CAST(:v AS text) AS vector) IS NOT NULL AND c.embedding IS NOT NULL
                                THEN 1 - (c.embedding <=> CAST(CAST(:v AS text) AS vector)) ELSE 0 END AS similarity,
                           CASE WHEN :q <> '' THEN ts_rank(c.search, to_tsquery('simple', :q)) ELSE 0 END AS rank,
                           :category = ANY(c.categories) AS category_match,
                           :classification <> '' AND :classification = ANY(c.classifications) AS class_match
                    FROM decision.procedure_chunk c
                    WHERE c.lang = :lang
                )
                SELECT *, max(rank) OVER () AS max_rank FROM scored
                WHERE similarity >= :min_sim OR rank > 0 OR category_match OR class_match
                """
            ),
            params,
        )
    ).mappings()
    hits: list[Hit] = []
    for row in rows:
        lexical = float(row["rank"]) / float(row["max_rank"]) if row["max_rank"] else 0.0
        matched = []
        if row["similarity"] >= MIN_SIMILARITY:
            matched.append("semantic")
        if lexical > 0:
            matched.append("words")
        if row["category_match"]:
            matched.append("category")
        if row["class_match"]:
            matched.append("classification")
        score = (
            float(row["similarity"])
            + 0.3 * lexical
            + (0.2 if row["category_match"] else 0.0)
            + (0.1 if row["class_match"] else 0.0)
        )
        hits.append(
            Hit(
                id=row["id"],
                procedure_id=row["procedure_id"],
                lang=row["lang"],
                title=row["title"],
                heading=row["heading"],
                body=row["body"],
                sources=list(row["sources"] or []),
                score=round(score, 4),
                matched=matched,
            )
        )
    hits.sort(key=lambda h: (-h.score, h.id))
    return hits[:limit]
