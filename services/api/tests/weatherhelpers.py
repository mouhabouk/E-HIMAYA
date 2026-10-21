"""Weather fixtures shared by test_weather.py and test_forecast.py: the grid filled by the simulator (or a scripted
provider), and a clean slate afterwards so other tests' priority scores never see weather data."""

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import get_system_sessionmaker
from app.modules.forecast import terrain
from app.modules.weather import provider, router
from app.modules.weather.provider import Hour, Series, SimProvider


class ScriptedProvider:
    """Every point gets the same hourly values, from ``values(at) -> dict``."""

    name = "scripted"
    simulated = True

    def __init__(self, values: Callable[[datetime], dict[str, Any]]) -> None:
        self.values = values
        self.calls: list[tuple[int, int, int]] = []

    def attribution(self) -> dict[str, str] | str:
        return "scripted test weather"

    async def fetch(self, points: list[tuple[float, float]], past_days: int, forecast_days: int) -> list[Series]:
        self.calls.append((len(points), past_days, forecast_days))
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        start = now.replace(hour=0) - timedelta(days=past_days)
        hours = 24 * (past_days + forecast_days)
        base = {
            "temperature_c": 25.0,
            "relative_humidity_pct": 50.0,
            "wind_speed_kmh": 10.0,
            "wind_gust_kmh": 20.0,
            "wind_direction_deg": 270.0,
            "precipitation_mm": 0.0,
            "weather_code": 1,
        }
        series = []
        for lat, lon in points:
            series.append(
                Series(
                    lat,
                    lon,
                    [
                        Hour(at=start + timedelta(hours=h), **{**base, **self.values(start + timedelta(hours=h))})
                        for h in range(hours)
                    ],
                )
            )
        return series


async def clear_weather() -> None:
    async with get_system_sessionmaker()() as s, s.begin():
        await s.execute(text("DELETE FROM weather.alert_suggestion"))
        await s.execute(text("DELETE FROM weather.observation"))
        await s.execute(text("DELETE FROM weather.grid_point"))
        await s.execute(text("DELETE FROM weather.rule WHERE gouvernorat_code IS NOT NULL"))
        await s.execute(
            text(
                "UPDATE weather.rule SET threshold = d.t, severity = d.s, enabled = true FROM (VALUES "
                "('fire_danger', 3, 'medium'), ('wind_gust', 70, 'medium'), ('rain_24h', 50, 'medium'), "
                "('rain_1h', 20, 'high')) AS d(m, t, s) WHERE metric = d.m AND gouvernorat_code IS NULL"
            )
        )
    router.cache.clear()


@pytest.fixture
async def weather_env(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Fast settings (whole grid in one cycle, 2 days of spin-up) and a clean weather schema around the test."""
    settings = get_settings()
    monkeypatch.setattr(settings, "weather_max_points_per_cycle", 2000)
    monkeypatch.setattr(settings, "weather_spinup_days", 2)
    await clear_weather()
    yield
    await clear_weather()
    provider.set_provider(None)
    terrain.set_terrain(None)


async def seed_grid(*, keep: tuple[float, float, float, float] = (34.5, 9.8, 37.0, 11.0)) -> int:
    """Lay the grid, then keep only the points in (min_lat, min_lon, max_lat, max_lon) (Tunis to Sfax) to stay fast."""
    from app.modules.weather import service

    async with get_system_sessionmaker()() as s, s.begin():
        await service.ensure_grid(s)
        min_lat, min_lon, max_lat, max_lon = keep
        await s.execute(
            text("DELETE FROM weather.grid_point WHERE NOT (lat BETWEEN :a AND :c AND lon BETWEEN :b AND :d)"),
            {"a": min_lat, "b": min_lon, "c": max_lat, "d": max_lon},
        )
        return int((await s.execute(text("SELECT count(*) FROM weather.grid_point"))).scalar_one())


async def refresh(source: Any = None) -> dict[str, int]:
    from app.modules.weather import service

    await seed_grid()
    return await service.refresh(get_system_sessionmaker(), source or SimProvider())


@pytest.fixture
async def sim_grid(weather_env: None) -> dict[str, int]:
    return await refresh()


class PlaneTerrain:
    """Test terrain: z = base + slope_east·x + slope_north·y (metres), optionally a bowl."""

    source = "test"
    attribution = "test terrain"

    def __init__(self, lat0: float, lon0: float, east: float = 0.0, north: float = 0.0, bowl: float = 0.0) -> None:
        self.lat0, self.lon0, self.east, self.north, self.bowl = lat0, lon0, east, north, bowl

    def elevation(self, lat: float, lon: float) -> float | None:
        import math

        y = (lat - self.lat0) * 111_320.0
        x = (lon - self.lon0) * 111_320.0 * math.cos(math.radians(self.lat0))
        return 100.0 + self.east * x + self.north * y + self.bowl * (x * x + y * y) / 1000.0
