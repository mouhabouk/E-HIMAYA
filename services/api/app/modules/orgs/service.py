"""Institutions (FR-B-001…FR-B-009, FR-B-011, FR-C-05): membership, card, registers, views.

Authorization is by membership (``org.member``), checked on every call; a caller who is not a member
gets ``404 org_not_found`` so the existence of an institution is not disclosed.
"""

import base64
import hashlib
import secrets
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from geoalchemy2 import Geography, Geometry
from sqlalchemy import Select, and_, case, cast, delete, exists, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.events import emit
from app.core.security import CurrentPrincipal, Principal, Realm
from app.modules.identity.service import Reporter, resolve_reporter
from app.modules.notify import outbox, templates
from app.modules.notify.org_target import ORG_TARGET
from app.modules.orgs import domain, schemas
from app.modules.orgs.domain import OrgRole, OrgStatus
from app.modules.orgs.models import (
    Certificate,
    Document,
    DocumentVersion,
    Equipment,
    Hazmat,
    Invitation,
    MapFeature,
    Member,
    Organization,
    TeamMember,
)

_LAT = func.ST_Y(cast(Organization.location, Geometry))
_LON = func.ST_X(cast(Organization.location, Geometry))


def point(lat: float, lon: float) -> Any:
    return cast(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), Geography)


def now() -> datetime:
    return datetime.now(UTC)


def today() -> date:
    return now().date()


# ---------------------------------------------------------------- callers and membership


@dataclass(frozen=True, slots=True)
class PortalUser:
    """A signed-in user of the public realm (portal or app) with their unified account."""

    reporter: Reporter
    principal: Principal

    @property
    def user_id(self) -> uuid.UUID:
        return self.reporter.user_id

    @property
    def display_name(self) -> str | None:
        claims = self.principal.claims
        name = claims.get("name") or " ".join(p for p in (claims.get("given_name"), claims.get("family_name")) if p)
        return str(name or claims.get("preferred_username") or "") or None

    @property
    def email(self) -> str | None:
        value = self.principal.claims.get("email")
        return str(value).lower() if value else None

    @property
    def email_verified(self) -> bool:
        return bool(self.principal.claims.get("email_verified")) and self.email is not None

    @property
    def actor(self) -> str:
        return f"{self.principal.realm.value}:{self.principal.subject}"


async def get_portal_user(
    principal: CurrentPrincipal, session: Annotated[AsyncSession, Depends(get_session)]
) -> PortalUser:
    if principal.realm is not Realm.PUBLIC:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "realm_not_allowed")
    reporter = await resolve_reporter(session, principal, None)
    return PortalUser(reporter=reporter, principal=principal)


CurrentUser = Annotated[PortalUser, Depends(get_portal_user)]


async def membership(
    session: AsyncSession,
    user: PortalUser,
    org_id: uuid.UUID,
    needed: OrgRole = OrgRole.MEMBER,
    *,
    lock: bool = False,
) -> tuple[Organization, Member]:
    query = select(Organization).where(Organization.id == org_id)
    org = await session.scalar(query.with_for_update() if lock else query)
    member = await session.get(Member, (org_id, user.user_id)) if org is not None else None
    if org is None or member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "org_not_found")
    if not domain.role_allows(OrgRole(member.role), needed):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "org_role_required")
    # Keep the name and e-mail shown to other members in step with the identity provider.
    if (member.display_name, member.email) != (user.display_name, user.email):
        member.display_name, member.email = user.display_name, user.email
    return org, member


def require_active(org: Organization) -> None:
    if org.status != OrgStatus.ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, "org_not_active")


# ---------------------------------------------------------------- registers and computed views


@dataclass(slots=True)
class Registers:
    team: list[TeamMember]
    hazmat: list[Hazmat]
    equipment: list[Equipment]
    features: list[tuple[MapFeature, float, float]]
    documents: list[tuple[Document, DocumentVersion | None, int]]


async def load_registers(session: AsyncSession, org_id: uuid.UUID) -> Registers:
    team = list(
        await session.scalars(
            select(TeamMember)
            .where(TeamMember.org_id == org_id)
            .order_by(TeamMember.team_role.desc(), TeamMember.full_name, TeamMember.id)
        )
    )
    hazmat = list(await session.scalars(select(Hazmat).where(Hazmat.org_id == org_id).order_by(Hazmat.name, Hazmat.id)))
    equipment = list(
        await session.scalars(
            select(Equipment).where(Equipment.org_id == org_id).order_by(Equipment.kind, Equipment.id)
        )
    )
    features = [
        (row[0], float(row[1]), float(row[2]))
        for row in await session.execute(
            select(
                MapFeature,
                func.ST_Y(cast(MapFeature.location, Geometry)),
                func.ST_X(cast(MapFeature.location, Geometry)),
            )
            .where(MapFeature.org_id == org_id)
            .order_by(MapFeature.created_at, MapFeature.id)
        )
    ]
    return Registers(team, hazmat, equipment, features, await documents_of(session, org_id))


async def documents_of(session: AsyncSession, org_id: uuid.UUID) -> list[tuple[Document, DocumentVersion | None, int]]:
    docs = list(
        await session.scalars(
            select(Document)
            # Maintenance photos are shown with their equipment, not in the documents list (phase P2b).
            .where(Document.org_id == org_id, Document.kind != "maintenance_photo")
            .order_by(Document.kind, Document.title)
        )
    )
    if not docs:
        return []
    ids = [d.id for d in docs]
    current: dict[uuid.UUID, DocumentVersion] = {}
    for version in await session.scalars(
        select(DocumentVersion)
        .where(DocumentVersion.document_id.in_(ids), DocumentVersion.status == "stored")
        .order_by(DocumentVersion.document_id, DocumentVersion.version.desc())
        .ext(distinct_on(DocumentVersion.document_id))
    ):
        current[version.document_id] = version
    counts = dict(
        (
            await session.execute(
                select(DocumentVersion.document_id, func.count())
                .where(DocumentVersion.document_id.in_(ids), DocumentVersion.status != "rejected")
                .group_by(DocumentVersion.document_id)
            )
        ).all()
    )
    return [(d, current.get(d.id), int(counts.get(d.id, 0))) for d in docs]


def classification_of(org: Organization, hazmat_count: int) -> domain.Classification:
    return domain.classify(
        kind=org.kind,
        capacity=org.capacity,
        height_m=org.height_m,
        receives_public=org.receives_public,
        hazmat_count=hazmat_count,
    )


def classification_out(c: domain.Classification) -> schemas.ClassificationOut:
    return schemas.ClassificationOut(
        family=c.family,
        category=c.category,
        high_rise=c.high_rise,
        required=list(c.required),
        provisional=c.provisional,
    )


def team_out(member: TeamMember, on: date) -> schemas.TeamMemberOut:
    state, expires = domain.training_status(member.last_training_on, member.training_valid_months, on)
    return schemas.TeamMemberOut(
        id=member.id,
        full_name=member.full_name,
        team_role=member.team_role,
        position=member.position,
        phone=member.phone,
        email=member.email,
        last_training_on=member.last_training_on,
        training_valid_months=member.training_valid_months,
        training_status=state,
        training_expires_on=expires,
    )


def equipment_out(item: Equipment, on: date) -> schemas.EquipmentOut:
    state, due = domain.maintenance_status(item.last_maintenance_on, item.maintenance_interval_months, on)
    return schemas.EquipmentOut(
        id=item.id,
        kind=item.kind,
        count=item.count,
        location=item.location,
        last_maintenance_on=item.last_maintenance_on,
        maintenance_interval_months=item.maintenance_interval_months,
        maintenance_status=state,
        next_maintenance_on=due,
    )


def hazmat_out(item: Hazmat) -> schemas.HazmatOut:
    return schemas.HazmatOut(
        id=item.id,
        name=item.name,
        un_number=item.un_number,
        hazard_class=item.hazard_class,
        quantity=float(item.quantity),
        unit=item.unit,
        storage_location=item.storage_location,
        sds_document_id=item.sds_document_id,
    )


def feature_out(feature: MapFeature, lat: float, lon: float) -> schemas.FeatureOut:
    return schemas.FeatureOut(
        id=feature.id,
        kind=feature.kind,
        label=feature.label,
        location=schemas.Point(lat=lat, lon=lon),
    )


def version_out(version: DocumentVersion) -> schemas.DocumentVersionOut:
    return schemas.DocumentVersionOut(
        version=version.version,
        filename=version.filename,
        content_type=version.content_type,
        bytes=version.bytes,
        sha256=version.sha256,
        status=version.status,
        uploaded_at=version.created_at,
        uploaded_by=version.uploaded_by_name,
        note=version.note,
    )


def document_out(doc: Document, current: DocumentVersion | None, count: int) -> schemas.DocumentOut:
    return schemas.DocumentOut(
        id=doc.id,
        kind=doc.kind,
        title=doc.title,
        current_version=version_out(current) if current else None,
        versions_count=count,
    )


def alerts_of(team: Sequence[TeamMember], equipment: Sequence[Equipment], on: date) -> list[schemas.Alert]:
    alerts: list[schemas.Alert] = []
    for member in team:
        state, expires = domain.training_status(member.last_training_on, member.training_valid_months, on)
        if state in ("expired", "expiring"):
            kind = "training_expired" if state == "expired" else "training_expiring"
            alerts.append(schemas.Alert(kind=kind, ref=member.id, since=expires))
    for item in equipment:
        state, due = domain.maintenance_status(item.last_maintenance_on, item.maintenance_interval_months, on)
        if state in ("overdue", "due_soon"):
            kind = "maintenance_overdue" if state == "overdue" else "maintenance_due_soon"
            alerts.append(schemas.Alert(kind=kind, ref=item.id, since=due))
    return alerts


def completeness_of(classification: domain.Classification, regs: Registers, on: date) -> schemas.Completeness:
    facts = domain.Facts(
        stored_document_kinds=frozenset(doc.kind for doc, current, _ in regs.documents if current is not None),
        representative=any(m.team_role == "representative" for m in regs.team),
        team_members=sum(1 for m in regs.team if m.team_role == "member"),
        training_statuses=tuple(
            domain.training_status(m.last_training_on, m.training_valid_months, on)[0] for m in regs.team
        ),
        hazmat_without_sds=sum(1 for h in regs.hazmat if h.sds_document_id is None or not _has_stored(regs, h)),
        equipment_statuses=tuple(
            domain.maintenance_status(e.last_maintenance_on, e.maintenance_interval_months, on)[0]
            for e in regs.equipment
        ),
        evacuation_points=sum(1 for f, _, _ in regs.features if f.kind == "evacuation_point"),
    )
    missing = domain.missing(classification.required, facts)
    return schemas.Completeness(ok=not missing, missing=list(missing))


def _has_stored(regs: Registers, hazmat: Hazmat) -> bool:
    return any(doc.id == hazmat.sds_document_id and current is not None for doc, current, _ in regs.documents)


async def coords(session: AsyncSession, org_id: uuid.UUID) -> tuple[float, float]:
    found = (await session.execute(select(_LAT, _LON).where(Organization.id == org_id))).one()
    return float(found[0]), float(found[1])


def _person(raw: dict[str, Any] | None) -> schemas.Person:
    return schemas.Person.model_validate(raw or {})


async def card(
    session: AsyncSession, org: Organization, regs: Registers | None = None, reader: str = "member"
) -> dict[str, Any]:
    """Fields of ``OrgCard`` (shared by the member and staff views); ``reader`` limits the kind fields."""
    regs = regs or await load_registers(session, org.id)
    on = today()
    classification = classification_of(org, len(regs.hazmat))
    completeness = completeness_of(classification, regs, on)
    lat, lon = await coords(session, org.id)
    return {
        "id": org.id,
        "status": org.status,
        "version": org.version,
        "name": org.name,
        "kind": org.kind,
        "identifier_type": org.identifier_type,
        "identifier": org.identifier,
        "activity_sector": org.activity_sector,
        "activity_type": org.activity_type,
        "capacity": org.capacity,
        "floors": org.floors,
        "height_m": org.height_m,
        "receives_public": org.receives_public,
        "address": org.address,
        "location": schemas.Point(lat=lat, lon=lon),
        "gouvernorat_code": org.gouvernorat_code,
        "delegation_id": org.delegation_id,
        "manager": _person(org.manager),
        "contact_email": org.contact_email,
        "contact_phone": org.contact_phone,
        "classification": classification_out(classification),
        "completeness": completeness,
        "readiness": domain.readiness(classification.required, completeness.missing),
        "kind_fields": domain.visible_kind_fields(org.kind, org.kind_fields or {}, reader),
        "kind_review": org.kind_review,
        "alerts": alerts_of(regs.team, regs.equipment, on) + await _certificate_alerts(session, org, regs, on),
        "review": schemas.Review(reason=org.review_reason, at=org.reviewed_at),
        "created_at": org.created_at,
        "updated_at": org.updated_at,
    }


async def org_out(session: AsyncSession, org: Organization, member: Member) -> schemas.OrgOut:
    return schemas.OrgOut(**(await card(session, org)), my_role=OrgRole(member.role))


# ---------------------------------------------------------------- card (FR-B-001, FR-B-002)


def _validated_card(body: schemas.OrgIn) -> dict[str, Any]:
    identifier = domain.normalize_identifier(body.identifier_type, body.identifier)
    if identifier is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_identifier")
    phones: dict[str, str | None] = {}
    for key, raw in (("contact_phone", body.contact_phone), ("manager_phone", body.manager.phone)):
        if raw:
            normalized = domain.normalize_phone(raw)
            if normalized is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_phone")
            phones[key] = normalized
        else:
            phones[key] = None
    manager = body.manager.model_dump(mode="json")
    manager["phone"] = phones["manager_phone"]
    kind_fields = domain.clean_kind_fields(body.kind, body.kind_fields)
    if isinstance(kind_fields, str):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"invalid_kind_field:{kind_fields}")
    phone = kind_fields.get("reception_phone")
    if isinstance(phone, str):
        normalized_reception = domain.normalize_phone(phone)
        if normalized_reception is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_phone")
        kind_fields["reception_phone"] = normalized_reception
    return {
        "name": body.name.strip(),
        "kind": body.kind.value,
        "identifier_type": body.identifier_type,
        "identifier": identifier,
        "activity_sector": body.activity_sector,
        "activity_type": body.activity_type,
        "capacity": body.capacity,
        "floors": body.floors,
        "height_m": body.height_m,
        "receives_public": body.receives_public,
        "address": body.address,
        "manager": manager,
        "contact_email": str(body.contact_email).lower() if body.contact_email else None,
        "contact_phone": phones["contact_phone"],
        "kind_fields": kind_fields,
    }


async def _identifier_taken(session: AsyncSession, identifier: str, except_id: uuid.UUID | None = None) -> bool:
    query = select(Organization.id).where(Organization.identifier == identifier)
    if except_id is not None:
        query = query.where(Organization.id != except_id)
    return await session.scalar(query.limit(1)) is not None


async def create_org(session: AsyncSession, user: PortalUser, body: schemas.OrgIn) -> tuple[Organization, Member]:
    from app.modules.reports.service import locate_gouvernorat

    if not user.email_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "email_not_verified")
    created = await session.scalar(select(func.count()).where(Organization.created_by == user.user_id))
    if (created or 0) >= domain.MAX_ORGS_PER_ACCOUNT:
        raise HTTPException(status.HTTP_409_CONFLICT, "too_many_orgs")
    values = _validated_card(body)
    if await _identifier_taken(session, values["identifier"]):
        raise HTTPException(status.HTTP_409_CONFLICT, "identifier_already_registered")
    org = Organization(
        **values,
        status=OrgStatus.PENDING_REVIEW.value,
        version=1,
        location=point(body.location.lat, body.location.lon),
        gouvernorat_code=await locate_gouvernorat(session, body.location.lat, body.location.lon),
        created_by=user.user_id,
    )
    session.add(org)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "identifier_already_registered") from None
    member = Member(
        org_id=org.id, user_id=user.user_id, role=OrgRole.ADMIN.value, display_name=user.display_name, email=user.email
    )
    session.add(member)
    await session.flush()
    await session.refresh(org)
    return org, member


async def update_org(session: AsyncSession, org: Organization, body: schemas.OrgUpdate) -> bool:
    """Apply the card; returns True when the institution went back to review."""
    from app.modules.reports.service import locate_gouvernorat

    if body.version != org.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
    values = _validated_card(body)
    if values["identifier"] != org.identifier and await _identifier_taken(session, values["identifier"], org.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "identifier_already_registered")
    back_to_review = org.status == OrgStatus.ACTIVE and (
        values["identifier"] != org.identifier or values["name"] != org.name
    )
    if values["kind"] != org.kind:
        org.kind_review = False  # the institution chose its kind itself
    for key, value in values.items():
        setattr(org, key, value)
    org.location = point(body.location.lat, body.location.lon)
    org.gouvernorat_code = await locate_gouvernorat(session, body.location.lat, body.location.lon)
    if back_to_review:
        org.status = OrgStatus.PENDING_REVIEW.value
    org.version += 1
    org.updated_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(org)
    return back_to_review


async def my_orgs(session: AsyncSession, user: PortalUser) -> list[schemas.MyOrg]:
    rows = (
        await session.execute(
            select(Organization, Member.role)
            .join(Member, Member.org_id == Organization.id)
            .where(Member.user_id == user.user_id)
            .order_by(func.lower(Organization.name), Organization.id)
        )
    ).all()
    alerts = await alerts_counts(session, [org.id for org, _ in rows])
    return [
        schemas.MyOrg(
            id=org.id,
            name=org.name,
            kind=org.kind,
            status=org.status,
            my_role=OrgRole(role),
            alerts_count=alerts.get(org.id, 0),
        )
        for org, role in rows
    ]


async def alerts_counts(session: AsyncSession, org_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not org_ids:
        return {}
    team: dict[uuid.UUID, list[TeamMember]] = defaultdict(list)
    equipment: dict[uuid.UUID, list[Equipment]] = defaultdict(list)
    for member in await session.scalars(select(TeamMember).where(TeamMember.org_id.in_(org_ids))):
        team[member.org_id].append(member)
    for item in await session.scalars(select(Equipment).where(Equipment.org_id.in_(org_ids))):
        equipment[item.org_id].append(item)
    on = today()
    # The certificate's end of validity counts here; "needs update" needs the full comparison and shows on the card.
    ending = set(
        await session.scalars(
            select(Certificate.org_id).where(
                Certificate.org_id.in_(org_ids),
                Certificate.status == "approved",
                Certificate.superseded_by.is_(None),
                Certificate.valid_until <= on + timedelta(days=domain.CERTIFICATE_REMINDER_DAYS[0]),
            )
        )
    )
    return {org_id: len(alerts_of(team[org_id], equipment[org_id], on)) + (org_id in ending) for org_id in org_ids}


async def _certificate_alerts(
    session: AsyncSession, org: Organization, regs: Registers, on: date
) -> list[schemas.Alert]:
    from app.modules.orgs import certificate  # certificate builds on this module

    return await certificate.certificate_alerts(session, org, regs, on)


async def hazmat_counts(session: AsyncSession, org_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not org_ids:
        return {}
    rows = await session.execute(
        select(Hazmat.org_id, func.count()).where(Hazmat.org_id.in_(org_ids)).group_by(Hazmat.org_id)
    )
    return {org_id: int(n) for org_id, n in rows.all()}


# ---------------------------------------------------------------- members and invitations (FR-B-009)


async def members(session: AsyncSession, org_id: uuid.UUID) -> list[Member]:
    return list(
        await session.scalars(select(Member).where(Member.org_id == org_id).order_by(Member.joined_at, Member.user_id))
    )


def member_out(member: Member) -> schemas.MemberOut:
    return schemas.MemberOut(
        user_id=member.user_id,
        display_name=member.display_name,
        email=member.email,
        role=OrgRole(member.role),
        joined_at=member.joined_at,
    )


async def _admins(session: AsyncSession, org_id: uuid.UUID) -> int:
    return int(
        await session.scalar(select(func.count()).where(Member.org_id == org_id, Member.role == OrgRole.ADMIN.value))
        or 0
    )


async def set_role(session: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, role: OrgRole) -> Member:
    target = await session.get(Member, (org_id, user_id), with_for_update=True)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if target.role == OrgRole.ADMIN and role != OrgRole.ADMIN and await _admins(session, org_id) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "last_admin")
    target.role = role.value
    await session.flush()
    return target


async def remove_member(session: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
    target = await session.get(Member, (org_id, user_id), with_for_update=True)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if target.role == OrgRole.ADMIN and await _admins(session, org_id) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "last_admin")
    await session.delete(target)
    await session.flush()


def _token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def _pending() -> Any:
    return and_(Invitation.accepted_at.is_(None), Invitation.revoked_at.is_(None))


async def invite(
    session: AsyncSession, org: Organization, user: PortalUser, body: schemas.InvitationIn
) -> schemas.InvitationCreated:
    require_active(org)
    pending = await session.scalar(
        select(func.count()).where(Invitation.org_id == org.id, _pending(), Invitation.expires_at > func.now())
    )
    if (pending or 0) >= domain.MAX_PENDING_INVITATIONS:
        raise HTTPException(status.HTTP_409_CONFLICT, "too_many_invitations")
    token = secrets.token_urlsafe(32)
    invitation = Invitation(
        org_id=org.id,
        email=str(body.email).lower(),
        role=body.role.value,
        token_hash=_token_hash(token),
        expires_at=datetime.now(UTC) + timedelta(days=domain.INVITATION_DAYS),
        created_by=user.user_id,
    )
    session.add(invitation)
    await session.flush()
    await session.refresh(invitation)
    accept_url = f"{get_settings().portal_public_url}/invite/{token}"
    # The link is also returned to the admin, who can share it another way if the e-mail does not arrive.
    values = {
        "org": org.name,
        "inviter": user.display_name or user.email or "",
        "expires": invitation.expires_at.date().isoformat(),
        "link": accept_url,
    }
    outbox.email(
        session,
        invitation.email,
        templates.pick(templates.fill(templates.INVITATION_SUBJECT, org=org.name), "ar"),
        templates.multilingual(templates.fill(templates.INVITATION_BODY, **values)),
    )
    return schemas.InvitationCreated(**invitation_out(invitation).model_dump(), token=token, accept_url=accept_url)


def invitation_out(invitation: Invitation) -> schemas.InvitationOut:
    return schemas.InvitationOut(
        id=invitation.id,
        email=invitation.email,
        role=OrgRole(invitation.role),
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
    )


async def pending_invitations(session: AsyncSession, org_id: uuid.UUID) -> list[Invitation]:
    return list(
        await session.scalars(
            select(Invitation)
            .where(Invitation.org_id == org_id, _pending(), Invitation.expires_at > func.now())
            .order_by(Invitation.created_at)
        )
    )


async def revoke_invitation(session: AsyncSession, org_id: uuid.UUID, invitation_id: uuid.UUID) -> None:
    invitation = await session.get(Invitation, invitation_id, with_for_update=True)
    if invitation is None or invitation.org_id != org_id or invitation.accepted_at or invitation.revoked_at:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invitation_not_found")
    invitation.revoked_at = datetime.now(UTC)
    await session.flush()


async def invitation_by_token(session: AsyncSession, token: str, *, lock: bool = False) -> Invitation:
    query = select(Invitation).where(Invitation.token_hash == _token_hash(token), _pending())
    invitation = await session.scalar(query.with_for_update() if lock else query)
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invitation_not_found")
    if invitation.expires_at <= datetime.now(UTC):
        raise HTTPException(status.HTTP_410_GONE, "invitation_expired")
    return invitation


async def accept_invitation(session: AsyncSession, user: PortalUser, token: str) -> Member:
    invitation = await invitation_by_token(session, token, lock=True)
    if not user.email_verified or user.email != invitation.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invitation_email_mismatch")
    org = await session.get(Organization, invitation.org_id)
    assert org is not None
    require_active(org)
    member = await session.get(Member, (org.id, user.user_id), with_for_update=True)
    if member is None:
        member = Member(
            org_id=org.id, user_id=user.user_id, role=invitation.role, display_name=user.display_name, email=user.email
        )
        session.add(member)
    elif domain.role_allows(OrgRole(invitation.role), OrgRole(member.role)):
        # Accepting never lowers an existing role.
        member.role = invitation.role
    invitation.accepted_at = datetime.now(UTC)
    invitation.accepted_by = user.user_id
    await session.flush()
    return member


# ---------------------------------------------------------------- safety team and registers


async def owned[T: (TeamMember, Hazmat, Equipment, MapFeature, Document)](
    session: AsyncSession, model: type[T], org_id: uuid.UUID, item_id: uuid.UUID
) -> T:
    item = await session.get(model, item_id, with_for_update=True)
    if item is None or item.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return item


async def check_representative(
    session: AsyncSession, org_id: uuid.UUID, body: schemas.TeamMemberIn, except_id: uuid.UUID | None = None
) -> None:
    if body.team_role != "representative":
        return
    query = select(TeamMember.id).where(TeamMember.org_id == org_id, TeamMember.team_role == "representative")
    if except_id is not None:
        query = query.where(TeamMember.id != except_id)
    if await session.scalar(query.limit(1)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "representative_exists")


def team_values(body: schemas.TeamMemberIn) -> dict[str, Any]:
    values = body.model_dump()
    if body.phone:
        values["phone"] = domain.normalize_phone(body.phone)
        if values["phone"] is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_phone")
    values["email"] = str(body.email).lower() if body.email else None
    values["full_name"] = body.full_name.strip()
    return values


async def hazmat_values(session: AsyncSession, org_id: uuid.UUID, body: schemas.HazmatIn) -> dict[str, Any]:
    if body.un_number is not None and not domain.valid_un_number(body.un_number):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_un_number")
    if body.sds_document_id is not None:
        doc = await session.get(Document, body.sds_document_id)
        if doc is None or doc.org_id != org_id or doc.kind != "sds":
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_document")
    return body.model_dump()


async def feature_values(session: AsyncSession, org: Organization, body: schemas.FeatureIn) -> dict[str, Any]:
    distance = await session.scalar(
        select(func.ST_Distance(Organization.location, point(body.location.lat, body.location.lon))).where(
            Organization.id == org.id
        )
    )
    if distance is None or float(distance) > domain.FEATURE_MAX_DISTANCE_M:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "feature_too_far")
    return {"kind": body.kind, "label": body.label, "location": point(body.location.lat, body.location.lon)}


async def feature_count(session: AsyncSession, org_id: uuid.UUID) -> int:
    return int(await session.scalar(select(func.count()).where(MapFeature.org_id == org_id)) or 0)


async def feature_coords(session: AsyncSession, feature_id: uuid.UUID) -> tuple[float, float]:
    found = (
        await session.execute(
            select(
                func.ST_Y(cast(MapFeature.location, Geometry)), func.ST_X(cast(MapFeature.location, Geometry))
            ).where(MapFeature.id == feature_id)
        )
    ).one()
    return float(found[0]), float(found[1])


async def touch(session: AsyncSession, org: Organization) -> None:
    """A register changed: the institution's computed views (completeness, alerts) changed too."""
    org.updated_at = datetime.now(UTC)
    await session.flush()


# ---------------------------------------------------------------- documents


async def document_in_use(session: AsyncSession, doc_id: uuid.UUID) -> bool:
    return await session.scalar(select(exists().where(Hazmat.sds_document_id == doc_id))) or False


async def versions(session: AsyncSession, doc_id: uuid.UUID) -> list[DocumentVersion]:
    return list(
        await session.scalars(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == doc_id, DocumentVersion.status != "rejected")
            .order_by(DocumentVersion.version.desc())
        )
    )


async def stored_version(session: AsyncSession, doc_id: uuid.UUID, version: int) -> DocumentVersion:
    found = await session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == doc_id,
            DocumentVersion.version == version,
            DocumentVersion.status == "stored",
        )
    )
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return found


# ---------------------------------------------------------------- reports of the institution (FR-B-011)


def encode_cursor(at: datetime, row_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{at.isoformat()}|{row_id}".encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        at, rid = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode().split("|")
        return datetime.fromisoformat(at), uuid.UUID(rid)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc


async def org_reports(
    session: AsyncSession, org_id: uuid.UUID, limit: int, cursor: str | None
) -> tuple[list[schemas.OrgReport], str | None]:
    from app.modules.reports.models import Report

    query = (
        select(Report, Member.display_name)
        .outerjoin(Member, and_(Member.org_id == Report.organization_id, Member.user_id == Report.user_id))
        .where(Report.organization_id == org_id)
    )
    if cursor:
        at, rid = decode_cursor(cursor)
        query = query.where(or_(Report.received_at < at, and_(Report.received_at == at, Report.id < rid)))
    rows = (await session.execute(query.order_by(Report.received_at.desc(), Report.id.desc()).limit(limit))).all()
    items = [
        schemas.OrgReport(
            id=r.id,
            tracking_code=r.tracking_code,
            category=r.category,
            status=r.status,
            text=r.text_original,
            received_at=r.received_at,
            updated_at=r.updated_at,
            reporter_display_name=name,
        )
        for r, name in rows
    ]
    last = rows[-1][0] if len(rows) == limit else None
    return items, encode_cursor(last.received_at, last.id) if last else None


async def reporting_org(session: AsyncSession, reporter: Reporter, org_id: uuid.UUID) -> Organization:
    """The institution a report is made on behalf of (FR-A-080): the caller must be a member."""
    member = await session.get(Member, (org_id, reporter.user_id))
    org = await session.get(Organization, org_id) if member is not None else None
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "org_not_found")
    require_active(org)
    return org


async def refs(session: AsyncSession, org_ids: Sequence[uuid.UUID | None]) -> dict[uuid.UUID, Organization]:
    wanted = {i for i in org_ids if i is not None}
    if not wanted:
        return {}
    return {org.id: org for org in await session.scalars(select(Organization).where(Organization.id.in_(wanted)))}


async def summary(session: AsyncSession, org: Organization) -> schemas.OrgSummary:
    regs = await load_registers(session, org.id)
    on = today()
    lat, lon = await coords(session, org.id)
    classification = classification_of(org, len(regs.hazmat))
    completeness = completeness_of(classification, regs, on)
    alerts = alerts_of(regs.team, regs.equipment, on) + await _certificate_alerts(session, org, regs, on)
    return schemas.OrgSummary(
        id=org.id,
        name=org.name,
        kind=org.kind,
        status=org.status,
        capacity=org.capacity,
        address=org.address,
        location=schemas.Point(lat=lat, lon=lon),
        classification=classification_out(classification),
        readiness=domain.readiness(classification.required, completeness.missing),
        missing=completeness.missing,
        kind_fields=domain.visible_kind_fields(org.kind, org.kind_fields or {}, "member"),
        team=[
            schemas.SummaryTeamMember(
                full_name=m.full_name,
                team_role=m.team_role,
                phone=m.phone,
                training_status=domain.training_status(m.last_training_on, m.training_valid_months, on)[0],
            )
            for m in regs.team
        ],
        hazmat_count=len(regs.hazmat),
        hazmat=[
            schemas.SummaryHazmat(name=h.name, un_number=h.un_number, quantity=float(h.quantity), unit=h.unit)
            for h in regs.hazmat
        ],
        alerts_count=len(alerts),
        alerts=alerts,
        messages_pending=await messages_pending(session, org.id),
    )


# Office messages addressed to an institution (phase P2b): published "organizations" messages of the last
# MESSAGE_DAYS days that reach it. ``:oid`` is the institution.
MESSAGE_DAYS = 180
ORG_MESSAGES = f"""
    FROM notify.message m JOIN org.organization o ON o.id = :oid
    LEFT JOIN notify.org_ack a ON a.message_id = m.id AND a.org_id = o.id
    WHERE m.status = 'published' AND m.published_at > now() - make_interval(days => {MESSAGE_DAYS})
      AND {ORG_TARGET}
"""


async def messages_pending(session: AsyncSession, org_id: uuid.UUID) -> int:
    count = await session.scalar(
        text(f"SELECT count(*) {ORG_MESSAGES} AND m.ack_required AND a.org_id IS NULL"),
        {"oid": org_id},
    )
    return int(count or 0)


async def organization_card(session: AsyncSession, org: Organization) -> schemas.OrganizationCard:
    regs = await load_registers(session, org.id)
    lat, lon = await coords(session, org.id)
    representative = next((m for m in regs.team if m.team_role == "representative"), None)
    return schemas.OrganizationCard(
        id=org.id,
        name=org.name,
        kind=org.kind,
        capacity=org.capacity,
        address=org.address,
        location=schemas.Point(lat=lat, lon=lon),
        classification=classification_out(classification_of(org, len(regs.hazmat))),
        representative=schemas.Person(full_name=representative.full_name, phone=representative.phone)
        if representative
        else None,
        hazmat=[schemas.HazmatIn.model_validate(hazmat_out(h).model_dump(exclude={"id"})) for h in regs.hazmat],
        features=[feature_out(f, la, lo) for f, la, lo in regs.features],
        kind_fields=domain.visible_kind_fields(org.kind, org.kind_fields or {}, "incident"),
    )


# ---------------------------------------------------------------- staff (FR-C-05)


def staff_scope(principal: Principal) -> Any:
    if principal.is_national:
        return True
    return Organization.gouvernorat_code == principal.gouvernorat_code


def in_scope(principal: Principal, org: Organization) -> bool:
    return principal.is_national or (
        org.gouvernorat_code is not None and principal.can_access_gouvernorat(org.gouvernorat_code)
    )


def _latest_certificate() -> Any:
    return (
        select(Certificate.org_id, Certificate.status, Certificate.valid_until)
        .order_by(Certificate.org_id, Certificate.created_at.desc())
        .ext(distinct_on(Certificate.org_id))
        .subquery("latest_certificate")
    )


@dataclass(frozen=True, slots=True)
class StaffOrgFilters:
    statuses: list[str]
    kinds: list[str]
    gouvernorat_code: int | None
    q: str | None
    has_hazmat: bool | None
    certificate: str | None


def _certificate_state(latest: Any) -> Any:
    return case(
        (latest.c.status.is_(None), "none"),
        (and_(latest.c.status == "approved", latest.c.valid_until < func.current_date()), "expired"),
        else_=latest.c.status,
    )


def _staff_query(principal: Principal) -> tuple[Select[Any], Any]:
    latest = _latest_certificate()
    query = (
        select(Organization, _LAT, _LON, _certificate_state(latest), latest.c.valid_until)
        .outerjoin(latest, latest.c.org_id == Organization.id)
        .where(staff_scope(principal))
    )
    return query, latest


async def staff_list(
    session: AsyncSession, principal: Principal, filters: StaffOrgFilters, limit: int, cursor: str | None
) -> tuple[list[schemas.StaffOrg], str | None]:
    query, latest = _staff_query(principal)
    if filters.statuses:
        query = query.where(Organization.status.in_(filters.statuses))
    if filters.kinds:
        query = query.where(Organization.kind.in_(filters.kinds))
    if filters.gouvernorat_code is not None:
        query = query.where(Organization.gouvernorat_code == filters.gouvernorat_code)
    if filters.q:
        pattern = "%" + filters.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(
            or_(Organization.name.ilike(pattern, escape="\\"), Organization.identifier.ilike(pattern, escape="\\"))
        )
    if filters.has_hazmat is not None:
        has = exists().where(Hazmat.org_id == Organization.id)
        query = query.where(has if filters.has_hazmat else ~has)
    if filters.certificate:
        query = query.where(_certificate_state(latest) == filters.certificate)
    name_key = func.lower(Organization.name)
    if cursor:
        try:
            raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
            last_name, last_id = raw.rsplit("|", 1)
            after = uuid.UUID(last_id)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc
        query = query.where(or_(name_key > last_name, and_(name_key == last_name, Organization.id > after)))
    rows = (await session.execute(query.order_by(name_key, Organization.id).limit(limit))).all()
    items = await staff_orgs(session, rows)
    next_cursor = None
    if len(rows) == limit:
        last = rows[-1][0]
        next_cursor = base64.urlsafe_b64encode(f"{last.name.lower()}|{last.id}".encode()).decode().rstrip("=")
    return items, next_cursor


async def staff_orgs(session: AsyncSession, rows: Sequence[Any]) -> list[schemas.StaffOrg]:
    ids = [row[0].id for row in rows]
    hazmat = await hazmat_counts(session, ids)
    alerts = await alerts_counts(session, ids)
    return [
        schemas.StaffOrg(
            id=org.id,
            name=org.name,
            kind=org.kind,
            status=org.status,
            identifier_type=org.identifier_type,
            identifier=org.identifier,
            gouvernorat_code=org.gouvernorat_code,
            capacity=org.capacity,
            location=schemas.Point(lat=float(lat), lon=float(lon)),
            classification=classification_out(classification_of(org, hazmat.get(org.id, 0))),
            kind_review=org.kind_review,
            hazmat_count=hazmat.get(org.id, 0),
            alerts_count=alerts.get(org.id, 0),
            certificate_status=cert_state,
            certificate_valid_until=valid_until,
            created_at=org.created_at,
        )
        for org, lat, lon, cert_state, valid_until in rows
    ]


async def staff_org(session: AsyncSession, principal: Principal, org_id: uuid.UUID) -> schemas.StaffOrg | None:
    query, _ = _staff_query(principal)
    rows = (await session.execute(query.where(Organization.id == org_id))).all()
    items = await staff_orgs(session, rows)
    return items[0] if items else None


async def org_event(session: AsyncSession, org_id: uuid.UUID) -> None:
    """Live update for the dashboard (scope filtered by gouvernorat in the hub)."""
    rows = (await session.execute(_national_query().where(Organization.id == org_id))).all()
    items = await staff_orgs(session, rows)
    if items:
        await emit(session, "org.updated", {"org": items[0].model_dump(mode="json")})


def _national_query() -> Select[Any]:
    latest = _latest_certificate()
    return select(Organization, _LAT, _LON, _certificate_state(latest), latest.c.valid_until).outerjoin(
        latest, latest.c.org_id == Organization.id
    )


async def staff_map(
    session: AsyncSession, principal: Principal, bbox: tuple[float, float, float, float] | None
) -> dict[str, Any]:
    query = select(Organization, _LAT, _LON).where(staff_scope(principal), Organization.status == OrgStatus.ACTIVE)
    if bbox is not None:
        envelope = func.ST_MakeEnvelope(*bbox, 4326)
        query = query.where(func.ST_Intersects(cast(Organization.location, Geometry), envelope))
    rows = (await session.execute(query.limit(5000))).all()
    hazmat = await hazmat_counts(session, [r[0].id for r in rows])
    features = []
    for org, lat, lon in rows:
        classification = classification_of(org, hazmat.get(org.id, 0))
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
                "properties": {
                    "id": str(org.id),
                    "name": org.name,
                    "kind": org.kind,
                    "capacity": org.capacity,
                    "hazmat_count": hazmat.get(org.id, 0),
                    "category": classification.category,
                    "family": classification.family,
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


async def review_org(session: AsyncSession, org: Organization, body: schemas.OrgReviewIn, actor: str) -> str:
    allowed_from, result = domain.REVIEW_TRANSITIONS[body.decision]
    if org.status != allowed_from:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    reason = body.reason.strip() if body.reason and body.reason.strip() else None
    if body.decision in ("reject", "suspend") and reason is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reason_required")
    previous = org.status
    if body.kind is not None:
        if body.decision != "approve":
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "kind_only_on_approval")
        if body.kind.value != org.kind:
            kept = domain.clean_kind_fields(body.kind, dict(org.kind_fields or {}))
            org.kind = body.kind.value
            org.kind_fields = kept if isinstance(kept, dict) else {}
        org.kind_review = False
    org.status = result.value
    org.review_reason = reason
    org.reviewed_by = actor
    org.reviewed_at = datetime.now(UTC)
    org.updated_at = org.reviewed_at
    await session.flush()
    return previous


async def kpis(session: AsyncSession, principal: Principal) -> tuple[int, int]:
    pending = await session.scalar(
        select(func.count()).where(staff_scope(principal), Organization.status == OrgStatus.PENDING_REVIEW)
    )
    submitted = await session.scalar(
        select(func.count())
        .select_from(Certificate)
        .join(Organization, Organization.id == Certificate.org_id)
        .where(staff_scope(principal), Certificate.status == "submitted")
    )
    return int(pending or 0), int(submitted or 0)


async def bump_version(session: AsyncSession, org_id: uuid.UUID) -> None:
    await session.execute(update(Organization).where(Organization.id == org_id).values(updated_at=func.now()))


async def delete_document(session: AsyncSession, doc: Document) -> list[str]:
    keys = list(await session.scalars(select(DocumentVersion.object_key).where(DocumentVersion.document_id == doc.id)))
    await session.execute(delete(Document).where(Document.id == doc.id))
    return keys
