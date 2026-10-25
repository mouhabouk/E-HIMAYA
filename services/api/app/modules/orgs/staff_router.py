"""Institutions hub of the dashboard (FR-C-05), contract phase 4 §9. Every query is restricted to the scope."""

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.core.storage import get_store
from app.modules.audit import service as audit
from app.modules.audit.service import actor_of
from app.modules.orgs import certificate, schemas, service
from app.modules.orgs.domain import OrgKind, OrgRole, OrgStatus
from app.modules.orgs.models import Certificate, Document, Organization
from app.modules.orgs.router import delete_objects, download_url
from app.modules.reports import service as reports
from app.modules.reports.schemas import StaffReportPage
from app.modules.reports.staff_router import READ_ROLES, _bbox

router = APIRouter(prefix="/api/v1/staff", tags=["staff-institutions"])

ORG_READ_ROLES = (*READ_ROLES, Role.ORG_AUDITOR)
OrgReader = Annotated[Principal, Depends(require_roles(*ORG_READ_ROLES))]
Auditor = Annotated[Principal, Depends(require_roles(Role.ORG_AUDITOR))]
Session = Annotated[AsyncSession, Depends(get_session)]
CertificateState = Literal["none", "draft", "submitted", "approved", "rejected", "revoked", "expired"]


def _csv[E: (OrgStatus, OrgKind)](raw: str | None, enum: type[E], code: str) -> list[str]:
    if not raw:
        return []
    try:
        return [enum(item.strip()).value for item in raw.split(",") if item.strip()]
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, code) from exc


async def _org_in_scope(
    session: AsyncSession, principal: Principal, org_id: uuid.UUID, *, lock: bool = False
) -> Organization:
    query = select(Organization).where(Organization.id == org_id)
    org = await session.scalar(query.with_for_update() if lock else query)
    # Out-of-scope institutions answer 404, so their existence is not disclosed.
    if org is None or not service.in_scope(principal, org):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "org_not_found")
    return org


@router.get("/orgs", response_model=schemas.StaffOrgPage)
async def list_orgs(
    principal: OrgReader,
    session: Session,
    status_: Annotated[str | None, Query(alias="status")] = None,
    kind: str | None = None,
    gouvernorat_code: int | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    has_hazmat: bool | None = None,
    certificate_: Annotated[CertificateState | None, Query(alias="certificate")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> schemas.StaffOrgPage:
    filters = service.StaffOrgFilters(
        statuses=_csv(status_, OrgStatus, "invalid_status"),
        kinds=_csv(kind, OrgKind, "invalid_kind"),
        gouvernorat_code=gouvernorat_code,
        q=q.strip() if q and q.strip() else None,
        has_hazmat=has_hazmat,
        certificate=certificate_,
    )
    items, next_cursor = await service.staff_list(session, principal, filters, limit, cursor)
    return schemas.StaffOrgPage(items=items, next_cursor=next_cursor)


@router.get("/orgs/map")
async def orgs_map(principal: OrgReader, session: Session, bbox: str | None = None) -> dict[str, Any]:
    """GeoJSON of the active institutions in scope (map layer «المؤسسات», FR-C-10)."""
    return await service.staff_map(session, principal, _bbox(bbox))


async def detail_of(session: AsyncSession, org: Organization) -> schemas.StaffOrgDetail:
    regs = await service.load_registers(session, org.id)
    on = service.today()
    return schemas.StaffOrgDetail(
        **(await service.card(session, org, regs, reader="auditor")),
        team=[service.team_out(m, on) for m in regs.team],
        hazmat=[service.hazmat_out(h) for h in regs.hazmat],
        equipment=[service.equipment_out(e, on) for e in regs.equipment],
        features=[service.feature_out(f, la, lo) for f, la, lo in regs.features],
        documents=[service.document_out(d, c, n) for d, c, n in regs.documents],
        members=[
            schemas.StaffMember(display_name=m.display_name, email=m.email, role=OrgRole(m.role))
            for m in await service.members(session, org.id)
        ],
        certificates=[certificate.certificate_out(c) for c in await certificate.certificates_of(session, org.id)],
    )


@router.get("/orgs/{org_id}", response_model=schemas.StaffOrgDetail)
async def get_org(principal: OrgReader, session: Session, org_id: uuid.UUID) -> schemas.StaffOrgDetail:
    org = await _org_in_scope(session, principal, org_id)
    detail = await detail_of(session, org)
    # NFR-06: the detail shows personal data (members, safety team) and is audited.
    await audit.record(session, actor=actor_of(principal), action="org.view", target=f"org:{org_id}")
    await session.commit()
    return detail


@router.get("/orgs/{org_id}/documents/{doc_id}/versions", response_model=list[schemas.DocumentVersionOut])
async def list_versions(
    principal: OrgReader, session: Session, org_id: uuid.UUID, doc_id: uuid.UUID
) -> list[schemas.DocumentVersionOut]:
    await _org_in_scope(session, principal, org_id)
    doc = await session.get(Document, doc_id)
    if doc is None or doc.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document_not_found")
    return [service.version_out(v) for v in await service.versions(session, doc_id)]


@router.get("/orgs/{org_id}/documents/{doc_id}/versions/{version}/download", response_model=schemas.DownloadOut)
async def download_version(
    principal: OrgReader,
    session: Session,
    org_id: uuid.UUID,
    doc_id: uuid.UUID,
    version: Annotated[int, Path(ge=1)],
) -> schemas.DownloadOut:
    await _org_in_scope(session, principal, org_id)
    url = await download_url(session, org_id, doc_id, version)
    await audit.record(
        session,
        actor=actor_of(principal),
        action="org.document_download",
        target=f"org:{org_id}",
        details={"document_id": str(doc_id), "version": version},
    )
    await session.commit()
    return url


@router.get("/orgs/{org_id}/certificates/{cert_id}/pdf", response_model=schemas.DownloadOut)
async def certificate_pdf(
    principal: OrgReader, session: Session, org_id: uuid.UUID, cert_id: uuid.UUID
) -> schemas.DownloadOut:
    await _org_in_scope(session, principal, org_id)
    cert = await certificate.owned_certificate(session, org_id, cert_id)
    return schemas.DownloadOut(url=get_store().presign_get(cert.pdf_object_key, content_type=certificate.PDF_TYPE))


@router.get("/orgs/{org_id}/reports", response_model=StaffReportPage)
async def org_reports(
    principal: OrgReader,
    session: Session,
    org_id: uuid.UUID,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> StaffReportPage:
    await _org_in_scope(session, principal, org_id)
    filters = reports.StaffFilters(
        statuses=[],
        categories=[],
        gouvernorat_code=None,
        since=None,
        until=None,
        bbox=None,
        q=None,
        organization_id=org_id,
    )
    items, next_cursor = await reports.staff_list(session, principal, filters, limit, cursor)
    return StaffReportPage(items=items, next_cursor=next_cursor)


@router.post("/orgs/{org_id}/review", response_model=schemas.StaffOrgDetail)
async def review_org(
    principal: Auditor, session: Session, org_id: uuid.UUID, body: schemas.OrgReviewIn
) -> schemas.StaffOrgDetail:
    org = await _org_in_scope(session, principal, org_id, lock=True)
    actor = actor_of(principal)
    previous = await service.review_org(session, org, body, actor)
    await audit.record(
        session,
        actor=actor,
        action="org.review",
        target=f"org:{org_id}",
        reason=org.review_reason,
        details={"decision": body.decision, "from": previous, "to": org.status, "kind": org.kind},
    )
    await service.org_event(session, org_id)
    await session.commit()
    return await detail_of(session, org)


# ---------------------------------------------------------------- certificates review queue


@router.get("/certificates", response_model=schemas.CertificateQueuePage)
async def certificate_queue(
    principal: OrgReader,
    session: Session,
    status_: Annotated[Literal["submitted", "approved", "rejected", "revoked"], Query(alias="status")] = "submitted",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> schemas.CertificateQueuePage:
    items, next_cursor = await certificate.queue(session, principal, status_, limit, cursor)
    return schemas.CertificateQueuePage(items=items, next_cursor=next_cursor)


@router.post("/certificates/{cert_id}/review", response_model=schemas.CertificateOut)
async def review_certificate(
    principal: Auditor, session: Session, cert_id: uuid.UUID, body: schemas.CertificateReviewIn
) -> schemas.CertificateOut:
    cert = await session.get(Certificate, cert_id, with_for_update=True)
    org = await session.get(Organization, cert.org_id) if cert is not None else None
    if cert is None or org is None or not service.in_scope(principal, org) or cert.status == "draft":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    actor = actor_of(principal)
    stale = await certificate.review(session, cert, body, actor)
    await audit.record(
        session,
        actor=actor,
        action="certificate.review",
        target=f"org:{org.id}",
        reason=cert.review_reason,
        details={"code": cert.code, "decision": body.decision, "valid_until": str(cert.valid_until or "")},
    )
    await certificate.certificate_event(session, cert)
    await service.org_event(session, org.id)
    await session.commit()
    await delete_objects(*stale)
    return certificate.certificate_out(cert)


@router.post("/certificates/{cert_id}/revoke", response_model=schemas.CertificateOut)
async def revoke_certificate(
    principal: Auditor, session: Session, cert_id: uuid.UUID, body: schemas.CertificateRevokeIn
) -> schemas.CertificateOut:
    """Revoke an approved certificate (phase 10 §4.1): the public verification answers ``valid: false`` at once."""
    cert = await session.get(Certificate, cert_id, with_for_update=True)
    org = await session.get(Organization, cert.org_id) if cert is not None else None
    if cert is None or org is None or not service.in_scope(principal, org) or cert.status == "draft":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    actor = actor_of(principal)
    stale = await certificate.revoke(session, cert, body.reason, actor)
    await audit.record(
        session,
        actor=actor,
        action="certificate.revoke",
        target=f"org:{org.id}",
        reason=cert.revoke_reason,
        details={"code": cert.code},
    )
    await certificate.certificate_event(session, cert)
    await service.org_event(session, org.id)
    await session.commit()
    await delete_objects(*stale)
    return certificate.certificate_out(cert)
