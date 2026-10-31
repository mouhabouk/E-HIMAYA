"""A volunteer (a doctor among them) answers a call-out by SMS when there is no internet (phase D, S2-5).

The citizen app opens the SMS app with a ready message to the platform's number (the same as the citizens' ``EH1``
reports and the teams' ``EH2`` steps) and the volunteer presses Send; the gateway posts it to
``POST /internal/sms/inbound``:

``EH3 <volunteer> <callout> <reply> <eta> <unix time> <signature>``

* ``volunteer`` and ``callout``: 32 hex digits each (UUIDs without dashes);
* ``reply``: ``accept`` («قبلت», with the minutes to arrive), ``decline`` («أعتذر»), ``arrived`` («وصلت»);
* ``eta``: minutes to arrive for ``accept`` (1 to 600), ``0`` otherwise;
* ``signature``: the first 16 hex digits of HMAC-SHA256(the volunteer's key, ``EH3|volunteer|callout|reply|eta|time``).
  The key is the volunteer's own (``POST /api/v1/me/volunteer/sms-key``), encrypted at rest on both sides.

A message is applied as the app's answer would be. A wrong signature, a message older than 12 hours, or not newer
than the last one applied (a replay) is ignored, never an error the gateway would retry.
"""

import hashlib
import hmac
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import structlog
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, Realm, Role
from app.modules.audit import service as audit
from app.modules.identity.models import Account, AccountKind
from app.modules.identity.service import Reporter
from app.modules.ops import interventions
from app.modules.ops.models import Callout, Incident
from app.modules.volunteers.models import Volunteer

log = structlog.get_logger()

_BODY = re.compile(
    r"^\s*EH3\s+(?P<volunteer>[0-9a-f]{32})\s+(?P<callout>[0-9a-f]{32})\s+(?P<reply>accept|decline|arrived)\s+"
    r"(?P<eta>\d{1,3})\s+(?P<ts>\d{9,11})\s+(?P<sig>[0-9a-f]{16})\s*$",
    re.IGNORECASE,
)
MAX_AGE = timedelta(hours=12)
CLOCK_SKEW = timedelta(minutes=5)

Reply = Literal["accept", "decline", "arrived"]


@dataclass(frozen=True)
class CalloutSms:
    volunteer_id: uuid.UUID
    callout_id: uuid.UUID
    reply: Reply
    eta: int
    at: datetime
    signed: str
    signature: str


@dataclass(frozen=True)
class Outcome:
    status: Literal["applied", "ignored"]
    reason: str | None = None


def is_callout_sms(text: str) -> bool:
    return (text or "").lstrip()[:4].upper() == "EH3 "


def parse(text: str) -> CalloutSms | None:
    m = _BODY.match(text or "")
    if m is None:
        return None
    g = {k: v.lower() for k, v in m.groupdict().items()}
    signed = "|".join(("EH3", g["volunteer"], g["callout"], g["reply"], g["eta"], g["ts"]))
    reply: Reply = g["reply"]  # type: ignore[assignment]
    return CalloutSms(
        volunteer_id=uuid.UUID(g["volunteer"]),
        callout_id=uuid.UUID(g["callout"]),
        reply=reply,
        eta=int(g["eta"]),
        at=datetime.fromtimestamp(int(g["ts"]), UTC),
        signed=signed,
        signature=g["sig"],
    )


def sign(key: str, signed: str) -> str:
    return hmac.new(key.encode(), signed.encode(), hashlib.sha256).hexdigest()[:16]


def new_key() -> str:
    return secrets.token_hex(16)


async def receive(session: AsyncSession, text: str, now: datetime | None = None) -> Outcome:
    """Applies a signed EH3 message in the caller's (system) session; the caller commits."""
    message = parse(text)
    if message is None:
        return Outcome("ignored", "not_a_callout_message")
    now = now or datetime.now(UTC)
    volunteer = await session.get(Volunteer, message.volunteer_id, with_for_update=True)
    if volunteer is None or volunteer.sms_key is None:
        return Outcome("ignored", "unknown_volunteer")
    if not hmac.compare_digest(sign(volunteer.sms_key, message.signed), message.signature):
        log.warning("callout_sms.bad_signature")
        return Outcome("ignored", "invalid_signature")
    if message.at > now + CLOCK_SKEW or now - message.at > MAX_AGE:
        return Outcome("ignored", "too_old")
    if volunteer.sms_last_at is not None and message.at <= volunteer.sms_last_at:
        return Outcome("ignored", "replayed")
    if message.reply == "accept" and not 1 <= message.eta <= 600:
        return Outcome("ignored", "eta_required")
    account = await session.get(Account, volunteer.user_id)
    if account is None or account.keycloak_sub is None:
        return Outcome("ignored", "unknown_volunteer")
    principal = Principal(subject=account.keycloak_sub, realm=Realm.PUBLIC, roles=frozenset({Role.VOLUNTEER}))
    reporter = Reporter(user_id=volunteer.user_id, kind=AccountKind.CITIZEN, principal=principal)
    try:
        async with session.begin_nested():
            if message.reply == "arrived":
                callout = await session.get(Callout, message.callout_id, with_for_update=True)
                if callout is None:
                    raise HTTPException(404, "not_found")
                await interventions.mark_arrived(session, callout, volunteer.user_id, reporter.actor)
                incident = await session.get(Incident, callout.incident_id)
                await interventions.announce_callout(session, callout, incident.gouvernorat_code if incident else None)
            else:
                callout = await interventions.respond(
                    session,
                    reporter,
                    message.callout_id,
                    message.reply,
                    message.eta if message.reply == "accept" else None,
                )
    except HTTPException as exc:
        return Outcome("ignored", str(exc.detail))
    volunteer.sms_last_at = message.at
    await audit.record(
        session,
        actor=reporter.actor,
        action=f"volunteer.sms_{message.reply}",
        target=f"callout:{callout.id}",
        details={"incident_id": str(callout.incident_id), "via": "sms"},
    )
    return Outcome("applied")
