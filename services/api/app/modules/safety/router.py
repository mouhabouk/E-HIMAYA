"""Personal safety between citizens (phase B2, docs/phase-b/design-b2.md §4 and §7).

* Linked contacts: a registered user creates an invitation code and gives it (by SMS or WhatsApp, from the phone) to a
  relative who also uses e-Himaya; once accepted, the two accounts are linked both ways. No address book is uploaded.
* Alerts: an SOS message sent in the app to linked contacts rings on their critical channel; the receiver opens it
  over the API (message, position, battery, live location) and the sender sees who read it.
* Live location: a random link that ends by itself; the portal page reads it with the token, without an account.
* Safety check: a timer fired by the server (even if the phone is off) unless the owner answers "I am fine".

The operations room is not involved and staff scopes cannot read any of it: the SOS report to 198 stays separate.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import as_system, get_session
from app.core.ratelimit import client_key, enforce
from app.modules.audit import service as audit
from app.modules.identity.models import AccountKind
from app.modules.identity.service import CurrentReporter, Reporter, limit_reporter
from app.modules.notify import outbox
from app.modules.reports.schemas import LocationIn
from app.modules.safety import service
from app.modules.safety.models import Alert, AlertRecipient, Invitation, Link, LiveShare, SafetyCheck
from app.modules.settings import domain as settings_domain
from app.modules.settings import service as settings

router = APIRouter(prefix="/api/v1", tags=["safety"])
Session = Annotated[AsyncSession, Depends(get_session)]

HOUR_S = 3600
MAX_OPEN_INVITATIONS = 5
CODE_TRIES_PER_HOUR = 10
MAX_LINKS = 20
ALERTS_PER_HOUR = 10
LIVE_UPDATES_PER_MINUTE = 12
LIVE_VIEWS_PER_MINUTE = 30
INVITATION_TTL = timedelta(hours=48)

Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Battery = Annotated[int, Field(ge=0, le=100)]


def _now() -> datetime:
    return datetime.now(UTC)


def _registered(reporter: Reporter) -> Reporter:
    # Linking needs an accountable, stable identity: a guest (anonymous device) cannot link or alert contacts.
    if reporter.principal is None or reporter.kind is AccountKind.ANONYMOUS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "registration_required")
    return reporter


def _gone(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_410_GONE, detail)


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "not_found")


# ---------------------------------------------------------------- schemas


class InvitationOut(BaseModel):
    code: str
    expires_at: datetime


class InvitationPreview(BaseModel):
    first_name: str | None
    # Last two digits only, so the person can check who invited them.
    phone_hint: str | None
    expires_at: datetime


class LinkOut(BaseModel):
    id: uuid.UUID
    first_name: str | None
    phone: str | None
    created_at: datetime


class LinkList(BaseModel):
    items: list[LinkOut]


class PointOut(BaseModel):
    lat: float
    lon: float
    accuracy_m: float | None
    at: datetime


class AlertIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_uuid: uuid.UUID
    message: Message
    location: LocationIn | None = None
    battery: Battery | None = None
    # Null: every linked contact; otherwise the chosen links (a group of the phone).
    link_ids: list[uuid.UUID] | None = Field(default=None, max_length=50)
    live_share_id: uuid.UUID | None = None


class AlertSentOut(BaseModel):
    id: uuid.UUID
    recipients: int
    created_at: datetime


class LiveOut(BaseModel):
    active: bool
    points: list[PointOut]
    battery: int | None
    updated_at: datetime | None
    expires_at: datetime
    stopped_at: datetime | None


class AlertOut(BaseModel):
    id: uuid.UUID
    kind: Literal["sos", "check"]
    mine: bool
    sender_first_name: str | None
    sender_phone: str | None
    message: str
    position: PointOut | None
    battery: int | None
    created_at: datetime
    expires_at: datetime
    seen: bool
    # Sender only: how many recipients and how many opened it.
    recipients: int | None = None
    seen_by: int | None = None
    live: LiveOut | None = None


class AlertList(BaseModel):
    items: list[AlertOut]


class LiveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minutes: int = Field(default=60, ge=15)


class LiveStartOut(BaseModel):
    id: uuid.UUID
    # Shown once: only its hash is kept. The phone builds the portal link with it.
    token: str
    expires_at: datetime


class PositionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: LocationIn
    battery: Battery | None = None


class LiveViewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: Annotated[str, StringConstraints(min_length=20, max_length=100)]


class CheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minutes: int = Field(ge=5)
    message: Message
    location: LocationIn | None = None
    battery: Battery | None = None


class ExtendIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minutes: int = Field(ge=5)


class CheckOut(BaseModel):
    id: uuid.UUID
    due_at: datetime
    status: str
    created_at: datetime
    alert_id: uuid.UUID | None
    # Linked contacts that would be alerted now (0: only the SMS of the phone can reach anyone).
    contacts: int


# ---------------------------------------------------------------- invitations and links


async def _link_out(session: AsyncSession, link: Link, me: uuid.UUID) -> LinkOut:
    first_name, phone = await service.person(session, link.other(me))
    return LinkOut(id=link.id, first_name=first_name, phone=phone, created_at=link.created_at)


@router.post("/safety/invitations", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
async def create_invitation(reporter: CurrentReporter, session: Session) -> InvitationOut:
    me = _registered(reporter).user_id
    now = _now()
    open_count = await session.scalar(
        select(func.count())
        .select_from(Invitation)
        .where(
            Invitation.inviter_id == me,
            Invitation.accepted_at.is_(None),
            Invitation.cancelled_at.is_(None),
            Invitation.expires_at > now,
        )
    )
    if (open_count or 0) >= MAX_OPEN_INVITATIONS:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too_many_invitations")
    code = service.new_code()
    row = Invitation(inviter_id=me, code_hash=service.code_hash(code), expires_at=now + INVITATION_TTL)
    session.add(row)
    await session.flush()
    await audit.record(session, actor=reporter.actor, action="safety.invite", target=f"safety_invitation:{row.id}")
    await session.commit()
    return InvitationOut(code=code, expires_at=row.expires_at)


async def _invitation(session: AsyncSession, reporter: Reporter, raw: str) -> Invitation:
    # Codes are short: tries are limited per account (and the code space is 2^40).
    await enforce(f"safety-code:{reporter.user_id}", CODE_TRIES_PER_HOUR, HOUR_S)
    code = service.normalize_code(raw)
    if code is None:
        raise _not_found()
    async with as_system(session) as system:
        row = await system.scalar(select(Invitation).where(Invitation.code_hash == service.code_hash(code)))
    if row is None or row.cancelled_at is not None:
        raise _not_found()
    if row.accepted_at is not None:
        raise _gone("invitation_used")
    if row.expires_at <= _now():
        raise _gone("invitation_expired")
    if row.inviter_id == reporter.user_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "own_invitation")
    return row


@router.get("/safety/invitations/{code}", response_model=InvitationPreview)
async def preview_invitation(code: str, reporter: CurrentReporter, session: Session) -> InvitationPreview:
    _registered(reporter)
    row = await _invitation(session, reporter, code)
    async with as_system(session) as system:
        first_name, phone = await service.person(system, row.inviter_id)
    return InvitationPreview(first_name=first_name, phone_hint=service.phone_hint(phone), expires_at=row.expires_at)


@router.post("/safety/invitations/{code}/accept", response_model=LinkOut, status_code=status.HTTP_201_CREATED)
async def accept_invitation(code: str, reporter: CurrentReporter, session: Session) -> LinkOut:
    me = _registered(reporter).user_id
    row = await _invitation(session, reporter, code)
    a, b = service.ordered(row.inviter_id, me)
    async with as_system(session) as system:
        existing = await system.scalar(select(Link).where(Link.user_a == a, Link.user_b == b))
        if existing is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "already_linked")
        for user in (me, row.inviter_id):
            if len(await service.links_of(system, user)) >= MAX_LINKS:
                raise HTTPException(status.HTTP_409_CONFLICT, "too_many_links")
        link = Link(user_a=a, user_b=b)
        system.add(link)
        row.accepted_by = me
        row.accepted_at = _now()
        await system.flush()
        outbox.push(system, row.inviter_id, "safety_link", {"id": str(link.id)})
        out = await _link_out(system, link, me)
    await audit.record(session, actor=reporter.actor, action="safety.link", target=f"safety_link:{link.id}")
    await session.commit()
    return out


@router.get("/safety/links", response_model=LinkList)
async def my_links(reporter: CurrentReporter, session: Session) -> LinkList:
    me = _registered(reporter).user_id
    links = await service.links_of(session, me)
    # Row-level security returned only the caller's links; the other side's profile needs the system scope.
    async with as_system(session) as system:
        items = [await _link_out(system, link, me) for link in links]
    return LinkList(items=items)


@router.delete("/safety/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_link(link_id: uuid.UUID, reporter: CurrentReporter, session: Session) -> Response:
    me = _registered(reporter).user_id
    link = await session.get(Link, link_id)
    if link is None or me not in (link.user_a, link.user_b):
        raise _not_found()
    await session.delete(link)
    await audit.record(session, actor=reporter.actor, action="safety.unlink", target=f"safety_link:{link_id}")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- alerts


def _point(value: dict[str, object] | None) -> PointOut | None:
    return None if value is None else PointOut.model_validate(value)


def _live_out(share: LiveShare, now: datetime) -> LiveOut:
    return LiveOut(
        active=share.stopped_at is None and share.expires_at > now,
        points=[PointOut.model_validate(p) for p in share.points or []],
        battery=share.battery,
        updated_at=share.updated_at,
        expires_at=share.expires_at,
        stopped_at=share.stopped_at,
    )


async def _alert_out(session: AsyncSession, alert: Alert, me: uuid.UUID) -> AlertOut:
    """``session`` runs with the system scope; the caller checked that ``me`` sent or received the alert."""
    now = _now()
    mine = alert.sender_id == me
    first_name, phone = await service.person(session, alert.sender_id)
    rows = list(await session.scalars(select(AlertRecipient).where(AlertRecipient.alert_id == alert.id)))
    own = next((r for r in rows if r.recipient_id == me), None)
    share = await session.get(LiveShare, alert.live_share_id) if alert.live_share_id else None
    return AlertOut(
        id=alert.id,
        kind=alert.kind,
        mine=mine,
        sender_first_name=first_name,
        sender_phone=phone,
        message=alert.message,
        position=_point(alert.position),
        battery=alert.battery,
        created_at=alert.created_at,
        expires_at=alert.expires_at,
        seen=mine or (own is not None and own.seen_at is not None),
        recipients=len(rows) if mine else None,
        seen_by=sum(1 for r in rows if r.seen_at is not None) if mine else None,
        live=_live_out(share, now) if share is not None else None,
    )


async def _recipients(session: AsyncSession, me: uuid.UUID, link_ids: list[uuid.UUID] | None) -> list[uuid.UUID]:
    links = await service.links_of(session, me)
    if link_ids is not None:
        chosen = set(link_ids)
        known = {link.id for link in links}
        if not chosen <= known:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown_link")
        links = [link for link in links if link.id in chosen]
    return [link.other(me) for link in links]


@router.post("/safety/alerts", response_model=AlertSentOut, status_code=status.HTTP_201_CREATED)
async def send_alert(reporter: CurrentReporter, session: Session, body: AlertIn) -> AlertSentOut:
    me = _registered(reporter).user_id
    existing = await session.scalar(select(Alert).where(Alert.sender_id == me, Alert.client_uuid == body.client_uuid))
    if existing is not None:
        # The phone retries after a lost answer: the same alert, never a second ring.
        async with as_system(session) as system:
            count = await system.scalar(
                select(func.count()).select_from(AlertRecipient).where(AlertRecipient.alert_id == existing.id)
            )
        return AlertSentOut(id=existing.id, recipients=count or 0, created_at=existing.created_at)
    await enforce(f"safety-alert:{me}", ALERTS_PER_HOUR, HOUR_S)
    recipients = await _recipients(session, me, body.link_ids)
    if not recipients:
        raise HTTPException(status.HTTP_409_CONFLICT, "no_linked_contact")
    if body.live_share_id is not None:
        share = await session.get(LiveShare, body.live_share_id)
        if share is None or share.owner_id != me:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown_live_share")
    position = service.point(body.location.lat, body.location.lon, body.location.accuracy_m) if body.location else None
    async with as_system(session) as system:
        alert = await service.send_alert(
            system,
            sender_id=me,
            client_uuid=body.client_uuid,
            kind="sos",
            message=body.message,
            position=position,
            battery=body.battery,
            recipients=recipients,
            live_share_id=body.live_share_id,
        )
    # No message or position in the audit trail: only that an alert went to n contacts.
    await audit.record(
        session,
        actor=reporter.actor,
        action="safety.alert",
        target=f"safety_alert:{alert.id}",
        details={"recipients": len(recipients)},
    )
    await session.commit()
    return AlertSentOut(id=alert.id, recipients=len(recipients), created_at=alert.created_at)


@router.get("/safety/alerts", response_model=AlertList)
async def recent_alerts(reporter: CurrentReporter, session: Session) -> AlertList:
    """Alerts sent or received in the last 24 hours (row-level security keeps the others out)."""
    me = _registered(reporter).user_id
    received = select(AlertRecipient.alert_id).where(AlertRecipient.recipient_id == me)
    alerts = list(
        await session.scalars(
            select(Alert)
            .where(Alert.expires_at > _now(), or_(Alert.sender_id == me, Alert.id.in_(received)))
            .order_by(Alert.created_at.desc())
            .limit(50)
        )
    )
    async with as_system(session) as system:
        items = [await _alert_out(system, a, me) for a in alerts]
    return AlertList(items=items)


async def _is_recipient(session: AsyncSession, alert_id: uuid.UUID, me: uuid.UUID) -> bool:
    return await session.get(AlertRecipient, (alert_id, me)) is not None


async def _visible_alert(session: AsyncSession, alert_id: uuid.UUID, me: uuid.UUID) -> Alert:
    # Row-level security already hides other people's alerts; checked here too (defence in depth).
    alert = await session.get(Alert, alert_id)
    if alert is None or (alert.sender_id != me and not await _is_recipient(session, alert_id, me)):
        raise _not_found()
    if alert.expires_at <= _now():
        raise _gone("alert_expired")
    return alert


@router.get("/safety/alerts/{alert_id}", response_model=AlertOut)
async def get_alert(alert_id: uuid.UUID, reporter: CurrentReporter, session: Session) -> AlertOut:
    me = _registered(reporter).user_id
    alert = await _visible_alert(session, alert_id, me)
    async with as_system(session) as system:
        return await _alert_out(system, alert, me)


@router.post("/safety/alerts/{alert_id}/seen", status_code=status.HTTP_204_NO_CONTENT)
async def mark_seen(alert_id: uuid.UUID, reporter: CurrentReporter, session: Session) -> Response:
    me = _registered(reporter).user_id
    await _visible_alert(session, alert_id, me)
    row = await session.get(AlertRecipient, (alert_id, me))
    if row is None:
        raise _not_found()
    if row.seen_at is None:
        row.seen_at = _now()
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- live location


async def _own_share(session: AsyncSession, share_id: uuid.UUID, me: uuid.UUID) -> LiveShare:
    share = await session.get(LiveShare, share_id)
    if share is None or share.owner_id != me:
        raise _not_found()
    return share


@router.post("/safety/live", response_model=LiveStartOut, status_code=status.HTTP_201_CREATED)
async def start_live(request: Request, reporter: CurrentReporter, session: Session, body: LiveIn) -> LiveStartOut:
    await limit_reporter(request, reporter, "safety-live", per_account=10, per_ip=10, window_s=HOUR_S)
    max_minutes = int(await settings.get(session, settings_domain.SAFETY_LIVE_MAX_MINUTES))
    if body.minutes > max_minutes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "duration_too_long")
    token = service.new_token()
    now = _now()
    share = LiveShare(
        owner_id=reporter.user_id,
        token_hash=service.token_hash(token),
        started_at=now,
        expires_at=now + timedelta(minutes=body.minutes),
    )
    session.add(share)
    await session.flush()
    await audit.record(session, actor=reporter.actor, action="safety.live_start", target=f"safety_live:{share.id}")
    await session.commit()
    return LiveStartOut(id=share.id, token=token, expires_at=share.expires_at)


@router.put("/safety/live/{share_id}", response_model=LiveOut)
async def live_position(share_id: uuid.UUID, reporter: CurrentReporter, session: Session, body: PositionIn) -> LiveOut:
    await enforce(f"safety-live-pos:{reporter.user_id}", LIVE_UPDATES_PER_MINUTE, 60)
    share = await _own_share(session, share_id, reporter.user_id)
    now = _now()
    if share.stopped_at is not None or share.expires_at <= now:
        raise _gone("live_ended")
    points = list(share.points or [])
    points.append(service.point(body.location.lat, body.location.lon, body.location.accuracy_m, now))
    share.points = points[-service.MAX_POINTS :]
    share.battery = body.battery
    share.updated_at = now
    await session.commit()
    return _live_out(share, now)


@router.post("/safety/live/{share_id}/stop", response_model=LiveOut)
async def stop_live(share_id: uuid.UUID, reporter: CurrentReporter, session: Session) -> LiveOut:
    share = await _own_share(session, share_id, reporter.user_id)
    now = _now()
    if share.stopped_at is None:
        share.stopped_at = now
        await audit.record(session, actor=reporter.actor, action="safety.live_stop", target=f"safety_live:{share.id}")
        await session.commit()
    return _live_out(share, now)


@router.get("/safety/live/{share_id}", response_model=LiveOut)
async def follow_live(share_id: uuid.UUID, reporter: CurrentReporter, session: Session) -> LiveOut:
    """The owner, or a contact who received an alert pointing to this share, follows it in the app."""
    me = reporter.user_id
    async with as_system(session) as system:
        share = await system.get(LiveShare, share_id)
        if share is None:
            raise _not_found()
        if share.owner_id != me:
            allowed = await system.scalar(
                select(func.count())
                .select_from(Alert)
                .join(AlertRecipient, AlertRecipient.alert_id == Alert.id)
                .where(Alert.live_share_id == share_id, AlertRecipient.recipient_id == me)
            )
            if not allowed:
                raise _not_found()
        return _live_out(share, _now())


@router.post("/live/view", response_model=LiveOut)
async def view_live(request: Request, session: Session, body: LiveViewIn) -> LiveOut:
    """Public: the portal page of a live location link. The token travels in the body, never in a logged URL; no name
    or account is returned, only the points."""
    await enforce(f"live-view:{client_key(request)}", LIVE_VIEWS_PER_MINUTE, 60)
    async with as_system(session) as system:
        share = await system.scalar(select(LiveShare).where(LiveShare.token_hash == service.token_hash(body.token)))
        if share is None:
            raise _not_found()
        return _live_out(share, _now())


# ---------------------------------------------------------------- safety check


async def _check_out(session: AsyncSession, check: SafetyCheck, me: uuid.UUID) -> CheckOut:
    return CheckOut(
        id=check.id,
        due_at=check.due_at,
        status=check.status,
        created_at=check.created_at,
        alert_id=check.alert_id,
        contacts=len(await service.links_of(session, me)),
    )


async def _max_minutes(session: AsyncSession) -> int:
    return int(await settings.get(session, settings_domain.SAFETY_CHECK_MAX_HOURS)) * 60


async def _own_check(session: AsyncSession, check_id: uuid.UUID, me: uuid.UUID) -> SafetyCheck:
    check = await session.get(SafetyCheck, check_id)
    if check is None or check.owner_id != me:
        raise _not_found()
    return check


@router.post("/safety/checks", response_model=CheckOut, status_code=status.HTTP_201_CREATED)
async def start_check(reporter: CurrentReporter, session: Session, body: CheckIn) -> CheckOut:
    me = _registered(reporter).user_id
    if body.minutes > await _max_minutes(session):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "duration_too_long")
    active = await session.scalar(select(SafetyCheck).where(SafetyCheck.owner_id == me, SafetyCheck.status == "active"))
    if active is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "check_active")
    now = _now()
    check = SafetyCheck(
        owner_id=me,
        due_at=now + timedelta(minutes=body.minutes),
        message=body.message,
        position=service.point(body.location.lat, body.location.lon, body.location.accuracy_m)
        if body.location
        else None,
        battery=body.battery,
        created_at=now,
    )
    session.add(check)
    await session.flush()
    await audit.record(session, actor=reporter.actor, action="safety.check_start", target=f"safety_check:{check.id}")
    out = await _check_out(session, check, me)
    await session.commit()
    return out


@router.get("/safety/checks/current", response_model=CheckOut | None)
async def current_check(reporter: CurrentReporter, session: Session) -> CheckOut | None:
    me = _registered(reporter).user_id
    check = await session.scalar(
        select(SafetyCheck).where(SafetyCheck.owner_id == me).order_by(SafetyCheck.created_at.desc()).limit(1)
    )
    return None if check is None else await _check_out(session, check, me)


async def _active(session: AsyncSession, check_id: uuid.UUID, me: uuid.UUID) -> SafetyCheck:
    check = await _own_check(session, check_id, me)
    if check.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, f"check_{check.status}")
    return check


@router.post("/safety/checks/{check_id}/ok", response_model=CheckOut)
async def check_ok(check_id: uuid.UUID, reporter: CurrentReporter, session: Session) -> CheckOut:
    """ "I am fine": the check ends and nobody is alerted."""
    me = _registered(reporter).user_id
    check = await _active(session, check_id, me)
    check.status = "ok"
    check.ended_at = _now()
    await audit.record(session, actor=reporter.actor, action="safety.check_ok", target=f"safety_check:{check.id}")
    out = await _check_out(session, check, me)
    await session.commit()
    return out


@router.post("/safety/checks/{check_id}/extend", response_model=CheckOut)
async def check_extend(check_id: uuid.UUID, reporter: CurrentReporter, session: Session, body: ExtendIn) -> CheckOut:
    me = _registered(reporter).user_id
    check = await _active(session, check_id, me)
    now = _now()
    due = max(check.due_at, now) + timedelta(minutes=body.minutes)
    if due - now > timedelta(minutes=await _max_minutes(session)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "duration_too_long")
    check.due_at = due
    out = await _check_out(session, check, me)
    await session.commit()
    return out


@router.put("/safety/checks/{check_id}/position", response_model=CheckOut)
async def check_position(
    check_id: uuid.UUID, reporter: CurrentReporter, session: Session, body: PositionIn
) -> CheckOut:
    """The phone keeps the last position up to date, so a fired check carries where the person was last."""
    me = _registered(reporter).user_id
    await enforce(f"safety-check-pos:{me}", LIVE_UPDATES_PER_MINUTE, 60)
    check = await _active(session, check_id, me)
    check.position = service.point(body.location.lat, body.location.lon, body.location.accuracy_m)
    check.battery = body.battery
    out = await _check_out(session, check, me)
    await session.commit()
    return out
