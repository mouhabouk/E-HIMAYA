"""Prevention visits on the inspector's phone (phase P4c, docs/phase-p4/design-staff.md §8, F-STF-06).

The inspector (``org_auditor``) takes a scheduled visit on the staff app, downloads it, fills the grid on site even
without a network, takes photos and gets both signatures, then sends everything when the phone is back online: the
photos first, then the inspection, then the decision. Each write carries an id the phone made (``client_id``), so a
resent one is applied once. The rules are those of the dashboard (P3b, ``prevention.py``).
"""

import base64
import binascii
import hashlib
import uuid
from datetime import datetime

from fastapi import HTTPException, status
from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.core.storage import get_store
from app.modules.audit import service as audit
from app.modules.orgs import certificate, prevention, schemas, service
from app.modules.orgs.models import Organization, PreventionPhoto, PreventionVisit
from app.modules.reports import sniff

# Visits the phone lists: scheduled, or inspected and waiting for the decision.
FIELD_STATUSES = ("scheduled", "inspected")
PHOTO_TYPES = frozenset({"image/jpeg", "image/png"})
PHOTO_MAX_BYTES = 8 * 1024 * 1024
PHOTOS_PER_VISIT = 20
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _mine(visit: PreventionVisit, principal: Principal) -> bool:
    return visit.inspector_subject == principal.subject


def _taken_by_other(visit: PreventionVisit, principal: Principal) -> bool:
    return visit.inspector_subject is not None and visit.inspector_subject != principal.subject


async def _location(session: AsyncSession, org: Organization) -> schemas.Point | None:
    row = (
        await session.execute(
            select(
                func.ST_Y(cast(Organization.location, Geometry)), func.ST_X(cast(Organization.location, Geometry))
            ).where(Organization.id == org.id)
        )
    ).first()
    if row is None or row[0] is None:
        return None
    return schemas.Point(lat=row[0], lon=row[1])


async def view(
    session: AsyncSession, principal: Principal, visit: PreventionVisit, org: Organization
) -> schemas.FieldVisit:
    staff = await prevention.staff_view(session, visit, org)
    return schemas.FieldVisit(
        **staff.model_dump(),
        org_address=org.address,
        org_location=await _location(session, org),
        mine=_mine(visit, principal),
        taken_by_other=_taken_by_other(visit, principal),
    )


async def visits(session: AsyncSession, principal: Principal) -> list[schemas.FieldVisit]:
    """Scheduled visits and inspected ones waiting for the decision, in the inspector's scope, the nearest date
    first (the inspector's own first on the same day)."""
    rows = (
        await session.execute(
            select(PreventionVisit, Organization)
            .join(Organization, Organization.id == PreventionVisit.org_id)
            .where(service.staff_scope(principal), PreventionVisit.status.in_(FIELD_STATUSES))
            .order_by(
                PreventionVisit.scheduled_on.asc().nulls_last(),
                (PreventionVisit.inspector_subject == principal.subject).desc().nulls_last(),
                PreventionVisit.created_at,
            )
            .limit(50)
        )
    ).all()
    return [await view(session, principal, visit, org) for visit, org in rows]


async def field_visit(
    session: AsyncSession, principal: Principal, visit_id: uuid.UUID, *, lock: bool = False
) -> tuple[PreventionVisit, Organization]:
    visit, org = await prevention.scoped_visit(session, principal, visit_id, lock=lock)
    if visit.status not in (*FIELD_STATUSES, "decided"):
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    return visit, org


def _own(visit: PreventionVisit, principal: Principal) -> None:
    """A visit another inspector took on a phone stays theirs until the Office names someone else."""
    if _taken_by_other(visit, principal):
        raise HTTPException(status.HTTP_409_CONFLICT, "visit_taken")


def claim(visit: PreventionVisit, principal: Principal) -> None:
    """«آخذها»: the visit is the inspector's, on this phone, under the inspector's name."""
    if visit.status not in FIELD_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    _own(visit, principal)
    visit.inspector_subject = principal.subject
    visit.inspector_name = audit.name_of(principal) or visit.inspector_name


async def add_photo(
    session: AsyncSession,
    principal: Principal,
    visit: PreventionVisit,
    item_key: str | None,
    client_id: uuid.UUID,
    device_at: datetime | None,
    content_type: str,
    data: bytes,
) -> PreventionPhoto:
    """A photo sent as the request body; its type is checked from its bytes. Sent twice, kept once."""
    known = await session.scalar(select(PreventionPhoto).where(PreventionPhoto.client_id == client_id))
    if known is not None:
        if known.visit_id != visit.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "client_id_reused")
        return known
    if visit.status not in FIELD_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    _own(visit, principal)
    if content_type not in PHOTO_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported_media_type")
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "empty_file")
    if sniff.verify(content_type, data[: sniff.HEAD_BYTES]).reason is not None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "type_mismatch")
    count = await session.scalar(
        select(func.count()).select_from(PreventionPhoto).where(PreventionPhoto.visit_id == visit.id)
    )
    if (count or 0) >= PHOTOS_PER_VISIT:
        raise HTTPException(status.HTTP_409_CONFLICT, "too_many_photos")
    key = f"prevention/{visit.id}/photo-{uuid.uuid4().hex}{sniff.EXTENSIONS.get(content_type, '')}"
    await get_store().put(key, data, content_type)
    photo = PreventionPhoto(
        visit_id=visit.id,
        org_id=visit.org_id,
        item_key=item_key,
        object_key=key,
        sha256=hashlib.sha256(data).hexdigest(),
        bytes=len(data),
        content_type=content_type,
        client_id=client_id,
        created_by=audit.actor_of(principal),
        created_by_name=audit.name_of(principal),
        device_at=device_at,
    )
    session.add(photo)
    await session.flush()
    await session.refresh(photo)
    return photo


def _png(value: str) -> bytes:
    try:
        data = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_signature") from None
    if not data.startswith(PNG_MAGIC) or len(data) > prevention.SIGNATURE_MAX_BYTES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_signature")
    return data


async def inspect(
    session: AsyncSession,
    principal: Principal,
    visit: PreventionVisit,
    org: Organization,
    body: schemas.FieldInspectionIn,
) -> tuple[bool, list[str]]:
    """The grid filled on the phone with both signatures. Returns whether it was applied now (a resend is not) and
    the object keys to delete after commit."""
    if visit.inspection_client_id == body.client_id:
        return False, []
    _own(visit, principal)
    inspector, representative = _png(body.inspector_signature), _png(body.representative_signature)
    if visit.status not in FIELD_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    stale = [k for k in (visit.inspector_signature_key, visit.representative_signature_key) if k]
    store = get_store()
    keys = []
    for who, data in (("inspector", inspector), ("representative", representative)):
        key = f"prevention/{visit.id}/signature-{who}-{uuid.uuid4().hex[:8]}.png"
        await store.put(key, data, prevention.SIGNATURE_TYPE)
        keys.append(key)
    visit.inspector_signature_key, visit.representative_signature_key = keys
    visit.representative_name = body.representative_name.strip()
    visit.representative_role = prevention._clean(body.representative_role)
    visit.inspector_subject = principal.subject
    visit.inspection_client_id = body.client_id
    visit.inspected_device_at = body.device_at
    stale += await prevention.inspect(session, visit, org, body, audit.actor_of(principal), audit.name_of(principal))
    return True, stale


async def decide(
    session: AsyncSession,
    principal: Principal,
    visit: PreventionVisit,
    org: Organization,
    body: schemas.VisitDecisionIn,
) -> tuple[schemas.CertificateOut | None, list[str], bool]:
    """The decision from the phone, with the dashboard's rules. A decision resent by the same inspector after it
    was recorded is not applied again. Returns the issued certificate, the keys to delete and whether it was
    applied now."""
    if visit.status == "decided" and visit.decided_by == audit.actor_of(principal) and visit.decision == body.decision:
        return None, [], False
    _own(visit, principal)
    issued, stale = await prevention.decide(
        session, visit, org, body, audit.actor_of(principal), audit.name_of(principal)
    )
    if issued is not None:
        await certificate.certificate_event(session, issued)
        return certificate.certificate_out(issued), stale, True
    return None, stale, True
