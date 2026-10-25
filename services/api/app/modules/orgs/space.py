"""Institution space in the app, phase P2b (docs/phase-p2/design-institutions-app.md §5).

* Office messages addressed to the institution, and the read acknowledgement some of them ask for.
* Awareness: safety tips tagged with the institution's kind.
* Drills held and public events declared.
* Maintenance log of an equipment, with an optional photo kept as a ``maintenance_photo`` document.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy import and_, any_, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.audit import service as audit
from app.modules.content.models import SafetyTip
from app.modules.notify.models import OrgAck
from app.modules.orgs import schemas, service
from app.modules.orgs.domain import OrgRole
from app.modules.orgs.models import Activity, Document, DocumentVersion, Equipment, Maintenance, Organization
from app.modules.orgs.service import CurrentUser, PortalUser

router = APIRouter(prefix="/api/v1", tags=["institutions"])
Session = Annotated[AsyncSession, Depends(get_session)]
OrgId = Annotated[uuid.UUID, Path()]
MESSAGES_LIMIT = 50
ACTIVITIES_LIMIT = 100
MAINTENANCE_LIMIT = 50


async def _changed(session: AsyncSession, org: Organization, user: PortalUser, action: str, **details: Any) -> None:
    await audit.record(session, actor=user.actor, action=action, target=f"org:{org.id}", details=details or None)
    await service.touch(session, org)
    await service.org_event(session, org.id)


# ---------------------------------------------------------------- Office messages


async def org_messages(
    session: AsyncSession, org_id: uuid.UUID, message_id: uuid.UUID | None = None
) -> list[schemas.OrgMessage]:
    where = " AND m.id = :mid" if message_id else ""
    rows = (
        await session.execute(
            text(
                "SELECT m.id, m.topic, m.title, m.body, m.published_at, m.ack_required, a.acked_at, a.acked_by_name "
                f"{service.ORG_MESSAGES}{where} ORDER BY m.published_at DESC, m.id DESC LIMIT :limit"
            ),
            {"oid": org_id, "mid": message_id, "limit": MESSAGES_LIMIT},
        )
    ).all()
    return [
        schemas.OrgMessage(
            id=r.id,
            topic=r.topic,
            title=r.title,
            body=r.body,
            published_at=r.published_at,
            ack_required=r.ack_required,
            acked_at=r.acked_at,
            acked_by=r.acked_by_name,
        )
        for r in rows
    ]


@router.get("/orgs/{org_id}/messages", response_model=list[schemas.OrgMessage])
async def list_messages(org_id: OrgId, user: CurrentUser, session: Session) -> list[schemas.OrgMessage]:
    await service.membership(session, user, org_id)
    items = await org_messages(session, org_id)
    await session.commit()
    return items


@router.post("/orgs/{org_id}/messages/{message_id}/ack", response_model=schemas.OrgMessage)
async def ack_message(org_id: OrgId, message_id: uuid.UUID, user: CurrentUser, session: Session) -> schemas.OrgMessage:
    """The institution confirms it has read the message (editor or admin). Repeating it changes nothing."""
    org, _ = await service.membership(session, user, org_id, OrgRole.EDITOR)
    found = await org_messages(session, org_id, message_id)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "message_not_found")
    if not found[0].ack_required:
        raise HTTPException(status.HTTP_409_CONFLICT, "ack_not_required")
    if found[0].acked_at is None:
        await session.execute(
            insert(OrgAck)
            .values(message_id=message_id, org_id=org_id, acked_by=user.user_id, acked_by_name=user.display_name)
            .on_conflict_do_nothing()
        )
        await _changed(session, org, user, "org.message_ack", message_id=str(message_id))
        found = await org_messages(session, org_id, message_id)
    await session.commit()
    return found[0]


# ---------------------------------------------------------------- awareness by kind


@router.get("/orgs/{org_id}/awareness", response_model=list[schemas.AwarenessTip])
async def awareness(org_id: OrgId, user: CurrentUser, session: Session) -> list[schemas.AwarenessTip]:
    org, _ = await service.membership(session, user, org_id)
    await session.commit()
    rows = await session.scalars(
        select(SafetyTip)
        .where(SafetyTip.status == "published", any_(SafetyTip.org_kinds) == org.kind)
        .order_by(SafetyTip.position, SafetyTip.hazard)
    )
    return [schemas.AwarenessTip(id=t.id, hazard=t.hazard, content=t.content, updated_at=t.updated_at) for t in rows]


# ---------------------------------------------------------------- drills and events


def activity_out(item: Activity) -> schemas.ActivityOut:
    return schemas.ActivityOut(
        id=item.id,
        kind=item.kind,
        title=item.title,
        starts_on=item.starts_on,
        ends_on=item.ends_on,
        participants=item.participants,
        notes=item.notes,
        created_by=item.created_by_name,
        created_at=item.created_at,
    )


async def activities_of(session: AsyncSession, org_id: uuid.UUID) -> list[schemas.ActivityOut]:
    rows = await session.scalars(
        select(Activity)
        .where(Activity.org_id == org_id)
        .order_by(Activity.starts_on.desc(), Activity.created_at.desc())
        .limit(ACTIVITIES_LIMIT)
    )
    return [activity_out(a) for a in rows]


@router.get("/orgs/{org_id}/activities", response_model=list[schemas.ActivityOut])
async def list_activities(org_id: OrgId, user: CurrentUser, session: Session) -> list[schemas.ActivityOut]:
    await service.membership(session, user, org_id)
    await session.commit()
    return await activities_of(session, org_id)


@router.post("/orgs/{org_id}/activities", response_model=schemas.ActivityOut, status_code=status.HTTP_201_CREATED)
async def add_activity(
    org_id: OrgId, body: schemas.ActivityIn, user: CurrentUser, session: Session
) -> schemas.ActivityOut:
    org, _ = await service.membership(session, user, org_id, OrgRole.EDITOR, lock=True)
    if body.ends_on is not None and (body.kind != "event" or body.ends_on < body.starts_on):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_dates")
    # A drill is recorded once held; an event is declared ahead.
    if body.kind == "drill" and body.starts_on > service.today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "drill_in_future")
    item = Activity(
        org_id=org_id,
        **body.model_dump(),
        created_by=user.user_id,
        created_by_name=user.display_name,
    )
    session.add(item)
    await session.flush()
    await session.refresh(item)
    await _changed(session, org, user, f"org.{body.kind}_add", item_id=str(item.id))
    out = activity_out(item)
    await session.commit()
    return out


@router.delete("/orgs/{org_id}/activities/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_activity(org_id: OrgId, item_id: uuid.UUID, user: CurrentUser, session: Session) -> Response:
    org, _ = await service.membership(session, user, org_id, OrgRole.EDITOR, lock=True)
    item = await session.get(Activity, item_id, with_for_update=True)
    if item is None or item.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await session.delete(item)
    await session.flush()
    await _changed(session, org, user, f"org.{item.kind}_delete", item_id=str(item_id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- maintenance log


async def maintenance_of(
    session: AsyncSession, org_id: uuid.UUID, equipment_id: uuid.UUID | None = None
) -> list[schemas.MaintenanceOut]:
    stored = (
        select(DocumentVersion.document_id, func.max(DocumentVersion.version).label("version"))
        .where(DocumentVersion.status == "stored")
        .group_by(DocumentVersion.document_id)
        .subquery()
    )
    query = (
        select(Maintenance, stored.c.version)
        .outerjoin(stored, stored.c.document_id == Maintenance.document_id)
        .where(Maintenance.org_id == org_id)
        .order_by(Maintenance.done_on.desc(), Maintenance.recorded_at.desc())
        .limit(MAINTENANCE_LIMIT)
    )
    if equipment_id is not None:
        query = query.where(Maintenance.equipment_id == equipment_id)
    return [
        schemas.MaintenanceOut(
            id=m.id,
            equipment_id=m.equipment_id,
            done_on=m.done_on,
            note=m.note,
            document_id=m.document_id,
            photo_version=version,
            recorded_by=m.recorded_by_name,
            recorded_at=m.recorded_at,
        )
        for m, version in (await session.execute(query)).all()
    ]


@router.get("/orgs/{org_id}/equipment/{item_id}/maintenance", response_model=list[schemas.MaintenanceOut])
async def list_maintenance(
    org_id: OrgId, item_id: uuid.UUID, user: CurrentUser, session: Session
) -> list[schemas.MaintenanceOut]:
    await service.membership(session, user, org_id)
    item = await session.get(Equipment, item_id)
    if item is None or item.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await session.commit()
    return await maintenance_of(session, org_id, item_id)


@router.post(
    "/orgs/{org_id}/equipment/{item_id}/maintenance",
    response_model=schemas.MaintenanceOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_maintenance(
    org_id: OrgId, item_id: uuid.UUID, body: schemas.MaintenanceIn, user: CurrentUser, session: Session
) -> schemas.MaintenanceOut:
    """Records a maintenance; the most recent date becomes the equipment's last maintenance."""
    org, _ = await service.membership(session, user, org_id, OrgRole.EDITOR, lock=True)
    item = await service.owned(session, Equipment, org_id, item_id)
    if body.done_on > service.today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "maintenance_in_future")
    if body.document_id is not None:
        doc = await session.get(Document, body.document_id)
        used = await session.scalar(select(Maintenance.id).where(Maintenance.document_id == body.document_id))
        if doc is None or doc.org_id != org_id or doc.kind != "maintenance_photo" or used is not None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_document")
    entry = Maintenance(
        org_id=org_id,
        equipment_id=item_id,
        done_on=body.done_on,
        note=(body.note or "").strip() or None,
        document_id=body.document_id,
        recorded_by=user.user_id,
        recorded_by_name=user.display_name,
    )
    session.add(entry)
    if item.last_maintenance_on is None or body.done_on > item.last_maintenance_on:
        item.last_maintenance_on = body.done_on
        item.updated_at = service.now()
    await session.flush()
    await _changed(session, org, user, "org.maintenance_add", item_id=str(item_id), photo=body.document_id is not None)
    out = next(m for m in await maintenance_of(session, org_id, item_id) if m.id == entry.id)
    await session.commit()
    return out


# ---------------------------------------------------------------- dashboard


async def upcoming_events(session: AsyncSession, scope: Any, limit: int) -> list[schemas.StaffActivity]:
    """Public events not yet over, soonest first (``scope`` filters the institutions)."""
    on = service.today()
    rows = await session.execute(
        select(Activity, Organization)
        .join(Organization, Organization.id == Activity.org_id)
        .where(
            Activity.kind == "event",
            func.coalesce(Activity.ends_on, Activity.starts_on) >= on,
            and_(Organization.status == "active", scope),
        )
        .order_by(Activity.starts_on, Activity.id)
        .limit(limit)
    )
    return [
        schemas.StaffActivity(
            **activity_out(a).model_dump(),
            org_id=o.id,
            org_name=o.name,
            org_kind=o.kind,
            gouvernorat_code=o.gouvernorat_code,
        )
        for a, o in rows.all()
    ]
