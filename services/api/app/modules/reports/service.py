"""Reporting flow: creation (idempotent), tracking codes, location, status changes, staff queries."""

import base64
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from geoalchemy2 import Geography, Geometry
from sqlalchemy import Select, and_, cast, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.events import emit
from app.core.security import Principal
from app.modules.ai import pipeline
from app.modules.ai.models import Analysis
from app.modules.geo.models import Gouvernorat
from app.modules.identity.models import Account
from app.modules.identity.service import Reporter, has_consented
from app.modules.reports import schemas
from app.modules.reports.domain import NEAREST_GOUVERNORAT_MAX_M, Category, Status, can_transition
from app.modules.reports.models import Media, Report, StatusHistory

TUNIS_TZ = ZoneInfo("Africa/Tunis")
HIGH_PRIORITY = 70
# Device clocks drift; a creation time in the future is replaced by the reception time.
_MAX_CLOCK_SKEW = timedelta(minutes=5)

_LAT = func.ST_Y(cast(Report.location, Geometry)).label("lat")
_LON = func.ST_X(cast(Report.location, Geometry)).label("lon")


@dataclass(frozen=True, slots=True)
class ReportRow:
    report: Report
    lat: float
    lon: float


def _with_coords() -> Select[tuple[Report, float, float]]:
    return select(Report, _LAT, _LON)


def _row(found: Any) -> ReportRow:
    return ReportRow(found[0], float(found[1]), float(found[2]))


# ---------------------------------------------------------------- location & tracking code


async def locate_gouvernorat(session: AsyncSession, lat: float, lon: float) -> int | None:
    """Gouvernorat containing the point, else the nearest one within a coastal margin, else None."""
    point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    code = await session.scalar(
        select(Gouvernorat.code).where(func.ST_Intersects(Gouvernorat.boundary, point)).limit(1)
    )
    if code is not None:
        return code
    boundary, target = cast(Gouvernorat.boundary, Geography), cast(point, Geography)
    return await session.scalar(
        select(Gouvernorat.code)
        .where(func.ST_DWithin(boundary, target, NEAREST_GOUVERNORAT_MAX_M))
        .order_by(func.ST_Distance(boundary, target))
        .limit(1)
    )


async def next_tracking_code(session: AsyncSession, received_at: datetime, gouvernorat_code: int | None) -> str:
    """``EH-<yy>-<gouvernorat>-<7 digits>``, numbered per year (FR-A-046)."""
    year = received_at.astimezone(TUNIS_TZ).year
    number = await session.scalar(
        text(
            "INSERT INTO reports.tracking_counter (year, last) VALUES (:year, 1) "
            "ON CONFLICT (year) DO UPDATE SET last = reports.tracking_counter.last + 1 RETURNING last"
        ),
        {"year": year},
    )
    return f"EH-{year % 100:02d}-{gouvernorat_code or 0:02d}-{int(number or 0):07d}"


# ---------------------------------------------------------------- views


async def media_for(session: AsyncSession, report_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[Media]]:
    grouped: dict[uuid.UUID, list[Media]] = {rid: [] for rid in report_ids}
    if not report_ids:
        return grouped
    rows = await session.scalars(
        select(Media).where(Media.report_id.in_(report_ids), Media.status != "rejected").order_by(Media.created_at)
    )
    for media in rows:
        if media.report_id is not None:
            grouped[media.report_id].append(media)
    return grouped


def media_out(media: Media) -> schemas.MediaOut:
    return schemas.MediaOut(
        id=media.id,
        kind=media.kind,
        bytes=media.bytes,
        sha256=media.sha256,
        content_type=media.content_type,
        status=media.status,
        created_at=media.created_at,
    )


def _location(row: ReportRow) -> schemas.LocationOut:
    return schemas.LocationOut(lat=row.lat, lon=row.lon, accuracy_m=row.report.location_accuracy_m)


def report_out(row: ReportRow, media: list[Media]) -> schemas.ReportOut:
    r = row.report
    return schemas.ReportOut(
        id=r.id,
        tracking_code=r.tracking_code,
        client_uuid=r.client_uuid,
        category=Category(r.category),
        status=Status(r.status),
        text=r.text_original,
        lang=r.lang_original,
        location=_location(row),
        gouvernorat_code=r.gouvernorat_code,
        created_at=r.created_at,
        received_at=r.received_at,
        updated_at=r.updated_at,
        media=[media_out(m) for m in media],
    )


async def get_report_row(session: AsyncSession, report_id: uuid.UUID) -> ReportRow | None:
    found = (await session.execute(_with_coords().where(Report.id == report_id))).first()
    return _row(found) if found else None


# ---------------------------------------------------------------- creation


async def create_report(session: AsyncSession, reporter: Reporter, body: schemas.ReportIn) -> tuple[ReportRow, bool]:
    """Create a report, or return the existing one for a replayed ``client_uuid`` (offline retries)."""
    existing = await _by_client_uuid(session, body.client_uuid)
    if existing is not None:
        if existing.report.user_id != reporter.user_id:
            raise HTTPException(status.HTTP_409_CONFLICT, "client_uuid_conflict")
        return existing, False

    if not await has_consented(session, reporter.user_id, get_settings().charter_version):
        raise HTTPException(status.HTTP_428_PRECONDITION_REQUIRED, "consent_required")

    received_at = datetime.now(UTC)
    created_at = min(body.created_at, received_at + _MAX_CLOCK_SKEW)
    if created_at > received_at:
        created_at = received_at
    gouvernorat = await locate_gouvernorat(session, body.location.lat, body.location.lon)
    tracking_code = await next_tracking_code(session, received_at, gouvernorat)
    text_value = body.text.strip() if body.text and body.text.strip() else None

    report = Report(
        tracking_code=tracking_code,
        client_uuid=body.client_uuid,
        user_id=reporter.user_id,
        category=body.category.value,
        text_original=text_value,
        lang_original=body.lang if text_value else None,
        location=cast(func.ST_SetSRID(func.ST_MakePoint(body.location.lon, body.location.lat), 4326), Geography),
        location_accuracy_m=body.location.accuracy_m,
        gouvernorat_code=gouvernorat,
        status=Status.RECEIVED.value,
        source="app",
        created_at=created_at,
        received_at=received_at,
        updated_at=received_at,
    )
    session.add(report)
    try:
        await session.flush()
    except IntegrityError:
        # Same client_uuid inserted concurrently (two retries racing): answer with the stored report.
        await session.rollback()
        existing = await _by_client_uuid(session, body.client_uuid)
        if existing is None or existing.report.user_id != reporter.user_id:
            raise HTTPException(status.HTTP_409_CONFLICT, "client_uuid_conflict") from None
        return existing, False

    session.add(StatusHistory(report_id=report.id, status=Status.RECEIVED.value, at=received_at, actor="reporter"))
    # Rules-only priority at once; the models refine it in the background (ai.pipeline).
    await pipeline.baseline(session, report)
    row = ReportRow(report, body.location.lat, body.location.lon)
    analysis = await session.get(Analysis, report.id)
    await emit(
        session,
        "report.created",
        {"report": staff_report(row, reporter.kind.value, 0, analysis).model_dump(mode="json")},
    )
    await session.commit()
    return row, True


async def _by_client_uuid(session: AsyncSession, client_uuid: uuid.UUID) -> ReportRow | None:
    found = (await session.execute(_with_coords().where(Report.client_uuid == client_uuid))).first()
    return _row(found) if found else None


async def my_reports(
    session: AsyncSession, reporter: Reporter, limit: int, before: datetime | None
) -> tuple[list[schemas.ReportOut], datetime | None]:
    query = _with_coords().where(Report.user_id == reporter.user_id)
    if before is not None:
        query = query.where(Report.received_at < before)
    rows = [_row(r) for r in (await session.execute(query.order_by(Report.received_at.desc()).limit(limit)))]
    media = await media_for(session, [r.report.id for r in rows])
    items = [report_out(r, media[r.report.id]) for r in rows]
    next_before = rows[-1].report.received_at if len(rows) == limit else None
    return items, next_before


async def track(session: AsyncSession, tracking_code: str) -> schemas.TrackOut | None:
    report = await session.scalar(select(Report).where(Report.tracking_code == tracking_code))
    if report is None:
        return None
    history = await session.scalars(
        select(StatusHistory).where(StatusHistory.report_id == report.id).order_by(StatusHistory.at, StatusHistory.id)
    )
    return schemas.TrackOut(
        tracking_code=report.tracking_code,
        status=Status(report.status),
        received_at=report.received_at,
        updated_at=report.updated_at,
        history=[schemas.HistoryEntry(status=Status(h.status), at=h.at) for h in history],
    )


# ---------------------------------------------------------------- staff


def staff_report(
    row: ReportRow, reporter_kind: str, media_count: int, analysis: Analysis | None
) -> schemas.StaffReport:
    r = row.report
    extraction = analysis.extraction if analysis is not None else None
    return schemas.StaffReport(
        id=r.id,
        tracking_code=r.tracking_code,
        category=Category(r.category),
        status=Status(r.status),
        text=r.text_original,
        lang=r.lang_original,
        text_ar=r.text_ar,
        location=_location(row),
        gouvernorat_code=r.gouvernorat_code,
        delegation_id=r.delegation_id,
        reporter_kind=reporter_kind,
        media_count=media_count,
        created_at=r.created_at,
        received_at=r.received_at,
        updated_at=r.updated_at,
        priority_score=r.priority_score,
        credibility_score=r.credibility_score,
        analysis_state=analysis.state if analysis is not None else None,
        lives_at_risk=_lives_at_risk(analysis),
        suggested_category=Category(extraction["category"]) if extraction and extraction.get("category") else None,
        incident_id=r.incident_id,
        has_suggestion=bool(analysis is not None and analysis.suggestion),
    )


def _lives_at_risk(analysis: Analysis | None) -> bool | None:
    """From the priority explanation (model or keywords), so the list and the detail always agree."""
    if analysis is None or not analysis.priority:
        return None
    lives = next((c for c in analysis.priority.get("components", []) if c.get("key") == "lives"), None)
    return None if lives is None or lives.get("value") is None else lives["value"] >= 1.0


def scope_filter(principal: Principal) -> Any:
    """Geographic scope enforced on every staff query (not only in the UI)."""
    if principal.is_national:
        return True
    return Report.gouvernorat_code == principal.gouvernorat_code


def in_scope(principal: Principal, gouvernorat_code: int | None) -> bool:
    return principal.is_national or (
        gouvernorat_code is not None and principal.can_access_gouvernorat(gouvernorat_code)
    )


_MEDIA_COUNT = (
    select(func.count(Media.id))
    .where(Media.report_id == Report.id, Media.status != "rejected")
    .correlate(Report)
    .scalar_subquery()
    .label("media_count")
)


def encode_cursor(received_at: datetime, report_id: uuid.UUID, priority: int | None = None) -> str:
    raw = f"{received_at.isoformat()}|{report_id}" + ("" if priority is None else f"|{priority}")
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID, int | None]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        at, rid, *rest = raw.split("|")
        return datetime.fromisoformat(at), uuid.UUID(rid), int(rest[0]) if rest else None
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc


@dataclass(frozen=True, slots=True)
class StaffFilters:
    statuses: list[Status]
    categories: list[Category]
    gouvernorat_code: int | None
    since: datetime | None
    until: datetime | None
    bbox: tuple[float, float, float, float] | None
    q: str | None
    sort: str = "received"  # received | priority
    incident_id: uuid.UUID | None = None


async def staff_list(
    session: AsyncSession, principal: Principal, filters: StaffFilters, limit: int, cursor: str | None
) -> tuple[list[schemas.StaffReport], str | None]:
    query = (
        select(Report, _LAT, _LON, Account.kind, _MEDIA_COUNT, Analysis)
        .join(Account, Account.user_id == Report.user_id)
        .outerjoin(Analysis, Analysis.report_id == Report.id)
        .where(scope_filter(principal))
    )
    if filters.statuses:
        query = query.where(Report.status.in_([s.value for s in filters.statuses]))
    if filters.categories:
        query = query.where(Report.category.in_([c.value for c in filters.categories]))
    if filters.gouvernorat_code is not None:
        query = query.where(Report.gouvernorat_code == filters.gouvernorat_code)
    if filters.since is not None:
        query = query.where(Report.received_at >= filters.since)
    if filters.until is not None:
        query = query.where(Report.received_at < filters.until)
    if filters.bbox is not None:
        min_lon, min_lat, max_lon, max_lat = filters.bbox
        envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
        query = query.where(func.ST_Intersects(cast(Report.location, Geometry), envelope))
    if filters.q:
        pattern = "%" + filters.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(
            or_(
                Report.tracking_code.ilike(pattern, escape="\\"),
                Report.text_original.ilike(pattern, escape="\\"),
                Report.text_ar.ilike(pattern, escape="\\"),
            )
        )
    if filters.incident_id is not None:
        query = query.where(Report.incident_id == filters.incident_id)
    by_priority = filters.sort == "priority"
    priority = func.coalesce(Report.priority_score, -1)
    if cursor:
        at, rid, last_priority = decode_cursor(cursor)
        newer = or_(Report.received_at < at, and_(Report.received_at == at, Report.id < rid))
        if by_priority:
            if last_priority is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor")
            newer = or_(priority < last_priority, and_(priority == last_priority, newer))
        query = query.where(newer)
    order: list[Any] = [Report.received_at.desc(), Report.id.desc()]
    if by_priority:
        order.insert(0, priority.desc())
    rows = (await session.execute(query.order_by(*order).limit(limit))).all()
    items = [staff_report(ReportRow(r[0], r[1], r[2]), r[3].value, int(r[4]), r[5]) for r in rows]
    next_cursor = None
    if len(rows) == limit:
        last = rows[-1][0]
        next_cursor = encode_cursor(
            last.received_at,
            last.id,
            (last.priority_score if last.priority_score is not None else -1) if by_priority else None,
        )
    return items, next_cursor


async def staff_summary(session: AsyncSession, report_id: uuid.UUID) -> tuple[schemas.StaffReport, Report] | None:
    found = (
        await session.execute(
            select(Report, _LAT, _LON, Account.kind, _MEDIA_COUNT, Analysis)
            .join(Account, Account.user_id == Report.user_id)
            .outerjoin(Analysis, Analysis.report_id == Report.id)
            .where(Report.id == report_id)
        )
    ).first()
    if found is None:
        return None
    row = ReportRow(found[0], found[1], found[2])
    return staff_report(row, found[3].value, int(found[4]), found[5]), found[0]


async def history_of(session: AsyncSession, report_id: uuid.UUID) -> list[schemas.StaffHistoryEntry]:
    rows = await session.scalars(
        select(StatusHistory).where(StatusHistory.report_id == report_id).order_by(StatusHistory.at, StatusHistory.id)
    )
    return [schemas.StaffHistoryEntry(status=Status(h.status), at=h.at, actor=h.actor, note=h.note) for h in rows]


async def change_status(session: AsyncSession, report: Report, target: Status, actor: str, note: str | None) -> None:
    current = Status(report.status)
    if not can_transition(current, target):
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    now = datetime.now(UTC)
    report.status = target.value
    report.updated_at = now
    if report.first_response_at is None:
        report.first_response_at = now
    session.add(StatusHistory(report_id=report.id, status=target.value, at=now, actor=actor, note=note))
    await session.flush()


async def kpis(session: AsyncSession, principal: Principal, since: datetime) -> schemas.Kpis:
    base = and_(scope_filter(principal), Report.received_at >= since)
    by_status = dict(
        (await session.execute(select(Report.status, func.count()).where(base).group_by(Report.status))).all()
    )
    by_category = dict(
        (await session.execute(select(Report.category, func.count()).where(base).group_by(Report.category))).all()
    )
    by_gov = (
        await session.execute(
            select(Report.gouvernorat_code, func.count())
            .where(base)
            .group_by(Report.gouvernorat_code)
            .order_by(func.count().desc())
        )
    ).all()
    avg_response = await session.scalar(
        select(func.avg(func.extract("epoch", Report.first_response_at - Report.received_at))).where(
            base, Report.first_response_at.is_not(None)
        )
    )
    high = await session.scalar(select(func.count()).where(base, Report.priority_score >= HIGH_PRIORITY))
    pending = await session.scalar(
        select(func.count())
        .select_from(Report)
        .join(Analysis, Analysis.report_id == Report.id)
        .where(base, Analysis.state.in_(("pending", "running")))
    )
    return schemas.Kpis(
        since=since,
        high_priority=int(high or 0),
        analysis_pending=int(pending or 0),
        total=sum(by_status.values()),
        by_status={s.value: int(by_status.get(s.value, 0)) for s in Status},
        by_category={c.value: int(by_category.get(c.value, 0)) for c in Category},
        by_gouvernorat=[schemas.GouvernoratCount(code=code, count=int(n)) for code, n in by_gov],
        avg_first_response_s=float(avg_response) if avg_response is not None else None,
    )
