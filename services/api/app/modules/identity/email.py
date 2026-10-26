"""A work e-mail confirmed by code (phase P5b, F-APP-12, docs/phase-p5/design-simple.md §2.4).

An account signed in with a phone number and an SMS code (phase A) has no e-mail proven by the identity provider, and
registering an institution needs one (``email_not_verified``). The app asks for the address, the API sends a 6-digit
code valid 10 minutes, and the code confirms it:

* ``GET /api/v1/me/email``: the address the account may use for an institution and whether it is proven, by the
  identity provider (``account``) or by a code (``code``).
* ``POST /api/v1/me/email/code``: sends a code (5 per hour per account). Only an HMAC of the code is kept.
* ``POST /api/v1/me/email/verify``: 5 attempts per code; a wrong code returns ``invalid_code``, an expired or spent one
  ``code_expired``.
"""

import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import get_cipher
from app.core.db import get_session
from app.core.ratelimit import enforce
from app.modules.audit import service as audit
from app.modules.identity.models import EmailCode
from app.modules.identity.service import CurrentReporter, Reporter
from app.modules.notify import outbox

router = APIRouter(prefix="/api/v1/me/email", tags=["identity"])
Session = Annotated[AsyncSession, Depends(get_session)]

CODE_TTL = timedelta(minutes=10)
ATTEMPTS = 5
CODES_PER_HOUR = 5
_CODE_CONTEXT = "identity.email_code.code"

_SUBJECT = {
    "ar": "رمز تأكيد البريد: ء-حماية",
    "fr": "Code de confirmation de l'e-mail : e-Himaya",
    "en": "E-mail confirmation code: e-Himaya",
}
_BODY = {
    "ar": "رمز تأكيد بريدك في تطبيق ء-حماية: {code}\nصالح 10 دقائق. إن لم تطلبه، تجاهل هذه الرسالة.",
    "fr": "Votre code de confirmation e-Himaya : {code}\nValable 10 minutes. Si vous ne l'avez pas demandé, ignorez ce "
    "message.",
    "en": "Your e-Himaya confirmation code: {code}\nValid for 10 minutes. If you did not ask for it, ignore this "
    "message.",
}


class EmailOut(BaseModel):
    email: str | None
    verified: bool
    # Who proved it: the identity provider, or a code sent by the API.
    source: Literal["account", "code"] | None


class CodeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    locale: Literal["ar", "fr", "en"] = "ar"


class CodeOut(BaseModel):
    sent: bool
    expires_at: datetime


class VerifyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{6}$")]


def _registered(reporter: Reporter) -> Reporter:
    if reporter.principal is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "registration_required")
    return reporter


def _token_email(reporter: Reporter) -> tuple[str | None, bool]:
    assert reporter.principal is not None
    claims = reporter.principal.claims
    email = claims.get("email")
    return (str(email).lower() if email else None), bool(claims.get("email_verified")) and bool(email)


def _digest(reporter: Reporter, email: str, code: str) -> bytes:
    return get_cipher().blind_index(f"{reporter.user_id}:{email}:{code}", context=_CODE_CONTEXT)


async def confirmed_email(session: AsyncSession, reporter: Reporter) -> str | None:
    """The address this account confirmed by code, if any."""
    row = await session.get(EmailCode, reporter.user_id)
    return row.email if row is not None and row.verified_at is not None else None


@router.get("", response_model=EmailOut)
async def my_email(reporter: CurrentReporter, session: Session) -> EmailOut:
    _registered(reporter)
    email, verified = _token_email(reporter)
    if verified:
        return EmailOut(email=email, verified=True, source="account")
    confirmed = await confirmed_email(session, reporter)
    if confirmed is not None:
        return EmailOut(email=confirmed, verified=True, source="code")
    return EmailOut(email=email, verified=False, source=None)


@router.post("/code", response_model=CodeOut)
async def send_code(reporter: CurrentReporter, session: Session, body: CodeIn) -> CodeOut:
    _registered(reporter)
    await enforce(f"email-code:{reporter.user_id}", CODES_PER_HOUR, 3600)
    email = str(body.email).lower()
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = datetime.now(UTC)
    row = await session.get(EmailCode, reporter.user_id) or EmailCode(user_id=reporter.user_id)
    # A new address replaces the confirmed one only once its own code is given.
    if row.verified_at is not None and row.email != email:
        row.verified_at = None
    row.email = email
    row.code_hmac = _digest(reporter, email, code)
    row.expires_at = now + CODE_TTL
    row.attempts_left = ATTEMPTS
    row.updated_at = now
    session.add(row)
    outbox.email(session, email, _SUBJECT[body.locale], _BODY[body.locale].format(code=code))
    await audit.record(session, actor=reporter.actor, action="email.code_sent", target=f"account:{reporter.user_id}")
    await session.commit()
    return CodeOut(sent=True, expires_at=row.expires_at)


@router.post("/verify", response_model=EmailOut)
async def verify_code(reporter: CurrentReporter, session: Session, body: VerifyIn) -> EmailOut:
    _registered(reporter)
    row = await session.get(EmailCode, reporter.user_id, with_for_update=True)
    now = datetime.now(UTC)
    if row is None or row.code_hmac is None or row.expires_at is None or row.expires_at <= now:
        raise HTTPException(status.HTTP_409_CONFLICT, "code_expired")
    if row.attempts_left <= 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "code_expired")
    if not hmac.compare_digest(row.code_hmac, _digest(reporter, row.email, body.code)):
        row.attempts_left -= 1
        row.updated_at = now
        await session.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_code")
    row.verified_at = now
    row.code_hmac = None
    row.expires_at = None
    row.updated_at = now
    await audit.record(session, actor=reporter.actor, action="email.verified", target=f"account:{reporter.user_id}")
    await session.commit()
    return EmailOut(email=row.email, verified=True, source="code")
