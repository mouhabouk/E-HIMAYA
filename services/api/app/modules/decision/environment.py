"""Adapter from the weather layer and the spread forecasts (phase 7 §1–§2) to ``context.Environment``.

Weather: the nearest grid point with data (``weather.service.nearest_point``); the current hour's values, the latest
fire-danger class of the last 24 hours (the FWI system rates a day from its noon values) and the strongest heavy-rain
level from one hour ago to six hours ahead (a dispatcher plans for the coming rain, not only the current one).
Forecast: the incident's latest ``forecast.run``; its largest polygon gives the area and the alert geometry.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import any_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.decision.context import Environment, SpreadForecast, WeatherAtPoint
from app.modules.decision.domain import RAIN_LEVELS
from app.modules.forecast.models import ForecastRun
from app.modules.weather import service as weather
from app.modules.weather.models import AlertSuggestion

RAIN_AHEAD = timedelta(hours=6)
DANGER_BEHIND = timedelta(hours=24)


class PlatformEnvironment:
    async def weather_at(self, session: AsyncSession, lat: float, lon: float) -> WeatherAtPoint | None:
        point = await weather.nearest_point(session, lat, lon)
        if point is None:
            return None
        now = datetime.now(UTC)
        rows = await weather.series_of(session, point.id, now - DANGER_BEHIND, now + RAIN_AHEAD)
        current = weather.current_of(rows, now)
        if current is None:
            return None
        danger = next((o.fire_danger for o in reversed(rows) if o.at <= now and o.fire_danger), current.fire_danger)
        soon = [o.heavy_rain for o in rows if now - timedelta(hours=1) <= o.at <= now + RAIN_AHEAD]
        rain = max(soon, key=lambda level: RAIN_LEVELS.index(level) if level in RAIN_LEVELS else 0, default=None)
        return WeatherAtPoint(
            observed_at=current.at,
            wind_kmh=current.wind_speed_kmh,
            gust_kmh=current.wind_gust_kmh,
            wind_dir_deg=current.wind_direction_deg,
            temperature_c=current.temperature_c,
            humidity_pct=current.relative_humidity_pct,
            rain_1h_mm=current.precipitation_mm,
            rain_24h_mm=current.precipitation_24h_mm,
            fire_danger=danger,
            rain_level=rain or current.heavy_rain,
            simulated=bool(point.simulated),
        )

    async def latest_forecast(self, session: AsyncSession, incident_id: uuid.UUID) -> SpreadForecast | None:
        run = await session.scalar(
            select(ForecastRun)
            .where(ForecastRun.incident_id == incident_id)
            .order_by(ForecastRun.created_at.desc())
            .limit(1)
        )
        if run is None:
            return None
        result: dict[str, Any] = run.result or {}
        polygons = [p for p in result.get("polygons") or [] if isinstance(p, dict)]
        largest = max(polygons, key=lambda p: float(p.get("area_ha") or 0), default=None)
        geometry = largest.get("geojson") if largest else None
        if isinstance(geometry, dict) and geometry.get("type") == "Feature":
            geometry = geometry.get("geometry")
        rate = result.get("rate_of_spread_m_min")
        return SpreadForecast(
            forecast_id=str(run.id),
            kind=run.kind,
            generated_at=run.created_at,
            max_area_ha=float(largest["area_ha"]) if largest and largest.get("area_ha") is not None else None,
            horizon_min=int(largest["minutes"]) if largest and largest.get("minutes") is not None else None,
            level=result.get("level") or (largest.get("level") if largest else None),
            rate_of_spread_m_min=float(rate) if rate is not None else None,
            geometry=geometry if isinstance(geometry, dict) else None,
            simulated=bool(run.simulated),
        )

    async def pending_weather_suggestions(self, session: AsyncSession, gouvernorat_code: int) -> int:
        count = await session.scalar(
            select(func.count()).where(
                AlertSuggestion.status == "pending",
                AlertSuggestion.valid_until > func.now(),
                any_(AlertSuggestion.gouvernorat_codes) == gouvernorat_code,
            )
        )
        return int(count or 0)


_default = PlatformEnvironment()


def default_environment() -> Environment:
    return _default
