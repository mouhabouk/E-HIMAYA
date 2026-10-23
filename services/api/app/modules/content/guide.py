"""Emergency hub: topics and items (phase B1, docs/phase-b/design.md §2bis).

Content editors add, change, hide, show and reorder topics and items; nothing is deleted (hiding keeps the history).
Every change has a reason, is audited and bumps the ``emergency_guide`` revision, the ``ETag`` of the public guide the
app keeps offline. Changing an item's text withdraws its medical validation: the app shows it again under the amber
"[SIM] content awaiting medical validation" banner until it is validated again.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.content.models import GuideItem, GuideTopic, Revision
from app.modules.layers.domain import PALETTE

router = APIRouter(prefix="/api/v1", tags=["emergency-guide"])
Session = Annotated[AsyncSession, Depends(get_session)]
Editor = Annotated[Principal, Depends(require_roles(Role.CONTENT_EDITOR))]
REVISION = "emergency_guide"

# Icons the dashboard and the app both draw for the topics.
GUIDE_ICONS = ("fire", "bone", "first_aid", "lungs", "burn", "drop", "heart", "water", "electric", "poison", "pin")

Line = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=500)]


class Titles(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ar: Title
    fr: Title
    en: Title


class ItemText(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    call: list[Line] = Field(default_factory=list, max_length=5)
    steps: list[Line] = Field(min_length=1, max_length=15)
    dont: list[Line] = Field(default_factory=list, max_length=10)


class ItemContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ar: ItemText
    fr: ItemText
    en: ItemText


def _icon(value: str | None) -> str | None:
    if value is not None and value not in GUIDE_ICONS:
        raise ValueError("unknown icon")
    return value


def _colour(value: str | None) -> str | None:
    if value is not None and value.upper() not in PALETTE:
        raise ValueError("colour outside the palette")
    return value.upper() if value else value


class TopicIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")
    title: Titles
    icon: str
    colour: str
    reason: Reason

    _v_icon = field_validator("icon")(_icon)
    _v_colour = field_validator("colour")(_colour)


class TopicPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    reason: Reason
    title: Titles | None = None
    icon: str | None = None
    colour: str | None = None
    hidden: bool | None = None

    _v_icon = field_validator("icon")(_icon)
    _v_colour = field_validator("colour")(_colour)


class ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: ItemContent
    call_198: bool = False
    reason: Reason


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    reason: Reason
    content: ItemContent | None = None
    call_198: bool | None = None
    hidden: bool | None = None
    topic_id: uuid.UUID | None = None


class VersionReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    reason: Reason


class MoveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direction: Literal["up", "down"]


class ItemOut(BaseModel):
    id: uuid.UUID
    topic_id: uuid.UUID
    position: int
    content: ItemContent
    call_198: bool
    hidden: bool
    validated: bool
    validated_by: str | None
    validated_at: datetime | None
    version: int
    updated_at: datetime


class TopicOut(BaseModel):
    id: uuid.UUID
    key: str
    title: Titles
    icon: str
    colour: str
    position: int
    hidden: bool
    version: int
    updated_at: datetime
    items: list[ItemOut]


class GuideOut(BaseModel):
    revision: int
    topics: list[TopicOut]
    icons: list[str]
    palette: list[str]


class PublicItem(BaseModel):
    id: uuid.UUID
    content: ItemContent
    call_198: bool
    # False: the app shows the amber [SIM] "content awaiting medical validation" banner.
    validated: bool


class PublicTopic(BaseModel):
    id: uuid.UUID
    key: str
    title: Titles
    icon: str
    colour: str
    items: list[PublicItem]


class PublicGuide(BaseModel):
    revision: int
    topics: list[PublicTopic]


def _item_out(item: GuideItem) -> ItemOut:
    return ItemOut(
        id=item.id,
        topic_id=item.topic_id,
        position=item.position,
        content=ItemContent.model_validate(item.content),
        call_198=item.call_198,
        hidden=item.hidden,
        validated=item.validated_at is not None,
        validated_by=item.validated_by,
        validated_at=item.validated_at,
        version=item.version,
        updated_at=item.updated_at,
    )


async def _revision(session: AsyncSession) -> int:
    return int(await session.scalar(select(Revision.value).where(Revision.name == REVISION)) or 0)


async def _bump(session: AsyncSession) -> None:
    await session.execute(update(Revision).where(Revision.name == REVISION).values(value=Revision.value + 1))


async def _load(session: AsyncSession) -> tuple[list[GuideTopic], list[GuideItem]]:
    topics = list(await session.scalars(select(GuideTopic).order_by(GuideTopic.position, GuideTopic.key)))
    items = list(await session.scalars(select(GuideItem).order_by(GuideItem.position, GuideItem.id)))
    return topics, items


@router.get("/emergency-guide", response_model=PublicGuide)
async def public_guide(
    session: Session, response: Response, if_none_match: Annotated[str | None, Header()] = None
) -> PublicGuide | Response:
    """The visible topics and their visible items, in their order; kept offline by the app."""
    revision = await _revision(session)
    etag = f'"guide-{revision}"'
    if if_none_match == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    topics, items = await _load(session)
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=300"
    return PublicGuide(
        revision=revision,
        topics=[
            PublicTopic(
                id=t.id,
                key=t.key,
                title=Titles.model_validate(t.title),
                icon=t.icon,
                colour=t.colour,
                items=[
                    PublicItem(
                        id=i.id,
                        content=ItemContent.model_validate(i.content),
                        call_198=i.call_198,
                        validated=i.validated_at is not None,
                    )
                    for i in items
                    if i.topic_id == t.id and not i.hidden
                ],
            )
            for t in topics
            if not t.hidden
        ],
    )


async def _staff_guide(session: AsyncSession) -> GuideOut:
    topics, items = await _load(session)
    return GuideOut(
        revision=await _revision(session),
        topics=[
            TopicOut(
                id=t.id,
                key=t.key,
                title=Titles.model_validate(t.title),
                icon=t.icon,
                colour=t.colour,
                position=t.position,
                hidden=t.hidden,
                version=t.version,
                updated_at=t.updated_at,
                items=[_item_out(i) for i in items if i.topic_id == t.id],
            )
            for t in topics
        ],
        icons=list(GUIDE_ICONS),
        palette=list(PALETTE),
    )


@router.get("/staff/emergency-guide", response_model=GuideOut)
async def staff_guide(principal: Editor, session: Session) -> GuideOut:
    return await _staff_guide(session)


async def _topic(session: AsyncSession, topic_id: uuid.UUID) -> GuideTopic:
    topic = await session.get(GuideTopic, topic_id, with_for_update=True)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return topic


async def _item(session: AsyncSession, item_id: uuid.UUID) -> GuideItem:
    item = await session.get(GuideItem, item_id, with_for_update=True)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return item


async def _done(session: AsyncSession, principal: Principal, action: str, target: str, reason: str | None) -> GuideOut:
    await _bump(session)
    await audit.record(session, actor=audit.actor_of(principal), action=action, target=target, reason=reason)
    await session.flush()
    session.expire_all()
    out = await _staff_guide(session)
    await session.commit()
    return out


@router.post("/staff/emergency-guide/topics", response_model=GuideOut, status_code=status.HTTP_201_CREATED)
async def create_topic(principal: Editor, session: Session, body: TopicIn) -> GuideOut:
    if await session.scalar(select(GuideTopic.id).where(GuideTopic.key == body.key)):
        raise HTTPException(status.HTTP_409_CONFLICT, "key_taken")
    last = await session.scalar(select(GuideTopic.position).order_by(GuideTopic.position.desc()).limit(1))
    topic = GuideTopic(
        key=body.key,
        title=body.title.model_dump(),
        icon=body.icon,
        colour=body.colour,
        position=(last or 0) + 10,
        updated_by=audit.actor_of(principal),
    )
    session.add(topic)
    await session.flush()
    return await _done(session, principal, "guide.topic_create", f"guide_topic:{topic.key}", body.reason)


@router.patch("/staff/emergency-guide/topics/{topic_id}", response_model=GuideOut)
async def update_topic(principal: Editor, session: Session, topic_id: uuid.UUID, body: TopicPatch) -> GuideOut:
    topic = await _topic(session, topic_id)
    if body.version != topic.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
    for field, value in body.model_dump(exclude_unset=True, exclude={"version", "reason"}).items():
        if value is not None:
            setattr(topic, field, value)
    topic.version += 1
    topic.updated_by, topic.updated_at = audit.actor_of(principal), datetime.now(UTC)
    return await _done(session, principal, "guide.topic_update", f"guide_topic:{topic.key}", body.reason)


@router.post("/staff/emergency-guide/topics/{topic_id}/items", response_model=GuideOut, status_code=201)
async def create_item(principal: Editor, session: Session, topic_id: uuid.UUID, body: ItemIn) -> GuideOut:
    topic = await _topic(session, topic_id)
    last = await session.scalar(
        select(GuideItem.position).where(GuideItem.topic_id == topic.id).order_by(GuideItem.position.desc()).limit(1)
    )
    item = GuideItem(
        topic_id=topic.id,
        position=(last or 0) + 10,
        content=body.content.model_dump(),
        call_198=body.call_198,
        updated_by=audit.actor_of(principal),
    )
    session.add(item)
    await session.flush()
    return await _done(session, principal, "guide.item_create", f"guide_item:{item.id}", body.reason)


@router.patch("/staff/emergency-guide/items/{item_id}", response_model=GuideOut)
async def update_item(principal: Editor, session: Session, item_id: uuid.UUID, body: ItemPatch) -> GuideOut:
    item = await _item(session, item_id)
    if body.version != item.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
    if body.content is not None and body.content.model_dump() != item.content:
        item.content = body.content.model_dump()
        # New text: the medical validation applied to the old one.
        item.validated_by = item.validated_at = None
    if body.call_198 is not None:
        item.call_198 = body.call_198
    if body.hidden is not None:
        item.hidden = body.hidden
    if body.topic_id is not None and body.topic_id != item.topic_id:
        target = await _topic(session, body.topic_id)
        last = await session.scalar(
            select(GuideItem.position)
            .where(GuideItem.topic_id == target.id)
            .order_by(GuideItem.position.desc())
            .limit(1)
        )
        item.topic_id, item.position = target.id, (last or 0) + 10
    item.version += 1
    item.updated_by, item.updated_at = audit.actor_of(principal), datetime.now(UTC)
    return await _done(session, principal, "guide.item_update", f"guide_item:{item.id}", body.reason)


@router.post("/staff/emergency-guide/items/{item_id}/validate", response_model=GuideOut)
async def validate_item(principal: Editor, session: Session, item_id: uuid.UUID, body: VersionReason) -> GuideOut:
    """The content editor records that the Office's medical staff validated this text (named in the reason)."""
    item = await _item(session, item_id)
    if body.version != item.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
    item.validated_by = audit.name_of(principal) or audit.actor_of(principal)
    item.validated_at = datetime.now(UTC)
    item.version += 1
    return await _done(session, principal, "guide.item_validate", f"guide_item:{item.id}", body.reason)


def _swap(rows: list[GuideTopic] | list[GuideItem], target: uuid.UUID, up: bool) -> bool:
    ordered: list[GuideTopic | GuideItem] = list(rows)
    index = next(i for i, r in enumerate(ordered) if r.id == target)
    other = index - 1 if up else index + 1
    if not 0 <= other < len(ordered):
        return False
    a, b = ordered[index], ordered[other]
    # Positions may be equal (hand-made data): renumber the whole list first.
    for n, row in enumerate(ordered):
        row.position = n * 10
    a.position, b.position = b.position, a.position
    return True


@router.post("/staff/emergency-guide/topics/{topic_id}/move", response_model=GuideOut)
async def move_topic(principal: Editor, session: Session, topic_id: uuid.UUID, body: MoveIn) -> GuideOut:
    topic = await _topic(session, topic_id)
    rows = list(
        await session.scalars(select(GuideTopic).order_by(GuideTopic.position, GuideTopic.key).with_for_update())
    )
    if not _swap(rows, topic.id, body.direction == "up"):
        raise HTTPException(status.HTTP_409_CONFLICT, "cannot_move")
    return await _done(session, principal, "guide.topic_move", f"guide_topic:{topic.key}", None)


@router.post("/staff/emergency-guide/items/{item_id}/move", response_model=GuideOut)
async def move_item(principal: Editor, session: Session, item_id: uuid.UUID, body: MoveIn) -> GuideOut:
    item = await _item(session, item_id)
    rows = list(
        await session.scalars(
            select(GuideItem)
            .where(GuideItem.topic_id == item.topic_id)
            .order_by(GuideItem.position, GuideItem.id)
            .with_for_update()
        )
    )
    if not _swap(rows, item.id, body.direction == "up"):
        raise HTTPException(status.HTTP_409_CONFLICT, "cannot_move")
    return await _done(session, principal, "guide.item_move", f"guide_item:{item.id}", None)
