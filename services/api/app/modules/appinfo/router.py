"""What the phones need to know about the app itself (phase A, addition 3, docs/phase-a/design.md §2.4).

``GET /api/v1/app/version``: public, no account. The latest release and the oldest build still allowed come from the
national setting ``app.release`` (edited by the system administrator in the dashboard). The app asks at start and
once a day: below ``latest_build`` it offers the update, below ``min_build`` the update cannot be skipped (SOS and the
emergency numbers stay reachable).
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.notify.providers import sms_simulated
from app.modules.settings import domain
from app.modules.settings import service as settings

router = APIRouter(prefix="/api/v1/app", tags=["app"])
Session = Annotated[AsyncSession, Depends(get_session)]


class ReleaseNotesOut(BaseModel):
    ar: str
    fr: str
    en: str


class AppVersionOut(BaseModel):
    platform: Literal["android", "ios"]
    latest_version: str
    latest_build: int
    min_build: int
    notes: ReleaseNotesOut
    channel: Literal["server", "play"]
    download_url: str | None
    # Filled when the caller gave its build.
    update_available: bool | None
    mandatory: bool | None
    # SIMULATION: true while SMS go to the development gateway; the app shows a [SIM] strip on the code screen.
    sms_simulated: bool


@router.get("/version", response_model=AppVersionOut)
async def app_version(
    session: Session,
    response: Response,
    platform: Annotated[Literal["android", "ios"], Query()] = "android",
    build: Annotated[int | None, Query(ge=1, le=1_000_000)] = None,
) -> AppVersionOut:
    release = domain.AppRelease.model_validate(await settings.get(session, domain.APP_RELEASE))
    response.headers["Cache-Control"] = "public, max-age=600"
    return AppVersionOut(
        platform=platform,
        latest_version=release.latest_version,
        latest_build=release.latest_build,
        min_build=release.min_build,
        notes=ReleaseNotesOut(**release.notes.model_dump()),
        channel=release.channel,
        download_url=release.download_url,
        update_available=None if build is None else build < release.latest_build,
        mandatory=None if build is None else build < release.min_build,
        sms_simulated=sms_simulated(),
    )
