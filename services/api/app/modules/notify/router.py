"""App side of notifications (FR-A-060, FR-A-061): push devices, inbox, active alerts."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, Response, status
from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.ratelimit import enforce, opaque
from app.modules.identity.service import CurrentReporter
from app.modules.notify import schemas, service
from app.modules.notify.models import Device
from app.modules.reports.service import locate_gouvernorat

router = APIRouter(prefix="/api/v1", tags=["notifications"])
Session = Annotated[AsyncSession, Depends(get_session)]
ALERTS_LIMIT, ALERTS_WINDOW_S = 60, 60


@router.put("/devices", status_code=status.HTTP_204_NO_CONTENT)
async def register_device(reporter: CurrentReporter, session: Session, body: schemas.DeviceIn) -> Response:
    location, gouvernorat = None, None
    if body.location_alerts and body.lat is not None and body.lon is not None:
        # About 1 km: enough to target an alert zone, too coarse to follow anyone.
        lat, lon = round(body.lat, 2), round(body.lon, 2)
        location = f"SRID=4326;POINT({lon} {lat})"
        gouvernorat = await locate_gouvernorat(session, lat, lon)
    values = {
        "user_id": reporter.user_id,
        "platform": body.platform,
        "locale": body.locale,
        "location": location,
        "gouvernorat_code": gouvernorat,
        "updated_at": func.now(),
    }
    await session.execute(
        insert(Device)
        .values(token=body.token, **values)
        .on_conflict_do_update(index_elements=[Device.token], set_=values)
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/devices/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_device(
    reporter: CurrentReporter, session: Session, token: Annotated[str, Path(min_length=20, max_length=4096)]
) -> Response:
    await session.execute(delete(Device).where(Device.token == token, Device.user_id == reporter.user_id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/alerts/active", response_model=list[schemas.PublicAlert])
async def active_alerts(
    request: Request,
    response: Response,
    session: Session,
    lat: Annotated[float | None, Query(ge=30.0, le=37.6)] = None,
    lon: Annotated[float | None, Query(ge=7.4, le=11.7)] = None,
    gouvernorat_code: int | None = None,
) -> list[schemas.PublicAlert]:
    """Public: alerts are meant to be seen by everyone in the area, signed in or not."""
    client = request.client.host if request.client else "unknown"
    await enforce(f"alerts:{opaque(client)}", ALERTS_LIMIT, ALERTS_WINDOW_S)
    response.headers["Cache-Control"] = "public, max-age=60"
    if (lat is None) != (lon is None):
        lat = lon = None
    return await service.active_alerts(session, lat, lon, gouvernorat_code)


@router.get("/notifications", response_model=schemas.InboxPage)
async def inbox(
    reporter: CurrentReporter,
    session: Session,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    cursor: str | None = None,
) -> schemas.InboxPage:
    items, next_cursor = await service.inbox(session, reporter.user_id, limit, cursor)
    return schemas.InboxPage(items=items, next_cursor=next_cursor)
