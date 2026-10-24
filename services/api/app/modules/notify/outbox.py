"""Individual outgoing messages: a push to the devices of one account, or one e-mail.

Rows are written in the caller's transaction (so nothing is sent for a change that was rolled back)
and delivered by ``notify.delivery`` with retries.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notify import templates
from app.modules.notify.models import Outbox

Localized = dict[str, str]


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
        "data": {**(data or {}), "redacted": "1"},
        "alert": alert or critical,
        "critical": critical,
    }
    session.add(Outbox(channel="push", user_id=user_id, payload=payload))


def email(session: AsyncSession, address: str, subject: str, text: str) -> None:
    session.add(Outbox(channel="email", address=address, payload={"subject": subject, "text": text}))
