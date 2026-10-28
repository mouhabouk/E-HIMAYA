"""One item of the events library with its linked media (``GET /api/v1/staff/library/items/{kind}/{id}``).

The item is rebuilt from its source (never from the index), checked against the caller's scope like a search hit
(404 outside it), and its media are handed out as short-lived presigned URLs. Every opening is audited.
"""

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.core.storage import get_store
from app.modules.audit import service as audit
from app.modules.decision.models import ProcedureChunk
from app.modules.knowledge import documents
from app.modules.knowledge import schemas as s
from app.modules.knowledge.domain import Kind, can_see
from app.modules.knowledge.models import MemoryEntry
from app.modules.knowledge.search import allowed_kinds
from app.modules.ops.models import Incident, TimelineEvent
from app.modules.reports.models import Media, Report
from app.modules.reports.uploads import media_url
from app.modules.telephony.models import Call

MAX_MEDIA = 50


def _link(media: Media) -> s.MediaLink:
    return s.MediaLink(
        id=media.id,
        kind=media.kind,
        content_type=media.verified_type or media.content_type,
        duration_s=media.duration_s,
        url=media_url(get_store(), media),
    )


async def _media(session: AsyncSession, ids: list[uuid.UUID]) -> list[s.MediaLink]:
    if not ids:
        return []
    rows = await session.scalars(
        select(Media).where(Media.id.in_(ids), Media.status == "stored").order_by(Media.created_at).limit(MAX_MEDIA)
    )
    return [_link(m) for m in rows]


async def _report_media_ids(session: AsyncSession, report_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    if not report_ids:
        return []
    return list(await session.scalars(select(Media.id).where(Media.report_id.in_(report_ids))))


async def _details(session: AsyncSession, doc: documents.Doc) -> tuple[dict[str, Any], list[s.MediaLink]]:
    if doc.kind is Kind.MEMORY:
        entry = await session.get(MemoryEntry, uuid.UUID(doc.ref_id))
        assert entry is not None
        snapshot = await documents.published_snapshot(session, entry) or {}
        media_ids = [uuid.UUID(src["media_id"]) for src in snapshot.get("sources", []) if src.get("media_id")]
        return {"entry": snapshot, "published_version": entry.published_version}, await _media(session, media_ids)
    if doc.kind is Kind.REPORT:
        report = await session.get(Report, uuid.UUID(doc.ref_id))
        assert report is not None
        fields: dict[str, Any] = {
            "tracking_code": report.tracking_code,
            "status": report.status,
            "source": report.source,
            "priority_score": report.priority_score,
            "lang_original": report.lang_original,
        }
        return fields, await _media(session, await _report_media_ids(session, [report.id]))
    if doc.kind is Kind.TRANSCRIPT:
        media = await session.get(Media, uuid.UUID(doc.ref_id))
        assert media is not None
        report, call, _ = await documents.media_context(session, media)
        fields = {
            "media_kind": media.kind,
            "language": (media.analysis or {}).get("language"),
            "report_id": str(report.id) if report else None,
            "call_id": str(call.id) if call else None,
        }
        return fields, [_link(media)]
    if doc.kind is Kind.INCIDENT:
        incident = await session.get(Incident, uuid.UUID(doc.ref_id))
        assert incident is not None
        timeline = await session.scalars(
            select(TimelineEvent)
            .where(TimelineEvent.incident_id == incident.id, TimelineEvent.kind != "assistant")
            .order_by(TimelineEvent.at, TimelineEvent.id)
        )
        report_ids = list(await session.scalars(select(Report.id).where(Report.incident_id == incident.id)))
        calls = list(
            await session.scalars(
                select(Call.recording_media_id).where(
                    Call.incident_id == incident.id, Call.recording_media_id.is_not(None)
                )
            )
        )
        fields = {
            "status": incident.status,
            "severity": incident.severity,
            "classification": incident.classification,
            "op_level": incident.op_level.value,
            "closed_at": incident.closed_at.isoformat() if incident.closed_at else None,
            "evaluation": incident.evaluation,
            "report_count": len(report_ids),
            "timeline": [{"at": e.at.isoformat(), "kind": e.kind} for e in timeline],
        }
        media_ids = await _report_media_ids(session, report_ids) + [m for m in calls if m is not None]
        return fields, await _media(session, media_ids)
    if doc.kind is Kind.REPORT_DOC:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT kind, period_from, period_to, format, filters, media_id, sha256, created_at "
                        "FROM analytics.report WHERE id = :id"
                    ),
                    {"id": uuid.UUID(doc.ref_id)},
                )
            )
            .mappings()
            .one()
        )
        fields = {
            "report_kind": row["kind"],
            "period_from": row["period_from"].isoformat() if row["period_from"] else None,
            "period_to": row["period_to"].isoformat() if row["period_to"] else None,
            "format": row["format"],
            "filters": row["filters"],
            "sha256": row["sha256"],
        }
        return fields, await _media(session, [row["media_id"]] if row["media_id"] else [])
    if doc.kind is Kind.REGISTER:
        # The register page shows the document; the library links to it.
        return {"document_id": doc.ref_id, "register_kind": doc.categories[0] if doc.categories else None}, []
    chunk = await session.get(ProcedureChunk, doc.ref_id)
    assert chunk is not None
    return {"procedure_id": chunk.procedure_id, "lang": chunk.lang, "references": chunk.sources}, []


async def get_item(session: AsyncSession, principal: Principal, kind: Kind, ref_id: str) -> s.ItemOut:
    doc = await documents.build(session, kind, ref_id)
    if doc is None or kind not in allowed_kinds(principal) or not can_see(principal, doc.access, doc.gouvernorats):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    fields, media = await _details(session, doc)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="library.item_view",
        target=f"{kind.value}:{doc.ref_id}",
        details={"media": [str(m.id) for m in media]},
    )
    return s.ItemOut(
        kind=kind.value,
        id=doc.ref_id,
        title=doc.title,
        date=doc.date,
        gouvernorat=doc.gouvernorats[0] if doc.gouvernorats else None,
        gouvernorats=sorted(doc.gouvernorats),
        category=doc.categories[0] if doc.categories else None,
        incident_id=doc.incident_id,
        body=doc.body,
        fields=fields,
        media=media,
    )
