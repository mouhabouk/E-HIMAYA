"""The figures of the decision window (L4 §3): the quick and the advanced search, the comparison, the situation now.

Everything is computed on interventions (``ops.incident``) within the caller's view (``access.Viewer``): the scope of
the account, and for a delegate the delegated events only. Aggregates only: counts, durations and areas; an
intervention row carries its category, severity, status, place (gouvernorat and delegation) and dates, never a title,
an address, a reporter, a phone number or a victim. A count between 1 and ``ANALYTICS_MIN_CELL`` - 1 is answered
``None`` (shown "<5"), and a duration computed on fewer interventions than that is left out (§3.5).

The reports figures (received, confirmed) follow the period, the scope, the category and the source; for a delegate
they are those of the reports grouped in the delegated interventions.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import as_system
from app.modules.analytics import domain as analytics_domain
from app.modules.analytics import service as analytics
from app.modules.ops.domain import CLASSIFICATIONS
from app.modules.reports.domain import CATEGORY_LABELS, Category
from app.modules.schedule import domain as schedule_domain
from app.modules.schedule.models import Item, Period
from app.modules.window import schemas
from app.modules.window.access import Viewer
from app.modules.window.models import Synonym

DEFAULT_SPAN = timedelta(days=30)
MAX_ITEMS = 200
# Interventions merged into another or dissolved are not counted twice.
COUNTED = "i.status NOT IN ('merged', 'dissolved')"
# Led by, or with the participation of, the gouvernorats of ``:codes``.
IN_SCOPE = (
    "(i.gouvernorat_code = ANY(CAST(:codes AS smallint[])) OR EXISTS (SELECT 1 FROM ops.incident_gouvernorat ig "
    "WHERE ig.incident_id = i.id AND ig.gouvernorat_code = ANY(CAST(:codes AS smallint[]))))"
)


def min_cell() -> int:
    return get_settings().analytics_min_cell


def floor(n: int | None) -> int | None:
    if n is None:
        return None
    return None if 0 < n < min_cell() else n


# ---------------------------------------------------------------- the quick search

_AR = str.maketrans({"ة": "ه", "ى": "ي", "ـ": None})
_SPLIT = re.compile(r"[\s,،؛;.!?()\"']+")
_HEX = re.compile(r"^[0-9a-f]{6,32}$")
# Little words left out of a quick search.
STOPWORDS = frozenset("في من الي على علي عن مع و de du des la le les en a au aux et in of the at on and".split())


def norm(raw: str) -> str:
    """Lower case, without accents, Arabic diacritics, tatweel or hamza seats; ``ة`` read ``ه``, ``ى`` read ``ي``."""
    decomposed = unicodedata.normalize("NFKD", raw.lower())
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(_SPLIT.split(plain.translate(_AR))).strip()


def _variants(word: str) -> list[str]:
    """A word as written, then without the Arabic article or a leading "و" (and)."""
    out = [word]
    for prefix in ("وال", "ال", "و"):
        if word.startswith(prefix) and len(word) - len(prefix) >= 2:
            out.append(word[len(prefix) :])
    return out


@dataclass
class Criteria:
    categories: set[str] = field(default_factory=set)
    classifications: set[str] = field(default_factory=set)
    gouvernorats: set[int] = field(default_factory=set)
    delegations: set[int] = field(default_factory=set)
    refs: set[str] = field(default_factory=set)
    words: set[str] = field(default_factory=set)


@dataclass
class Vocabulary:
    phrases: dict[str, tuple[str, str]]
    longest: int


async def vocabulary(session: AsyncSession) -> Vocabulary:
    """Every phrase the quick search knows, normalised: categories and classifications (their keys and labels in the
    three languages), gouvernorats, delegations, then the dictionary of the central room."""
    phrases: dict[str, tuple[str, str]] = {}

    def add(phrase: str, kind: str, key: str) -> None:
        n = norm(phrase)
        if n and n not in phrases:
            phrases[n] = (kind, key)

    for category in Category:
        add(category.value.replace("_", " "), "category", category.value)
        for label in CATEGORY_LABELS[category].values():
            add(label, "category", category.value)
    for keys in CLASSIFICATIONS.values():
        for key in keys:
            add(key.replace("_", " "), "classification", key)
    for code, ar, fr, en in (
        await session.execute(text("SELECT code, name_ar, name_fr, name_en FROM geo.gouvernorat"))
    ).all():
        for name in (ar, fr, en):
            add(name, "gouvernorat", str(code))
    for ident, ar, fr in (await session.execute(text("SELECT id, name_ar, name_fr FROM geo.delegation"))).all():
        for name in (ar, fr):
            add(name, "delegation", str(ident))
    async with as_system(session):
        synonyms = (await session.execute(select(Synonym.meaning, Synonym.words))).all()
    for meaning, words in synonyms:
        target = phrases.get(norm(meaning)) or (
            ("category", meaning)
            if meaning in {c.value for c in Category}
            else ("classification", meaning)
            if any(meaning in keys for keys in CLASSIFICATIONS.values())
            else ("word", meaning)
        )
        for word in words:
            n = norm(word)
            if n:
                phrases.setdefault(n, target)
    return Vocabulary(phrases, max((len(p.split()) for p in phrases), default=1))


def interpret(q: str, vocab: Vocabulary, words_allowed: bool) -> tuple[Criteria, list[schemas.Understood]]:
    """Read a quick search: the longest known phrase first; an identifier start is a reference; any other word is
    searched in the titles and classifications (full view only: a delegate's unknown words are left out)."""
    crit = Criteria()
    understood: list[schemas.Understood] = []
    tokens = [t for t in norm(q).split() if t not in STOPWORDS]
    i = 0
    while i < len(tokens):
        hit: tuple[int, str, str] | None = None
        for size in range(min(vocab.longest, len(tokens) - i), 0, -1):
            phrase = " ".join(tokens[i : i + size])
            for candidate in _variants(phrase) if size == 1 else [phrase]:
                if candidate in vocab.phrases:
                    hit = (size, *vocab.phrases[candidate])
                    break
            if hit:
                break
        if hit is None:
            word = tokens[i]
            compact = word.replace("-", "")
            if _HEX.match(compact):
                crit.refs.add(compact)
                understood.append(schemas.Understood(text=word, kind="reference", key=compact))
            elif words_allowed and len(word) >= 2:
                crit.words.add(word)
                understood.append(schemas.Understood(text=word, kind="word", key=word))
            else:
                understood.append(schemas.Understood(text=word, kind="unmatched"))
            i += 1
            continue
        size, kind, key = hit
        shown = " ".join(tokens[i : i + size])
        if kind == "category":
            crit.categories.add(key)
        elif kind == "classification":
            crit.classifications.add(key)
        elif kind == "gouvernorat":
            crit.gouvernorats.add(int(key))
        elif kind == "delegation":
            crit.delegations.add(int(key))
        elif words_allowed:
            crit.words.add(norm(key))
        else:
            kind = "unmatched"
        understood.append(schemas.Understood(text=shown, kind=kind, key=key if kind != "unmatched" else None))
        i += size
    return crit, understood


# ---------------------------------------------------------------- the condition on the interventions


@dataclass
class Query:
    where: str
    params: dict[str, Any]
    start: date
    end: date
    codes: list[int]
    # The condition on the reports of the same scope, period, category and source.
    report_where: str
    report_params: dict[str, Any]


def period_of(raw_from: date | None, raw_to: date | None) -> tuple[date, date]:
    return analytics.period(raw_from, raw_to, DEFAULT_SPAN)


def build(viewer: Viewer, f: schemas.Filters, start: date, end: date, crit: Criteria | None = None) -> Query:
    codes = analytics.resolve_scope(viewer.principal, f.gouvernorats or None)
    if not codes and viewer.codes:
        codes = viewer.codes
    clauses = [COUNTED, "i.opened_at >= :t0", "i.opened_at < :t1"]
    bounds = {"t0": analytics_domain.day_start(start), "t1": analytics_domain.day_start(end + timedelta(days=1))}
    params: dict[str, Any] = dict(bounds)
    if codes:
        clauses.append(IN_SCOPE)
        params["codes"] = codes
    if viewer.incident_ids is not None:
        clauses.append("i.id = ANY(CAST(:ids AS uuid[]))")
        params["ids"] = viewer.incident_ids
    if f.delegation is not None:
        clauses.append("i.delegation_id = :delegation")
        params["delegation"] = f.delegation
    if f.category:
        clauses.append("i.category = ANY(:category)")
        params["category"] = f.category
    if f.classification:
        clauses.append("i.classification = ANY(:classification)")
        params["classification"] = f.classification
    if f.severity:
        clauses.append("i.severity = ANY(CAST(:severity AS smallint[]))")
        params["severity"] = f.severity
    if f.status:
        clauses.append("i.status = ANY(:status)")
        params["status"] = f.status
    if f.source:
        clauses.append(
            "EXISTS (SELECT 1 FROM reports.report rs WHERE rs.incident_id = i.id AND rs.source = ANY(:source))"
        )
        params["source"] = f.source
    if f.unit is not None:
        clauses.append(
            "EXISTS (SELECT 1 FROM ops.assignment a JOIN ops.resource res ON res.id = a.resource_id "
            "WHERE a.incident_id = i.id AND res.unit_id = :unit)"
        )
        params["unit"] = f.unit
    if f.org is not None:
        clauses.append(
            "EXISTS (SELECT 1 FROM reports.report ro WHERE ro.incident_id = i.id AND ro.organization_id = :org)"
        )
        params["org"] = f.org
    if crit is not None:
        if crit.categories:
            clauses.append("i.category = ANY(:q_category)")
            params["q_category"] = sorted(crit.categories)
        if crit.classifications:
            clauses.append("i.classification = ANY(:q_classification)")
            params["q_classification"] = sorted(crit.classifications)
        if crit.gouvernorats:
            clauses.append(
                "(i.gouvernorat_code = ANY(CAST(:q_codes AS smallint[])) OR EXISTS (SELECT 1 "
                "FROM ops.incident_gouvernorat qg WHERE qg.incident_id = i.id "
                "AND qg.gouvernorat_code = ANY(CAST(:q_codes AS smallint[]))))"
            )
            params["q_codes"] = sorted(crit.gouvernorats)
        if crit.delegations:
            clauses.append("i.delegation_id = ANY(:q_delegations)")
            params["q_delegations"] = sorted(crit.delegations)
        if crit.refs:
            clauses.append("replace(CAST(i.id AS text), '-', '') LIKE ANY(:q_refs)")
            params["q_refs"] = [f"{r}%" for r in sorted(crit.refs)]
        if crit.words:
            clauses.append("(i.title ILIKE ANY(:q_words) OR i.classification ILIKE ANY(:q_words))")
            params["q_words"] = [f"%{w}%" for w in sorted(crit.words)]

    report_clauses = ["r.received_at >= :t0", "r.received_at < :t1"]
    report_params: dict[str, Any] = dict(bounds)
    if viewer.incident_ids is not None:
        report_clauses.append("r.incident_id = ANY(CAST(:ids AS uuid[]))")
        report_params["ids"] = viewer.incident_ids
    if codes:
        report_clauses.append("r.gouvernorat_code = ANY(CAST(:codes AS smallint[]))")
        report_params["codes"] = codes
    categories = sorted(set(f.category) | (crit.categories if crit else set()))
    if categories:
        report_clauses.append("r.category = ANY(:category)")
        report_params["category"] = categories
    if f.source:
        report_clauses.append("r.source = ANY(:source)")
        report_params["source"] = f.source
    return Query(" AND ".join(clauses), params, start, end, codes, " AND ".join(report_clauses), report_params)


# ---------------------------------------------------------------- figures

_GROUPS = {
    "by_category": "i.category",
    "by_severity": "CAST(i.severity AS text)",
    "by_status": "i.status",
    "by_gouvernorat": "CAST(i.gouvernorat_code AS text)",
}


def _cells(rows: Any) -> list[schemas.Cell]:
    return [schemas.Cell(key=str(k) if k is not None else "unknown", count=floor(int(n))) for k, n in rows]


def _minutes(seconds: Any, n: Any) -> float | None:
    if seconds is None or int(n or 0) < min_cell():
        return None
    return round(float(seconds) / 60.0, 1)


async def figures(session: AsyncSession, q: Query) -> schemas.Figures:
    w, p = q.where, q.params
    groups: dict[str, list[schemas.Cell]] = {}
    for name, expression in _GROUPS.items():
        rows = await session.execute(
            text(f"SELECT {expression} AS k, count(*) FROM ops.incident i WHERE {w} GROUP BY k ORDER BY 2 DESC, 1"),  # noqa: S608 (constant SQL fragments, values are bound)
            p,
        )
        groups[name] = _cells(rows.all())
    step = "day" if (q.end - q.start).days <= 62 else "month"
    local = "(i.opened_at AT TIME ZONE 'Africa/Tunis')"
    series = await session.execute(
        text(
            f"SELECT to_char(date_trunc('{step}', {local}), 'YYYY-MM-DD') AS k, count(*) "  # noqa: S608 (constant SQL fragments, values are bound)
            f"FROM ops.incident i WHERE {w} GROUP BY k ORDER BY k"
        ),
        p,
    )
    totals = (
        await session.execute(
            text(
                "SELECT count(*), "  # noqa: S608 (constant SQL fragments, values are bound)
                "sum(c.injured_light + c.injured_serious), sum(c.deceased), sum(c.rescued), "
                "sum(CASE WHEN i.category = 'fire' AND i.area IS NOT NULL THEN ST_Area(i.area) END) / 10000.0 "
                f"FROM ops.incident i LEFT JOIN ops.casualty_count c ON c.incident_id = i.id WHERE {w}"
            ),
            p,
        )
    ).one()
    times = (
        await session.execute(
            text(
                "WITH t AS (SELECT i.opened_at, "  # noqa: S608 (constant SQL fragments, values are bound)
                "(SELECT min(a.created_at) FROM ops.assignment a WHERE a.incident_id = i.id) AS assigned, "
                "(SELECT min(a.on_scene_at) FROM ops.assignment a WHERE a.incident_id = i.id) AS on_scene "
                f"FROM ops.incident i WHERE {w}) "
                "SELECT avg(extract(epoch FROM assigned - opened_at)) FILTER (WHERE assigned >= opened_at), "
                "count(*) FILTER (WHERE assigned >= opened_at), "
                "avg(extract(epoch FROM on_scene - opened_at)) FILTER (WHERE on_scene >= opened_at), "
                "count(*) FILTER (WHERE on_scene >= opened_at) FROM t"
            ),
            p,
        )
    ).one()
    verified = [s.value for s in analytics_domain.VERIFIED_STATUSES]
    reports = (
        await session.execute(
            text(
                "SELECT count(*), count(*) FILTER (WHERE r.status = ANY(:verified)) "  # noqa: S608 (constant SQL fragments, values are bound)
                f"FROM reports.report r WHERE {q.report_where}"
            ),
            q.report_params | {"verified": verified},
        )
    ).one()
    received, confirmed = int(reports[0]), int(reports[1])
    burned = float(totals[4]) if totals[4] is not None else None
    return schemas.Figures(
        incidents=floor(int(totals[0])),
        by_category=groups["by_category"],
        by_severity=groups["by_severity"],
        by_status=groups["by_status"],
        by_gouvernorat=groups["by_gouvernorat"],
        series_step=step,
        series=_cells(series.all()),
        injured=floor(int(totals[1] or 0)),
        deceased=floor(int(totals[2] or 0)),
        rescued=floor(int(totals[3] or 0)),
        burned_ha=round(burned, 1) if burned is not None else None,
        to_assignment_min=_minutes(times[0], times[1]),
        to_on_scene_min=_minutes(times[2], times[3]),
        reports=floor(received),
        confirmed=floor(confirmed),
        confirmed_rate=round(confirmed / received, 3) if received >= min_cell() else None,
    )


async def items(session: AsyncSession, q: Query) -> tuple[list[schemas.IncidentRow], bool]:
    rows = (
        await session.execute(
            text(
                "SELECT i.id, i.category, i.classification, i.severity, i.status, i.gouvernorat_code, "  # noqa: S608 (constant SQL fragments, values are bound)
                "i.delegation_id, i.opened_at, i.closed_at, (SELECT x.number FROM crisis.axis_incident ai "
                "JOIN crisis.axis x ON x.id = ai.axis_id WHERE ai.incident_id = i.id AND ai.detached_at IS NULL "
                f"ORDER BY ai.attached_at DESC LIMIT 1) FROM ops.incident i WHERE {q.where} "
                "ORDER BY i.opened_at DESC LIMIT :limit"
            ),
            q.params | {"limit": MAX_ITEMS + 1},
        )
    ).all()
    out = [
        schemas.IncidentRow(
            id=r[0],
            ref=r[0].hex[:8],
            category=r[1],
            classification=r[2],
            severity=r[3],
            status=r[4],
            gouvernorat_code=r[5],
            delegation_id=r[6],
            opened_at=r[7],
            closed_at=r[8],
            axis_number=r[9],
        )
        for r in rows[:MAX_ITEMS]
    ]
    return out, len(rows) > MAX_ITEMS


async def search(session: AsyncSession, viewer: Viewer, f: schemas.Filters) -> schemas.SearchOut:
    start, end = period_of(f.from_, f.to)
    crit: Criteria | None = None
    understood: list[schemas.Understood] = []
    if f.q and f.q.strip():
        crit, understood = interpret(f.q, await vocabulary(session), words_allowed=viewer.full)
    q = build(viewer, f, start, end, crit)
    rows, truncated = await items(session, q)
    return schemas.SearchOut(
        from_=start,
        to=end,
        gouvernorats=q.codes,
        understood=understood,
        figures=await figures(session, q),
        items=rows,
        truncated=truncated,
        delegated=viewer.delegated,
        min_cell=min_cell(),
    )


# ---------------------------------------------------------------- the comparison


async def programmes(session: AsyncSession, codes: list[int], start: date, end: date) -> schemas.Programmes:
    """The seasonal programmes running in the period (L2) and the programme activities due in it (PL2)."""

    scope = "TRUE" if not codes else "pt.gouvernorat_code = ANY(CAST(:codes AS smallint[]))"
    row = (
        await session.execute(
            text(
                "SELECT count(DISTINCT p.id), count(pt.id), coalesce(sum(pt.lifeguards_planned), 0), "  # noqa: S608 (constant SQL fragments, values are bound)
                "coalesce(sum(pt.lifeguards_deployed), 0) FROM programme.programme p "
                "JOIN programme.point pt ON pt.programme_id = p.id "
                f"WHERE p.status <> 'cancelled' AND p.valid_from <= :end AND p.valid_to >= :start AND {scope}"
            ),
            {"start": start, "end": end, "codes": codes},
        )
    ).one()
    query = (
        select(Item)
        .join(Period, Period.id == Item.period_id)
        .where(Item.on_date >= start, Item.on_date <= end, Period.status == "approved")
    )
    if codes:
        query = query.where(Item.gouvernorat_code.in_(codes))
    now = datetime.now(UTC)
    today = analytics_domain.local_today(now)
    due = done = 0
    for item in await session.scalars(query.limit(20_000)):
        state, _ = schedule_domain.follow_up(
            item.status, item.status_manual, True, item.on_date, item.starts_at, item.ends_at, now
        )
        if item.on_date <= today and state not in schedule_domain.LEFT_OUT:
            due += 1
            done += state == "done"
    return schemas.Programmes(
        programmes=int(row[0]),
        posts=int(row[1]),
        lifeguards_planned=int(row[2]),
        lifeguards_deployed=int(row[3]),
        activities_due=due,
        activities_done=done,
        rate=round(done / due, 3) if due else None,
    )


def _delta(a: float | None, b: float | None) -> tuple[float | None, float | None]:
    if a is None or b is None:
        return None, None
    delta = round(b - a, 3)
    return delta, (round(delta / a, 3) if a else None)


def _row(metric: str, a: float | None, b: float | None, key: str | None = None) -> schemas.CompareRow:
    delta, pct = _delta(a, b)
    return schemas.CompareRow(metric=metric, key=key, a=a, b=b, delta=delta, pct=pct)


_SCALARS = (
    "incidents",
    "injured",
    "deceased",
    "rescued",
    "burned_ha",
    "to_assignment_min",
    "to_on_scene_min",
    "reports",
    "confirmed",
    "confirmed_rate",
)
_BREAKDOWNS = {"category": "by_category", "severity": "by_severity", "gouvernorat": "by_gouvernorat"}


def rows_of(a: schemas.Side, b: schemas.Side) -> list[schemas.CompareRow]:
    out = [_row(m, getattr(a.figures, m), getattr(b.figures, m)) for m in _SCALARS]
    for metric, attribute in _BREAKDOWNS.items():
        left = {c.key: c.count for c in getattr(a.figures, attribute)}
        right = {c.key: c.count for c in getattr(b.figures, attribute)}
        for key in sorted(left.keys() | right.keys()):
            out.append(_row(metric, left.get(key, 0), right.get(key, 0), key))
    if a.programmes and b.programmes:
        for m in ("programmes", "posts", "lifeguards_planned", "lifeguards_deployed", "activities_done", "rate"):
            out.append(_row(f"programmes.{m}", getattr(a.programmes, m), getattr(b.programmes, m)))
    return out


async def _side(
    session: AsyncSession, viewer: Viewer, f: schemas.Filters, start: date, end: date, label: str
) -> schemas.Side:
    q = build(viewer, f, start, end)
    return schemas.Side(
        label=label,
        from_=start,
        to=end,
        gouvernorats=q.codes,
        figures=await figures(session, q),
        programmes=await programmes(session, q.codes, start, end) if viewer.full else None,
    )


async def compare(session: AsyncSession, viewer: Viewer, body: schemas.CompareIn) -> schemas.CompareOut:
    f = body.filters.model_copy(update={"q": None})
    if body.mode == "periods":
        a_start, a_end = period_of(body.a_from, body.a_to)
        b_start, b_end = period_of(body.b_from, body.b_to)
        a = await _side(session, viewer, f, a_start, a_end, f"{a_start} → {a_end}")
        b = await _side(session, viewer, f, b_start, b_end, f"{b_start} → {b_end}")
    else:
        if body.a_gouvernorat is None or body.b_gouvernorat is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "two_gouvernorats_required")
        start, end = period_of(f.from_, f.to)
        a = await _side(session, viewer, f.model_copy(update={"gouvernorats": [body.a_gouvernorat]}), start, end, "a")
        b = await _side(session, viewer, f.model_copy(update={"gouvernorats": [body.b_gouvernorat]}), start, end, "b")
    return schemas.CompareOut(
        mode=body.mode, a=a, b=b, rows=rows_of(a, b), delegated=viewer.delegated, min_cell=min_cell()
    )


# ---------------------------------------------------------------- the situation now


async def now(session: AsyncSession, viewer: Viewer) -> schemas.NowOut:
    at = datetime.now(UTC)
    axis_where = ["x.status = 'open'"]
    params: dict[str, Any] = {}
    if viewer.axis_ids is not None:
        axis_where.append("x.id = ANY(CAST(:axes AS uuid[]))")
        params["axes"] = viewer.axis_ids
    if viewer.codes:
        axis_where.append("x.gouvernorat_code = ANY(CAST(:codes AS smallint[]))")
        params["codes"] = viewer.codes
    axes = [
        schemas.AxisNow(
            id=r[0],
            number=r[1],
            name=r[2],
            kind=r[3],
            level=r[4],
            scope=r[5],
            gouvernorat_code=r[6],
            opened_at=r[7],
            plan=r[8],
            plan_document_id=r[9],
            plan_title=r[10],
            incidents=int(r[11]),
        )
        for r in (
            await session.execute(
                text(
                    "SELECT x.id, x.number, x.name, x.kind, x.level, x.scope, x.gouvernorat_code, x.opened_at, "  # noqa: S608 (constant SQL fragments, values are bound)
                    "x.plan, x.plan_document_id, d.title, (SELECT count(*) FROM crisis.axis_incident ai "
                    "WHERE ai.axis_id = x.id AND ai.detached_at IS NULL) FROM crisis.axis x "
                    "LEFT JOIN register.document d ON d.id = x.plan_document_id "
                    f"WHERE {' AND '.join(axis_where)} ORDER BY x.level DESC, x.opened_at DESC LIMIT 50"
                ),
                params,
            )
        ).all()
    ]

    incident_where = [COUNTED, "i.status = 'open'"]
    incident_params: dict[str, Any] = {}
    if viewer.codes:
        incident_where.append(IN_SCOPE)
        incident_params["codes"] = viewer.codes
    if viewer.incident_ids is not None:
        incident_where.append("i.id = ANY(CAST(:ids AS uuid[]))")
        incident_params["ids"] = viewer.incident_ids
    by_severity = (
        await session.execute(
            text(
                "SELECT CAST(i.severity AS text) AS k, count(*) FROM ops.incident i "  # noqa: S608 (constant SQL fragments, values are bound)
                f"WHERE {' AND '.join(incident_where)} GROUP BY k ORDER BY k DESC NULLS LAST"
            ),
            incident_params,
        )
    ).all()
    # Live operational counts of interventions (no person in them): not floored, unlike the statistics of a period.
    open_cells = [schemas.Cell(key=str(k) if k is not None else "unknown", count=int(n)) for k, n in by_severity]

    resources = progress = None
    if viewer.full:
        scope = "TRUE" if not viewer.codes else "u.gouvernorat_code = ANY(CAST(:codes AS smallint[]))"
        resources = [
            schemas.ResourceNow(kind=k, available=int(a), assigned=int(s), out_of_service=int(o))
            for k, a, s, o in (
                await session.execute(
                    text(
                        "SELECT r.kind, count(*) FILTER (WHERE r.status = 'available'), "  # noqa: S608 (constant SQL fragments, values are bound)
                        "count(*) FILTER (WHERE r.status = 'assigned'), "
                        "count(*) FILTER (WHERE r.status = 'out_of_service') "
                        f"FROM ops.resource r JOIN ops.unit u ON u.id = r.unit_id WHERE {scope} "
                        "GROUP BY r.kind ORDER BY 2 DESC, 1"
                    ),
                    {"codes": viewer.codes},
                )
            ).all()
        ]
        progress = await _progress(session, viewer)

    decision_where = ["TRUE"]
    decision_params: dict[str, Any] = {}
    if viewer.axis_ids is not None:
        decision_where.append("x.id = ANY(CAST(:axes AS uuid[]))")
        decision_params["axes"] = viewer.axis_ids
    if viewer.codes:
        decision_where.append("x.gouvernorat_code = ANY(CAST(:codes AS smallint[]))")
        decision_params["codes"] = viewer.codes
    decisions = [
        schemas.DecisionNow(
            id=r[0],
            axis_id=r[1],
            axis_number=r[2],
            number=r[3],
            kind=r[4],
            category=r[5],
            body=r[6][:300],
            issuer_role=r[7],
            issued_at=r[8],
            status=r[9],
        )
        for r in (
            await session.execute(
                text(
                    "SELECT d.id, x.id, x.number, d.number, d.kind, d.category, d.body, d.issuer_role, "  # noqa: S608 (constant SQL fragments, values are bound)
                    "d.issued_at, d.status FROM crisis.directive d JOIN crisis.axis x ON x.id = d.axis_id "
                    f"WHERE {' AND '.join(decision_where)} ORDER BY d.issued_at DESC LIMIT 8"
                ),
                decision_params,
            )
        ).all()
    ]
    return schemas.NowOut(
        at=at,
        delegated=viewer.delegated,
        axes=axes,
        open_incidents=open_cells,
        open_total=sum(c.count or 0 for c in open_cells),
        resources=resources,
        progress=progress,
        decisions=decisions,
    )


async def _progress(session: AsyncSession, viewer: Viewer) -> list[schemas.ProgressNow]:
    from app.modules.schedule.router import get_progress

    today = analytics_domain.local_today()
    day = await get_progress(viewer.principal, session, "day", today)
    week = {r.gouvernorat_code: r for r in (await get_progress(viewer.principal, session, "week", today)).rows}
    out = []
    for r in day.rows:
        w = week.get(r.gouvernorat_code)
        out.append(
            schemas.ProgressNow(
                gouvernorat_code=r.gouvernorat_code,
                gouvernorat_name=r.gouvernorat_name,
                day_due=r.counts.due,
                day_done=r.counts.done,
                day_rate=r.counts.rate,
                week_due=w.counts.due if w else 0,
                week_done=w.counts.done if w else 0,
                week_rate=w.counts.rate if w else None,
            )
        )
    return out
