import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.modules.sensors.domain import MAX_BATCH, Kind, State

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
Provider = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
Code = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{1,39}$")]


class _Thresholds(BaseModel):
    watch_threshold: float = Field(ge=-30, le=300)
    alarm_threshold: float = Field(ge=-30, le=300)

    @model_validator(mode="after")
    def _ordered(self) -> "_Thresholds":
        if self.alarm_threshold < self.watch_threshold:
            raise ValueError("thresholds_order")
        return self


class SensorIn(_Thresholds):
    model_config = ConfigDict(extra="forbid")

    code: Code
    name: Name
    kind: Kind
    # None: the caller's own gouvernorat; the central room names one.
    gouvernorat_code: int | None = Field(default=None, ge=1, le=99)
    lat: float = Field(ge=30, le=38)
    lon: float = Field(ge=7, le=12)
    provider: Provider
    silent_after_min: int = Field(default=30, ge=5, le=1440)
    simulated: bool = True


class SensorUpdate(_Thresholds):
    model_config = ConfigDict(extra="forbid")

    name: Name
    lat: float = Field(ge=30, le=38)
    lon: float = Field(ge=7, le=12)
    provider: Provider
    silent_after_min: int = Field(ge=5, le=1440)
    enabled: bool


class SensorOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    kind: Kind
    unit: str
    gouvernorat_code: int
    lat: float
    lon: float
    provider: str
    watch_threshold: float
    alarm_threshold: float
    silent_after_min: int
    enabled: bool
    simulated: bool
    last_value: float | None
    last_at: datetime | None
    state: State
    level_since: datetime | None
    created_by_name: str | None
    updated_at: datetime


class SensorPage(BaseModel):
    items: list[SensorOut]
    can_manage: bool


class SensorKeyOut(BaseModel):
    """The sensor and its signing key, shown this once: it is never shown or logged again."""

    sensor: SensorOut
    key: str


class ReadingOut(BaseModel):
    at: datetime
    value: float


class ReadingsOut(BaseModel):
    sensor_id: uuid.UUID
    unit: str
    watch_threshold: float
    alarm_threshold: float
    items: list[ReadingOut]


# ---------------------------------------------------------------- the gateway beside MediaMTX (internal)


class RawReadingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sensor: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    at: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    value: Annotated[str, StringConstraints(min_length=1, max_length=16)]
    sig: Annotated[str, StringConstraints(min_length=1, max_length=64)]


class ReadingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readings: list[RawReadingIn] = Field(min_length=1, max_length=MAX_BATCH)


class IngestOut(BaseModel):
    accepted: int
    rejected: dict[Literal["unknown_sensor", "bad_signature", "bad_time", "bad_value", "replay"], int]
    suggestions: int
