"""Dashboard endpoints for staff (FR-C-01, FR-C-02). Every query is restricted to the caller's scope."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.events import emit
from app.core.security import Principal, Role, require_roles
from app.core.storage import get_store
from app.modules.ai.models import Analysis
from app.modules.audit import service as audit
from app.modules.audit.service import actor_of
from app.modules.identity.models import Profile
from app.modules.ops import service as ops
from app.modules.orgs import service as orgs
from app.modules.orgs.models import Organization
from app.modules.reports import schemas, service
from app.modules.reports.domain import TRANSITIONS, Category, Status
from app.modules.reports.models import Media

router = APIRouter(prefix="/api/v1/staff", tags=["staff"])

READ_ROLES = (Role.OPERATOR, Role.OPS_MANAGER, Role.FIELD_COMMANDER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE)
WRITE_ROLES = (Role.OPERATOR, Role.OPS_MANAGER, Role.FIELD_COMMANDER)

StaffReader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
StaffWriter = Annotated[Principal, Depends(require_roles(*WRITE_ROLES))]
Session = Annotated[AsyncSession, Depends(get_session)]


def _csv_enum[E: (Status, Category)](raw: str | None, enum: type[E]) -> list[E]:
    if not raw:
        return []
    try:
        return [enum(item.strip()) for item in raw.split(",") if item.strip()]
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"invalid_{enum.__name__.lower()}") from exc


def _bbox(raw: str | None) -> tuple[float, float, float, float] | None:
    if not raw:
        return None
    try:
        min_lon, min_lat, max_lon, max_lat = (float(v) for v in raw.split(","))
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_bbox") from exc
    if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_bbox")
    return min_lon, min_lat, max_lon, max_lat


@router.get("/kpis", response_model=schemas.Kpis)
async def kpis(principal: StaffReader, session: Session, since: datetime | None = None) -> schemas.Kpis:
    return await service.kpis(session, principal, since or datetime.now(UTC) - timedelta(hours=24))


@router.get("/reports", response_model=schemas.StaffReportPage)
async def list_reports(
    principal: StaffReader,
    session: Session,
    status_: Annotated[str | None, Query(alias="status")] = None,
    category: str | None = None,
    gouvernorat_code: int | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    bbox: str | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    sort: Annotated[Literal["received", "priority"], Query()] = "received",
    incident_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    cursor: str | None = None,
) -> schemas.StaffReportPage:
    filters = service.StaffFilters(
        statuses=_csv_enum(status_, Status),
        categories=_csv_enum(category, Category),
        gouvernorat_code=gouvernorat_code,
        since=since,
        until=until,
        bbox=_bbox(bbox),
        q=q.strip() if q and q.strip() else None,
        sort=sort,
        incident_id=incident_id,
    )
    items, next_cursor = await service.staff_list(session, principal, filters, limit, cursor)
    return schemas.StaffReportPage(items=items, next_cursor=next_cursor)


async def detail_of(session: AsyncSession, principal: Principal, report_id: uuid.UUID) -> schemas.StaffReportDetail:
    found = await service.staff_summary(session, report_id)
    # Out-of-scope reports answer 404, not 403, so their existence is not disclosed.
    if found is None or not service.in_scope(principal, found[1].gouvernorat_code):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    summary, report = found

    store = get_store()
    media = (await service.media_for(session, [report.id]))[report.id]
    media_out = [
        schemas.StaffMediaOut(
            **service.media_out(m).model_dump(),
            url=store.presign_get(m.object_key, content_type=m.content_type) if m.status == "stored" else None,
        )
        for m in media
    ]
    reporter = schemas.Reporter(kind=summary.reporter_kind)
    if summary.reporter_kind != "anonymous":
        profile = await session.get(Profile, report.user_id)
        if profile is not None:
            reporter = schemas.Reporter(
                kind=summary.reporter_kind,
                first_name=profile.first_name,
                last_name=profile.last_name,
                phone=profile.phone,
            )
    analysis = await session.get(Analysis, report.id)
    org = await session.get(Organization, report.organization_id) if report.organization_id else None
    return schemas.StaffReportDetail(
        **summary.model_dump(),
        history=await service.history_of(session, report.id),
        media=media_out,
        reporter=reporter,
        allowed_transitions=sorted(TRANSITIONS[Status(report.status)]),
        analysis=analysis_out(analysis, media) if analysis is not None else None,
        organization_card=await orgs.organization_card(session, org) if org is not None else None,
    )


def analysis_out(analysis: Analysis, media: list[Media]) -> schemas.AnalysisOut:
    transcripts = [
        schemas.Transcript(
            media_id=m.id,
            kind=m.kind,
            text=m.transcript,
            language=(m.analysis or {}).get("language"),
            language_probability=(m.analysis or {}).get("language_probability"),
            duration_s=m.duration_s,
            translation_ar=(m.analysis or {}).get("translation_ar"),
            error=(m.analysis or {}).get("error"),
            model=(m.analysis or {}).get("model"),
        )
        for m in media
        if m.kind in ("audio", "video") and (m.transcript is not None or (m.analysis or {}).get("error"))
    ]
    return schemas.AnalysisOut(
        state=analysis.state,
        attempts=analysis.attempts,
        language=analysis.language,
        steps=analysis.steps or {},
        extraction=schemas.Extraction.model_validate(analysis.extraction) if analysis.extraction else None,
        priority=schemas.ExplainedScore.model_validate(analysis.priority) if analysis.priority else None,
        credibility=schemas.ExplainedScore.model_validate(analysis.credibility) if analysis.credibility else None,
        suggestion=schemas.Suggestion.model_validate(analysis.suggestion) if analysis.suggestion else None,
        transcripts=transcripts,
        models=analysis.models or {},
        updated_at=analysis.updated_at,
    )


@router.get("/reports/{report_id}", response_model=schemas.StaffReportDetail)
async def get_report(principal: StaffReader, session: Session, report_id: uuid.UUID) -> schemas.StaffReportDetail:
    detail = await detail_of(session, principal, report_id)
    # NFR-06: opening a report shows personal data (reporter identity, location, media) and is audited.
    await audit.record(session, actor=actor_of(principal), action="report.view", target=f"report:{report_id}")
    await session.commit()
    return detail


@router.post("/reports/{report_id}/status", response_model=schemas.StaffReportDetail)
async def change_status(
    principal: StaffWriter, session: Session, report_id: uuid.UUID, body: schemas.StatusChangeIn
) -> schemas.StaffReportDetail:
    found = await service.staff_summary(session, report_id)
    if found is None or not service.in_scope(principal, found[1].gouvernorat_code):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    report = found[1]
    previous = report.status
    actor = actor_of(principal)
    await service.change_status(session, report, body.status, actor, body.note)
    await audit.record(
        session,
        actor=actor,
        action="report.status",
        target=f"report:{report_id}",
        reason=body.note,
        details={"from": previous, "to": body.status.value},
    )
    await ops.after_status_change(session, report, actor)
    summary = await service.staff_summary(session, report_id)
    assert summary is not None
    await emit(session, "report.status_changed", {"report": summary[0].model_dump(mode="json")})
    await session.commit()
    return await detail_of(session, principal, report_id)
