"""Individual outgoing messages: a push to the devices of one account, or one e-mail.

Rows are written in the caller's transaction (so nothing is sent for a change that was rolled back)
and delivered by ``notify.delivery`` with retries.
"""

import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notify import templates
from app.modules.notify.models import Outbox

Localized = dict[str, str]


# Review point 3 (phase D): a push travels through Google's servers, so its data holds identifiers and short codes only.
# Keys outside this list, or values that are not a short code (a uuid, a tracking code, a status), are refused when
# the push is queued, so a future change cannot leak a name, an address or a note through Firebase by mistake.
PUSH_DATA_KEYS = frozenset(
    {
        "id",
        "report_id",
        "tracking_code",
        "status",
        "team",
        "callout_id",
        "assignment_id",
        "incident_id",
        "prealert_id",
        "org_id",
        "stream_id",
    }
)
_CODE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")


class PersonalDataInPush(ValueError):
    """A push was given a key or a value that could carry personal data."""


def check_push_data(data: dict[str, Any]) -> dict[str, str]:
    """The push data as strings, or ``PersonalDataInPush`` when a key is unknown or a value is not a short code."""
    out: dict[str, str] = {}
    for key, value in data.items():
        if key not in PUSH_DATA_KEYS:
            raise PersonalDataInPush(f"push data key not allowed: {key}")
        text = str(value)
        if not _CODE.match(text):
            raise PersonalDataInPush(f"push data value of {key} is not a short code")
        out[key] = text
    return out


def localized(ar: str, fr: str, en: str) -> Localized:
    return {"ar": ar, "fr": fr, "en": en}


def push(
    session: AsyncSession,
    user_id: uuid.UUID,
    kind: str,
    data: dict[str, Any] | None = None,
    *,
    alert: bool = False,
    critical: bool = False,
    title: Localized | None = None,
    body: Localized | None = None,
) -> None:
    """Queue a content-free push to every device of ``user_id`` (A8).

    The title and body are the generic "you have an update" text in the device's language; ``data`` holds
    only identifiers (never names, addresses or free text) plus ``redacted: "1"``, and the app fetches the
    content over the authenticated API. ``critical`` rings on the Android critical channel (an alert from a linked
    contact, phase B2); ``title`` and ``body`` replace the generic text with another fixed, content-free text."""
    payload = {
        "type": kind,
        "title": title or templates.PERSONAL_PUSH_TITLE,
        "body": body or templates.PERSONAL_PUSH_BODY,
        "data": {**check_push_data(data or {}), "redacted": "1"},
        "alert": alert or critical,
        "critical": critical,
    }
    session.add(Outbox(channel="push", user_id=user_id, payload=payload))


def email(session: AsyncSession, address: str, subject: str, text: str) -> None:
    session.add(Outbox(channel="email", address=address, payload={"subject": subject, "text": text}))


def staff_push(
    session: AsyncSession,
    token: str,
    platform: str,
    kind: str,
    data: dict[str, Any],
    *,
    title: Localized,
    body: Localized,
    locale: str = "ar",
) -> None:
    """Queue a content-free urgent push to one staff device (phase P4a: the mission alert of a team leader).

    ``data`` holds identifiers only; the staff app fetches the mission over the authenticated API."""
    payload = {
        "type": kind,
        "title": title,
        "body": body,
        "data": {**check_push_data(data), "redacted": "1"},
        "platform": platform,
        "locale": locale,
    }
    session.add(Outbox(channel="staff_push", address=token, payload=payload))
