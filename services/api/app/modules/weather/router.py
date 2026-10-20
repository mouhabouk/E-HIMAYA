"""Public weather card (FR-A-034): current values and the next 12 h at a position, with the weather alerts covering it.

Positions are coarse (the app rounds to 2 decimals) and never stored. The weather part is cached in-process for
10 minutes per grid point; the alerts are read fresh on every call (an alert must show at once), so the HTTP cache
lifetime is that of GET /alerts/active (60 s).
"""

import time
from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.ratelimit import client_key, enforce
from app.modules.notify import service as notify
from app.modules.reports.domain import LAT_MAX, LAT_MIN, LON_MAX, LON_MIN
from app.modules.weather import schemas, service

router = APIRouter(prefix="/api/v1", tags=["weather"])
Session = Annotated[AsyncSession, Depends(get_session)]
WEATHER_LIMIT, WEATHER_WINDOW_S = 60, 60
CACHE_TTL_S = 600
CACHE_MAX = 2000
NEXT_HOURS = 12


class _Cache:
    """Bounded time-limited cache of the weather part of the card, per grid point."""

    def __init__(self) -> None:
        self._items: OrderedDict[int, tuple[float, dict[str, Any]]] = OrderedDict()

    def get(self, key: int) -> dict[str, Any] | None:
        item = self._items.get(key)
        if item is None or item[0] < time.monotonic():
            self._items.pop(key, None)
            return None
        return item[1]

    def put(self, key: int, value: dict[str, Any]) -> None:
        self._items[key] = (time.monotonic() + CACHE_TTL_S, value)
        self._items.move_to_end(key)
        while len(self._items) > CACHE_MAX:
            self._items.popitem(last=False)

    def clear(self) -> None:
        self._items.clear()


cache = _Cache()


@router.get("/weather", response_model=schemas.WeatherOut)
async def weather(
    request: Request,
    response: Response,
    session: Session,
    lat: Annotated[float, Query(ge=LAT_MIN, le=LAT_MAX)],
    lon: Annotated[float, Query(ge=LON_MIN, le=LON_MAX)],
) -> schemas.WeatherOut:
    await enforce(f"weather:{client_key(request)}", WEATHER_LIMIT, WEATHER_WINDOW_S)
    lat, lon = round(lat, 2), round(lon, 2)
    point = await service.nearest_point(session, lat, lon)
    if point is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "weather_unavailable")
    part = cache.get(point.id)
    if part is None:
        now = datetime.now(UTC)
        hour = now.replace(minute=0, second=0, microsecond=0)
        rows = await service.series_of(session, point.id, hour - timedelta(hours=3), hour + timedelta(hours=NEXT_HOURS))
        current = service.current_of(rows, now)
        if current is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "weather_unavailable")
        part = {
            "grid_point": {"lat": point.lat, "lon": point.lon},
            "updated_at": point.fetched_at,
            "current": service.hour_out(current),
            "hourly": [service.hour_out(o) for o in rows if o.at > current.at][:NEXT_HOURS],
            "simulated": point.simulated,
        }
        cache.put(point.id, part)
    alerts = [a for a in await notify.active_alerts(session, lat, lon, None) if a.category == "weather"]
    response.headers["Cache-Control"] = "public, max-age=60"
    return schemas.WeatherOut(
        location=schemas.Location(lat=lat, lon=lon),
        distance_km=service.distance_km(lat, lon, part["grid_point"]["lat"], part["grid_point"]["lon"]),
        alerts=alerts,
        attribution=service.attribution(part["simulated"]),
        **part,
    )
