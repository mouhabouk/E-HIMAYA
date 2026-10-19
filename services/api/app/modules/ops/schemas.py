import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.modules.reports.domain import Category
from app.modules.reports.schemas import StaffReport

IncidentStatus = Literal["open", "closed", "merged", "dissolved"]


class Point(BaseModel):
    lat: float
    lon: float


class IncidentSummary(BaseModel):
    id: uuid.UUID
    category: Category
    status: IncidentStatus
    gouvernorat_code: int | None
    centroid: Point | None
    # Highest priority among its reports (0..100).
    severity: int | None
    report_count: int
    reporter_count: int
    opened_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    merged_into: uuid.UUID | None


class TimelineEntry(BaseModel):
    at: datetime
    kind: str
    actor: str | None
    payload: dict[str, Any]


class IncidentDetail(IncidentSummary):
    reports: list[StaffReport]
    timeline: list[TimelineEntry]


class IncidentPage(BaseModel):
    items: list[IncidentSummary]
    next_cursor: str | None


class IncidentLinkIn(BaseModel):
    """accept_suggestion: follow the AI suggestion; link: into a chosen incident; new: start an incident."""

    action: Literal["accept_suggestion", "link", "new"]
    incident_id: uuid.UUID | None = None


class MergeIn(BaseModel):
    # The incident absorbed into the one in the path (its reports move, it becomes "merged").
    incident_id: uuid.UUID
