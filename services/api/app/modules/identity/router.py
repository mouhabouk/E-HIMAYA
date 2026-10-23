from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import sessions
from app.core.config import get_settings
from app.core.crypto import get_cipher
from app.core.db import get_session
from app.core.security import CurrentPrincipal
from app.modules.audit import service as audit
from app.modules.geo.models import Delegation, Gouvernorat
from app.modules.identity.models import Consent, Profile, phone_index
from app.modules.identity.service import CurrentReporter, Reporter, limit_reporter
from app.modules.moderation import service as moderation

router = APIRouter(prefix="/api/v1", tags=["identity"])

Session = Annotated[AsyncSession, Depends(get_session)]
Locale = Literal["ar", "fr", "en"]
_CIN_CONTEXT = "identity.profile.cin"


class MeOut(BaseModel):
    subject: str
    realm: str
    roles: list[str]
    gouvernorat_code: int | None
    is_staff: bool


@router.get("/me", response_model=MeOut)
async def me(principal: CurrentPrincipal) -> MeOut:
    """Who am I, as seen by the API (identity, roles and geographic scope)."""
    return MeOut(
        subject=principal.subject,
        realm=principal.realm.value,
        roles=sorted(r.value for r in principal.roles),
        gouvernorat_code=principal.gouvernorat_code,
        is_staff=principal.is_staff,
    )


@router.post("/me/sign-out-everywhere", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out_everywhere(principal: CurrentPrincipal) -> None:
    """Refuse every token issued to the caller until now, on every device (phase 10 §1.2)."""
    await sessions.revoke(principal.subject)


# ---------------------------------------------------------------- profile (FR-A-005)


BloodGroup = Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]


class MedicalInfo(BaseModel):
    """Optional data shown to responders (stored encrypted, never searchable)."""

    blood_group: BloodGroup | None = None
    conditions: str | None = Field(default=None, max_length=500)
    allergies: str | None = Field(default=None, max_length=300)
    medications: str | None = Field(default=None, max_length=300)
    emergency_contact_name: str | None = Field(default=None, max_length=100)
    emergency_contact_phone: str | None = Field(default=None, pattern=r"^\+216\d{8}$")


class ProfileIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    cin: str = Field(pattern=r"^\d{8}$", description="Tunisian national ID card number (8 digits)")
    phone: str = Field(pattern=r"^\+216\d{8}$")
    gouvernorat_code: int
    delegation_id: int
    address: str | None = Field(default=None, max_length=300)
    locale: Locale = "ar"
    # Left out: unchanged; null: erased. Phase B2: a non-empty value answers 410 (the medical file is on the phone).
    medical: MedicalInfo | None = None


class ProfileOut(BaseModel):
    first_name: str | None
    last_name: str | None
    cin_last4: str | None
    phone: str | None
    email: str | None
    gouvernorat_code: int | None
    delegation_id: int | None
    address: str | None
    locale: str
    medical: MedicalInfo | None = None


def _registered(reporter: Reporter) -> Reporter:
    if reporter.principal is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "registration_required")
    return reporter


def _profile_out(profile: Profile | None, email: str | None, verified_phone: str | None = None) -> ProfileOut:
    if profile is None:
        return ProfileOut(
            first_name=None,
            last_name=None,
            cin_last4=None,
            phone=verified_phone,
            email=email,
            gouvernorat_code=None,
            delegation_id=None,
            address=None,
            locale="ar",
        )
    cin_last4 = get_cipher().decrypt(profile.cin_enc, context=_CIN_CONTEXT)[-4:] if profile.cin_enc else None
    return ProfileOut(
        first_name=profile.first_name,
        last_name=profile.last_name,
        cin_last4=cin_last4,
        phone=profile.phone or verified_phone,
        email=profile.email or email,
        gouvernorat_code=profile.gouvernorat_code,
        delegation_id=profile.delegation_id,
        address=profile.address,
        locale=profile.locale,
        medical=MedicalInfo.model_validate(profile.medical) if profile.medical else None,
    )


def _token_email(reporter: Reporter) -> str | None:
    assert reporter.principal is not None
    email = reporter.principal.claims.get("email")
    return str(email) if email else None


def _token_phone(reporter: Reporter) -> str | None:
    """The phone number Keycloak verified by SMS code (phase A sign-in by phone), if any."""
    assert reporter.principal is not None
    claims = reporter.principal.claims
    phone = claims.get("phone_number")
    verified = claims.get("phone_number_verified") in (True, "true")
    return str(phone) if phone and verified else None


@router.get("/me/profile", response_model=ProfileOut)
async def get_profile(reporter: CurrentReporter, session: Session) -> ProfileOut:
    _registered(reporter)
    profile = await session.get(Profile, reporter.user_id)
    return _profile_out(profile, _token_email(reporter), _token_phone(reporter))


@router.put("/me/profile", response_model=ProfileOut)
async def put_profile(body: ProfileIn, reporter: CurrentReporter, session: Session) -> ProfileOut:
    _registered(reporter)
    assert reporter.principal is not None
    if await session.get(Gouvernorat, body.gouvernorat_code) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown_gouvernorat")
    delegation = await session.get(Delegation, body.delegation_id)
    if delegation is None or delegation.gouvernorat_code != body.gouvernorat_code:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "delegation_mismatch")
    # Rule 4: names and address are not emergency text, the respectful-language filter applies.
    await moderation.check(session, body.first_name, body.last_name, body.address)

    cipher = get_cipher()
    claims = reporter.principal.claims
    email = _token_email(reporter)
    now = datetime.now(UTC)
    profile = await session.get(Profile, reporter.user_id) or Profile(user_id=reporter.user_id)
    profile.first_name = body.first_name.strip()
    profile.last_name = body.last_name.strip()
    profile.cin_enc = cipher.encrypt(body.cin, context=_CIN_CONTEXT)
    profile.cin_hash = cipher.blind_index(body.cin, context=_CIN_CONTEXT)
    verified_phone = _token_phone(reporter)
    if profile.phone != body.phone:
        profile.phone = body.phone
        profile.phone_hash = phone_index(body.phone)
        profile.phone_verified_at = None
    if body.phone == verified_phone and profile.phone_verified_at is None:
        # Signed in with this number and the SMS code (phase A): the number is proven.
        profile.phone_verified_at = now
    profile.email = email
    profile.email_verified_at = now if email and claims.get("email_verified") else None
    profile.gouvernorat_code = body.gouvernorat_code
    profile.delegation_id = body.delegation_id
    profile.address = body.address.strip() if body.address else None
    profile.locale = body.locale
    if "medical" in body.model_fields_set:
        # Phase B2 (addition 7b): the medical file lives on the phone only. A file stored here before can still be
        # read (profile, "my data") and erased with ``medical: null``, never written again.
        if body.medical is not None and body.medical.model_dump(exclude_none=True):
            raise HTTPException(status.HTTP_410_GONE, "medical_moved_to_phone")
        profile.medical = None
    profile.updated_at = now
    session.add(profile)
    try:
        await audit.record(session, actor=reporter.actor, action="profile.update", target=f"account:{reporter.user_id}")
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "cin_already_registered") from exc
    return _profile_out(profile, email, verified_phone)


# ---------------------------------------------------------------- charter consent (FR-A-001)


class CharterOut(BaseModel):
    version: str


class ConsentIn(BaseModel):
    charter_version: str = Field(max_length=32)
    locale: Locale
    platform: Literal["android", "ios", "web"]


class ConsentOut(BaseModel):
    charter_version: str
    accepted_at: datetime


@router.get("/charter", response_model=CharterOut)
async def charter() -> CharterOut:
    return CharterOut(version=get_settings().charter_version)


@router.post("/consents", response_model=ConsentOut, status_code=status.HTTP_201_CREATED)
async def accept_charter(request: Request, body: ConsentIn, reporter: CurrentReporter, session: Session) -> ConsentOut:
    settings = get_settings()
    await limit_reporter(
        request, reporter, "consent", per_account=10, per_ip=settings.anon_consent_per_ip, window_s=3600
    )
    if body.charter_version != get_settings().charter_version:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown_charter_version")
    existing = await session.scalar(
        select(Consent).where(
            Consent.user_id == reporter.user_id,
            Consent.purpose == "charter",
            Consent.charter_version == body.charter_version,
        )
    )
    if existing is not None:
        return ConsentOut(charter_version=existing.charter_version, accepted_at=existing.accepted_at)
    consent = Consent(
        user_id=reporter.user_id, charter_version=body.charter_version, locale=body.locale, platform=body.platform
    )
    session.add(consent)
    await session.flush()
    await session.refresh(consent)
    await session.commit()
    return ConsentOut(charter_version=consent.charter_version, accepted_at=consent.accepted_at)
