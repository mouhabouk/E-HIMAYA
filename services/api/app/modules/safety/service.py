"""Personal safety (phase B2, docs/phase-b/design-b2.md §4): shared steps of the router, the worker and retention.

Everything here runs with the system scope on purpose (the caller checked who acts first): recipients are other
accounts, and the worker fires safety checks for accounts that are not signed in.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.crypto import get_cipher
from app.modules.identity.models import Profile
from app.modules.notify import outbox, templates
from app.modules.safety.models import Alert, AlertRecipient, Invitation, Link, LiveShare, SafetyCheck

ALERT_TTL = timedelta(hours=24)
ALERT_KEEP = timedelta(days=7)
LIVE_KEEP = timedelta(hours=24)
CHECK_KEEP = timedelta(days=7)
INVITATION_KEEP = timedelta(days=7)
MAX_POINTS = 120
_BATCH = 500

# Crockford base 32: no I, L, O or U, so a code read aloud or copied by hand is not misread.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_CODE_LEN = 8
_CODE_CONTEXT = "safety.invitation.code"


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------- codes and tokens


def new_code() -> str:
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LEN))
    return f"{raw[:4]}-{raw[4:]}"


def normalize_code(value: str) -> str | None:
    """``abcd efgh``, ``ABCD-EFGH``, ``0O``/``1IL`` mix-ups → ``ABCD-EFGH``; None when it cannot be a code."""
    raw = value.upper().replace("-", "").replace(" ", "").translate(str.maketrans("OIL", "011"))
    if len(raw) != _CODE_LEN or any(c not in _ALPHABET for c in raw):
        return None
    return f"{raw[:4]}-{raw[4:]}"


def code_hash(code: str) -> bytes:
    # Keyed (blind index): a copy of the table alone does not let anyone try the 2^40 codes offline.
    return get_cipher().blind_index(code, context=_CODE_CONTEXT)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode("ascii", errors="replace")).digest()


# ---------------------------------------------------------------- people


def ordered(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (a, b) if a < b else (b, a)


async def links_of(session: AsyncSession, user_id: uuid.UUID) -> list[Link]:
    return list(
        await session.scalars(
            select(Link).where(or_(Link.user_a == user_id, Link.user_b == user_id)).order_by(Link.created_at)
        )
    )


async def person(session: AsyncSession, user_id: uuid.UUID) -> tuple[str | None, str | None]:
    """First name and phone of a linked account (both accepted to share them by linking)."""
    profile = await session.get(Profile, user_id)
    if profile is None:
        return None, None
    return profile.first_name, profile.phone


def phone_hint(phone: str | None) -> str | None:
    """The last two digits only, for the invitation preview: ``•• •• •• 42``."""
    if not phone or len(phone) < 2:
        return None
    return f"•• •• •• {phone[-2:]}"


# ---------------------------------------------------------------- alerts


def point(lat: float, lon: float, accuracy_m: float | None, at: datetime | None = None) -> dict[str, Any]:
    return {
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "accuracy_m": None if accuracy_m is None else round(accuracy_m, 1),
        "at": (at or _now()).isoformat(),
    }


async def send_alert(
    session: AsyncSession,
    *,
    sender_id: uuid.UUID,
    client_uuid: uuid.UUID,
    kind: str,
    message: str,
    position: dict[str, Any] | None,
    battery: int | None,
    recipients: list[uuid.UUID],
    live_share_id: uuid.UUID | None = None,
) -> Alert:
    """Store the alert and queue one critical push per recipient (system scope; the caller checked the links)."""
    now = _now()
    alert = Alert(
        client_uuid=client_uuid,
        sender_id=sender_id,
        kind=kind,
        message=message,
        position=position,
        battery=battery,
        live_share_id=live_share_id,
        created_at=now,
        expires_at=now + ALERT_TTL,
    )
    session.add(alert)
    await session.flush()
    for rid in dict.fromkeys(recipients):
        session.add(AlertRecipient(alert_id=alert.id, recipient_id=rid))
        outbox.push(
            session,
            rid,
            "safety_alert",
            {"id": str(alert.id)},
            critical=True,
            title=templates.SAFETY_ALERT_TITLE,
            body=templates.SAFETY_ALERT_BODY,
        )
    await session.flush()
    return alert


async def fire_due_checks(session: AsyncSession, now: datetime | None = None) -> int:
    """Safety checks past their time without "I am fine": alert every linked contact, once (system scope)."""
    now = now or _now()
    due = list(
        await session.scalars(
            select(SafetyCheck)
            .where(SafetyCheck.status == "active", SafetyCheck.due_at <= now)
            .order_by(SafetyCheck.due_at)
            .limit(100)
            .with_for_update(skip_locked=True)
        )
    )
    for check in due:
        recipients = [link.other(check.owner_id) for link in await links_of(session, check.owner_id)]
        alert = await send_alert(
            session,
            sender_id=check.owner_id,
            client_uuid=check.id,
            kind="check",
            message=check.message,
            position=check.position,
            battery=check.battery,
            recipients=recipients,
        )
        check.status = "fired"
        check.alert_id = alert.id
        check.ended_at = now
        # The owner's phone shows that the contacts were told (and offers the SMS for those without the app).
        outbox.push(session, check.owner_id, "safety_check_fired", {"id": str(check.id)}, alert=True)
    await session.flush()
    return len(due)


# ---------------------------------------------------------------- erasure (POST /me/delete)


async def forget(session: AsyncSession, user_id: uuid.UUID) -> dict[str, int]:
    """Right to erasure: links, invitations, live shares, safety checks and the alerts sent or received go at once
    (the account row stays as a tombstone, so nothing would cascade)."""
    counts: dict[str, int] = {}
    for name, stmt in (
        ("safety_links", delete(Link).where(or_(Link.user_a == user_id, Link.user_b == user_id))),
        ("safety_invitations", delete(Invitation).where(Invitation.inviter_id == user_id)),
        ("safety_checks", delete(SafetyCheck).where(SafetyCheck.owner_id == user_id)),
        ("safety_alerts", delete(Alert).where(Alert.sender_id == user_id)),
        ("safety_received", delete(AlertRecipient).where(AlertRecipient.recipient_id == user_id)),
        ("safety_live_shares", delete(LiveShare).where(LiveShare.owner_id == user_id)),
    ):
        counts[name] = (await session.execute(stmt)).rowcount  # type: ignore[attr-defined]
    return counts


# ---------------------------------------------------------------- retention (privacy/retention.py JOBS)


async def _purge(session: AsyncSession, model: Any, condition: Any) -> int:
    ids = list(await session.scalars(select(model.id).where(condition).limit(_BATCH)))
    if ids:
        await session.execute(delete(model).where(model.id.in_(ids)))
    return len(ids)


async def purge_alerts(session: AsyncSession, settings: Settings, now: datetime) -> int:
    return await _purge(session, Alert, Alert.created_at < now - ALERT_KEEP)


async def purge_live_shares(session: AsyncSession, settings: Settings, now: datetime) -> int:
    # Ended (stopped or expired) for more than 24 h; an alert that pointed to it keeps its own position.
    return await _purge(
        session,
        LiveShare,
        or_(LiveShare.stopped_at < now - LIVE_KEEP, LiveShare.expires_at < now - LIVE_KEEP),
    )


async def purge_checks(session: AsyncSession, settings: Settings, now: datetime) -> int:
    return await _purge(
        session, SafetyCheck, (SafetyCheck.status != "active") & (SafetyCheck.ended_at < now - CHECK_KEEP)
    )


async def purge_invitations(session: AsyncSession, settings: Settings, now: datetime) -> int:
    return await _purge(session, Invitation, Invitation.expires_at < now - INVITATION_KEEP)
