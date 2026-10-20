import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.modules.ops.domain import (
    AssignmentStatus,
    CalloutStatus,
    Outcome,
    ResourceKind,
    ResourceStatus,
    TargetStatus,
    UnitKind,
)
from app.modules.ops.models import OpLevel
from app.modules.reports.domain import Category
from app.modules.reports.schemas import StaffReport

IncidentStatus = Literal["open", "closed", "merged", "dissolved"]
CommandLevel = Literal["regional", "central"]
RequestStatus = Literal["pending", "approved", "refused", "cancelled"]
Text = Annotated[str, StringConstraints(strip_whitespace=True)]
Reason = Annotated[Text, StringConstraints(min_length=5, max_length=500)]


class Point(BaseModel):
    lat: float
    lon: float


class IncidentSummary(BaseModel):
    id: uuid.UUID
    category: Category
    status: IncidentStatus
    # Lead gouvernorat (phase 9); ``lead_gouvernorat_code`` repeats it under its explicit name.
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
    title: str | None = None
    classification: str | None = None
    op_level: OpLevel = OpLevel.NORMAL
    assignments_active: int = 0
    callouts_open: int = 0
    lead_gouvernorat_code: int | None = None
    participating_gouvernorats: list[int] = Field(default_factory=list)
    command_level: CommandLevel = "regional"


class NearbyIncident(BaseModel):
    """Summary of an open incident near a report, whatever its gouvernorat (no reporter data)."""

    id: uuid.UUID
    category: Category
    lead_gouvernorat_code: int | None
    participating_gouvernorats: list[int]
    centroid: Point | None
    severity: int | None
    opened_at: datetime
    report_count: int


class TimelineEntry(BaseModel):
    at: datetime
    kind: str
    actor: str | None
    payload: dict[str, Any]


class Casualties(BaseModel):
    rescued: int = Field(default=0, ge=0, le=100_000)
    injured: int = Field(default=0, ge=0, le=100_000)
    deceased: int = Field(default=0, ge=0, le=100_000)
    evacuated: int = Field(default=0, ge=0, le=1_000_000)


class CloseIn(BaseModel):
    outcome: Outcome
    summary: Annotated[Text, StringConstraints(min_length=10, max_length=5000)]
    casualties: Casualties = Field(default_factory=Casualties)
    lessons: Annotated[Text, StringConstraints(max_length=5000)] | None = None


class Evaluation(CloseIn):
    closed_by: str | None
    closed_at: datetime


class ResourceRef(BaseModel):
    id: uuid.UUID
    label: str
    kind: ResourceKind
    unit_name: str


class VolunteerRef(BaseModel):
    id: uuid.UUID
    full_name: str | None
    phone: str | None
    skills: list[str]


class AssignmentOut(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    kind: Literal["resource", "volunteer"]
    resource: ResourceRef | None
    volunteer: VolunteerRef | None
    order: str | None
    status: AssignmentStatus
    created_by: str
    created_at: datetime
    en_route_at: datetime | None
    on_scene_at: datetime | None
    released_at: datetime | None
    cancelled_at: datetime | None


class Position(BaseModel):
    lat: float
    lon: float
    at: datetime


class CalloutTargetOut(BaseModel):
    volunteer_id: uuid.UUID
    full_name: str | None
    phone: str | None
    distance_m: int | None
    status: TargetStatus
    eta_minutes: int | None
    responded_at: datetime | None
    arrived_at: datetime | None
    position: Position | None


class CalloutOut(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    skill: str
    requested: int
    radius_km: int
    message: str | None
    status: CalloutStatus
    created_by: str
    created_at: datetime
    accepted: int
    targets: list[CalloutTargetOut]


class IncidentDetail(IncidentSummary):
    reports: list[StaffReport]
    timeline: list[TimelineEntry]
    assignments: list[AssignmentOut] = Field(default_factory=list)
    callouts: list[CalloutOut] = Field(default_factory=list)
    evaluation: Evaluation | None = None
    resource_requests: list["ResourceRequestOut"] = Field(default_factory=list)


class IncidentCardIn(BaseModel):
    title: Annotated[Text, StringConstraints(max_length=150)] | None = None
    classification: str | None = None


class NoteIn(BaseModel):
    text: Annotated[Text, StringConstraints(min_length=1, max_length=2000)]


class AssignmentIn(BaseModel):
    resource_id: uuid.UUID
    order: Annotated[Text, StringConstraints(max_length=1000)] | None = None


class AssignmentStatusIn(BaseModel):
    status: AssignmentStatus
    note: Annotated[Text, StringConstraints(max_length=500)] | None = None


class CalloutIn(BaseModel):
    skill: str
    requested: int = Field(ge=1, le=50)
    radius_km: int = Field(default=30, ge=1, le=100)
    message: Annotated[Text, StringConstraints(max_length=300)] | None = None
    volunteer_ids: list[uuid.UUID] | None = Field(default=None, max_length=100)


class VolunteerSuggestion(BaseModel):
    volunteer_id: uuid.UUID
    full_name: str | None
    phone: str | None
    skills: list[str]
    distance_m: int
    busy: bool


# ---------------------------------------------------------------- levels and committees


class LevelOut(BaseModel):
    gouvernorat_code: int
    level: OpLevel
    since: datetime
    reason: str | None
    set_by: str | None


class LevelIn(BaseModel):
    gouvernorat_codes: list[int] = Field(min_length=1, max_length=24)
    level: OpLevel
    reason: Annotated[Text, StringConstraints(min_length=5, max_length=500)]


class DirectiveAckOut(BaseModel):
    gouvernorat_code: int
    acked_by: str | None
    acked_at: datetime
    note: str | None


class DirectiveOut(BaseModel):
    id: uuid.UUID
    title: str
    body: str
    urgency: Literal["normal", "urgent"]
    from_level: Literal["central", "local"]
    issued_by: str | None
    issued_at: datetime
    gouvernorat_codes: list[int]
    acks: list[DirectiveAckOut]
    pending_acks: list[int]


class DirectivePage(BaseModel):
    items: list[DirectiveOut]
    next_cursor: str | None


class DirectiveIn(BaseModel):
    title: Annotated[Text, StringConstraints(min_length=3, max_length=150)]
    body: Annotated[Text, StringConstraints(min_length=1, max_length=5000)]
    urgency: Literal["normal", "urgent"] = "normal"
    gouvernorat_codes: list[int] = Field(default_factory=list, max_length=24)


class AckIn(BaseModel):
    note: Annotated[Text, StringConstraints(max_length=1000)] | None = None


class PerformanceRow(BaseModel):
    gouvernorat_code: int | None
    level: OpLevel | None
    reports: int
    closed: int
    rejected: int
    avg_first_response_s: float | None
    avg_resolution_s: float | None
    open_incidents: int
    active_assignments: int
    volunteers_approved: int
    volunteers_ready: int
    alerts_active: int
    # Open incidents led elsewhere in which the gouvernorat participates (counted apart from those it leads).
    participating_incidents: int = 0


class PerformanceOut(BaseModel):
    since: datetime
    rows: list[PerformanceRow]
    national: PerformanceRow


# ---------------------------------------------------------------- units and resources


class LatLon(BaseModel):
    lat: float = Field(ge=30.0, le=37.6)
    lon: float = Field(ge=7.4, le=11.7)


class UnitIn(BaseModel):
    name_ar: Annotated[Text, StringConstraints(min_length=2, max_length=150)]
    name_fr: Annotated[Text, StringConstraints(min_length=2, max_length=150)]
    kind: UnitKind
    gouvernorat_code: int
    location: LatLon
    phone: Annotated[Text, StringConstraints(max_length=20)] | None = None
    version: int | None = None


class UnitOut(BaseModel):
    id: uuid.UUID
    name_ar: str
    name_fr: str
    kind: UnitKind
    gouvernorat_code: int
    location: Point
    phone: str | None
    resources: int
    version: int


class ResourceIn(BaseModel):
    unit_id: uuid.UUID
    kind: ResourceKind
    label: Annotated[Text, StringConstraints(min_length=1, max_length=60)]
    status: Literal["available", "out_of_service"] = "available"
    notes: Annotated[Text, StringConstraints(max_length=500)] | None = None
    location: LatLon | None = None
    version: int | None = None


class ResourceAssignmentRef(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    status: AssignmentStatus


class ResourceOut(BaseModel):
    id: uuid.UUID
    unit_id: uuid.UUID
    unit_name: str
    kind: ResourceKind
    label: str
    status: ResourceStatus
    notes: str | None
    location: Point | None
    gouvernorat_code: int
    assignment: ResourceAssignmentRef | None
    version: int
    updated_at: datetime


class ResourcePage(BaseModel):
    items: list[ResourceOut]
    next_cursor: str | None


class ResourceSummary(BaseModel):
    by_kind: dict[str, dict[str, int]]


class IncidentPage(BaseModel):
    items: list[IncidentSummary]
    next_cursor: str | None


class IncidentLinkIn(BaseModel):
    """accept_suggestion: follow the AI suggestion; link: into a chosen incident; new: start an incident."""

    action: Literal["accept_suggestion", "link", "new"]
    incident_id: uuid.UUID | None = None
    # ``new`` next to an open incident of a compatible type (409 possible_duplicate) needs a reason (audited).
    override_reason: Reason | None = None


class ParticipantIn(BaseModel):
    gouvernorat_code: int
    reason: Reason


class ReasonIn(BaseModel):
    reason: Reason


class LeadIn(BaseModel):
    gouvernorat_code: int
    reason: Reason


class CommandLevelIn(BaseModel):
    # None returns to the automatic rule.
    level: CommandLevel | None
    reason: Reason


class ResourceRequestIn(BaseModel):
    to_gouvernorat_code: int
    resource_id: uuid.UUID | None = None
    resource_kind: ResourceKind | None = None
    quantity: int = Field(default=1, ge=1, le=50)
    reason: Reason


class ResourceRequestOut(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    from_room: str
    to_gouvernorat_code: int
    resource_id: uuid.UUID | None
    resource_kind: str
    quantity: int
    reason: str
    status: RequestStatus
    requested_by_name: str | None
    requested_at: datetime
    decided_by_name: str | None
    decided_at: datetime | None
    decision_note: str | None
    assignment_ids: list[uuid.UUID] = Field(default_factory=list)


class ResourceRequestPage(BaseModel):
    items: list[ResourceRequestOut]
    next_cursor: str | None


class ApproveIn(BaseModel):
    resource_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    note: Annotated[Text, StringConstraints(max_length=500)] | None = None


class MergeIn(BaseModel):
    # The incident absorbed into the one in the path (its reports move, it becomes "merged").
    incident_id: uuid.UUID


IncidentDetail.model_rebuild()
