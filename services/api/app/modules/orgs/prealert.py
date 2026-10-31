"""Pre-alert of an institution (review point 25, docs/phase-d/design-d.md §2).

A camera of an institution (a live stream with ``org_id``) confirms a fire or smoke. Before the room is disturbed,
the institution's administrators and editors get a critical push and have ``orgs.prealert_seconds`` (90 s by
default, a setting) to answer:

* «false alarm» with a reason: the pre-alert is closed, nothing reaches the room, the reason is audited;
* «confirm»: the report is created at once;
* no answer: the worker raises it to the room when the delay runs out.

The report is a normal ``iot`` report on behalf of the institution, at its address, so the grouping, the priority
score, the follow-up and the institution's own report list all apply unchanged. The camera stream is linked to it,
so the room watches the live picture and later detections land on the incident's timeline.
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from fastapi import HTTPException, status
from geoalchemy2 import Geography, Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.events import emit
from app.modules.ai import pipeline
from app.modules.ai.models import Analysis
from app.modules.geo.service import admin_address
from app.modules.identity.models import Account
from app.modules.notify import outbox
from app.modules.orgs.domain import OrgRole
from app.modules.orgs.models import Member, Organization, Prealert
from app.modules.reports.domain import Category, Status
from app.modules.reports.models import Report, StatusHistory
from app.modules.reports.service import ReportRow, next_tracking_code, staff_report
from app.modules.settings import service as settings_service
from app.modules.streams.models import LiveStream

log = structlog.get_logger()

PENDING, CANCELLED, CONFIRMED, ESCALATED = "pending", "cancelled", "confirmed", "escalated"
ACTOR = "system:prealert"
# The owner's phone shows a fixed text; the camera, the label and the countdown come from the authenticated API.
PUSH_TITLE = outbox.localized("ء-حماية: تنبيه مسبق", "e-Himaya : pré-alerte", "e-Himaya: pre-alert")
PUSH_BODY = outbox.localized(
    "رصدت كاميرا مؤسستك خطرا محتملا. افتح التطبيق للتأكيد أو الإلغاء.",
    "Une caméra de votre établissement a détecté un danger possible. Ouvrez l'application.",
    "A camera of your institution saw a possible danger. Open the app to confirm or cancel.",
)
INTERVAL_S = 5


@dataclass(frozen=True, slots=True)
class Raised:
    prealert: Prealert
    new: bool


async def raise_for_stream(
    session: AsyncSession, stream: LiveStream, label: str, confidence: float, media_id: uuid.UUID | None
) -> Raised | None:
    """Open a pre-alert for a confirmed detection of an institution's camera (one pending per camera at a time)."""
    if stream.org_id is None or stream.report_id is not None:
        return None
    pending = await session.scalar(
        select(Prealert)
        .where(Prealert.stream_id == stream.id, Prealert.state == PENDING)
        .with_for_update(skip_locked=True)
    )
    if pending is not None:
        pending.confidence = max(pending.confidence, confidence)
        return Raised(pending, False)
    return Raised(
        await open_prealert(
            session,
            stream.org_id,
            source="camera",
            label=label,
            confidence=confidence,
            stream_id=stream.id,
            media_id=media_id,
            simulated=stream.source == "sim",
        ),
        True,
    )


async def open_prealert(
    session: AsyncSession,
    org_id: uuid.UUID,
    *,
    source: str,
    label: str,
    confidence: float,
    stream_id: uuid.UUID | None = None,
    media_id: uuid.UUID | None = None,
    simulated: bool = False,
) -> Prealert:
    now = datetime.now(UTC)
    delay = await settings_service.threshold(session, "orgs.prealert_seconds")
    row = Prealert(
        org_id=org_id,
        stream_id=stream_id,
        source=source,
        label=label,
        confidence=confidence,
        media_id=media_id,
        simulated=simulated,
        state=PENDING,
        raised_at=now,
        deadline_at=now + timedelta(seconds=delay),
    )
    session.add(row)
    await session.flush()
    members = await session.scalars(
        select(Member.user_id).where(
            Member.org_id == org_id, Member.role.in_((OrgRole.ADMIN.value, OrgRole.EDITOR.value))
        )
    )
    for user_id in members:
        outbox.push(
            session,
            user_id,
            "prealert",
            {"prealert_id": str(row.id), "org_id": str(org_id)},
            critical=True,
            title=PUSH_TITLE,
            body=PUSH_BODY,
        )
    log.info("prealert.raised", prealert_id=str(row.id), org_id=str(org_id), label=label, delay_s=delay)
    return row


async def decide(session: AsyncSession, row: Prealert, user_id: uuid.UUID, action: str, reason: str | None) -> Prealert:
    """The owner's answer: ``cancel`` (false alarm, with a reason) or ``confirm`` (report now)."""
    if row.state != PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, f"prealert_{row.state}")
    now = datetime.now(UTC)
    row.decided_by, row.decided_at = user_id, now
    if action == "cancel":
        row.state, row.reason = CANCELLED, reason
    else:
        row.state = CONFIRMED
        await _report(session, row, now)
    await session.flush()
    return row


async def escalate_due(session: AsyncSession, now: datetime | None = None) -> int:
    """Raise to the room every pending pre-alert whose delay ran out."""
    now = now or datetime.now(UTC)
    due = list(
        await session.scalars(
            select(Prealert)
            .where(Prealert.state == PENDING, Prealert.deadline_at <= now)
            .order_by(Prealert.deadline_at)
            .limit(50)
            .with_for_update(skip_locked=True)
        )
    )
    for row in due:
        row.state = ESCALATED
        await _report(session, row, now)
    await session.flush()
    return len(due)


async def _report(session: AsyncSession, row: Prealert, now: datetime) -> Report:
    org = await session.get(Organization, row.org_id)
    if org is None:  # pragma: no cover - the pre-alert goes with its institution (cascade)
        raise HTTPException(status.HTTP_404_NOT_FOUND, "org_not_found")
    lat, lon = (
        await session.execute(
            select(
                func.ST_Y(cast(Organization.location, Geometry)), func.ST_X(cast(Organization.location, Geometry))
            ).where(Organization.id == org.id)
        )
    ).one()
    address = await admin_address(session, lat, lon)
    gouvernorat = org.gouvernorat_code
    report = Report(
        tracking_code=await next_tracking_code(session, now, gouvernorat),
        client_uuid=None,
        user_id=org.created_by,
        organization_id=org.id,
        category=Category.FIRE.value,
        text_original=prealert_text(row),
        lang_original="ar",
        location=cast(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), Geography),
        location_accuracy_m=None,
        gouvernorat_code=gouvernorat,
        delegation_id=address.delegation_id,
        sector_code=address.sector_code,
        municipality_id=address.municipality_id,
        status=Status.RECEIVED.value,
        source="iot",
        created_at=row.raised_at,
        received_at=now,
        updated_at=now,
    )
    session.add(report)
    await session.flush()
    session.add(StatusHistory(report_id=report.id, status=Status.RECEIVED.value, at=now, actor=ACTOR))
    row.report_id = report.id
    if row.stream_id is not None:
        stream = await session.get(LiveStream, row.stream_id)
        if stream is not None and stream.report_id is None:
            stream.report_id = report.id
    if row.media_id is not None:
        from app.modules.reports.models import Media

        media = await session.get(Media, row.media_id)
        if media is not None and media.report_id is None:
            media.report_id = report.id
    await pipeline.baseline(session, report)
    account = await session.get(Account, org.created_by)
    analysis = await session.get(Analysis, report.id)
    await emit(
        session,
        "report.created",
        {
            "report": staff_report(
                ReportRow(report, lat, lon), account.kind.value if account else "registered", 0, analysis
            ).model_dump(mode="json")
        },
    )
    log.info("prealert.reported", prealert_id=str(row.id), report_id=str(report.id), state=row.state)
    return report


LABELS_AR = {"fire": "نار", "smoke": "دخان"}


def prealert_text(row: Prealert) -> str:
    """The report's text: what was seen, how sure, and how the owner answered (no name, no personal data)."""
    seen = LABELS_AR.get(row.label, row.label)
    how = "أكّده صاحب المؤسسة" if row.state == CONFIRMED else "لم يُجب صاحب المؤسسة في الأجل"
    sim = "[SIM] " if row.simulated else ""
    return f"{sim}تنبيه مسبق من كاميرا المؤسسة: {seen} (ثقة {round(row.confidence * 100)}٪). {how}."


def seconds_left(row: Prealert, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    return max(0, int((row.deadline_at - now).total_seconds())) if row.state == PENDING else 0


async def prealerts_forever(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    while True:
        try:
            async with sessionmaker() as session, session.begin():
                raised = await escalate_due(session)
            if raised:
                log.info("prealert.escalated", count=raised)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("prealert.loop_failed")
        await asyncio.sleep(INTERVAL_S)


def out(row: Prealert, org_name: str | None = None) -> dict[str, Any]:
    return {
        "id": row.id,
        "org_id": row.org_id,
        "org_name": org_name,
        "stream_id": row.stream_id,
        "source": row.source,
        "label": row.label,
        "confidence": round(row.confidence, 3),
        "simulated": row.simulated,
        "state": row.state,
        "raised_at": row.raised_at,
        "deadline_at": row.deadline_at,
        "seconds_left": seconds_left(row),
        "reason": row.reason,
        "report_id": row.report_id,
        "has_frame": row.media_id is not None,
    }
