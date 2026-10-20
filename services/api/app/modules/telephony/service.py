"""Call life cycle and staff actions (docs/api/phase-7-contract.md §4, docs/telephony.md).

    inbound (8000):  ringing ──(an operator answers)──► answered ──(hang-up)──► ended
                       │                                   └──(transfer-198, scenario 2)──► transferred
                       └──(caller hangs up first)──► missed (abandoned)
    outbound (dial): ringing ──(the number answers)──► answered ──► ended;  no answer ──► missed;  error ──► failed

States change from ARI events (``handle_event``, run by the worker's event loop) and from staff actions. Every change
writes its live-feed event (``call.ringing``, ``call.answered``, ``call.ended``, ``call.recording``) in the same
transaction; the feed masks the number for readers without call access (reports/live.py).
"""

import base64
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy import Select, and_, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.events import emit
from app.core.security import Principal
from app.modules.reports.models import Media, Report
from app.modules.reports.service import in_scope
from app.modules.telephony import schemas
from app.modules.telephony.ari import AriClient, AriUnavailable, get_ari
from app.modules.telephony.domain import (
    ACTIVE,
    CALL_ROLES,
    QUEUE,
    CallStatus,
    Direction,
    EndReason,
    Source,
    caller_index,
    mask_number,
    normalize_caller,
    valid_channel_id,
    valid_endpoint,
)
from app.modules.telephony.models import Call, OperatorEndpoint

log = structlog.get_logger()

# A recording is ingested once Asterisk has closed the file (shortly after the hang-up).
RECORDING_SETTLE = timedelta(seconds=3)


def unavailable() -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "telephony_unavailable")


def require_ari() -> AriClient:
    client = get_ari()
    if client is None:
        raise unavailable()
    return client


# ---------------------------------------------------------------- views


def _select() -> Select[Call, str | None]:
    return select(Call, Report.tracking_code).outerjoin(Report, Report.id == Call.report_id)


def sees_numbers(principal: Principal) -> bool:
    return bool(principal.roles & CALL_ROLES)


def _duration(call: Call) -> float | None:
    if call.answered_at is None:
        return None
    end = call.ended_at or datetime.now(UTC)
    return round(max((end - call.answered_at).total_seconds(), 0.0), 1)


def call_out(call: Call, tracking_code: str | None, *, full: bool = True) -> schemas.CallOut:
    number = call.caller_number
    return schemas.CallOut(
        id=call.id,
        direction=call.direction,
        source=call.source,
        caller_number=number if full else mask_number(number),
        caller_masked=not full and number is not None,
        started_at=call.started_at,
        answered_at=call.answered_at,
        ended_at=call.ended_at,
        duration_s=_duration(call),
        operator_user_id=call.operator_user_id,
        queue=call.queue,
        status=call.status,
        end_reason=call.end_reason,
        report_id=call.report_id,
        incident_id=call.incident_id,
        tracking_code=tracking_code,
        gouvernorat_code=call.gouvernorat_code,
        recording_media_id=call.recording_media_id,
        transferred_to=call.transferred_to,
        simulated=call.source == Source.SIM,
    )


def scope_filter(principal: Principal) -> Any:
    """National staff see every call; the others their gouvernorat's, the ringing calls not located yet (the shared
    queue) and the calls they took themselves. Once answered or ended an unlocated call is national only (phase 9)."""
    if principal.is_national:
        return True
    return or_(
        Call.gouvernorat_code == principal.gouvernorat_code,
        and_(Call.gouvernorat_code.is_(None), Call.status == CallStatus.RINGING.value),
        Call.operator_user_id == principal.subject,
    )


def visible(principal: Principal, call: Call) -> bool:
    return (
        (call.gouvernorat_code is None and (principal.is_national or call.status == CallStatus.RINGING.value))
        or (call.gouvernorat_code is not None and in_scope(principal, call.gouvernorat_code))
        or call.operator_user_id == principal.subject
    )


def encode_cursor(started_at: datetime, call_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{started_at.isoformat()}|{call_id}".encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        at, cid = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode().split("|")
        return datetime.fromisoformat(at), uuid.UUID(cid)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc


async def staff_list(
    session: AsyncSession, principal: Principal, status_filter: str | None, limit: int, cursor: str | None
) -> tuple[list[schemas.CallOut], str | None]:
    query = _select().where(scope_filter(principal))
    if status_filter == "active":
        query = query.where(Call.status.in_(ACTIVE))
    elif status_filter:
        query = query.where(Call.status == status_filter)
    if cursor:
        at, cid = decode_cursor(cursor)
        query = query.where(or_(Call.started_at < at, and_(Call.started_at == at, Call.id < cid)))
    rows = (await session.execute(query.order_by(Call.started_at.desc(), Call.id.desc()).limit(limit))).all()
    full = sees_numbers(principal)
    items = [call_out(call, code, full=full) for call, code in rows]
    next_cursor = encode_cursor(rows[-1][0].started_at, rows[-1][0].id) if len(rows) == limit else None
    return items, next_cursor


async def visible_call(
    session: AsyncSession, principal: Principal, call_id: uuid.UUID, *, lock: bool = False
) -> tuple[Call, str | None]:
    query = _select().where(Call.id == call_id)
    if lock:
        query = query.with_for_update(of=Call)
    row = (await session.execute(query)).first()
    if row is None or not visible(principal, row[0]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return row[0], row[1]


async def detail(session: AsyncSession, principal: Principal, call: Call, code: str | None) -> schemas.CallDetail:
    recording = None
    if call.recording_media_id is not None:
        media = await session.get(Media, call.recording_media_id)
        if media is not None and media.status == "stored":
            recording = schemas.RecordingOut(
                media_id=media.id,
                sha256=media.sha256,
                bytes=media.bytes,
                duration_s=media.duration_s,
                created_at=media.created_at,
            )
    return schemas.CallDetail(
        **call_out(call, code, full=sees_numbers(principal)).model_dump(),
        recording=recording,
        transfer_198_available=transfer_available()
        and call.direction == Direction.INBOUND
        and call.status == CallStatus.ANSWERED,
    )


def transfer_available() -> bool:
    settings = get_settings()
    return settings.telephony_transfer_198_enabled and settings.telephony_trunk_enabled


async def emit_call(session: AsyncSession, subject: str, call: Call) -> None:
    """call.* live-feed event: the full item (masked per client by the live feed), routed by gouvernorat."""
    await session.flush()
    code = (
        await session.scalar(select(Report.tracking_code).where(Report.id == call.report_id))
        if call.report_id
        else None
    )
    await emit(
        session,
        subject,
        {
            "call_id": str(call.id),
            "gouvernorat_code": call.gouvernorat_code,
            "call": schemas.as_json(call_out(call, code)),
        },
    )


# ---------------------------------------------------------------- ARI events


def _time(value: object) -> datetime:
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.now(UTC)


def _source(value: object) -> str:
    text = str(value or "").lower()
    return text if text in {s.value for s in Source} else Source.UNKNOWN.value


async def _locked(session: AsyncSession, channel_id: str) -> Call | None:
    return await session.scalar(select(Call).where(Call.channel_id == channel_id).with_for_update())


def _recorded(body: dict[str, Any]) -> bool:
    """Whether Asterisk records this call (``recording: 0|1`` of the dialplan event; the setting when absent)."""
    flag = str(body.get("recording") or "").strip()
    return flag == "1" if flag in ("0", "1") else get_settings().telephony_recording_enabled


async def upsert_inbound(
    session: AsyncSession,
    channel_id: str,
    number: str | None,
    source: str,
    started_at: datetime,
    *,
    recorded: bool = True,
) -> tuple[Call, bool]:
    """The call of an inbound channel, created on first sight. Returns (call, created)."""
    normalized = normalize_caller(number)
    statement = (
        insert(Call)
        .values(
            id=uuid.uuid4(),
            channel_id=channel_id,
            direction=Direction.INBOUND.value,
            source=source,
            caller_number=normalized,
            caller_hash=caller_index(normalized) if normalized else None,
            started_at=started_at,
            queue=QUEUE,
            status=CallStatus.RINGING.value,
            recording_state="pending" if recorded else "none",
        )
        .on_conflict_do_nothing(index_elements=["channel_id"])
        .returning(Call.id)
    )
    created = (await session.execute(statement)).scalar() is not None
    call = await _locked(session, channel_id)
    assert call is not None
    return call, created


async def _tag_channel(channel_id: str, call_id: uuid.UUID) -> None:
    """Hand calls.id to Asterisk while the caller hears the notice: the queue's pre-dial handler puts it in the
    X-EHimaya-Call-Id header of the INVITE to each operator (best effort: the softphone otherwise pairs the INVITE
    with the latest call.ringing event)."""
    client = get_ari()
    if client is None:
        return
    try:
        await client.set_variable(channel_id, "__EH_CALL_UUID", str(call_id))
    except AriUnavailable as exc:
        log.info("telephony.tag_failed", error=str(exc)[:120])


async def _on_call_event(session: AsyncSession, event: dict[str, Any]) -> None:
    body = event.get("userevent") or {}
    state = str(body.get("state") or "").strip()
    channel = event.get("channel") or {}
    call_channel = str(body.get("call") or channel.get("id") or "").strip()
    if not valid_channel_id(call_channel):
        return
    now = _time(event.get("timestamp"))
    if state == "ringing":
        caller = channel.get("caller") or {}
        new_call, created = await upsert_inbound(
            session,
            call_channel,
            caller.get("number"),
            _source(body.get("source")),
            _time(channel.get("creationtime")),
            recorded=_recorded(body),
        )
        if created:
            await emit_call(session, "call.ringing", new_call)
            await _tag_channel(call_channel, new_call.id)
        return
    call = await _locked(session, call_channel)
    if call is None:
        log.info("telephony.event_unknown_call", state=state)
        return
    if state == "answered" and call.status == CallStatus.RINGING:
        endpoint = str(body.get("endpoint") or "")
        operator = await session.get(OperatorEndpoint, endpoint) if valid_endpoint(endpoint) else None
        call.status, call.answered_at, call.updated_at = CallStatus.ANSWERED.value, now, now
        call.operator_endpoint = endpoint or None
        if operator is not None:
            call.operator_user_id = operator.user_subject
            if call.gouvernorat_code is None:
                call.gouvernorat_code = operator.gouvernorat_code
        await emit_call(session, "call.answered", call)
    elif state == "dialing":
        call.recording_state, call.updated_at = ("pending" if _recorded(body) else "none"), now
    elif state == "remote_answered" and call.status == CallStatus.RINGING:
        call.status, call.answered_at, call.updated_at = CallStatus.ANSWERED.value, now, now
        await emit_call(session, "call.answered", call)
    elif state == "dial_failed" and call.status == CallStatus.RINGING:
        busy = str(body.get("status") or "").upper() in ("NOANSWER", "BUSY", "CANCEL")
        call.status = CallStatus.MISSED.value if busy else CallStatus.FAILED.value
        call.end_reason = EndReason.NO_ANSWER.value if busy else EndReason.FAILED.value
        call.updated_at = now
    elif state == "transferring":
        call.status, call.transferred_to, call.updated_at = CallStatus.TRANSFERRED.value, "198", now
    elif state in ("transfer_failed", "transfer_disabled") and call.status == CallStatus.TRANSFERRED:
        # Back in the operators queue (dialplan requeue): it rings again.
        call.status, call.transferred_to, call.answered_at, call.updated_at = CallStatus.RINGING.value, None, None, now
        log.warning("telephony.transfer_failed", call_id=str(call.id), reason=state, dial=body.get("status"))
        await emit_call(session, "call.ringing", call)


async def _on_destroyed(session: AsyncSession, event: dict[str, Any]) -> None:
    channel_id = str((event.get("channel") or {}).get("id") or "")
    if not valid_channel_id(channel_id):
        return
    call = await _locked(session, channel_id)
    if call is None or call.ended_at is not None:
        return
    await end_call(session, call, _time(event.get("timestamp")))


async def end_call(session: AsyncSession, call: Call, now: datetime, reason: EndReason | None = None) -> None:
    """The citizen's leg (inbound) or the operator's leg (outbound) is gone."""
    call.ended_at = max(now, call.started_at)
    call.updated_at = now
    if reason is not None:
        call.end_reason = reason.value
    if call.status == CallStatus.ANSWERED:
        call.status, call.end_reason = CallStatus.ENDED.value, call.end_reason or EndReason.COMPLETED.value
    elif call.status == CallStatus.TRANSFERRED:
        call.end_reason = EndReason.TRANSFERRED.value
    elif call.status == CallStatus.RINGING:
        call.status = CallStatus.MISSED.value
        default = EndReason.ABANDONED if call.direction == Direction.INBOUND else EndReason.NO_ANSWER
        call.end_reason = call.end_reason or default.value
    if call.recording_state == "pending":
        call.recording_next_at = now + RECORDING_SETTLE
    await emit_call(session, "call.ended", call)


async def handle_event(session: AsyncSession, event: dict[str, Any]) -> None:
    """One ARI event (the caller commits)."""
    kind = event.get("type")
    if kind == "ChannelUserevent" and event.get("eventname") == "EhimayaCall":
        await _on_call_event(session, event)
    elif kind == "ChannelDestroyed":
        await _on_destroyed(session, event)


async def reconcile(session: AsyncSession, live_channels: set[str]) -> int:
    """After a reconnection: calls still active whose channel is gone ended while nobody listened."""
    stale = list(
        await session.scalars(
            select(Call).where(Call.status.in_(ACTIVE), Call.ended_at.is_(None)).with_for_update(skip_locked=True)
        )
    )
    ended = 0
    now = datetime.now(UTC)
    for call in stale:
        if call.channel_id not in live_channels:
            await end_call(session, call, now)
            ended += 1
    return ended


# ---------------------------------------------------------------- operator credentials


def ice_servers() -> list[schemas.IceServer]:
    urls = get_settings().telephony_ice_servers
    return [schemas.IceServer(urls=[url]) for url in urls]


async def active_endpoint(session: AsyncSession, principal: Principal) -> OperatorEndpoint | None:
    row = await session.scalar(select(OperatorEndpoint).where(OperatorEndpoint.user_subject == principal.subject))
    if row is None or row.removed_at is not None or row.expires_at <= datetime.now(UTC):
        return None
    return row


async def issue_credentials(
    session: AsyncSession, principal: Principal, endpoint: str, display_name: str | None
) -> tuple[OperatorEndpoint, str]:
    """Push a fresh password for the operator's endpoint and put it in the queue. Returns (row, password)."""
    client = require_ari()
    settings = get_settings()
    now = datetime.now(UTC)
    password = secrets.token_urlsafe(24)
    row = await session.get(OperatorEndpoint, endpoint, with_for_update=True)
    if row is None:
        row = OperatorEndpoint(endpoint=endpoint, user_subject=principal.subject, created_at=now)
        session.add(row)
    row.display_name = (display_name or "")[:100] or None
    row.gouvernorat_code = principal.gouvernorat_code
    row.expires_at = now + timedelta(seconds=settings.telephony_credential_ttl_s)
    row.updated_at = now
    row.removed_at = None
    await session.flush()
    try:
        await client.push_operator(endpoint, password, row.display_name or endpoint)
        await client.control(f"member-add-{endpoint}")
    except AriUnavailable as exc:
        log.warning("telephony.credentials_failed", error=str(exc)[:120])
        raise unavailable() from exc
    return row, password


async def retire_endpoint(client: AriClient, row: OperatorEndpoint, now: datetime) -> None:
    await client.control(f"member-del-{row.endpoint}")
    await client.remove_operator(row.endpoint)
    row.removed_at = now
    row.updated_at = now
