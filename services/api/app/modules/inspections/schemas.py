import uuid
from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True)]
Matricule = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9A-Za-z-]{3,20}$")]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9 ]{8,16}$")]
Name = Annotated[Text, StringConstraints(min_length=2, max_length=120)]
Reason = Annotated[Text, StringConstraints(min_length=3, max_length=500)]
Answer = Literal["ok", "note", "ko"]
Priority = Literal["high", "medium", "low"]
Audience = Literal["none", "regional", "central", "both"]
Kind = Literal["periodic", "surprise"]
Target = Literal["unit", "room"]
RoomKind = Literal["central", "regional"]
# The kinds of unit a planner picks before typing the unit's name (Yamen 2026-11-11).
UnitKind = Literal["regional_directorate", "brigade", "centre", "advanced_centre", "guard_post", "beach", "other"]
UnitName = Annotated[Text, StringConstraints(min_length=2, max_length=160)]
InspectorStatus = Literal["pending", "code_sent", "active", "blocked", "rejected", "closed"]


# ---------------------------------------------------------------- settings


class AxisIn(BaseModel):
    key: Annotated[str, StringConstraints(pattern=r"^[a-z]{1,8}$")]
    name: Annotated[Text, StringConstraints(min_length=2, max_length=60)]
    weight: int = Field(ge=0, le=100)


class ItemIn(BaseModel):
    key: Annotated[str, StringConstraints(pattern=r"^[a-z]{1,8}[0-9]{1,3}$")]
    axis: Annotated[str, StringConstraints(pattern=r"^[a-z]{1,8}$")]
    text: Annotated[Text, StringConstraints(min_length=2, max_length=200)]
    weight: int = Field(ge=0, le=100)


class ValuesIn(BaseModel):
    ok: int = Field(ge=0, le=100)
    note: int = Field(ge=0, le=100)
    ko: int = Field(ge=0, le=100)


class WeightsIn(BaseModel):
    items: int = Field(ge=0, le=100)
    presence: int = Field(ge=0, le=100)
    exit: int = Field(ge=0, le=100)


class ExitIn(BaseModel):
    fast: int = Field(ge=1, le=3600)
    ok: int = Field(ge=1, le=3600)
    fast_value: int = Field(ge=0, le=100)
    ok_value: int = Field(ge=0, le=100)
    slow_value: int = Field(ge=0, le=100)


class LevelIn(BaseModel):
    name: Annotated[Text, StringConstraints(min_length=2, max_length=40)]
    min: int = Field(ge=0, le=100)
    colour: Literal["green", "amber", "orange", "red"]


class ProfileConfig(BaseModel):
    axes: list[AxisIn] = Field(min_length=1, max_length=6)
    items: list[ItemIn] = Field(min_length=1, max_length=80)
    values: ValuesIn
    weights: WeightsIn
    exit: ExitIn
    levels: list[LevelIn] = Field(min_length=2, max_length=6)
    sections: list[Annotated[Text, StringConstraints(min_length=2, max_length=60)]] = Field(max_length=20)


class ProfileIn(BaseModel):
    name: Annotated[Text, StringConstraints(min_length=2, max_length=120)]
    config: ProfileConfig


class ProfileOut(BaseModel):
    id: uuid.UUID
    name: str
    version: int
    config: ProfileConfig
    created_by_name: str | None
    created_at: datetime


class OrderNotesIn(BaseModel):
    notes: list[Annotated[Text, StringConstraints(min_length=2, max_length=400)]] = Field(max_length=20)


class OrderNotesOut(BaseModel):
    notes: list[str]


class RoomDisclosure(BaseModel):
    inspection: bool
    verdict: bool
    score: bool


class RecommendationRules(BaseModel):
    high: Audience
    medium: Audience
    low: Audience
    general: Audience


class PolicyIn(BaseModel):
    central: RoomDisclosure
    regional: RoomDisclosure
    recommendations: RecommendationRules
    publish_programme: bool
    # The inspector's alerts on a mission order (Yamen 2026-11-12): a first notice so many days before the date,
    # then a reminder (0: none). Defaults so that a policy saved before them stays valid.
    notice_days: int = Field(15, ge=1, le=60)
    reminder_days: int = Field(2, ge=0, le=14)


class PolicyOut(PolicyIn):
    updated_by_name: str | None
    updated_at: datetime


# ---------------------------------------------------------------- inspectors


class RegisterIn(BaseModel):
    """A registration typed on the app; no account yet."""

    kind: Literal["internal", "external"]
    matricule: Matricule
    name: Name
    organisation: Annotated[Text, StringConstraints(min_length=2, max_length=160)] | None = None
    phone: Phone | None = None
    email: EmailStr | None = None
    via: Literal["sms", "email"]
    device_model: Annotated[Text, StringConstraints(max_length=80)] | None = None


class RegisterOut(BaseModel):
    status: Literal["pending"]
    # Where the code will go, masked (+216 •• ••• 905, n•••@protectioncivile.tn).
    destination: str


class InspectorOut(BaseModel):
    id: uuid.UUID
    kind: Literal["internal", "external"]
    matricule: str
    name: str
    organisation: str | None
    phone: str | None
    email: str | None
    via: Literal["sms", "email"]
    status: InspectorStatus
    expires_on: date | None
    matched_agent: bool
    requested_device: str | None
    requested_at: datetime
    decided_at: datetime | None
    decided_by_name: str | None
    reject_reason: str | None
    code_expires_at: datetime | None
    activated_at: datetime | None
    device_model: str | None
    last_seen_at: datetime | None
    lost_at: datetime | None


class ActivateIn(BaseModel):
    """The inspector general activates a registration; an external inspector's account needs its end date."""

    expires_on: date | None = None


class RejectIn(BaseModel):
    reason: Reason


class AppDevice(BaseModel):
    platform: Literal["android", "ios"]
    model: Annotated[Text, StringConstraints(max_length=80)] | None = None
    device_ref: Annotated[Text, StringConstraints(max_length=80)] | None = None
    push_token: Annotated[str, StringConstraints(max_length=4096)] | None = None


class AppActivateIn(BaseModel):
    matricule: Matricule
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=12)]
    device: AppDevice


class AppRefreshIn(BaseModel):
    refresh_token: Annotated[str, StringConstraints(min_length=20, max_length=200)]


class AppTokens(BaseModel):
    access_token: str
    expires_at: datetime
    refresh_token: str
    name: str
    kind: Literal["internal", "external"]
    expires_on: date | None


# ---------------------------------------------------------------- missions


class SiteIn(BaseModel):
    """A unit: its gouvernorat, its kind and its name (the register's id is optional); or an operations room."""

    target: Target
    unit_kind: UnitKind | None = None
    unit_name: UnitName | None = None
    unit_id: uuid.UUID | None = None
    room: RoomKind | None = None
    gouvernorat_code: int | None = Field(default=None, ge=1, le=99)
    sections: list[Annotated[Text, StringConstraints(min_length=2, max_length=60)]] = Field(
        default_factory=list, max_length=20
    )


class MissionIn(BaseModel):
    on_date: date
    at_time: time
    kind: Kind
    inspector_id: uuid.UUID
    sites: list[SiteIn] = Field(min_length=1, max_length=10)
    publish: bool = False


class CancelIn(BaseModel):
    reason: Reason


class SiteOut(BaseModel):
    id: uuid.UUID
    position: int
    target: Target
    unit_kind: UnitKind | None
    unit_name: str | None
    unit_id: uuid.UUID | None
    room: RoomKind | None
    name: str
    gouvernorat_code: int | None
    sections: list[str]
    inspection_id: uuid.UUID | None
    inspection_status: Literal["in_progress", "submitted"] | None
    arrived_at: datetime | None = None
    arrived_offline: bool = False
    left_at: datetime | None = None
    left_offline: bool = False


class MissionOut(BaseModel):
    id: uuid.UUID
    ref: str
    on_date: date
    at_time: time
    kind: Kind
    inspector_id: uuid.UUID
    inspector_name: str
    status: Literal["planned", "live", "done", "cancelled"]
    cancel_reason: str | None
    published: bool
    sites: list[SiteOut]
    created_by_name: str | None
    created_at: datetime


class OrderVerifyOut(BaseModel):
    """What the QR code of a mission order shows to anyone: enough to tell a real order from a forged one."""

    ref: str
    on_date: date
    inspector_name: str
    places: int
    valid: bool


# ---------------------------------------------------------------- the inspection (app)


class StartIn(BaseModel):
    site_id: uuid.UUID
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    started_at: datetime | None = None


class PresenceIn(BaseModel):
    """«Arrived» or «left» on a place, at the phone's time; ``offline`` when it was recorded without network."""

    kind: Literal["arrived", "left"]
    at: datetime
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    offline: bool = False


class PresenceOut(BaseModel):
    site_id: uuid.UUID
    arrived_at: datetime | None
    arrived_offline: bool
    left_at: datetime | None
    left_offline: bool


class ProgressIn(BaseModel):
    answers: dict[Annotated[str, StringConstraints(pattern=r"^[a-z]{1,8}[0-9]{1,3}$")], Answer] = Field(
        default_factory=dict, max_length=80
    )
    present: int | None = Field(default=None, ge=0, le=1000)
    expected: int | None = Field(default=None, ge=1, le=1000)
    exit_seconds: int | None = Field(default=None, ge=0, le=3600)


class RecommendationIn(BaseModel):
    kind: Literal["detailed", "general"]
    item_key: Annotated[str, StringConstraints(pattern=r"^[a-z]{1,8}[0-9]{1,3}$")] | None = None
    text: Annotated[Text, StringConstraints(min_length=2, max_length=600)]
    priority: Priority | None = None


class SubmitIn(ProgressIn):
    client_id: uuid.UUID
    summary: Annotated[Text, StringConstraints(max_length=4000)] | None = None
    recommendations: list[RecommendationIn] = Field(default_factory=list, max_length=60)
    head_name: Name
    # PNG images, base64 (data URL prefix allowed), 200 kB each at most.
    inspector_signature: Annotated[str, StringConstraints(min_length=20, max_length=280_000)]
    head_signature: Annotated[str, StringConstraints(min_length=20, max_length=280_000)]
    signed_at: datetime


class ReceiptOut(BaseModel):
    inspection_id: uuid.UUID
    receipt: str
    score: int
    verdict: str
    received_at: datetime


class AppSiteOut(SiteOut):
    head_hint: str | None = None


class AppMissionOut(BaseModel):
    id: uuid.UUID
    ref: str
    on_date: date
    at_time: time
    kind: Kind
    sites: list[SiteOut]
    # The active model, so that the app opens a report on the place without network (Yamen 2026-11-12):
    # the server keeps the version it holds when the report reaches it.
    profile: ProfileConfig | None = None


class AppHistoryRow(BaseModel):
    """One report of the inspector, for «my inspections» in the app."""

    id: uuid.UUID
    site_id: uuid.UUID
    mission_ref: str
    on_date: date
    kind: Kind
    place: str
    status: Literal["in_progress", "submitted"]
    started_at: datetime
    submitted_at: datetime | None
    score: int | None
    verdict: str | None
    receipt: str | None


class AppInspectionOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    status: Literal["in_progress", "submitted"]
    profile: ProfileConfig
    answers: dict[str, Answer]
    present: int | None
    expected: int | None
    exit_seconds: int | None
    score: int | None
    verdict: str | None
    receipt: str | None


# ---------------------------------------------------------------- records and disclosure


class RecommendationOut(BaseModel):
    id: uuid.UUID
    kind: Literal["detailed", "general"]
    item_key: str | None
    text: str
    priority: Priority | None
    audience: Audience


class RecordRow(BaseModel):
    id: uuid.UUID
    mission_ref: str
    kind: Kind
    target: Target
    unit_kind: UnitKind | None
    room: RoomKind | None
    place: str
    gouvernorat_code: int | None
    inspector_name: str
    status: Literal["in_progress", "submitted"]
    started_at: datetime
    submitted_at: datetime | None
    score: int | None
    verdict: str | None
    previous_score: int | None
    receipt: str | None


class RecordOut(RecordRow):
    answers: dict[str, Answer]
    present: int | None
    expected: int | None
    exit_seconds: int | None
    summary: str | None
    head_name: str | None
    signed_at: datetime | None
    profile_name: str
    profile_version: int
    disclosure: dict[str, RoomDisclosure]
    recommendations: list[RecommendationOut]


class DisclosureIn(BaseModel):
    room: RoomKind
    inspection: bool | None = None
    verdict: bool | None = None
    score: bool | None = None


class AudienceIn(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=60)
    audience: Audience


class DashboardOut(BaseModel):
    month_missions: int
    month_done: int
    month_planned: int
    rooms_without_plan: int
    average_score: int | None
    by_month: list[dict[str, int | str]]
    levels: dict[str, int]


class UnitStatusOut(BaseModel):
    target: Target
    unit_kind: UnitKind | None
    unit_name: str | None
    room: RoomKind | None
    name: str
    gouvernorat_code: int | None
    last_inspection_id: uuid.UUID | None
    last_on: datetime | None
    last_score: int | None
    last_verdict: str | None
    next_on: date | None


# ---------------------------------------------------------------- rooms


class RoomResultOut(BaseModel):
    id: uuid.UUID
    room: RoomKind
    place: str
    gouvernorat_code: int | None
    kind: Kind
    submitted_at: datetime
    verdict: str | None
    score: int | None
    recommendations: list[RecommendationOut]


class RoomLiveOut(BaseModel):
    id: uuid.UUID
    room: RoomKind
    place: str
    gouvernorat_code: int | None
    inspector_name: str
    started_at: datetime
    answered: int
    items: int
    score: int | None


class RoomUpcomingOut(BaseModel):
    ref: str
    room: RoomKind
    place: str
    gouvernorat_code: int | None
    on_date: date
    kind: Kind


# ---------------------------------------------------------------- the system administrator


class DeleteIn(BaseModel):
    scope: Literal["one", "period", "all"]
    inspection_id: uuid.UUID | None = None
    from_date: date | None = None
    to_date: date | None = None
    reason: Annotated[Text, StringConstraints(min_length=10, max_length=500)]
    confirm: str


class DeleteOut(BaseModel):
    deleted: int


class BinRow(BaseModel):
    id: uuid.UUID
    place: str
    submitted_at: datetime | None
    deleted_at: datetime
    deleted_by_name: str | None
    delete_reason: str | None
