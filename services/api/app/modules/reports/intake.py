"""Reports an operations room enters by hand (phase N, docs/phase-n/design-n.md §5).

A citizen calls the room, a patrol radios in, someone walks in: the agent writes the report down. It becomes a report
like the others, so it gets a tracking code, the AI baseline, the claim deadline, grouping into interventions and the
usual follow-up. It is marked ``source = 'room'`` with the channel it came by and who entered it. The regional room
that entered it holds it from the start; one the central room enters goes to its gouvernorat's room. A regional room
enters reports of its own gouvernorat only; the central room enters reports anywhere.
"""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from geoalchemy2 import Geography
from sqlalchemy import cast, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, authorize
from app.core.crypto import pseudonym
from app.core.events import emit
from app.core.security import Principal
from app.modules.ai import pipeline
from app.modules.ai.models import Analysis
from app.modules.audit import service as audit
from app.modules.geo.service import admin_address
from app.modules.identity.models import AccountKind
from app.modules.identity.service import _upsert_account
from app.modules.reports import jurisdiction, schemas, sla
from app.modules.reports.domain import Status
from app.modules.reports.models import Report, StatusHistory
from app.modules.reports.service import (
    ReportRow,
    gouvernorat_codes,
    locate_gouvernorat,
    next_tracking_code,
    report_ctx,
    staff_report,
)

# The identity every room-entered report belongs to: the caller is not a user of the app (no consent, no account).
ROOM_REPORTER = b"room-intake"


async def create(session: AsyncSession, principal: Principal, body: schemas.RoomReportIn) -> uuid.UUID:
    now = datetime.now(UTC)
    lat, lon = body.location.lat, body.location.lon
    gouvernorat = await locate_gouvernorat(session, lat, lon)
    if gouvernorat is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "outside_tunisia")
    if not principal.is_national and principal.gouvernorat_code != gouvernorat:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "outside_gouvernorat")
    account = await _upsert_account(session, AccountKind.ANONYMOUS, sub=None, anon=pseudonym(ROOM_REPORTER))
    address = await admin_address(session, lat, lon)
    text = body.text.strip() if body.text and body.text.strip() else None
    created_at = min(body.received_at, now) if body.received_at is not None else now
    report = Report(
        tracking_code=await next_tracking_code(session, now, gouvernorat),
        client_uuid=None,
        user_id=account.user_id,
        category=body.category.value,
        text_original=text,
        lang_original=body.lang if text else None,
        location=cast(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), Geography),
        location_accuracy_m=body.location.accuracy_m,
        gouvernorat_code=gouvernorat,
        delegation_id=address.delegation_id,
        sector_code=address.sector_code,
        municipality_id=address.municipality_id,
        status=Status.RECEIVED.value,
        source="room",
        intake_channel=body.channel,
        entered_by=audit.actor_of(principal),
        entered_by_name=audit.name_of(principal),
        created_at=created_at,
        received_at=now,
        updated_at=now,
    )
    session.add(report)
    await session.flush()
    session.add(
        StatusHistory(report_id=report.id, status=Status.RECEIVED.value, at=now, actor=audit.actor_of(principal))
    )
    await pipeline.baseline(session, report)
    await sla.assign(session, report)
    await session.flush()
    # The regional room that wrote it down answers it; one the central room enters goes to its gouvernorat's room,
    # as any report does (the central room claims only late reports, phase 9 §4.4). One a team opens from the field
    # (phase F) is left to its room.
    ctx = await report_ctx(session, report)
    if (await authorize(session, principal, Action.REPORT_CLAIM, ctx)).allowed:
        locked, ctx = await jurisdiction.load(session, principal, report.id)
        await jurisdiction.claim(session, principal, locked, ctx)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="report.room_entered",
        target=str(report.id),
        details={"channel": body.channel, "category": body.category.value},
        gouvernorats=[gouvernorat],
    )
    analysis = await session.get(Analysis, report.id)
    await emit(
        session,
        "report.created",
        {
            "report": staff_report(ReportRow(report, lat, lon), "anonymous", 0, analysis).model_dump(mode="json"),
            "gouvernorat_codes": await gouvernorat_codes(session, report),
        },
    )
    return report.id
