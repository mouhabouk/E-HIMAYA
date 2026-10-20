"""Telephony vocabulary (docs/api/phase-7-contract.md §4, docs/telephony.md): call states, Tunisian numbers, the
operator endpoint names and the blind index of caller numbers.

Caller numbers are personal data: stored encrypted (``EncryptedText``) with a keyed hash (blind index, a sub-key of
FIELD_ENCRYPTION_KEY version 1) for exact lookups (export and erasure of a citizen's calls).
"""

import re
from enum import StrEnum

from app.core.crypto import get_cipher
from app.core.security import Role


class Direction(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(StrEnum):
    # Inbound: waiting in the operators queue. Outbound: the operator's softphone or the number is ringing.
    RINGING = "ringing"
    ANSWERED = "answered"
    # Scenario 2: handed to 198 through the trunk (the call may still be up, now outside the platform).
    TRANSFERRED = "transferred"
    ENDED = "ended"
    # Inbound call that ended before any operator answered; outbound call nobody answered.
    MISSED = "missed"
    FAILED = "failed"


class EndReason(StrEnum):
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    NO_ANSWER = "no_answer"
    TRANSFERRED = "transferred"
    FAILED = "failed"
    # The call was only found through its recording (the API was not listening when it happened).
    UNTRACKED = "untracked"


class Source(StrEnum):
    TRUNK = "trunk"
    WEBRTC = "webrtc"
    SIM = "sim"
    OPERATOR = "operator"
    UNKNOWN = "unknown"


ACTIVE = (CallStatus.RINGING.value, CallStatus.ANSWERED.value)
QUEUE = "operators"
# Staff who take and place calls see caller numbers in full; the other report readers see only the last 2 digits.
CALL_ROLES = frozenset({Role.OPERATOR, Role.OPS_MANAGER, Role.FIELD_COMMANDER})

_CALLER_CONTEXT = "telephony.call.caller_number"
_ENDPOINT_CONTEXT = "telephony.operator_endpoint"
_ENDPOINT = re.compile(r"^op-[0-9a-f]{12}$")
_CHANNEL_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_ROOM = re.compile(r"^[0-9]{8}$")

# Tunisian numbers (ITU-T E.164 country code 216, 8 national digits): mobile 2x, 4x, 5x, 9x; fixed 3x, 7x; 8x
# special-rate services. Short emergency numbers (190, 193, 197, 198) are never dialled through the platform.
_TN_NATIONAL = re.compile(r"^[2-9][0-9]{7}$")
_SEPARATORS = re.compile(r"[\s().-]")


def normalize_tn_number(raw: str) -> str | None:
    """``+216 XX XXX XXX`` / ``00216…`` / ``216…`` / ``XXXXXXXX`` → ``+216XXXXXXXX``; None when not Tunisian."""
    value = _SEPARATORS.sub("", raw or "")
    if value.startswith("+216"):
        value = value[4:]
    elif value.startswith("00216"):
        value = value[5:]
    elif value.startswith("216") and len(value) == 11:
        value = value[3:]
    return f"+216{value}" if _TN_NATIONAL.match(value) else None


def normalize_caller(raw: str | None) -> str | None:
    """A caller number as presented by the network: Tunisian numbers normalised, others kept as digits (and +)."""
    if not raw:
        return None
    tunisian = normalize_tn_number(raw)
    if tunisian:
        return tunisian
    cleaned = re.sub(r"[^0-9+]", "", raw)[:32]
    return cleaned or None


def dial_extension(number: str) -> str:
    """The dialplan extension of a normalised Tunisian number: ``216XXXXXXXX``."""
    return number.removeprefix("+")


def caller_index(number: str) -> bytes:
    return get_cipher().blind_index(number, context=_CALLER_CONTEXT)


def mask_number(number: str | None) -> str | None:
    """Only the last 2 digits stay visible (roles without call access)."""
    if not number:
        return number
    return "•" * max(len(number) - 2, 0) + number[-2:]


def endpoint_for(subject: str) -> str:
    """Stable PJSIP endpoint name of a staff member: ``op-`` + 12 hex of a keyed hash of the subject."""
    return "op-" + get_cipher().blind_index(subject, context=_ENDPOINT_CONTEXT).hex()[:12]


def valid_endpoint(name: str) -> bool:
    return bool(_ENDPOINT.match(name))


def valid_channel_id(value: str) -> bool:
    return bool(_CHANNEL_ID.match(value)) and not value.startswith(".")


def valid_room(room: str) -> bool:
    return bool(_ROOM.match(room))
