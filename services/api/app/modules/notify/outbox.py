"""Individual outgoing messages: a push to the devices of one account, or one e-mail.

Rows are written in the caller's transaction (so nothing is sent for a change that was rolled back)
and delivered by ``notify.delivery`` with retries.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notify.models import Outbox

Localized = dict[str, str]


def localized(ar: str, fr: str, en: str) -> Localized:
    return {"ar": ar, "fr": fr, "en": en}


def push(
    session: AsyncSession,
    user_id: uuid.UUID,
    kind: str,
    title: Localized,
    body: Localized,
    data: dict[str, Any] | None = None,
    *,
    alert: bool = False,
) -> None:
    """Queue a push to every device of ``user_id``. ``data`` must hold no personal data."""
    payload = {"type": kind, "title": title, "body": body, "data": data or {}, "alert": alert}
    session.add(Outbox(channel="push", user_id=user_id, payload=payload))


def email(session: AsyncSession, address: str, subject: str, text: str) -> None:
    session.add(Outbox(channel="email", address=address, payload={"subject": subject, "text": text}))
