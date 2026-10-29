import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
Code = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{1,39}$")]


class _Place(BaseModel):
    label: Label
    lat: float = Field(ge=30, le=38)
    lon: float = Field(ge=7, le=12)
    # Degrees clockwise from north the camera looks at, its opening, and how far it sees.
    bearing_deg: int = Field(ge=0, le=359)
    fov_deg: int = Field(ge=5, le=360)
    range_m: int = Field(ge=100, le=50_000)


class TowerIn(_Place):
    model_config = ConfigDict(extra="forbid")

    code: Code
    # None: the caller's own gouvernorat; the central room names one.
    gouvernorat_code: int | None = Field(default=None, ge=1, le=99)
    simulated: bool = True


class TowerUpdate(_Place):
    model_config = ConfigDict(extra="forbid")


class LastEvent(BaseModel):
    at: datetime
    label: Literal["fire", "smoke"]
    confidence: float


class TowerOut(BaseModel):
    id: uuid.UUID
    code: str
    label: str
    gouvernorat_code: int
    lat: float
    lon: float
    bearing_deg: int
    fov_deg: int
    range_m: int
    simulated: bool
    # The camera's stream: pending (never connected), live, ended (between two connections).
    stream_status: str
    last_event: LastEvent | None
    # The field of view on the map: a closed GeoJSON ring of [lon, lat].
    field_of_view: list[list[float]]
    created_by_name: str | None
    updated_at: datetime


class TowerPage(BaseModel):
    items: list[TowerOut]
    can_manage: bool


class TowerCreated(BaseModel):
    """The new tower, the key of its edge computer and the camera's publish token, shown this once."""

    tower: TowerOut
    edge_key: str
    publish_token: str
    publish_url_rtsp: str
    publish_url_rtmp: str


class TowerKeyOut(BaseModel):
    tower: TowerOut
    edge_key: str


class TowerEventOut(BaseModel):
    at: datetime
    label: Literal["fire", "smoke"]
    confidence: float
    hits: int
    frames: int
    model: str | None
    media_id: uuid.UUID | None
    suggestion_id: uuid.UUID | None


class TowerEventsOut(BaseModel):
    tower_id: uuid.UUID
    items: list[TowerEventOut]


# ---------------------------------------------------------------- the gateway beside MediaMTX (internal)


class TowerEventIn(BaseModel):
    """One signed event of an edge computer, every field the string it signed."""

    model_config = ConfigDict(extra="forbid")

    tower: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    at: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    label: Annotated[str, StringConstraints(min_length=1, max_length=16)]
    confidence: Annotated[str, StringConstraints(min_length=1, max_length=8)]
    hits: Annotated[str, StringConstraints(min_length=1, max_length=2)]
    frames: Annotated[str, StringConstraints(min_length=1, max_length=2)]
    model: Annotated[str, StringConstraints(max_length=80)] = ""
    # One JPEG of the confirming frame (base64), at most ~2 MB once decoded; its SHA-256 is signed.
    frame_jpeg_b64: Annotated[str, StringConstraints(max_length=2_800_000)] = ""
    sig: Annotated[str, StringConstraints(min_length=1, max_length=64)]


Refusal = Literal[
    "unknown_tower", "bad_frame", "bad_signature", "bad_time", "bad_value", "not_confirmed", "low_confidence", "replay"
]


class TowerEventResult(BaseModel):
    accepted: bool
    reason: Refusal | None = None
    suggestion: bool = False
