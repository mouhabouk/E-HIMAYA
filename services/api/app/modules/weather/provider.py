"""Where hourly weather comes from: the Open-Meteo forecast API (or a compatible server), or the simulator.

Open-Meteo (https://open-meteo.com, data licence CC BY 4.0, attribution shown wherever the data is shown): one
request carries up to WEATHER_BATCH_SIZE coordinates (each counts as one API call; 7 hourly variables and at most
14 days keep the weight at 1 call per location, past_days for a spin-up counts more). Timeouts, three attempts with
back-off on network errors and 5xx, and a 429 stops the cycle (the points are retried later): a failure never blocks
anything, the last stored values stay in use. WEATHER_API_URL points at a self-hosted Open-Meteo or a national (INM)
feed exposing the same /v1/forecast interface; WEATHER_API_KEY selects the commercial customer API.
"""

import asyncio
import hashlib
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import httpx
import structlog

from app.core.config import get_settings

log = structlog.get_logger()

HOURLY_VARIABLES = (
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "wind_gusts_10m",
    "wind_direction_10m",
    "weather_code",
)
OPEN_METEO_ATTRIBUTION = {
    "text": "Weather data by Open-Meteo.com",
    "url": "https://open-meteo.com/",
    "licence": "CC BY 4.0",
}
SIM_ATTRIBUTION = "[SIM] Simulated weather (e-Himaya simulator), not real data"
MAX_ATTEMPTS = 3


class WeatherUnavailable(Exception):
    """The provider failed for this batch (network, 5xx, malformed answer)."""


class WeatherRateLimited(WeatherUnavailable):
    """The provider answered 429: stop this cycle."""


@dataclass(frozen=True, slots=True)
class Hour:
    at: datetime
    temperature_c: float | None
    relative_humidity_pct: float | None
    wind_speed_kmh: float | None
    wind_gust_kmh: float | None
    wind_direction_deg: float | None
    precipitation_mm: float | None
    weather_code: int | None


@dataclass(frozen=True, slots=True)
class Series:
    lat: float
    lon: float
    hours: list[Hour]


class WeatherProvider(Protocol):
    name: str
    simulated: bool

    def attribution(self) -> dict[str, str] | str: ...

    async def fetch(self, points: list[tuple[float, float]], past_days: int, forecast_days: int) -> list[Series]:
        """Hourly series (UTC, whole hours) of each point, in the order given."""
        ...


def _num(values: list[Any] | None, i: int) -> float | None:
    if values is None or i >= len(values) or values[i] is None:
        return None
    return float(values[i])


def parse_open_meteo(payload: Any, expected: int) -> list[Series]:
    """Open-Meteo answers an object for one location and a list for several."""
    items = payload if isinstance(payload, list) else [payload]
    if len(items) != expected:
        raise WeatherUnavailable("location_count_mismatch")
    out: list[Series] = []
    for item in items:
        try:
            hourly = item["hourly"]
            times = hourly["time"]
            columns = {name: hourly.get(name) for name in HOURLY_VARIABLES}
            hours = [
                Hour(
                    at=datetime.fromtimestamp(int(t), UTC),
                    temperature_c=_num(columns["temperature_2m"], i),
                    relative_humidity_pct=_num(columns["relative_humidity_2m"], i),
                    wind_speed_kmh=_num(columns["wind_speed_10m"], i),
                    wind_gust_kmh=_num(columns["wind_gusts_10m"], i),
                    wind_direction_deg=_num(columns["wind_direction_10m"], i),
                    precipitation_mm=_num(columns["precipitation"], i),
                    weather_code=None if (code := _num(columns["weather_code"], i)) is None else int(code),
                )
                for i, t in enumerate(times)
            ]
            out.append(Series(lat=float(item["latitude"]), lon=float(item["longitude"]), hours=hours))
        except (KeyError, TypeError, ValueError) as exc:
            raise WeatherUnavailable("malformed_answer") from exc
    return out


class OpenMeteoProvider:
    name = "open-meteo"
    simulated = False

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        timeout_s: float,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_pause_s: float = 1.0,
    ) -> None:
        self._transport = transport
        self._retry_pause_s = retry_pause_s
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = httpx.Timeout(timeout_s, connect=min(timeout_s, 10.0))

    def attribution(self) -> dict[str, str] | str:
        return dict(OPEN_METEO_ATTRIBUTION)

    def _params(self, points: list[tuple[float, float]], past_days: int, forecast_days: int) -> dict[str, str]:
        params = {
            "latitude": ",".join(f"{lat:.4f}" for lat, _ in points),
            "longitude": ",".join(f"{lon:.4f}" for _, lon in points),
            "hourly": ",".join(HOURLY_VARIABLES),
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
            "timezone": "GMT",
            "timeformat": "unixtime",
            "past_days": str(past_days),
            "forecast_days": str(forecast_days),
        }
        if self._api_key:
            params["apikey"] = self._api_key
        return params

    async def fetch(self, points: list[tuple[float, float]], past_days: int, forecast_days: int) -> list[Series]:
        params = self._params(points, past_days, forecast_days)
        last_error = "unknown"
        headers = {"User-Agent": "e-Himaya/1.0 (civil protection, Tunisia)"}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers, transport=self._transport) as client:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    response = await client.get(f"{self._base_url}/v1/forecast", params=params)
                except httpx.HTTPError as exc:
                    last_error = type(exc).__name__
                else:
                    if response.status_code == 429:
                        raise WeatherRateLimited("rate_limited")
                    if response.status_code == 200:
                        try:
                            return parse_open_meteo(response.json(), len(points))
                        except ValueError as exc:
                            raise WeatherUnavailable("malformed_answer") from exc
                    last_error = f"http_{response.status_code}"
                    if response.status_code < 500:
                        break  # a 4xx will not get better by retrying
                if attempt < MAX_ATTEMPTS:
                    await asyncio.sleep(self._retry_pause_s * 2 ** (attempt - 1))
        raise WeatherUnavailable(last_error)


# ┏━━ SIMULATION ━━ deterministic weather simulator (WEATHER_PROVIDER=sim, the development default)
# ┃ A smooth climate (season, day/night cycle, south hotter and drier, north wetter) plus recurring episodes every few
# ┃ days, so the dashboard shows fire danger, wind and heavy rain levels and suggested alerts without any network:
# ┃ a sirocco (hot, dry, gusty) over the centre and north-west on days ≡ 2 (mod 5), a rain storm over the north-east
# ┃ on days ≡ 4 (mod 7). The same position and hour always give the same values (tests rely on it).
# ┃ PRODUCTION: WEATHER_PROVIDER=open-meteo (APP_ENV=production refuses sim), see docs/weather-forecast.md.
# ┗━━━━━━━━━━━━━━━━
def _noise(*parts: float) -> float:
    """Deterministic value in [-1, 1) from the given numbers."""
    digest = hashlib.blake2b(repr(parts).encode(), digest_size=4).digest()
    return int.from_bytes(digest, "big") / 2**31 - 1.0


def simulated_hour(lat: float, lon: float, at: datetime) -> Hour:
    day = at.toordinal()
    doy = at.timetuple().tm_yday
    local_hour = (at.hour + 1) % 24  # Africa/Tunis, UTC+1 all year
    south = max(37.3 - lat, 0.0)  # degrees south of the northern coast
    season = math.cos(2 * math.pi * (doy - 205) / 365.0)  # +1 late July, -1 late January
    mean_t = 19.0 + 8.5 * season + 0.55 * south
    diurnal = math.sin(2 * math.pi * (local_hour - 9) / 24.0)
    temp = mean_t + (5.0 + 0.4 * south) * diurnal + 1.5 * _noise(lat, lon, day)
    rh = 62.0 - 2.2 * south - 14.0 * diurnal - 10.0 * season + 6.0 * _noise(lon, lat, day)
    wind = 13.0 + 6.0 * max(diurnal, 0.0) + 5.0 * _noise(lat, day, local_hour // 6)
    direction = (300.0 + 40.0 * _noise(day, 7.0)) % 360.0
    rain = 0.0
    code = 1 if rh < 70 else 3

    sirocco = day % 5 == 2 and 33.5 <= lat <= 37.0 and lon <= 10.3
    if sirocco:
        temp += 9.0
        rh = min(rh, 18.0 + 4.0 * _noise(lat, lon, at.hour))
        wind = 38.0 + 10.0 * max(diurnal, 0.0)
        direction = 200.0
        code = 0
    storm = day % 7 == 4 and lat >= 35.8 and lon >= 9.6
    if storm and 6 <= local_hour <= 20:
        peak = math.exp(-(((local_hour - 14) / 3.0) ** 2))
        rain = round(26.0 * peak + 0.8, 1)
        rh = max(rh, 88.0)
        temp -= 4.0
        wind = 30.0 + 20.0 * peak
        direction = 20.0
        code = 65 if rain >= 7.6 else 63
    rh = min(max(rh, 5.0), 100.0)
    return Hour(
        at=at,
        temperature_c=round(temp, 1),
        relative_humidity_pct=round(rh),
        wind_speed_kmh=round(max(wind, 0.0), 1),
        wind_gust_kmh=round(max(wind, 0.0) * (1.9 if sirocco or storm else 1.5), 1),
        wind_direction_deg=round(direction),
        precipitation_mm=rain,
        weather_code=code,
    )


class SimProvider:
    name = "sim"
    simulated = True

    def __init__(self, now: datetime | None = None) -> None:
        self._now = now

    def attribution(self) -> dict[str, str] | str:
        return SIM_ATTRIBUTION

    async def fetch(self, points: list[tuple[float, float]], past_days: int, forecast_days: int) -> list[Series]:
        now = (self._now or datetime.now(UTC)).replace(minute=0, second=0, microsecond=0)
        start = now.replace(hour=0) - timedelta(days=past_days)
        end = now.replace(hour=0) + timedelta(days=forecast_days)
        hours = int((end - start).total_seconds() // 3600)
        log.info("[SIM] weather.simulated_fetch", points=len(points), hours=hours)
        return [
            Series(lat, lon, [simulated_hour(lat, lon, start + timedelta(hours=h)) for h in range(hours)])
            for lat, lon in points
        ]


_provider: WeatherProvider | None = None


def get_provider() -> WeatherProvider:
    global _provider
    if _provider is None:
        settings = get_settings()
        if settings.weather_source == "sim":
            _provider = SimProvider()
        else:
            key = settings.weather_api_key.get_secret_value() if settings.weather_api_key else None
            _provider = OpenMeteoProvider(settings.weather_api_url, key, settings.weather_request_timeout_s)
    return _provider


def set_provider(provider: WeatherProvider | None) -> None:
    """Replace the provider (tests); None re-reads the settings on next use."""
    global _provider
    _provider = provider
