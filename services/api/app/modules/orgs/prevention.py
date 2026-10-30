"""Prevention certificate (F-POR-08) and the institution's reports (F-APP-132), phase P3b.

docs/phase-p3/design-prevention.md:

* A visit is requested by the institution or scheduled by the Office, inspected on site with a grid built from the
  institution's declaration, then decided: approved, approved with reservations and deadlines, or refused with a reason.
* The comparison report (declared against found) is computed by the server and kept with the inspection.
* An approval issues a prevention certificate in the certificates table (``kind = 'prevention'``, code ``EHP-…``),
  signed like the safety certificate, so verification, revocation, the counter and stamps work for it too. Its text
  and validity are a model [SIM] until the Office provides them.
* The visit report (PDF) is rendered at the inspection and again at the decision.
"""

import base64
import hashlib
import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

import segno
from fastapi import HTTPException, status
from sqlalchemy import and_, extract, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import Principal
from app.core.storage import get_store
from app.modules.orgs import certificate, domain, schemas, service
from app.modules.orgs.certificate import TUNIS_TZ, _e, _pair
from app.modules.orgs.models import (
    Activity,
    Certificate,
    CertificateStamp,
    Maintenance,
    Member,
    Organization,
    PreventionPhoto,
    PreventionReservation,
    PreventionVisit,
    TeamMember,
)
from app.modules.settings import service as settings

PDF_TYPE = certificate.PDF_TYPE
SIGNATURE_TYPE = "image/png"
SIGNATURE_MAX_BYTES = 200_000


# ---------------------------------------------------------------- outputs


def reservation_out(item: PreventionReservation, on: date) -> schemas.ReservationOut:
    return schemas.ReservationOut(
        id=item.id,
        visit_id=item.visit_id,
        item_key=item.item_key,
        text=item.text,
        due_on=item.due_on,
        state=domain.reservation_state(item.due_on, item.responded_at is not None, item.lifted_at is not None, on),
        response_note=item.response_note,
        responded_by_name=item.responded_by_name,
        responded_at=item.responded_at,
        lifted_by_name=item.lifted_by_name,
        lift_note=item.lift_note,
        lifted_at=item.lifted_at,
    )


async def _reservations(
    session: AsyncSession, visit_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[PreventionReservation]]:
    found: dict[uuid.UUID, list[PreventionReservation]] = {i: [] for i in visit_ids}
    if visit_ids:
        rows = await session.scalars(
            select(PreventionReservation)
            .where(PreventionReservation.visit_id.in_(visit_ids))
            .order_by(PreventionReservation.due_on, PreventionReservation.created_at)
        )
        for item in rows:
            found[item.visit_id].append(item)
    return found


async def _certificates(session: AsyncSession, visit_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Certificate]:
    if not visit_ids:
        return {}
    rows = await session.scalars(
        select(Certificate).where(Certificate.kind == "prevention", Certificate.visit_id.in_(visit_ids))
    )
    return {c.visit_id: c for c in rows if c.visit_id is not None}


async def visit_views(
    session: AsyncSession, org: Organization, visits: Sequence[PreventionVisit]
) -> list[schemas.VisitOut]:
    """The visits with their reservations and certificate; the current certificate with its comparison."""
    ids = [v.id for v in visits]
    reservations = await _reservations(session, ids)
    certs = await _certificates(session, ids)
    stamps = await certificate.stamps_of(session, [c.id for c in certs.values()])
    on = service.today()
    out = []
    for visit in visits:
        cert = certs.get(visit.id)
        cert_out = None
        if cert is not None:
            changes = await certificate.changes_of(session, org, cert) if certificate.is_current(cert) else None
            cert_out = certificate.certificate_out(cert, changes=changes, stamps=stamps[cert.id])
        out.append(visit_out(visit, reservations[visit.id], cert_out, on))
    return out


def visit_out(
    visit: PreventionVisit,
    reservations: Sequence[PreventionReservation],
    cert: schemas.CertificateOut | None,
    on: date,
) -> schemas.VisitOut:
    return schemas.VisitOut(
        id=visit.id,
        org_id=visit.org_id,
        origin=visit.origin,
        status=visit.status,
        request_note=visit.request_note,
        requested_by_name=visit.requested_by_name,
        requested_at=visit.requested_at,
        scheduled_on=visit.scheduled_on,
        inspector_name=visit.inspector_name,
        inspected_on=visit.inspected_on,
        attendees=visit.attendees,
        comparison=schemas.ComparisonReport.model_validate(visit.comparison) if visit.comparison else None,
        decision=visit.decision,
        decision_reason=visit.decision_reason,
        decided_by_name=visit.decided_by_name,
        decided_at=visit.decided_at,
        certificate=cert,
        reservations=[reservation_out(r, on) for r in reservations],
        has_report=visit.report_object_key is not None,
        cancel_reason=visit.cancel_reason,
        cancelled_at=visit.cancelled_at,
        created_at=visit.created_at,
    )


async def visits_of(session: AsyncSession, org_id: uuid.UUID) -> list[PreventionVisit]:
    return list(
        await session.scalars(
            select(PreventionVisit)
            .where(PreventionVisit.org_id == org_id)
            .order_by(PreventionVisit.created_at.desc(), PreventionVisit.id.desc())
        )
    )


async def org_visits(session: AsyncSession, org: Organization) -> list[schemas.VisitOut]:
    return await visit_views(session, org, await visits_of(session, org.id))


def checklist_out(declared: dict[str, Any]) -> list[schemas.ChecklistItemOut]:
    return [
        schemas.ChecklistItemOut(key=i.key, section=i.section, declared=i.declared)
        for i in domain.prevention_checklist(declared)
    ]


async def photos_of(session: AsyncSession, visit_id: uuid.UUID) -> list[PreventionPhoto]:
    rows = await session.scalars(
        select(PreventionPhoto).where(PreventionPhoto.visit_id == visit_id).order_by(PreventionPhoto.created_at)
    )
    return list(rows)


def _link(key: str | None, content_type: str) -> str | None:
    return get_store().presign_get(key, expires_s=600, content_type=content_type) if key else None


def photo_out(photo: PreventionPhoto) -> schemas.VisitPhotoOut:
    return schemas.VisitPhotoOut(
        id=photo.id,
        item_key=photo.item_key,
        content_type=photo.content_type,
        bytes=photo.bytes,
        created_by_name=photo.created_by_name,
        device_at=photo.device_at,
        created_at=photo.created_at,
        url=_link(photo.object_key, photo.content_type),
    )


def signatures_out(visit: PreventionVisit) -> schemas.VisitSignatures | None:
    if visit.inspector_signature_key is None and visit.representative_signature_key is None:
        return None
    return schemas.VisitSignatures(
        inspector_name=visit.inspected_by_name,
        inspector_url=_link(visit.inspector_signature_key, SIGNATURE_TYPE),
        representative_name=visit.representative_name,
        representative_role=visit.representative_role,
        representative_url=_link(visit.representative_signature_key, SIGNATURE_TYPE),
    )


async def staff_view(session: AsyncSession, visit: PreventionVisit, org: Organization) -> schemas.StaffVisit:
    (out,) = await visit_views(session, org, [visit])
    checklist: list[schemas.ChecklistItemOut] = []
    if visit.status in domain.OPEN_VISIT_STATUSES:
        # Before the decision, the grid follows the declaration as it is today (a new inspection re-reads it).
        checklist = checklist_out(await certificate.snapshot_of(session, org))
    return schemas.StaffVisit(
        **out.model_dump(),
        org_name=org.name,
        org_kind=org.kind,
        org_status=org.status,
        gouvernorat_code=org.gouvernorat_code,
        checklist=checklist,
        inspector_on_phone=visit.inspector_subject is not None,
        photos=[photo_out(p) for p in await photos_of(session, visit.id)],
        signatures=signatures_out(visit),
    )


# ---------------------------------------------------------------- staff queue


async def staff_queue(
    session: AsyncSession, principal: Principal, statuses: Sequence[str], limit: int, cursor: str | None
) -> tuple[list[schemas.StaffVisit], str | None]:
    query = (
        select(PreventionVisit, Organization)
        .join(Organization, Organization.id == PreventionVisit.org_id)
        .where(service.staff_scope(principal))
    )
    if statuses:
        query = query.where(PreventionVisit.status.in_(statuses))
    if cursor:
        at, last_id = service.decode_cursor(cursor)
        query = query.where(
            or_(
                PreventionVisit.created_at < at,
                and_(PreventionVisit.created_at == at, PreventionVisit.id < last_id),
            )
        )
    rows = (
        await session.execute(query.order_by(PreventionVisit.created_at.desc(), PreventionVisit.id.desc()).limit(limit))
    ).all()
    visits = [v for v, _ in rows]
    reservations = await _reservations(session, [v.id for v in visits])
    certs = await _certificates(session, [v.id for v in visits])
    on = service.today()
    items = [
        schemas.StaffVisit(
            **visit_out(
                visit,
                reservations[visit.id],
                certificate.certificate_out(certs[visit.id]) if visit.id in certs else None,
                on,
            ).model_dump(),
            org_name=org.name,
            org_kind=org.kind,
            org_status=org.status,
            gouvernorat_code=org.gouvernorat_code,
        )
        for visit, org in rows
    ]
    next_cursor = service.encode_cursor(rows[-1][0].created_at, rows[-1][0].id) if len(rows) == limit else None
    return items, next_cursor


async def scoped_visit(
    session: AsyncSession, principal: Principal, visit_id: uuid.UUID, *, lock: bool = False
) -> tuple[PreventionVisit, Organization]:
    query = select(PreventionVisit).where(PreventionVisit.id == visit_id)
    visit = await session.scalar(query.with_for_update() if lock else query)
    org = await session.get(Organization, visit.org_id) if visit is not None else None
    if visit is None or org is None or not service.in_scope(principal, org):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return visit, org


async def scoped_reservation(
    session: AsyncSession, principal: Principal, reservation_id: uuid.UUID
) -> tuple[PreventionReservation, Organization]:
    item = await session.get(PreventionReservation, reservation_id, with_for_update=True)
    org = await session.get(Organization, item.org_id) if item is not None else None
    if item is None or org is None or not service.in_scope(principal, org):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return item, org


# ---------------------------------------------------------------- lifecycle


async def _open_visit(session: AsyncSession, org_id: uuid.UUID) -> PreventionVisit | None:
    return await session.scalar(
        select(PreventionVisit).where(
            PreventionVisit.org_id == org_id, PreventionVisit.status.in_(domain.OPEN_VISIT_STATUSES)
        )
    )


def _check_scheduled_on(day: date) -> None:
    today = service.today()
    if not (today <= day <= domain.add_months(today, domain.RESERVATION_MAX_MONTHS)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_scheduled_on")


def _clean(text: str | None) -> str | None:
    return text.strip() if text and text.strip() else None


async def request_visit(
    session: AsyncSession, org: Organization, user: service.PortalUser, note: str | None
) -> PreventionVisit:
    service.require_active(org)
    if await _open_visit(session, org.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "visit_open")
    visit = PreventionVisit(
        id=uuid.uuid4(),
        org_id=org.id,
        origin="request",
        status="requested",
        request_note=_clean(note),
        requested_by=user.user_id,
        requested_by_name=user.display_name,
        requested_at=datetime.now(UTC),
    )
    session.add(visit)
    await session.flush()
    await session.refresh(visit)
    return visit


async def schedule_new(
    session: AsyncSession, org: Organization, body: schemas.VisitScheduleIn, actor: str
) -> PreventionVisit:
    service.require_active(org)
    if await _open_visit(session, org.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "visit_open")
    _check_scheduled_on(body.scheduled_on)
    visit = PreventionVisit(id=uuid.uuid4(), org_id=org.id, origin="scheduled", status="scheduled")
    _set_schedule(visit, body, actor)
    session.add(visit)
    await session.flush()
    await session.refresh(visit)
    return visit


def _set_schedule(visit: PreventionVisit, body: schemas.VisitScheduleIn, actor: str) -> None:
    visit.status = "scheduled"
    visit.scheduled_on = body.scheduled_on
    name = _clean(body.inspector_name)
    if name != visit.inspector_name:
        # Another inspector named by the Office: the visit leaves the phone that had taken it (P4c).
        visit.inspector_subject = None
    visit.inspector_name = name
    visit.scheduled_by = actor
    visit.scheduled_at = datetime.now(UTC)


async def schedule(session: AsyncSession, visit: PreventionVisit, body: schemas.VisitScheduleIn, actor: str) -> None:
    """Schedule a requested visit, or move a scheduled one."""
    if visit.status not in ("requested", "scheduled"):
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    _check_scheduled_on(body.scheduled_on)
    _set_schedule(visit, body, actor)
    await session.flush()


def _findings(items: Sequence[schemas.InspectionItemIn], keys: set[str]) -> dict[str, domain.Finding]:
    findings: dict[str, domain.Finding] = {}
    for item in items:
        if item.key not in keys:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown_item")
        observed, note = _clean(item.observed), _clean(item.note)
        if item.result == "nonconform" and observed is None and note is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "finding_detail_required")
        findings[item.key] = domain.Finding(item.result, observed, note)
    return findings


async def inspect(
    session: AsyncSession,
    visit: PreventionVisit,
    org: Organization,
    body: schemas.InspectionIn,
    actor: str,
    name: str | None,
) -> list[str]:
    """Record the inspection and compute the comparison report. Returns the object keys to delete after commit."""
    if visit.status not in ("scheduled", "inspected"):
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    if body.inspected_on > service.today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_inspected_on")
    declared = await certificate.snapshot_of(session, org)
    findings = _findings(body.items, {i.key for i in domain.prevention_checklist(declared)})
    current = await certificate.current_of(session, org.id)
    changes = domain.certificate_changes(current.snapshot, declared) if current is not None else []
    visit.status = "inspected"
    visit.inspected_on = body.inspected_on
    visit.attendees = _clean(body.attendees)
    visit.inspected_by = actor
    visit.inspected_by_name = name
    visit.declared = declared
    visit.comparison = domain.comparison_report(declared, findings, changes)
    stale = await store_report(session, visit, org)
    await session.flush()
    return stale


def _check_reservations(body: schemas.VisitDecisionIn, keys: set[str]) -> None:
    if body.decision != "approved_with_reservations":
        if body.reservations:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reservations_not_allowed")
        return
    if not body.reservations:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reservations_required")
    today = service.today()
    latest = domain.add_months(today, domain.RESERVATION_MAX_MONTHS)
    for item in body.reservations:
        if not item.text.strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reservation_text_required")
        if not (today < item.due_on <= latest):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_due_on")
        if item.item_key is not None and item.item_key not in keys:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown_item")


async def decide(
    session: AsyncSession,
    visit: PreventionVisit,
    org: Organization,
    body: schemas.VisitDecisionIn,
    actor: str,
    name: str | None,
) -> tuple[Certificate | None, list[str]]:
    """Decide an inspected visit; an approval issues the prevention certificate. Returns it and the object keys to
    delete after commit."""
    if visit.status != "inspected" or visit.comparison is None or visit.declared is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    reason = _clean(body.reason)
    if body.decision == "refused" and reason is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reason_required")
    _check_reservations(body, {item["key"] for item in visit.comparison["items"]})
    now = datetime.now(UTC)
    issued: Certificate | None = None
    if body.decision != "refused":
        valid_until = certificate.check_valid_until(body.valid_until)
        service.require_active(org)
        issued = await _issue(session, visit, org, body, valid_until, actor, now)
    for item in body.reservations:
        session.add(
            PreventionReservation(
                id=uuid.uuid4(),
                visit_id=visit.id,
                org_id=org.id,
                item_key=item.item_key,
                text=item.text.strip(),
                due_on=item.due_on,
            )
        )
    visit.status = "decided"
    visit.decision = body.decision
    visit.decision_reason = reason
    visit.decided_by = actor
    visit.decided_by_name = name
    visit.decided_at = now
    await session.flush()
    stale = await store_report(session, visit, org)
    await session.flush()
    return issued, stale


async def _issue(
    session: AsyncSession,
    visit: PreventionVisit,
    org: Organization,
    body: schemas.VisitDecisionIn,
    valid_until: date,
    actor: str,
    now: datetime,
) -> Certificate:
    assert visit.declared is not None and visit.comparison is not None
    key = certificate._private_key()
    if key is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "signing_key_missing")
    snapshot = {
        **visit.declared,
        "generated_on": service.today().isoformat(),
        "prevention": {
            "visit_id": str(visit.id),
            "inspected_on": visit.inspected_on.isoformat() if visit.inspected_on else None,
            "inspector_name": visit.inspector_name,
            "decision": body.decision,
            "reservations": [{"text": r.text.strip(), "due_on": r.due_on.isoformat()} for r in body.reservations],
            "conform": visit.comparison["conform"],
            "nonconform": visit.comparison["nonconform"],
            "not_checked": visit.comparison["not_checked"],
        },
    }
    cert = Certificate(
        id=uuid.uuid4(),
        org_id=org.id,
        kind="prevention",
        visit_id=visit.id,
        code=await certificate.next_code(session, org.gouvernorat_code, "EHP"),
        status="approved",
        snapshot=snapshot,
        fingerprint=certificate.fingerprint_of(snapshot),
        created_by=None,
        reviewed_by=actor,
        reviewed_at=now,
        valid_until=valid_until,
    )
    cert.signature = key.sign(certificate.signed_message(cert.code, cert.fingerprint, valid_until))
    cert.key_id = certificate.key_id_of(key.public_key())
    await certificate._store_pdf(cert, "approved")
    session.add(cert)
    await session.flush()
    await session.execute(
        update(Certificate)
        .where(
            Certificate.org_id == org.id,
            Certificate.kind == "prevention",
            Certificate.id != cert.id,
            Certificate.status == "approved",
            Certificate.superseded_by.is_(None),
        )
        .values(superseded_by=cert.id)
    )
    await session.refresh(cert)
    return cert


async def cancel(visit: PreventionVisit, actor: str, reason: str | None, *, by_office: bool) -> None:
    """The institution withdraws its request; the Office cancels a requested or scheduled visit, with a reason."""
    allowed = ("requested", "scheduled") if by_office else ("requested",)
    if visit.status not in allowed:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    reason = _clean(reason)
    if by_office and reason is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reason_required")
    visit.status = "cancelled"
    visit.cancel_reason = reason
    visit.cancelled_by = actor
    visit.cancelled_at = datetime.now(UTC)


def respond(item: PreventionReservation, user: service.PortalUser, note: str) -> None:
    if item.lifted_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "reservation_lifted")
    text = _clean(note)
    if text is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "note_required")
    item.response_note = text
    item.responded_by_name = user.display_name
    item.responded_at = datetime.now(UTC)


def lift(item: PreventionReservation, actor: str, name: str | None, note: str | None) -> None:
    if item.lifted_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "reservation_lifted")
    item.lifted_by = actor
    item.lifted_by_name = name
    item.lift_note = _clean(note)
    item.lifted_at = datetime.now(UTC)


async def notify_admins(session: AsyncSession, org: Organization, visit: PreventionVisit, what: str) -> None:
    """E-mail the institution's admins that a visit is scheduled (``scheduled``) or decided (``decided``)."""
    from app.modules.notify import outbox, templates

    admins = await session.scalars(
        select(Member.email).where(Member.org_id == org.id, Member.role == "admin", Member.email.is_not(None))
    )
    values: dict[str, object] = {
        "org": org.name,
        "day": visit.scheduled_on.isoformat() if visit.scheduled_on else "",
        "link": f"{get_settings().portal_public_url}/orgs/{org.id}/prevention",
    }
    if what == "scheduled":
        subject, body = templates.VISIT_SCHEDULED_SUBJECT, templates.VISIT_SCHEDULED_BODY
    else:
        words = templates.DECISION_WORDS[visit.decision or "refused"]
        values |= {f"decision_{lang}": words[lang] for lang in ("ar", "fr", "en")}
        subject, body = templates.VISIT_DECIDED_SUBJECT, templates.VISIT_DECIDED_BODY
    text = templates.multilingual(templates.fill(body, **values))
    for address in admins:
        if address:
            outbox.email(session, address, subject["ar"].format(**values), text)


# ---------------------------------------------------------------- alerts


async def prevention_alerts(session: AsyncSession, org_id: uuid.UUID, on: date) -> list[schemas.Alert]:
    """A visit to come, and reservations due within 14 days or overdue."""
    alerts: list[schemas.Alert] = []
    visit = await session.scalar(
        select(PreventionVisit).where(
            PreventionVisit.org_id == org_id, PreventionVisit.status == "scheduled", PreventionVisit.scheduled_on >= on
        )
    )
    if visit is not None:
        alerts.append(schemas.Alert(kind="visit_scheduled", ref=visit.id, since=visit.scheduled_on))
    soon = await settings.threshold(session, "orgs.reservation_due_soon_days")
    rows = await session.scalars(
        select(PreventionReservation)
        .where(
            PreventionReservation.org_id == org_id,
            PreventionReservation.lifted_at.is_(None),
            PreventionReservation.due_on <= on + timedelta(days=soon),
        )
        .order_by(PreventionReservation.due_on)
    )
    for item in rows:
        kind = "reservation_overdue" if item.due_on < on else "reservation_due_soon"
        alerts.append(schemas.Alert(kind=kind, ref=item.id, since=item.due_on))
    return alerts


# ---------------------------------------------------------------- PDFs

_ITEM = {
    "building.capacity": ("طاقة الاستيعاب", "Capacité d'accueil"),
    "building.floors": ("عدد الطوابق", "Nombre d'étages"),
    "building.height_m": ("الارتفاع (م)", "Hauteur (m)"),
    "building.address": ("العنوان", "Adresse"),
    "classification.family": ("عائلة التصنيف", "Famille"),
    "classification.category": ("الصنف", "Catégorie"),
    "evacuation.points": ("نقاط الإخلاء", "Points de rassemblement"),
    "safety_team.representative": ("ممثل فريق السلامة", "Représentant de l'équipe"),
    "safety_team.members": ("أعضاء فريق السلامة", "Membres de l'équipe"),
    "documents.safety_file": ("ملف السلامة", "Dossier de sécurité"),
    "documents.safety_plan": ("مخطط السلامة", "Plan de sécurité"),
    "site.exits": ("المخارج سالكة", "Issues de secours dégagées"),
    "site.signage": ("اللافتات", "Signalisation"),
    "site.emergency_lighting": ("إنارة الطوارئ تعمل", "Éclairage de secours en état"),
    "site.alarm": ("تجربة الإنذار", "Essai de l'alarme"),
    "site.extinguishers_access": ("المطافئ في متناول اليد", "Extincteurs accessibles"),
    "site.electrical": ("التجهيزات الكهربائية", "Installations électriques"),
}
_RESULT = {
    "conform": ("مطابق", "Conforme"),
    "nonconform": ("غير مطابق", "Non conforme"),
    "not_checked": ("لم يُتفقَّد", "Non vérifié"),
}
_DECISION = {
    "approved": ("موافقة", "Avis favorable"),
    "approved_with_reservations": ("موافقة بتحفظات", "Avis favorable avec réserves"),
    "refused": ("رفض معلَّل", "Avis défavorable motivé"),
}
_STATUS = {
    "requested": ("مطلوبة", "Demandée"),
    "scheduled": ("مبرمجة", "Programmée"),
    "inspected": ("تمّ التفقد", "Inspectée"),
    "decided": ("صدر القرار", "Décidée"),
    "cancelled": ("ملغاة", "Annulée"),
}
#: Printed on the prevention certificate until the Office provides its text and validity (design-prevention.md §5).
PREVENTION_NOTE = {
    "ar": "نموذج شهادة وقاية [SIM] في انتظار النص الرسمي للديوان الوطني للحماية المدنية ومدة صلاحيتها.",
    "fr": "Modèle de certificat de prévention [SIM], en attente du texte officiel de l'Office national de la "
    "protection civile et de sa durée de validité.",
}


def item_label(key: str) -> tuple[str, str]:
    section, _, rest = key.partition(".")
    if section == "hazmat":
        return "مادة خطرة", "Matière dangereuse"
    if section == "equipment":
        return _pair(certificate._EQUIPMENT, rest)
    return _ITEM.get(key, (key, key))


def _declared(key: str, value: Any) -> str:
    if value is None:
        return "—"
    if key == "classification.family":
        return " / ".join(_pair(certificate._FAMILY, str(value)))
    return str(value)


def _local(at: datetime | None) -> date | None:
    return at.astimezone(TUNIS_TZ).date() if at else None


def _reservation_rows(rows: Sequence[tuple[str, str]]) -> str:
    return "".join(f"<tr><td>{_e(text)}</td><td>{_e(due)}</td></tr>" for text, due in rows) or (
        '<tr><td colspan="2">—</td></tr>'
    )


def _signature_cell(title: str, png: bytes | None, name: str | None, role: str | None) -> str:
    image = (
        f'<img src="data:image/png;base64,{base64.b64encode(png).decode()}" alt="" style="height:70px">' if png else "—"
    )
    who = " · ".join(x for x in (name, role) if x)
    return f"<td><b>{_e(title)}</b><br>{image}<br>{_e(who)}</td>"


def _signatures_html(visit: PreventionVisit, signatures: tuple[bytes | None, bytes | None], photos: int) -> str:
    """The two signatures of an inspection made on the phone, and the number of photos (phase P4c)."""
    if visit.inspector_signature_key is None and visit.representative_signature_key is None and not photos:
        return ""
    inspector, representative = signatures
    return (
        "<h2>التوقيعات / Signatures</h2><table><tr>"
        + _signature_cell("المفقِّد / L'inspecteur", inspector, visit.inspected_by_name, None)
        + _signature_cell(
            "ممثل المؤسسة / Le représentant", representative, visit.representative_name, visit.representative_role
        )
        + f"</tr></table><p>الصور الملتقطة في الموقع / Photos prises sur site : <b>{photos}</b></p>"
    )


def render_report_html(
    visit: PreventionVisit,
    org: Organization,
    reservations: Sequence[tuple[str, str]],
    cert_code: str | None,
    signatures: tuple[bytes | None, bytes | None] = (None, None),
    photos: int = 0,
) -> str:
    """The visit report (procès-verbal): the visit, the grid, the comparison, the decision and reservations."""
    comparison = visit.comparison or {"items": [], "conform": 0, "nonconform": 0, "not_checked": 0}
    st_ar, st_fr = _STATUS[visit.status]
    rows = "".join(
        f"<tr><td>{_e(' / '.join(item_label(i['key'])))}</td><td>{_e(_declared(i['key'], i['declared']))}</td>"
        f'<td class="{"ko" if i["result"] == "nonconform" else ""}">{_e(" / ".join(_RESULT[i["result"]]))}</td>'
        f"<td>{_e(i.get('observed') or '')}{' · ' if i.get('observed') and i.get('note') else ''}"
        f"{_e(i.get('note') or '')}</td></tr>"
        for i in comparison["items"]
    )
    missing = ", ".join(" / ".join(_pair(certificate._MISSING, m)) for m in comparison.get("missing", [])) or "—"
    changes = len(comparison.get("changes", []))
    decision = ""
    if visit.decision:
        dec_ar, dec_fr = _DECISION[visit.decision]
        decision = (
            f'<h2>القرار / Décision</h2><p><span class="status {"ko" if visit.decision == "refused" else "ok"}">'
            f"{_e(dec_ar)} / {_e(dec_fr)}</span></p>"
            f"<p>{_e(visit.decision_reason or '')}</p>"
            f"<p>بتاريخ / Le : {_e(_local(visit.decided_at))} · {_e(visit.decided_by_name or '')}"
            + (f" · شهادة الوقاية / Certificat : <b class='mono'>{_e(cert_code)}</b>" if cert_code else "")
            + "</p>"
        )
        if reservations:
            decision += (
                "<h3>التحفظات وآجالها / Réserves et délais</h3>"
                "<table><tr><th>التحفظ / Réserve</th><th>الأجل / Délai</th></tr>"
                f"{_reservation_rows(reservations)}</table>"
            )
    return f"""<!doctype html><html lang="ar"><head><meta charset="utf-8"><style>{certificate._CSS}
.ko {{ color: #b71c1c; font-weight: bold; }}</style></head><body>
<div class="head">
  <div class="fr"><h1>Procès-verbal de visite de prévention</h1>
    <div class="small">e-Himaya · Protection civile</div></div>
  <div class="ar"><h1>محضر زيارة وقاية</h1><div class="small">منصة ء-حماية · الحماية المدنية</div></div>
</div>
<div class="bi">
  <div class="ar">
    <p>المؤسسة: <b>{_e(org.name)}</b><br>العنوان: {_e(org.address)}<br>الحالة: {_e(st_ar)}</p>
    <p>تاريخ الزيارة: <b>{_e(visit.inspected_on or visit.scheduled_on)}</b><br>المفقِّد: {_e(visit.inspector_name)}<br>
       الحاضرون: {_e(visit.attendees or "—")}</p>
  </div>
  <div class="fr">
    <p>Établissement : <b>{_e(org.name)}</b><br>Gouvernorat : {_e(org.gouvernorat_code)}<br>État : {_e(st_fr)}</p>
    <p>Origine : {_e("demande de l'établissement" if visit.origin == "request" else "programmée par l'Office")}<br>
       Saisi par / سجّله : {_e(visit.inspected_by_name or "—")}</p>
  </div>
</div>
<h2>تقرير المقارنة / Rapport de comparaison</h2>
<p>مطابق / Conformes : <b>{comparison["conform"]}</b> · غير مطابق / Non conformes : <b>{comparison["nonconform"]}</b>
 · لم يُتفقَّد / Non vérifiés : {comparison["not_checked"]}</p>
<p>العناصر الناقصة / Éléments manquants : {_e(missing)}<br>
   فروق منذ شهادة السلامة / Écarts depuis le certificat de sécurité : {changes}</p>
<table><tr><th>البند / Point</th><th>المصرَّح به / Déclaré</th><th>النتيجة / Résultat</th>
<th>المعاين والملاحظة / Constaté et remarque</th></tr>{rows or '<tr><td colspan="4">—</td></tr>'}</table>
{_signatures_html(visit, signatures, photos)}
{decision}
<p class="small">بنود «المعاينة» نموذج [SIM] في انتظار شبكة التفقد الرسمية للديوان /
Les points « constat sur site » sont un modèle [SIM], en attente de la grille officielle de l'Office.</p>
</body></html>"""


async def _signature(key: str | None) -> bytes | None:
    return await get_store().head(key, SIGNATURE_MAX_BYTES) if key else None


async def store_report(session: AsyncSession, visit: PreventionVisit, org: Organization) -> list[str]:
    """Render and keep the visit report; returns the replaced object key to delete after commit."""
    reservations = [(r.text, r.due_on.isoformat()) for r in (await _reservations(session, [visit.id]))[visit.id]]
    cert = (await _certificates(session, [visit.id])).get(visit.id)
    signatures = (
        await _signature(visit.inspector_signature_key),
        await _signature(visit.representative_signature_key),
    )
    photos = len(await photos_of(session, visit.id))
    data = await certificate.render_document_pdf(
        render_report_html(visit, org, reservations, cert.code if cert else None, signatures, photos)
    )
    old = visit.report_object_key
    key = f"prevention/{visit.id}/report-{uuid.uuid4().hex[:8]}.pdf"
    await get_store().put(key, data, PDF_TYPE)
    visit.report_object_key = key
    visit.report_sha256 = hashlib.sha256(data).hexdigest()
    return [old] if old else []


def render_certificate_html(cert: Certificate, verify_url: str) -> str:
    """The prevention certificate [SIM]: the institution, the visit, the decision, its reservations, the seal."""
    snap = cert.snapshot
    org, prev = snap["org"], snap.get("prevention", {})
    kind_ar, kind_fr = _pair(certificate._KIND, org["kind"])
    dec_ar, dec_fr = _DECISION.get(prev.get("decision", "approved"), _DECISION["approved"])
    qr = segno.make(verify_url, error="m").svg_data_uri(scale=4, border=1)
    approved_on = _local(cert.reviewed_at)
    if cert.status == "revoked":
        state = (
            '<div class="status ko">شهادة ملغاة / Certificat révoqué</div>'
            f"<p>أُلغيت في / Révoqué le : <b>{_e(_local(cert.revoked_at))}</b></p>"
        )
    else:
        state = (
            f'<div class="status ok">{_e(dec_ar)} / {_e(dec_fr)}</div>'
            f"<p>صالحة إلى غاية / Valable jusqu'au : <b>{_e(cert.valid_until)}</b><br>"
            f"تاريخ الإصدار / Délivré le : {_e(approved_on)}</p>"
        )
    reservations = [(r["text"], r["due_on"]) for r in prev.get("reservations", [])]
    signature = (
        f'<p class="small">التوقيع الرقمي / Signature Ed25519 :</p><p class="mono">'
        f"{_e(base64.b64encode(cert.signature).decode())}</p>"
        if cert.signature
        else ""
    )
    return f"""<!doctype html><html lang="ar"><head><meta charset="utf-8"><style>{certificate._CSS}
.simnote {{ border: 2px dashed #ffb300; padding: 4px 8px; }}</style></head><body>
<div class="head">
  <div class="fr"><h1>Certificat de prévention</h1><div class="small">e-Himaya · Protection civile</div></div>
  <div class="ar"><h1>شهادة الوقاية</h1><div class="small">منصة ء-حماية · الحماية المدنية</div></div>
</div>
<p class="simnote small"><span class="ar">{PREVENTION_NOTE["ar"]}</span><br>
<span class="fr">{PREVENTION_NOTE["fr"]}</span></p>
<div class="bi">
  <div class="ar">
    <p>رمز الشهادة: <b class="mono" style="font-size:10pt">{_e(cert.code)}</b></p>
    <p>المؤسسة: <b>{_e(org["name"])}</b><br>الصبغة: {_e(kind_ar)}<br>المعرف: {_e(org["identifier"])}<br>
       العنوان: {_e(org["address"])}</p>
    <p>زيارة الوقاية بتاريخ: <b>{_e(prev.get("inspected_on"))}</b><br>
       المفقِّد: {_e(prev.get("inspector_name") or "—")}<br>
       البنود: مطابق {_e(prev.get("conform"))} · غير مطابق {_e(prev.get("nonconform"))}</p>
  </div>
  <div class="fr">
    <p>{state}</p>
    <p>Établissement : <b>{_e(org["name"])}</b><br>Type : {_e(kind_fr)}<br>
       Gouvernorat : {_e(org["gouvernorat_code"])}</p>
  </div>
</div>
<h2>التحفظات وآجالها / Réserves et délais</h2>
<table><tr><th>التحفظ / Réserve</th><th>الأجل / Délai</th></tr>{_reservation_rows(reservations)}</table>
<h2>التحقق / Vérification</h2>
<div class="bi">
  <div class="qr"><img src="{qr}" alt="QR">{certificate.seal_html(cert, approved_on)}</div>
  <div class="fr">
    <p class="small">Scannez le code ou ouvrez / امسح الرمز أو افتح :</p><p class="mono">{_e(verify_url)}</p>
    <p class="small">Empreinte du contenu / بصمة المحتوى (SHA-256) :</p><p class="mono">{_e(cert.fingerprint)}</p>
    {signature}
  </div>
</div>
</body></html>"""


# ---------------------------------------------------------------- annual report (F-APP-132)


def check_year(year: int) -> None:
    if not (2020 <= year <= service.today().year):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_year")


async def annual_report(session: AsyncSession, org: Organization, year: int) -> schemas.AnnualReport:
    """The institution's year: what it did and what the Office decided. The current year runs to today."""
    from app.modules.orgs import space  # space builds on this module's neighbours
    from app.modules.reports.models import Report

    check_year(year)
    today = service.today()
    first, last = date(year, 1, 1), min(date(year, 12, 31), today)
    activities = [
        space.activity_out(a)
        for a in await session.scalars(
            select(Activity)
            .where(Activity.org_id == org.id, Activity.starts_on >= first, Activity.starts_on <= last)
            .order_by(Activity.starts_on)
        )
    ]
    drills = [a for a in activities if a.kind == "drill"]
    maintenance = await session.scalar(
        select(func.count())
        .select_from(Maintenance)
        .where(Maintenance.org_id == org.id, Maintenance.done_on >= first, Maintenance.done_on <= last)
    )
    training = {"valid": 0, "expiring": 0, "expired": 0, "unknown": 0}
    for member in await session.scalars(select(TeamMember).where(TeamMember.org_id == org.id)):
        state, _ = domain.training_status(member.last_training_on, member.training_valid_months, last)
        training[state] += 1
    when = func.coalesce(
        PreventionVisit.inspected_on, PreventionVisit.scheduled_on, func.date(PreventionVisit.created_at)
    )
    visits = list(
        await session.scalars(
            select(PreventionVisit)
            .where(PreventionVisit.org_id == org.id, when >= first, when <= last)
            .order_by(when, PreventionVisit.id)
        )
    )
    reservations = list(
        await session.scalars(
            select(PreventionReservation).where(
                PreventionReservation.org_id == org.id,
                extract("year", PreventionReservation.created_at) == year,
            )
        )
    )
    certs = list(
        await session.scalars(
            select(Certificate)
            .where(
                Certificate.org_id == org.id,
                Certificate.status.in_(("approved", "revoked")),
                extract("year", Certificate.reviewed_at) == year,
            )
            .order_by(Certificate.reviewed_at)
        )
    )
    stamps = await session.scalar(
        select(func.count())
        .select_from(CertificateStamp)
        .join(Certificate, Certificate.id == CertificateStamp.certificate_id)
        .where(Certificate.org_id == org.id, CertificateStamp.stamped_on >= first, CertificateStamp.stamped_on <= last)
    )
    reports = await session.scalar(
        select(func.count())
        .select_from(Report)
        .where(Report.organization_id == org.id, extract("year", Report.received_at) == year)
    )
    return schemas.AnnualReport(
        year=year,
        org_id=org.id,
        org_name=org.name,
        generated_on=today,
        drills=drills,
        events=[a for a in activities if a.kind == "event"],
        participants=sum(a.participants or 0 for a in drills),
        maintenance=maintenance or 0,
        training=schemas.AnnualCount(**training),
        visits=await visit_views(session, org, visits),
        reservations=schemas.AnnualReservations(
            opened=len(reservations),
            lifted=sum(1 for r in reservations if r.lifted_at is not None),
            open=sum(1 for r in reservations if r.lifted_at is None and r.due_on >= today),
            overdue=sum(1 for r in reservations if r.lifted_at is None and r.due_on < today),
        ),
        certificates=[certificate.certificate_out(c) for c in certs],
        stamps=stamps or 0,
        reports=reports or 0,
    )
