"""Weather input of the priority score (BR-20 ``weather`` component, ai.scoring): kept free of the pipeline imports.

The report's nearest grid point (within WEATHER_MAX_DISTANCE_KM) at the current hour gives, by report type:
* fire: the fire danger class of the day (low 0 … extreme 1);
* flood: the heavy-rain level of the current and next 6 hours (none 0, watch 0.5, warning 1);
* any other type: the strongest wind gust of the current and next 3 hours (40 km/h → 0, 100 km/h → 1).
The component only raises a priority (ai.scoring.BONUS_COMPONENTS).
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports.domain import Category
from app.modules.weather.fwi import DANGER_RANK, FireDanger
from app.modules.weather.models import Observation
from app.modules.weather.service import nearest_point

RAIN_VALUES = {"none": 0.0, "watch": 0.5, "warning": 1.0}
GUST_FLOOR_KMH, GUST_CEILING_KMH = 40.0, 100.0


async def weather_signal(
    session: AsyncSession, category: Category, lat: float | None, lon: float | None, now: datetime | None = None
) -> tuple[float, dict[str, Any]] | None:
    if lat is None or lon is None:
        return None
    point = await nearest_point(session, lat, lon)
    if point is None:
        return None
    hour = (now or datetime.now(UTC)).replace(minute=0, second=0, microsecond=0)
    ahead = 6 if category is Category.FLOOD else 3
    rows = list(
        await session.scalars(
            select(Observation)
            .where(
                Observation.point_id == point.id,
                Observation.at >= hour,
                Observation.at <= hour + timedelta(hours=ahead),
            )
            .order_by(Observation.at)
        )
    )
    if not rows:
        return None
    detail: dict[str, Any] = {"point": {"lat": point.lat, "lon": point.lon}, "at": rows[0].at.isoformat()}
    if point.simulated:
        detail["simulated"] = True
    if category is Category.FIRE:
        danger = rows[0].fire_danger
        if danger is None:
            return None
        value = DANGER_RANK[FireDanger(danger)] / (len(FireDanger) - 1)
        return value, {**detail, "source": "fire_danger", "class": danger, "fwi": round(rows[0].fwi or 0.0, 1)}
    if category is Category.FLOOD:
        level = max((o.heavy_rain for o in rows), key=lambda lv: RAIN_VALUES[lv])
        rain_24h = max((o.precipitation_24h_mm or 0.0) for o in rows)
        return RAIN_VALUES[level], {**detail, "source": "heavy_rain", "level": level, "rain_24h_mm": rain_24h}
    gust = max((o.wind_gust_kmh or 0.0) for o in rows)
    value = min(max((gust - GUST_FLOOR_KMH) / (GUST_CEILING_KMH - GUST_FLOOR_KMH), 0.0), 1.0)
    return value, {**detail, "source": "wind_gust", "wind_gust_kmh": round(gust, 1)}
