"""Reporter-facing endpoints (mobile app): create, list mine, public tracking."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.ratelimit import enforce, opaque
from app.modules.identity.service import CurrentReporter
from app.modules.orgs import service as orgs
from app.modules.reports import schemas, service
from app.modules.reports.domain import CATEGORY_LABELS, Lang

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
    body: schemas.ReportIn, reporter: CurrentReporter, session: Session, response: Response
) -> schemas.ReportOut:
    """Receive a report and assign its tracking code. Safe to retry with the same ``client_uuid``."""
    await enforce(f"report:{reporter.user_id}", CREATE_LIMIT, CREATE_WINDOW_S)
    row, created = await service.create_report(session, reporter, body)
    if not created:
        response.status_code = status.HTTP_200_OK
    media = await service.media_for(session, [row.report.id])
    refs = await orgs.refs(session, [row.report.organization_id])
    org = refs.get(row.report.organization_id) if row.report.organization_id else None
    return service.report_out(row, media[row.report.id], org)


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
    session: Session,
    tracking_code: Annotated[str, Path(pattern=r"^EH-\d{2}-\d{2}-\d{7}$")],
) -> schemas.TrackOut:
    """Status of a report by tracking code (works for anonymous reporters). Exposes no report content."""
    client = request.client.host if request.client else "unknown"
    await enforce(f"track:{opaque(client)}", TRACK_LIMIT, TRACK_WINDOW_S)
    result = await service.track(session, tracking_code)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return result
