"""Register of plans, decisions and instructions, the work on the database (phase L3b, docs/phase-l/design-l3b.md)."""

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.core.storage import get_store
from app.modules.audit import service as audit
from app.modules.geo.models import Gouvernorat
from app.modules.knowledge import text as kt
from app.modules.register import domain, schemas
from app.modules.register.models import Document, Link, Recommendation, Revision

# Fields of a document a revision keeps (the text of the search is derived, the file is its key and hash).
SNAPSHOT_FIELDS = (
    "reference",
    "kind",
    "level",
    "gouvernorat_code",
    "issuer",
    "signatory",
    "title",
    "summary",
    "body",
    "topics",
    "issued_on",
    "effective_from",
    "effective_to",
    "status",
    "repeal_reason",
    "access",
    "axis_ids",
    "file_name",
    "file_sha256",
)
PAGE_MAX = 100


def now() -> datetime:
    return datetime.now(UTC)


def today() -> date:
    return now().date()


def error(code: int, detail: str) -> HTTPException:
    return HTTPException(code, detail)


def not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "document_not_found")


def conflict(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail)


def forbidden(detail: str = "insufficient_role") -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, detail)


async def next_number(session: AsyncSession, year: int) -> str:
    n = await session.scalar(
        text(
            "INSERT INTO register.counter (year, last) VALUES (:y, 1) "
            "ON CONFLICT (year) DO UPDATE SET last = register.counter.last + 1 RETURNING last"
        ),
        {"y": year},
    )
    return f"REG-{year}-{int(n or 0):04d}"


async def gouvernorat_names(session: AsyncSession) -> dict[int, str]:
    rows = await session.execute(select(Gouvernorat.code, Gouvernorat.name_ar))
    return dict(rows.all())


def _value(v: Any) -> Any:
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, list):
        return [_value(x) for x in v]
    return v


def snapshot(doc: Document) -> dict[str, Any]:
    return {name: _value(getattr(doc, name)) for name in SNAPSHOT_FIELDS}


def refresh_norm(doc: Document) -> None:
    doc.norm = domain.norm_text(
        [doc.number, doc.reference, doc.title, doc.issuer, doc.signatory, doc.summary, doc.body, " ".join(doc.topics)]
    )


async def add_revision(
    session: AsyncSession, doc: Document, principal: Principal | None, change: str, reason: str | None
) -> None:
    session.add(
        Revision(
            document_id=doc.id,
            version=doc.version,
            snapshot=snapshot(doc),
            change=change,
            reason=reason,
            created_by=audit.actor_of(principal),
            created_by_name=audit.name_of(principal),
            created_at=now(),
        )
    )


async def get(session: AsyncSession, document_id: uuid.UUID, *, lock: bool = False) -> Document:
    query = select(Document).where(Document.id == document_id)
    found = await session.scalar(query.with_for_update() if lock else query)
    if found is None:
        raise not_found()
    return found


def readable(principal: Principal, doc: Document) -> bool:
    return domain.can_read(
        principal,
        access=doc.access,
        gouvernorat_code=doc.gouvernorat_code,
        status=doc.status,
        created_by=doc.created_by,
        actor=audit.actor_of(principal),
    )


def editable(principal: Principal, doc: Document) -> bool:
    return doc.source == "manual" and domain.can_write(principal, doc.level, doc.gouvernorat_code)


async def visible(
    session: AsyncSession, principal: Principal, document_id: uuid.UUID, *, lock: bool = False
) -> Document:
    doc = await get(session, document_id, lock=lock)
    if not readable(principal, doc):
        # Same answer as a document outside the scope: its existence is not disclosed.
        raise not_found()
    return doc


def _check(principal: Principal, body: schemas.DocumentIn) -> None:
    if body.level == "central" and body.gouvernorat_code is not None:
        raise error(status.HTTP_422_UNPROCESSABLE_CONTENT, "central_without_gouvernorat")
    if body.level == "regional" and body.gouvernorat_code is None:
        raise error(status.HTTP_422_UNPROCESSABLE_CONTENT, "gouvernorat_required")
    if body.kind == "temporary_instruction" and body.effective_to is None:
        raise error(status.HTTP_422_UNPROCESSABLE_CONTENT, "end_date_required")
    start = body.effective_from or body.issued_on
    if body.effective_to is not None and body.effective_to < start:
        raise error(status.HTTP_422_UNPROCESSABLE_CONTENT, "dates_out_of_order")
    if not domain.can_write(principal, body.level, body.gouvernorat_code):
        raise forbidden("out_of_scope")


def _apply(doc: Document, body: schemas.DocumentIn) -> None:
    doc.reference = body.reference
    doc.kind = body.kind
    doc.level = body.level
    doc.gouvernorat_code = body.gouvernorat_code
    doc.issuer = body.issuer
    doc.signatory = body.signatory
    doc.title = body.title
    doc.summary = body.summary
    doc.body = body.body
    doc.topics = list(dict.fromkeys(t for t in body.topics if t))
    doc.issued_on = body.issued_on
    doc.effective_from = body.effective_from
    doc.effective_to = body.effective_to
    doc.access = body.access
    doc.axis_ids = list(dict.fromkeys(body.axis_ids))


def _published_status(doc: Document) -> str:
    return domain.status_on("in_force", doc.effective_to, today())


async def create(session: AsyncSession, principal: Principal, body: schemas.DocumentIn) -> Document:
    _check(principal, body)
    actor, name = audit.actor_of(principal), audit.name_of(principal)
    doc = Document(
        id=uuid.uuid4(),
        number=await next_number(session, body.issued_on.year if body.issued_on.year >= 2000 else today().year),
        source="manual",
        created_by=actor,
        created_by_name=name,
        updated_by=actor,
        updated_by_name=name,
        created_at=now(),
        updated_at=now(),
        version=1,
        status="draft",
    )
    _apply(doc, body)
    if body.publish:
        doc.status = _published_status(doc)
    refresh_norm(doc)
    session.add(doc)
    await session.flush()
    await add_revision(session, doc, principal, "created", None)
    await audit.record(
        session,
        actor=actor,
        action="register.document_created",
        target=str(doc.id),
        details={"number": doc.number, "kind": doc.kind, "level": doc.level, "status": doc.status},
        gouvernorats=[doc.gouvernorat_code] if doc.gouvernorat_code else None,
    )
    return doc


async def update_document(
    session: AsyncSession, principal: Principal, doc: Document, body: schemas.DocumentPatch
) -> Document:
    if not editable(principal, doc):
        raise forbidden("out_of_scope")
    if doc.version != body.version:
        raise conflict("version_conflict")
    if doc.status == "repealed":
        raise conflict("document_repealed")
    _check(principal, body)
    _apply(doc, body)
    if body.publish and doc.status == "draft":
        doc.status = _published_status(doc)
    elif doc.status in ("in_force", "expired"):
        doc.status = _published_status(doc)
    doc.version += 1
    doc.updated_by, doc.updated_by_name, doc.updated_at = audit.actor_of(principal), audit.name_of(principal), now()
    refresh_norm(doc)
    await session.flush()
    await add_revision(session, doc, principal, "updated", body.reason)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="register.document_updated",
        target=str(doc.id),
        reason=body.reason,
        details={"number": doc.number, "version": doc.version, "status": doc.status},
        gouvernorats=[doc.gouvernorat_code] if doc.gouvernorat_code else None,
    )
    return doc


async def repeal(
    session: AsyncSession, principal: Principal | None, doc: Document, reason: str, by: Document | None
) -> Document:
    """A document in force (or expired) stops applying; a draft is not repealed but deleted."""
    if doc.status in ("draft", "repealed"):
        raise conflict(f"document_{doc.status}")
    doc.status = "repealed"
    doc.repeal_reason = reason
    doc.repealed_by = by.id if by is not None else None
    doc.version += 1
    doc.updated_by, doc.updated_by_name, doc.updated_at = audit.actor_of(principal), audit.name_of(principal), now()
    await session.flush()
    if by is not None:
        await _link(session, principal, by, doc, "repeals")
    await add_revision(session, doc, principal, "repealed", reason)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="register.document_repealed",
        target=str(doc.id),
        reason=reason,
        details={"number": doc.number, "by": by.number if by else None},
        gouvernorats=[doc.gouvernorat_code] if doc.gouvernorat_code else None,
    )
    return doc


async def delete_draft(session: AsyncSession, principal: Principal, doc: Document) -> None:
    if doc.status != "draft":
        raise conflict("not_a_draft")
    if not editable(principal, doc):
        raise forbidden("out_of_scope")
    if doc.file_key:
        await get_store().delete(doc.file_key)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="register.draft_deleted",
        target=str(doc.id),
        details={"number": doc.number},
        gouvernorats=[doc.gouvernorat_code] if doc.gouvernorat_code else None,
    )
    await session.delete(doc)
    await session.flush()


async def _link(
    session: AsyncSession, principal: Principal | None, src: Document, dst: Document, relation: str
) -> None:
    existing = await session.get(Link, (src.id, dst.id))
    if existing is not None:
        existing.relation = relation
    else:
        session.add(Link(from_id=src.id, to_id=dst.id, relation=relation, created_by=audit.actor_of(principal)))
    await session.flush()


async def link(session: AsyncSession, principal: Principal, src: Document, dst: Document, relation: str) -> None:
    if src.id == dst.id:
        raise error(status.HTTP_422_UNPROCESSABLE_CONTENT, "self_link")
    if not editable(principal, src):
        raise forbidden("out_of_scope")
    if relation == "repeals":
        if not domain.can_write(principal, dst.level, dst.gouvernorat_code):
            raise forbidden("out_of_scope")
        await repeal(session, principal, dst, f"{src.number} {src.reference}".strip(), src)
        return
    await _link(session, principal, src, dst, relation)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="register.document_linked",
        target=str(src.id),
        details={"to": dst.number, "relation": relation},
    )


async def unlink(session: AsyncSession, principal: Principal, src: Document, dst_id: uuid.UUID) -> None:
    if not editable(principal, src):
        raise forbidden("out_of_scope")
    found = await session.get(Link, (src.id, dst_id))
    if found is None:
        raise error(status.HTTP_404_NOT_FOUND, "link_not_found")
    if found.relation == "repeals":
        raise conflict("repeal_is_final")
    await session.delete(found)
    await session.flush()


# --- File -----------------------------------------------------------------------------------------------------------


def file_key(doc: Document, content_type: str) -> str:
    return f"register/{doc.id}/{uuid.uuid4().hex}{domain.FILE_SUFFIX[content_type]}"


async def attach_file(
    session: AsyncSession, principal: Principal, doc: Document, name: str, data: bytes, declared: str | None
) -> Document:
    if not editable(principal, doc):
        raise forbidden("out_of_scope")
    if not data:
        raise error(status.HTTP_422_UNPROCESSABLE_CONTENT, "file_empty")
    content_type = domain.file_type(data, declared)
    if content_type is None:
        raise error(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "file_type_not_allowed")
    key = file_key(doc, content_type)
    await get_store().put(key, data, content_type)
    old = doc.file_key
    doc.file_key, doc.file_name, doc.file_type = key, name[:200], content_type
    doc.file_size, doc.file_sha256 = len(data), hashlib.sha256(data).hexdigest()
    doc.version += 1
    doc.updated_by, doc.updated_by_name, doc.updated_at = audit.actor_of(principal), audit.name_of(principal), now()
    await session.flush()
    await add_revision(session, doc, principal, "file", None)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="register.file_attached",
        target=str(doc.id),
        details={"number": doc.number, "sha256": doc.file_sha256, "size": doc.file_size, "type": content_type},
        gouvernorats=[doc.gouvernorat_code] if doc.gouvernorat_code else None,
    )
    if old:
        await get_store().delete(old)
    return doc


# --- Recommendations ------------------------------------------------------------------------------------------------


async def add_recommendation(
    session: AsyncSession, principal: Principal, doc: Document, body: schemas.RecommendationIn
) -> Recommendation:
    if not domain.can_write(principal, doc.level, doc.gouvernorat_code):
        raise forbidden("out_of_scope")
    number = (
        int(
            await session.scalar(
                select(func.coalesce(func.max(Recommendation.number), 0)).where(Recommendation.document_id == doc.id)
            )
            or 0
        )
        + 1
    )
    rec = Recommendation(
        id=uuid.uuid4(),
        document_id=doc.id,
        number=number,
        body=body.body,
        responsible=body.responsible,
        due_on=body.due_on,
        status="proposed",
        updated_by=audit.actor_of(principal),
        updated_by_name=audit.name_of(principal),
        updated_at=now(),
    )
    session.add(rec)
    await session.flush()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="register.recommendation_added",
        target=str(doc.id),
        details={"number": doc.number, "recommendation": number},
    )
    return rec


async def set_recommendation_status(
    session: AsyncSession, principal: Principal, doc: Document, rec: Recommendation, new: str, reason: str
) -> Recommendation:
    if not domain.can_write(principal, doc.level, doc.gouvernorat_code):
        raise forbidden("out_of_scope")
    if new == "dropped" and len(reason) < 5:
        raise error(status.HTTP_422_UNPROCESSABLE_CONTENT, "reason_required")
    rec.status, rec.status_reason = new, reason or None
    rec.updated_by, rec.updated_by_name, rec.updated_at = audit.actor_of(principal), audit.name_of(principal), now()
    await session.flush()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="register.recommendation_status",
        target=str(doc.id),
        reason=reason or None,
        details={"number": doc.number, "recommendation": rec.number, "status": new},
    )
    return rec


def recommendation_out(r: Recommendation) -> schemas.RecommendationOut:
    return schemas.RecommendationOut(
        id=str(r.id),
        number=r.number,
        body=r.body,
        responsible=r.responsible,
        due_on=r.due_on,
        status=r.status,
        status_reason=r.status_reason,
        updated_by_name=r.updated_by_name,
        updated_at=r.updated_at,
        overdue=r.due_on is not None and r.due_on < today() and r.status in ("proposed", "in_progress"),
    )


# --- Crisis axes (L3) -----------------------------------------------------------------------------------------------

_DIRECTIVE_TOPICS = {"evacuation": "civil_protection", "public_information": "public_information"}


async def record_directive(
    session: AsyncSession,
    principal: Principal,
    *,
    directive_id: uuid.UUID,
    axis_id: uuid.UUID,
    axis_number: str,
    axis_name: str,
    axis_kind: str,
    gouvernorat_code: int | None,
    number: int,
    kind: str,
    category: str,
    body: str,
    issuer_role: str,
    issued_at: datetime,
    due_at: datetime | None,
    signature: str | None,
    key_id: str | None,
    overridden: list[str],
) -> Document:
    """A signed recommendation or decision of an axis enters the register in force (design §4). The minister's is
    central; the governor's is regional. The governor's decisions it overrides are repealed by it."""
    minister = issuer_role == "minister"
    issued_on = issued_at.date()
    title = f"{axis_name} ({axis_number}) · {number}"
    doc = Document(
        id=uuid.uuid4(),
        number=await next_number(session, issued_on.year),
        reference=f"{axis_number} · {number}",
        kind="decision" if kind == "decision" else "recommendation",
        level="central" if minister else "regional",
        gouvernorat_code=None if minister else gouvernorat_code,
        issuer="وزير الداخلية" if minister else "الوالي",
        signatory=audit.name_of(principal) or "",
        title=title[:300],
        summary=body[:4000],
        body="",
        topics=[t for t in (domain.AXIS_KIND_TOPICS.get(axis_kind), _DIRECTIVE_TOPICS.get(category)) if t],
        issued_on=issued_on,
        effective_from=issued_on,
        effective_to=due_at.date() if due_at is not None and kind == "recommendation" else None,
        status="in_force",
        access="command",
        axis_ids=[axis_id],
        source="axis",
        directive_id=directive_id,
        signature=signature,
        key_id=key_id,
        created_by=audit.actor_of(principal),
        created_by_name=audit.name_of(principal),
        updated_by=audit.actor_of(principal),
        updated_by_name=audit.name_of(principal),
        created_at=issued_at,
        updated_at=issued_at,
        version=1,
    )
    refresh_norm(doc)
    session.add(doc)
    await session.flush()
    await add_revision(session, doc, principal, "recorded_from_axis", None)
    if overridden:
        for earlier in await session.scalars(
            select(Document).where(Document.directive_id.in_([uuid.UUID(i) for i in overridden]))
        ):
            if earlier.status == "in_force":
                await repeal(session, principal, earlier, f"{doc.number}: قرار الوزير يُعتمد عند التعارض", doc)
    return doc


async def axis_documents(session: AsyncSession, principal: Principal, axis_ids: list[uuid.UUID]) -> list[Document]:
    """Documents that concern one of ``axis_ids`` (an axis and its sub-axes) and the caller may read."""
    rows = await session.scalars(
        select(Document)
        .where(Document.axis_ids.overlap(axis_ids), Document.status != "draft")
        .order_by(Document.issued_on.desc(), Document.number.desc())
    )
    return [d for d in rows if readable(principal, d)]


# --- Search ---------------------------------------------------------------------------------------------------------


@dataclass(slots=True)
class Filters:
    q: str = ""
    kinds: list[str] = field(default_factory=list)
    levels: list[str] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    gouvernorat_code: int | None = None
    topics: list[str] = field(default_factory=list)
    issuer: str = ""
    date_from: date | None = None
    date_to: date | None = None
    # issued | effective
    date_field: str = "issued"
    in_force_on: date | None = None
    has_file: bool | None = None
    axis_id: uuid.UUID | None = None
    sort: str = "relevance"
    limit: int = 30
    offset: int = 0


def _scope(principal: Principal, params: dict[str, Any]) -> list[str]:
    """The access and draft rules of ``domain.can_read`` as SQL (the row-level security does the gouvernorats)."""
    params["actor"] = audit.actor_of(principal)
    params["access"] = domain.readable_access(principal)
    params["home"] = principal.gouvernorat_code
    params["writer"] = domain.writes(principal)
    params["national"] = principal.is_national
    where = [
        "(d.access = ANY(CAST(:access AS text[])) OR d.created_by = :actor)",
        "(d.status <> 'draft' OR d.created_by = :actor OR (:writer AND (:national OR d.gouvernorat_code = :home)))",
    ]
    if not principal.is_national:
        where.append("(d.gouvernorat_code IS NULL OR d.gouvernorat_code = :home)")
    return where


def _where(principal: Principal, f: Filters, params: dict[str, Any], *, skip: str = "") -> list[str]:
    where = _scope(principal, params)
    terms = kt.query_terms(f.q) if f.q else []
    if terms:
        params["tsq"] = " & ".join(f"{t}:*" for t in terms)
        where.append("d.search @@ to_tsquery('simple', :tsq)")
    if f.kinds and skip != "kind":
        params["kinds"] = f.kinds
        where.append("d.kind = ANY(CAST(:kinds AS text[]))")
    if f.levels and skip != "level":
        params["levels"] = f.levels
        where.append("d.level = ANY(CAST(:levels AS text[]))")
    if f.statuses and skip != "status":
        params["statuses"] = f.statuses
        where.append("d.status = ANY(CAST(:statuses AS text[]))")
    if f.gouvernorat_code is not None:
        params["g"] = f.gouvernorat_code
        where.append("d.gouvernorat_code = :g")
    if f.topics:
        params["topics"] = f.topics
        where.append("d.topics && CAST(:topics AS text[])")
    if f.issuer:
        params["issuer"] = f"%{f.issuer}%"
        where.append("d.issuer ILIKE :issuer")
    column = "coalesce(d.effective_from, d.issued_on)" if f.date_field == "effective" else "d.issued_on"
    if f.date_from is not None:
        params["date_from"] = f.date_from
        where.append(f"{column} >= :date_from")
    if f.date_to is not None:
        params["date_to"] = f.date_to
        where.append(f"{column} <= :date_to")
    if f.in_force_on is not None:
        params["day"] = f.in_force_on
        where.append(
            "d.status IN ('in_force', 'expired', 'repealed') AND coalesce(d.effective_from, d.issued_on) <= :day "
            "AND (d.effective_to IS NULL OR d.effective_to >= :day) "
            "AND (d.status <> 'repealed' OR d.updated_at::date > :day)"
        )
    if f.has_file is not None:
        where.append("d.file_key IS NOT NULL" if f.has_file else "d.file_key IS NULL")
    if f.axis_id is not None:
        params["axis"] = f.axis_id
        where.append("CAST(:axis AS uuid) = ANY(d.axis_ids)")
    return where


async def search(
    session: AsyncSession, principal: Principal, f: Filters
) -> tuple[list[Document], int, dict[str, Any], list[str]]:
    params: dict[str, Any] = {}
    where = _where(principal, f, params)
    terms = kt.query_terms(f.q) if f.q else []
    clause = " AND ".join(where)
    order = "d.issued_on DESC, d.number DESC"
    if terms and f.sort == "relevance":
        order = "ts_rank(d.search, to_tsquery('simple', :tsq)) DESC, " + order
    elif f.sort == "oldest":
        order = "d.issued_on ASC, d.number ASC"
    params["limit"], params["offset"] = min(f.limit, PAGE_MAX), f.offset
    ids = [
        row[0]
        for row in (
            await session.execute(
                text(
                    f"SELECT d.id FROM register.document d WHERE {clause} ORDER BY {order} LIMIT :limit OFFSET :offset"  # noqa: S608 (constant SQL fragments, values are bound)
                ),
                params,
            )
        ).all()
    ]
    count_sql = f"SELECT count(*) FROM register.document d WHERE {clause}"  # noqa: S608 (constant SQL fragments, values are bound)
    total = int(await session.scalar(text(count_sql), params) or 0)
    facets: dict[str, Any] = {}
    for name, column in (("kind", "d.kind"), ("level", "d.level"), ("status", "d.status")):
        fparams: dict[str, Any] = {}
        fclause = " AND ".join(_where(principal, f, fparams, skip=name))
        rows = await session.execute(
            text(f"SELECT {column}, count(*) FROM register.document d WHERE {fclause} GROUP BY 1 ORDER BY 2 DESC"),  # noqa: S608 (constant SQL fragments, values are bound)
            fparams,
        )
        facets[name] = [{"key": k, "count": int(c)} for k, c in rows.all()]
    found = {d.id: d for d in await session.scalars(select(Document).where(Document.id.in_(ids)))} if ids else {}
    return [found[i] for i in ids if i in found], total, facets, terms


async def open_recommendations(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
    if not ids:
        return {}
    rows = await session.execute(
        select(
            Recommendation.document_id,
            func.count(),
            func.count().filter(Recommendation.status.in_(("proposed", "in_progress"))),
        )
        .where(Recommendation.document_id.in_(ids))
        .group_by(Recommendation.document_id)
    )
    return {r[0]: (int(r[1]), int(r[2])) for r in rows.all()}


def document_out(
    principal: Principal,
    doc: Document,
    names: dict[int, str],
    counts: dict[uuid.UUID, tuple[int, int]],
    terms: list[str] | None = None,
) -> schemas.DocumentOut:
    total, pending = counts.get(doc.id, (0, 0))
    excerpt = kt.excerpt(f"{doc.summary}\n{doc.body}", terms) if terms else None
    return schemas.DocumentOut(
        id=str(doc.id),
        number=doc.number,
        reference=doc.reference,
        kind=doc.kind,
        level=doc.level,
        gouvernorat_code=doc.gouvernorat_code,
        gouvernorat_name=names.get(doc.gouvernorat_code) if doc.gouvernorat_code else None,
        issuer=doc.issuer,
        signatory=doc.signatory,
        title=doc.title,
        summary=doc.summary,
        topics=list(doc.topics),
        issued_on=doc.issued_on,
        effective_from=doc.effective_from,
        effective_to=doc.effective_to,
        status=doc.status,
        repeal_reason=doc.repeal_reason,
        repealed_by=str(doc.repealed_by) if doc.repealed_by else None,
        access=doc.access,
        source=doc.source,
        signed=doc.signature is not None,
        file_name=doc.file_name,
        file_type=doc.file_type,
        file_size=doc.file_size,
        file_sha256=doc.file_sha256,
        recommendations=total,
        recommendations_open=pending,
        updated_by_name=doc.updated_by_name,
        updated_at=doc.updated_at,
        version=doc.version,
        excerpt=excerpt or None,
        can_edit=editable(principal, doc) and doc.status != "repealed",
    )


# --- Worker ---------------------------------------------------------------------------------------------------------


async def tick(session: AsyncSession) -> int:
    """Temporary instructions (and any document with an end date) expire the day after their end date."""
    result = await session.execute(
        update(Document)
        .where(Document.status == "in_force", Document.effective_to.isnot(None), Document.effective_to < today())
        .values(status="expired", updated_at=now())
        .returning(Document.id, Document.number)
    )
    expired = result.all()
    for doc_id, number in expired:
        await audit.record(
            session,
            actor=audit.SYSTEM_ACTOR,
            action="register.document_expired",
            target=str(doc_id),
            details={"number": number},
        )
    return len(expired)
