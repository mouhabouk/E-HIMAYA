"""Events library search (FR-C-23): OpenSearch or PostgreSQL full text, merged with pgvector by reciprocal rank fusion.

1. Text ranking: OpenSearch (``<prefix>-library`` alias, Arabic/French analysers, highlights) when configured and
   answering; otherwise PostgreSQL over ``knowledge.search_doc``: 'simple' full-text vector and pg_trgm word
   similarity on the normalised text, blind-index word tokens for texts that are encrypted at rest.
2. Semantic ranking: the query's multilingual-e5 vector (AI service ``embed``) against the stored vectors (pgvector,
   cosine), when the AI service answers.
3. Reciprocal rank fusion (k = 60) of the two lists.
4. Scope: both engines already filter by the caller's scope, and every candidate is checked again against its
   PostgreSQL row (kind allowed for the role, access level, gouvernorats, filters) before it is returned.
"""

import base64
import binascii
import calendar
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, Role
from app.modules.ai.client import AiRejected, AiUnavailable, get_ai_client
from app.modules.decision.domain import CATEGORY_LABELS
from app.modules.knowledge import documents
from app.modules.knowledge import schemas as s
from app.modules.knowledge import text as kt
from app.modules.knowledge.domain import COMMITTEE_ROLES, KIND_LABELS, Kind, can_see
from app.modules.knowledge.models import SearchDoc
from app.modules.knowledge.opensearch import SEARCH_FIELDS, SearchUnavailable, get_engine, highlight_spec
from app.modules.reports.staff_router import READ_ROLES

log = structlog.get_logger()

TUNIS = ZoneInfo("Africa/Tunis")
RRF_K = 60
# Candidates taken from each ranking; a query pages through at most this many hits.
CANDIDATES = 300
# Browsing (no query) pages through at most this many items, newest first.
BROWSE_WINDOW = 1000
MIN_SIMILARITY = 0.8
# Kinds holding operational data (incidents, citizens' words, analytics): roles that read incidents only.
OPERATIONAL_KINDS = frozenset({Kind.INCIDENT, Kind.REPORT, Kind.TRANSCRIPT, Kind.REPORT_DOC})

Key = tuple[str, str]


@dataclass(slots=True)
class Filters:
    kinds: list[Kind] = field(default_factory=list)
    date_from: date | None = None
    date_to: date | None = None
    gouvernorat: int | None = None
    category: str | None = None


def allowed_kinds(principal: Principal) -> list[Kind]:
    operational = bool(principal.roles & frozenset(READ_ROLES))
    return [k for k in Kind if operational or k not in OPERATIONAL_KINDS]


def _kinds(principal: Principal, filters: Filters) -> list[str]:
    allowed = allowed_kinds(principal)
    return [k.value for k in (filters.kinds or allowed) if k in allowed]


def _bounds(filters: Filters) -> tuple[datetime | None, datetime | None]:
    start = datetime.combine(filters.date_from, datetime.min.time(), TUNIS) if filters.date_from else None
    end = datetime.combine(filters.date_to + timedelta(days=1), datetime.min.time(), TUNIS) if filters.date_to else None
    return start, end


def _where(principal: Principal, filters: Filters) -> tuple[str, dict[str, Any]]:
    """SQL conditions on ``d`` (knowledge.search_doc): not deleted, scope, then the caller's filters."""
    start, end = _bounds(filters)
    params: dict[str, Any] = {
        "kinds": _kinds(principal, filters),
        "national": principal.is_national,
        "code": principal.gouvernorat_code or 0,
        "central": Role.CENTRAL_COMMITTEE in principal.roles and principal.is_national,
        "committee": bool(principal.roles & COMMITTEE_ROLES),
    }
    clauses = [
        "NOT d.deleted",
        "d.kind = ANY(CAST(:kinds AS text[]))",
        "(d.access = 'all'"
        " OR (d.access = 'gouvernorat' AND (:national OR :code = ANY(d.gouvernorats)))"
        " OR (d.access = 'committee' AND (:central OR (:committee AND :code = ANY(d.gouvernorats)))))",
    ]
    if start is not None:
        clauses.append("d.date >= :start")
        params["start"] = start
    if end is not None:
        clauses.append("d.date < :end")
        params["end"] = end
    if filters.gouvernorat is not None:
        clauses.append("CAST(:gouvernorat AS smallint) = ANY(d.gouvernorats)")
        params["gouvernorat"] = filters.gouvernorat
    if filters.category:
        clauses.append("CAST(:category AS text) = ANY(d.categories)")
        params["category"] = filters.category
    return " AND ".join(clauses), params


def visible(principal: Principal, row: SearchDoc, filters: Filters) -> bool:
    """The same rule as ``_where``, applied in Python to every candidate (whatever engine produced it)."""
    if row.deleted or row.kind not in _kinds(principal, filters):
        return False
    if not can_see(principal, row.access, row.gouvernorats):
        return False
    start, end = _bounds(filters)
    if start is not None and (row.date is None or row.date < start):
        return False
    if end is not None and (row.date is None or row.date >= end):
        return False
    if filters.gouvernorat is not None and filters.gouvernorat not in row.gouvernorats:
        return False
    return not (filters.category and filters.category not in row.categories)


# ---------------------------------------------------------------- cursors


def _encode(offset: int) -> str:
    return base64.urlsafe_b64encode(f"o:{offset}".encode()).decode().rstrip("=")


def _decode(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        tag, _, value = raw.partition(":")
        offset = int(value)
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc
    if tag != "o" or offset < 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor")
    return offset


# ---------------------------------------------------------------- rankings


def _tsquery(terms: list[str]) -> str:
    # Terms are folded \w words (no quote, colon or operator can occur); each one also matches as a prefix.
    return " | ".join(f"{t}:*" for t in terms)


async def _pg_text(
    session: AsyncSession, principal: Principal, filters: Filters, terms: list[str], size: int
) -> list[Key]:
    where, params = _where(principal, filters)
    params.update(
        {
            "tsq": _tsquery(terms),
            "qnorm": " ".join(terms),
            "tokens": documents.query_tokens(terms),
            "ntokens": max(1, len(terms)),
            "size": size,
        }
    )
    rows = await session.execute(
        text(
            f"""
            WITH q AS (SELECT to_tsquery('simple', :tsq) AS tsq)
            SELECT d.kind, d.ref_id,
                   ts_rank_cd(d.search, q.tsq)
                   + CASE WHEN d.norm IS NOT NULL THEN word_similarity(:qnorm, d.norm) ELSE 0 END
                   + (SELECT count(*) FROM unnest(d.tokens) t WHERE t = ANY(CAST(:tokens AS bytea[])))::float
                     / :ntokens AS score
            FROM knowledge.search_doc d, q
            WHERE {where}
              AND (d.search @@ q.tsq OR :qnorm <% d.norm OR d.tokens && CAST(:tokens AS bytea[]))
            ORDER BY score DESC, d.date DESC NULLS LAST, d.kind, d.ref_id
            LIMIT :size
            """  # noqa: S608 (conditions are fixed SQL with bound parameters)
        ),
        params,
    )
    return [(r.kind, r.ref_id) for r in rows]


async def _pg_browse(session: AsyncSession, principal: Principal, filters: Filters, size: int) -> list[Key]:
    where, params = _where(principal, filters)
    rows = await session.execute(
        text(
            f"SELECT d.kind, d.ref_id FROM knowledge.search_doc d WHERE {where} "  # noqa: S608
            "ORDER BY d.date DESC NULLS LAST, d.kind, d.ref_id LIMIT :size"
        ),
        {**params, "size": size},
    )
    return [(r.kind, r.ref_id) for r in rows]


async def _pg_vector(
    session: AsyncSession, principal: Principal, filters: Filters, vector: list[float], size: int
) -> list[Key]:
    where, params = _where(principal, filters)
    rows = await session.execute(
        text(
            f"""
            SELECT kind, ref_id FROM (
                SELECT d.kind, d.ref_id, 1 - (d.embedding <=> CAST(:v AS vector)) AS similarity
                FROM knowledge.search_doc d
                WHERE {where} AND d.embedding IS NOT NULL
                ORDER BY d.embedding <=> CAST(:v AS vector)
                LIMIT :size
            ) near WHERE similarity >= :min_sim
            """  # noqa: S608
        ),
        {**params, "v": str(vector), "size": size, "min_sim": MIN_SIMILARITY},
    )
    return [(r.kind, r.ref_id) for r in rows]


def _os_filters(principal: Principal, filters: Filters) -> list[dict[str, Any]]:
    scope: list[dict[str, Any]] = [{"term": {"access": "all"}}]
    if principal.is_national:
        scope.append({"term": {"access": "gouvernorat"}})
    elif principal.gouvernorat_code is not None:
        scope.append(
            {
                "bool": {
                    "filter": [
                        {"term": {"access": "gouvernorat"}},
                        {"term": {"gouvernorats": principal.gouvernorat_code}},
                    ]
                }
            }
        )
    if Role.CENTRAL_COMMITTEE in principal.roles and principal.is_national:
        scope.append({"term": {"access": "committee"}})
    elif principal.roles & COMMITTEE_ROLES and principal.gouvernorat_code is not None:
        scope.append(
            {
                "bool": {
                    "filter": [
                        {"term": {"access": "committee"}},
                        {"term": {"gouvernorats": principal.gouvernorat_code}},
                    ]
                }
            }
        )
    clauses: list[dict[str, Any]] = [
        {"terms": {"kind": _kinds(principal, filters)}},
        {"bool": {"should": scope, "minimum_should_match": 1}},
    ]
    start, end = _bounds(filters)
    if start is not None or end is not None:
        span: dict[str, str] = {}
        if start is not None:
            span["gte"] = start.isoformat()
        if end is not None:
            span["lt"] = end.isoformat()
        clauses.append({"range": {"date": span}})
    if filters.gouvernorat is not None:
        clauses.append({"term": {"gouvernorats": filters.gouvernorat}})
    if filters.category:
        clauses.append({"term": {"categories": filters.category}})
    return clauses


async def _os_rank(
    principal: Principal, filters: Filters, query: str | None, size: int
) -> tuple[list[Key], dict[Key, str]]:
    engine = get_engine()
    if engine is None:
        raise SearchUnavailable("disabled")
    body: dict[str, Any] = {"size": size, "_source": ["kind", "ref_id"], "track_total_hits": False}
    if query:
        body["query"] = {
            "bool": {
                "must": [{"multi_match": {"query": query, "fields": SEARCH_FIELDS, "type": "most_fields"}}],
                "filter": _os_filters(principal, filters),
            }
        }
        body["highlight"] = highlight_spec()
    else:
        body["query"] = {"bool": {"filter": _os_filters(principal, filters)}}
        body["sort"] = [{"date": {"order": "desc", "missing": "_last"}}, {"_id": "asc"}]
    answer = await engine.search(body)
    keys: list[Key] = []
    highlights: dict[Key, str] = {}
    for hit in answer.get("hits", {}).get("hits", []):
        source = hit.get("_source") or {}
        key = (str(source.get("kind")), str(source.get("ref_id")))
        keys.append(key)
        fragments = [f for name in ("body", "body.ar", "body.fr") for f in (hit.get("highlight") or {}).get(name, [])]
        if fragments:
            highlights[key] = kt.from_highlight(max(fragments, key=lambda f: f.count(kt.HL_OPEN)))
    return keys, highlights


def fuse(rankings: list[list[Key]]) -> list[tuple[Key, float]]:
    """Reciprocal rank fusion: score = Σ 1 / (k + rank)."""
    scores: dict[Key, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking, start=1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


async def _query_vector(query: str) -> list[float] | None:
    ai = get_ai_client()
    if ai is None:
        return None
    try:
        answer = await ai.embed([query])
    except (AiUnavailable, AiRejected) as exc:
        log.info("library.embed_unavailable", error=str(exc))
        return None
    vectors = answer.get("vectors") or []
    return [float(x) for x in vectors[0]] if vectors and len(vectors[0]) == 768 else None


# ---------------------------------------------------------------- search


async def _rows(session: AsyncSession, keys: list[Key]) -> dict[Key, SearchDoc]:
    rows: dict[Key, SearchDoc] = {}
    for kind in {k for k, _ in keys}:
        ids = [r for k, r in keys if k == kind]
        for row in await session.scalars(select(SearchDoc).where(SearchDoc.kind == kind, SearchDoc.ref_id.in_(ids))):
            rows[(row.kind, row.ref_id)] = row
    return rows


def _hit(row: SearchDoc, score: float, excerpt: str) -> s.Hit:
    return s.Hit(
        kind=row.kind,
        id=row.ref_id,
        title=row.title,
        excerpt=excerpt,
        date=row.date,
        gouvernorat=row.gouvernorats[0] if row.gouvernorats else None,
        gouvernorats=list(row.gouvernorats),
        category=row.categories[0] if row.categories else None,
        incident_id=row.incident_id,
        score=round(score, 6),
    )


def _facets(rows: list[SearchDoc]) -> s.Facets:
    kinds: Counter[str] = Counter()
    years: Counter[str] = Counter()
    gouvernorats: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    for row in rows:
        kinds[row.kind] += 1
        if row.date is not None:
            years[str(row.date.astimezone(TUNIS).year)] += 1
        gouvernorats.update(str(g) for g in set(row.gouvernorats))
        categories.update(set(row.categories))

    def values(counter: Counter[str], by_key: bool = False) -> list[s.FacetValue]:
        items = sorted(counter.items(), key=(lambda i: i[0]) if by_key else (lambda i: (-i[1], i[0])))
        return [s.FacetValue(key=k, count=n) for k, n in items]

    return s.Facets(
        kind=values(kinds),
        year=values(years, by_key=True),
        gouvernorat=values(gouvernorats),
        category=values(categories),
    )


async def _sql_facets(session: AsyncSession, principal: Principal, filters: Filters) -> s.Facets:
    where, params = _where(principal, filters)

    async def count(expression: str) -> list[s.FacetValue]:
        rows = await session.execute(
            text(
                f"SELECT key, count(*) AS n FROM (SELECT {expression} AS key FROM knowledge.search_doc d "  # noqa: S608
                f"WHERE {where}) f WHERE key IS NOT NULL GROUP BY key ORDER BY n DESC, key"
            ),
            params,
        )
        return [s.FacetValue(key=str(r.key), count=int(r.n)) for r in rows]

    years = await count("CAST(extract(year FROM d.date AT TIME ZONE 'Africa/Tunis') AS int)")
    return s.Facets(
        kind=await count("d.kind"),
        year=sorted(years, key=lambda v: v.key),
        gouvernorat=await count("unnest(d.gouvernorats)"),
        category=await count("unnest(d.categories)"),
    )


async def search(
    session: AsyncSession, principal: Principal, query: str, filters: Filters, limit: int, cursor: str | None
) -> s.SearchOut:
    offset = _decode(cursor)
    query = " ".join(query.split())
    terms = kt.query_terms(query) if query else []
    window = BROWSE_WINDOW if not query else CANDIDATES
    if offset >= window or (query and not terms):
        empty = s.Facets(kind=[], year=[], gouvernorat=[], category=[])
        return s.SearchOut(items=[], facets=empty, backend="postgres", semantic=False, next_cursor=None)
    size = min(window, offset + limit + 1) if not query else CANDIDATES

    backend: str = "postgres"
    highlights: dict[Key, str] = {}
    ranking: list[Key] | None = None
    if get_engine() is not None:
        try:
            ranking, highlights = await _os_rank(principal, filters, query or None, size)
            backend = "opensearch"
        except SearchUnavailable as exc:
            log.warning("library.opensearch_unavailable", error=str(exc))
    if ranking is None:
        ranking = (
            await _pg_text(session, principal, filters, terms, size)
            if query
            else await _pg_browse(session, principal, filters, size)
        )

    vector = await _query_vector(query) if query else None
    if vector is not None:
        fused = fuse([ranking, await _pg_vector(session, principal, filters, vector, CANDIDATES)])
    elif query:
        fused = fuse([ranking])
    else:
        fused = [(key, 0.0) for key in ranking]

    rows = await _rows(session, [key for key, _ in fused])
    accepted = [(rows[key], score) for key, score in fused if key in rows and visible(principal, rows[key], filters)]
    page = accepted[offset : offset + limit]
    more = len(accepted) > offset + limit and offset + limit < window
    items = []
    for row, score in page:
        key = (row.kind, row.ref_id)
        excerpt = highlights.get(key) or kt.excerpt(documents.stored_body(row), terms)
        items.append(_hit(row, score, excerpt))
    facets = _facets([row for row, _ in accepted]) if query else await _sql_facets(session, principal, filters)
    return s.SearchOut(
        items=items,
        facets=facets,
        backend=backend,
        semantic=vector is not None,
        next_cursor=_encode(offset + limit) if more else None,
    )


async def search_ids(
    session: AsyncSession, principal: Principal, q: str, kinds: list[str] | None = None
) -> list[Any] | None:
    """Ids of the matching items of ``kinds`` (best first), for other modules' own lists (e.g. the reports library).

    None when the search cannot answer (empty query, error): the caller falls back to its own filter. Never raises.
    """
    if not q.strip():
        return None
    try:
        filters = Filters(kinds=[Kind(k) for k in kinds] if kinds else [])
        result = await search(session, principal, q, filters, limit=CANDIDATES, cursor=None)
    except Exception:
        log.exception("library.search_ids_failed")
        return None
    found: list[Any] = []
    for hit in result.items:
        try:
            found.append(uuid.UUID(hit.id))
        except ValueError:
            found.append(hit.id)
    return found


# ---------------------------------------------------------------- calendar and tree


async def calendar_counts(
    session: AsyncSession, principal: Principal, filters: Filters, year: int, month: int
) -> s.CalendarOut:
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    span = Filters(
        kinds=filters.kinds,
        date_from=max(first, filters.date_from) if filters.date_from else first,
        date_to=min(last, filters.date_to) if filters.date_to else last,
        gouvernorat=filters.gouvernorat,
        category=filters.category,
    )
    where, params = _where(principal, span)
    rows = await session.execute(
        text(
            "SELECT CAST(d.date AT TIME ZONE 'Africa/Tunis' AS date) AS day, count(*) AS n "  # noqa: S608
            f"FROM knowledge.search_doc d WHERE {where} AND d.date IS NOT NULL GROUP BY day ORDER BY day"
        ),
        params,
    )
    return s.CalendarOut(year=year, month=month, days=[s.Day(date=r.day, count=int(r.n)) for r in rows])


async def _gouvernorat_labels(session: AsyncSession) -> dict[str, dict[str, str]]:
    rows = await session.execute(text("SELECT code, name_ar, name_fr FROM geo.gouvernorat"))
    return {str(r.code): {"ar": r.name_ar, "fr": r.name_fr} for r in rows}


async def tree(session: AsyncSession, principal: Principal, filters: Filters, by: str) -> s.TreeOut:
    where, params = _where(principal, filters)
    outer, inner = {
        "period": (
            "CAST(extract(year FROM d.date AT TIME ZONE 'Africa/Tunis') AS int)",
            "CAST(extract(month FROM d.date AT TIME ZONE 'Africa/Tunis') AS int)",
        ),
        "type": ("d.kind", "coalesce(d.categories[1], 'other')"),
        "gouvernorat": (
            "unnest(CASE WHEN d.gouvernorats = '{}' THEN ARRAY[0::smallint] ELSE d.gouvernorats END)",
            "d.kind",
        ),
    }[by]
    rows = await session.execute(
        text(
            f"SELECT a, b, count(*) AS n FROM (SELECT {outer} AS a, {inner} AS b FROM knowledge.search_doc d "  # noqa: S608
            f"WHERE {where}) t WHERE a IS NOT NULL GROUP BY a, b ORDER BY a, b"
        ),
        params,
    )
    gouvernorats = await _gouvernorat_labels(session) if by == "gouvernorat" else {}

    def label(level: str, key: str) -> dict[str, str] | None:
        if level == "kind":
            return KIND_LABELS.get(key)
        if level == "category":
            return CATEGORY_LABELS.get(key)
        if level == "gouvernorat":
            return gouvernorats.get(key) or ({"ar": "وطني", "fr": "National"} if key == "0" else None)
        return None

    levels = {"period": ("year", "month"), "type": ("kind", "category"), "gouvernorat": ("gouvernorat", "kind")}[by]
    nodes: dict[str, s.TreeNode] = {}
    for row in rows:
        top = str(row.a)
        node = nodes.setdefault(top, s.TreeNode(key=top, label=label(levels[0], top), count=0))
        node.count += int(row.n)
        child = str(row.b) if by != "period" else f"{int(row.a):04d}-{int(row.b):02d}"
        node.children.append(s.TreeNode(key=child, label=label(levels[1], str(row.b)), count=int(row.n)))
    ordered = list(nodes.values())
    if by == "period":
        ordered.reverse()
    else:
        ordered.sort(key=lambda n: -n.count)
    return s.TreeOut(by=by, nodes=ordered)


# ---------------------------------------------------------------- incident assistant (phase 7, sources.kind="memory")


async def memory_for_assistant(
    session: AsyncSession,
    principal: Principal,
    *,
    question: str,
    category: str | None,
    vector: list[float] | None,
    limit: int,
) -> list[SearchDoc]:
    """Published national memory entries the caller may read, best first: e5 similarity, words of the question,
    and the incident's category (the same candidate rule as the procedures library)."""
    where, params = _where(principal, Filters(kinds=[Kind.MEMORY]))
    terms = kt.query_terms(question)
    params.update(
        {
            "tsq": _tsquery(terms),
            "category": category or "",
            "v": str(vector) if vector is not None else None,
            "min_sim": MIN_SIMILARITY,
            "limit": limit,
        }
    )
    rows = await session.execute(
        text(
            f"""
            WITH scored AS (
                SELECT d.kind, d.ref_id,
                       CASE WHEN CAST(CAST(:v AS text) AS vector) IS NOT NULL AND d.embedding IS NOT NULL
                            THEN 1 - (d.embedding <=> CAST(CAST(:v AS text) AS vector)) ELSE 0 END AS similarity,
                       CASE WHEN :tsq <> '' THEN ts_rank_cd(d.search, to_tsquery('simple', :tsq)) ELSE 0 END AS rank,
                       :category = ANY(d.categories) AS category_match
                FROM knowledge.search_doc d
                WHERE {where}
            )
            SELECT kind, ref_id FROM scored
            WHERE similarity >= :min_sim OR rank > 0 OR category_match
            ORDER BY similarity + least(rank, 1) * 0.3 + CASE WHEN category_match THEN 0.2 ELSE 0 END DESC, ref_id
            LIMIT :limit
            """  # noqa: S608
        ),
        params,
    )
    keys = [(r.kind, r.ref_id) for r in rows]
    found = await _rows(session, keys)
    return [found[k] for k in keys if k in found and visible(principal, found[k], Filters(kinds=[Kind.MEMORY]))]
