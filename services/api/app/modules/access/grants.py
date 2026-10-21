"""Break-glass grants (phase 9 §6.1): time-boxed, justified, read-only access beyond a staff member's scope.

A grant targets one report, one incident or one gouvernorat. It is active from its creation until it expires or is
revoked, and only ever extends ``report.read``, ``incident.read`` and ``report.read_sensitive`` (``core.access``): it
never allows a write or a command. Every grant is reviewed afterwards by a national security admin, never by its
holder; the ``breakglass`` worker announces the end of each grant and the reviews still missing 72 hours later.
"""

import base64
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import as_system
from app.core.events import emit
from app.core.security import Principal, Role
from app.modules.access import schemas
from app.modules.access.models import BreakGlassGrant
from app.modules.audit import service as audit
from app.modules.ops.models import Incident
from app.modules.reports.models import Report

MIN_JUSTIFICATION, MAX_JUSTIFICATION = 20, 1000
REVIEW_OVERDUE = timedelta(hours=72)


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class Grant:
    """An active grant as the policy function sees it (``core.access.Grant``)."""

    id: uuid.UUID
    target_kind: str
    target_id: uuid.UUID | None
    gouvernorat_code: int | None
    expires_at: datetime


def _active() -> Any:
    return and_(BreakGlassGrant.ended_at.is_(None), BreakGlassGrant.expires_at > _now())


async def active_grants(session: AsyncSession, subject: str) -> list[Grant]:
    """Unexpired, unrevoked grants of a staff member (frozen interface, §11)."""
    rows = await session.execute(
        select(
            BreakGlassGrant.id,
            BreakGlassGrant.target_kind,
            BreakGlassGrant.target_id,
            BreakGlassGrant.gouvernorat_code,
            BreakGlassGrant.expires_at,
        ).where(BreakGlassGrant.subject == subject, _active())
    )
    return [Grant(*row) for row in rows.all()]


def is_security_admin(principal: Principal) -> bool:
    return Role.SECURITY_ADMIN in principal.roles and principal.is_national


def state_of(row: BreakGlassGrant, now: datetime | None = None) -> str:
    if row.reviewed_at is not None:
        return "reviewed"
    if row.ended_at is None and row.expires_at > (now or _now()):
        return "active"
    return "pending_review"


def grant_out(row: BreakGlassGrant) -> schemas.GrantOut:
    return schemas.GrantOut(
        id=row.id,
        subject=row.subject,
        subject_name=row.subject_name,
        target_kind=row.target_kind,
        target_id=row.target_id,
        gouvernorat_code=row.gouvernorat_code,
        justification=row.justification,
        granted_at=row.granted_at,
        expires_at=row.expires_at,
        ended_at=row.ended_at,
        revoked_at=row.revoked_at,
        state=state_of(row),
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
        review_outcome=row.review_outcome,
        review_note=row.review_note,
    )


async def announce(session: AsyncSession, subject: str, row: BreakGlassGrant) -> None:
    """``breakglass.*`` events go to the national security admins and the holder (live feed)."""
    await emit(session, subject, {"grant": grant_out(row).model_dump(mode="json"), "subject": row.subject})


# ---------------------------------------------------------------- request


async def _target_gouvernorat(session: AsyncSession, body: schemas.GrantIn) -> int | None:
    """Gouvernorat of the target (audit scope); 422 ``invalid_target`` when the target does not exist."""
    invalid = HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_target")
    if body.target_kind == "gouvernorat":
        if body.target_id is not None or body.gouvernorat_code is None:
            raise invalid
        known = await session.scalar(
            text("SELECT count(*) FROM geo.gouvernorat WHERE code = :c"), {"c": body.gouvernorat_code}
        )
        if not known:
            raise invalid
        return body.gouvernorat_code
    if body.target_id is None or body.gouvernorat_code is not None:
        raise invalid
    # The target is outside the caller's scope by definition: looked up with the system scope (row-level security),
    # and only its existence and gouvernorat are used.
    model = Report if body.target_kind == "report" else Incident
    async with as_system(session):
        found = (await session.execute(select(model.gouvernorat_code).where(model.id == body.target_id))).first()
    if found is None:
        raise invalid
    code: int | None = found.gouvernorat_code
    return code


async def request(session: AsyncSession, principal: Principal, body: schemas.GrantIn) -> BreakGlassGrant:
    justification = (body.justification or "").strip()
    if not MIN_JUSTIFICATION <= len(justification) <= MAX_JUSTIFICATION:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "breakglass_justification_required")
    code = await _target_gouvernorat(session, body)
    now = _now()
    row = BreakGlassGrant(
        subject=principal.subject,
        subject_name=audit.name_of(principal),
        target_kind=body.target_kind,
        target_id=body.target_id,
        # A report or incident grant covers that object only, not its gouvernorat.
        gouvernorat_code=body.gouvernorat_code if body.target_kind == "gouvernorat" else None,
        justification=justification,
        granted_at=now,
        expires_at=now + timedelta(minutes=body.duration_min),
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="breakglass.grant",
        target=f"{body.target_kind}:{body.target_id or body.gouvernorat_code}",
        reason=justification,
        details={"grant_id": str(row.id), "kind": body.target_kind, "duration_min": body.duration_min},
        gouvernorats=[code] if code is not None else None,
    )
    await announce(session, "breakglass.granted", row)
    return row


# ---------------------------------------------------------------- list, revoke, review

GRANT_STATES = ("active", "expired", "pending_review", "reviewed")


def _encode(at: datetime, gid: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{at.isoformat()}|{gid}".encode()).decode().rstrip("=")


def _decode(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        at, gid = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode().split("|", 1)
        return datetime.fromisoformat(at), uuid.UUID(gid)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc


def _state_filter(state: str) -> Any:
    ended = or_(BreakGlassGrant.ended_at.is_not(None), BreakGlassGrant.expires_at <= _now())
    if state == "active":
        return _active()
    if state == "expired":
        return ended
    if state == "pending_review":
        return and_(ended, BreakGlassGrant.reviewed_at.is_(None))
    return BreakGlassGrant.reviewed_at.is_not(None)


async def list_grants(
    session: AsyncSession, principal: Principal, state: str | None, limit: int, cursor: str | None
) -> tuple[list[schemas.GrantOut], str | None]:
    """National security admins see every grant; everybody else their own."""
    query = select(BreakGlassGrant)
    if not is_security_admin(principal):
        query = query.where(BreakGlassGrant.subject == principal.subject)
    if state:
        query = query.where(_state_filter(state))
    if cursor:
        at, gid = _decode(cursor)
        query = query.where(
            or_(BreakGlassGrant.granted_at < at, and_(BreakGlassGrant.granted_at == at, BreakGlassGrant.id < gid))
        )
    rows = list(
        await session.scalars(query.order_by(BreakGlassGrant.granted_at.desc(), BreakGlassGrant.id.desc()).limit(limit))
    )
    next_cursor = _encode(rows[-1].granted_at, rows[-1].id) if len(rows) == limit else None
    return [grant_out(r) for r in rows], next_cursor


async def get_visible(session: AsyncSession, principal: Principal, grant_id: uuid.UUID) -> BreakGlassGrant:
    row = await session.get(BreakGlassGrant, grant_id, with_for_update=True)
    if row is None or (row.subject != principal.subject and not is_security_admin(principal)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return row


async def revoke(session: AsyncSession, principal: Principal, grant_id: uuid.UUID) -> BreakGlassGrant:
    """The holder or a national security admin ends a grant before its expiry."""
    row = await get_visible(session, principal, grant_id)
    if state_of(row) != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "grant_not_active")
    now = _now()
    row.revoked_at = row.ended_at = now
    row.revoked_by = audit.actor_of(principal)
    await session.flush()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="breakglass.revoke",
        target=f"breakglass:{row.id}",
        details={"grant_id": str(row.id)},
        gouvernorats=[row.gouvernorat_code] if row.gouvernorat_code is not None else None,
    )
    await announce(session, "breakglass.revoked", row)
    return row


async def review(
    session: AsyncSession, principal: Principal, grant_id: uuid.UUID, body: schemas.ReviewIn
) -> BreakGlassGrant:
    """A national security admin, never the holder, decides whether the grant was justified (once)."""
    row = await get_visible(session, principal, grant_id)
    if row.subject == principal.subject:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "breakglass_self_review")
    if row.reviewed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_reviewed")
    row.reviewed_by, row.reviewed_at = audit.name_of(principal) or audit.actor_of(principal), _now()
    row.review_outcome, row.review_note = body.outcome, body.note
    await session.flush()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="breakglass.review",
        target=f"breakglass:{row.id}",
        reason=body.note,
        details={"grant_id": str(row.id), "outcome": body.outcome},
        gouvernorats=[row.gouvernorat_code] if row.gouvernorat_code is not None else None,
    )
    await announce(session, "breakglass.reviewed", row)
    return row


# ---------------------------------------------------------------- worker steps


async def end_expired(session: AsyncSession, limit: int = 200) -> int:
    """Close the grants past their expiry (announced once, ``breakglass.expired``)."""
    rows = list(
        await session.scalars(
            select(BreakGlassGrant)
            .where(BreakGlassGrant.ended_at.is_(None), BreakGlassGrant.expires_at <= _now())
            .order_by(BreakGlassGrant.expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    for row in rows:
        row.ended_at = row.expires_at
        await announce(session, "breakglass.expired", row)
    await session.flush()
    return len(rows)


async def flag_overdue_reviews(session: AsyncSession, limit: int = 200) -> int:
    """Grants still unreviewed 72 hours after their end: ``breakglass.review_overdue`` (once each)."""
    rows = list(
        await session.scalars(
            select(BreakGlassGrant)
            .where(
                BreakGlassGrant.reviewed_at.is_(None),
                BreakGlassGrant.overdue_notified_at.is_(None),
                BreakGlassGrant.ended_at.is_not(None),
                BreakGlassGrant.ended_at <= _now() - REVIEW_OVERDUE,
            )
            .order_by(BreakGlassGrant.ended_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    for row in rows:
        row.overdue_notified_at = _now()
        await announce(session, "breakglass.review_overdue", row)
    await session.flush()
    return len(rows)
