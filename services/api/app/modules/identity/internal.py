"""Internal endpoint of the phone sign-in (phase A, docs/phase-a/design.md §2.2), never routed by Caddy.

``POST /internal/auth/otp-sms``: the Keycloak provider ``ehimaya-phone-otp`` asks the API to send a sign-in code by
SMS through the national SMS provider (in development the ``[SIM]`` gateway notify-sim). Keycloak keeps the code
(hashed) and checks it; the API only renders the text in the user's language and sends it, and never stores it.

Signed like the SMS gateway webhook: ``X-Timestamp`` (unix seconds, at most 5 minutes old) and
``X-Signature: sha256=<hex>`` = HMAC-SHA256(OTP_SMS_SECRET, "<timestamp>.<raw body>"). 404 while OTP_SMS_SECRET is
unset, 401 on a bad signature, 429 beyond the per-number limit, 503 when no SMS provider is configured and 502 when
the provider refused the message.
"""

import hashlib
import hmac
import time
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field, ValidationError

from app.core import ratelimit
from app.core.config import get_settings
from app.modules.notify.providers import get_providers, sms_simulated

log = structlog.get_logger()
router = APIRouter(include_in_schema=False)

SIGNATURE_MAX_AGE_S = 300
MAX_BODY_BYTES = 1024
# Keycloak allows 5 codes per number per hour; one more here so the two limits never disagree by a clock tick.
CODES_PER_NUMBER_PER_HOUR = 6

TEXTS = {
    "ar": "رمز الدخول إلى ء-حماية: {code}. صالح 5 دقائق. لا تعطه لأي شخص.",
    "fr": "Code de connexion e-Himaya : {code}. Valable 5 minutes. Ne le communiquez à personne.",
    "en": "e-Himaya sign-in code: {code}. Valid for 5 minutes. Never share it.",
}


class OtpSmsIn(BaseModel):
    # Tunisian mobile numbers: +216 then 8 digits starting with 2, 3, 4, 5 or 9.
    phone: str = Field(pattern=r"^\+216[23459]\d{7}$")
    code: str = Field(pattern=r"^\d{6}$")
    locale: Literal["ar", "fr", "en"] = "ar"


class OtpSmsOut(BaseModel):
    sent: bool
    # SIMULATION: true while SMS go to notify-sim (development); the app then shows a [SIM] strip.
    simulated: bool


def signature(secret: str, timestamp: str, body: bytes) -> str:
    mac = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return f"sha256={mac}"


def _check_signature(timestamp: str | None, presented: str | None, body: bytes) -> None:
    secret = get_settings().otp_sms_secret
    if secret is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if not timestamp or not presented or not timestamp.isdigit():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_signature")
    if abs(time.time() - int(timestamp)) > SIGNATURE_MAX_AGE_S:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_signature")
    expected = signature(secret.get_secret_value(), timestamp, body)
    if not hmac.compare_digest(expected.encode(), presented.strip().encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_signature")


@router.post("/internal/auth/otp-sms", response_model=OtpSmsOut)
async def otp_sms(
    request: Request,
    x_timestamp: Annotated[str | None, Header(max_length=20)] = None,
    x_signature: Annotated[str | None, Header(max_length=100)] = None,
) -> OtpSmsOut:
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "too_large")
    _check_signature(x_timestamp, x_signature, body)
    try:
        message = OtpSmsIn.model_validate_json(body)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_body") from exc

    number_key = hashlib.sha256(message.phone.encode()).hexdigest()[:32]
    verdict = await ratelimit.check(f"otp-sms:{number_key}", CODES_PER_NUMBER_PER_HOUR, 3600)
    if verdict.exceeded:
        log.warning("otp_sms.rate_limited")
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited")

    sms = get_providers().sms
    if not sms.configured:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "sms_unavailable")
    result = await sms.send(message.phone, TEXTS[message.locale].format(code=message.code))
    if not result.ok:
        log.warning("otp_sms.failed", error=result.error)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "sms_failed")
    # Never log the number or the code.
    log.info("otp_sms.sent", locale=message.locale)
    return OtpSmsOut(sent=True, simulated=sms_simulated())
