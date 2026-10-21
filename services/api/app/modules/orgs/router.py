"""Institution endpoints for the portal and the app (realm ``ehimaya-public``), contract phase 4 §1–§8."""

import uuid
from decimal import Decimal
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.ratelimit import enforce, opaque
from app.core.storage import get_store
from app.modules.audit import service as audit
from app.modules.orgs import certificate, domain, schemas, service
from app.modules.orgs.domain import OrgRole, OrgStatus
from app.modules.orgs.models import Document, Equipment, Hazmat, MapFeature, Organization, TeamMember
from app.modules.orgs.service import CurrentUser, PortalUser

log = structlog.get_logger()
router = APIRouter(prefix="/api/v1", tags=["institutions"])

Session = Annotated[AsyncSession, Depends(get_session)]
OrgId = Annotated[uuid.UUID, Path()]
CODE_PATTERN = r"^EHC-\d{2}-\d{2}-\d{6}$"
VERIFY_LIMIT, VERIFY_WINDOW_S = 30, 60
CREATE_LIMIT, CREATE_WINDOW_S = 10, 3600


async def _changed(session: AsyncSession, org: Organization, user: PortalUser, action: str, **details: Any) -> None:
    """A change to the institution: audit it, refresh its computed views and tell the dashboard."""
    await audit.record(session, actor=user.actor, action=action, target=f"org:{org.id}", details=details or None)
    await service.touch(session, org)
    await service.org_event(session, org.id)
    await session.commit()


async def delete_objects(*keys: str) -> None:
    """Best effort once the database no longer references them (an orphan object is harmless)."""
    if not keys:
        return
    try:
        await get_store().delete(*keys, *(f"{k}.info" for k in keys))
    except Exception:
        log.warning("orgs.object_delete_failed", count=len(keys))


# ---------------------------------------------------------------- institution card (§1)


@router.post("/orgs", response_model=schemas.OrgOut, status_code=status.HTTP_201_CREATED)
async def create_org(body: schemas.OrgIn, user: CurrentUser, session: Session) -> schemas.OrgOut:
    await enforce(f"org-create:{user.user_id}", CREATE_LIMIT, CREATE_WINDOW_S)
    org, member = await service.create_org(session, user, body)
    await _changed(session, org, user, "org.create", identifier=org.identifier)
    return await service.org_out(session, org, member)


@router.get("/orgs/mine", response_model=list[schemas.MyOrg])
async def my_orgs(user: CurrentUser, session: Session) -> list[schemas.MyOrg]:
    return await service.my_orgs(session, user)


@router.get("/orgs/{org_id}", response_model=schemas.OrgOut)
async def get_org(org_id: OrgId, user: CurrentUser, session: Session) -> schemas.OrgOut:
    org, member = await service.membership(session, user, org_id)
    await session.commit()
    return await service.org_out(session, org, member)


@router.put("/orgs/{org_id}", response_model=schemas.OrgOut)
async def update_org(org_id: OrgId, body: schemas.OrgUpdate, user: CurrentUser, session: Session) -> schemas.OrgOut:
    org, member = await service.membership(session, user, org_id, OrgRole.EDITOR, lock=True)
    back_to_review = await service.update_org(session, org, body)
    await _changed(session, org, user, "org.update", back_to_review=back_to_review)
    return await service.org_out(session, org, member)


@router.post("/orgs/{org_id}/resubmit", response_model=schemas.OrgOut)
async def resubmit(org_id: OrgId, user: CurrentUser, session: Session) -> schemas.OrgOut:
    org, member = await service.membership(session, user, org_id, OrgRole.ADMIN, lock=True)
    if org.status != OrgStatus.REJECTED:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    org.status = OrgStatus.PENDING_REVIEW.value
    await _changed(session, org, user, "org.resubmit")
    return await service.org_out(session, org, member)


# ---------------------------------------------------------------- members and invitations (§2)


@router.get("/orgs/{org_id}/members", response_model=list[schemas.MemberOut])
async def list_members(org_id: OrgId, user: CurrentUser, session: Session) -> list[schemas.MemberOut]:
    await service.membership(session, user, org_id)
    await session.commit()
    return [service.member_out(m) for m in await service.members(session, org_id)]


@router.put("/orgs/{org_id}/members/{user_id}", response_model=schemas.MemberOut)
async def set_member_role(
    org_id: OrgId, user_id: uuid.UUID, body: schemas.MemberRoleIn, user: CurrentUser, session: Session
) -> schemas.MemberOut:
    await service.membership(session, user, org_id, OrgRole.ADMIN, lock=True)
    target = await service.set_role(session, org_id, user_id, body.role)
    await audit.record(
        session,
        actor=user.actor,
        action="org.member_role",
        target=f"org:{org_id}",
        details={"user_id": str(user_id), "role": body.role.value},
    )
    await session.commit()
    return service.member_out(target)


@router.delete("/orgs/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(org_id: OrgId, user_id: uuid.UUID, user: CurrentUser, session: Session) -> Response:
    # An admin removes anyone; any member may leave.
    needed = OrgRole.MEMBER if user_id == user.user_id else OrgRole.ADMIN
    await service.membership(session, user, org_id, needed, lock=True)
    await service.remove_member(session, org_id, user_id)
    await audit.record(
        session, actor=user.actor, action="org.member_remove", target=f"org:{org_id}", details={"user_id": str(user_id)}
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/orgs/{org_id}/invitations", response_model=schemas.InvitationCreated, status_code=status.HTTP_201_CREATED
)
async def create_invitation(
    org_id: OrgId, body: schemas.InvitationIn, user: CurrentUser, session: Session
) -> schemas.InvitationCreated:
    org, _ = await service.membership(session, user, org_id, OrgRole.ADMIN, lock=True)
    created = await service.invite(session, org, user, body)
    await audit.record(
        session,
        actor=user.actor,
        action="org.invite",
        target=f"org:{org_id}",
        details={"invitation_id": str(created.id), "role": created.role.value},
    )
    await session.commit()
    return created


@router.get("/orgs/{org_id}/invitations", response_model=list[schemas.InvitationOut])
async def list_invitations(org_id: OrgId, user: CurrentUser, session: Session) -> list[schemas.InvitationOut]:
    await service.membership(session, user, org_id, OrgRole.ADMIN)
    await session.commit()
    return [service.invitation_out(i) for i in await service.pending_invitations(session, org_id)]


@router.delete("/orgs/{org_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(org_id: OrgId, invitation_id: uuid.UUID, user: CurrentUser, session: Session) -> Response:
    await service.membership(session, user, org_id, OrgRole.ADMIN)
    await service.revoke_invitation(session, org_id, invitation_id)
    await audit.record(
        session,
        actor=user.actor,
        action="org.invite_revoke",
        target=f"org:{org_id}",
        details={"invitation_id": str(invitation_id)},
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


Token = Annotated[str, Path(min_length=20, max_length=100)]


@router.get("/invitations/{token}", response_model=schemas.InvitationPreview)
async def preview_invitation(token: Token, user: CurrentUser, session: Session) -> schemas.InvitationPreview:
    invitation = await service.invitation_by_token(session, token)
    org = await session.get(Organization, invitation.org_id)
    assert org is not None
    return schemas.InvitationPreview(
        org_name=org.name, role=OrgRole(invitation.role), email=invitation.email, expires_at=invitation.expires_at
    )


@router.post("/invitations/{token}/accept", response_model=schemas.InvitationAccepted)
async def accept_invitation(token: Token, user: CurrentUser, session: Session) -> schemas.InvitationAccepted:
    await enforce(f"invite-accept:{user.user_id}", 20, 600)
    member = await service.accept_invitation(session, user, token)
    await audit.record(
        session,
        actor=user.actor,
        action="org.invite_accept",
        target=f"org:{member.org_id}",
        details={"role": member.role},
    )
    await session.commit()
    return schemas.InvitationAccepted(org_id=member.org_id, role=OrgRole(member.role))


# ---------------------------------------------------------------- safety team (§3)


@router.get("/orgs/{org_id}/team", response_model=list[schemas.TeamMemberOut])
async def list_team(org_id: OrgId, user: CurrentUser, session: Session) -> list[schemas.TeamMemberOut]:
    await service.membership(session, user, org_id)
    await session.commit()
    regs = await service.load_registers(session, org_id)
    on = service.today()
    return [service.team_out(m, on) for m in regs.team]


@router.post("/orgs/{org_id}/team", response_model=schemas.TeamMemberOut, status_code=status.HTTP_201_CREATED)
async def add_team_member(
    org_id: OrgId, body: schemas.TeamMemberIn, user: CurrentUser, session: Session
) -> schemas.TeamMemberOut:
    org, _ = await service.membership(session, user, org_id, OrgRole.EDITOR, lock=True)
    await service.check_representative(session, org_id, body)
    item = TeamMember(org_id=org_id, **service.team_values(body))
    session.add(item)
    await session.flush()
    await session.refresh(item)
    await _changed(session, org, user, "org.team_add", item_id=str(item.id))
    return service.team_out(item, service.today())


@router.put("/orgs/{org_id}/team/{item_id}", response_model=schemas.TeamMemberOut)
async def update_team_member(
    org_id: OrgId, item_id: uuid.UUID, body: schemas.TeamMemberIn, user: CurrentUser, session: Session
) -> schemas.TeamMemberOut:
    org, _ = await service.membership(session, user, org_id, OrgRole.EDITOR, lock=True)
    item = await service.owned(session, TeamMember, org_id, item_id)
    await service.check_representative(session, org_id, body, except_id=item_id)
    for key, value in service.team_values(body).items():
        setattr(item, key, value)
    item.updated_at = service.now()
    await _changed(session, org, user, "org.team_update", item_id=str(item_id))
    return service.team_out(item, service.today())


async def _delete_item(
    session: AsyncSession,
    user: PortalUser,
    org_id: uuid.UUID,
    model: type[Any],
    item_id: uuid.UUID,
    action: str,
) -> Response:
    org, _ = await service.membership(session, user, org_id, OrgRole.EDITOR, lock=True)
    item = await service.owned(session, model, org_id, item_id)
    await session.delete(item)
    await session.flush()
    await _changed(session, org, user, action, item_id=str(item_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/orgs/{org_id}/team/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team_member(org_id: OrgId, item_id: uuid.UUID, user: CurrentUser, session: Session) -> Response:
    return await _delete_item(session, user, org_id, TeamMember, item_id, "org.team_delete")


# ---------------------------------------------------------------- hazardous materials and equipment (§4)


def _hazmat_row(values: dict[str, Any]) -> dict[str, Any]:
    return {**values, "quantity": Decimal(str(values["quantity"]))}


@router.get("/orgs/{org_id}/hazmat", response_model=list[schemas.HazmatOut])
async def list_hazmat(org_id: OrgId, user: CurrentUser, session: Session) -> list[schemas.HazmatOut]:
    await service.membership(session, user, org_id)
    await session.commit()
    return [service.hazmat_out(h) for h in (await service.load_registers(session, org_id)).hazmat]


@router.post("/orgs/{org_id}/hazmat", response_model=schemas.HazmatOut, status_code=status.HTTP_201_CREATED)
async def add_hazmat(org_id: OrgId, body: schemas.HazmatIn, user: CurrentUser, session: Session) -> schemas.HazmatOut:
    org, _ = await service.membership(session, user, org_id, OrgRole.EDITOR, lock=True)
    item = Hazmat(org_id=org_id, **_hazmat_row(await service.hazmat_values(session, org_id, body)))
    session.add(item)
    await session.flush()
    await session.refresh(item)
    await _changed(session, org, user, "org.hazmat_add", item_id=str(item.id))
    return service.hazmat_out(item)


@router.put("/orgs/{org_id}/hazmat/{item_id}", response_model=schemas.HazmatOut)
async def update_hazmat(
    org_id: OrgId, item_id: uuid.UUID, body: schemas.HazmatIn, user: CurrentUser, session: Session
) -> schemas.HazmatOut:
    org, _ = await service.membership(session, user, org_id, OrgRole.EDITOR, lock=True)
    item = await service.owned(session, Hazmat, org_id, item_id)
    for key, value in _hazmat_row(await service.hazmat_values(session, org_id, body)).items():
        setattr(item, key, value)
    item.updated_at = service.now()
    await _changed(session, org, user, "org.hazmat_update", item_id=str(item_id))
    return service.hazmat_out(item)


@router.delete("/orgs/{org_id}/hazmat/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hazmat(org_id: OrgId, item_id: uuid.UUID, user: CurrentUser, session: Session) -> Response:
    return await _delete_item(session, user, org_id, Hazmat, item_id, "org.hazmat_delete")


@router.get("/orgs/{org_id}/equipment", response_model=list[schemas.EquipmentOut])
async def list_equipment(org_id: OrgId, user: CurrentUser, session: Session) -> list[schemas.EquipmentOut]:
    await service.membership(session, user, org_id)
    await session.commit()
    on = service.today()
    return [service.equipment_out(e, on) for e in (await service.load_registers(session, org_id)).equipment]


@router.post("/orgs/{org_id}/equipment", response_model=schemas.EquipmentOut, status_code=status.HTTP_201_CREATED)
async def add_equipment(
    org_id: OrgId, body: schemas.EquipmentIn, user: CurrentUser, session: Session
) -> schemas.EquipmentOut:
    org, _ = await service.membership(session, user, org_id, OrgRole.EDITOR, lock=True)
    item = Equipment(org_id=org_id, **body.model_dump())
    session.add(item)
    await session.flush()
    await session.refresh(item)
    await _changed(session, org, user, "org.equipment_add", item_id=str(item.id))
    return service.equipment_out(item, service.today())


@router.put("/orgs/{org_id}/equipment/{item_id}", response_model=schemas.EquipmentOut)
async def update_equipment(
    org_id: OrgId, item_id: uuid.UUID, body: schemas.EquipmentIn, user: CurrentUser, session: Session
) -> schemas.EquipmentOut:
    org, _ = await service.membership(session, user, org_id, OrgRole.EDITOR, lock=True)
    item = await service.owned(session, Equipment, org_id, item_id)
    for key, value in body.model_dump().items():
        setattr(item, key, value)
    item.updated_at = service.now()
    await _changed(session, org, user, "org.equipment_update", item_id=str(item_id))
    return service.equipment_out(item, service.today())


@router.delete("/orgs/{org_id}/equipment/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_equipment(org_id: OrgId, item_id: uuid.UUID, user: CurrentUser, session: Session) -> Response:
    return await _delete_item(session, user, org_id, Equipment, item_id, "org.equipment_delete")


# ---------------------------------------------------------------- map features (§5)


@router.get("/orgs/{org_id}/features", response_model=list[schemas.FeatureOut])
async def list_features(org_id: OrgId, user: CurrentUser, session: Session) -> list[schemas.FeatureOut]:
    await service.membership(session, user, org_id)
    await session.commit()
    return [service.feature_out(f, la, lo) for f, la, lo in (await service.load_registers(session, org_id)).features]


@router.post("/orgs/{org_id}/features", response_model=schemas.FeatureOut, status_code=status.HTTP_201_CREATED)
async def add_feature(
    org_id: OrgId, body: schemas.FeatureIn, user: CurrentUser, session: Session
) -> schemas.FeatureOut:
    org, _ = await service.membership(session, user, org_id, OrgRole.EDITOR, lock=True)
    if await service.feature_count(session, org_id) >= domain.MAX_FEATURES:
        raise HTTPException(status.HTTP_409_CONFLICT, "too_many_features")
    item = MapFeature(org_id=org_id, **await service.feature_values(session, org, body))
    session.add(item)
    await session.flush()
    await _changed(session, org, user, "org.feature_add", item_id=str(item.id))
    return service.feature_out(item, body.location.lat, body.location.lon)


@router.put("/orgs/{org_id}/features/{item_id}", response_model=schemas.FeatureOut)
async def update_feature(
    org_id: OrgId, item_id: uuid.UUID, body: schemas.FeatureIn, user: CurrentUser, session: Session
) -> schemas.FeatureOut:
    org, _ = await service.membership(session, user, org_id, OrgRole.EDITOR, lock=True)
    item = await service.owned(session, MapFeature, org_id, item_id)
    for key, value in (await service.feature_values(session, org, body)).items():
        setattr(item, key, value)
    await session.flush()
    await _changed(session, org, user, "org.feature_update", item_id=str(item_id))
    return service.feature_out(item, body.location.lat, body.location.lon)


@router.delete("/orgs/{org_id}/features/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feature(org_id: OrgId, item_id: uuid.UUID, user: CurrentUser, session: Session) -> Response:
    return await _delete_item(session, user, org_id, MapFeature, item_id, "org.feature_delete")


# ---------------------------------------------------------------- documents (§6)


@router.get("/orgs/{org_id}/documents", response_model=list[schemas.DocumentOut])
async def list_documents(org_id: OrgId, user: CurrentUser, session: Session) -> list[schemas.DocumentOut]:
    await service.membership(session, user, org_id)
    await session.commit()
    return [service.document_out(d, c, n) for d, c, n in await service.documents_of(session, org_id)]


async def _document_view(session: AsyncSession, doc: Document) -> schemas.DocumentOut:
    found = next(row for row in await service.documents_of(session, doc.org_id) if row[0].id == doc.id)
    return service.document_out(*found)


@router.post("/orgs/{org_id}/documents", response_model=schemas.DocumentOut, status_code=status.HTTP_201_CREATED)
async def create_document(
    org_id: OrgId, body: schemas.DocumentIn, user: CurrentUser, session: Session
) -> schemas.DocumentOut:
    org, _ = await service.membership(session, user, org_id, OrgRole.EDITOR, lock=True)
    doc = Document(org_id=org_id, kind=body.kind, title=body.title.strip())
    session.add(doc)
    await session.flush()
    await session.refresh(doc)
    await _changed(session, org, user, "org.document_add", document_id=str(doc.id))
    return service.document_out(doc, None, 0)


@router.put("/orgs/{org_id}/documents/{doc_id}", response_model=schemas.DocumentOut)
async def rename_document(
    org_id: OrgId, doc_id: uuid.UUID, body: schemas.DocumentTitleIn, user: CurrentUser, session: Session
) -> schemas.DocumentOut:
    org, _ = await service.membership(session, user, org_id, OrgRole.EDITOR, lock=True)
    doc = await service.owned(session, Document, org_id, doc_id)
    doc.title = body.title.strip()
    doc.updated_at = service.now()
    await _changed(session, org, user, "org.document_rename", document_id=str(doc_id))
    return await _document_view(session, doc)


@router.delete("/orgs/{org_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(org_id: OrgId, doc_id: uuid.UUID, user: CurrentUser, session: Session) -> Response:
    org, _ = await service.membership(session, user, org_id, OrgRole.ADMIN, lock=True)
    doc = await service.owned(session, Document, org_id, doc_id)
    if await service.document_in_use(session, doc_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "document_in_use")
    keys = await service.delete_document(session, doc)
    await _changed(session, org, user, "org.document_delete", document_id=str(doc_id), kind=doc.kind)
    await delete_objects(*keys)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/orgs/{org_id}/documents/{doc_id}/versions", response_model=list[schemas.DocumentVersionOut])
async def list_versions(
    org_id: OrgId, doc_id: uuid.UUID, user: CurrentUser, session: Session
) -> list[schemas.DocumentVersionOut]:
    await service.membership(session, user, org_id)
    await session.commit()
    doc = await session.get(Document, doc_id)
    if doc is None or doc.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document_not_found")
    return [service.version_out(v) for v in await service.versions(session, doc_id)]


async def download_url(
    session: AsyncSession, org_id: uuid.UUID, doc_id: uuid.UUID, version: int
) -> schemas.DownloadOut:
    doc = await session.get(Document, doc_id)
    if doc is None or doc.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document_not_found")
    found = await service.stored_version(session, doc_id, version)
    # The type is the one declared at upload: always a download, never rendered inline by the browser (A7).
    url = get_store().presign_get(
        found.object_key, content_type=found.content_type, disposition=f'attachment; filename="{found.id}"'
    )
    return schemas.DownloadOut(url=url)


@router.get("/orgs/{org_id}/documents/{doc_id}/versions/{version}/download", response_model=schemas.DownloadOut)
async def download_version(
    org_id: OrgId, doc_id: uuid.UUID, version: Annotated[int, Path(ge=1)], user: CurrentUser, session: Session
) -> schemas.DownloadOut:
    await service.membership(session, user, org_id)
    await session.commit()
    return await download_url(session, org_id, doc_id, version)


# ---------------------------------------------------------------- certificate (§7)


@router.post("/orgs/{org_id}/certificate", response_model=schemas.CertificateOut, status_code=status.HTTP_201_CREATED)
async def generate_certificate(org_id: OrgId, user: CurrentUser, session: Session) -> schemas.CertificateOut:
    org, _ = await service.membership(session, user, org_id, OrgRole.EDITOR, lock=True)
    await enforce(f"certificate:{org_id}", 20, 3600)  # rendering a PDF is costly
    cert, stale = await certificate.generate_draft(session, org, user)
    await audit.record(
        session,
        actor=user.actor,
        action="certificate.draft",
        target=f"org:{org_id}",
        details={"code": cert.code, "fingerprint": cert.fingerprint},
    )
    await session.commit()
    await delete_objects(*stale)
    return certificate.certificate_out(cert)


@router.get("/orgs/{org_id}/certificates", response_model=list[schemas.CertificateOut])
async def list_certificates(org_id: OrgId, user: CurrentUser, session: Session) -> list[schemas.CertificateOut]:
    await service.membership(session, user, org_id)
    await session.commit()
    return [certificate.certificate_out(c) for c in await certificate.certificates_of(session, org_id)]


@router.get("/orgs/{org_id}/certificates/{cert_id}/pdf", response_model=schemas.DownloadOut)
async def certificate_pdf(
    org_id: OrgId, cert_id: uuid.UUID, user: CurrentUser, session: Session
) -> schemas.DownloadOut:
    await service.membership(session, user, org_id)
    await session.commit()
    cert = await certificate.owned_certificate(session, org_id, cert_id)
    return schemas.DownloadOut(url=get_store().presign_get(cert.pdf_object_key, content_type=certificate.PDF_TYPE))


@router.post("/orgs/{org_id}/certificates/{cert_id}/submit", response_model=schemas.CertificateOut)
async def submit_certificate(
    org_id: OrgId, cert_id: uuid.UUID, user: CurrentUser, session: Session
) -> schemas.CertificateOut:
    org, _ = await service.membership(session, user, org_id, OrgRole.ADMIN, lock=True)
    cert = await certificate.owned_certificate(session, org_id, cert_id, lock=True)
    await certificate.submit(session, org, cert, user)
    await audit.record(
        session, actor=user.actor, action="certificate.submit", target=f"org:{org_id}", details={"code": cert.code}
    )
    await certificate.certificate_event(session, cert)
    await service.org_event(session, org_id)
    await session.commit()
    return certificate.certificate_out(cert)


@router.get("/public/certificate-key", response_model=schemas.SigningKeyOut, tags=["public"])
async def signing_key() -> schemas.SigningKeyOut:
    """Public key that signs approved certificates, for independent verification."""
    current = certificate.current_key_id()
    keys = {key_id: certificate.b64(public) for key_id, public in certificate.known_public_keys().items()}
    return schemas.SigningKeyOut(
        algorithm="Ed25519",
        public_key=keys.get(current) if current else None,
        signed_message=certificate.SIGNED_MESSAGE,
        key_id=current,
        previous_keys={key_id: raw for key_id, raw in keys.items() if key_id != current},
        disclaimer=certificate.DISCLAIMER,
    )


@router.get("/public/certificates/{code}", response_model=schemas.PublicCertificate, tags=["public"])
async def verify_certificate(
    request: Request, session: Session, code: Annotated[str, Path(pattern=CODE_PATTERN)]
) -> schemas.PublicCertificate:
    client = request.client.host if request.client else "unknown"
    await enforce(f"verify:{opaque(client)}", VERIFY_LIMIT, VERIFY_WINDOW_S)
    found = await certificate.public_view(session, code)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return found


# ---------------------------------------------------------------- reports of the institution (§8)


@router.get("/orgs/{org_id}/reports", response_model=schemas.OrgReportPage)
async def org_reports(
    org_id: OrgId,
    user: CurrentUser,
    session: Session,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> schemas.OrgReportPage:
    await service.membership(session, user, org_id)
    await session.commit()
    items, next_cursor = await service.org_reports(session, org_id, limit, cursor)
    return schemas.OrgReportPage(items=items, next_cursor=next_cursor)


@router.get("/orgs/{org_id}/summary", response_model=schemas.OrgSummary)
async def org_summary(org_id: OrgId, user: CurrentUser, session: Session) -> schemas.OrgSummary:
    org, _ = await service.membership(session, user, org_id)
    await session.commit()
    return await service.summary(session, org)
