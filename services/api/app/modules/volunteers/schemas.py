import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

Skill = Literal[
    "first_aid", "diving", "heavy_vehicles", "firefighting", "search_rescue", "logistics", "medical", "other"
]
Availability = Literal["continuous", "intermittent"]
VolunteerStatus = Literal["pending", "approved", "rejected", "suspended", "withdrawn"]
Text = Annotated[str, StringConstraints(strip_whitespace=True)]


class VolunteerIn(BaseModel):
    skills: list[Skill] = Field(min_length=1, max_length=8)
    other_skill: Annotated[Text, StringConstraints(max_length=100)] | None = None
    availability: Availability
    period_from: date
    period_to: date | None = None
    notes: Annotated[Text, StringConstraints(max_length=500)] | None = None
    version: int | None = None


class VolunteerOut(BaseModel):
    status: VolunteerStatus
    skills: list[Skill]
    other_skill: str | None
    availability: Availability
    period_from: date
    period_to: date | None
    notes: str | None
    review_reason: str | None
    submitted_at: datetime
    reviewed_at: datetime | None
    ready: bool
    ready_until: datetime | None
    version: int


class ReadinessIn(BaseModel):
    ready: bool
    lat: float | None = Field(default=None, ge=30.0, le=37.6)
    lon: float | None = Field(default=None, ge=7.4, le=11.7)
    accuracy_m: float | None = Field(default=None, ge=0, le=100_000)
    hours: int = Field(default=8, ge=1, le=24)


class LocationIn(BaseModel):
    lat: float = Field(ge=30.0, le=37.6)
    lon: float = Field(ge=7.4, le=11.7)
    accuracy_m: float | None = Field(default=None, ge=0, le=100_000)


class StaffVolunteer(BaseModel):
    id: uuid.UUID
    full_name: str | None
    phone: str | None
    gouvernorat_code: int
    skills: list[Skill]
    availability: Availability
    period_from: date
    period_to: date | None
    status: VolunteerStatus
    ready: bool
    ready_until: datetime | None
    submitted_at: datetime


class StaffVolunteerPage(BaseModel):
    items: list[StaffVolunteer]
    next_cursor: str | None


class VolunteerReviewOut(BaseModel):
    decision: str
    reason: str | None
    at: datetime


class VolunteerCalloutRef(BaseModel):
    callout_id: uuid.UUID
    incident_id: uuid.UUID
    skill: str
    status: str
    sent_at: datetime
    responded_at: datetime | None


class StaffVolunteerDetail(StaffVolunteer):
    email: str | None
    other_skill: str | None
    notes: str | None
    review_reason: str | None
    reviews: list[VolunteerReviewOut]
    callouts: list[VolunteerCalloutRef]


class VolunteerReviewIn(BaseModel):
    decision: Literal["approve", "reject", "suspend", "reinstate"]
    reason: Annotated[Text, StringConstraints(max_length=1000)] | None = None


class MyCallout(BaseModel):
    id: uuid.UUID
    incident_category: str
    message: str | None
    skill: str
    distance_m: int | None
    location: dict[str, float] | None
    status: str
    my_status: str
    eta_minutes: int | None
    created_at: datetime


class RespondIn(BaseModel):
    response: Literal["accept", "decline"]
    eta_minutes: int | None = Field(default=None, ge=1, le=600)
