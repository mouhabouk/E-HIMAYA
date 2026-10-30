"""Dashboard endpoints for staff (FR-C-01, FR-C-02). Every query is restricted to the caller's scope."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, authorize, require
from app.core.db import as_system, get_session
from app.core.events import emit
from app.core.security import Principal, Role, require_roles
from app.core.storage import get_store
from app.modules.ai.models import Analysis
from app.modules.audit import service as audit
from app.modules.audit.service import actor_of
from app.modules.geo import service as geo_service
from app.modules.identity.models import Profile
from app.modules.medical import service as locked_files
from app.modules.moderation import service as moderation
from app.modules.ops import service as ops
from app.modules.orgs import service as orgs
from app.modules.orgs.models import Organization
from app.modules.reports import intake, jurisdiction, schemas, service
from app.modules.reports.domain import TRANSITIONS, Category, Status
from app.modules.reports.models import Media, MedicalAttachment, ReporterContext
from app.modules.reports.uploads import media_url

router = APIRouter(prefix="/api/v1/staff", tags=["staff"])

READ_ROLES = (Role.OPERATOR, Role.OPS_MANAGER, Role.FIELD_COMMANDER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE)
WRITE_ROLES = (Role.OPERATOR, Role.OPS_MANAGER, Role.FIELD_COMMANDER)

StaffReader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
StaffWriter = Annotated[Principal, Depends(require_roles(*WRITE_ROLES))]
# Coarse first gates of the phase 9 actions; core.access decides on the loaded report.
RoomAgent = Annotated[Principal, Depends(require_roles(Role.OPERATOR, Role.OPS_MANAGER))]
Referrer = Annotated[Principal, Depends(require_roles(Role.OPERATOR, Role.OPS_MANAGER, Role.CENTRAL_COMMITTEE))]
ReferralDecider = Annotated[Principal, Depends(require_roles(Role.OPERATOR, Role.OPS_MANAGER, Role.LOCAL_COMMITTEE))]
GEO_STATES = ("trusted", "pending", "contradictory", "verified")
ESCALATION_STATES = ("none", "late", "central_responding", "referred", "referral_accepted", "referral_refused")
SLA_BANDS = ("critical", "high", "normal", "low")
Session = Annotated[AsyncSession, Depends(get_session)]


def _csv(raw: str | None, allowed: tuple[str, ...], code: str) -> list[str]:
    values = [item.strip() for item in (raw or "").split(",") if item.strip()]
    if any(v not in allowed for v in values):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, code)
    return values


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


@router.get("/kpis/delegations", response_model=list[schemas.DelegationCount])
async def kpis_by_delegation(
    principal: StaffReader,
    session: Session,
    since: datetime | None = None,
    category: Category | None = None,
) -> list[schemas.DelegationCount]:
    """Reports per délégation in the caller's scope (phase M): the map colours each délégation by its rate per
    10,000 inhabitants (census 2024, from the boundaries)."""
    return await service.kpis_by_delegation(
        session, principal, since or datetime.now(UTC) - timedelta(days=30), category
    )


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
    needs_verification: bool | None = None,
    geo_state: str | None = None,
    escalation_state: str | None = None,
    claimed: bool | None = None,
    sla_band: str | None = None,
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
        needs_verification=needs_verification,
        geo_states=_csv(geo_state, GEO_STATES, "invalid_geo_state"),
        escalation_states=_csv(escalation_state, ESCALATION_STATES, "invalid_escalation_state"),
        claimed=claimed,
        sla_bands=_csv(sla_band, SLA_BANDS, "invalid_sla_band"),
    )
    items, next_cursor = await service.staff_list(session, principal, filters, limit, cursor)
    return schemas.StaffReportPage(items=items, next_cursor=next_cursor)


@router.get("/reports/late", response_model=schemas.StaffReportPage)
async def late_reports(
    principal: StaffReader,
    session: Session,
    gouvernorat: int | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    cursor: str | None = None,
) -> schemas.StaffReportPage:
    """Reports past their claim deadline, for the central room (phase 9 §4.4)."""
    items, next_cursor = await jurisdiction.late_list(session, principal, gouvernorat, limit, cursor)
    return schemas.StaffReportPage(items=items, next_cursor=next_cursor)


@router.get("/reports/geo-queue", response_model=schemas.StaffReportPage)
async def geo_queue(
    principal: StaffReader,
    session: Session,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    cursor: str | None = None,
) -> schemas.StaffReportPage:
    """Open reports whose location waits for a verifier (phase 9 §4.5)."""
    items, next_cursor = await jurisdiction.geo_queue(session, principal, limit, cursor)
    return schemas.StaffReportPage(items=items, next_cursor=next_cursor)


def masked_phone(phone: str | None) -> str | None:
    """``+216••••••12``: enough to recognise a call-back, not to dial (§1.3)."""
    return f"{phone[:4]}••••••{phone[-2:]}" if phone and len(phone) > 6 else None


async def detail_of(
    session: AsyncSession, principal: Principal, report_id: uuid.UUID, *, just_handed_back: bool = False
) -> schemas.StaffReportDetail:
    """The staff view of one report. `just_handed_back`: the caller was in scope for the write it just made (a
    refused referral) and has lost the read since; it gets this one masked answer to its own request, read with the
    system scope since row-level security no longer shows it the row."""
    if just_handed_back:
        async with as_system(session):
            return await _detail(session, principal, report_id, just_handed_back=True)
    return await _detail(session, principal, report_id, just_handed_back=False)


async def _detail(
    session: AsyncSession, principal: Principal, report_id: uuid.UUID, *, just_handed_back: bool
) -> schemas.StaffReportDetail:
    found = await service.staff_summary(session, report_id)
    # Out-of-scope reports answer 404, not 403, so their existence is not disclosed.
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    summary, report = found
    ctx = await service.report_ctx(session, report)
    if not just_handed_back:
        require(await authorize(session, principal, Action.REPORT_READ, ctx))

    store = get_store()
    media = (await service.media_for(session, [report.id]))[report.id]
    media_out = [
        schemas.StaffMediaOut(
            **service.media_out(m).model_dump(),
            url=media_url(store, m),
            rejection_reason=m.rejection_reason,
        )
        for m in media
    ]
    # Reporter identity and residence only for the handling operations room or under break-glass (§1.3).
    sensitive = await authorize(session, principal, Action.REPORT_READ_SENSITIVE, ctx)
    profile = await session.get(Profile, report.user_id) if summary.reporter_kind != "anonymous" else None
    if sensitive.allowed:
        reporter = schemas.Reporter(
            kind=summary.reporter_kind,
            first_name=profile.first_name if profile else None,
            last_name=profile.last_name if profile else None,
            phone=profile.phone if profile else None,
        )
        context = await session.get(ReporterContext, report.id)
        reporter_context = (
            schemas.ReporterContextOut(
                reporter_gouvernorat_code=context.reporter_gouvernorat_code,
                source=context.source,
            )
            if context is not None
            else None
        )
        if sensitive.grant_id is not None:
            await audit.record(
                session,
                actor=actor_of(principal),
                action="report.view_sensitive",
                target=f"report:{report.id}",
                details={"grant_id": str(sensitive.grant_id)},
                gouvernorats=await service.gouvernorat_codes(session, report),
            )
            await session.commit()
    else:
        reporter = schemas.Reporter(
            kind=summary.reporter_kind, masked=True, phone=masked_phone(profile.phone if profile else None)
        )
        reporter_context = None
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
        escalations=await jurisdiction.escalations_of(session, report.id),
        reporter_context=reporter_context,
        medical_attached=await session.get(MedicalAttachment, report.id) is not None,
        address=await geo_service.address_out(
            session, report.delegation_id, report.sector_code, report.municipality_id
        ),
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
            translation_ar=m.translation_ar,
            error=(m.analysis or {}).get("error"),
            model=(m.analysis or {}).get("model"),
            text_masks=moderation.masks(m.transcript),
            translation_ar_masks=moderation.masks(m.translation_ar),
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
    # NFR-06: opening a report shows personal data (location, media, reporter when allowed) and is audited.
    await audit.record(
        session,
        actor=actor_of(principal),
        action="report.view",
        target=f"report:{report_id}",
        details={"reporter_masked": detail.reporter.masked},
    )
    await session.commit()
    return detail


@router.get("/reports/{report_id}/medical", response_model=schemas.MedicalOut)
async def get_medical(principal: StaffReader, session: Session, report_id: uuid.UUID) -> schemas.MedicalOut:
    """The medical file the reporter attached (phase B2, addition 7b): only for the staff allowed to see the reporter's
    identity (the handling operations room, or break-glass), and every opening is audited."""
    found = await service.staff_summary(session, report_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    _, report = found
    ctx = await service.report_ctx(session, report)
    require(await authorize(session, principal, Action.REPORT_READ, ctx))
    sensitive = await authorize(session, principal, Action.REPORT_READ_SENSITIVE, ctx)
    require(sensitive)
    attachment = await session.get(MedicalAttachment, report.id)
    if attachment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_medical_file")
    details: dict[str, str] = {}
    if sensitive.grant_id is not None:
        details["grant_id"] = str(sensitive.grant_id)
    await audit.record(
        session,
        actor=actor_of(principal),
        action="report.medical_view",
        target=f"report:{report.id}",
        details=details,
        gouvernorats=await service.gouvernorat_codes(session, report),
    )
    referrals, opinions = await locked_files.counts(session, report.id)
    out = schemas.MedicalOut(
        data=schemas.MedicalFile.model_validate(attachment.data),
        attached_at=attachment.attached_at,
        locked=await locked_files.has_locked(session, report.id),
        referrals=referrals,
        opinions=opinions,
    )
    await session.commit()
    return out


@router.post("/reports/{report_id}/status", response_model=schemas.StaffReportDetail)
async def change_status(
    principal: StaffWriter, session: Session, report_id: uuid.UUID, body: schemas.StatusChangeIn
) -> schemas.StaffReportDetail:
    report, ctx = await jurisdiction.load(session, principal, report_id)
    # The caller's room must hold the claim; an unclaimed report is claimed on the way (phase 9 §4.3).
    await jurisdiction.before_status_change(session, principal, report, ctx)
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
        gouvernorats=await service.gouvernorat_codes(session, report),
    )
    await ops.after_status_change(session, report, actor)
    summary = await service.staff_summary(session, report_id)
    assert summary is not None
    await emit(
        session,
        "report.status_changed",
        {
            "report": summary[0].model_dump(mode="json"),
            "gouvernorat_codes": await service.gouvernorat_codes(session, report),
        },
    )
    await session.commit()
    return await detail_of(session, principal, report_id)


# ---------------------------------------------------------------- reports entered by a room (phase N §5)


@router.post("/reports", response_model=schemas.StaffReportDetail, status_code=status.HTTP_201_CREATED)
async def enter_report(principal: RoomAgent, session: Session, body: schemas.RoomReportIn) -> schemas.StaffReportDetail:
    """A report that came by telephone, radio or in person, written down by the room that answers it."""
    report_id = await intake.create(session, principal, body)
    await session.commit()
    return await detail_of(session, principal, report_id)


# ---------------------------------------------------------------- claim, referral, geo-verification (phase 9 §4)


@router.post("/reports/{report_id}/claim", response_model=schemas.StaffReportDetail)
async def claim_report(principal: StaffWriter, session: Session, report_id: uuid.UUID) -> schemas.StaffReportDetail:
    report, ctx = await jurisdiction.load(session, principal, report_id)
    await jurisdiction.claim(session, principal, report, ctx)
    await session.commit()
    return await detail_of(session, principal, report_id)


@router.delete("/reports/{report_id}/claim", response_model=schemas.StaffReportDetail)
async def release_claim(
    principal: StaffWriter, session: Session, report_id: uuid.UUID, body: schemas.ReleaseIn
) -> schemas.StaffReportDetail:
    await jurisdiction.release(session, principal, report_id, body.reason)
    await session.commit()
    return await detail_of(session, principal, report_id)


@router.post("/reports/{report_id}/refer", response_model=schemas.StaffReportDetail)
async def refer_report(
    principal: Referrer, session: Session, report_id: uuid.UUID, body: schemas.ReferIn
) -> schemas.StaffReportDetail:
    await jurisdiction.refer(session, principal, report_id, body)
    await session.commit()
    return await detail_of(session, principal, report_id)


@router.post("/reports/{report_id}/referral/accept", response_model=schemas.StaffReportDetail)
async def accept_referral(
    principal: ReferralDecider, session: Session, report_id: uuid.UUID, body: schemas.ReferralAcceptIn
) -> schemas.StaffReportDetail:
    await jurisdiction.decide_referral(session, principal, report_id, accept=True, text_=body.note)
    await session.commit()
    return await detail_of(session, principal, report_id)


@router.post("/reports/{report_id}/referral/refuse", response_model=schemas.StaffReportDetail)
async def refuse_referral(
    principal: ReferralDecider, session: Session, report_id: uuid.UUID, body: schemas.ReferralRefuseIn
) -> schemas.StaffReportDetail:
    await jurisdiction.decide_referral(session, principal, report_id, accept=False, text_=body.reason)
    await session.commit()
    # The refusing region no longer sees the report (it returns to the central late list).
    return await detail_of(session, principal, report_id, just_handed_back=True)


@router.post("/reports/{report_id}/geo-verify", response_model=schemas.StaffReportDetail)
async def geo_verify(
    principal: Referrer, session: Session, report_id: uuid.UUID, body: schemas.GeoVerifyIn
) -> schemas.StaffReportDetail:
    await jurisdiction.geo_verify(session, principal, report_id, body)
    await session.commit()
    return await detail_of(session, principal, report_id)
