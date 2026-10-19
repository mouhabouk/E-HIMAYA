# ┏━━ SIMULATION ━━ HTTP SMS gateway of a Tunisian operator/aggregator (POST {"to","text","sender"}, bearer token)
# ┃ PRODUCTION: set the API's SMS_HTTP_URL and SMS_HTTP_TOKEN to the endpoint and token of the SMS provider
# ┃   contract (and SMS_SENDER to the registered sender name); remove the notify-sim service.
# ┗━━━━━━━━━━━━━━━━
"""SIMULATION — validation and segment counting of the emulated SMS gateway."""

import math
import re
from dataclasses import dataclass

TUNISIAN_MOBILE = re.compile(r"\+216[2-9][0-9]{7}")  # ASCII digits only; used with fullmatch
MAX_TEXT = 1000
MAX_SENDER = 11  # alphanumeric sender id

# GSM 03.38 default alphabet and its extension table (extension characters take two septets).
GSM7_BASIC = frozenset(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM7_EXTENSION = frozenset("^{}\\[~]|€\f")


@dataclass(frozen=True, slots=True)
class Segments:
    count: int
    encoding: str  # "GSM-7" | "UCS-2"


def segments(text: str) -> Segments:
    """Number of SMS parts: GSM-7 160 per single part, 153 when concatenated; UCS-2 (Arabic) 70, then 67."""
    if all(ch in GSM7_BASIC or ch in GSM7_EXTENSION for ch in text):
        septets = sum(2 if ch in GSM7_EXTENSION else 1 for ch in text)
        return Segments(1 if septets <= 160 else math.ceil(septets / 153), "GSM-7")
    units = len(text.encode("utf-16-le")) // 2  # characters outside the BMP (emoji) take two units
    return Segments(1 if units <= 70 else math.ceil(units / 67), "UCS-2")


def validate(body: object) -> str | None:
    """The gateway's error code for a bad request body, or None when it is acceptable."""
    if not isinstance(body, dict):
        return "invalid_request"
    to, text, sender = body.get("to"), body.get("text"), body.get("sender")
    if not isinstance(to, str) or not TUNISIAN_MOBILE.fullmatch(to):
        return "invalid_number"
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
        return "invalid_text"
    if not isinstance(sender, str) or not sender.strip() or len(sender) > MAX_SENDER:
        return "invalid_sender"
    return None
