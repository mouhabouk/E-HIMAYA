from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Level = Literal["green", "yellow", "red"]


class Factor(BaseModel):
    code: str
    points: int
    value: Any = None


class DayRisk(BaseModel):
    day: date
    level: Level
    score: int
    factors: list[Factor]
    wave_height_m: float | None = None
    sea_temp_c: float | None = None
    current_kmh: float | None = None
    onshore_wind_kmh: float | None = None
    max_temperature_c: float | None = None


class BeachOut(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    gouvernorat_code: int | None
    level: Level | None
    score: int | None
    factors: list[Factor] = []
    wave_height_m: float | None = None
    sea_temp_c: float | None = None
    current_kmh: float | None = None
    classification: str | None = None
    guarded: bool | None = None
    crowd: str | None = None
    # Phones counted at this beach in the last 30 minutes (staff only; anonymous, with the citizen's consent).
    present: int | None = None


class BeachesOut(BaseModel):
    day: date
    computed_at: datetime | None
    simulated: bool
    attribution: list[dict[str, str] | str]
    # The phone warns when it is this close to a yellow or red beach (computed on the phone).
    warn_radius_m: int
    items: list[BeachOut]


class BeachDetail(BaseModel):
    beach: BeachOut
    days: list[DayRisk]
    # The beach card (PLAGES_MASTER): only the columns the reader may see; each with its source and date when known.
    card: dict[str, Any]
    sources: dict[str, Any]
    length_m: float | None
    seaward_deg: float | None
    simulated: bool
    attribution: list[dict[str, str] | str]


class Kpis(BaseModel):
    beaches: int
    red: int
    yellow: int
    green: int
    unknown: int
    average_score: float | None
    guarded: int
    drownings_season: int
    present: int


class GouvernoratRisk(BaseModel):
    code: int | None
    beaches: int
    red: int
    yellow: int
    green: int
    average_score: float | None
    crowd_high: int
    crowd_medium: int
    crowd_low: int


class Overview(BaseModel):
    day: date
    computed_at: datetime | None
    simulated: bool
    attribution: list[dict[str, str] | str]
    kpis: Kpis
    top_dangerous: list[BeachOut]
    top_touristic: list[BeachOut]
    by_gouvernorat: list[GouvernoratRisk]
    beaches: list[BeachOut]
    # [lat, lon, weight 0..1]: the risk of the day, and past drownings (5 years) grouped by about 1 km.
    heat_risk: list[list[float]]
    heat_drownings: list[list[float]]


class AlertOut(BaseModel):
    id: str
    feature_id: str
    name: str
    day: date
    level: Literal["yellow", "red"]
    previous_level: Level | None
    score: int
    gouvernorat_code: int | None
    simulated: bool
    created_at: datetime
    acked_by_name: str | None
    acked_at: datetime | None


class AlertsOut(BaseModel):
    items: list[AlertOut]


class PresenceIn(BaseModel):
    # A random token the phone draws each day; never stored as such.
    token: str = Field(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class SettingsOut(BaseModel):
    rules: dict[str, Any]
    defaults: dict[str, Any]
    updated_by: str | None
    updated_at: datetime | None


class SettingsIn(BaseModel):
    rules: dict[str, Any]
    reason: str = Field(min_length=3, max_length=500)
