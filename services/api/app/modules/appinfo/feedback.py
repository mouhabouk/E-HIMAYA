"""Rating of the app (phase P5b, F-APP-143, docs/phase-p5/design-simple.md §2.2).

``POST /api/v1/app/feedback``: any reporter, registered or anonymous, rates the app from 1 to 5 stars with an optional
remark. Not a "contact us" request: no number, no due date, no answer; the app points to "contact us" for that.

``GET /api/v1/staff/app-feedback``: the system administrator and the content editor read the average, the share of
each star, the average per build and the latest remarks over a period. Every reading is audited (remarks are
the citizens' own words).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.appinfo.models import AppRating
from app.modules.audit import service as audit
from app.modules.identity.service import CurrentReporter, limit_reporter
from app.modules.moderation import service as moderation

router = APIRouter(prefix="/api/v1", tags=["app"])
Session = Annotated[AsyncSession, Depends(get_session)]
Reader = Annotated[Principal, Depends(require_roles(Role.SYSADMIN, Role.CONTENT_EDITOR))]

PER_ACCOUNT_PER_DAY = 3
PER_IP_PER_DAY = 10
DAY_S = 86_400
LATEST = 30
BUILDS = 10

Remark = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stars: int = Field(ge=1, le=5)
    remark: Remark | None = None
    platform: Literal["android", "ios"] | None = None
    build: int | None = Field(default=None, ge=1, le=1_000_000)
    version: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None = None
    locale: Literal["ar", "fr", "en"] = "ar"


class FeedbackOut(BaseModel):
    id: uuid.UUID
    stars: int
    created_at: datetime


class BuildAverage(BaseModel):
    build: int | None
    version: str | None
    count: int
    average: float


class RemarkOut(BaseModel):
    stars: int
    remark: str
    platform: str | None
    version: str | None
    locale: str
    created_at: datetime


class SummaryOut(BaseModel):
    days: int
    count: int
    # None while nobody rated in the period.
    average: float | None
    # Ratings per star, "1" to "5".
    by_stars: dict[str, int]
    by_build: list[BuildAverage]
    remarks: list[RemarkOut]


class ExportRating(BaseModel):
    stars: int
    remark: str | None
    platform: str | None
    version: str | None
    created_at: datetime


@router.post("/app/feedback", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
async def rate_app(request: Request, reporter: CurrentReporter, session: Session, body: FeedbackIn) -> FeedbackOut:
    await limit_reporter(
        request, reporter, "app-feedback", per_account=PER_ACCOUNT_PER_DAY, per_ip=PER_IP_PER_DAY, window_s=DAY_S
    )
    remark = body.remark or None
    # Not emergency text: the respectful-language filter applies (rule 4).
    await moderation.check(session, remark)
    row = AppRating(
        user_id=reporter.user_id,
        stars=body.stars,
        remark=remark,
        platform=body.platform,
        build=body.build,
        version=body.version or None,
        locale=body.locale,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    out = FeedbackOut(id=row.id, stars=row.stars, created_at=row.created_at)
    await session.commit()
    return out


@router.get("/staff/app-feedback", response_model=SummaryOut)
async def summary(principal: Reader, session: Session, days: Annotated[int, Query(ge=1, le=365)] = 90) -> SummaryOut:
    since = datetime.now(UTC) - timedelta(days=days)
    period = AppRating.created_at >= since
    stars = dict(
        (await session.execute(select(AppRating.stars, func.count()).where(period).group_by(AppRating.stars))).all()
    )
    count = sum(int(n) for n in stars.values())
    average = round(sum(int(s) * int(n) for s, n in stars.items()) / count, 2) if count else None
    builds = (
        await session.execute(
            select(AppRating.build, func.max(AppRating.version), func.count(), func.avg(AppRating.stars))
            .where(period)
            .group_by(AppRating.build)
            .order_by(AppRating.build.desc().nulls_last())
            .limit(BUILDS)
        )
    ).all()
    latest = await session.scalars(
        select(AppRating)
        .where(period, AppRating.remark.is_not(None))
        .order_by(AppRating.created_at.desc())
        .limit(LATEST)
    )
    remarks = [
        RemarkOut(
            stars=r.stars,
            remark=r.remark or "",
            platform=r.platform,
            version=r.version,
            locale=r.locale,
            created_at=r.created_at,
        )
        for r in latest.all()
        if r.remark
    ]
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="app_feedback.read",
        details={"days": days, "remarks": len(remarks)},
    )
    await session.commit()
    return SummaryOut(
        days=days,
        count=count,
        average=average,
        by_stars={str(s): int(stars.get(s, 0)) for s in range(1, 6)},
        by_build=[BuildAverage(build=b, version=v, count=int(n), average=round(float(a), 2)) for b, v, n, a in builds],
        remarks=remarks,
    )


async def export(session: AsyncSession, user_id: uuid.UUID) -> list[ExportRating]:
    rows = await session.scalars(select(AppRating).where(AppRating.user_id == user_id).order_by(AppRating.created_at))
    return [
        ExportRating(stars=r.stars, remark=r.remark, platform=r.platform, version=r.version, created_at=r.created_at)
        for r in rows.all()
    ]


async def forget(session: AsyncSession, user_id: uuid.UUID) -> int:
    """Ratings are the account's own words: they go with the account."""
    result = await session.execute(delete(AppRating).where(AppRating.user_id == user_id))
    return int(result.rowcount)  # type: ignore[attr-defined]
