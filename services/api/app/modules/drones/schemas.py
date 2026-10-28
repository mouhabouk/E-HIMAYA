import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from app.modules.drones.domain import MAX_POINTS, AlertKind

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
Ring = Annotated[list[Annotated[list[float], Field(min_length=2, max_length=2)]], Field(min_length=3, max_length=101)]


class DroneIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Name
    # None: the caller's own gouvernorat; the central room names one.
    gouvernorat_code: int | None = Field(default=None, ge=1, le=99)


class Telemetry(BaseModel):
    at: datetime
    lat: float
    lon: float
    alt_m: float | None
    heading_deg: float | None
    sensor_az_deg: float | None
    sensor_hfov_deg: float | None
    battery_pct: float | None
    mode: str | None


class DroneOut(BaseModel):
    id: uuid.UUID
    label: str
    gouvernorat_code: int | None
    stream_status: str
    last: Telemetry | None
    # The camera's view on the map (a closed ring of [lon, lat]) when the source gives its direction and opening.
    camera_view: list[list[float]] | None
    open_alerts: int


class DronePage(BaseModel):
    items: list[DroneOut]
    can_register: bool


class DroneCreated(BaseModel):
    """The new drone and its publish token, shown once (MediaMTX takes its video; nothing is ever sent back)."""

    drone: DroneOut
    publish_token: str
    publish_url_rtsp: str
    publish_url_rtmp: str


class TrackOut(BaseModel):
    drone_id: uuid.UUID
    items: list[Telemetry]


class ZoneIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["work", "no_fly"]
    name: Name
    # GeoJSON ring of [lon, lat]; closed by the server when it is not.
    ring: Ring
    margin_m: int = Field(default=500, ge=0, le=5000)
    gouvernorat_code: int | None = Field(default=None, ge=1, le=99)


class ZoneUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    ring: Ring
    margin_m: int = Field(ge=0, le=5000)
    active: bool


class ZoneOut(BaseModel):
    id: uuid.UUID
    kind: Literal["work", "no_fly"]
    name: str
    gouvernorat_code: int
    ring: list[list[float]]
    margin_m: int
    active: bool
    created_by_name: str | None
    updated_at: datetime


class AlertOut(BaseModel):
    id: int
    drone_id: uuid.UUID
    drone_label: str
    at: datetime
    kind: AlertKind
    zone_name: str | None
    detail: dict[str, float | str | None]
    acknowledged_by_name: str | None
    acknowledged_at: datetime | None


# ---------------------------------------------------------------- the reader beside MediaMTX (internal)


class PointIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    at: AwareDatetime
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    alt_m: float | None = Field(default=None, ge=-900, le=19000)
    heading_deg: float | None = Field(default=None, ge=0, lt=360)
    sensor_az_deg: float | None = Field(default=None, ge=0, lt=360)
    sensor_hfov_deg: float | None = Field(default=None, gt=0, le=180)
    battery_pct: float | None = Field(default=None, ge=0, le=100)
    mode: Annotated[str, StringConstraints(max_length=32)] | None = None


class TelemetryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stream_id: uuid.UUID
    points: list[PointIn] = Field(min_length=1, max_length=MAX_POINTS)


class TelemetryResult(BaseModel):
    accepted: int
    rejected: dict[Literal["bad_time", "replay"], int]
    alerts: list[AlertKind]


class LiveDrones(BaseModel):
    """The drone streams on air, for the reader beside MediaMTX (which path to read)."""

    items: list[uuid.UUID]
