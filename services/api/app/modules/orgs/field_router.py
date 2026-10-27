"""Prevention visits on the inspector's phone, phase P4c (docs/phase-p4/design-staff.md §8.7, F-STF-06).

The inspector (``org_auditor``) uses the staff app with a registered phone (``X-Staff-Device``), like team leaders.
Each write answers the visit as the phone shows it; a resent write (same ``client_id``) is applied once.
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.ops import crew
from app.modules.ops.crew_router import _body
from app.modules.ops.models import StaffDevice
from app.modules.orgs import field, prevention, schemas, service
from app.modules.orgs.router import delete_objects

router = APIRouter(prefix="/api/v1/crew/prevention", tags=["crew"])

Session = Annotated[AsyncSession, Depends(get_session)]
Inspector = Annotated[Principal, Depends(require_roles(Role.ORG_AUDITOR))]
DeviceId = Annotated[uuid.UUID | None, Header(alias="X-Staff-Device")]


async def _device(principal: Inspector, session: Session, device_id: DeviceId = None) -> StaffDevice:
    return await crew.current_device(session, principal, device_id)


Device = Annotated[StaffDevice, Depends(_device)]


@router.get("/visits", response_model=list[schemas.FieldVisit])
async def visits(principal: Inspector, session: Session, _device: Device) -> list[schemas.FieldVisit]:
    """Scheduled visits, and inspected ones waiting for the decision, in the inspector's scope."""
    out = await field.visits(session, principal)
    await session.commit()
    return out


@router.get("/visits/{visit_id}", response_model=schemas.FieldVisit)
async def get_visit(principal: Inspector, session: Session, _device: Device, visit_id: uuid.UUID) -> schemas.FieldVisit:
    visit, org = await field.field_visit(session, principal, visit_id)
    out = await field.view(session, principal, visit, org)
    await session.commit()
    return out


@router.post("/visits/{visit_id}/claim", response_model=schemas.FieldVisit)
async def claim(principal: Inspector, session: Session, _device: Device, visit_id: uuid.UUID) -> schemas.FieldVisit:
    """«آخذها»: the visit is the inspector's, on this phone."""
    visit, org = await field.field_visit(session, principal, visit_id, lock=True)
    if not field._mine(visit, principal):
        field.claim(visit, principal)
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action="prevention.claim",
            target=f"org:{org.id}",
            details={"visit": str(visit_id)},
        )
        await service.org_event(session, org.id)
    await session.commit()
    return await field.view(session, principal, visit, org)


@router.post(
    "/visits/{visit_id}/photos",
    response_model=schemas.FieldVisit,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {t: {"schema": {"type": "string", "format": "binary"}} for t in sorted(field.PHOTO_TYPES)},
        }
    },
)
async def add_photo(
    principal: Inspector,
    session: Session,
    _device: Device,
    request: Request,
    visit_id: uuid.UUID,
    client_id: uuid.UUID,
    item_key: Annotated[str | None, Query(max_length=60, pattern=r"^[a-z0-9_.]+$")] = None,
    device_at: datetime | None = None,
) -> schemas.FieldVisit:
    """A photo of the visit (under a grid item, or general) as the raw request body, its type in ``Content-Type``."""
    content_type = (request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    data = await _body(request, field.PHOTO_MAX_BYTES)
    visit, org = await field.field_visit(session, principal, visit_id, lock=True)
    photo = await field.add_photo(session, principal, visit, item_key, client_id, device_at, content_type, data)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="prevention.photo",
        target=f"org:{org.id}",
        details={"visit": str(visit_id), "photo": str(photo.id), "item": item_key},
    )
    await session.commit()
    return await field.view(session, principal, visit, org)


@router.post("/visits/{visit_id}/inspection", response_model=schemas.FieldVisit)
async def record_inspection(
    principal: Inspector, session: Session, _device: Device, visit_id: uuid.UUID, body: schemas.FieldInspectionIn
) -> schemas.FieldVisit:
    """The grid filled on site, with both signatures; the server renders the visit report."""
    visit, org = await field.field_visit(session, principal, visit_id, lock=True)
    applied, stale = await field.inspect(session, principal, visit, org, body)
    if applied:
        comparison = visit.comparison or {}
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action="prevention.inspection",
            target=f"org:{org.id}",
            details={
                "visit": str(visit_id),
                "inspected_on": str(visit.inspected_on),
                "conform": comparison.get("conform"),
                "nonconform": comparison.get("nonconform"),
                "on_phone": True,
            },
        )
        await service.org_event(session, org.id)
    await session.commit()
    await delete_objects(*stale)
    return await field.view(session, principal, visit, org)


@router.post("/visits/{visit_id}/decision", response_model=schemas.FieldVisit)
async def decide(
    principal: Inspector, session: Session, _device: Device, visit_id: uuid.UUID, body: schemas.VisitDecisionIn
) -> schemas.FieldVisit:
    """The decision with its reservations and their due dates; sent only online (the certificate is issued now)."""
    visit, org = await field.field_visit(session, principal, visit_id, lock=True)
    issued, stale, applied = await field.decide(session, principal, visit, org, body)
    if applied:
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action="prevention.decision",
            target=f"org:{org.id}",
            reason=visit.decision_reason,
            details={
                "visit": str(visit_id),
                "decision": body.decision,
                "reservations": len(body.reservations),
                "code": issued.code if issued else None,
                "on_phone": True,
            },
        )
        await prevention.notify_admins(session, org, visit, "decided")
        await service.org_event(session, org.id)
    await session.commit()
    await delete_objects(*stale)
    return await field.view(session, principal, visit, org)
