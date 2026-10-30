"""The staff app's text messages when there is no internet (phase P4d, docs/phase-p4/design-staff.md §9.3).

The phone opens the SMS app with a ready message to the platform's gateway number and the team leader presses Send.
The gateway posts it to ``POST /internal/sms/inbound`` (telephony.internal) next to the citizens' ``EH1`` reports:

``EH2 <device> <assignment> <event> <unix time> <client_id> <signature>``

* ``device``, ``assignment`` and ``client_id``: 32 hex digits each (UUIDs without dashes);
* ``event``: ``ack``, ``en_route``, ``on_scene``, ``released``, ``backup``, ``danger``, or a later step of the
  mission (phase S2): ``left_scene``, ``at_hospital``, ``back_at_unit``;
* ``signature``: the first 16 hex digits of HMAC-SHA256(phone's key, ``EH2|device|assignment|event|time|client_id``).
  The key is the phone's own (``POST /crew/devices/current/sms-key``), encrypted at rest on both sides.

A message is applied as if the phone had sent the same write through the app, with the same ``client_id``: when the
phone later sends it again over the internet, it is not applied twice. A wrong signature, a revoked phone, a message
older than 12 hours or a leader without that mission is ignored (never an error the gateway would retry).
"""

import hashlib
import hmac
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import structlog
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, Realm, Role
from app.modules.audit import service as audit
from app.modules.ops import crew, schemas
from app.modules.ops.models import Assignment, CrewEvent, StaffDevice

log = structlog.get_logger()

_BODY = re.compile(
    r"^\s*EH2\s+(?P<device>[0-9a-f]{32})\s+(?P<assignment>[0-9a-f]{32})\s+"
    r"(?P<event>ack|en_route|on_scene|released|backup|danger|left_scene|at_hospital|back_at_unit)\s+(?P<ts>\d{9,11})\s+"
    r"(?P<client>[0-9a-f]{32})\s+(?P<sig>[0-9a-f]{16})\s*$",
    re.IGNORECASE,
)
MAX_AGE = timedelta(hours=12)
CLOCK_SKEW = timedelta(minutes=5)

Event = Literal[
    "ack", "en_route", "on_scene", "released", "backup", "danger", "left_scene", "at_hospital", "back_at_unit"
]


@dataclass(frozen=True, slots=True)
class CrewSms:
    device_id: uuid.UUID
    assignment_id: uuid.UUID
    event: Event
    at: datetime
    client_id: uuid.UUID
    signature: str
    signed: str


@dataclass(frozen=True, slots=True)
class Outcome:
    status: Literal["applied", "duplicate", "ignored"]
    reason: str | None = None


def is_crew_sms(text: str) -> bool:
    return (text or "").lstrip()[:4].upper() == "EH2 "


def parse(text: str) -> CrewSms | None:
    match = _BODY.match(text or "")
    if match is None:
        return None
    g = {k: v.lower() for k, v in match.groupdict().items()}
    signed = "|".join(("EH2", g["device"], g["assignment"], g["event"], g["ts"], g["client"]))
    return CrewSms(
        device_id=uuid.UUID(g["device"]),
        assignment_id=uuid.UUID(g["assignment"]),
        event=g["event"],  # type: ignore[arg-type]
        at=datetime.fromtimestamp(int(g["ts"]), UTC),
        client_id=uuid.UUID(g["client"]),
        signature=g["sig"],
        signed=signed,
    )


def sign(key: str, signed: str) -> str:
    return hmac.new(key.encode(), signed.encode(), hashlib.sha256).hexdigest()[:16]


def _leader(device: StaffDevice) -> Principal:
    """The phone's holder, as the app would present them (the message proves the phone, not a fresh sign-in)."""
    return Principal(
        subject=device.subject,
        realm=Realm.STAFF,
        roles=frozenset({Role.TEAM_LEADER}),
        gouvernorat_code=device.gouvernorat_code,
        claims={"name": device.holder_name} if device.holder_name else {},
    )


async def receive(session: AsyncSession, text: str, now: datetime | None = None) -> Outcome:
    """Applies a signed EH2 message in the caller's (system) session; the caller commits."""
    message = parse(text)
    if message is None:
        return Outcome("ignored", "not_a_crew_message")
    now = now or datetime.now(UTC)
    device = await session.get(StaffDevice, message.device_id)
    if device is None or device.sms_key is None or device.revoked_at is not None:
        return Outcome("ignored", "unknown_device")
    if not hmac.compare_digest(sign(device.sms_key, message.signed), message.signature):
        log.warning("crew_sms.bad_signature", device=str(device.id))
        return Outcome("ignored", "invalid_signature")
    if message.at > now + CLOCK_SKEW or now - message.at > MAX_AGE:
        return Outcome("ignored", "too_old")
    if await session.get(CrewEvent, message.client_id) is not None:
        return Outcome("duplicate")
    principal = _leader(device)
    token = crew.VIA.set("sms")
    try:
        # A refused write leaves nothing behind (in the app, the whole request would be rolled back).
        async with session.begin_nested():
            assignment = await _apply(session, principal, message)
    except HTTPException as exc:
        return Outcome("ignored", str(exc.detail))
    finally:
        crew.VIA.reset(token)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action=f"crew.sms_{message.event}",
        target=f"assignment:{assignment.id}",
        details={"incident_id": str(assignment.incident_id), "via": "sms"},
        gouvernorats=[device.gouvernorat_code],
    )
    return Outcome("applied")


async def _apply(session: AsyncSession, principal: Principal, message: CrewSms) -> Assignment:
    write = {"client_id": message.client_id, "device_at": message.at}
    match message.event:
        case "ack":
            return await crew.acknowledge(session, principal, message.assignment_id, schemas.CrewWrite(**write))
        case "en_route" | "on_scene" | "released":
            step = schemas.StepIn(status=message.event, **write)
            return await crew.step(session, principal, message.assignment_id, step)
        case "left_scene" | "at_hospital" | "back_at_unit":
            milestone = schemas.MilestoneIn(step=message.event, **write)
            return await crew.milestone(session, principal, message.assignment_id, milestone)
        case "backup" | "danger":
            alert = schemas.AlertIn(kind=message.event, items=[], **write)
            return await crew.alert(session, principal, message.assignment_id, alert)
