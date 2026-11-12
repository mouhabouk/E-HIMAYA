"""Address warnings, OS8: request and response bodies."""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.modules.reports.schemas import LocationIn as LocationIn

Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
Text500 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=500)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=300)]
Minutes = Annotated[int, Field(ge=0, le=1440)]
RoomSource = Literal["room", "org", "municipality", "report"]
Status = Literal["pending", "active", "archived", "rejected", "withdrawn"]

#: Incident kinds a category can be critical with (the report categories of the rooms).
INCIDENT_KINDS = (
    "fire",
    "chemical_leak",
    "landslide",
    "flood",
    "traffic_accident",
    "drowning",
    "medical",
    "sos",
    "other",
)
IncidentKind = Literal[
    "fire", "chemical_leak", "landslide", "flood", "traffic_accident", "drowning", "medical", "sos", "other"
]


class Point(BaseModel):
    lat: float
    lon: float


class CategoryOut(BaseModel):
    key: str
    name: str
    icon: str
    colour: str
    personal: bool
    radius_m: int
    review_months: int
    team: bool
    critical_with: list[str]
    examples: list[str]
    updated_by_name: str | None = None


class CategoryIn(BaseModel):
    radius_m: int = Field(ge=20, le=1000)
    review_months: int = Field(ge=1, le=36)
    team: bool
    critical_with: list[IncidentKind] = Field(max_length=len(INCIDENT_KINDS))


class Hours(BaseModel):
    start: Minutes
    end: Minutes


class MarkerIn(BaseModel):
    category: str = Field(min_length=2, max_length=20)
    location: LocationIn
    address: Address
    description: Text500
    source: RoomSource = "room"
    source_ref: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    team_visible: bool = True
    hours: Hours | None = None
    review_on: date | None = None


class MarkerPatch(BaseModel):
    address: Address | None = None
    description: Text500 | None = None
    team_visible: bool | None = None
    hours: Hours | None = None
    clear_hours: bool = False
    location: LocationIn | None = None


class DecisionIn(BaseModel):
    reason: Reason | None = None


class MarkerOut(BaseModel):
    id: uuid.UUID
    category: str
    gouvernorat_code: int | None
    location: Point
    address: str
    description: str
    source: str
    source_ref: str | None
    org_id: uuid.UUID | None
    incident_id: uuid.UUID | None
    team_visible: bool
    hours: Hours | None
    review_on: date
    review_due: bool
    status: Status
    created_at: datetime
    created_by_name: str | None
    decided_at: datetime | None
    decided_by_name: str | None
    decision_reason: str | None
    confirmed_at: datetime | None


class Counts(BaseModel):
    active: int
    pending: int
    review_due: int
    personal: int


class MarkerPage(BaseModel):
    items: list[MarkerOut]
    counts: Counts


class ImportOut(BaseModel):
    created: int


# ---------------------------------------------------------------- warnings of an incident


class Warning(BaseModel):
    marker_id: uuid.UUID
    category: str
    # The category's name, for the phone (which has no list of categories).
    category_name: str = ""
    personal: bool
    location: Point
    address: str
    # A personal mark shows the need its owner wrote, never a name.
    description: str
    source: str
    source_ref: str | None
    team_visible: bool
    distance_m: int
    critical: bool
    # Outside its hours (a nursery at night): shown greyed, never critical.
    off_hours: bool
    hours: Hours | None
    review_on: date
    room_ack_at: datetime | None = None
    room_ack_by: str | None = None
    team_ack_at: datetime | None = None
    team_ack_by: str | None = None
    revealed: bool = False


class IncidentWarnings(BaseModel):
    incident_id: uuid.UUID
    incident_kind: str
    location: Point | None
    items: list[Warning]
    unread: int


class AckIn(BaseModel):
    """The warnings read; empty = every warning shown."""

    marker_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)


class RevealIn(BaseModel):
    reason: Reason


class RevealOut(BaseModel):
    name: str | None
    phone: str | None


class RevealRow(BaseModel):
    at: datetime
    by_name: str | None
    category: str
    address: str
    incident_id: uuid.UUID | None
    reason: str


# ---------------------------------------------------------------- the team


class ProposalIn(BaseModel):
    category: str = Field(min_length=2, max_length=20)
    description: Text500
    address: Address | None = None
    location: LocationIn | None = None


# ---------------------------------------------------------------- the citizen


class NeedIn(BaseModel):
    category: Literal["mob", "oxy", "deaf"]
    description: Text500


class MyWarningsIn(BaseModel):
    location: LocationIn
    address: Address
    needs: list[NeedIn] = Field(max_length=3)

    @model_validator(mode="after")
    def _distinct(self) -> "MyWarningsIn":
        if len({n.category for n in self.needs}) != len(self.needs):
            raise ValueError("one need per category")
        return self


class MyNeed(BaseModel):
    id: uuid.UUID
    category: str
    description: str
    review_on: date


class MyReveal(BaseModel):
    at: datetime
    category: str
    reason: str


class MyWarningsOut(BaseModel):
    location: Point | None
    address: str | None
    needs: list[MyNeed]
    reveals: list[MyReveal]
    categories: list[CategoryOut]
