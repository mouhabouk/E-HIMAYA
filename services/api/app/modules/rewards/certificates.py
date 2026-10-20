"""Reward certificates (FR-A-072, FR-C-20): signed PDF of a confirmed gold/ambassador badge or an approved nomination.

Same approach as the phase 4 safety certificate (app/modules/orgs/certificate.py): a code numbered per year, an
Ed25519 signature with the platform's certificate key (CERTIFICATE_SIGNING_KEY) over
``<code>|<distinction>|<initials>|<issued ISO date>``, a bilingual (ar/fr) WeasyPrint PDF stored in S3 and a QR code
pointing at the public verification endpoint. The public view discloses the name initials, the distinction and the
date only; the PDF itself (full name) is handed to its holder and to staff.

The code ends with 4 random hex digits so certificates cannot be enumerated by counting.
"""

import base64
import hashlib
import html
import secrets
import uuid
from datetime import date

import segno
from anyio import to_thread
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.storage import get_store
from app.modules.identity.models import Profile
from app.modules.orgs.models import Organization
from app.modules.rewards.domain import CERTIFIED_LEVELS, DISTINCTION_LABELS, BadgeStatus, Level, SubjectKind, initials
from app.modules.rewards.models import BadgeAward, Nomination, RewardCertificate
from app.modules.rewards.service import TUNIS_TZ, now_utc

PDF_TYPE = "application/pdf"
CODE_PATTERN = r"^EHR-[0-9]{2}-[0-9]{6}-[0-9A-F]{4}$"


def _private_key() -> Ed25519PrivateKey | None:
    secret = get_settings().certificate_signing_key
    if secret is None:
        return None
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(secret.get_secret_value()))


def signed_message(code: str, distinction: str, holder_initials: str, issued_on: date) -> bytes:
    return f"{code}|{distinction}|{holder_initials}|{issued_on.isoformat()}".encode()


def issued_on(cert: RewardCertificate) -> date:
    return cert.issued_at.astimezone(TUNIS_TZ).date()


def signature_valid(cert: RewardCertificate) -> bool:
    key = _private_key()
    if key is None:
        return False
    try:
        key.public_key().verify(
            cert.signature, signed_message(cert.code, cert.distinction, cert.initials, issued_on(cert))
        )
    except InvalidSignature:
        return False
    return True


def verify_url(code: str) -> str:
    return f"{get_settings().api_public_url}/api/v1/rewards/certificates/{code}"


async def next_code(session: AsyncSession) -> str:
    year = now_utc().astimezone(TUNIS_TZ).year
    number = await session.scalar(
        text(
            "INSERT INTO rewards.certificate_counter (year, last) VALUES (:year, 1) "
            "ON CONFLICT (year) DO UPDATE SET last = rewards.certificate_counter.last + 1 RETURNING last"
        ),
        {"year": year},
    )
    return f"EHR-{year % 100:02d}-{int(number or 0):06d}-{secrets.token_hex(2).upper()}"


# ---------------------------------------------------------------- holder


async def _holder(
    session: AsyncSession, subject_kind: str, subject_id: uuid.UUID | None
) -> tuple[str | None, str, int | None]:
    """(full name for the PDF, initials for the public view, gouvernorat) of a certificate's holder."""
    if subject_id is None:
        return None, "—", None
    if subject_kind == "org":
        org = await session.get(Organization, subject_id)
        if org is None:
            return None, "—", None
        return org.name, initials(*org.name.split()[:3]), org.gouvernorat_code
    profile = await session.get(Profile, subject_id)
    if profile is None:
        return None, "—", None
    full = " ".join(p for p in (profile.first_name, profile.last_name) if p) or None
    return full, initials(profile.first_name, profile.last_name), profile.gouvernorat_code


# ---------------------------------------------------------------- PDF

_CSS = """
@page { size: A4 landscape; margin: 14mm; }
body { font-family: "Noto Naskh Arabic", "Noto Sans Arabic", "Noto Sans", "DejaVu Sans", sans-serif;
  color: #1b1b1b; font-size: 11pt; }
.frame { border: 4px double #b71c1c; padding: 10mm 12mm; height: 160mm; position: relative; }
.head { display: flex; justify-content: space-between; border-bottom: 2px solid #b71c1c; padding-bottom: 4mm; }
.ar { direction: rtl; text-align: right; } .fr { direction: ltr; text-align: left; }
h1 { font-size: 22pt; margin: 6mm 0 2mm; color: #b71c1c; text-align: center; }
.name { font-size: 20pt; font-weight: bold; text-align: center; margin: 6mm 0; }
.distinction { font-size: 15pt; text-align: center; }
.bi { display: flex; gap: 10mm; margin-top: 6mm; } .bi > div { flex: 1; }
.foot { position: absolute; bottom: 8mm; left: 12mm; right: 12mm; display: flex; justify-content: space-between;
  align-items: flex-end; }
.qr img { width: 30mm; height: 30mm; }
.mono { font-family: "DejaVu Sans Mono", monospace; font-size: 7.5pt; word-break: break-all; direction: ltr; }
.small { font-size: 8pt; color: #555; }
"""


def _e(value: object) -> str:
    return html.escape("" if value is None else str(value))


def render_html(cert: RewardCertificate, full_name: str | None) -> str:
    label = DISTINCTION_LABELS[cert.distinction]
    url = verify_url(cert.code)
    qr = segno.make(url, error="m").svg_data_uri(scale=4, border=1)
    when = issued_on(cert)
    holder = full_name or cert.initials
    return f"""<!doctype html><html lang="ar"><head><meta charset="utf-8"><style>{_CSS}</style></head><body>
<div class="frame">
  <div class="head">
    <div class="fr"><b>e-Himaya</b><br>Protection civile</div>
    <div class="ar"><b>منصة ء-حماية</b><br>الحماية المدنية</div>
  </div>
  <h1>شهادة تقدير · Certificat de reconnaissance</h1>
  <div class="name">{_e(holder)}</div>
  <div class="distinction"><span class="ar">{_e(label["ar"])}</span> · <span class="fr">{_e(label["fr"])}</span>
    — {_e(cert.year)}</div>
  <div class="bi">
    <div class="ar"><p>تقديرا لمساهمته في حماية الأرواح والممتلكات ولروح المواطنة التي أبداها.</p>
      <p class="small">شهادة شرفية لا قيمة مالية لها.</p></div>
    <div class="fr"><p>En reconnaissance de sa contribution à la protection des personnes et des biens et de son
      esprit civique.</p><p class="small">Distinction honorifique sans valeur pécuniaire.</p></div>
  </div>
  <div class="foot">
    <div class="fr small">Code / الرمز : <b class="mono" style="font-size:10pt">{_e(cert.code)}</b><br>
      Délivré le / حُرّر في : {_e(when.isoformat())}<br>
      Vérification / التحقق : <span class="mono">{_e(url)}</span><br>
      Signature Ed25519 : <span class="mono">{_e(base64.b64encode(cert.signature).decode())}</span></div>
    <div class="qr"><img src="{qr}" alt="QR"></div>
  </div>
</div>
</body></html>"""


def _render_pdf_sync(document: str) -> bytes:
    from weasyprint import HTML

    pdf: bytes = HTML(string=document).write_pdf()
    return pdf


async def store_pdf(cert: RewardCertificate, full_name: str | None) -> None:
    data = await to_thread.run_sync(_render_pdf_sync, render_html(cert, full_name))
    key = f"rewards/certificates/{cert.id}.pdf"
    await get_store().put(key, data, PDF_TYPE)
    cert.pdf_object_key = key
    cert.pdf_sha256 = hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------- issue and revoke


async def issue(
    session: AsyncSession,
    actor: str,
    *,
    badge: BadgeAward | None = None,
    nomination: Nomination | None = None,
) -> RewardCertificate:
    """Certificate of a confirmed gold/ambassador badge or an approved nomination (one per source)."""
    key = _private_key()
    if key is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "signing_key_missing")
    subject_kind: SubjectKind
    if badge is not None:
        if badge.status != BadgeStatus.CONFIRMED.value or Level(badge.level) not in CERTIFIED_LEVELS:
            raise HTTPException(status.HTTP_409_CONFLICT, "not_eligible")
        kind, distinction, subject_kind, subject_id = "badge", badge.level, "citizen", badge.citizen_id
        year = badge.awarded_at.astimezone(TUNIS_TZ).year
    else:
        assert nomination is not None
        if nomination.status != "approved" or nomination.subject_id is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "not_eligible")
        kind, distinction, year = "nomination", nomination.kind, nomination.year
        subject_kind, subject_id = nomination.subject_kind, nomination.subject_id  # type: ignore[assignment]
    full_name, holder_initials, gouvernorat = await _holder(session, subject_kind, subject_id)
    now = now_utc()
    cert = RewardCertificate(
        id=uuid.uuid4(),
        code=await next_code(session),
        kind=kind,
        badge_award_id=badge.id if badge is not None else None,
        nomination_id=nomination.id if nomination is not None else None,
        subject_kind=subject_kind,
        subject_id=subject_id,
        gouvernorat_code=gouvernorat,
        distinction=distinction,
        initials=holder_initials,
        year=year,
        issued_at=now,
        issued_by=actor,
    )
    cert.signature = key.sign(signed_message(cert.code, distinction, holder_initials, issued_on(cert)))
    await store_pdf(cert, full_name)
    session.add(cert)
    await session.flush()
    return cert


def revoke(cert: RewardCertificate, actor: str, reason: str) -> None:
    if cert.revoked_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_revoked")
    cert.revoked_at, cert.revoked_by, cert.revoked_reason = now_utc(), actor, reason
