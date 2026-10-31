"""Internal endpoints of telephony, never routed by Caddy (``/internal/*`` answers 404 at the edge).

* ``POST /internal/sms/inbound`` — SMS gateway webhook (FR-A-048, and since phase P4d the staff app's signed ``EH2``
  messages, ``ops.crew_sms``). Signed: ``X-Timestamp`` (unix seconds, at most
  5 minutes old) and ``X-Signature: sha256=<hex>`` = HMAC-SHA256(SMS_INBOUND_SECRET, "<timestamp>.<raw body>").
  Answers 404 while SMS_INBOUND_SECRET is unset, 401 on a bad signature, and 200 with the outcome otherwise (a
  malformed SMS is "ignored", never an error the gateway would retry forever).
* SIMULATION ``GET /internal/sim/calls`` — the latest source=sim calls (smoke test), ``X-Sim-Token``; 404 unless
  TELEPHONY_SIM_TOKEN is set (never in production).
"""

import hashlib
import hmac
import time
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import ratelimit
from app.core.config import get_settings
from app.core.db import get_system_session
from app.modules.notify.providers import get_providers
from app.modules.ops import crew_sms
from app.modules.streams.internal import _secret_matches
from app.modules.telephony import schemas, sms
from app.modules.telephony.domain import Source, normalize_caller
from app.modules.telephony.models import Call
from app.modules.volunteers import callout_sms

log = structlog.get_logger()
router = APIRouter(include_in_schema=False)
Session = Annotated[AsyncSession, Depends(get_system_session)]

SIGNATURE_MAX_AGE_S = 300
MAX_BODY_BYTES = 16 * 1024
# SMS reports per sender number per hour; beyond, messages are ignored (abuse, loops between gateways).
SMS_PER_SENDER_PER_HOUR = 10
# A team leader's phone without internet: a few steps and alerts per mission, a busy shift has many missions.
CREW_SMS_PER_SENDER_PER_HOUR = 60


def signature(secret: str, timestamp: str, body: bytes) -> str:
    mac = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return f"sha256={mac}"


def _check_signature(timestamp: str | None, presented: str | None, body: bytes) -> None:
    secret = get_settings().sms_inbound_secret
    if secret is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if not timestamp or not presented or not timestamp.isdigit():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_signature")
    if abs(time.time() - int(timestamp)) > SIGNATURE_MAX_AGE_S:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_signature")
    expected = signature(secret.get_secret_value(), timestamp, body)
    if not hmac.compare_digest(expected.encode(), presented.strip().encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_signature")


@router.post("/internal/sms/inbound", response_model=schemas.SmsInboundOut)
async def sms_inbound(
    request: Request,
    session: Session,
    x_timestamp: Annotated[str | None, Header(max_length=20)] = None,
    x_signature: Annotated[str | None, Header(max_length=100)] = None,
) -> schemas.SmsInboundOut:
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "too_large")
    _check_signature(x_timestamp, x_signature, body)
    try:
        message = schemas.SmsInboundIn.model_validate_json(body)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_body") from exc

    return await _receive(session, message)


async def _receive(session: AsyncSession, message: schemas.SmsInboundIn) -> schemas.SmsInboundOut:
    """One received SMS, whichever gateway brought it: a team's step (EH2) or a citizen's report (EH1)."""
    sender_key = sms.sender_hash(message.sender).hex()[:32]
    if callout_sms.is_callout_sms(message.text):
        verdict = await ratelimit.check(f"callout-sms-in:{sender_key}", CREW_SMS_PER_SENDER_PER_HOUR, 3600)
        if verdict.exceeded:
            return schemas.SmsInboundOut(status="ignored", reason="rate_limited")
        answer = await callout_sms.receive(session, message.text)
        await session.commit()
        log.info("callout_sms.inbound", outcome=answer.status, reason=answer.reason)
        return schemas.SmsInboundOut(status=answer.status, reason=answer.reason)
    if crew_sms.is_crew_sms(message.text):
        verdict = await ratelimit.check(f"crew-sms-in:{sender_key}", CREW_SMS_PER_SENDER_PER_HOUR, 3600)
        if verdict.exceeded:
            log.warning("crew_sms.rate_limited")
            return schemas.SmsInboundOut(status="ignored", reason="rate_limited")
        crew_outcome = await crew_sms.receive(session, message.text)
        await session.commit()
        log.info("crew_sms.inbound", outcome=crew_outcome.status, reason=crew_outcome.reason)
        return schemas.SmsInboundOut(status=crew_outcome.status, reason=crew_outcome.reason)
    verdict = await ratelimit.check(f"sms-in:{sender_key}", SMS_PER_SENDER_PER_HOUR, 3600)
    if verdict.exceeded:
        log.warning("sms.rate_limited")
        return schemas.SmsInboundOut(status="ignored", reason="rate_limited")

    outcome = await sms.receive(session, message.message_id, message.sender, message.text, message.received_at)
    await session.commit()
    tracking = outcome.report.tracking_code if outcome.report is not None else None
    log.info("sms.inbound", outcome=outcome.status, reason=outcome.reason)
    if outcome.status == "created" and tracking:
        # Best effort: the citizen gets the tracking code back (no retry; the report exists either way).
        number = normalize_caller(message.sender)
        if number:
            result = await get_providers().sms.send(number, sms.reply_text(tracking))
            if not result.ok:
                log.warning("sms.reply_failed", error=result.error)
    return schemas.SmsInboundOut(status=outcome.status, tracking_code=tracking, reason=outcome.reason)


# ---------------------------------------------------------------- demonstration
# ┏━━ DEMONSTRATION ━━ an Android phone with a SIM card as the gateway (docs/sms-phone-gateway.md): the app
# ┃   "SMS Gateway for Android" (Apache-2.0) posts its "sms:received" webhook here, signed with its signing key.
# ┃ PRODUCTION: the operators' gateway on /internal/sms/inbound; SMS_PHONE_SIGNING_KEY empty and this answers 404.
# ┗━━━━━━━━━━━━━━━━


def phone_signature(key: str, timestamp: str, body: bytes) -> str:
    """The app's signature: hex HMAC-SHA256 of the raw body followed by the timestamp."""
    return hmac.new(key.encode(), body + timestamp.encode(), hashlib.sha256).hexdigest()


@router.post("/internal/sms/phone", response_model=schemas.SmsInboundOut)
async def sms_phone(
    request: Request,
    session: Session,
    x_timestamp: Annotated[str | None, Header(max_length=20)] = None,
    x_signature: Annotated[str | None, Header(max_length=100)] = None,
) -> schemas.SmsInboundOut:
    key = get_settings().sms_phone_signing_key
    if key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "too_large")
    if not x_timestamp or not x_signature or not x_timestamp.isdigit():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_signature")
    if abs(time.time() - int(x_timestamp)) > SIGNATURE_MAX_AGE_S:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_signature")
    expected = phone_signature(key.get_secret_value(), x_timestamp, body)
    if not hmac.compare_digest(expected.encode(), x_signature.strip().lower().encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_signature")
    try:
        hook = schemas.PhoneWebhookIn.model_validate_json(body)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_body") from exc
    if hook.event != "sms:received" or hook.payload is None:
        # Other events of the app (sent, delivered, ping): answered so that the phone does not retry them.
        return schemas.SmsInboundOut(status="ignored", reason="not_a_received_sms")
    try:
        received = schemas.PhoneSms.model_validate(hook.payload)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_body") from exc
    message = schemas.SmsInboundIn.model_validate(
        {
            "message_id": f"phone:{received.message_id}",
            "from": received.sender,
            "to": received.recipient,
            "text": received.message,
        }
    )
    return await _receive(session, message)


# ---------------------------------------------------------------- simulation
# ┏━━ SIMULATION ━━ the smoke test places a call into 8000 inside the telephony container (source=sim) and reads
# ┃   its state here. Every call listed carries "simulated": true.
# ┃ PRODUCTION: leave TELEPHONY_SIM_TOKEN empty (APP_ENV=production refuses it) and this endpoint answers 404.
# ┗━━━━━━━━━━━━━━━━


@router.get("/internal/sim/calls", response_model=schemas.SimCallList)
async def sim_calls(
    session: Session,
    x_sim_token: Annotated[str | None, Header(max_length=512)] = None,
) -> schemas.SimCallList:
    settings = get_settings()
    if settings.app_env == "production" or not _secret_matches(x_sim_token or "", settings.telephony_sim_token):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    rows = await session.scalars(
        select(Call).where(Call.source == Source.SIM).order_by(Call.started_at.desc()).limit(20)
    )
    return schemas.SimCallList(
        items=[
            schemas.SimCall(
                id=c.id,
                status=c.status,
                end_reason=c.end_reason,
                recording_state=c.recording_state,
                recording_media_id=c.recording_media_id,
                started_at=c.started_at,
                simulated=True,
            )
            for c in rows
        ],
        simulated=True,
    )
