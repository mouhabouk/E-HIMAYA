"""Dashboard endpoints of telephony (docs/api/phase-7-contract.md §4). Geographic scope applies: a call outside the
caller's scope answers 404 like a report (calls not located yet are visible to every operator: one national queue).

Every write is audited; reading a call's detail and downloading its recording too (personal data)."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import ratelimit
from app.core.config import get_settings
from app.core.db import get_session
from app.core.security import Principal, require_roles
from app.core.storage import get_store
from app.modules.audit import service as audit
from app.modules.audit.service import actor_of, name_of
from app.modules.ops import service as ops
from app.modules.ops.models import TimelineEvent
from app.modules.reports.models import Media, Report
from app.modules.reports.staff_router import READ_ROLES
from app.modules.telephony import actions, schemas, service
from app.modules.telephony.ari import AriUnavailable
from app.modules.telephony.domain import (
    CALL_ROLES,
    CallStatus,
    Direction,
    EndReason,
    dial_extension,
    endpoint_for,
    mask_number,
)
from app.modules.telephony.models import Call, Conference

log = structlog.get_logger()
router = APIRouter(prefix="/api/v1/staff", tags=["staff", "telephony"])

StaffReader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
Caller = Annotated[Principal, Depends(require_roles(*CALL_ROLES))]
Session = Annotated[AsyncSession, Depends(get_session)]
RECORDING_LINK_S = 300
HOUR_S = 3600
CallFilter = Literal["active", "ringing", "answered", "transferred", "ended", "missed", "failed"]


@router.post("/telephony/credentials", response_model=schemas.CredentialsOut)
async def credentials(principal: Caller, session: Session, response: Response) -> schemas.CredentialsOut:
    """Short-lived SIP credentials of the caller's WebRTC endpoint (the dashboard softphone); also joins the queue."""
    settings = get_settings()
    service.require_ari()
    await ratelimit.enforce(f"tel-cred:{principal.subject}", 30, HOUR_S)
    endpoint = endpoint_for(principal.subject)
    row, password = await service.issue_credentials(session, principal, endpoint, name_of(principal))
    await audit.record(
        session,
        actor=actor_of(principal),
        action="telephony.credentials",
        target=f"sip:{endpoint}",
        details={"expires_at": row.expires_at.isoformat()},
    )
    await session.commit()
    response.headers["Cache-Control"] = "no-store"
    return schemas.CredentialsOut(
        ws_url=settings.telephony_ws_public_url,
        sip_uri=f"sip:{endpoint}@{settings.telephony_sip_domain}",
        username=endpoint,
        password=password,
        expires_at=row.expires_at,
        ice_servers=service.ice_servers(),
    )


@router.get("/calls", response_model=schemas.CallPage)
async def list_calls(
    principal: StaffReader,
    session: Session,
    status_: Annotated[CallFilter | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> schemas.CallPage:
    items, next_cursor = await service.staff_list(session, principal, status_, limit, cursor)
    return schemas.CallPage(items=items, next_cursor=next_cursor)


@router.post("/calls/dial", response_model=schemas.CallOut, status_code=status.HTTP_201_CREATED)
async def dial(principal: Caller, session: Session, body: schemas.DialIn) -> schemas.CallOut:
    """Outbound call from the caller's softphone (FR-C-10, contact from the map): Tunisian numbers only."""
    settings = get_settings()
    client = service.require_ari()
    if not actions.outbound_available():
        raise HTTPException(status.HTTP_409_CONFLICT, "outbound_unavailable")
    endpoint = await service.active_endpoint(session, principal)
    if endpoint is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "softphone_not_registered")
    report: Report | None = None
    gouvernorat = principal.gouvernorat_code
    if body.report_id is not None:
        report = await actions.report_in_scope(session, principal, body.report_id)
        raw = await actions.number_of_report(session, report)
        gouvernorat = report.gouvernorat_code
        kind = "report"
    elif body.volunteer_id is not None:
        raw, gouvernorat = await actions.number_of_volunteer(session, principal, body.volunteer_id)
        kind = "volunteer"
    else:
        raw, kind = body.number, "number"
    number = actions.tunisian(raw)
    await ratelimit.enforce(f"tel-dial:{principal.subject}", settings.telephony_dial_per_hour, HOUR_S)
    actor = actor_of(principal)
    call = await actions.create_outbound(
        session, principal, endpoint, number, report=report, gouvernorat_code=gouvernorat, actor=actor
    )
    target = body.report_id or body.volunteer_id
    await audit.record(
        session,
        actor=actor,
        action="call.dial",
        target=f"call:{call.id}",
        details={"kind": kind, "target": str(target) if target else None, "number": mask_number(number)},
    )
    await session.commit()
    try:
        await client.originate_operator_call(endpoint.endpoint, dial_extension(number), call.channel_id, "e-Himaya")
    except AriUnavailable as exc:
        log.warning("telephony.dial_failed", call_id=str(call.id), error=str(exc)[:120])
        locked = await session.get(Call, call.id, with_for_update=True)
        assert locked is not None
        locked.status = CallStatus.FAILED.value
        await service.end_call(session, locked, datetime.now(UTC), EndReason.FAILED)
        await session.commit()
        raise service.unavailable() from exc
    view, code = await service.visible_call(session, principal, call.id)
    return service.call_out(view, code)


@router.get("/calls/{call_id}", response_model=schemas.CallDetail)
async def get_call(principal: StaffReader, session: Session, call_id: uuid.UUID) -> schemas.CallDetail:
    call, code = await service.visible_call(session, principal, call_id)
    out = await service.detail(session, principal, call, code)
    await audit.record(session, actor=actor_of(principal), action="call.detail", target=f"call:{call_id}")
    await session.commit()
    return out


@router.post("/calls/{call_id}/link", response_model=schemas.CallOut)
async def link_call(principal: Caller, session: Session, call_id: uuid.UUID, body: schemas.LinkIn) -> schemas.CallOut:
    call, _ = await service.visible_call(session, principal, call_id, lock=True)
    actor = actor_of(principal)
    details = await actions.link(
        session,
        principal,
        call,
        report_id=body.report_id,
        tracking_code=body.tracking_code,
        incident_id=body.incident_id,
        actor=actor,
    )
    await audit.record(session, actor=actor, action="call.link", target=f"call:{call_id}", details=details)
    await session.flush()
    view, code = await service.visible_call(session, principal, call_id)
    out = service.call_out(view, code)
    await session.commit()
    return out


@router.post("/calls/{call_id}/transfer-198", response_model=schemas.CallOut)
async def transfer_198(principal: Caller, session: Session, call_id: uuid.UUID) -> schemas.CallOut:
    """Scenario 2 (ADR-10): blind transfer of the caller to 198 through the trunk. Disabled by default: the operator
    then calls 198 from their own phone (scenario 1)."""
    if not service.transfer_available():
        raise HTTPException(status.HTTP_409_CONFLICT, "transfer_disabled")
    client = service.require_ari()
    call, code = await service.visible_call(session, principal, call_id, lock=True)
    if call.direction != Direction.INBOUND or call.status != CallStatus.ANSWERED:
        raise HTTPException(status.HTTP_409_CONFLICT, "call_not_answered")
    now = datetime.now(UTC)
    call.status, call.transferred_to, call.updated_at = CallStatus.TRANSFERRED.value, "198", now
    await audit.record(
        session, actor=actor_of(principal), action="call.transfer_198", target=f"call:{call_id}", details={"to": "198"}
    )
    await session.flush()
    try:
        await client.control(f"transfer-{call.channel_id}")
    except AriUnavailable as exc:
        await session.rollback()
        raise service.unavailable() from exc
    out = service.call_out(call, code)
    await session.commit()
    return out


@router.get("/calls/{call_id}/recording", status_code=status.HTTP_302_FOUND)
async def recording(principal: Caller, session: Session, call_id: uuid.UUID) -> RedirectResponse:
    call, _ = await service.visible_call(session, principal, call_id)
    media = await session.get(Media, call.recording_media_id) if call.recording_media_id else None
    if media is None or media.status != "stored" or media.kind != "call_recording":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    url = get_store().presign_get(
        media.object_key,
        expires_s=RECORDING_LINK_S,
        content_type="audio/wav",
        disposition=f'attachment; filename="call-{call_id}.wav"',
    )
    await audit.record(
        session,
        actor=actor_of(principal),
        action="call.recording.download",
        target=f"media:{media.id}",
        details={"call_id": str(call_id), "sha256": media.sha256},
    )
    await session.commit()
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND, headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------- crisis rooms


def _conference_out(conference: Conference) -> schemas.ConferenceOut:
    return schemas.ConferenceOut(
        id=conference.id,
        room=conference.room,
        join_uri=actions.join_uri(conference.room),
        incident_id=conference.incident_id,
        created_at=conference.created_at,
        ended_at=conference.ended_at,
        active=conference.ended_at is None,
    )


@router.post("/incidents/{incident_id}/conference", response_model=schemas.ConferenceOut)
async def open_conference(
    principal: Caller, session: Session, incident_id: uuid.UUID, response: Response
) -> schemas.ConferenceOut:
    """The incident's crisis room (created when none is open): operators join by dialling conf-<room>."""
    service.require_ari()
    incident = await ops.get_in_scope(session, principal, incident_id)
    actor = actor_of(principal)
    conference, created = await actions.open_conference(session, incident, actor)
    if created:
        await audit.record(
            session,
            actor=actor,
            action="conference.open",
            target=f"incident:{incident_id}",
            details={"conference_id": str(conference.id), "room": conference.room},
        )
        response.status_code = status.HTTP_201_CREATED
    await session.flush()
    await session.refresh(conference)
    out = _conference_out(conference)
    await session.commit()
    return out


@router.get("/incidents/{incident_id}/conferences", response_model=schemas.ConferenceList)
async def list_conferences(principal: StaffReader, session: Session, incident_id: uuid.UUID) -> schemas.ConferenceList:
    await ops.get_in_scope(session, principal, incident_id)
    rows = await session.scalars(
        select(Conference).where(Conference.incident_id == incident_id).order_by(Conference.created_at.desc())
    )
    return schemas.ConferenceList(items=[_conference_out(c) for c in rows])


async def _conference_in_scope(
    session: AsyncSession, principal: Principal, conference_id: uuid.UUID, *, lock: bool = False
) -> Conference:
    conference = await session.get(Conference, conference_id, with_for_update=lock)
    if conference is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await ops.get_in_scope(session, principal, conference.incident_id)
    return conference


@router.post("/conferences/{conference_id}/end", response_model=schemas.ConferenceOut)
async def end_conference(principal: Caller, session: Session, conference_id: uuid.UUID) -> schemas.ConferenceOut:
    client = service.require_ari()
    conference = await _conference_in_scope(session, principal, conference_id, lock=True)
    if conference.ended_at is None:
        actor = actor_of(principal)
        now = datetime.now(UTC)
        conference.ended_at, conference.ended_by = now, actor
        session.add(
            TimelineEvent(
                incident_id=conference.incident_id,
                kind="conference_ended",
                actor=actor,
                payload={"room": conference.room},
            )
        )
        await audit.record(
            session, actor=actor, action="conference.end", target=f"conference:{conference_id}", details={}
        )
        await session.flush()
        try:
            await client.control(f"confkick-{conference.room}")
        except AriUnavailable as exc:
            await session.rollback()
            raise service.unavailable() from exc
    out = _conference_out(conference)
    await session.commit()
    return out


@router.post(
    "/conferences/{conference_id}/invite", response_model=schemas.InviteOut, status_code=status.HTTP_202_ACCEPTED
)
async def invite(
    principal: Caller, session: Session, conference_id: uuid.UUID, body: schemas.InviteIn
) -> schemas.InviteOut:
    """Call an official or a volunteer into the crisis room (through the trunk)."""
    settings = get_settings()
    client = service.require_ari()
    if not actions.outbound_available():
        raise HTTPException(status.HTTP_409_CONFLICT, "outbound_unavailable")
    conference = await _conference_in_scope(session, principal, conference_id)
    if conference.ended_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "conference_ended")
    if body.volunteer_id is not None:
        raw, _ = await actions.number_of_volunteer(session, principal, body.volunteer_id)
    else:
        raw = body.number
    number = actions.tunisian(raw)
    await ratelimit.enforce(f"tel-dial:{principal.subject}", settings.telephony_dial_per_hour, HOUR_S)
    await audit.record(
        session,
        actor=actor_of(principal),
        action="conference.invite",
        target=f"conference:{conference_id}",
        details={"number": mask_number(number), "volunteer_id": str(body.volunteer_id) if body.volunteer_id else None},
    )
    await session.flush()
    try:
        await client.invite(dial_extension(number), conference.room)
    except AriUnavailable as exc:
        await session.rollback()
        raise service.unavailable() from exc
    await session.commit()
    return schemas.InviteOut(status="calling", number_masked=mask_number(number) or "")
