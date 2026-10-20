"""Staff actions on calls: linking, outbound calls, scenario 2 transfer and crisis rooms (contract §4).

Each action is audited by the router; the ARI request is sent before the commit so a refused request leaves no row
behind (except outbound calls, whose row is committed first so the ARI events always find it).
"""

import secrets
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import Principal
from app.modules.identity.models import Profile
from app.modules.ops import service as ops
from app.modules.ops.models import Incident, TimelineEvent
from app.modules.reports.models import Report
from app.modules.reports.service import in_scope
from app.modules.telephony import service
from app.modules.telephony.domain import (
    CallStatus,
    Direction,
    Source,
    caller_index,
    normalize_tn_number,
)
from app.modules.telephony.models import Call, Conference, OperatorEndpoint, SmsInbound
from app.modules.volunteers.models import Volunteer


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "not_found")


async def report_in_scope(session: AsyncSession, principal: Principal, report_id: uuid.UUID) -> Report:
    report = await session.get(Report, report_id)
    if report is None or not in_scope(principal, report.gouvernorat_code):
        raise _not_found()
    return report


# ---------------------------------------------------------------- link


async def link(
    session: AsyncSession,
    principal: Principal,
    call: Call,
    *,
    report_id: uuid.UUID | None,
    tracking_code: str | None,
    incident_id: uuid.UUID | None,
    actor: str,
) -> dict[str, str]:
    """Attach the call to a report (by id or tracking code) or to an incident; returns the audit details."""
    if tracking_code is not None:
        found = await session.scalar(select(Report.id).where(Report.tracking_code == tracking_code))
        if found is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "report_not_found")
        report_id = found
    if report_id is not None:
        try:
            report = await report_in_scope(session, principal, report_id)
        except HTTPException as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "report_not_found") from exc
        call.report_id = report.id
        if report.incident_id is not None:
            call.incident_id = report.incident_id
        if call.gouvernorat_code is None:
            call.gouvernorat_code = report.gouvernorat_code
    if incident_id is not None:
        try:
            incident = await ops.get_in_scope(session, principal, incident_id)
        except HTTPException as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "incident_not_found") from exc
        call.incident_id = incident.id
        if call.gouvernorat_code is None:
            call.gouvernorat_code = incident.gouvernorat_code
    call.updated_at = datetime.now(UTC)
    if call.incident_id is not None:
        session.add(
            TimelineEvent(
                incident_id=call.incident_id,
                kind="call_linked",
                actor=actor,
                payload={"call_id": str(call.id), "report_id": str(call.report_id) if call.report_id else None},
            )
        )
    details = {"report_id": str(call.report_id) if call.report_id else "", "incident_id": str(call.incident_id or "")}
    return details


# ---------------------------------------------------------------- numbers


async def _profile_phone(session: AsyncSession, user_id: uuid.UUID) -> str | None:
    profile = await session.get(Profile, user_id)
    return profile.phone if profile is not None else None


async def number_of_report(session: AsyncSession, report: Report) -> str | None:
    """How to call a reporter back: the SMS sender, the registered citizen's phone, or the number of a linked call."""
    sms = await session.scalar(
        select(SmsInbound)
        .where(SmsInbound.report_id == report.id, SmsInbound.sender_number.is_not(None))
        .order_by(SmsInbound.received_at.desc())
        .limit(1)
    )
    if sms is not None and sms.sender_number:
        return sms.sender_number
    phone = await _profile_phone(session, report.user_id)
    if phone:
        return phone
    call = await session.scalar(
        select(Call)
        .where(Call.report_id == report.id, Call.caller_hash.is_not(None))
        .order_by(Call.started_at.desc())
        .limit(1)
    )
    return call.caller_number if call is not None else None


async def number_of_volunteer(
    session: AsyncSession, principal: Principal, volunteer_id: uuid.UUID
) -> tuple[str | None, int]:
    volunteer = await session.get(Volunteer, volunteer_id)
    if volunteer is None or not in_scope(principal, volunteer.gouvernorat_code):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "volunteer_not_found")
    return await _profile_phone(session, volunteer_id), volunteer.gouvernorat_code


def tunisian(number: str | None) -> str:
    if not number:
        raise HTTPException(status.HTTP_409_CONFLICT, "no_number")
    normalized = normalize_tn_number(number)
    if normalized is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_number")
    return normalized


def outbound_available() -> bool:
    """A trunk, or (development only) the call-sim service answering in its place."""
    settings = get_settings()
    return settings.telephony_trunk_enabled or settings.app_env != "production"


# ---------------------------------------------------------------- outbound call


async def create_outbound(
    session: AsyncSession,
    principal: Principal,
    endpoint: OperatorEndpoint,
    number: str,
    *,
    report: Report | None,
    gouvernorat_code: int | None,
    actor: str,
) -> Call:
    now = datetime.now(UTC)
    call_id = uuid.uuid4()
    call = Call(
        id=call_id,
        channel_id=str(call_id),
        direction=Direction.OUTBOUND.value,
        source=Source.OPERATOR.value if get_settings().telephony_trunk_enabled else Source.SIM.value,
        caller_number=number,
        caller_hash=caller_index(number),
        started_at=now,
        operator_user_id=principal.subject,
        operator_endpoint=endpoint.endpoint,
        status=CallStatus.RINGING.value,
        report_id=report.id if report is not None else None,
        incident_id=report.incident_id if report is not None else None,
        gouvernorat_code=gouvernorat_code,
        created_by=actor,
        created_at=now,
        updated_at=now,
    )
    session.add(call)
    await service.emit_call(session, "call.ringing", call)
    return call


# ---------------------------------------------------------------- conferences


def join_uri(room: str) -> str:
    return f"sip:conf-{room}@{get_settings().telephony_sip_domain}"


async def open_conference(session: AsyncSession, incident: Incident, actor: str) -> tuple[Conference, bool]:
    """The incident's open crisis room, created when there is none. Returns (room, created)."""
    existing = await session.scalar(
        select(Conference).where(Conference.incident_id == incident.id, Conference.ended_at.is_(None))
    )
    if existing is not None:
        return existing, False
    for _ in range(5):
        room = f"{secrets.randbelow(10**8):08d}"
        conference = Conference(
            room=room, incident_id=incident.id, gouvernorat_code=incident.gouvernorat_code, created_by=actor
        )
        try:
            async with session.begin_nested():
                session.add(conference)
                await session.flush()
        except IntegrityError:
            again = await session.scalar(
                select(Conference).where(Conference.incident_id == incident.id, Conference.ended_at.is_(None))
            )
            if again is not None:
                return again, False
            continue
        session.add(
            TimelineEvent(incident_id=incident.id, kind="conference_opened", actor=actor, payload={"room": room})
        )
        return conference, True
    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "telephony_unavailable")
