import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator

from app.modules.orgs.domain import OrgKind

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
    # institutions (phase P2b): some kinds only (empty: every kind), and a read acknowledgement
    org_kinds: list[OrgKind] = Field(default_factory=list, max_length=12)
    ack_required: bool = False
    # both
    area: Area = Field(default_factory=Area)
    version: int | None = None

    @field_validator("channels")
    @classmethod
    def _unique(cls, value: list[Channel]) -> list[Channel]:
        return sorted(set(value), key=["push", "sms", "email"].index)

    @field_validator("org_kinds")
    @classmethod
    def _unique_kinds(cls, value: list[OrgKind]) -> list[OrgKind]:
        return sorted(set(value))


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
    # Four eyes (phase 10 §5.1).
    updated_by: str | None = None
    single_reviewer: bool = False
    emergency_reason: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    # Phase P2b.
    org_kinds: list[OrgKind] = Field(default_factory=list)
    ack_required: bool = False


class OrgAckRow(BaseModel):
    org_id: uuid.UUID
    name: str
    kind: OrgKind
    gouvernorat_code: int | None
    acked_at: datetime | None
    acked_by: str | None


class OrgAcks(BaseModel):
    """Institutions a message reaches and those that confirmed reading it (phase P2b)."""

    targeted: int
    acked: int
    items: list[OrgAckRow]


class PublishIn(BaseModel):
    """Optional body of a publication: the author of an alert publishes it alone only with an emergency reason."""

    emergency_reason: str | None = Field(default=None, max_length=500)


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


class UserLookupIn(BaseModel):
    # In the body rather than the query string, so the address stays out of URLs and proxy logs.
    email: EmailStr = Field(max_length=254)


class UserChannels(BaseModel):
    push: bool
    sms: bool
    email: bool


class UserLookupOut(BaseModel):
    """Just enough to confirm the right person before targeting them (no full name, no full address)."""

    user_id: uuid.UUID
    display_name: str | None
    email: str
    channels: UserChannels
