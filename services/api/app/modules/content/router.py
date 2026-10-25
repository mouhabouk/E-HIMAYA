"""Safety tips (FR-A-062, FR-C-19): edited in three languages, previewed, published; read offline by the app.

The public list carries a revision number (ETag) bumped at every change of the published set, so the
app re-downloads only when something changed.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.content import schemas
from app.modules.content.models import Revision, SafetyTip

router = APIRouter(prefix="/api/v1", tags=["safety-tips"])
Session = Annotated[AsyncSession, Depends(get_session)]
Editor = Annotated[Principal, Depends(require_roles(Role.CONTENT_EDITOR))]
REVISION = "safety_tips"


def tip_out(tip: SafetyTip) -> schemas.TipOut:
    return schemas.TipOut(
        id=tip.id,
        hazard=tip.hazard,
        position=tip.position,
        status=tip.status,
        content=schemas.TipContent.model_validate(tip.content),
        org_kinds=list(tip.org_kinds or []),
        version=tip.version,
        updated_at=tip.updated_at,
        published_at=tip.published_at,
    )


async def _bump(session: AsyncSession) -> None:
    await session.execute(update(Revision).where(Revision.name == REVISION).values(value=Revision.value + 1))


async def _get(session: AsyncSession, tip_id: uuid.UUID) -> SafetyTip:
    tip = await session.get(SafetyTip, tip_id, with_for_update=True)
    if tip is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return tip


@router.get("/safety-tips", response_model=schemas.PublicTips)
async def public_tips(
    session: Session, response: Response, if_none_match: Annotated[str | None, Header()] = None
) -> schemas.PublicTips | Response:
    revision = int(await session.scalar(select(Revision.value).where(Revision.name == REVISION)) or 0)
    etag = f'"tips-{revision}"'
    if if_none_match == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    rows = await session.scalars(
        # Awareness tagged with institution kinds reaches those institutions only (phase P2b).
        select(SafetyTip)
        .where(SafetyTip.status == "published", func.cardinality(SafetyTip.org_kinds) == 0)
        .order_by(SafetyTip.position, SafetyTip.hazard)
    )
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=300"
    return schemas.PublicTips(
        revision=revision,
        items=[
            schemas.PublicTip(
                id=t.id,
                hazard=t.hazard,
                position=t.position,
                content=schemas.TipContent.model_validate(t.content),
                updated_at=t.updated_at,
            )
            for t in rows
        ],
    )


@router.get("/staff/safety-tips", response_model=list[schemas.TipOut])
async def staff_tips(principal: Editor, session: Session) -> list[schemas.TipOut]:
    rows = await session.scalars(select(SafetyTip).order_by(SafetyTip.position, SafetyTip.hazard))
    return [tip_out(t) for t in rows]


@router.post("/staff/safety-tips", response_model=schemas.TipOut, status_code=status.HTTP_201_CREATED)
async def create_tip(principal: Editor, session: Session, body: schemas.TipIn) -> schemas.TipOut:
    tip = SafetyTip(
        hazard=body.hazard,
        position=body.position,
        status="draft",
        content=body.content.model_dump(),
        org_kinds=list(body.org_kinds),
        updated_by=audit.actor_of(principal),
        version=1,
    )
    session.add(tip)
    await session.flush()
    await audit.record(
        session, actor=audit.actor_of(principal), action="safety_tip.create", target=f"safety_tip:{tip.id}"
    )
    await session.refresh(tip)
    out = tip_out(tip)
    await session.commit()
    return out


@router.put("/staff/safety-tips/{tip_id}", response_model=schemas.TipOut)
async def update_tip(principal: Editor, session: Session, tip_id: uuid.UUID, body: schemas.TipIn) -> schemas.TipOut:
    tip = await _get(session, tip_id)
    if body.version is not None and body.version != tip.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
    if tip.status == "published" and not all(getattr(body.content, lang).complete for lang in ("ar", "fr", "en")):
        # A published tip stays complete in the three languages the app shows.
        raise HTTPException(status.HTTP_409_CONFLICT, "translation_missing")
    tip.hazard, tip.position, tip.content = body.hazard, body.position, body.content.model_dump()
    tip.org_kinds = list(body.org_kinds)
    tip.version += 1
    tip.updated_at, tip.updated_by = datetime.now(UTC), audit.actor_of(principal)
    if tip.status == "published":
        await _bump(session)
    await audit.record(
        session, actor=audit.actor_of(principal), action="safety_tip.update", target=f"safety_tip:{tip.id}"
    )
    await session.flush()
    await session.refresh(tip)
    out = tip_out(tip)
    await session.commit()
    return out


@router.delete("/staff/safety-tips/{tip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tip(principal: Editor, session: Session, tip_id: uuid.UUID) -> Response:
    tip = await _get(session, tip_id)
    if tip.status == "published":
        await _bump(session)
    await session.delete(tip)
    await audit.record(
        session, actor=audit.actor_of(principal), action="safety_tip.delete", target=f"safety_tip:{tip_id}"
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/staff/safety-tips/{tip_id}/publish", response_model=schemas.TipOut)
async def publish_tip(principal: Editor, session: Session, tip_id: uuid.UUID) -> schemas.TipOut:
    tip = await _get(session, tip_id)
    content = schemas.TipContent.model_validate(tip.content)
    if not all(getattr(content, lang).complete for lang in ("ar", "fr", "en")):
        raise HTTPException(status.HTTP_409_CONFLICT, "translation_missing")
    tip.status, tip.published_at, tip.updated_at = "published", datetime.now(UTC), datetime.now(UTC)
    tip.version += 1
    await _bump(session)
    await audit.record(
        session, actor=audit.actor_of(principal), action="safety_tip.publish", target=f"safety_tip:{tip.id}"
    )
    await session.flush()
    await session.refresh(tip)
    out = tip_out(tip)
    await session.commit()
    return out


@router.post("/staff/safety-tips/{tip_id}/unpublish", response_model=schemas.TipOut)
async def unpublish_tip(principal: Editor, session: Session, tip_id: uuid.UUID) -> schemas.TipOut:
    tip = await _get(session, tip_id)
    if tip.status != "published":
        raise HTTPException(status.HTTP_409_CONFLICT, "not_published")
    tip.status, tip.updated_at = "draft", datetime.now(UTC)
    tip.version += 1
    await _bump(session)
    await audit.record(
        session, actor=audit.actor_of(principal), action="safety_tip.unpublish", target=f"safety_tip:{tip.id}"
    )
    await session.flush()
    await session.refresh(tip)
    out = tip_out(tip)
    await session.commit()
    return out
