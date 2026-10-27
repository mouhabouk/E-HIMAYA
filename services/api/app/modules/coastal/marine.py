"""Where the marine weather of the beaches comes from: the Open-Meteo Marine API (or the same interface from INM), or
the simulator.

Open-Meteo Marine (https://open-meteo.com/en/docs/marine-weather-api, data licence CC BY 4.0, attribution shown
wherever the data is shown): one request carries up to 50 beaches; hourly wave height, period and direction, sea
surface temperature and ocean current. Same behaviour as the weather provider (app/modules/weather/provider.py):
timeouts, three attempts on network errors and 5xx, a 429 stops the cycle, and a failure keeps the last values.
A beach too close to the land for the marine model answers empty values: the risk then counts the waves as unknown.
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
    "wave_height",
    "wave_period",
    "wave_direction",
    "sea_surface_temperature",
    "ocean_current_velocity",
    "ocean_current_direction",
)
ATTRIBUTION = {
    "text": "Marine data by Open-Meteo.com",
    "url": "https://open-meteo.com/en/docs/marine-weather-api",
    "licence": "CC BY 4.0",
}
SIM_ATTRIBUTION = "[SIM] Simulated marine weather (e-Himaya simulator), not real data"
MAX_ATTEMPTS = 3
BATCH = 50


class MarineUnavailable(Exception):
    """The provider failed for this batch (network, 5xx, malformed answer)."""


class MarineRateLimited(MarineUnavailable):
    """The provider answered 429: stop this cycle."""


@dataclass(frozen=True, slots=True)
class MarineValues:
    at: datetime
    wave_height_m: float | None
    wave_period_s: float | None
    wave_direction_deg: float | None
    sea_temp_c: float | None
    current_kmh: float | None
    current_direction_deg: float | None


class MarineProvider(Protocol):
    name: str
    simulated: bool

    def attribution(self) -> dict[str, str] | str: ...

    async def fetch(self, points: list[tuple[float, float]], forecast_days: int) -> list[list[MarineValues]]:
        """Hourly values (UTC, whole hours, from today 00:00) of each point, in the order given."""
        ...


def _num(values: list[Any] | None, i: int) -> float | None:
    if values is None or i >= len(values) or values[i] is None:
        return None
    return float(values[i])


def parse(payload: Any, expected: int) -> list[list[MarineValues]]:
    """Open-Meteo answers an object for one location and a list for several."""
    items = payload if isinstance(payload, list) else [payload]
    if len(items) != expected:
        raise MarineUnavailable("location_count_mismatch")
    out: list[list[MarineValues]] = []
    for item in items:
        try:
            hourly = item["hourly"]
            columns = {name: hourly.get(name) for name in HOURLY_VARIABLES}
            out.append(
                [
                    MarineValues(
                        at=datetime.fromtimestamp(int(t), UTC),
                        wave_height_m=_num(columns["wave_height"], i),
                        wave_period_s=_num(columns["wave_period"], i),
                        wave_direction_deg=_num(columns["wave_direction"], i),
                        sea_temp_c=_num(columns["sea_surface_temperature"], i),
                        current_kmh=_num(columns["ocean_current_velocity"], i),
                        current_direction_deg=_num(columns["ocean_current_direction"], i),
                    )
                    for i, t in enumerate(hourly["time"])
                ]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise MarineUnavailable("malformed_answer") from exc
    return out


class OpenMeteoMarine:
    name = "open-meteo"
    simulated = False

    def __init__(
        self,
        base_url: str,
        timeout_s: float,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_pause_s: float = 1.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_s, connect=min(timeout_s, 10.0))
        self._transport = transport
        self._retry_pause_s = retry_pause_s

    def attribution(self) -> dict[str, str] | str:
        return dict(ATTRIBUTION)

    async def fetch(self, points: list[tuple[float, float]], forecast_days: int) -> list[list[MarineValues]]:
        params = {
            "latitude": ",".join(f"{lat:.4f}" for lat, _ in points),
            "longitude": ",".join(f"{lon:.4f}" for _, lon in points),
            "hourly": ",".join(HOURLY_VARIABLES),
            "timezone": "GMT",
            "timeformat": "unixtime",
            "forecast_days": str(forecast_days),
            "cell_selection": "sea",
        }
        last_error = "unknown"
        headers = {"User-Agent": "e-Himaya/1.0 (civil protection, Tunisia)"}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers, transport=self._transport) as client:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    response = await client.get(f"{self._base_url}/v1/marine", params=params)
                except httpx.HTTPError as exc:
                    last_error = type(exc).__name__
                else:
                    if response.status_code == 429:
                        raise MarineRateLimited("rate_limited")
                    if response.status_code == 200:
                        try:
                            return parse(response.json(), len(points))
                        except ValueError as exc:
                            raise MarineUnavailable("malformed_answer") from exc
                    last_error = f"http_{response.status_code}"
                    if response.status_code < 500:
                        break
                if attempt < MAX_ATTEMPTS:
                    await asyncio.sleep(self._retry_pause_s * 2 ** (attempt - 1))
        raise MarineUnavailable(last_error)


# ┏━━ SIMULATION ━━ deterministic marine simulator (the development default, with WEATHER_PROVIDER=sim)
# ┃ Calm summer seas (0.2 to 0.6 m), rougher in winter, and recurring episodes so that the coastal dashboard shows the
# ┃ three colours without any network: a northern swell (2 to 2.8 m north of 36.8° N) on days ≡ 1 (mod 4), and an
# ┃ eastern chop (1.2 to 1.6 m east of 10.4° E) on days ≡ 3 (mod 6), with a stronger current. The same position and
# ┃ hour always give the same values (tests rely on it).
# ┃ PRODUCTION: Open-Meteo Marine (APP_ENV=production refuses the simulated weather).
# ┗━━━━━━━━━━━━━━━━
def _noise(*parts: float) -> float:
    digest = hashlib.blake2b(repr(parts).encode(), digest_size=4).digest()
    return int.from_bytes(digest, "big") / 2**31 - 1.0


def simulated_values(lat: float, lon: float, at: datetime) -> MarineValues:
    day = at.toordinal()
    doy = at.timetuple().tm_yday
    season = math.cos(2 * math.pi * (doy - 215) / 365.0)  # +1 early August, -1 early February
    wave = 0.6 - 0.25 * season + 0.15 * _noise(lat, lon, day)
    current = 0.8 + 0.3 * _noise(lon, lat, day)
    direction = (330.0 + 30.0 * _noise(day, 3.0)) % 360.0
    if day % 4 == 1 and lat >= 36.8:
        wave = 2.0 + 0.8 * max(math.sin(math.pi * at.hour / 24.0), 0.0)
        current = 2.4
        direction = 340.0
    elif day % 6 == 3 and lon >= 10.4:
        wave = 1.2 + 0.4 * max(math.sin(math.pi * at.hour / 24.0), 0.0)
        current = 2.0
        direction = 70.0
    sea = 20.5 + 6.0 * season - 0.4 * max(lat - 36.0, 0.0) + 0.3 * _noise(lat, day)
    return MarineValues(
        at=at,
        wave_height_m=round(max(wave, 0.1), 2),
        wave_period_s=round(4.0 + 2.0 * max(wave, 0.1), 1),
        wave_direction_deg=round(direction),
        sea_temp_c=round(sea, 1),
        current_kmh=round(max(current, 0.1), 2),
        current_direction_deg=round((direction + 90.0) % 360.0),
    )


class SimMarine:
    name = "sim"
    simulated = True

    def __init__(self, now: datetime | None = None) -> None:
        self._now = now

    def attribution(self) -> dict[str, str] | str:
        return SIM_ATTRIBUTION

    async def fetch(self, points: list[tuple[float, float]], forecast_days: int) -> list[list[MarineValues]]:
        start = (self._now or datetime.now(UTC)).replace(hour=0, minute=0, second=0, microsecond=0)
        hours = forecast_days * 24
        log.info("[SIM] coastal.simulated_marine_fetch", points=len(points), hours=hours)
        return [[simulated_values(lat, lon, start + timedelta(hours=h)) for h in range(hours)] for lat, lon in points]


_provider: MarineProvider | None = None


def get_provider() -> MarineProvider:
    global _provider
    if _provider is None:
        settings = get_settings()
        if settings.weather_source == "sim":
            _provider = SimMarine()
        else:
            _provider = OpenMeteoMarine(settings.marine_api_url, settings.weather_request_timeout_s)
    return _provider


def set_provider(provider: MarineProvider | None) -> None:
    """Replace the provider (tests); None re-reads the settings on next use."""
    global _provider
    _provider = provider
