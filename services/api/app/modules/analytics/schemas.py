"""Request and response bodies of the analytics module (docs/api/phase-8-contract.md §1)."""

import re
import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.modules.analytics.domain import ReportFormat, ReportKind, ReportLang
from app.modules.reports.domain import Category

Text = Annotated[str, StringConstraints(strip_whitespace=True)]
LabelPair = dict[str, str]
_SUBJECT = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_HHMM = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


# ---------------------------------------------------------------- overview, trends


class KeyCount(BaseModel):
    key: str | int
    count: int


class Stage(BaseModel):
    mean_s: float | None
    p90_s: float | None
    n: int


class ResponseTimes(BaseModel):
    to_assignment: Stage
    to_on_scene: Stage
    to_closed: Stage


class Totals(BaseModel):
    received: int
    verified: int
    in_progress: int
    closed: int
    rejected: int


class IncidentCount(BaseModel):
    """Incidents opened in the period (phase 9 §5.6): attributed to their lead; ``participating`` marks those where
    the gouvernorats queried take part without leading."""

    participating: bool
    count: int


class Overview(BaseModel):
    from_: date = Field(serialization_alias="from")
    to: date
    gouvernorats: list[int]
    category: str | None
    totals: Totals
    response_time: ResponseTimes
    by_category: list[KeyCount]
    by_gouvernorat: list[KeyCount]
    by_status: list[KeyCount]
    by_source: list[KeyCount]
    by_hour: list[KeyCount]
    by_weekday: list[KeyCount]
    incidents: list[IncidentCount] = Field(default_factory=list)
    min_cell: int


class TrendPoint(BaseModel):
    period_start: date
    value: float | None
    last_year: float | None
    expected: float | None
    low: float | None
    high: float | None


class Trend(BaseModel):
    metric: str
    interval: str
    unit: Literal["count", "seconds"]
    from_: date = Field(serialization_alias="from")
    to: date
    gouvernorats: list[int]
    category: str | None
    points: list[TrendPoint]
    baseline_available: bool
    history_years: int


# ---------------------------------------------------------------- scenarios


class ScenarioIn(BaseModel):
    name: Annotated[Text, StringConstraints(min_length=1, max_length=150)]
    gouvernorats: Annotated[list[Annotated[int, Field(ge=1, le=99)]], Field(min_length=1, max_length=24)]
    category: Category | None = None
    demand_factor: Annotated[float, Field(ge=1.0, le=10.0)] = 1.0
    # Resource ids taken out, or a number of resources per kind ({"fire_engine": 2}).
    unavailable_resources: list[uuid.UUID] | dict[str, Annotated[int, Field(ge=0, le=500)]] = Field(
        default_factory=list
    )
    horizon_hours: Annotated[int, Field(ge=6, le=72)] = 24
    weather: Literal["as_forecast", "fire_danger_extreme", "heavy_rain"] = "as_forecast"
    # Same seed, same history and parameters: same result (stored with the run).
    seed: Annotated[int, Field(ge=0, le=2**53)] | None = None

    @field_validator("gouvernorats")
    @classmethod
    def _unique(cls, value: list[int]) -> list[int]:
        return sorted(set(value))


class Band(BaseModel):
    p10: float
    p50: float
    p90: float


class ScenarioOut(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    seed: int
    runs: int
    gouvernorats: list[int]
    category: str | None
    params: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    created_by: str
    created_at: datetime


class ScenarioPage(BaseModel):
    items: list[ScenarioOut]
    next_cursor: str | None


# ---------------------------------------------------------------- reports repository


class ReportFilters(BaseModel):
    category: Category | None = None
    incident_id: uuid.UUID | None = None
    scenario_id: uuid.UUID | None = None


class ReportIn(BaseModel):
    kind: ReportKind
    title: Annotated[Text, StringConstraints(min_length=1, max_length=200)]
    period_from: date
    period_to: date
    gouvernorats: Annotated[list[Annotated[int, Field(ge=1, le=99)]], Field(max_length=24)] = Field(
        default_factory=list
    )
    filters: ReportFilters = Field(default_factory=ReportFilters)
    format: ReportFormat = "pdf"
    lang: ReportLang = "ar"

    @field_validator("gouvernorats")
    @classmethod
    def _unique(cls, value: list[int]) -> list[int]:
        return sorted(set(value))


class ReportOut(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    lang: str
    period_from: date
    period_to: date
    gouvernorats: list[int]
    filters: dict[str, Any]
    format: str
    status: str
    error: str | None
    media_id: uuid.UUID | None
    sha256: str | None
    bytes: int | None
    created_by: str
    schedule_id: uuid.UUID | None
    created_at: datetime
    ready_at: datetime | None


class ReportPage(BaseModel):
    items: list[ReportOut]
    next_cursor: str | None
    # "knowledge" when the full-text part came from the events library index, "postgres" otherwise.
    search_backend: Literal["knowledge", "postgres"] | None = None


class DownloadOut(BaseModel):
    url: str


# ---------------------------------------------------------------- schedules


class Cron(BaseModel):
    frequency: Literal["daily", "weekly", "monthly"]
    # "HH:MM", local time in Africa/Tunis.
    time: Annotated[str, StringConstraints(min_length=5, max_length=5)]
    weekday: Annotated[int, Field(ge=1, le=7)] | None = None
    day: Annotated[int, Field(ge=1, le=28)] | None = None

    def valid(self) -> bool:
        """weekday only (and always) for weekly, day only (and always) for monthly."""
        return (
            bool(_HHMM.match(self.time))
            and (self.frequency == "weekly") == (self.weekday is not None)
            and (self.frequency == "monthly") == (self.day is not None)
        )


def valid_subjects(value: list[str]) -> list[str] | None:
    """Recipients normalised (lower case, unique, sorted), or None when one is not a staff subject (a UUID)."""
    cleaned = sorted({v.strip().lower() for v in value})
    return None if any(not _SUBJECT.match(v) for v in cleaned) else cleaned


class ScheduleIn(BaseModel):
    kind: Literal["period_summary", "gouvernorat_summary"]
    title: Annotated[Text, StringConstraints(min_length=1, max_length=200)]
    filters: ReportFilters = Field(default_factory=ReportFilters)
    gouvernorats: Annotated[list[Annotated[int, Field(ge=1, le=99)]], Field(max_length=24)] = Field(
        default_factory=list
    )
    format: ReportFormat = "pdf"
    lang: ReportLang = "ar"
    cron: Cron
    # Staff user ids (subjects of the staff realm) only.
    recipients: Annotated[list[str], Field(max_length=50)] = Field(default_factory=list)
    enabled: bool = True


class SchedulePatch(BaseModel):
    title: Annotated[Text, StringConstraints(min_length=1, max_length=200)] | None = None
    filters: ReportFilters | None = None
    gouvernorats: Annotated[list[Annotated[int, Field(ge=1, le=99)]], Field(max_length=24)] | None = None
    format: ReportFormat | None = None
    lang: ReportLang | None = None
    cron: Cron | None = None
    recipients: Annotated[list[str], Field(max_length=50)] | None = None
    enabled: bool | None = None


class ScheduleOut(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    filters: dict[str, Any]
    gouvernorats: list[int]
    format: str
    lang: str
    cron: Cron
    recipients: list[str]
    enabled: bool
    last_run_at: datetime | None
    next_run_at: datetime
    last_report_id: uuid.UUID | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class SchedulePage(BaseModel):
    items: list[ScheduleOut]
    next_cursor: str | None


# ---------------------------------------------------------------- staff notifications


class NotificationOut(BaseModel):
    id: int
    kind: str
    report_id: uuid.UUID
    schedule_id: uuid.UUID | None
    title: str
    created_at: datetime
    read_at: datetime | None


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    next_cursor: str | None
    unread: int
