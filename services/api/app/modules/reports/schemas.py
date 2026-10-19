import uuid
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

from app.modules.reports.domain import LAT_MAX, LAT_MIN, LON_MAX, LON_MIN, Category, Lang, Status


class LocationIn(BaseModel):
    lat: float = Field(ge=LAT_MIN, le=LAT_MAX)
    lon: float = Field(ge=LON_MIN, le=LON_MAX)
    accuracy_m: float | None = Field(default=None, ge=0, le=100_000)


class LocationOut(BaseModel):
    lat: float
    lon: float
    accuracy_m: float | None


class ReportIn(BaseModel):
    client_uuid: uuid.UUID
    category: Category
    text: str | None = Field(default=None, max_length=4000)
    lang: Lang | None = None
    location: LocationIn
    created_at: AwareDatetime


class MediaOut(BaseModel):
    id: uuid.UUID
    kind: str
    bytes: int | None
    sha256: str
    content_type: str | None
    status: str
    created_at: datetime


class StaffMediaOut(MediaOut):
    url: str | None = None


class ReportOut(BaseModel):
    id: uuid.UUID
    tracking_code: str
    client_uuid: uuid.UUID | None
    category: Category
    status: Status
    text: str | None
    lang: str | None
    location: LocationOut
    gouvernorat_code: int | None
    created_at: datetime
    received_at: datetime
    updated_at: datetime
    media: list[MediaOut]


class ReportPage(BaseModel):
    items: list[ReportOut]
    next_before: datetime | None


class CategoryOut(BaseModel):
    code: Category
    label: str


class HistoryEntry(BaseModel):
    status: Status
    at: datetime


class TrackOut(BaseModel):
    tracking_code: str
    status: Status
    received_at: datetime
    updated_at: datetime
    history: list[HistoryEntry]


# ---------------------------------------------------------------- staff


class StaffReport(BaseModel):
    id: uuid.UUID
    tracking_code: str
    category: Category
    status: Status
    text: str | None
    lang: str | None
    location: LocationOut
    gouvernorat_code: int | None
    delegation_id: int | None
    reporter_kind: Literal["citizen", "organization", "anonymous"]
    media_count: int
    created_at: datetime
    received_at: datetime
    updated_at: datetime


class StaffHistoryEntry(BaseModel):
    status: Status
    at: datetime
    actor: str
    note: str | None


class Reporter(BaseModel):
    kind: Literal["citizen", "organization", "anonymous"]
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None


class StaffReportDetail(StaffReport):
    history: list[StaffHistoryEntry]
    media: list[StaffMediaOut]
    reporter: Reporter
    allowed_transitions: list[Status]


class StaffReportPage(BaseModel):
    items: list[StaffReport]
    next_cursor: str | None


class StatusChangeIn(BaseModel):
    status: Status
    note: str | None = Field(default=None, max_length=1000)


class GouvernoratCount(BaseModel):
    code: int | None
    count: int


class Kpis(BaseModel):
    since: datetime
    total: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    by_gouvernorat: list[GouvernoratCount]
    avg_first_response_s: float | None
