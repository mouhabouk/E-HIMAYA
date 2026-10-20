"""Phase 7 §1: weather layer — FWI System against its published reference values, derived levels, Open-Meteo client,
simulator, grid refresh, public card, staff layer, suggested alerts, rules and the weather priority component."""

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_sessionmaker
from app.modules.ai import scoring
from app.modules.ai.settings import PrioritySettings
from app.modules.notify.schemas import MessageIn
from app.modules.reports.domain import Category
from app.modules.reports.live import _route
from app.modules.weather import fwi, indices, provider, service
from app.modules.weather.provider import Hour, OpenMeteoProvider, SimProvider, WeatherRateLimited, WeatherUnavailable
from app.modules.weather.texts import suggestion_texts
from tests.conftest import SFAX, TUNIS, accept_charter, device_headers, outbox_events, report_body
from tests.weatherhelpers import ScriptedProvider, refresh, sim_grid, weather_env

__all__ = ["sim_grid", "weather_env"]  # fixtures
Staff = Callable[..., dict[str, str]]

# Wang, Anderson and Suddaby (2015), NOR-X-424, Table 7 "Sample of input data and result output" (the test data of
# Van Wagner and Pickett 1985): month day temp rh wind rain → FFMC DMC DC ISI BUI FWI, start-up 85 / 6 / 15.
TABLE_7 = """
4 13 17.0 42 25 0.0 87.7 8.5 19.0 10.9 8.5 10.1
4 14 20.0 21 25 2.4 86.2 10.4 23.6 8.8 10.4 9.3
4 15 8.5 40 17 0.0 87.0 11.8 26.1 6.5 11.7 7.6
4 16 6.5 25 6 0.0 88.8 13.2 28.2 4.9 13.1 6.2
4 17 13.0 34 24 0.0 89.1 15.4 31.5 12.6 15.3 14.8
4 18 6.0 40 22 0.4 88.7 16.5 33.5 10.7 16.4 13.5
4 19 5.5 52 6 0.0 87.4 17.2 35.4 4.0 17.1 5.9
4 20 8.5 46 16 0.0 87.4 18.5 37.9 6.6 18.4 9.7
4 21 9.5 54 20 0.0 86.8 19.7 40.6 7.4 19.6 11.0
4 22 7.0 93 14 9.0 29.9 10.1 29.5 0.0 10.9 0.0
4 23 6.5 71 17 1.0 49.4 10.7 31.6 0.4 11.6 0.2
4 24 6.0 59 17 0.0 67.3 11.4 33.7 1.3 12.3 0.9
4 25 13.0 52 4 0.0 77.8 13.0 37.0 1.1 13.9 0.8
4 26 15.5 40 11 0.0 85.5 15.4 40.7 3.9 15.9 5.5
4 27 23.0 25 9 0.0 91.5 19.8 45.8 8.4 19.8 12.2
4 28 19.0 46 16 0.0 89.9 22.5 50.2 9.5 22.4 14.3
4 29 18.0 41 20 0.0 90.0 25.2 54.4 11.7 25.1 17.7
4 30 14.5 51 16 0.0 88.4 27.0 57.9 7.7 27.0 13.3
5 1 14.5 69 11 0.0 85.7 28.3 63.0 4.0 28.2 8.0
5 2 15.5 42 8 0.0 87.4 30.8 68.2 4.4 30.8 9.1
5 3 21.0 37 8 0.0 89.4 34.5 74.3 5.9 34.4 12.3
5 4 23.0 32 16 0.0 91.0 38.8 80.9 11.1 38.7 21.0
5 5 23.0 32 14 0.0 91.2 43.1 87.4 10.3 43.0 21.1
5 6 27.0 33 12 0.0 91.7 48.1 94.7 9.9 47.9 21.7
5 7 28.0 17 27 0.0 95.2 54.5 102.1 34.5 54.3 52.6
5 8 23.5 54 20 0.0 89.7 57.4 108.8 11.3 57.2 25.9
5 9 16.0 50 22 12.2 62.2 29.9 91.8 1.4 33.0 3.0
5 10 11.5 58 20 0.0 76.7 31.3 96.3 2.3 34.5 5.4
5 11 16.0 54 16 0.0 83.5 33.4 101.6 3.8 36.7 8.9
5 12 21.5 37 9 0.0 88.7 37.1 107.8 5.6 39.9 12.8
5 13 14.0 61 22 0.2 86.7 38.7 112.8 8.1 41.6 17.3
5 14 15.0 30 27 0.0 89.6 41.7 117.9 15.9 44.2 28.8
5 15 20.0 23 11 0.0 92.1 45.9 123.9 10.1 47.7 21.9
5 16 14.0 95 3 16.4 21.3 20.1 97.0 0.0 26.5 0.0
5 17 20.0 53 4 2.8 51.0 18.3 103.0 0.2 25.3 0.2
5 18 19.5 30 16 0.0 82.3 22.1 108.9 3.3 29.3 6.8
5 19 25.5 51 20 6.0 75.4 16.4 106.4 2.1 23.7 3.8
5 20 10.0 38 24 0.0 84.3 18.2 110.6 6.4 25.8 11.3
5 21 19.0 27 16 0.0 90.3 22.1 116.4 10.0 29.9 17.2
5 22 26.0 46 11 4.2 77.6 18.7 117.7 1.6 26.8 2.9
5 23 30.0 38 22 0.0 90.2 23.8 125.5 13.4 32.3 22.0
5 24 25.5 67 19 12.6 65.3 13.1 108.5 1.4 20.2 1.9
5 25 12.0 53 28 11.8 55.4 7.7 91.6 1.2 12.8 0.8
5 26 21.0 38 8 0.0 80.8 11.3 97.8 1.9 17.6 2.6
5 27 13.0 70 20 3.8 61.7 8.4 97.9 1.2 13.8 0.9
5 28 9.0 78 24 1.4 64.5 9.0 101.9 1.7 14.7 2.0
5 29 11.0 54 16 0.0 77.6 10.5 106.3 2.0 16.8 2.8
5 30 15.5 39 9 0.0 85.4 13.1 111.5 3.5 20.3 5.8
5 31 18.0 36 5 0.0 88.5 16.3 117.1 4.4 24.2 7.9
"""


# ---------------------------------------------------------------- FWI System (pure)


def test_fwi_reproduces_the_published_reference_table() -> None:
    codes = fwi.Codes()
    rows = [line.split() for line in TABLE_7.strip().splitlines()]
    assert len(rows) == 49
    for row in rows:
        month, day = int(row[0]), int(row[1])
        temp, rh, wind, rain, *expected = map(float, row[2:])
        result = fwi.daily(codes, temp, rh, wind, rain, month, lat=46.0)
        codes = result.codes
        got = [result.ffmc, result.dmc, result.dc, result.isi, result.bui, result.fwi]
        assert [round(v, 1) for v in got] == expected, (month, day, got)


def test_fwi_components_and_classes() -> None:
    # Eq. 1 and Eq. 10 are inverse of each other.
    assert fwi.ffmc_to_moisture(85.0) == pytest.approx(147.2 * 16 / 144.5)
    # Day-length tables: Tunisia (> 30° N) uses the 46° N table, the far south the 20° N one.
    assert fwi.duff_moisture_code(10, 30, 20, 0, 7, lat=36) > fwi.duff_moisture_code(10, 30, 20, 0, 7, lat=25)
    assert fwi.buildup_index(0, 0) == 0
    assert fwi.danger_class(0) is fwi.FireDanger.LOW
    assert fwi.danger_class(5.2) is fwi.FireDanger.MODERATE
    assert fwi.danger_class(11.2) is fwi.FireDanger.HIGH
    assert fwi.danger_class(21.3) is fwi.FireDanger.VERY_HIGH
    assert fwi.danger_class(38.0) is fwi.FireDanger.EXTREME
    # Out-of-range inputs are clamped, never raise.
    assert fwi.daily(fwi.Codes(), -10, 120, -5, -1, 1).fwi >= 0


def test_heavy_rain_levels() -> None:
    assert indices.heavy_rain_level(None, None) == "none"
    assert indices.heavy_rain_level(10, 0) == "watch"
    assert indices.heavy_rain_level(2, 30) == "watch"
    assert indices.heavy_rain_level(20, 0) == "warning"
    assert indices.heavy_rain_level(0, 50) == "warning"


def _hour(at: datetime, **values: float) -> Hour:
    base: dict[str, Any] = {
        "temperature_c": 30.0,
        "relative_humidity_pct": 20.0,
        "wind_speed_kmh": 20.0,
        "wind_gust_kmh": 30.0,
        "wind_direction_deg": 0.0,
        "precipitation_mm": 0.0,
        "weather_code": 0,
    }
    return Hour(at=at, **{**base, **values})


def test_daily_indices_come_from_noon_and_carry_over() -> None:
    start = datetime(2026, 7, 1, tzinfo=UTC)
    hours = [_hour(start + timedelta(hours=h), precipitation_mm=1.0 if h < 24 else 0.0) for h in range(72)]
    now = start + timedelta(hours=40)  # 2 July 16:00 UTC: the noons of 1 and 2 July are past
    result = indices.compute(hours, 36.8, None, None, now)
    assert set(result.daily) == {date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3)}
    assert result.last_past_date == date(2026, 7, 2)
    assert result.last_past == result.daily[date(2026, 7, 2)]
    # 24 h totals appear once 24 hours of history are known; 24 x 1 mm.
    assert result.rows[22].precipitation_24h_mm is None
    assert result.rows[23].precipitation_24h_mm == 24.0
    assert result.rows[23].heavy_rain == "none"
    # Every hour of a local day carries that day's indices (local midnight is 23:00 UTC).
    assert result.rows[30].indices == result.daily[date(2026, 7, 2)]
    assert result.rows[23].indices == result.daily[date(2026, 7, 2)]
    # The next fetch starts from the folded day and does not fold it again.
    again = indices.compute(hours, 36.8, result.last_past, result.last_past_date, now)
    assert again.daily[date(2026, 7, 2)] == result.daily[date(2026, 7, 2)]
    assert again.last_past is None
    # Dry, hot and windy: high danger after a few days.
    assert result.daily[date(2026, 7, 3)].fwi > result.daily[date(2026, 7, 1)].fwi


# ---------------------------------------------------------------- providers


def test_simulator_is_deterministic_and_plausible() -> None:
    at = datetime(2026, 7, 15, 12, tzinfo=UTC)
    first = provider.simulated_hour(36.8, 10.2, at)
    assert first == provider.simulated_hour(36.8, 10.2, at)
    hours = [provider.simulated_hour(lat, lon, at + timedelta(hours=h)) for lat in (31, 37) for lon in (8, 11)
             for h in range(0, 24 * 14, 5)]  # fmt: skip
    assert all(0 <= (h.relative_humidity_pct or 0) <= 100 for h in hours)
    assert all(-5 < (h.temperature_c or 0) < 55 for h in hours)
    assert any((h.precipitation_mm or 0) > 0 for h in hours)  # a storm day falls within any two weeks
    assert provider.SimProvider.simulated is True


async def test_simulator_series_covers_past_and_forecast() -> None:
    now = datetime(2026, 7, 15, 10, 30, tzinfo=UTC)
    series = await SimProvider(now=now).fetch([(36.8, 10.2), (34.7, 10.7)], past_days=1, forecast_days=3)
    assert [len(s.hours) for s in series] == [96, 96]
    assert series[0].hours[0].at == datetime(2026, 7, 14, tzinfo=UTC)


def _open_meteo_answer(points: int) -> list[dict[str, Any]]:
    t0 = int(datetime(2026, 7, 15, tzinfo=UTC).timestamp())
    times = [t0 + 3600 * h for h in range(4)]
    hourly = {
        "time": times,
        "temperature_2m": [20.0, 21.5, None, 23.0],
        "relative_humidity_2m": [50, 48, 47, 45],
        "precipitation": [0.0, 0.2, 0.0, 0.0],
        "wind_speed_10m": [10.0, 12.0, 14.0, 16.0],
        "wind_gusts_10m": [20.0, 22.0, 24.0, 26.0],
        "wind_direction_10m": [270, 280, 290, 300],
        "weather_code": [0, 1, 2, 3],
    }
    return [{"latitude": 36.75 + i, "longitude": 10.25, "hourly": hourly} for i in range(points)]


async def test_open_meteo_client_batches_and_parses() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_open_meteo_answer(2))

    client = OpenMeteoProvider("https://api.open-meteo.test/", "key-1", 5.0, transport=httpx.MockTransport(handler))
    series = await client.fetch([(36.75, 10.25), (37.75, 10.25)], past_days=1, forecast_days=3)
    params = seen[0].url.params
    assert seen[0].url.path == "/v1/forecast"
    assert params["latitude"] == "36.7500,37.7500" and params["longitude"] == "10.2500,10.2500"
    assert params["past_days"] == "1" and params["forecast_days"] == "3" and params["timezone"] == "GMT"
    assert params["wind_speed_unit"] == "kmh" and params["apikey"] == "key-1"
    assert len(params["hourly"].split(",")) == 7  # ≤ 10 variables: one API call per location
    assert len(series) == 2 and series[0].hours[1].temperature_c == 21.5 and series[0].hours[2].temperature_c is None
    assert series[0].hours[0].at == datetime(2026, 7, 15, tzinfo=UTC)
    assert client.attribution() == {
        "text": "Weather data by Open-Meteo.com",
        "url": "https://open-meteo.com/",
        "licence": "CC BY 4.0",
    }


async def test_open_meteo_client_failures() -> None:
    calls = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503)

    client = OpenMeteoProvider("https://x.test", None, 5.0, transport=httpx.MockTransport(flaky), retry_pause_s=0)
    with pytest.raises(WeatherUnavailable, match="http_503"):
        await client.fetch([(36.0, 10.0)], 1, 3)
    assert calls["n"] == 3  # three attempts with back-off

    too_many = httpx.MockTransport(lambda r: httpx.Response(429))
    limited = OpenMeteoProvider("https://x.test", None, 5.0, transport=too_many)
    with pytest.raises(WeatherRateLimited):
        await limited.fetch([(36.0, 10.0)], 1, 3)

    one_answer = httpx.MockTransport(lambda r: httpx.Response(200, json=_open_meteo_answer(1)))
    wrong = OpenMeteoProvider("https://x.test", None, 5.0, transport=one_answer)
    with pytest.raises(WeatherUnavailable, match="location_count_mismatch"):
        await wrong.fetch([(36.0, 10.0), (35.0, 10.0)], 1, 3)

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    slow = OpenMeteoProvider("https://x.test", None, 5.0, transport=httpx.MockTransport(timeout), retry_pause_s=0)
    with pytest.raises(WeatherUnavailable, match="ConnectTimeout"):
        await slow.fetch([(36.0, 10.0)], 1, 3)


def test_provider_choice_follows_the_environment() -> None:
    from app.core.config import Settings

    base = {"database_url": "postgresql+asyncpg://u:p@h/db", "anon_pseudonym_secret": "x" * 32}
    key = "dGVzdC1rZXktdGVzdC1rZXktdGVzdC1rZXktMzJieXQ="
    development = Settings(_env_file=None, field_encryption_key=key, **base)  # type: ignore[call-arg]
    assert development.weather_source == "sim"
    chosen = Settings(_env_file=None, field_encryption_key=key, weather_provider="open-meteo", **base)  # type: ignore[call-arg]
    assert chosen.weather_source == "open-meteo"


# ---------------------------------------------------------------- refresh and endpoints


async def test_refresh_fills_the_grid_and_spins_up(sim_grid: dict[str, int], session: AsyncSession) -> None:
    assert sim_grid["fetched"] > 20 and sim_grid["failed"] == 0
    row = (
        await session.execute(
            text(
                "SELECT count(*) AS points, count(codes) AS spun_up, bool_and(simulated) AS simulated, "
                "count(DISTINCT gouvernorat_code) AS gouvernorats FROM weather.grid_point"
            )
        )
    ).one()
    assert row.points == sim_grid["fetched"] and row.spun_up == row.points and row.simulated
    assert row.gouvernorats >= 5
    span = (await session.execute(text("SELECT min(at), max(at), count(*) FROM weather.observation"))).one()
    now = datetime.now(UTC)
    assert span[0] >= now - timedelta(hours=31) and span[1] >= now + timedelta(hours=47)
    # Nothing is due again before WEATHER_FETCH_MIN_AGE_S.
    assert (await service.refresh(get_sessionmaker(), SimProvider()))["fetched"] == 0


async def test_refresh_survives_provider_failures(weather_env: None, session: AsyncSession) -> None:
    class Down:
        name, simulated = "down", False

        def attribution(self) -> str:
            return "down"

        async def fetch(self, points: list[tuple[float, float]], past: int, ahead: int) -> list[Any]:
            raise WeatherRateLimited("rate_limited")

    result = await refresh(Down())
    assert result["fetched"] == 0 and result["failed"] > 0
    row = (await session.execute(text("SELECT min(attempts), min(next_fetch_at) FROM weather.grid_point"))).one()
    assert row[0] == 1 and row[1] > datetime.now(UTC)


async def test_public_weather_card(client: httpx.AsyncClient, sim_grid: dict[str, int]) -> None:
    r = await client.get("/api/v1/weather", params={"lat": TUNIS["lat"], "lon": TUNIS["lon"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert r.headers["Cache-Control"] == "public, max-age=60"
    assert body["location"] == {"lat": 36.81, "lon": 10.18}
    assert body["simulated"] is True and body["attribution"].startswith("[SIM]")
    assert body["distance_km"] < 25 and body["updated_at"]
    assert isinstance(body["alerts"], list)
    current = body["current"]
    for key in (
        "time",
        "temperature_c",
        "wind_speed_kmh",
        "wind_gust_kmh",
        "wind_direction_deg",
        "relative_humidity_pct",
        "precipitation_mm_h",
        "precipitation_24h_mm",
        "weather_code",
    ):
        assert key in current, key
    assert current["fire_danger"]["class"] in ("low", "moderate", "high", "very_high", "extreme")
    assert current["fire_danger"]["fwi"] >= 0
    assert current["heavy_rain"]["level"] in ("none", "watch", "warning")
    assert 1 <= len(body["hourly"]) <= 12
    times = [current["time"]] + [h["time"] for h in body["hourly"]]
    assert times == sorted(times) and len(set(times)) == len(times)

    # Outside the covered grid: no data. Outside Tunisia: rejected.
    r = await client.get("/api/v1/weather", params={"lat": 31.0, "lon": 8.0})
    assert r.status_code == 503 and r.json()["detail"] == "weather_unavailable"
    r = await client.get("/api/v1/weather", params={"lat": 45.0, "lon": 10.0})
    assert r.status_code == 422


async def test_public_weather_card_lists_weather_alerts(
    client: httpx.AsyncClient, sim_grid: dict[str, int], staff: Staff
) -> None:
    editor = staff(["central_committee"], gouvernorat=None)
    draft = {
        "kind": "alert",
        "title": {"ar": "رياح قوية", "fr": "Vents violents"},
        "body": {"ar": "هبوب رياح قوية", "fr": "Rafales"},
        "severity": "medium",
        "category": "weather",
        "hazard": "wind",
        "expires_at": (datetime.now(UTC) + timedelta(hours=6)).isoformat(),
        "area": {"gouvernorat_codes": [11]},
    }
    r = await client.post("/api/v1/staff/notifications", json=draft, headers=editor)
    assert r.status_code == 201, r.text
    message_id = r.json()["id"]
    r = await client.post(f"/api/v1/staff/notifications/{message_id}/publish", headers=editor)
    assert r.status_code == 200, r.text
    try:
        body = (await client.get("/api/v1/weather", params={"lat": TUNIS["lat"], "lon": TUNIS["lon"]})).json()
        assert message_id in [a["id"] for a in body["alerts"]]
        assert all(a["category"] == "weather" for a in body["alerts"])
        sfax = (await client.get("/api/v1/weather", params={"lat": 34.75, "lon": 10.75})).json()
        assert message_id not in [a["id"] for a in sfax["alerts"]]
    finally:
        await client.post(f"/api/v1/staff/notifications/{message_id}/cancel", headers=editor)


async def test_public_weather_is_rate_limited(client: httpx.AsyncClient, sim_grid: dict[str, int]) -> None:
    statuses = [
        (await client.get("/api/v1/weather", params={"lat": 36.8, "lon": 10.18})).status_code for _ in range(61)
    ]
    assert statuses[:60] == [200] * 60 and statuses[60] == 429


async def test_staff_grid_and_point(client: httpx.AsyncClient, sim_grid: dict[str, int], staff: Staff) -> None:
    r = await client.get("/api/v1/staff/weather/grid", params={"bbox": "10.0,36.5,10.5,37.0"}, headers=staff())
    assert r.status_code == 200, r.text
    layer = r.json()
    assert layer["type"] == "FeatureCollection" and layer["simulated"] is True
    assert layer["features"] and all(
        10.0 <= f["geometry"]["coordinates"][0] <= 10.5 and 36.5 <= f["geometry"]["coordinates"][1] <= 37.0
        for f in layer["features"]
    )
    props = layer["features"][0]["properties"]
    assert {"wind_speed_kmh", "fire_danger", "heavy_rain", "rain_level", "fwi", "point_id", "gouvernorat_code"} <= set(
        props
    )
    assert props["fire_danger"] in {d.value for d in fwi.FireDanger} and props["rain_level"] == props["heavy_rain"]
    ahead = (await client.get("/api/v1/staff/weather/grid", params={"hour": 24}, headers=staff())).json()
    assert ahead["hour"] > layer["hour"] and len(ahead["features"]) >= len(layer["features"])
    r = await client.get("/api/v1/staff/weather/grid", params={"bbox": "11,36,10,37"}, headers=staff())
    assert r.status_code == 422 and r.json()["detail"] == "invalid_bbox"

    r = await client.get("/api/v1/staff/weather/at", params={"lat": 36.8, "lon": 10.18}, headers=staff())
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["point"]["gouvernorat_code"] is not None
    assert 40 <= len(detail["hourly"]) <= 48 and len(detail["past"]) >= 20
    assert (detail["lat"], detail["lon"]) == (detail["point"]["lat"], detail["point"]["lon"])
    assert detail["alerts"] == [] and detail["current"]["fire_danger"]["class"]

    citizen_like = {"Authorization": staff()["Authorization"]}
    assert (await client.get("/api/v1/staff/weather/grid", headers=citizen_like)).status_code == 200
    assert (await client.get("/api/v1/staff/weather/grid")).status_code == 401
    # Phase 9 §1.1: technical roles hold no operational picture.
    sysadmin = staff(roles=["sysadmin"], gouvernorat=None)
    assert (await client.get("/api/v1/staff/weather/grid", headers=sysadmin)).status_code == 403


# ---------------------------------------------------------------- suggested alerts


def _gale(at: datetime) -> dict[str, Any]:
    return {"wind_gust_kmh": 95.0, "wind_speed_kmh": 50.0, "relative_humidity_pct": 95.0, "temperature_c": 12.0}


async def test_rules_create_suggestions_once_and_humans_decide(
    client: httpx.AsyncClient, weather_env: None, staff: Staff, session: AsyncSession
) -> None:
    result = await refresh(ScriptedProvider(_gale))
    assert result["suggestions"] == 1
    suggestion = (await session.execute(text("SELECT * FROM weather.alert_suggestion"))).mappings().one()
    assert suggestion["metric"] == "wind_gust" and suggestion["status"] == "pending"
    assert suggestion["severity"] == "medium" and suggestion["hazard"] == "wind"
    codes = list(suggestion["gouvernorat_codes"])
    assert 11 in codes and 61 in codes
    assert suggestion["evidence"]["max_value"] == 95.0 and suggestion["evidence"]["thresholds"]["11"] == 70.0
    assert "95" in suggestion["body"]["ar"] and "95 km/h" in suggestion["body"]["fr"] and suggestion["body"]["en"]
    events = await outbox_events(session, "weather.suggestion")
    assert any(e.get("suggestion_id") == e["suggestion"]["id"] == str(suggestion["id"]) for e in events)
    assert suggestion["evidence"]["wind_gust"] == 95.0

    # The next cycle does not suggest the same thing again.
    await session.execute(text("UPDATE weather.grid_point SET next_fetch_at = now() - interval '1 minute'"))
    await session.commit()
    assert (await refresh(ScriptedProvider(_gale)))["suggestions"] == 0

    national, sfax_editor, operator = staff(["content_editor"], gouvernorat=None), staff(["content_editor"]), staff()
    listed = (await client.get("/api/v1/staff/weather/suggestions", headers=national)).json()["items"]
    assert [s["id"] for s in listed] == [str(suggestion["id"])]
    assert (await client.get("/api/v1/staff/weather/suggestions", headers=sfax_editor)).json()["items"]
    elsewhere = staff(["content_editor"], gouvernorat=81)
    assert (await client.get("/api/v1/staff/weather/suggestions", headers=elsewhere)).json()["items"] == []
    assert (await client.get("/api/v1/staff/weather/suggestions", headers=operator)).status_code == 403

    url = f"/api/v1/staff/weather/suggestions/{suggestion['id']}"
    r = await client.post(f"{url}/accept", headers=elsewhere)
    assert r.status_code == 404
    messages = text("SELECT count(*) FROM notify.message")
    before = await session.scalar(messages)
    r = await client.post(f"{url}/accept", headers=sfax_editor)
    assert r.status_code == 200, r.text
    accepted = r.json()
    assert accepted["suggestion"]["status"] == "accepted"
    form = MessageIn.model_validate(accepted["alert_form"])
    assert form.kind == "alert" and form.category == "weather" and form.hazard == "wind"
    assert form.area.gouvernorat_codes == [61]  # a local editor's alert covers their gouvernorat only
    # Nothing was sent: no alert exists until the editor creates and publishes it.
    assert await session.scalar(messages) == before
    assert (await client.post(f"{url}/accept", headers=national)).status_code == 409
    audit_row = await session.scalar(
        text("SELECT action FROM audit.log WHERE target = :t ORDER BY seq DESC LIMIT 1"),
        {"t": f"weather_suggestion:{suggestion['id']}"},
    )
    assert audit_row == "weather.suggestion.accept"


async def test_dismiss_needs_a_reason(
    client: httpx.AsyncClient, weather_env: None, staff: Staff, session: AsyncSession
) -> None:
    def downpour(at: datetime) -> dict[str, Any]:
        return {"precipitation_mm": 25.0, "relative_humidity_pct": 95.0}

    result = await refresh(ScriptedProvider(downpour))
    metrics = set((await session.execute(text("SELECT metric FROM weather.alert_suggestion"))).scalars())
    assert result["suggestions"] == 2 and metrics == {"rain_1h", "rain_24h"}
    one = await session.scalar(text("SELECT id FROM weather.alert_suggestion WHERE metric = 'rain_1h'"))
    editor = staff(["central_committee"], gouvernorat=None)
    url = f"/api/v1/staff/weather/suggestions/{one}/dismiss"
    assert (await client.post(url, json={"reason": ""}, headers=editor)).status_code == 422
    r = await client.post(url, json={"reason": "Déjà couvert par l'alerte INM"}, headers=editor)
    assert r.status_code == 200 and r.json()["status"] == "dismissed" and r.json()["dismiss_reason"]
    assert (await client.post(url, json={"reason": "encore"}, headers=editor)).status_code == 409


async def test_rules_per_gouvernorat(client: httpx.AsyncClient, weather_env: None, staff: Staff) -> None:
    sfax = staff(["local_committee"])
    rules = (await client.get("/api/v1/staff/weather/rules", headers=sfax)).json()
    assert {r["metric"] for r in rules if r["gouvernorat_code"] is None} == {
        "fire_danger",
        "wind_gust",
        "rain_24h",
        "rain_1h",
    }
    own = {"gouvernorat_code": 61, "rules": [{"metric": "wind_gust", "threshold": 120, "severity": "high"}]}
    r = await client.put("/api/v1/staff/weather/rules", json=own, headers=sfax)
    assert r.status_code == 200, r.text
    assert any(x["gouvernorat_code"] == 61 and x["threshold"] == 120 for x in r.json())
    other = {**own, "gouvernorat_code": 11}
    assert (await client.put("/api/v1/staff/weather/rules", json=other, headers=sfax)).status_code == 403
    national = {"gouvernorat_code": None, "rules": own["rules"]}
    assert (await client.put("/api/v1/staff/weather/rules", json=national, headers=sfax)).status_code == 403
    central = staff(["central_committee"], gouvernorat=None)
    r = await client.put("/api/v1/staff/weather/rules", json=national, headers=central)
    assert r.status_code == 422 and r.json()["detail"] == "national_rules_incomplete"
    bad = {"gouvernorat_code": 61, "rules": [{"metric": "fire_danger", "threshold": 2.5, "severity": "high"}]}
    assert (await client.put("/api/v1/staff/weather/rules", json=bad, headers=sfax)).status_code == 422

    # Sfax's own threshold (120 km/h) wins over the national 70 km/h: a 95 km/h gale is suggested elsewhere only.
    await refresh(ScriptedProvider(_gale))
    async with get_sessionmaker()() as s:
        codes = (await s.execute(text("SELECT gouvernorat_codes FROM weather.alert_suggestion"))).scalar_one()
    assert 61 not in codes and 11 in codes


def test_live_feed_routes_suggestions_to_editors_in_scope() -> None:
    route = _route("weather.suggestion", {"suggestion": {"gouvernorat_codes": [11, 12]}})
    assert route is not None and route[0] == "editors"


# ---------------------------------------------------------------- priority component (BR-20)


def test_weather_component_is_a_bonus() -> None:
    settings = PrioritySettings()
    base = scoring.Facts(category=Category.FIRE, reporter_kind="citizen")
    without = scoring.priority(base, 60, settings)
    weather = {c["key"]: c for c in without["components"]}["weather"]
    assert weather["value"] is None and weather["detail"] == {"reason": "no_weather_data"}
    calm = scoring.priority(
        scoring.Facts(category=Category.FIRE, reporter_kind="citizen", weather=(0.0, {"class": "low"})), 60, settings
    )
    assert calm["score"] == without["score"]
    extreme = scoring.priority(
        scoring.Facts(category=Category.FIRE, reporter_kind="citizen", weather=(1.0, {"class": "extreme"})),
        60,
        settings,
    )
    assert extreme["score"] > without["score"]


async def test_reports_are_scored_with_the_weather(
    client: httpx.AsyncClient, sim_grid: dict[str, int], staff: Staff, session: AsyncSession
) -> None:
    await session.execute(text("UPDATE weather.observation SET fire_danger = 'extreme', fwi = 55, wind_gust_kmh = 100"))
    await session.commit()
    headers = device_headers()
    await accept_charter(client, headers)
    reports = {}
    for category in ("fire", "traffic_accident"):
        r = await client.post("/api/v1/reports", json=report_body(SFAX, category=category), headers=headers)
        assert r.status_code == 201, r.text
        reports[category] = r.json()["id"]
    for category, source in (("fire", "fire_danger"), ("traffic_accident", "wind_gust")):
        detail = (await client.get(f"/api/v1/staff/reports/{reports[category]}", headers=staff())).json()
        components = {c["key"]: c for c in detail["analysis"]["priority"]["components"]}
        assert components["weather"]["value"] == 1.0, components["weather"]
        assert components["weather"]["detail"]["source"] == source
        assert components["weather"]["points"] > 0


def test_suggestion_payload_is_json() -> None:
    start, end = datetime(2026, 7, 1, 10, tzinfo=UTC), datetime(2026, 7, 1, 18, tzinfo=UTC)
    title, body = suggestion_texts("fire_danger", 4, ["صفاقس"], ["Sfax"], start, end)
    assert title["fr"] == "Danger d'incendie extrême" and "198" in body["ar"] and "01/07 11:00" in body["fr"]
    assert json.dumps({"t": title, "b": body}, ensure_ascii=False)
