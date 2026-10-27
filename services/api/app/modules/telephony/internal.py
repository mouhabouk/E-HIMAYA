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

    sender_key = sms.sender_hash(message.sender).hex()[:32]
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
