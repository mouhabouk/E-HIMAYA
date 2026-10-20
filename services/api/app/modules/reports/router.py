"""Reporter-facing endpoints (mobile app): create, list mine, public tracking."""

import time
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import metrics
from app.core.config import get_settings
from app.core.db import get_session, get_system_sessionmaker
from app.core.ratelimit import Verdict, check, client_key, enforce, too_many
from app.modules.identity.service import AnonQuota, CurrentReporter, Reporter, anon_quota
from app.modules.orgs import service as orgs
from app.modules.reports import schemas, service
from app.modules.reports.domain import CATEGORY_LABELS, Lang
from app.modules.settings import domain as settings_domain
from app.modules.settings import service as settings

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

Session = Annotated[AsyncSession, Depends(get_session)]

# Generous enough for a real emergency (several reports + retries), low enough to stop floods.
CREATE_LIMIT, CREATE_WINDOW_S = 20, 600
TRACK_LIMIT, TRACK_WINDOW_S = 30, 60


@router.get("/categories", response_model=list[schemas.CategoryOut])
async def categories(lang: Lang = "ar") -> list[schemas.CategoryOut]:
    return [schemas.CategoryOut(code=code, label=labels[lang]) for code, labels in CATEGORY_LABELS.items()]


@router.post(
    "",
    response_model=schemas.ReportOut,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"model": schemas.ReportOut, "description": "Replay of an already received client_uuid"}},
)
async def create_report(
    request: Request, body: schemas.ReportIn, reporter: CurrentReporter, session: Session, response: Response
) -> schemas.ReportOut:
    """Receive a report and assign its tracking code. Safe to retry with the same ``client_uuid``.

    A replay of a known ``client_uuid`` is answered first (200) and consumes neither limits nor quota.
    Abuse controls (A1, A2): per account and, for anonymous reporters, per client address (429 beyond).
    Anonymous reports beyond the global budget are still accepted, flagged ``needs_verification`` with a
    lowered priority. While the limiter is degraded (Valkey down) a report is never refused: what the
    fallback limiter would have refused is accepted and flagged instead. Anonymous installations have a quota
    (phase 9 §3): beyond it a non-SOS report answers ``403 anon_quota_exhausted``; every answer carries
    ``X-Anon-Quota-Limit`` / ``X-Anon-Quota-Remaining``."""
    started = time.perf_counter()
    try:
        existing = await service.replay(session, reporter, body.client_uuid)
        if existing is not None:
            row, created = existing, False
        else:
            verification = await _abuse_checks(request, reporter)
            row, created = await service.create_report(session, reporter, body, verification)
    except HTTPException as exc:
        await session.rollback()
        exc.headers = {**(exc.headers or {}), **await _quota_headers(session, reporter)}
        raise
    if created:
        metrics.REPORT_INGEST_SECONDS.labels(reporter_kind=reporter.kind.value).observe(time.perf_counter() - started)
        if row.report.verification_reason is not None:
            metrics.REPORTS_FLAGGED.labels(reason=row.report.verification_reason).inc()
    if not created:
        response.status_code = status.HTTP_200_OK
    response.headers.update(await _quota_headers(session, reporter))
    media = await service.media_for(session, [row.report.id])
    refs = await orgs.refs(session, [row.report.organization_id])
    org = refs.get(row.report.organization_id) if row.report.organization_id else None
    return service.report_out(row, media[row.report.id], org)


async def _quota(session: AsyncSession, reporter: Reporter) -> AnonQuota | None:
    return await anon_quota(session, reporter, int(await settings.get(session, settings_domain.ANON_QUOTA)))


async def _quota_headers(session: AsyncSession, reporter: Reporter) -> dict[str, str]:
    quota = await _quota(session, reporter)
    if quota is None:
        return {}
    return {"X-Anon-Quota-Limit": str(quota.limit), "X-Anon-Quota-Remaining": str(quota.remaining)}


@router.get("/quota", response_model=schemas.QuotaOut)
async def quota(reporter: CurrentReporter, session: Session, response: Response) -> schemas.QuotaOut:
    """Anonymous report quota of this installation; all null for registered accounts (no quota)."""
    found = await _quota(session, reporter)
    if found is None:
        return schemas.QuotaOut(limit=None, used=None, remaining=None)
    response.headers.update(await _quota_headers(session, reporter))
    return schemas.QuotaOut(limit=found.limit, used=found.used, remaining=found.remaining)


async def _abuse_checks(request: Request, reporter: Reporter) -> str | None:
    """Apply the report limits; return the verification reason to flag the report with, if any."""
    settings = get_settings()
    flag: str | None = None

    def refuse_or_flag(verdict: Verdict) -> None:
        nonlocal flag
        if not verdict.exceeded:
            return
        if not verdict.degraded:
            raise too_many(verdict.retry_after)
        flag = flag or "limiter_degraded"

    refuse_or_flag(await check(f"report:{reporter.user_id}", CREATE_LIMIT, CREATE_WINDOW_S))
    if reporter.is_anonymous:
        refuse_or_flag(
            await check(f"report-ip:{client_key(request)}", settings.anon_report_per_ip, settings.anon_report_window_s)
        )
        budget = await check("anon-report-budget", settings.anon_report_budget, settings.anon_report_budget_window_s)
        if budget.exceeded:
            metrics.ANON_BUDGET_EXCEEDED.inc()
            flag = "anonymous_budget"
    return flag


@router.get("/mine", response_model=schemas.ReportPage)
async def my_reports(
    reporter: CurrentReporter,
    session: Session,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before: datetime | None = None,
) -> schemas.ReportPage:
    items, next_before = await service.my_reports(session, reporter, limit, before)
    return schemas.ReportPage(items=items, next_before=next_before)


@router.get("/track/{tracking_code}", response_model=schemas.TrackOut)
async def track(
    request: Request,
    tracking_code: Annotated[str, Path(pattern=r"^EH-\d{2}-\d{2}-\d{7}$")],
) -> schemas.TrackOut:
    """Status of a report by tracking code (works for anonymous reporters). Exposes no report content."""
    await enforce(f"track:{client_key(request)}", TRACK_LIMIT, TRACK_WINDOW_S)
    # No caller identity: the single lookup runs with the system database scope (row-level security, §9.1).
    async with get_system_sessionmaker()() as system:
        result = await service.track(system, tracking_code)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return result
