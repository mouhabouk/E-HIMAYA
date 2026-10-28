"""Bodies of the weather endpoints (docs/api/phase-7-contract.md §1; the hourly shape is the one the app reads, see
the contract's implementation notes)."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.modules.notify.schemas import PublicAlert

DangerClass = Literal["low", "moderate", "high", "very_high", "extreme"]
RainLevel = Literal["none", "watch", "warning"]
Metric = Literal["fire_danger", "wind_gust", "rain_24h", "rain_1h"]
# A suggestion may also come from a sensor or a watch tower of the local network (L5b, design-l5.md §3.1 and §3.2);
# rules stay weather only.
SuggestionMetric = (
    Metric | Literal["sensor_rain_1h", "sensor_water_level", "sensor_temperature", "tower_fire", "tower_smoke"]
)
Severity = Literal["high", "medium", "low"]


class FireDangerOut(BaseModel):
    """Canadian FWI System of the day (noon values) and its class."""

    model_config = ConfigDict(populate_by_name=True)

    class_: DangerClass = Field(alias="class")
    fwi: float
    ffmc: float | None = None
    dmc: float | None = None
    dc: float | None = None
    isi: float | None = None
    bui: float | None = None


class HeavyRainOut(BaseModel):
    level: RainLevel


class HourOut(BaseModel):
    time: datetime
    temperature_c: float | None
    wind_speed_kmh: float | None
    wind_gust_kmh: float | None
    wind_direction_deg: int | None
    relative_humidity_pct: int | None
    precipitation_mm_h: float | None
    precipitation_24h_mm: float | None
    fire_danger: FireDangerOut | None
    heavy_rain: HeavyRainOut
    weather_code: int | None = None


class Location(BaseModel):
    lat: float
    lon: float


class WeatherOut(BaseModel):
    """GET /api/v1/weather (public)."""

    location: Location
    # Grid point the values come from and its distance to the asked position.
    grid_point: Location
    distance_km: float
    updated_at: datetime | None
    current: HourOut
    hourly: list[HourOut]
    alerts: list[PublicAlert]
    attribution: dict[str, str] | str
    simulated: bool


class PointInfo(BaseModel):
    id: int
    lat: float
    lon: float
    gouvernorat_code: int | None
    distance_km: float


class PointDetail(BaseModel):
    """GET /api/v1/staff/weather/at."""

    point: PointInfo
    # The grid point's position again at the top level (the shape of the public card).
    lat: float
    lon: float
    updated_at: datetime | None
    current: HourOut
    past: list[HourOut]
    hourly: list[HourOut]
    # Active weather alerts covering the asked position (as in GET /api/v1/weather).
    alerts: list[PublicAlert]
    attribution: dict[str, str] | str
    simulated: bool


class SuggestionOut(BaseModel):
    id: uuid.UUID
    metric: SuggestionMetric
    gouvernorat_codes: list[int]
    category: Literal["weather"]
    hazard: str
    severity: Severity
    title: dict[str, str]
    body: dict[str, str]
    evidence: dict[str, Any]
    valid_from: datetime
    valid_until: datetime
    status: Literal["pending", "accepted", "dismissed", "expired"]
    created_at: datetime
    decided_by: str | None
    decided_at: datetime | None
    dismiss_reason: str | None
    simulated: bool


class SuggestionPage(BaseModel):
    items: list[SuggestionOut]


class AcceptOut(BaseModel):
    """The suggestion, now accepted, and the phase 5 alert form prefilled with it. Nothing has been sent: the editor
    reviews the form and creates and publishes the alert through POST /api/v1/staff/notifications."""

    suggestion: SuggestionOut
    alert_form: dict[str, Any]


class DismissIn(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class RuleIn(BaseModel):
    metric: Metric
    # fire_danger: class rank (0 low, 1 moderate, 2 high, 3 very_high, 4 extreme); wind_gust: km/h; rain: mm.
    threshold: float = Field(ge=0, le=1000)
    severity: Severity
    enabled: bool = True


class RulesIn(BaseModel):
    # None: the national rules (central committee, ops manager); a code: that gouvernorat's own rules.
    gouvernorat_code: int | None = None
    rules: list[RuleIn] = Field(max_length=4)


class RuleOut(BaseModel):
    id: int
    gouvernorat_code: int | None
    metric: Metric
    threshold: float
    severity: Severity
    enabled: bool
    updated_by: str | None
    updated_at: datetime
