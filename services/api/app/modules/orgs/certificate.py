"""Digital safety certificate (FR-B-008): snapshot, fingerprint, PDF, review and public verification.

* The certificate certifies a **snapshot** of the institution (card, classification, team, registers, map
  features and the SHA-256 of the current document versions) frozen when the draft is generated.
* ``fingerprint`` = SHA-256 of the canonical JSON of that snapshot; it never changes afterwards.
* On approval the server signs ``<code>|<fingerprint>|<valid_until>`` with Ed25519 and re-renders the PDF
  without the draft mark. Anyone can check a code on the public verification page.
* Phase 10 §4.1: the certificate records the ``key_id`` of the key that signed it, so the signing key can be rotated
  (earlier public keys stay in ``CERTIFICATE_PREVIOUS_PUBLIC_KEYS``); an auditor can revoke an approved certificate,
  which makes it invalid at once. The document says it is a self-assessment, not an official certificate.
"""

import base64
import hashlib
import html
import json
import re
import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import segno
from anyio import to_thread
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import HTTPException, status
from sqlalchemy import and_, delete, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.events import emit
from app.core.storage import get_store
from app.modules.orgs import domain, schemas, service
from app.modules.orgs.models import Certificate, CertificateStamp, Organization

TUNIS_TZ = ZoneInfo("Africa/Tunis")
PDF_TYPE = "application/pdf"
SIGNED_MESSAGE = "<code>|<fingerprint>|<valid_until ISO date>, UTF-8"


# ---------------------------------------------------------------- signing key


def _private_key() -> Ed25519PrivateKey | None:
    secret = get_settings().certificate_signing_key
    if secret is None:
        return None
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(secret.get_secret_value()))


def _raw(public: Ed25519PublicKey) -> bytes:
    return public.public_bytes(Encoding.Raw, PublicFormat.Raw)


def key_id_of(public: Ed25519PublicKey) -> str:
    """First 16 hex characters of the SHA-256 of the raw public key."""
    return hashlib.sha256(_raw(public)).hexdigest()[:16]


def b64(public: Ed25519PublicKey) -> str:
    return base64.b64encode(_raw(public)).decode()


def current_key_id() -> str | None:
    key = _private_key()
    return key_id_of(key.public_key()) if key is not None else None


def known_public_keys() -> dict[str, Ed25519PublicKey]:
    """Every key whose signatures are still accepted: the current one and the previous ones, by key id."""
    keys: dict[str, Ed25519PublicKey] = {}
    for raw in get_settings().certificate_previous_public_keys:
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(raw))
        keys[key_id_of(public)] = public
    current = _private_key()
    if current is not None:
        keys[key_id_of(current.public_key())] = current.public_key()
    return keys


def signed_message(code: str, fingerprint: str, valid_until: date) -> bytes:
    return f"{code}|{fingerprint}|{valid_until.isoformat()}".encode()


def signature_valid(cert: Certificate) -> bool:
    """The signature checks out with the key named by ``key_id`` (an unknown key id is not valid). Certificates signed
    before key ids existed are checked against every known key."""
    if cert.signature is None or cert.valid_until is None:
        return False
    keys = known_public_keys()
    candidates = [keys[cert.key_id]] if cert.key_id in keys else [] if cert.key_id else list(keys.values())
    message = signed_message(cert.code, cert.fingerprint, cert.valid_until)
    for public in candidates:
        try:
            public.verify(cert.signature, message)
        except InvalidSignature:
            continue
        return True
    return False


# ---------------------------------------------------------------- snapshot


def canonical(snapshot: dict[str, Any]) -> bytes:
    return json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def fingerprint_of(snapshot: dict[str, Any]) -> str:
    return hashlib.sha256(canonical(snapshot)).hexdigest()


async def snapshot_of(
    session: AsyncSession, org: Organization, regs: service.Registers | None = None
) -> dict[str, Any]:
    """The certified content, in plain JSON types so its canonical form is stable."""
    regs = regs or await service.load_registers(session, org.id)
    on = service.today()
    classification = service.classification_of(org, len(regs.hazmat))
    completeness = service.completeness_of(classification, regs, on)
    lat, lon = await service.coords(session, org.id)
    return {
        "generated_on": on.isoformat(),
        "org": {
            "id": str(org.id),
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
            "location": {"lat": round(lat, 6), "lon": round(lon, 6)},
            "gouvernorat_code": org.gouvernorat_code,
            "manager": schemas.Person.model_validate(org.manager or {}).model_dump(mode="json"),
        },
        "classification": service.classification_out(classification).model_dump(mode="json"),
        "completeness": completeness.model_dump(mode="json"),
        "team": [
            {
                "full_name": m.full_name,
                "team_role": m.team_role,
                "position": m.position,
                "training_status": t.training_status,
                "training_expires_on": t.training_expires_on.isoformat() if t.training_expires_on else None,
            }
            for m in regs.team
            for t in (service.team_out(m, on),)
        ],
        "hazmat": [
            {
                "name": h.name,
                "un_number": h.un_number,
                "hazard_class": h.hazard_class,
                "quantity": str(h.quantity),
                "unit": h.unit,
                "storage_location": h.storage_location,
            }
            for h in regs.hazmat
        ],
        "equipment": [
            {
                "kind": e.kind,
                "count": e.count,
                "maintenance_status": out.maintenance_status,
                "next_maintenance_on": out.next_maintenance_on.isoformat() if out.next_maintenance_on else None,
            }
            for e in regs.equipment
            for out in (service.equipment_out(e, on),)
        ],
        "features": [
            {"kind": f.kind, "label": f.label, "location": {"lat": round(la, 6), "lon": round(lo, 6)}}
            for f, la, lo in regs.features
        ],
        "documents": [
            {
                "kind": doc.kind,
                "title": doc.title,
                "version": current.version,
                "filename": current.filename,
                "sha256": current.sha256,
            }
            for doc, current, _ in regs.documents
            if current is not None
        ],
    }


# ---------------------------------------------------------------- PDF

_KIND = {
    "health": ("صحية", "Santé"),
    "industrial": ("صناعية", "Industrielle"),
    "energy": ("طاقة ومحروقات", "Énergie et carburants"),
    "tourism": ("سياحية", "Tourisme"),
    "education": ("تربوية", "Éducation"),
    "social_care": ("رعاية اجتماعية", "Action sociale"),
    "public_admin": ("عمومية وإدارية", "Administration publique"),
    "culture_sport": ("ثقافية ورياضية", "Culture et sport"),
    "commercial": ("تجارية", "Commerce"),
    "transport": ("نقل", "Transport"),
    "religious": ("دينية", "Culte"),
    "other": ("أخرى", "Autre"),
}
_FAMILY = {
    "high_rise": ("عمارة شاهقة", "Immeuble de grande hauteur"),
    "industrial": ("منشأة صناعية", "Établissement industriel"),
    "erp": ("مؤسسة تستقبل العموم", "Établissement recevant du public"),
    "workplace": ("مكان عمل", "Lieu de travail"),
}
_DOC = {
    "safety_file": ("ملف السلامة", "Dossier de sécurité"),
    "safety_plan": ("مخطط السلامة", "Plan de sécurité"),
    "sds": ("بطاقة بيانات السلامة", "Fiche de données de sécurité"),
    "other": ("وثيقة", "Document"),
}
_EQUIPMENT = {
    "extinguisher": ("مطافئ", "Extincteurs"),
    "fire_hose_reel": ("خراطيم الحريق", "RIA"),
    "sprinkler": ("رشاشات آلية", "Sprinklers"),
    "smoke_detector": ("كواشف الدخان", "Détecteurs de fumée"),
    "alarm_panel": ("لوحة الإنذار", "Centrale d'alarme"),
    "emergency_lighting": ("إنارة الطوارئ", "Éclairage de secours"),
    "fire_door": ("أبواب مقاومة للحريق", "Portes coupe-feu"),
    "other": ("أخرى", "Autre"),
}
_MISSING = {
    "safety_file": ("ملف السلامة", "dossier de sécurité"),
    "safety_plan": ("مخطط السلامة", "plan de sécurité"),
    "safety_team": ("فريق السلامة", "équipe de sécurité"),
    "training": ("التكوين", "formation"),
    "hazmat_sds": ("بطاقات بيانات السلامة", "fiches de données de sécurité"),
    "equipment": ("التجهيزات", "équipements"),
    "evacuation_points": ("نقاط الإخلاء", "points de rassemblement"),
}

_TEAM_ROLE = {True: "الممثل / Représentant", False: "عضو / Membre"}

_CSS = """
@page { size: A4; margin: 16mm 14mm 18mm 14mm;
  @bottom-center { content: counter(page) " / " counter(pages); font-size: 8pt; color: #666; } }
body { font-family: "Noto Naskh Arabic", "Noto Sans Arabic", "Noto Sans", "DejaVu Sans", sans-serif;
  font-size: 9.5pt; color: #1b1b1b; }
h1 { font-size: 15pt; margin: 0; } h2 { font-size: 11pt; margin: 14px 0 6px; border-bottom: 1px solid #b71c1c;
  color: #b71c1c; padding-bottom: 2px; }
.head { display: flex; justify-content: space-between; align-items: center; border-bottom: 3px solid #b71c1c;
  padding-bottom: 8px; }
.ar { direction: rtl; text-align: right; } .fr { direction: ltr; text-align: left; }
.bi { display: flex; gap: 14px; } .bi > div { flex: 1; }
table { width: 100%; border-collapse: collapse; margin-top: 4px; }
th, td { border: 1px solid #ccc; padding: 3px 5px; vertical-align: top; }
th { background: #f4f4f4; font-weight: bold; }
.mono { font-family: "DejaVu Sans Mono", monospace; font-size: 7.5pt; word-break: break-all; direction: ltr; }
.status { font-size: 12pt; font-weight: bold; padding: 6px 10px; border: 2px solid; display: inline-block; }
.ok { color: #1b5e20; border-color: #1b5e20; } .ko { color: #b71c1c; border-color: #b71c1c; }
.draft { position: fixed; top: 45%; left: 0; right: 0; text-align: center; font-size: 64pt; color: rgba(183,28,28,.13);
  transform: rotate(-30deg); font-weight: bold; }
.qr { text-align: center; } .qr img { width: 34mm; height: 34mm; }
.small { font-size: 8pt; color: #555; }
.seal { width: 40mm; height: 40mm; box-sizing: border-box; padding: 5mm; border-radius: 50%;
  border: 2.5px double #1f3d99; color: #1f3d99; text-align: center; display: flex; flex-direction: column;
  justify-content: center; align-items: center; font-size: 6.5pt; line-height: 1.25; margin: 2mm auto 0; }
.seal b { font-size: 7pt; } .seal .sim { background: #ffb300; color: #1f1300; padding: 0 4px; font-weight: bold; }
"""


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _pair(table: dict[str, tuple[str, str]], key: str) -> tuple[str, str]:
    return table.get(key, (key, key))


def render_html(cert: Certificate, verify_url: str) -> str:
    snap = cert.snapshot
    org, cls = snap["org"], snap["classification"]
    kind_ar, kind_fr = _pair(_KIND, org["kind"])
    fam_ar, fam_fr = _pair(_FAMILY, cls["family"])
    category = f" — {cls['category']}" if cls.get("category") else ""
    qr = segno.make(verify_url, error="m").svg_data_uri(scale=4, border=1)
    approved = cert.status in ("approved", "revoked") and cert.valid_until is not None

    approved_on = cert.reviewed_at.astimezone(TUNIS_TZ).date() if cert.reviewed_at else None
    if cert.status == "revoked":
        revoked_on = cert.revoked_at.astimezone(TUNIS_TZ).date() if cert.revoked_at else None
        state = (
            '<div class="status ko">شهادة ملغاة / Certificat révoqué</div>'
            f"<p>أُلغيت في / Révoqué le : <b>{_e(revoked_on)}</b></p>"
        )
    elif approved:
        state = (
            f'<div class="status ok">شهادة مصادق عليها / Certificat approuvé</div>'
            f"<p>صالحة إلى غاية / Valable jusqu'au : <b>{_e(cert.valid_until)}</b><br>"
            f"تاريخ المصادقة / Approuvé le : {_e(approved_on)}"
            "</p>"
        )
    else:
        state = '<div class="status ko">مسودة — غير صالحة / Brouillon — sans valeur</div>'

    missing = snap["completeness"]["missing"]
    completeness = (
        "<p>الملف مكتمل حسب التصنيف / Dossier complet selon la classification.</p>"
        if not missing
        else "<p>عناصر ناقصة / Éléments manquants : "
        + ", ".join(f"{_e(_pair(_MISSING, m)[0])} / {_e(_pair(_MISSING, m)[1])}" for m in missing)
        + "</p>"
    )
    rep = next((m for m in snap["team"] if m["team_role"] == "representative"), None)
    team_rows = "".join(
        f"<tr><td>{_e(m['full_name'])}</td><td>{_TEAM_ROLE[m['team_role'] == 'representative']}</td>"
        f"<td>{_e(m['position'])}</td><td>{_e(m['training_status'])} {_e(m['training_expires_on'])}</td></tr>"
        for m in snap["team"]
    )
    hazmat_rows = "".join(
        f"<tr><td>{_e(h['name'])}</td><td>{_e(h['un_number'])}</td><td>{_e(h['hazard_class'])}</td>"
        f"<td>{_e(h['quantity'])} {_e(h['unit'])}</td><td>{_e(h['storage_location'])}</td></tr>"
        for h in snap["hazmat"]
    )
    equipment_rows = "".join(
        f"<tr><td>{_e(' / '.join(_pair(_EQUIPMENT, x['kind'])))}</td><td>{_e(x['count'])}</td>"
        f"<td>{_e(x['maintenance_status'])} {_e(x['next_maintenance_on'])}</td></tr>"
        for x in snap["equipment"]
    )
    document_rows = "".join(
        f"<tr><td>{_e(' / '.join(_pair(_DOC, d['kind'])))}</td><td>{_e(d['title'])} (v{_e(d['version'])})</td>"
        f'<td class="mono">{_e(d["sha256"])}</td></tr>'
        for d in snap["documents"]
    )
    evacuation = sum(1 for f in snap["features"] if f["kind"] == "evacuation_point")
    signature = (
        f'<p class="small">التوقيع الرقمي / Signature Ed25519 :</p><p class="mono">'
        f"{_e(base64.b64encode(cert.signature).decode())}</p>"
        if approved and cert.signature
        else ""
    )
    empty = '<tr><td colspan="5">—</td></tr>'
    # Phase P3a: the Office's electronic seal, a picture of the Ed25519 signature above (it adds no signature).
    seal = seal_html(cert, approved_on)
    return f"""<!doctype html><html lang="ar"><head><meta charset="utf-8"><style>{_CSS}</style></head><body>
{"" if approved else '<div class="draft">مسودة · BROUILLON</div>'}
<div class="head">
  <div class="fr"><h1>Certificat numérique de sécurité</h1><div class="small">e-Himaya · Protection civile</div></div>
  <div class="ar"><h1>شهادة السلامة الرقمية</h1><div class="small">منصة ء-حماية · الحماية المدنية</div></div>
</div>
<div class="bi">
  <div class="ar">
    <p>رمز الشهادة: <b class="mono" style="font-size:10pt">{_e(cert.code)}</b></p>
    <p>المؤسسة: <b>{_e(org["name"])}</b><br>الصبغة: {_e(kind_ar)}<br>
       المعرف: {_e(org["identifier"])}<br>العنوان: {_e(org["address"])}<br>
       الطاقة الاستيعابية: {_e(org["capacity"])} · الطوابق: {_e(org["floors"])} · الارتفاع: {_e(org["height_m"])} م</p>
    <p>التصنيف: <b>{_e(fam_ar)}{_e(category)}</b> (مؤقت، في انتظار المصادقة على العتبات)</p>
  </div>
  <div class="fr">
    <p>{state}</p>
    <p>Établissement : <b>{_e(org["name"])}</b><br>Type : {_e(kind_fr)}<br>
       Identifiant : {_e(org["identifier"])}<br>Gouvernorat : {_e(org["gouvernorat_code"])}</p>
    <p>Classification : <b>{_e(fam_fr)}{_e(category)}</b> (provisoire)</p>
  </div>
</div>
{completeness}
<h2>فريق السلامة / Équipe de sécurité</h2>
<p>الممثل / Représentant : <b>{_e(rep["full_name"] if rep else "—")}</b> ·
   نقاط الإخلاء / Points de rassemblement : {evacuation}</p>
<table><tr><th>الاسم / Nom</th><th>الدور / Rôle</th><th>الخطة / Fonction</th><th>التكوين / Formation</th></tr>
{team_rows or empty}</table>
<h2>المواد الخطرة / Matières dangereuses</h2>
<table><tr><th>المادة / Matière</th><th>ONU</th><th>الصنف / Classe</th><th>الكمية / Quantité</th>
<th>التخزين / Stockage</th></tr>
{hazmat_rows or empty}</table>
<h2>التجهيزات / Équipements</h2>
<table><tr><th>النوع / Type</th><th>العدد / Nombre</th><th>الصيانة / Maintenance</th></tr>
{equipment_rows or empty}</table>
<h2>الوثائق المعتمدة / Documents certifiés (SHA-256)</h2>
<table><tr><th>النوع / Type</th><th>العنوان / Titre</th><th>SHA-256</th></tr>{document_rows or empty}</table>
<h2>التحقق / Vérification</h2>
<div class="bi">
  <div class="qr"><img src="{qr}" alt="QR">{seal}</div>
  <div class="fr">
    <p class="small">Scannez le code ou ouvrez / امسح الرمز أو افتح :</p><p class="mono">{_e(verify_url)}</p>
    <p class="small">Empreinte du contenu / بصمة المحتوى (SHA-256) :</p><p class="mono">{_e(cert.fingerprint)}</p>
    {signature}
    <p class="small">Établi le / حُرّر في : {_e(snap["generated_on"])}</p>
  </div>
</div>
<h2>تنبيه / Avertissement / Notice</h2>
<p class="ar small">{DISCLAIMER["ar"]}</p>
<p class="fr small">{DISCLAIMER["fr"]}</p>
<p class="fr small">{DISCLAIMER["en"]}</p>
</body></html>"""


#: What the certificate is and is not (phase 10 §4.1), printed on the PDF; the portal shows the same text.
DISCLAIMER = {
    "ar": (
        "هذه الشهادة تقييم ذاتي للسلامة سجّلته المؤسسة على منصة ء-حماية وراجعه مدققو المنصة. "
        "ليست شهادة رسمية صادرة عن الديوان الوطني للحماية المدنية ولا عن أي إدارة أخرى، "
        "ولا تعوّض التراخيص والمعاينات التي يفرضها القانون."
    ),
    "fr": (
        "Ce certificat est une auto-évaluation de sécurité enregistrée par l'établissement sur la plateforme "
        "e-Himaya et revue par ses auditeurs. Ce n'est pas un certificat officiel de l'Office national de la "
        "protection civile ni d'une autre administration, et il ne remplace pas les autorisations et visites "
        "prévues par la loi."
    ),
    "en": (
        "This certificate is a safety self-assessment recorded by the institution on the e-Himaya platform and "
        "reviewed by its auditors. It is not an official certificate of the National Office of Civil Protection "
        "or of any other administration, and it does not replace the permits and inspections required by law."
    ),
}


def seal_html(cert: Certificate, approved_on: date | None) -> str:
    """The Office's electronic seal on an approved certificate, a picture of its Ed25519 signature [SIM]."""
    if cert.status != "approved" or not cert.signature:
        return ""
    return (
        '<div class="seal"><b>الديوان الوطني للحماية المدنية</b><span>Office national de la protection civile</span>'
        f"<span>ختم إلكتروني · Cachet électronique</span><span>{_e(approved_on)}</span>"
        f'<span class="mono">{_e(cert.key_id or "")}</span><span class="sim">[SIM]</span></div>'
        f'<p class="small" style="text-align:center">{SEAL_NOTE}</p>'
    )


#: Printed under the electronic seal until the Office provides its official seal (docs/phase-p3 §3.1).
SEAL_NOTE = "نموذج ختم في انتظار الختم الرسمي للديوان / Modèle de cachet, en attente du cachet officiel"


def _render_pdf_sync(document: str) -> bytes:
    from weasyprint import HTML

    pdf: bytes = HTML(string=document).write_pdf()
    return pdf


async def render_pdf(cert: Certificate) -> bytes:
    if cert.kind == "prevention":
        from app.modules.orgs import prevention  # prevention builds on this module

        document = prevention.render_certificate_html(cert, verify_url(cert.code))
    else:
        document = render_html(cert, verify_url(cert.code))
    return await to_thread.run_sync(_render_pdf_sync, document)


async def render_document_pdf(document: str) -> bytes:
    return await to_thread.run_sync(_render_pdf_sync, document)


def verify_url(code: str) -> str:
    return f"{get_settings().portal_public_url}/verify/{code}"


async def _store_pdf(cert: Certificate, name: str) -> None:
    data = await render_pdf(cert)
    key = f"certificates/{cert.id}/{name}.pdf"
    await get_store().put(key, data, PDF_TYPE)
    cert.pdf_object_key = key
    cert.pdf_sha256 = hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------- lifecycle


async def next_code(session: AsyncSession, gouvernorat_code: int | None, prefix: str = "EHC") -> str:
    """``EHC-<yy>-<gouvernorat>-<6 digits>`` (``EHP-`` for a prevention certificate), numbered per year."""
    year = datetime.now(TUNIS_TZ).year
    number = await session.scalar(
        text(
            "INSERT INTO org.certificate_counter (year, last) VALUES (:year, 1) "
            "ON CONFLICT (year) DO UPDATE SET last = org.certificate_counter.last + 1 RETURNING last"
        ),
        {"year": year},
    )
    return f"{prefix}-{year % 100:02d}-{gouvernorat_code or 0:02d}-{int(number or 0):06d}"


def certificate_out(
    cert: Certificate,
    *,
    changes: list[schemas.CertificateChange] | None = None,
    stamps: Sequence[CertificateStamp] = (),
) -> schemas.CertificateOut:
    """``changes`` is given for the current approved certificate only (``needs_update`` stays null otherwise)."""
    return schemas.CertificateOut(
        id=cert.id,
        code=cert.code,
        kind=cert.kind,
        status=cert.status,
        superseded=cert.superseded_by is not None,
        created_at=cert.created_at,
        submitted_at=cert.submitted_at,
        reviewed_at=cert.reviewed_at,
        review_reason=cert.review_reason,
        valid_until=cert.valid_until,
        fingerprint=cert.fingerprint,
        pdf_sha256=cert.pdf_sha256,
        verify_url=verify_url(cert.code),
        key_id=cert.key_id,
        revoked_at=cert.revoked_at,
        revoke_reason=cert.revoke_reason,
        needs_update=bool(changes) if changes is not None else None,
        changes=changes or [],
        stamps=[stamp_out(s) for s in stamps],
    )


async def certificates_of(session: AsyncSession, org_id: uuid.UUID, kind: str = "safety") -> list[Certificate]:
    return list(
        await session.scalars(
            select(Certificate)
            .where(Certificate.org_id == org_id, Certificate.kind == kind)
            .order_by(Certificate.created_at.desc(), Certificate.id.desc())
        )
    )


async def owned_certificate(
    session: AsyncSession, org_id: uuid.UUID, cert_id: uuid.UUID, *, lock: bool = False
) -> Certificate:
    query = select(Certificate).where(Certificate.id == cert_id, Certificate.org_id == org_id)
    cert = await session.scalar(query.with_for_update() if lock else query)
    if cert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return cert


async def generate_draft(
    session: AsyncSession, org: Organization, user: service.PortalUser
) -> tuple[Certificate, list[str]]:
    """New draft replacing any previous one. Returns it and the object keys to delete after commit."""
    stale: list[str] = []
    previous = await session.scalar(
        select(Certificate).where(Certificate.org_id == org.id, Certificate.status == "draft").with_for_update()
    )
    if previous is not None:
        stale.append(previous.pdf_object_key)
        await session.execute(delete(Certificate).where(Certificate.id == previous.id))
        await session.flush()
    snapshot = await snapshot_of(session, org)
    cert = Certificate(
        id=uuid.uuid4(),
        org_id=org.id,
        code=await next_code(session, org.gouvernorat_code),
        status="draft",
        snapshot=snapshot,
        fingerprint=fingerprint_of(snapshot),
        created_by=user.user_id,
    )
    await _store_pdf(cert, "draft")
    session.add(cert)
    await session.flush()
    await session.refresh(cert)
    return cert, stale


async def submit(session: AsyncSession, org: Organization, cert: Certificate, user: service.PortalUser) -> None:
    service.require_active(org)
    if cert.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    regs = await service.load_registers(session, org.id)
    current = service.completeness_of(service.classification_of(org, len(regs.hazmat)), regs, service.today())
    if not current.ok:
        raise HTTPException(status.HTTP_409_CONFLICT, "incomplete")
    if not cert.snapshot["completeness"]["ok"]:
        # The registers were completed after this draft: generate a new one, which certifies them.
        raise HTTPException(status.HTTP_409_CONFLICT, "certificate_outdated")
    cert.status = "submitted"
    cert.submitted_by = user.user_id
    cert.submitted_at = datetime.now(UTC)
    await session.flush()


def check_valid_until(valid_until: date | None) -> date:
    today = service.today()
    latest = domain.add_months(today, 12 * domain.CERTIFICATE_MAX_YEARS)
    if valid_until is None or not (today < valid_until <= latest):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_valid_until")
    return valid_until


async def review(session: AsyncSession, cert: Certificate, body: schemas.CertificateReviewIn, actor: str) -> list[str]:
    """Approve (sign, re-render, supersede older approvals) or reject. Returns object keys to delete."""
    if cert.status != "submitted":
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    reason = body.reason.strip() if body.reason and body.reason.strip() else None
    now = datetime.now(UTC)
    stale: list[str] = []
    if body.decision == "reject":
        if reason is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reason_required")
        cert.status = "rejected"
    else:
        valid_until = check_valid_until(body.valid_until)
        key = _private_key()
        if key is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "signing_key_missing")
        org = await session.get(Organization, cert.org_id)
        assert org is not None
        if org.status != domain.OrgStatus.ACTIVE:
            raise HTTPException(status.HTTP_409_CONFLICT, "org_not_active")
        cert.status = "approved"
        cert.valid_until = valid_until
        cert.reviewed_at = now
        cert.signature = key.sign(signed_message(cert.code, cert.fingerprint, valid_until))
        cert.key_id = key_id_of(key.public_key())
        stale.append(cert.pdf_object_key)
        await _store_pdf(cert, "approved")
        await session.execute(
            update(Certificate)
            .where(
                Certificate.org_id == cert.org_id,
                Certificate.kind == cert.kind,
                Certificate.id != cert.id,
                Certificate.status == "approved",
                Certificate.superseded_by.is_(None),
            )
            .values(superseded_by=cert.id)
        )
    cert.reviewed_at = now
    cert.reviewed_by = actor
    cert.review_reason = reason
    await session.flush()
    return stale


async def revoke(session: AsyncSession, cert: Certificate, reason: str | None, actor: str) -> list[str]:
    """Revoke an approved certificate (granted in error, or the institution no longer meets it). Returns the object
    keys to delete after commit: the PDF is rendered again with the revocation."""
    reason = reason.strip() if reason else None
    if not reason:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reason_required")
    if cert.status == "revoked":
        raise HTTPException(status.HTTP_409_CONFLICT, "already_revoked")
    if cert.status != "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    cert.status = "revoked"
    cert.revoked_at = datetime.now(UTC)
    cert.revoked_by = actor
    cert.revoke_reason = reason
    stale = [cert.pdf_object_key]
    await _store_pdf(cert, "revoked")
    await session.flush()
    return stale


async def certificate_event(session: AsyncSession, cert: Certificate) -> None:
    org = await session.get(Organization, cert.org_id)
    assert org is not None
    await emit(
        session,
        "certificate.updated",
        {
            "certificate": {
                "id": str(cert.id),
                "code": cert.code,
                "status": cert.status,
                "org_id": str(org.id),
                "org_name": org.name,
                "gouvernorat_code": org.gouvernorat_code,
            }
        },
    )


async def public_view(session: AsyncSession, code: str) -> schemas.PublicCertificate | None:
    found = (
        await session.execute(
            select(Certificate, Organization)
            .join(Organization, Organization.id == Certificate.org_id)
            .where(Certificate.code == code, Certificate.status != "draft")
        )
    ).first()
    if found is None:
        return None
    cert, org = found
    revoked = cert.status == "revoked"
    signed = cert.status in ("approved", "revoked") and signature_valid(cert)
    valid = (
        signed
        and not revoked
        and cert.superseded_by is None
        and cert.valid_until is not None
        and cert.valid_until >= service.today()
        and org.status == domain.OrgStatus.ACTIVE
    )
    cls = cert.snapshot.get("classification", {})
    return schemas.PublicCertificate(
        code=cert.code,
        kind=cert.kind,
        status=cert.status,
        valid=valid,
        superseded=cert.superseded_by is not None,
        org_name=cert.snapshot.get("org", {}).get("name", org.name),
        org_kind=org.kind,
        gouvernorat_code=org.gouvernorat_code,
        classification={"family": cls.get("family"), "category": cls.get("category")},
        issued_at=cert.reviewed_at if cert.status in ("approved", "revoked") else None,
        valid_until=cert.valid_until,
        fingerprint=cert.fingerprint,
        pdf_sha256=cert.pdf_sha256,
        signature_valid=signed,
        key_id=cert.key_id,
        revoked=revoked,
        revoked_at=cert.revoked_at,
        stamps=[
            schemas.PublicStamp(place=s.place, stamped_on=s.stamped_on)
            for s in (await stamps_of(session, [cert.id]))[cert.id]
        ],
        with_reservations=cert.snapshot.get("prevention", {}).get("decision") == "approved_with_reservations",
    )


# ---------------------------------------------------------------- staff queue


async def queue(
    session: AsyncSession, principal: Any, status_: str, limit: int, cursor: str | None
) -> tuple[list[schemas.CertificateQueueItem], str | None]:
    at = func.coalesce(Certificate.submitted_at, Certificate.created_at)
    query = (
        select(Certificate, Organization, at)
        .join(Organization, Organization.id == Certificate.org_id)
        .where(service.staff_scope(principal), Certificate.kind == "safety", Certificate.status == status_)
    )
    if cursor:
        last_at, last_id = service.decode_cursor(cursor)
        query = query.where(or_(at > last_at, and_(at == last_at, Certificate.id > last_id)))
    rows = (await session.execute(query.order_by(at, Certificate.id).limit(limit))).all()
    items = [
        schemas.CertificateQueueItem(
            id=cert.id,
            code=cert.code,
            status=cert.status,
            org_id=org.id,
            org_name=org.name,
            gouvernorat_code=org.gouvernorat_code,
            submitted_at=cert.submitted_at,
            completeness=schemas.Completeness.model_validate(
                cert.snapshot.get("completeness", {"ok": False, "missing": []})
            ),
        )
        for cert, org, _ in rows
    ]
    next_cursor = service.encode_cursor(rows[-1][2], rows[-1][0].id) if len(rows) == limit else None
    return items, next_cursor


# ---------------------------------------------------------------- phase P3a: needs update, alerts, renewal


def stamp_out(stamp: CertificateStamp) -> schemas.StampOut:
    return schemas.StampOut(
        id=stamp.id,
        place=stamp.place,
        gouvernorat_code=stamp.gouvernorat_code,
        stamped_on=stamp.stamped_on,
        note=stamp.note,
        stamped_by_name=stamp.stamped_by_name,
        recorded_at=stamp.recorded_at,
        has_photo=stamp.photo_object_key is not None,
        changes=[schemas.CertificateChange.model_validate(c) for c in stamp.changes or []],
    )


def is_current(cert: Certificate) -> bool:
    """The approved certificate that has not been replaced (it may have expired)."""
    return cert.status == "approved" and cert.superseded_by is None


async def current_of(session: AsyncSession, org_id: uuid.UUID, kind: str = "safety") -> Certificate | None:
    return await session.scalar(
        select(Certificate)
        .where(
            Certificate.org_id == org_id,
            Certificate.kind == kind,
            Certificate.status == "approved",
            Certificate.superseded_by.is_(None),
        )
        .order_by(Certificate.reviewed_at.desc())
        .limit(1)
    )


async def changes_of(
    session: AsyncSession, org: Organization, cert: Certificate, regs: service.Registers | None = None
) -> list[schemas.CertificateChange]:
    now = await snapshot_of(session, org, regs)
    return [
        schemas.CertificateChange(section=section, field=name, certified=old, current=new)
        for section, name, old, new in domain.certificate_changes(cert.snapshot, now)
    ]


async def stamps_of(session: AsyncSession, cert_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[CertificateStamp]]:
    found: dict[uuid.UUID, list[CertificateStamp]] = {i: [] for i in cert_ids}
    if cert_ids:
        rows = await session.scalars(
            select(CertificateStamp)
            .where(CertificateStamp.certificate_id.in_(cert_ids))
            .order_by(CertificateStamp.stamped_on.desc(), CertificateStamp.recorded_at.desc())
        )
        for stamp in rows:
            found[stamp.certificate_id].append(stamp)
    return found


async def certificates_view(
    session: AsyncSession, org: Organization, regs: service.Registers | None = None
) -> list[schemas.CertificateOut]:
    """Every certificate of the institution, the current one with its comparison, each with its stamps."""
    certs = await certificates_of(session, org.id)
    stamps = await stamps_of(session, [c.id for c in certs])
    out = []
    for cert in certs:
        changes = await changes_of(session, org, cert, regs) if is_current(cert) else None
        out.append(certificate_out(cert, changes=changes, stamps=stamps[cert.id]))
    return out


async def certificate_alerts(
    session: AsyncSession, org: Organization, regs: service.Registers | None, on: date
) -> list[schemas.Alert]:
    """Alerts about the current certificate: ends within 90 days, has ended, or no longer matches the institution;
    and about the current prevention certificate (phase P3b): ends within 90 days or has ended."""
    alerts: list[schemas.Alert] = []
    prevention = await current_of(session, org.id, "prevention")
    if prevention is not None and prevention.valid_until is not None:
        if prevention.valid_until < on:
            alerts.append(schemas.Alert(kind="prevention_expired", ref=prevention.id, since=prevention.valid_until))
        elif (prevention.valid_until - on).days <= domain.CERTIFICATE_REMINDER_DAYS[0]:
            alerts.append(schemas.Alert(kind="prevention_expiring", ref=prevention.id, since=prevention.valid_until))
    cert = await current_of(session, org.id)
    if cert is None or cert.valid_until is None:
        return alerts
    if cert.valid_until < on:
        alerts.append(schemas.Alert(kind="certificate_expired", ref=cert.id, since=cert.valid_until))
    elif (cert.valid_until - on).days <= domain.CERTIFICATE_REMINDER_DAYS[0]:
        alerts.append(schemas.Alert(kind="certificate_expiring", ref=cert.id, since=cert.valid_until))
    if await changes_of(session, org, cert, regs):
        alerts.append(schemas.Alert(kind="certificate_needs_update", ref=cert.id, since=None))
    return alerts


async def renewal_reminders(session: AsyncSession, today: date) -> int:
    """E-mail the admins of each institution whose current certificate ends within 90, then 30 days (once each)."""
    from app.modules.notify import outbox, templates
    from app.modules.orgs.models import Member

    sent = 0
    first, last = domain.CERTIFICATE_REMINDER_DAYS
    rows = await session.execute(
        select(Certificate, Organization)
        .join(Organization, Organization.id == Certificate.org_id)
        .where(
            Certificate.kind == "safety",
            Certificate.status == "approved",
            Certificate.superseded_by.is_(None),
            Organization.status == domain.OrgStatus.ACTIVE,
            Certificate.valid_until >= today,
            Certificate.valid_until <= today + timedelta(days=first),
        )
        .with_for_update(of=Certificate, skip_locked=True)
    )
    for cert, org in rows.all():
        assert cert.valid_until is not None
        days = (cert.valid_until - today).days
        if days <= last and cert.reminded_30_on is None:
            cert.reminded_30_on = today
            cert.reminded_90_on = cert.reminded_90_on or today
        elif cert.reminded_90_on is None:
            cert.reminded_90_on = today
        else:
            continue
        admins = await session.scalars(
            select(Member.email).where(Member.org_id == org.id, Member.role == "admin", Member.email.is_not(None))
        )
        values = {
            "org": org.name,
            "code": cert.code,
            "valid_until": cert.valid_until.isoformat(),
            "days": days,
            "link": f"{get_settings().portal_public_url}/orgs/{org.id}/certificate",
        }
        body = templates.multilingual(templates.fill(templates.RENEWAL_BODY, **values))
        subject = templates.RENEWAL_SUBJECT["ar"].format(**values)
        for address in admins:
            if address:
                outbox.email(session, address, subject, body)
        sent += 1
    await session.flush()
    return sent


# ---------------------------------------------------------------- phase P3a: counter of a regional administration

_CODE = re.compile(r"EH[CP]-\d{2}-\d{2}-\d{6}")
_IMAGE_MAGIC = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG\r\n\x1a\n": "image/png"}


def code_from(raw: str) -> str:
    """The certificate code typed, or read from the QR code (the whole verification URL)."""
    found = _CODE.search(raw.strip().upper())
    if found is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_code")
    return found.group(0)


def counter_reasons(cert: Certificate, org: Organization, on: date) -> list[schemas.CounterReason]:
    reasons: list[schemas.CounterReason] = []
    if cert.status == "revoked":
        reasons.append("revoked")
    elif cert.status != "approved":
        reasons.append("not_approved")
    if cert.superseded_by is not None:
        reasons.append("superseded")
    if cert.valid_until is not None and cert.valid_until < on:
        reasons.append("expired")
    if cert.status in ("approved", "revoked") and not signature_valid(cert):
        reasons.append("signature")
    if org.status != domain.OrgStatus.ACTIVE:
        reasons.append("org_inactive")
    return reasons


async def counter_view(
    session: AsyncSession, cert: Certificate, org: Organization, *, may_stamp: bool
) -> schemas.CounterView:
    on = service.today()
    reasons = counter_reasons(cert, org, on)
    changes = await changes_of(session, org, cert) if is_current(cert) else None
    stamps = (await stamps_of(session, [cert.id]))[cert.id]
    return schemas.CounterView(
        certificate=certificate_out(cert, changes=changes, stamps=stamps),
        valid=not reasons,
        reasons=reasons,
        signature_valid=cert.status in ("approved", "revoked") and signature_valid(cert),
        can_stamp=may_stamp and not reasons,
        org_id=org.id,
        org_name=org.name,
        org_kind=org.kind,
        org_status=org.status,
        org_address=org.address,
        gouvernorat_code=org.gouvernorat_code,
    )


async def scoped_certificate(
    session: AsyncSession, principal: Any, *, code: str | None = None, cert_id: uuid.UUID | None = None
) -> tuple[Certificate, Organization]:
    """A submitted or later certificate of an institution in the staff member's scope (404 otherwise)."""
    query = select(Certificate, Organization).join(Organization, Organization.id == Certificate.org_id)
    query = query.where(Certificate.code == code) if code is not None else query.where(Certificate.id == cert_id)
    found = (await session.execute(query.where(Certificate.status != "draft"))).first()
    if found is None or not service.in_scope(principal, found[1]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return found[0], found[1]


async def add_stamp(
    session: AsyncSession, cert: Certificate, org: Organization, body: schemas.StampIn, actor: str, name: str | None
) -> CertificateStamp:
    on = service.today()
    if counter_reasons(cert, org, on):
        raise HTTPException(status.HTTP_409_CONFLICT, "certificate_not_valid")
    approved_on = cert.reviewed_at.astimezone(TUNIS_TZ).date() if cert.reviewed_at else on
    if body.stamped_on > on or body.stamped_on < approved_on:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_stamp_date")
    changes = await changes_of(session, org, cert)
    stamp = CertificateStamp(
        id=uuid.uuid4(),
        certificate_id=cert.id,
        place=body.place.strip(),
        gouvernorat_code=org.gouvernorat_code,
        stamped_on=body.stamped_on,
        note=body.note.strip() if body.note and body.note.strip() else None,
        stamped_by=actor,
        stamped_by_name=name,
        changes=[c.model_dump(mode="json") for c in changes],
    )
    if not stamp.place:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "place_required")
    session.add(stamp)
    await session.flush()
    await session.refresh(stamp)
    return stamp


def photo_type(data: bytes) -> str:
    """JPEG or PNG, read from the bytes themselves (the declared type is not trusted)."""
    if len(data) > domain.STAMP_PHOTO_MAX_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "photo_too_large")
    for magic, content_type in _IMAGE_MAGIC.items():
        if data.startswith(magic):
            return content_type
    raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported_media_type")


async def set_photo(stamp: CertificateStamp, data: bytes) -> str | None:
    """Store the photo of the stamped paper; returns the replaced object key, to delete after commit."""
    content_type = photo_type(data)
    old = stamp.photo_object_key
    key = f"certificates/{stamp.certificate_id}/stamps/{stamp.id}-{uuid.uuid4().hex[:8]}"
    await get_store().put(key, data, content_type)
    stamp.photo_object_key = key
    stamp.photo_sha256 = hashlib.sha256(data).hexdigest()
    stamp.photo_content_type = content_type
    return old
