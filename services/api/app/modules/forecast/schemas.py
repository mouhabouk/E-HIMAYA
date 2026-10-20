"""Bodies of the spread forecast endpoints (docs/api/phase-7-contract.md §2)."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.modules.reports.domain import LAT_MAX, LAT_MIN, LON_MAX, LON_MIN

FuelKey = Literal["grass", "shrub", "timber_litter", "mixed"]


class Point(BaseModel):
    lat: float = Field(ge=LAT_MIN, le=LAT_MAX)
    lon: float = Field(ge=LON_MIN, le=LON_MAX)


class FireForecastIn(BaseModel):
    # None: the incident's centroid.
    ignition: Point | None = None
    # None: "mixed" (no land-cover layer yet; stated in the assumptions).
    fuel_model: FuelKey | None = None
    horizons_min: list[int] = Field(default_factory=lambda: [30, 60, 120], min_length=1, max_length=6)

    @field_validator("horizons_min")
    @classmethod
    def _horizons(cls, value: list[int]) -> list[int]:
        if any(not 5 <= m <= 720 for m in value):
            raise ValueError("horizons must be between 5 and 720 minutes")
        return sorted(set(value))


class Assumption(BaseModel):
    code: str
    text: dict[str, str]


class FirePolygon(BaseModel):
    minutes: int
    geojson: dict[str, Any]
    area_ha: float
    head_m: float
    back_m: float
    length_m: float
    width_m: float


class FireForecastOut(BaseModel):
    forecast_id: uuid.UUID
    incident_id: uuid.UUID
    kind: Literal["fire"] = "fire"
    model: str
    inputs: dict[str, Any]
    polygons: list[FirePolygon]
    rate_of_spread_m_min: float
    backing_rate_m_min: float
    heading_deg: float
    length_to_breadth: float
    fireline_intensity_kw_m: float
    flame_length_m: float
    assumptions: list[Assumption]
    disclaimer: dict[str, str]
    attribution: list[str]
    generated_at: datetime
    created_by: str
    simulated: bool


class FloodForecastOut(BaseModel):
    forecast_id: uuid.UUID
    incident_id: uuid.UUID
    kind: Literal["flood"] = "flood"
    model: str
    advisory: Literal[True] = True
    inputs: dict[str, Any]
    level: Literal["minimal", "low", "moderate", "high"]
    risk_polygon: dict[str, Any]
    risk_area_ha: float
    low_points: list[dict[str, float]]
    drainage_direction_deg: float | None
    assumptions: list[Assumption]
    disclaimer: dict[str, str]
    attribution: list[str]
    generated_at: datetime
    created_by: str
    simulated: bool


class ForecastPage(BaseModel):
    items: list[FireForecastOut | FloodForecastOut]
