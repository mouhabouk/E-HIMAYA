from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Kind = Literal["road", "seasonal", "beach", "other"]
Status = Literal["draft", "approved", "updated", "ended", "cancelled"]
PointStatus = Literal["open", "closed", "postponed"]
Confidence = Literal["confirmed", "high", "medium", "approximate", "review", "unknown"]
CODE = r"^[A-Z]+-[0-9]{4}(-[A-Z0-9]+)?$"


class Figures(BaseModel):
    points: int = 0
    unlocated: int = 0
    open: int = 0
    gouvernorats: int = 0
    staff: int = 0
    lifeguards_planned: int = 0
    lifeguards_deployed: int = 0


class ProgrammeOut(BaseModel):
    id: str
    code: str
    kind: Kind
    title: str
    season: str
    valid_from: date
    valid_to: date
    status: Status
    version: int
    source_document: str
    declared: dict[str, int]
    approved_by_name: str | None
    approved_at: datetime | None
    cancel_reason: str | None
    layer_key: str | None
    # On the maps today: approved or updated, and today within the validity dates.
    live: bool
    updated_by_name: str | None
    updated_at: datetime
    figures: Figures
    can_edit: bool
    can_follow_up: bool


class ProgrammesOut(BaseModel):
    items: list[ProgrammeOut]
    can_create: bool


class PointOut(BaseModel):
    id: str
    ref: str
    gouvernorat_code: int | None
    place_name: str
    sub_points: str | None
    lat: float | None
    lon: float | None
    geo_confidence: Confidence
    geo_note: str | None
    staff_count: int | None
    staff_composition: str | None
    supervisors: int | None
    lifeguards_planned: int | None
    lifeguards_deployed: int | None
    equipment: str | None
    hours: str | None
    opening_date: date | None
    closing_date: date | None
    status: PointStatus
    # The supervisor's name and phone: the operations rooms only (null for everyone else).
    supervisor_name: str | None
    supervisor_phone: str | None
    notes: str | None
    updated_at: datetime
    can_follow_up: bool


class ProgrammeDetail(BaseModel):
    programme: ProgrammeOut
    points: list[PointOut]
    computed: dict[str, int]


class ProgrammeIn(BaseModel):
    code: str = Field(pattern=CODE, max_length=40)
    kind: Kind
    title: str = Field(min_length=3, max_length=300)
    season: str = Field(default="", max_length=80)
    valid_from: date
    valid_to: date
    source_document: str = Field(default="", max_length=300)


class ProgrammePatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=300)
    season: str | None = Field(default=None, max_length=80)
    valid_from: date | None = None
    valid_to: date | None = None
    source_document: str | None = Field(default=None, max_length=300)
    reason: str = Field(default="", max_length=500)


class ReasonIn(BaseModel):
    reason: str = Field(default="", max_length=500)


class CopyIn(BaseModel):
    code: str = Field(pattern=CODE, max_length=40)
    valid_from: date
    valid_to: date
    season: str = Field(default="", max_length=80)
    title: str | None = Field(default=None, min_length=3, max_length=300)


class PointIn(BaseModel):
    ref: str = Field(min_length=1, max_length=60)
    gouvernorat_code: int | None = Field(default=None, ge=11, le=83)
    place_name: str = Field(min_length=2, max_length=300)
    sub_points: str | None = Field(default=None, max_length=500)
    lat: float | None = Field(default=None, ge=30.0, le=37.6)
    lon: float | None = Field(default=None, ge=7.4, le=11.7)
    geo_confidence: Confidence | None = None
    staff_count: int | None = Field(default=None, ge=0)
    staff_composition: str | None = Field(default=None, max_length=300)
    supervisors: int | None = Field(default=None, ge=0)
    lifeguards_planned: int | None = Field(default=None, ge=0)
    lifeguards_deployed: int | None = Field(default=None, ge=0)
    equipment: str | None = Field(default=None, max_length=300)
    hours: str | None = Field(default=None, max_length=200)
    opening_date: date | None = None
    closing_date: date | None = None
    status: PointStatus = "open"
    supervisor_name: str | None = Field(default=None, max_length=120)
    supervisor_phone: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=1000)
    reason: str = Field(default="", max_length=500)


class PointPatch(BaseModel):
    """Every field is optional: only the fields sent change. A regional room may send status, lifeguards_deployed
    and notes only (the daily follow-up)."""

    gouvernorat_code: int | None = Field(default=None, ge=11, le=83)
    place_name: str | None = Field(default=None, min_length=2, max_length=300)
    sub_points: str | None = Field(default=None, max_length=500)
    lat: float | None = Field(default=None, ge=30.0, le=37.6)
    lon: float | None = Field(default=None, ge=7.4, le=11.7)
    geo_confidence: Confidence | None = None
    staff_count: int | None = Field(default=None, ge=0)
    staff_composition: str | None = Field(default=None, max_length=300)
    supervisors: int | None = Field(default=None, ge=0)
    lifeguards_planned: int | None = Field(default=None, ge=0)
    lifeguards_deployed: int | None = Field(default=None, ge=0)
    equipment: str | None = Field(default=None, max_length=300)
    hours: str | None = Field(default=None, max_length=200)
    opening_date: date | None = None
    closing_date: date | None = None
    status: PointStatus | None = None
    supervisor_name: str | None = Field(default=None, max_length=120)
    supervisor_phone: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=1000)
    reason: str = Field(default="", max_length=500)


class RevisionOut(BaseModel):
    number: int
    action: str
    reason: str | None
    created_by_name: str | None
    created_at: datetime
    points: int


class RevisionsOut(BaseModel):
    items: list[RevisionOut]


class DiffOut(BaseModel):
    number: int
    against: int | None
    programme: dict[str, list[Any]]
    added: list[str]
    removed: list[str]
    changed: dict[str, dict[str, list[Any]]]


class ProblemOut(BaseModel):
    code: str
    programme: str | None = None
    ref: str | None = None
    line: int | None = None
    value: str | None = None


class ImportedProgramme(BaseModel):
    code: str
    title: str | None
    kind: Kind | None
    exists: bool
    status: Status | None
    points: int
    unlocated: int
    computed: dict[str, int]
    declared: dict[str, int]
    # For a programme already in the system: what the file changes.
    diff: DiffOut | None


class ImportOut(BaseModel):
    format: str
    applied: bool
    programmes: list[ImportedProgramme]
    errors: list[ProblemOut]
    warnings: list[ProblemOut]
