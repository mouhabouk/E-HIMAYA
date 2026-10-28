"""Register of plans, decisions and instructions, central and regional (phase L3b, docs/phase-l/design-l3b.md).

The central and regional rooms and committees record documents in their scope (plans, decisions, memos, circulars,
standing and temporary instructions, recommendations, minutes) with their official reference, dates, topics, file
and key recommendations; every staff member who works with them searches them (words, type, level, gouvernorat,
issuer, topic, period, "in force on"). The signed recommendations and decisions of the crisis axes are recorded
automatically. The governor sees the central documents and those of their gouvernorat; the minister sees all.
"""

import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.core.storage import get_store
from app.modules.audit import service as audit
from app.modules.crisis.models import Axis
from app.modules.register import domain, schemas, service
from app.modules.register.models import Document, Link, Recommendation, Revision

router = APIRouter(prefix="/api/v1/staff/register", tags=["staff", "register"])
Session = Annotated[AsyncSession, Depends(get_session)]
_Staff = Annotated[
    Principal,
    Depends(
        require_roles(
            Role.OPERATOR,
            Role.OPS_MANAGER,
            Role.FIELD_COMMANDER,
            Role.LOCAL_COMMITTEE,
            Role.CENTRAL_COMMITTEE,
            Role.CONTENT_EDITOR,
            Role.SYSADMIN,
            Role.GOVERNOR,
            Role.MINISTER,
        )
    ),
]


async def reader(principal: _Staff) -> Principal:
    if not domain.reads(principal):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient_role")
    return principal


Reader = Annotated[Principal, Depends(reader)]


async def _detail(session: AsyncSession, principal: Principal, doc: Document) -> schemas.DocumentDetail:
    names = await service.gouvernorat_names(session)
    counts = await service.open_recommendations(session, [doc.id])
    axes = (
        list(await session.scalars(select(Axis).where(Axis.id.in_(doc.axis_ids)).order_by(Axis.opened_at)))
        if doc.axis_ids
        else []
    )
    links: list[schemas.LinkOut] = []
    rows = await session.execute(
        select(Link, Document)
        .join(Document, or_(Document.id == Link.to_id, Document.id == Link.from_id))
        .where(or_(Link.from_id == doc.id, Link.to_id == doc.id), Document.id != doc.id)
    )
    for link, other in rows.all():
        if not service.readable(principal, other):
            continue
        links.append(
            schemas.LinkOut(
                id=str(other.id),
                number=other.number,
                title=other.title,
                kind=other.kind,
                status=other.status,
                relation=link.relation,
                direction="out" if link.from_id == doc.id else "in",
            )
        )
    recs = list(
        await session.scalars(
            select(Recommendation).where(Recommendation.document_id == doc.id).order_by(Recommendation.number)
        )
    )
    return schemas.DocumentDetail(
        document=service.document_out(principal, doc, names, counts),
        body=doc.body,
        axes=[schemas.AxisRef(id=str(a.id), number=a.number, name=a.name, status=a.status) for a in axes],
        links=links,
        recommendations=[service.recommendation_out(r) for r in recs],
        created_by_name=doc.created_by_name,
        created_at=doc.created_at,
    )


def _csv(raw: str, allowed: tuple[str, ...] | None, name: str) -> list[str]:
    """A comma-separated filter (the dashboard's query style); unknown values are refused."""
    values = list(dict.fromkeys(v.strip() for v in raw.split(",") if v.strip()))
    if allowed is not None and any(v not in allowed for v in values):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"invalid_{name}")
    return values


@router.get("/documents", response_model=schemas.SearchOut)
async def search(
    principal: Reader,
    session: Session,
    q: Annotated[str, Query(max_length=300)] = "",
    kind: Annotated[str, Query(max_length=300, description="Comma-separated kinds")] = "",
    level: Annotated[str, Query(max_length=40, description="Comma-separated levels")] = "",
    doc_status: Annotated[str, Query(alias="status", max_length=80, description="Comma-separated statuses")] = "",
    gouvernorat: Annotated[int | None, Query(ge=11, le=83)] = None,
    topic: Annotated[str, Query(max_length=400, description="Comma-separated topics")] = "",
    issuer: Annotated[str, Query(max_length=200)] = "",
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    date_field: Annotated[Literal["issued", "effective"], Query()] = "issued",
    in_force_on: Annotated[date | None, Query()] = None,
    has_file: Annotated[bool | None, Query()] = None,
    axis: Annotated[uuid.UUID | None, Query()] = None,
    sort: Annotated[Literal["relevance", "newest", "oldest"], Query()] = "relevance",
    limit: Annotated[int, Query(ge=1, le=service.PAGE_MAX)] = 30,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> schemas.SearchOut:
    """Advanced search. Words match whole words or their starts, in Arabic and French, without diacritics or hamza
    variants. Without a status filter every status is listed (drafts only to those who may write them)."""
    filters = service.Filters(
        q=q.strip(),
        kinds=_csv(kind, domain.KINDS, "kind"),
        levels=_csv(level, domain.LEVELS, "level"),
        statuses=_csv(doc_status, domain.STATUSES, "status"),
        gouvernorat_code=gouvernorat,
        topics=[t for t in _csv(topic, None, "topic") if 2 <= len(t) <= 60][:12],
        issuer=issuer.strip(),
        date_from=date_from,
        date_to=date_to,
        date_field=date_field,
        in_force_on=in_force_on,
        has_file=has_file,
        axis_id=axis,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    docs, total, facets, terms = await service.search(session, principal, filters)
    names = await service.gouvernorat_names(session)
    counts = await service.open_recommendations(session, [d.id for d in docs])
    return schemas.SearchOut(
        items=[service.document_out(principal, d, names, counts, terms) for d in docs],
        total=total,
        facets={k: [schemas.Facet(**f) for f in v] for k, v in facets.items()},
        can_create=domain.writes(principal),
        can_create_central=domain.writes(principal) and principal.is_national,
    )


@router.post("/documents", response_model=schemas.DocumentDetail, status_code=status.HTTP_201_CREATED)
async def create(principal: Reader, session: Session, body: schemas.DocumentIn) -> schemas.DocumentDetail:
    doc = await service.create(session, principal, body)
    out = await _detail(session, principal, doc)
    await session.commit()
    return out


@router.get("/documents/{document_id}", response_model=schemas.DocumentDetail)
async def get_document(principal: Reader, session: Session, document_id: uuid.UUID) -> schemas.DocumentDetail:
    return await _detail(session, principal, await service.visible(session, principal, document_id))


@router.patch("/documents/{document_id}", response_model=schemas.DocumentDetail)
async def update(
    principal: Reader, session: Session, document_id: uuid.UUID, body: schemas.DocumentPatch
) -> schemas.DocumentDetail:
    doc = await service.visible(session, principal, document_id, lock=True)
    await service.update_document(session, principal, doc, body)
    out = await _detail(session, principal, doc)
    await session.commit()
    return out


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft(principal: Reader, session: Session, document_id: uuid.UUID) -> Response:
    doc = await service.visible(session, principal, document_id, lock=True)
    await service.delete_draft(session, principal, doc)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/documents/{document_id}/repeal", response_model=schemas.DocumentDetail)
async def repeal(
    principal: Reader, session: Session, document_id: uuid.UUID, body: schemas.RepealIn
) -> schemas.DocumentDetail:
    doc = await service.visible(session, principal, document_id, lock=True)
    if not domain.can_write(principal, doc.level, doc.gouvernorat_code) or doc.source != "manual":
        raise service.forbidden("out_of_scope")
    by = await service.visible(session, principal, body.by_document_id) if body.by_document_id else None
    await service.repeal(session, principal, doc, body.reason, by)
    out = await _detail(session, principal, doc)
    await session.commit()
    return out


@router.post("/documents/{document_id}/links", response_model=schemas.DocumentDetail)
async def add_link(
    principal: Reader, session: Session, document_id: uuid.UUID, body: schemas.LinkIn
) -> schemas.DocumentDetail:
    doc = await service.visible(session, principal, document_id, lock=True)
    other = await service.visible(session, principal, body.to_id, lock=True)
    await service.link(session, principal, doc, other, body.relation)
    out = await _detail(session, principal, doc)
    await session.commit()
    return out


@router.delete("/documents/{document_id}/links/{other_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_link(principal: Reader, session: Session, document_id: uuid.UUID, other_id: uuid.UUID) -> Response:
    doc = await service.visible(session, principal, document_id)
    await service.unlink(session, principal, doc, other_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _read_body(request: Request) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > domain.MAX_FILE_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "file_too_large")
        chunks.append(chunk)
    return b"".join(chunks)


@router.put("/documents/{document_id}/file", response_model=schemas.DocumentDetail)
async def put_file(
    principal: Reader,
    session: Session,
    document_id: uuid.UUID,
    request: Request,
    file_name: Annotated[str, Query(min_length=1, max_length=200)],
) -> schemas.DocumentDetail:
    """The file (PDF, Word, PNG or JPEG, up to 20 MB) is the request body; it replaces the previous one."""
    doc = await service.visible(session, principal, document_id, lock=True)
    data = await _read_body(request)
    await service.attach_file(session, principal, doc, file_name, data, request.headers.get("content-type"))
    out = await _detail(session, principal, doc)
    await session.commit()
    return out


@router.get("/documents/{document_id}/file", response_model=schemas.FileOut)
async def get_file(principal: Reader, session: Session, document_id: uuid.UUID) -> schemas.FileOut:
    doc = await service.visible(session, principal, document_id)
    if not doc.file_key or not doc.file_type:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file_not_found")
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="register.file_read",
        target=str(doc.id),
        details={"number": doc.number},
        gouvernorats=[doc.gouvernorat_code] if doc.gouvernorat_code else None,
    )
    await session.commit()
    name = (doc.file_name or doc.number).replace('"', "")
    return schemas.FileOut(
        url=get_store().presign_get(doc.file_key, content_type=doc.file_type, disposition=f'inline; filename="{name}"')
    )


@router.post("/documents/{document_id}/recommendations", response_model=schemas.DocumentDetail)
async def add_recommendation(
    principal: Reader, session: Session, document_id: uuid.UUID, body: schemas.RecommendationIn
) -> schemas.DocumentDetail:
    doc = await service.visible(session, principal, document_id, lock=True)
    await service.add_recommendation(session, principal, doc, body)
    out = await _detail(session, principal, doc)
    await session.commit()
    return out


@router.post("/recommendations/{recommendation_id}/status", response_model=schemas.RecommendationOut)
async def recommendation_status(
    principal: Reader, session: Session, recommendation_id: uuid.UUID, body: schemas.RecommendationStatusIn
) -> schemas.RecommendationOut:
    rec = await session.get(Recommendation, recommendation_id, with_for_update=True)
    if rec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "recommendation_not_found")
    doc = await service.visible(session, principal, rec.document_id)
    await service.set_recommendation_status(session, principal, doc, rec, body.status, body.reason)
    out = service.recommendation_out(rec)
    await session.commit()
    return out


@router.get("/documents/{document_id}/revisions", response_model=list[schemas.RevisionOut])
async def revisions(principal: Reader, session: Session, document_id: uuid.UUID) -> list[schemas.RevisionOut]:
    doc = await service.visible(session, principal, document_id)
    rows = await session.scalars(
        select(Revision)
        .where(Revision.document_id == doc.id)
        .order_by(Revision.version.desc(), Revision.created_at.desc())
    )
    return [
        schemas.RevisionOut(
            version=r.version,
            change=r.change,
            reason=r.reason,
            created_by_name=r.created_by_name,
            created_at=r.created_at,
            snapshot=r.snapshot,
        )
        for r in rows
    ]
