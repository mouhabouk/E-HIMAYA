"""Evidence anchors (phase 10 §4.3): the list for the security team, and the proof of one media file."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, authorize, require
from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.evidence import schemas, service
from app.modules.evidence.models import Anchor
from app.modules.reports import service as reports
from app.modules.reports.models import Media, Report
from app.modules.reports.staff_router import READ_ROLES
from app.modules.streams.models import LiveStream

router = APIRouter(prefix="/api/v1/staff", tags=["evidence"])

Session = Annotated[AsyncSession, Depends(get_session)]
Auditor = Annotated[Principal, Depends(require_roles(Role.SECURITY_ADMIN, Role.SYSADMIN))]
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]


@router.get("/evidence/anchors", response_model=schemas.AnchorPage)
async def list_anchors(
    principal: Auditor,
    session: Session,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    before_seq: int | None = None,
) -> schemas.AnchorPage:
    query = select(Anchor).order_by(Anchor.seq.desc()).limit(limit)
    if before_seq is not None:
        query = query.where(Anchor.seq < before_seq)
    rows = (await session.scalars(query)).all()
    items = [schemas.AnchorOut.model_validate(service.anchor_out(a)) for a in rows]
    return schemas.AnchorPage(items=items, next_before_seq=rows[-1].seq if len(rows) == limit else None)


async def _report_of(session: AsyncSession, media: Media) -> Report | None:
    report_id = media.report_id
    if report_id is None and media.stream_id is not None:
        report_id = await session.scalar(select(LiveStream.report_id).where(LiveStream.id == media.stream_id))
    return await session.get(Report, report_id) if report_id is not None else None


@router.get("/media/{media_id}/proof", response_model=schemas.ProofOut)
async def media_proof(principal: Reader, session: Session, media_id: uuid.UUID) -> schemas.ProofOut:
    """Only for staff who may read the report the media belongs to (404 otherwise, like the report itself)."""
    media = await session.get(Media, media_id)
    report = await _report_of(session, media) if media is not None else None
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    require(await authorize(session, principal, Action.REPORT_READ, await reports.report_ctx(session, report)))
    proof = await service.proof_of(session, media_id)
    if proof is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_anchored_yet")
    return schemas.ProofOut.model_validate(proof)
