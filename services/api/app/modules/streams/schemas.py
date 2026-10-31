"""Request and response bodies of the live-stream endpoints (docs/api/phase-6-contract.md)."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from app.modules.reports.domain import LAT_MAX, LAT_MIN, LON_MAX, LON_MIN

# ---------------------------------------------------------------- citizen (§2)


class StreamCreated(BaseModel):
    stream_id: uuid.UUID
    path: str
    whip_url: str
    publish_token: str
    expires_at: datetime
    max_duration_s: int
    location_interval_s: int
    simulated: bool


class LocationIn(BaseModel):
    lat: float = Field(ge=LAT_MIN, le=LAT_MAX)
    lon: float = Field(ge=LON_MIN, le=LON_MAX)
    accuracy_m: float | None = Field(default=None, ge=0, le=100_000)


class StreamSummary(BaseModel):
    stream_id: uuid.UUID
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    end_reason: str | None


# ---------------------------------------------------------------- staff (§4)


class Point(BaseModel):
    lat: float
    lon: float


class StaffStream(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID | None
    tracking_code: str | None
    source: str
    label: str | None
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_s: float | None
    gouvernorat_code: int | None
    last_location: Point | None
    max_fire_confidence: float | None
    max_smoke_confidence: float | None
    recordings_count: int
    simulated: bool
    # A team's stream (phase D): its incident, for the incident page and the wall.
    incident_id: uuid.UUID | None = None


class StaffStreamPage(BaseModel):
    items: list[StaffStream]
    next_cursor: str | None


class RecordingOut(BaseModel):
    media_id: uuid.UUID
    sha256: str
    bytes: int | None
    duration_s: float | None
    created_at: datetime


class DetectionOut(BaseModel):
    at: datetime
    label: str
    confidence: float
    boxes: list[list[float]]


class TrackPoint(BaseModel):
    at: datetime
    lat: float
    lon: float


class StaffStreamDetail(StaffStream):
    recordings: list[RecordingOut]
    detections: list[DetectionOut]
    track: list[TrackPoint]


class ViewerOut(BaseModel):
    whep_url: str
    hls_url: str
    token: str
    expires_at: datetime


Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class FixedSourceIn(BaseModel):
    source: Literal["drone", "camera"]
    label: Label
    gouvernorat_code: int = Field(ge=1, le=99)
    # Where a fixed camera stands (shown on the map until it reports positions).
    lat: float | None = Field(default=None, ge=LAT_MIN, le=LAT_MAX)
    lon: float | None = Field(default=None, ge=LON_MIN, le=LON_MAX)
    # A camera of an institution (review point 25): a fire or smoke it confirms goes to the owner first (pre-alert).
    org_id: uuid.UUID | None = None


class FixedSourceOut(BaseModel):
    id: uuid.UUID
    path: str
    publish_url_rtsp: str
    publish_url_rtmp: str
    publish_token: str


# ---------------------------------------------------------------- internal (§3)


class MediamtxAuthIn(BaseModel):
    """Body MediaMTX posts to authHTTPAddress (extra fields such as userAgent are ignored)."""

    model_config = ConfigDict(extra="ignore")

    user: str = Field(default="", max_length=256)
    password: str = Field(default="", max_length=1024)
    token: str = Field(default="", max_length=4096)
    ip: str = Field(default="", max_length=64)
    action: str = Field(default="", max_length=32)
    path: str = Field(default="", max_length=256)
    protocol: str = Field(default="", max_length=32)
    id: str | None = Field(default=None, max_length=64)
    query: str = Field(default="", max_length=4096)


class HookIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event: Literal["ready", "not_ready", "segment_complete"]
    path: str = Field(max_length=256)
    source_type: str | None = Field(default=None, max_length=64)
    source_id: str | None = Field(default=None, max_length=64)
    segment_path: str | None = Field(default=None, max_length=1024)
    segment_duration_s: float | None = Field(default=None, ge=0, le=86_400)


class DetectionIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str = Field(max_length=32)
    confidence: float = Field(ge=0, le=1)
    boxes: list[Annotated[list[float], Field(min_length=4, max_length=5)]] = Field(default_factory=list, max_length=50)


class DetectionsIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    stream_id: uuid.UUID
    at: AwareDatetime
    model: str = Field(default="", max_length=200)
    detections: list[DetectionIn] = Field(default_factory=list, max_length=100)
    # One JPEG of the frame (base64), sent with a detection worth showing; at most ~2 MB once decoded.
    frame_jpeg_b64: str | None = Field(default=None, max_length=2_800_000)


# ---------------------------------------------------------------- simulation (stream-sim)


class SimStreamIn(BaseModel):
    """SIMULATION: body of POST /internal/sim/streams (stream-sim service)."""

    label: Label = "SIM camera"
    gouvernorat_code: int = Field(default=11, ge=1, le=99)
    lat: float | None = Field(default=None, ge=LAT_MIN, le=LAT_MAX)
    lon: float | None = Field(default=None, ge=LON_MIN, le=LON_MAX)


class SimStreamOut(BaseModel):
    id: uuid.UUID
    path: str
    publish_token: str
    rtsp_url: str


class SimStreamStatus(BaseModel):
    id: uuid.UUID
    status: str
    recordings_count: int
    simulated: bool


def as_json(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
