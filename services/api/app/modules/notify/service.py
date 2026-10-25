"""Informational notifications (FR-C-17) and urgent geographic alerts (FR-C-18), their targeting and the
app inbox (FR-A-060, FR-A-061).

A message is drafted, then published: publishing creates one ``notify.dispatch`` job per channel, run
by ``delivery`` in the background. Recipients are computed at delivery time from the target:
gouvernorats or a polygon (alerts), an audience (informational: everyone, volunteers, institutions, one
user). A device's coarse current position wins over its owner's profile gouvernorat (FR-A-061).
"""

import base64
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, any_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import get_cipher
from app.core.events import emit
from app.core.security import Principal, Role
from app.modules.audit import service as audit
from app.modules.identity.models import PHONE_CONTEXT, Account
from app.modules.notify import schemas
from app.modules.notify.models import Dispatch, Message
from app.modules.notify.org_target import ORG_TARGET
from app.modules.ops.levels import levels_of
from app.modules.ops.models import OpLevel
from app.modules.reports.domain import LAT_MAX, LAT_MIN, LON_MAX, LON_MIN
from app.modules.settings import domain as settings_domain
from app.modules.settings import service as settings_service

MAX_ALERT_DAYS = 7
MAX_POLYGON_POINTS = 500
SCOPE_TOLERANCE_M = 5000
INBOX_ALERT_DAYS = 30

INFO_ROLES = frozenset({Role.CONTENT_EDITOR, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE})
ALERT_DRAFT_ROLES = frozenset({Role.OPS_MANAGER, Role.CONTENT_EDITOR, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE})
ALERT_PUBLISH_ROLES = INFO_ROLES


def _now() -> datetime:
    return datetime.now(UTC)


def _forbid(code: str = "insufficient_role") -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, code)


def can_draft(principal: Principal, kind: str) -> bool:
    return bool(principal.roles & (INFO_ROLES if kind == "info" else ALERT_DRAFT_ROLES))


def can_publish(principal: Principal, kind: str) -> bool:
    return bool(principal.roles & (INFO_ROLES if kind == "info" else ALERT_PUBLISH_ROLES))


# ---------------------------------------------------------------- validation


def _polygon_wkt(polygon: dict[str, Any]) -> str:
    try:
        if polygon.get("type") != "Polygon":
            raise ValueError
        rings = polygon["coordinates"]
        if len(rings) != 1:
            raise ValueError
        points = [(float(lon), float(lat)) for lon, lat in rings[0]]
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_area") from exc
    if points and points[0] != points[-1]:
        points.append(points[0])
    if not 4 <= len(points) <= MAX_POLYGON_POINTS + 1:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_area")
    if any(not (LON_MIN <= lon <= LON_MAX and LAT_MIN <= lat <= LAT_MAX) for lon, lat in points):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_area")
    return "SRID=4326;POLYGON((" + ", ".join(f"{lon} {lat}" for lon, lat in points) + "))"


async def _check_polygon(session: AsyncSession, wkt: str) -> None:
    valid = await session.scalar(text("SELECT ST_IsValid(ST_GeomFromEWKT(:wkt))"), {"wkt": wkt})
    if not valid:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_area")


async def _check_codes(session: AsyncSession, codes: list[int]) -> None:
    if not codes:
        return
    found = await session.scalar(
        text("SELECT count(*) FROM geo.gouvernorat WHERE code = ANY(:codes)"), {"codes": codes}
    )
    if found != len(set(codes)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_gouvernorat")


async def check_scope(session: AsyncSession, principal: Principal, message: Message) -> None:
    """A regional staff member targets its own gouvernorat only (a polygon with a 5 km tolerance)."""
    if principal.is_national:
        return
    own = principal.gouvernorat_code
    if message.area_polygon is not None:
        inside = await session.scalar(
            text(
                "SELECT ST_Within(m.area_polygon, ST_Buffer(CAST(g.boundary AS geography), :tol)::geometry) "
                "FROM notify.message m, geo.gouvernorat g WHERE m.id = :mid AND g.code = :code"
            ),
            {"mid": message.id, "code": own, "tol": SCOPE_TOLERANCE_M},
        )
        if not inside:
            raise _forbid("out_of_scope")
    elif message.audience == "user":
        # Phase 9 §5.6: a one-user message from a regional editor targets an account of its gouvernorat only.
        target = await session.scalar(
            text("SELECT gouvernorat_code FROM identity.profile WHERE user_id = :uid"), {"uid": message.user_id}
        )
        if target != own:
            raise _forbid("out_of_scope")
    elif set(message.gouvernorat_codes) != {own}:
        raise _forbid("out_of_scope")


async def _apply(session: AsyncSession, message: Message, body: schemas.MessageIn) -> None:
    message.title = body.title.model_dump()
    message.body = body.body.model_dump()
    message.channels = list(body.channels)
    codes = sorted(set(body.area.gouvernorat_codes))
    await _check_codes(session, codes)
    if body.kind == "info":
        if body.topic is None or body.audience is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "topic_and_audience_required")
        if body.area.polygon is not None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_area")
        if body.audience == "user":
            if body.user_id is None or await session.get(Account, body.user_id) is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_user")
            codes = []
        if (body.org_kinds or body.ack_required) and body.audience != "organizations":
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "org_target_requires_organizations")
        message.topic, message.audience = body.topic, body.audience
        message.user_id = body.user_id if body.audience == "user" else None
        message.org_kinds, message.ack_required = list(body.org_kinds), body.ack_required
        message.severity = message.category = message.hazard = None
        message.expires_at, message.area_polygon = None, None
    else:
        if body.severity is None or body.category is None or body.expires_at is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "severity_category_expiry_required")
        expires = body.expires_at if body.expires_at.tzinfo else body.expires_at.replace(tzinfo=UTC)
        if not _now() < expires <= _now() + timedelta(days=MAX_ALERT_DAYS):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_expiry")
        message.severity, message.category, message.hazard = body.severity, body.category, body.hazard
        message.expires_at = expires
        if body.org_kinds or body.ack_required:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "org_target_requires_organizations")
        message.topic = message.audience = None
        message.user_id = None
        message.org_kinds, message.ack_required = [], False
        if body.area.polygon is not None:
            if codes:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_area")
            wkt = _polygon_wkt(body.area.polygon)
            await _check_polygon(session, wkt)
            message.area_polygon = wkt
        else:
            message.area_polygon = None
    message.gouvernorat_codes = codes
    message.updated_at = _now()


# ---------------------------------------------------------------- outputs


async def _area(session: AsyncSession, message: Message) -> schemas.Area:
    polygon = None
    if message.area_polygon is not None:
        raw = await session.scalar(select(func.ST_AsGeoJSON(Message.area_polygon, 6)).where(Message.id == message.id))
        polygon = json.loads(raw) if raw else None
    return schemas.Area(gouvernorat_codes=list(message.gouvernorat_codes), polygon=polygon)


async def message_out(session: AsyncSession, message: Message) -> schemas.MessageOut:
    jobs = await session.scalars(
        select(Dispatch).where(Dispatch.message_id == message.id, Dispatch.purpose == "publish")
    )
    return schemas.MessageOut(
        id=message.id,
        kind=message.kind,
        status=message.status,
        title=message.title,
        body=message.body,
        channels=list(message.channels),
        topic=message.topic,
        audience=message.audience,
        user_id=message.user_id,
        severity=message.severity,
        category=message.category,
        hazard=message.hazard,
        expires_at=message.expires_at,
        area=await _area(session, message),
        created_by=message.created_by_name,
        created_at=message.created_at,
        published_by=message.published_by_name,
        published_at=message.published_at,
        cancelled_at=message.cancelled_at,
        version=message.version,
        updated_by=message.updated_by_name,
        single_reviewer=message.single_reviewer,
        emergency_reason=message.emergency_reason,
        reviewed_by=message.reviewed_by_name,
        reviewed_at=message.reviewed_at,
        org_kinds=list(message.org_kinds or []),
        ack_required=message.ack_required,
        stats={j.channel: schemas.ChannelStats(status=j.status, sent=j.sent, failed=j.failed) for j in jobs},
    )


async def area_codes(session: AsyncSession, message: Message) -> list[int]:
    """Gouvernorats a polygon intersects (live routing to the editors concerned, phase 9 §5.6)."""
    if message.area_polygon is None:
        return list(message.gouvernorat_codes)
    rows = await session.scalars(
        text(
            "SELECT g.code FROM geo.gouvernorat g, notify.message m "
            "WHERE m.id = :mid AND ST_Intersects(g.boundary, m.area_polygon) ORDER BY g.code"
        ),
        {"mid": message.id},
    )
    return [int(c) for c in rows]


async def announce(session: AsyncSession, message: Message) -> None:
    out = await message_out(session, message)
    await emit(
        session,
        "notification.updated",
        {"message": out.model_dump(mode="json"), "gouvernorat_codes": await area_codes(session, message)},
    )


# ---------------------------------------------------------------- staff actions


def _visible(principal: Principal) -> Any:
    if principal.is_national:
        return True
    own = principal.gouvernorat_code
    touches_polygon = text(
        "ST_Intersects(notify.message.area_polygon, (SELECT boundary FROM geo.gouvernorat WHERE code = :own_scope))"
    ).bindparams(own_scope=own)
    return or_(
        Message.creator_scope == own,
        any_(Message.gouvernorat_codes) == own,
        # National messages once published; a one-user message stays with the gouvernorat that wrote it (phase 9).
        and_(
            func.cardinality(Message.gouvernorat_codes) == 0,
            Message.area_polygon.is_(None),
            Message.status != "draft",
            Message.audience.is_distinct_from("user"),
        ),
        and_(Message.area_polygon.is_not(None), touches_polygon),
    )


async def get_in_scope(
    session: AsyncSession, principal: Principal, message_id: uuid.UUID, lock: bool = False
) -> Message:
    message = await session.scalar(
        select(Message).where(Message.id == message_id, _visible(principal)).with_for_update(of=Message)
        if lock
        else select(Message).where(Message.id == message_id, _visible(principal))
    )
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return message


def _encode(at: datetime, mid: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{at.isoformat()}|{mid}".encode()).decode().rstrip("=")


def _decode(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        at, mid = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode().split("|", 1)
        return datetime.fromisoformat(at), uuid.UUID(mid)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc


async def staff_list(
    session: AsyncSession,
    principal: Principal,
    kinds: list[str],
    statuses: list[str],
    limit: int,
    cursor: str | None,
) -> tuple[list[schemas.MessageOut], str | None]:
    query = select(Message).where(_visible(principal))
    if kinds:
        query = query.where(Message.kind.in_(kinds))
    if statuses:
        query = query.where(Message.status.in_(statuses))
    if cursor:
        at, mid = _decode(cursor)
        query = query.where(or_(Message.created_at < at, and_(Message.created_at == at, Message.id < mid)))
    rows = list(await session.scalars(query.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit)))
    items = [await message_out(session, m) for m in rows]
    next_cursor = _encode(rows[-1].created_at, rows[-1].id) if len(rows) == limit else None
    return items, next_cursor


async def create(session: AsyncSession, principal: Principal, body: schemas.MessageIn) -> Message:
    if not can_draft(principal, body.kind):
        raise _forbid()
    message = Message(
        kind=body.kind,
        status="draft",
        creator_scope=principal.gouvernorat_code,
        created_by=audit.actor_of(principal),
        created_by_name=audit.name_of(principal),
        version=1,
    )
    if not principal.is_national and not body.area.gouvernorat_codes and body.area.polygon is None:
        # A regional editor's message targets its gouvernorat unless it says otherwise.
        body.area.gouvernorat_codes = [principal.gouvernorat_code]  # type: ignore[list-item]
    await _apply(session, message, body)
    session.add(message)
    await session.flush()
    await check_scope(session, principal, message)
    await session.refresh(message)
    return message


async def update(session: AsyncSession, principal: Principal, message: Message, body: schemas.MessageIn) -> Message:
    if not can_draft(principal, message.kind) or body.kind != message.kind:
        raise (
            _forbid()
            if body.kind == message.kind
            else HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "kind_change")
        )
    if message.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "not_draft")
    if body.version is not None and body.version != message.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
    await _apply(session, message, body)
    message.version += 1
    message.updated_by, message.updated_by_name = audit.actor_of(principal), audit.name_of(principal)
    await session.flush()
    await check_scope(session, principal, message)
    await session.refresh(message)
    return message


async def delete(session: AsyncSession, principal: Principal, message: Message) -> None:
    if not can_draft(principal, message.kind):
        raise _forbid()
    if message.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "not_draft")
    await session.delete(message)
    await session.flush()


async def _targets_disaster(session: AsyncSession, message: Message) -> bool:
    levels = await levels_of(session)
    disaster = {code for code, level in levels.items() if level is OpLevel.DISASTER}
    if not disaster:
        return False
    if message.audience == "user":
        return False
    codes = set(message.gouvernorat_codes)
    return not codes or bool(codes & disaster)


#: Shortest emergency reason that lets the author of an alert publish it alone (phase 10 §5.1).
EMERGENCY_REASON_MIN = 10


async def _four_eyes(
    session: AsyncSession, principal: Principal, message: Message, emergency_reason: str | None
) -> str | None:
    """The emergency reason to record when the author publishes alone, None when a second person publishes.

    Raises ``403 second_reviewer_required`` when the publisher wrote or last edited the alert and gave no reason."""
    if message.kind != "alert" or not await settings_service.get(session, settings_domain.ALERTS_FOUR_EYES):
        return None
    actor = audit.actor_of(principal)
    if actor not in (message.created_by, message.updated_by):
        return None
    reason = (emergency_reason or "").strip()
    if not reason:
        raise _forbid("second_reviewer_required")
    if len(reason) < EMERGENCY_REASON_MIN:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reason_required")
    return reason


async def publish(
    session: AsyncSession, principal: Principal, message: Message, emergency_reason: str | None = None
) -> None:
    if not can_publish(principal, message.kind):
        raise _forbid()
    if message.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "not_draft")
    await check_scope(session, principal, message)
    if message.kind == "info" and await _targets_disaster(session, message):
        # Requirements §6.4: non-essential functions are suspended at disaster level; alerts are not.
        raise HTTPException(status.HTTP_409_CONFLICT, "suspended_by_level")
    if message.kind == "alert" and (message.expires_at is None or message.expires_at <= _now()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_expiry")
    single = await _four_eyes(session, principal, message, emergency_reason)
    if single is not None:
        message.single_reviewer, message.emergency_reason = True, single
    message.status, message.published_at = "published", _now()
    message.published_by, message.published_by_name = audit.actor_of(principal), audit.name_of(principal)
    message.version += 1
    for channel in message.channels:
        session.add(Dispatch(message_id=message.id, channel=channel, purpose="publish", status="pending"))
    await session.flush()
    if message.kind == "alert":
        out = await message_out(session, message)
        payload = {"message": out.model_dump(mode="json"), "gouvernorat_codes": await area_codes(session, message)}
        await emit(session, "alert.issued", payload)
        if message.single_reviewer:
            # Published alone in an emergency: a second publisher looks at it afterwards.
            await emit(session, "alert.review_needed", payload)


async def acknowledge(session: AsyncSession, principal: Principal, message: Message) -> None:
    """A second publisher has looked at an alert published alone under the emergency override (phase 10 §5.1)."""
    if not can_publish(principal, message.kind):
        raise _forbid()
    await check_scope(session, principal, message)
    if not message.single_reviewer:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    if message.reviewed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_acknowledged")
    if audit.actor_of(principal) in (message.published_by, message.created_by, message.updated_by):
        raise _forbid("second_reviewer_required")
    message.reviewed_by, message.reviewed_by_name = audit.actor_of(principal), audit.name_of(principal)
    message.reviewed_at = _now()
    await session.flush()


async def cancel(session: AsyncSession, principal: Principal, message: Message) -> None:
    if not can_publish(principal, message.kind):
        raise _forbid()
    if message.status != "published":
        raise HTTPException(status.HTTP_409_CONFLICT, "not_published")
    await check_scope(session, principal, message)
    message.status, message.cancelled_at = "cancelled", _now()
    message.version += 1
    await session.execute(
        text(
            "UPDATE notify.dispatch SET status = 'skipped', finished_at = now(), error = 'cancelled' "
            "WHERE message_id = :mid AND status IN ('pending', 'running')"
        ),
        {"mid": message.id},
    )
    if message.kind == "alert" and "push" in message.channels:
        # Phones that showed the alert are told it is lifted.
        session.add(Dispatch(message_id=message.id, channel="push", purpose="cancel", status="pending"))
    await session.flush()


async def expire_alerts(session: AsyncSession) -> list[uuid.UUID]:
    rows = await session.scalars(
        text(
            "UPDATE notify.message SET status = 'expired', updated_at = now() "
            "WHERE kind = 'alert' AND status = 'published' AND expires_at <= now() RETURNING id"
        ).columns(Message.id)
    )
    return list(rows)


# ---------------------------------------------------------------- one-user lookup

# Exact, case-insensitive match on the registered profile e-mail of an active citizen account. No partial
# search: the caller must already know the address (served by ix_profile_email_lower).
_LOOKUP_SQL = """
    SELECT a.user_id, p.first_name, p.last_name, p.email, p.gouvernorat_code, p.phone_enc IS NOT NULL AS has_phone,
           EXISTS (SELECT 1 FROM notify.device d WHERE d.user_id = a.user_id) AS has_push
    FROM identity.profile p
    JOIN identity.account a ON a.user_id = p.user_id AND a.kind = 'citizen' AND a.status = 'active'
    WHERE lower(p.email) = :email
    LIMIT 2
"""


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain.lower()}"


def mask_name(first_name: str | None, last_name: str | None) -> str | None:
    first, last = (first_name or "").strip(), (last_name or "").strip()
    if not first and not last:
        return None
    return " ".join(part for part in (f"{first[:1]}***" if first else "", f"{last[:1]}." if last else "") if part)


async def lookup_user(session: AsyncSession, email: str, principal: Principal | None = None) -> schemas.UserLookupOut:
    rows = (await session.execute(text(_LOOKUP_SQL), {"email": email.strip().lower()})).all()
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user_not_found")
    if len(rows) > 1:  # a stale profile still holds an address another account now uses
        raise HTTPException(status.HTTP_409_CONFLICT, "ambiguous_email")
    row = rows[0]
    if principal is not None and not principal.is_national and row.gouvernorat_code != principal.gouvernorat_code:
        # Phase 9 §5.6: a regional editor resolves the accounts of its gouvernorat only.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return schemas.UserLookupOut(
        user_id=row.user_id,
        display_name=mask_name(row.first_name, row.last_name),
        email=mask_email(row.email),
        channels=schemas.UserChannels(push=bool(row.has_push), sms=bool(row.has_phone), email=True),
    )


# ---------------------------------------------------------------- recipients


# Shared target conditions: ``d`` is a device, ``p`` the owner's profile, ``m`` the message.
_GEO_DEVICE = """
    (cardinality(m.gouvernorat_codes) = 0 AND m.area_polygon IS NULL)
    OR (m.area_polygon IS NULL AND d.gouvernorat_code = ANY(m.gouvernorat_codes))
    OR (m.area_polygon IS NULL AND d.gouvernorat_code IS NULL AND p.gouvernorat_code = ANY(m.gouvernorat_codes))
    OR (m.area_polygon IS NOT NULL AND d.location IS NOT NULL
        AND ST_Intersects(m.area_polygon, CAST(d.location AS geometry)))
    OR (m.area_polygon IS NOT NULL AND d.location IS NULL AND p.gouvernorat_code IN (
        SELECT g.code FROM geo.gouvernorat g WHERE ST_Intersects(g.boundary, m.area_polygon)))
"""
_GEO_PROFILE = """
    (cardinality(m.gouvernorat_codes) = 0 AND m.area_polygon IS NULL)
    OR (m.area_polygon IS NULL AND p.gouvernorat_code = ANY(m.gouvernorat_codes))
    OR (m.area_polygon IS NOT NULL AND p.gouvernorat_code IN (
        SELECT g.code FROM geo.gouvernorat g WHERE ST_Intersects(g.boundary, m.area_polygon)))
"""
_AUDIENCE = """
    m.kind = 'alert' OR m.audience = 'all'
    OR (m.audience = 'volunteers' AND EXISTS (
        SELECT 1 FROM identity.volunteer v WHERE v.user_id = {owner} AND v.status = 'approved'))
    OR (m.audience = 'organizations' AND EXISTS (
        SELECT 1 FROM org.member om JOIN org.organization o ON o.id = om.org_id
        WHERE om.user_id = {owner} AND o.status = 'active'
          AND (cardinality(m.org_kinds) = 0 OR o.kind = ANY(m.org_kinds))))
"""


def _device_target(owner: str = "d.user_id") -> str:
    return (
        f"((m.audience = 'user' AND {owner} = m.user_id) OR (coalesce(m.audience, 'all') <> 'user' "
        f"AND ({_AUDIENCE.format(owner=owner)}) AND ({_GEO_DEVICE})))"
    )


def _profile_target() -> str:
    return (
        "((m.audience = 'user' AND p.user_id = m.user_id) OR (coalesce(m.audience, 'all') <> 'user' "
        f"AND ({_AUDIENCE.format(owner='p.user_id')}) AND ({_GEO_PROFILE})))"
    )


DEVICES_SQL = f"""
    SELECT d.token, d.platform, d.locale FROM notify.device d
    JOIN notify.message m ON m.id = :mid
    LEFT JOIN identity.profile p ON p.user_id = d.user_id
    WHERE d.token > :after AND {_device_target()}
    ORDER BY d.token LIMIT :limit
"""  # noqa: S608 (constant SQL fragments, values are bound)
# Phones and e-mails of registered profiles (one message per address, in the profile's language). Phones are
# encrypted: ``address`` is then the hex blind index (dedup and cursor) and ``secret`` the encrypted number.
PROFILES_SQL = """
    SELECT DISTINCT ON (address) address, locale, secret FROM (
        SELECT {column} AS address, p.locale, {secret} AS secret FROM identity.profile p
        JOIN identity.account a ON a.user_id = p.user_id AND a.status = 'active'
        JOIN notify.message m ON m.id = :mid
        WHERE {column} IS NOT NULL AND {target}
        {extra}
    ) r
    WHERE address > :after
    ORDER BY address LIMIT :limit
"""
# Institutions are reached at their members' e-mails (members may have no citizen profile).
_ORG_EMAILS = """
    UNION ALL
    SELECT om.email AS address, 'ar' AS locale, NULL::bytea AS secret FROM org.member om
    JOIN org.organization o ON o.id = om.org_id AND o.status = 'active'
    JOIN notify.message m ON m.id = :mid
    WHERE om.email IS NOT NULL AND m.audience = 'organizations'
      AND (cardinality(m.gouvernorat_codes) = 0 OR o.gouvernorat_code = ANY(m.gouvernorat_codes))
      AND (cardinality(m.org_kinds) = 0 OR o.kind = ANY(m.org_kinds))
"""


async def org_acks(session: AsyncSession, message: Message) -> schemas.OrgAcks:
    rows = (
        await session.execute(
            text(
                "SELECT o.id, o.name, o.kind, o.gouvernorat_code, a.acked_at, a.acked_by_name "  # noqa: S608 (constant SQL fragments, values are bound)
                "FROM org.organization o JOIN notify.message m ON m.id = :mid "
                "LEFT JOIN notify.org_ack a ON a.message_id = m.id AND a.org_id = o.id "
                f"WHERE {ORG_TARGET} ORDER BY a.acked_at IS NOT NULL, a.acked_at DESC, o.name, o.id"
            ),
            {"mid": message.id},
        )
    ).all()
    items = [
        schemas.OrgAckRow(
            org_id=r.id,
            name=r.name,
            kind=r.kind,
            gouvernorat_code=r.gouvernorat_code,
            acked_at=r.acked_at,
            acked_by=r.acked_by_name,
        )
        for r in rows
    ]
    return schemas.OrgAcks(targeted=len(items), acked=sum(1 for i in items if i.acked_at), items=items)


def profiles_sql(channel: str) -> str:
    column = "encode(p.phone_hash, 'hex')" if channel == "sms" else "lower(p.email)"
    secret = "p.phone_enc" if channel == "sms" else "NULL::bytea"
    extra = _ORG_EMAILS if channel == "email" else ""
    return PROFILES_SQL.format(column=column, secret=secret, target=_profile_target(), extra=extra)


def phone_of(secret: bytes) -> str:
    """Clear phone number of a ``profiles_sql("sms")`` row, decrypted just before sending."""
    return get_cipher().decrypt(bytes(secret), context=PHONE_CONTEXT)


async def audience(session: AsyncSession, message: Message) -> schemas.AudienceOut:
    push = await session.scalar(
        text(
            "SELECT count(*) FROM notify.device d JOIN notify.message m ON m.id = :mid "  # noqa: S608 (constant SQL fragments, values are bound)
            f"LEFT JOIN identity.profile p ON p.user_id = d.user_id WHERE {_device_target()}"
        ),
        {"mid": message.id},
    )
    counts: dict[str, int] = {}
    for channel in ("sms", "email"):
        sql = profiles_sql(channel).replace("LIMIT :limit", "").replace("ORDER BY address", "")
        counts[channel] = int(
            await session.scalar(text(f"SELECT count(*) FROM ({sql}) c"), {"mid": message.id, "after": ""}) or 0  # noqa: S608 (constant SQL fragments, values are bound)
        )
    return schemas.AudienceOut(push=int(push or 0), sms=counts["sms"], email=counts["email"])


# ---------------------------------------------------------------- public (app)


_ACTIVE_ALERT = and_(Message.kind == "alert", Message.status == "published", Message.expires_at > func.now())


def _covers(lat: float | None, lon: float | None, gouvernorat_code: int | None) -> Any:
    conditions: list[Any] = [and_(func.cardinality(Message.gouvernorat_codes) == 0, Message.area_polygon.is_(None))]
    if gouvernorat_code is not None:
        conditions.append(any_(Message.gouvernorat_codes) == gouvernorat_code)
        conditions.append(
            text(
                "ST_Intersects(notify.message.area_polygon, (SELECT boundary FROM geo.gouvernorat WHERE code = :cov_g))"
            ).bindparams(cov_g=gouvernorat_code)
        )
    if lat is not None and lon is not None:
        point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
        conditions.append(func.ST_Intersects(Message.area_polygon, point))
        conditions.append(
            text(
                "notify.message.gouvernorat_codes && ARRAY(SELECT code FROM geo.gouvernorat "
                "WHERE ST_Intersects(boundary, ST_SetSRID(ST_MakePoint(:cov_lon, :cov_lat), 4326)))::smallint[]"
            ).bindparams(cov_lon=lon, cov_lat=lat)
        )
    return or_(*conditions)


async def active_alerts(
    session: AsyncSession, lat: float | None, lon: float | None, gouvernorat_code: int | None
) -> list[schemas.PublicAlert]:
    query = select(Message).where(_ACTIVE_ALERT)
    if lat is not None or gouvernorat_code is not None:
        query = query.where(_covers(lat, lon, gouvernorat_code))
    rows = await session.scalars(
        query.order_by(
            func.array_position(text("ARRAY['high', 'medium', 'low']"), Message.severity), Message.published_at.desc()
        )
    )
    return [
        schemas.PublicAlert(
            id=m.id,
            severity=m.severity,
            category=m.category,
            hazard=m.hazard,
            title=m.title,
            body=m.body,
            area=await _area(session, m),
            published_at=m.published_at,
            expires_at=m.expires_at,
        )
        for m in rows
    ]


async def inbox(
    session: AsyncSession, user_id: uuid.UUID, limit: int, cursor: str | None
) -> tuple[list[schemas.InboxItem], str | None]:
    """Messages addressed to this account (any of its devices or its profile) and recent alerts for its area."""
    where = f"""
        m.status IN ('published', 'expired', 'cancelled') AND m.published_at IS NOT NULL
        AND (m.kind = 'info' OR m.published_at > now() - make_interval(days => {INBOX_ALERT_DAYS}))
        AND (m.kind = 'alert' OR m.status = 'published')
        AND (
            EXISTS (SELECT 1 FROM notify.device d LEFT JOIN identity.profile p ON p.user_id = d.user_id
                    WHERE d.user_id = :uid AND {_device_target()})
            OR EXISTS (SELECT 1 FROM identity.profile p WHERE p.user_id = :uid AND {_profile_target()})
            OR (m.audience = 'user' AND m.user_id = :uid)
            OR (m.kind = 'alert' AND cardinality(m.gouvernorat_codes) = 0 AND m.area_polygon IS NULL)
            OR (m.kind = 'info' AND m.audience = 'all' AND cardinality(m.gouvernorat_codes) = 0)
        )
    """  # noqa: S608 (constant SQL fragments, values are bound)
    params: dict[str, Any] = {"uid": user_id, "limit": limit}
    if cursor:
        at, mid = _decode(cursor)
        where += " AND (m.published_at < :c_at OR (m.published_at = :c_at AND m.id < :c_id))"
        params |= {"c_at": at, "c_id": mid}
    ids = list(
        await session.scalars(
            text(
                f"SELECT m.id FROM notify.message m WHERE {where} ORDER BY m.published_at DESC, m.id DESC LIMIT :limit"  # noqa: S608 (constant SQL fragments, values are bound)
            ),
            params,
        )
    )
    messages = {m.id: m for m in await session.scalars(select(Message).where(Message.id.in_(ids)))}
    now = _now()
    items = [
        schemas.InboxItem(
            id=m.id,
            kind=m.kind,
            topic=m.topic,
            severity=m.severity,
            title=m.title,
            body=m.body,
            published_at=m.published_at,
            expires_at=m.expires_at,
            active=m.kind == "alert" and m.status == "published" and (m.expires_at or now) > now,
        )
        for m in (messages[i] for i in ids)
    ]
    next_cursor = _encode(items[-1].published_at, items[-1].id) if len(items) == limit else None
    return items, next_cursor
