"""Citizen and public rewards endpoints (FR-A-072, docs/api/phase-8-contract.md §3).

* ``GET /api/v1/me/rewards`` — balance, confirmed badges, next badge, history, certificates, pause state and the
  fixed notices (no cash prizes; never put yourself in danger to report). Anonymous device identities get an empty
  answer with ``"anonymous": true``: anonymous reports earn no points (the app explains why).
* ``GET /api/v1/me/rewards/history`` — the ledger page by page.
* ``GET /api/v1/me/rewards/certificates/{id}`` — the holder's certificate PDF (302 to a short-lived presigned URL).
* ``GET /api/v1/rewards/certificates/{code}`` — public verification (QR code): initials, distinction, date only.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.ratelimit import client_key, enforce
from app.core.storage import get_store
from app.modules.audit import service as audit
from app.modules.identity.models import Profile
from app.modules.identity.service import CurrentReporter
from app.modules.rewards import certificates, schemas, service
from app.modules.rewards.domain import (
    DISTINCTION_LABELS,
    LEVEL_ORDER,
    PRIZES_NOTICE,
    SAFETY_NOTICE,
    BadgeStatus,
    Level,
)
from app.modules.rewards.models import BadgeAward, LedgerEntry, RewardCertificate

router = APIRouter(prefix="/api/v1", tags=["rewards"])
Session = Annotated[AsyncSession, Depends(get_session)]

HISTORY_LIMIT = 50
VERIFY_LIMIT = 60
VERIFY_WINDOW_S = 60


def history_item(entry: LedgerEntry, tracking_code: str | None) -> schemas.HistoryItem:
    return schemas.HistoryItem(
        id=entry.id,
        delta=entry.delta,
        reason=entry.reason,
        report_id=entry.report_id,
        tracking_code=tracking_code,
        intervention_id=entry.intervention_id,
        multiplier=float(entry.multiplier) if entry.multiplier is not None else None,
        capped=entry.capped,
        created_at=entry.created_at,
    )


def _empty(anonymous: bool) -> schemas.MyRewards:
    return schemas.MyRewards(
        anonymous=anonymous,
        balance=0,
        pending_points=0,
        paused=False,
        daily_cap=get_settings().rewards_daily_cap,
        badges=[],
        current_badge=None,
        next_badge=None,
        history=[],
        history_next_cursor=None,
        certificates=[],
        prizes_notice=schemas.Localized(**PRIZES_NOTICE),
        safety_notice=schemas.Localized(**SAFETY_NOTICE),
    )


@router.get("/me/rewards", response_model=schemas.MyRewards)
async def my_rewards(reporter: CurrentReporter, session: Session) -> schemas.MyRewards:
    user_id = reporter.user_id
    if reporter.is_anonymous:
        return _empty(anonymous=True)
    if not await service.eligible(session, user_id):
        return _empty(anonymous=False)
    balance = await service.balance_of(session, user_id)
    pending = await service.pending_points_of(session, user_id)
    profile = await session.get(Profile, user_id)
    paused = pending > 0 or await service.paused_in(session, profile.gouvernorat_code if profile else None)
    badges = list(
        await session.scalars(
            select(BadgeAward).where(BadgeAward.citizen_id == user_id, BadgeAward.status == BadgeStatus.CONFIRMED.value)
        )
    )
    badges.sort(key=lambda b: LEVEL_ORDER.index(Level(b.level)))
    confirmed = {Level(b.level) for b in badges}
    upcoming = service.next_badge(balance, confirmed)
    rows, next_cursor = await service.ledger_page(session, user_id, HISTORY_LIMIT, None)
    certs = await session.scalars(
        select(RewardCertificate)
        .where(RewardCertificate.subject_id == user_id, RewardCertificate.revoked_at.is_(None))
        .order_by(RewardCertificate.issued_at.desc())
    )
    return schemas.MyRewards(
        anonymous=False,
        balance=balance,
        pending_points=pending,
        paused=paused,
        daily_cap=get_settings().rewards_daily_cap,
        badges=[schemas.BadgeOut(id=b.id, level=Level(b.level), confirmed_at=b.decided_at) for b in badges],
        current_badge=Level(badges[-1].level) if badges else None,
        next_badge=(
            schemas.NextBadge(level=upcoming[0], threshold=upcoming[1], missing_points=max(upcoming[1] - balance, 0))
            if upcoming
            else None
        ),
        history=[history_item(entry, code) for entry, code, _ in rows],
        history_next_cursor=next_cursor,
        certificates=[
            schemas.MyCertificate(
                id=c.id,
                code=c.code,
                distinction=c.distinction,
                year=c.year,
                issued_at=c.issued_at,
                verify_url=certificates.verify_url(c.code),
            )
            for c in certs
        ],
        prizes_notice=schemas.Localized(**PRIZES_NOTICE),
        safety_notice=schemas.Localized(**SAFETY_NOTICE),
    )


@router.get("/me/rewards/history", response_model=schemas.HistoryPage)
async def my_history(
    reporter: CurrentReporter,
    session: Session,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> schemas.HistoryPage:
    if reporter.is_anonymous:
        return schemas.HistoryPage(items=[], next_cursor=None)
    rows, next_cursor = await service.ledger_page(session, reporter.user_id, limit, cursor)
    return schemas.HistoryPage(items=[history_item(e, code) for e, code, _ in rows], next_cursor=next_cursor)


def pdf_response(object_key: str, accept: str | None) -> Response:
    """302 to a short-lived presigned URL of the PDF; ``Accept: application/json``: ``{"url"}`` instead."""
    url = get_store().presign_get(object_key, content_type=certificates.PDF_TYPE)
    if accept and "application/json" in accept:
        return JSONResponse(schemas.DownloadOut(url=url).model_dump(), headers={"Cache-Control": "no-store"})
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND, headers={"Cache-Control": "no-store"})


@router.get(
    "/me/rewards/certificates/{cert_id}",
    response_model=None,
    responses={302: {"description": "presigned URL"}, 200: {"model": schemas.DownloadOut}},
)
async def my_certificate_pdf(
    reporter: CurrentReporter,
    session: Session,
    cert_id: uuid.UUID,
    accept: Annotated[str | None, Header()] = None,
) -> Response:
    cert = await session.get(RewardCertificate, cert_id)
    if cert is None or reporter.is_anonymous or cert.subject_id != reporter.user_id or cert.pdf_object_key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await audit.record(
        session, actor=reporter.actor, action="rewards.certificate.download", target=f"reward_certificate:{cert.id}"
    )
    await session.commit()
    return pdf_response(cert.pdf_object_key, accept)


@router.get("/rewards/certificates/{code}", response_model=schemas.PublicCertificate, tags=["public"])
async def verify_certificate(
    request: Request, session: Session, code: Annotated[str, Path(pattern=certificates.CODE_PATTERN)]
) -> schemas.PublicCertificate:
    await enforce(f"reward-verify:{client_key(request)}", VERIFY_LIMIT, VERIFY_WINDOW_S)
    cert = await session.scalar(select(RewardCertificate).where(RewardCertificate.code == code))
    if cert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return schemas.PublicCertificate(
        code=cert.code,
        valid=cert.revoked_at is None and certificates.signature_valid(cert),
        initials=cert.initials,
        distinction=cert.distinction,
        distinction_label=dict(DISTINCTION_LABELS[cert.distinction]),
        date=certificates.issued_on(cert),
    )
