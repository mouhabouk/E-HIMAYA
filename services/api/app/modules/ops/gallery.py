"""The incident's media in one place (phase D, review point 21, docs/phase-d/design-d.md §6).

What the citizens sent with their reports, what the teams sent from the staff app (photos and voice notes, with the
transcript when it was read), the frames the vision service kept, the recordings of the streams, and the streams
themselves (live now or ended), in time order; with the counts the dashboard turns into one summary line
(«12 photos · 2 videos · 3 voice notes · 1 stream live»). Opening it shows personal data and is audited.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, require_roles
from app.core.storage import get_store
from app.modules.audit import service as audit
from app.modules.ops import service as incidents
from app.modules.ops.models import FieldAttachment
from app.modules.reports.models import Media, Report
from app.modules.reports.staff_router import READ_ROLES
from app.modules.reports.uploads import media_url
from app.modules.streams.domain import ACTIVE, Source
from app.modules.streams.models import LiveStream

router = APIRouter(prefix="/api/v1/staff", tags=["incidents"])
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
Session = Annotated[AsyncSession, Depends(get_session)]

MAX_ITEMS = 300

Kind = Literal["photo", "video", "voice", "frame", "recording", "stream"]
Origin = Literal["citizen", "team", "camera", "vision"]


class GalleryItem(BaseModel):
    id: uuid.UUID
    kind: Kind
    origin: Origin
    at: datetime
    url: str | None = None
    content_type: str | None = None
    duration_s: float | None = None
    # Where it comes from: the report's tracking code, the team member, the stream's label.
    label: str | None = None
    report_id: uuid.UUID | None = None
    stream_id: uuid.UUID | None = None
    # A team's voice note read by the transcription service (S2-1).
    transcript: str | None = None
    live: bool = False
    simulated: bool = False


class Gallery(BaseModel):
    counts: dict[str, int]
    live_streams: int
    items: list[GalleryItem]


def _media_kind(m: Media) -> Kind:
    if m.kind == "recording":
        return "recording"
    if (m.analysis or {}).get("source") == "vision":
        return "frame"
    if m.kind in ("video", "audio"):
        return "video" if m.kind == "video" else "voice"
    return "photo"


@router.get("/incidents/{incident_id}/media", response_model=Gallery)
async def incident_media(principal: Reader, session: Session, incident_id: uuid.UUID) -> Gallery:
    incident = await incidents.get_in_scope(session, principal, incident_id)
    store = get_store()
    reports = {
        r.id: r.tracking_code for r in await session.scalars(select(Report).where(Report.incident_id == incident.id))
    }
    items: list[GalleryItem] = []

    if reports:
        for m in await session.scalars(
            select(Media)
            # Call recordings stay on the call's page, behind its own access rules.
            .where(Media.report_id.in_(reports), Media.status == "stored", Media.kind != "call_recording")
            .order_by(Media.created_at)
        ):
            kind = _media_kind(m)
            items.append(
                GalleryItem(
                    id=m.id,
                    kind=kind,
                    origin="vision" if kind == "frame" else "camera" if kind == "recording" else "citizen",
                    at=m.created_at,
                    url=media_url(store, m),
                    content_type=m.verified_type or m.content_type,
                    duration_s=m.duration_s,
                    label=reports.get(m.report_id) if m.report_id else None,
                    report_id=m.report_id,
                    stream_id=m.stream_id,
                )
            )

    for a in await session.scalars(
        select(FieldAttachment)
        .where(
            FieldAttachment.incident_id == incident.id,
            FieldAttachment.kind.in_(("photo", "voice")),
            FieldAttachment.object_key.is_not(None),
        )
        .order_by(FieldAttachment.created_at)
    ):
        assert a.object_key is not None
        items.append(
            GalleryItem(
                id=a.id,
                kind="photo" if a.kind == "photo" else "voice",
                origin="team",
                at=a.device_at or a.created_at,
                url=store.presign_get(a.object_key, expires_s=600, content_type=a.content_type),
                content_type=a.content_type,
                duration_s=a.duration_s,
                label=a.created_by_name,
                transcript=a.transcript,
            )
        )

    conditions = [LiveStream.incident_id == incident.id]
    if reports:
        conditions.append(LiveStream.report_id.in_(reports))
    for st in await session.scalars(
        select(LiveStream).where(or_(*conditions), LiveStream.started_at.is_not(None)).order_by(LiveStream.started_at)
    ):
        assert st.started_at is not None
        items.append(
            GalleryItem(
                id=st.id,
                kind="stream",
                origin="team" if st.source == Source.CREW else "citizen" if st.source == Source.APP else "camera",
                at=st.started_at,
                label=st.label or (reports.get(st.report_id) if st.report_id else None),
                report_id=st.report_id,
                stream_id=st.id,
                live=st.status in ACTIVE,
                simulated=st.source == Source.SIM,
            )
        )

    items.sort(key=lambda i: i.at)
    counts: dict[str, int] = {}
    for i in items:
        counts[i.kind] = counts.get(i.kind, 0) + 1
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="incident.media",
        target=f"incident:{incident.id}",
        details={"items": len(items)},
        gouvernorats=await incidents.all_gouvernorats(session, incident.id),
    )
    await session.commit()
    return Gallery(counts=counts, live_streams=sum(1 for i in items if i.live), items=items[-MAX_ITEMS:])
