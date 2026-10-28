import uuid
from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.modules.schedule.domain import Approval, Repeat, Span

Text = Annotated[str, StringConstraints(strip_whitespace=True)]
Reason = Annotated[Text, StringConstraints(min_length=5, max_length=1000)]
Code = Annotated[int, Field(ge=11, le=83)]
Activity = Literal[
    "duty",
    "patrol",
    "exercise",
    "prevention_visit",
    "maintenance",
    "training",
    "awareness",
    "readiness_check",
    "meeting",
    "other",
]
PeriodStatus = Literal["draft", "submitted", "awaiting_centre", "approved", "returned"]
ItemStatus = Literal["planned", "done", "postponed", "cancelled"]
CategoryKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]


class SettingOut(BaseModel):
    gouvernorat_code: int
    gouvernorat_name: str | None
    approval: Approval
    updated_by_name: str | None
    updated_at: datetime | None
    can_edit: bool


class SettingIn(BaseModel):
    approval: Approval


class PeriodIn(BaseModel):
    gouvernorat_code: Code | None = None
    span: Span
    on: date


class PeriodNotes(BaseModel):
    version: int
    notes: Annotated[Text, StringConstraints(max_length=4000)] = ""


class Step(BaseModel):
    version: int


class ReturnIn(BaseModel):
    version: int
    reason: Reason


class Resource(BaseModel):
    category_key: CategoryKey
    qty: Annotated[int, Field(ge=1, le=1000)]


class ItemIn(BaseModel):
    activity: Activity
    title: Annotated[Text, StringConstraints(min_length=2, max_length=300)]
    on_date: date
    starts_at: time | None = None
    ends_at: time | None = None
    unit_id: uuid.UUID | None = None
    place: Annotated[Text, StringConstraints(max_length=300)] = ""
    responsible: Annotated[Text, StringConstraints(max_length=200)] = ""
    staff_count: Annotated[int, Field(ge=0, le=10000)] | None = None
    resources: Annotated[list[Resource], Field(max_length=20)] = Field(default_factory=list)
    plan_document_id: uuid.UUID | None = None
    notes: Annotated[Text, StringConstraints(max_length=2000)] = ""


class ItemCreate(ItemIn):
    repeat: Repeat = "none"


class ItemStatusIn(BaseModel):
    status: ItemStatus
    reason: Annotated[Text, StringConstraints(max_length=1000)] = ""


class ResourceOut(BaseModel):
    category_key: str
    name: dict[str, str]
    qty: int


class ItemOut(BaseModel):
    id: uuid.UUID
    series_id: uuid.UUID | None
    activity: str
    title: str
    on_date: date
    starts_at: time | None
    ends_at: time | None
    unit_id: uuid.UUID | None
    unit_name: str | None
    place: str
    responsible: str
    staff_count: int | None
    resources: list[ResourceOut]
    plan_document_id: uuid.UUID | None
    plan_title: str | None
    notes: str
    status: ItemStatus
    status_reason: str | None
    status_by_name: str | None
    status_at: datetime | None


class Counts(BaseModel):
    items: int = 0
    due: int = 0
    done: int = 0
    postponed: int = 0
    cancelled: int = 0
    # Done among the activities whose day has come (cancelled ones left out); None when nothing is due yet.
    rate: float | None = None


class PeriodOut(BaseModel):
    id: uuid.UUID
    gouvernorat_code: int
    gouvernorat_name: str | None
    span: Span
    starts_on: date
    ends_on: date
    status: PeriodStatus
    approval: Approval
    notes: str
    return_reason: str | None
    submitted_by_name: str | None
    submitted_at: datetime | None
    approved_by_name: str | None
    approved_at: datetime | None
    centre_approved_by_name: str | None
    centre_approved_at: datetime | None
    version: int
    created_by_name: str | None
    updated_by_name: str | None
    updated_at: datetime
    counts: Counts


class PeriodDetail(BaseModel):
    period: PeriodOut
    items: list[ItemOut]
    can_edit: bool
    can_submit: bool
    can_approve: bool
    can_return: bool
    can_follow_up: bool
    can_delete: bool
    previous_id: uuid.UUID | None


class PeriodSlot(BaseModel):
    """The period of a gouvernorat that contains a day, recorded or not yet."""

    gouvernorat_code: int
    span: Span
    starts_on: date
    ends_on: date
    period: PeriodDetail | None
    can_create: bool


class ProgressRow(BaseModel):
    gouvernorat_code: int
    gouvernorat_name: str | None
    approval: Approval
    period_id: uuid.UUID | None
    status: PeriodStatus | None
    counts: Counts


class ProgressOut(BaseModel):
    span: Span
    starts_on: date
    ends_on: date
    rows: list[ProgressRow]
    lists: bool


class UnitOption(BaseModel):
    id: uuid.UUID
    name: str


class CategoryOption(BaseModel):
    key: str
    kind: str
    name: dict[str, str]


class PlanOption(BaseModel):
    id: uuid.UUID
    title: str
    hazard_key: str | None


class Options(BaseModel):
    units: list[UnitOption]
    categories: list[CategoryOption]
    plans: list[PlanOption]


TemplateName = Annotated[Text, StringConstraints(min_length=2, max_length=120)]


class TemplateIn(BaseModel):
    name: TemplateName


class ApplyTemplate(BaseModel):
    version: int
    template_id: uuid.UUID


class TemplateOut(BaseModel):
    id: uuid.UUID
    gouvernorat_code: int
    span: Span
    name: str
    items: int
    activities: dict[str, int]
    created_by_name: str | None
    created_at: datetime
    updated_by_name: str | None
    updated_at: datetime
