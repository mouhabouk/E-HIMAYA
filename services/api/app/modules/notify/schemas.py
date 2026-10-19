import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

Kind = Literal["info", "alert"]
MessageStatus = Literal["draft", "published", "cancelled", "expired"]
Channel = Literal["push", "sms", "email"]
Topic = Literal["activity", "awareness", "training", "world_day", "other"]
Audience = Literal["all", "volunteers", "organizations", "user"]
Severity = Literal["high", "medium", "low"]
AlertCategory = Literal["weather", "climate", "hazard"]
Hazard = Literal[
    "heavy_rain", "flood", "storm", "wind", "heat_wave", "cold_wave", "sea", "forest_fire", "chemical", "other"
]
Text = Annotated[str, StringConstraints(strip_whitespace=True)]


class LocalizedTitle(BaseModel):
    ar: Annotated[Text, StringConstraints(min_length=1, max_length=120)]
    fr: Annotated[Text, StringConstraints(max_length=120)] = ""
    en: Annotated[Text, StringConstraints(max_length=120)] = ""


class LocalizedBody(BaseModel):
    ar: Annotated[Text, StringConstraints(min_length=1, max_length=1000)]
    fr: Annotated[Text, StringConstraints(max_length=1000)] = ""
    en: Annotated[Text, StringConstraints(max_length=1000)] = ""


class Area(BaseModel):
    gouvernorat_codes: list[int] = Field(default_factory=list, max_length=24)
    # GeoJSON Polygon: {"type": "Polygon", "coordinates": [[[lon, lat], ...]]}
    polygon: dict[str, Any] | None = None


class MessageIn(BaseModel):
    kind: Kind
    title: LocalizedTitle
    body: LocalizedBody
    channels: list[Channel] = Field(default=["push"], min_length=1, max_length=3)
    # informational
    topic: Topic | None = None
    audience: Audience | None = None
    user_id: uuid.UUID | None = None
    # alert
    severity: Severity | None = None
    category: AlertCategory | None = None
    hazard: Hazard | None = None
    expires_at: datetime | None = None
    # both
    area: Area = Field(default_factory=Area)
    version: int | None = None

    @field_validator("channels")
    @classmethod
    def _unique(cls, value: list[Channel]) -> list[Channel]:
        return sorted(set(value), key=["push", "sms", "email"].index)


class ChannelStats(BaseModel):
    status: str
    sent: int
    failed: int


class MessageOut(BaseModel):
    id: uuid.UUID
    kind: Kind
    status: MessageStatus
    title: dict[str, str]
    body: dict[str, str]
    channels: list[Channel]
    topic: Topic | None
    audience: Audience | None
    user_id: uuid.UUID | None
    severity: Severity | None
    category: AlertCategory | None
    hazard: Hazard | None
    expires_at: datetime | None
    area: Area
    created_by: str | None
    created_at: datetime
    published_by: str | None
    published_at: datetime | None
    cancelled_at: datetime | None
    version: int
    stats: dict[str, ChannelStats]


class MessagePage(BaseModel):
    items: list[MessageOut]
    next_cursor: str | None


class AudienceOut(BaseModel):
    push: int
    sms: int
    email: int


class PublicAlert(BaseModel):
    id: uuid.UUID
    severity: Severity
    category: AlertCategory
    hazard: Hazard | None
    title: dict[str, str]
    body: dict[str, str]
    area: Area
    published_at: datetime
    expires_at: datetime


class InboxItem(BaseModel):
    id: uuid.UUID
    kind: Kind
    topic: Topic | None
    severity: Severity | None
    title: dict[str, str]
    body: dict[str, str]
    published_at: datetime
    expires_at: datetime | None
    active: bool


class InboxPage(BaseModel):
    items: list[InboxItem]
    next_cursor: str | None


class DeviceIn(BaseModel):
    token: Annotated[str, StringConstraints(min_length=20, max_length=4096)]
    platform: Literal["android", "ios"]
    locale: Literal["ar", "fr", "en"] = "ar"
    lat: float | None = Field(default=None, ge=30.0, le=37.6)
    lon: float | None = Field(default=None, ge=7.4, le=11.7)
    location_alerts: bool = True
