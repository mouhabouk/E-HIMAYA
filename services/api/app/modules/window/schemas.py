import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Lang = Literal["ar", "fr", "en"]


class Filters(BaseModel):
    """The criteria of a search, of each side of a comparison and of an export (L4 §3.2)."""

    model_config = ConfigDict(populate_by_name=True)

    q: str | None = Field(default=None, max_length=200)
    from_: date | None = Field(default=None, alias="from")
    to: date | None = None
    gouvernorats: list[int] = Field(default_factory=list, max_length=24)
    delegation: int | None = None
    category: list[str] = Field(default_factory=list, max_length=20)
    classification: list[str] = Field(default_factory=list, max_length=40)
    severity: list[int] = Field(default_factory=list, max_length=5)
    status: list[Literal["open", "closed"]] = Field(default_factory=list, max_length=2)
    source: list[str] = Field(default_factory=list, max_length=5)
    unit: uuid.UUID | None = None
    org: uuid.UUID | None = None


class Understood(BaseModel):
    """How one word or phrase of the quick search was read."""

    text: str
    # category | classification | gouvernorat | delegation | reference | word | unmatched
    kind: str
    key: str | None = None


class Cell(BaseModel):
    key: str
    # None: fewer than the floor (L4 §3.5), shown "<5".
    count: int | None


class Figures(BaseModel):
    incidents: int | None
    by_category: list[Cell]
    by_severity: list[Cell]
    by_status: list[Cell]
    by_gouvernorat: list[Cell]
    series_step: Literal["day", "month"]
    series: list[Cell]
    injured: int | None
    deceased: int | None
    rescued: int | None
    burned_ha: float | None
    to_assignment_min: float | None
    to_on_scene_min: float | None
    reports: int | None
    confirmed: int | None
    confirmed_rate: float | None


class IncidentRow(BaseModel):
    id: uuid.UUID
    ref: str
    category: str
    classification: str | None
    severity: int | None
    status: str
    gouvernorat_code: int | None
    delegation_id: int | None
    opened_at: datetime
    closed_at: datetime | None
    axis_number: str | None


class SearchOut(BaseModel):
    from_: date = Field(serialization_alias="from")
    to: date
    gouvernorats: list[int]
    understood: list[Understood]
    figures: Figures
    items: list[IncidentRow]
    truncated: bool
    delegated: bool
    min_cell: int


class Programmes(BaseModel):
    programmes: int
    posts: int
    lifeguards_planned: int
    lifeguards_deployed: int
    activities_due: int
    activities_done: int
    rate: float | None


class Side(BaseModel):
    label: str
    from_: date = Field(serialization_alias="from")
    to: date
    gouvernorats: list[int]
    figures: Figures
    programmes: Programmes | None


class CompareRow(BaseModel):
    # incidents | injured | ... | category | severity | status | gouvernorat
    metric: str
    key: str | None = None
    a: float | None
    b: float | None
    delta: float | None
    pct: float | None


class CompareIn(BaseModel):
    filters: Filters = Field(default_factory=Filters)
    mode: Literal["periods", "gouvernorats"] = "periods"
    # periods: two free periods; gouvernorats: two gouvernorats over the period of the filters.
    a_from: date | None = None
    a_to: date | None = None
    b_from: date | None = None
    b_to: date | None = None
    a_gouvernorat: int | None = None
    b_gouvernorat: int | None = None


class CompareOut(BaseModel):
    mode: Literal["periods", "gouvernorats"]
    a: Side
    b: Side
    rows: list[CompareRow]
    delegated: bool
    min_cell: int


# ---------------------------------------------------------------- the situation now


class AxisNow(BaseModel):
    id: uuid.UUID
    number: str
    name: str
    kind: str
    level: int
    scope: str
    gouvernorat_code: int | None
    opened_at: datetime
    plan: str
    plan_document_id: uuid.UUID | None
    plan_title: str | None
    incidents: int


class ResourceNow(BaseModel):
    kind: str
    available: int
    assigned: int
    out_of_service: int


class ProgressNow(BaseModel):
    gouvernorat_code: int
    gouvernorat_name: str
    day_due: int
    day_done: int
    day_rate: float | None
    week_due: int
    week_done: int
    week_rate: float | None


class DecisionNow(BaseModel):
    id: uuid.UUID
    axis_id: uuid.UUID
    axis_number: str
    number: int
    kind: str
    category: str
    body: str
    issuer_role: str
    issued_at: datetime
    status: str


class NowOut(BaseModel):
    at: datetime
    delegated: bool
    axes: list[AxisNow]
    open_incidents: list[Cell]
    open_total: int
    resources: list[ResourceNow] | None
    progress: list[ProgressNow] | None
    decisions: list[DecisionNow]


# ---------------------------------------------------------------- access, delegations


class EventRef(BaseModel):
    kind: Literal["axis", "incident"]
    id: uuid.UUID


class EventOut(EventRef):
    label: str
    gouvernorat_code: int | None
    added_by_name: str | None
    added_at: datetime


class DelegationIn(BaseModel):
    grantee: str = Field(min_length=1, max_length=255)
    reason: str = Field(min_length=5, max_length=500)
    starts_at: datetime | None = None
    ends_at: datetime
    events: list[EventRef] = Field(min_length=1, max_length=50)


class EventsIn(BaseModel):
    events: list[EventRef] = Field(min_length=1, max_length=50)


class RevokeIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class DelegationOut(BaseModel):
    id: uuid.UUID
    grantee: str
    grantee_name: str | None
    grantee_roles: list[str]
    grantee_gouvernorat: int | None
    reason: str
    starts_at: datetime
    ends_at: datetime
    granted_by_name: str | None
    granted_room: str
    created_at: datetime
    revoked_at: datetime | None
    revoked_by_name: str | None
    revoke_reason: str | None
    # active | scheduled | ended | revoked
    state: str
    events: list[EventOut]


class Delegate(BaseModel):
    id: str
    name: str
    roles: list[str]
    gouvernorat_code: int | None


class AccessOut(BaseModel):
    full: bool
    delegated: bool
    may_delegate: bool
    keeps_dictionary: bool
    delegations: list[DelegationOut]


# ---------------------------------------------------------------- saved searches, synonyms, export


class SavedIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["search", "compare"]
    query: dict[str, object]


class SavedOut(SavedIn):
    id: uuid.UUID
    created_at: datetime


class SynonymIn(BaseModel):
    meaning: str = Field(min_length=1, max_length=80)
    words: list[str] = Field(min_length=1, max_length=50)


class SynonymOut(SynonymIn):
    id: uuid.UUID
    updated_by_name: str | None
    updated_at: datetime


class ExportIn(BaseModel):
    kind: Literal["search", "compare"]
    format: Literal["pdf", "xlsx"]
    lang: Lang = "ar"
    filters: Filters = Field(default_factory=Filters)
    compare: CompareIn | None = None


class SummaryIn(BaseModel):
    kind: Literal["search", "compare"]
    lang: Lang = "ar"
    filters: Filters = Field(default_factory=Filters)
    compare: CompareIn | None = None


class SummaryOut(BaseModel):
    text: str
    # False: the model's answer was refused (not JSON, or a number that is not one of the figures).
    supported: bool
    model: str
    notice: str
    generated_at: datetime
