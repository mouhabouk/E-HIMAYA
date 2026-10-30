import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, Field, StringConstraints

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
    # True while the national room has fixed the level by hand (``POST …/command-level``).
    command_level_manual: bool = False


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


class CrewRef(BaseModel):
    """The shift holding the vehicle on the staff app (phase P4a)."""

    shift_id: uuid.UUID
    leader_name: str | None
    crew_size: int
    acknowledged_at: datetime | None
    #: Alerts from this team the room has not marked seen yet (phase P4b).
    unseen_alerts: int = 0


class VehiclePosition(BaseModel):
    lat: float
    lon: float
    at: datetime
    distance_m: int | None = None


#: What a mission uses (phase S2, ``record.CONSUMABLES``).
Consumable = Literal[
    "water_m3", "foam_l", "powder_kg", "co2_kg", "extinguishers", "oxygen_l", "fuel_l", "sandbags", "absorbent_kg"
]
TimeSource = Literal["app", "sms", "room"]


class MissionRecord(BaseModel):
    """The rest of a mission's times, its crew, what it used and who gave each time (phase S2)."""

    left_scene_at: datetime | None = None
    at_hospital_at: datetime | None = None
    back_at_unit_at: datetime | None = None
    crew_count: int | None = None
    consumables: dict[Consumable, float] = Field(default_factory=dict)
    time_sources: dict[str, TimeSource] = Field(default_factory=dict)
    #: Times that hold but are not credible, for the room to check (``record_checks.WARNINGS``).
    record_warnings: list[str] = Field(default_factory=list)


class AssignmentOut(MissionRecord):
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
    crew: CrewRef | None = None
    contact_phone: str | None = None
    #: The vehicle's last position from the team's phone during this mission (phase P4d).
    position: VehiclePosition | None = None


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
    field_reports: list["FieldReportOut"] = Field(default_factory=list)
    casualties: "CasualtiesOut | None" = None
    transports: list["TransportOut"] = Field(default_factory=list)
    alerts: list["AlertOut"] = Field(default_factory=list)
    attachments: list["AttachmentOut"] = Field(default_factory=list)


class IncidentCardIn(BaseModel):
    title: Annotated[Text, StringConstraints(max_length=150)] | None = None
    classification: str | None = None


class NoteIn(BaseModel):
    text: Annotated[Text, StringConstraints(min_length=1, max_length=2000)]


class AssignmentIn(BaseModel):
    resource_id: uuid.UUID
    order: Annotated[Text, StringConstraints(max_length=1000)] | None = None
    #: A number the team may call on the scene (phase P4b); the reporter's own number is never sent automatically.
    contact_phone: Annotated[Text, StringConstraints(pattern=r"^\+?[0-9 ]{6,20}$")] | None = None


class AssignmentStatusIn(BaseModel):
    status: AssignmentStatus
    note: Annotated[Text, StringConstraints(max_length=500)] | None = None


class RecordTimes(BaseModel):
    """The times the room gives or corrects; a time left out stays as it is, ``null`` clears it."""

    en_route_at: AwareDatetime | None = None
    on_scene_at: AwareDatetime | None = None
    left_scene_at: AwareDatetime | None = None
    at_hospital_at: AwareDatetime | None = None
    back_at_unit_at: AwareDatetime | None = None


class RecordIn(BaseModel):
    """The room completes or corrects the record of a mission (phase S2)."""

    times: RecordTimes | None = None
    crew_count: int | None = Field(default=None, ge=1, le=60)
    consumables: dict[Consumable, float] | None = Field(default=None, max_length=12)
    #: Required when a time the team gave changes.
    reason: Annotated[Text, StringConstraints(max_length=300)] | None = None


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


# ---------------------------------------------------------------- staff app (phases P4a and P4b)

Severity = Literal[1, 2, 3, 4]
Triage = Literal["red", "yellow", "green", "black"]
#: Age bands the phone offers (phase P4b); ``child``, ``adult`` and ``elderly`` are the former ones, still read.
AgeBandIn = Literal["under_12", "12_17", "18_29", "30_44", "45_59", "60_plus", "unknown"]
AgeBand = Literal["under_12", "12_17", "18_29", "30_44", "45_59", "60_plus", "unknown", "child", "adult", "elderly"]
Sex = Literal["female", "male", "unknown"]
CrewStep = Literal["en_route", "on_scene", "released"]
COUNTERS = ("injured_light", "injured_serious", "deceased", "rescued", "trapped")
#: Chips of "backup" and of "danger to the crew" (design §5.4).
BackupKind = Literal[
    "fire_engine", "ambulance", "extrication", "ladder", "water_tanker", "hazmat", "police", "heavy_equipment"
]
DangerKind = Literal["fire_spread", "collapse", "gas", "electricity", "violence", "traffic"]
BACKUP_KINDS: tuple[str, ...] = BackupKind.__args__  # type: ignore[attr-defined]
DANGER_KINDS: tuple[str, ...] = DangerKind.__args__  # type: ignore[attr-defined]
ReportKind = Literal["first", "update", "detailed"]


class FieldReportOut(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    resource_label: str | None = None
    kind: ReportKind = "first"
    category: Category
    classification: str | None
    severity: int | None
    backup_needed: bool
    backup_note: str | None
    backup_kinds: list[str] = Field(default_factory=list)
    crew_danger: bool
    #: Detailed report (F-STF-05): the template it answers and the answers by field key.
    template_id: uuid.UUID | None = None
    template_version: int | None = None
    answers: dict[str, Any] | None = None
    note: str | None = None
    author_name: str | None
    device_at: datetime | None
    created_at: datetime


class CasualtiesOut(BaseModel):
    injured_light: int = 0
    injured_serious: int = 0
    deceased: int = 0
    rescued: int = 0
    trapped: int = 0
    #: People taken to hospital, counted from the transports.
    transported: int = 0
    updated_by: str | None = None
    updated_at: datetime | None = None


class TransportOut(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    triage: Triage
    age_band: AgeBand
    sex: Sex
    hospital: str
    hospital_ref: uuid.UUID | None = None
    created_by_name: str | None
    device_at: datetime | None
    created_at: datetime


class AlertOut(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    resource_label: str | None = None
    kind: Literal["backup", "danger"]
    items: list[str]
    created_by_name: str | None
    device_at: datetime | None
    created_at: datetime
    seen_by_name: str | None
    seen_at: datetime | None
    #: "sms" when it came as a signed text message, without its chips (phase P4d).
    via: Literal["app", "sms"] = "app"


class AttachmentOut(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    kind: Literal["photo", "voice", "text"]
    body: str | None
    content_type: str | None
    bytes: int | None
    duration_s: float | None
    created_by_name: str | None
    device_at: datetime | None
    created_at: datetime
    #: Short-lived link to the file, for the room only (never sent to the phone).
    url: str | None = None


Localized = dict[Literal["ar", "fr", "en"], Annotated[Text, StringConstraints(min_length=1, max_length=120)]]


class TemplateOption(BaseModel):
    key: Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,40}$")]
    label: Localized


class TemplateField(BaseModel):
    """One question of a detailed report: chips (one or several), yes or no, or a number with + and −."""

    key: Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,40}$")]
    type: Literal["single", "multi", "yesno", "count"]
    label: Localized
    options: list[TemplateOption] = Field(default_factory=list, max_length=20)
    required: bool = False
    unit: Localized | None = None
    max: int | None = Field(default=None, ge=1, le=1_000_000)


class TemplateOut(BaseModel):
    id: uuid.UUID
    category: Category
    classification: str | None
    version: int
    status: Literal["draft", "approved", "retired"]
    fields: list[TemplateField]
    simulated: bool
    created_by_name: str | None
    created_at: datetime
    updated_at: datetime
    approved_by_name: str | None
    approved_at: datetime | None


class TemplateIn(BaseModel):
    """A draft: a new one for a category (and classification), or the next version of the approved one."""

    category: Category
    classification: Annotated[str, StringConstraints(max_length=40)] | None = None
    fields: list[TemplateField] = Field(min_length=1, max_length=30)


class TemplatePatch(BaseModel):
    fields: list[TemplateField] = Field(min_length=1, max_length=30)


class Hospital(BaseModel):
    """A hospital of the map layers near the incident (phase P4b), for the transport chips."""

    id: uuid.UUID
    name: str
    phone: str | None
    distance_m: int
    simulated: bool


class CrewWrite(BaseModel):
    """Every write from the staff app: the id the phone generated (a write sent twice is applied once) and the
    phone's clock."""

    client_id: uuid.UUID
    device_at: datetime | None = None


class DeviceIn(BaseModel):
    platform: Literal["android", "ios"]
    label: Annotated[Text, StringConstraints(max_length=80)] | None = None
    app_build: int | None = Field(default=None, ge=1, le=1_000_000)
    push_token: Annotated[str, StringConstraints(max_length=4096)] | None = None


class DevicePatch(BaseModel):
    push_token: Annotated[str, StringConstraints(max_length=4096)] | None = None
    app_build: int | None = Field(default=None, ge=1, le=1_000_000)


class DeviceOut(BaseModel):
    id: uuid.UUID
    holder_name: str | None
    label: str | None
    platform: str
    app_build: int | None
    created_at: datetime
    last_seen_at: datetime
    revoked_at: datetime | None
    on_shift: bool = False


class ShiftIn(CrewWrite):
    resource_id: uuid.UUID
    crew_size: int = Field(ge=1, le=20)
    crew_names: Annotated[Text, StringConstraints(max_length=300)] | None = None


class ShiftOut(BaseModel):
    id: uuid.UUID
    resource: ResourceRef
    crew_size: int
    crew_names: str | None
    started_at: datetime
    ended_at: datetime | None


class CrewResource(BaseModel):
    id: uuid.UUID
    label: str
    kind: ResourceKind
    unit_name: str
    status: ResourceStatus
    on_shift: bool


class CrewMe(BaseModel):
    name: str | None
    # The field roles of the account: ``team_leader`` (shifts, missions), ``org_auditor`` (prevention visits, P4c).
    roles: list[str] = Field(default_factory=list)
    gouvernorat_code: int
    device: DeviceOut
    shift: ShiftOut | None


class MissionIncident(BaseModel):
    id: uuid.UUID
    category: Category
    classification: str | None
    title: str | None
    location: Point | None
    gouvernorat_code: int | None
    delegation_ar: str | None
    delegation_fr: str | None
    op_level: OpLevel
    status: IncidentStatus


class MissionOut(MissionRecord):
    id: uuid.UUID
    status: AssignmentStatus
    order: str | None
    created_at: datetime
    acknowledged_at: datetime | None
    en_route_at: datetime | None
    on_scene_at: datetime | None
    released_at: datetime | None
    cancelled_at: datetime | None
    incident: MissionIncident
    #: The last situation report (first or update).
    field_report: FieldReportOut | None
    detailed_report: FieldReportOut | None = None
    casualties: CasualtiesOut
    transports: list[TransportOut]
    alerts: list[AlertOut] = Field(default_factory=list)
    attachments: list[AttachmentOut] = Field(default_factory=list)
    #: The approved detailed-report template of the incident's category (and classification), if any.
    template: TemplateOut | None = None
    contact_phone: str | None = None
    #: Distance in metres between the phone and the incident at the last step that carried a position.
    distance_m: int | None = None


class MissionPage(BaseModel):
    items: list[MissionOut]


class StepIn(CrewWrite):
    status: CrewStep
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


class MilestoneIn(CrewWrite):
    """A step of the mission after the arrival on scene (phase S2)."""

    step: Literal["left_scene", "at_hospital", "back_at_unit"]


class TeamRecordIn(CrewWrite):
    """The crew and what the mission used, as the team gives them (phase S2)."""

    crew_count: int | None = Field(default=None, ge=1, le=60)
    consumables: dict[Consumable, float] | None = Field(default=None, max_length=12)


class FirstReportIn(CrewWrite):
    """A situation report: the first one, then updates (the last one is shown)."""

    category: Category
    classification: str | None = None
    severity: Severity
    backup_needed: bool = False
    backup_kinds: list[BackupKind] = Field(default_factory=list, max_length=8)
    backup_note: Annotated[Text, StringConstraints(max_length=300)] | None = None
    crew_danger: bool = False


class CasualtiesIn(CrewWrite):
    """Changes to the live counters (+1, -1, ...); a counter never goes below zero."""

    injured_light: int = Field(default=0, ge=-50, le=50)
    injured_serious: int = Field(default=0, ge=-50, le=50)
    deceased: int = Field(default=0, ge=-50, le=50)
    rescued: int = Field(default=0, ge=-50, le=50)
    trapped: int = Field(default=0, ge=-50, le=50)


class TransportIn(CrewWrite):
    triage: Triage
    age_band: AgeBandIn
    sex: Sex
    hospital: Annotated[Text, StringConstraints(min_length=1, max_length=120)] | None = None
    #: A hospital of ``/missions/{id}/hospitals``; its name is taken from the map, ``hospital`` is then ignored.
    hospital_ref: uuid.UUID | None = None


class AlertIn(CrewWrite):
    kind: Literal["backup", "danger"]
    items: list[str] = Field(default_factory=list, max_length=8)


class PositionIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0, le=100_000)
    at: AwareDatetime


class PositionsIn(BaseModel):
    """Positions of the vehicle kept on the phone and sent together (phase P4d, design §9.2)."""

    points: list[PositionIn] = Field(min_length=1, max_length=50)


class PositionsOut(BaseModel):
    accepted: int


class SmsKeyOut(BaseModel):
    """The phone's own key for its signed EH2 text messages (design §9.3)."""

    key: str


class TextNoteIn(CrewWrite):
    body: Annotated[Text, StringConstraints(min_length=1, max_length=500)]


class DetailedReportIn(CrewWrite):
    template_id: uuid.UUID
    answers: dict[str, Any] = Field(max_length=30)
    note: Annotated[Text, StringConstraints(max_length=1000)] | None = None


IncidentDetail.model_rebuild()


class NearHospital(BaseModel):
    """A hospital near an incident, timed on the road (phase L1b)."""

    id: uuid.UUID
    name: str
    phone: str | None
    layer: str
    lat: float
    lon: float
    distance_m: int
    road_m: int
    road_s: int
    # The routing engine, or "fallback" for the estimate.
    engine: str
    simulated: bool


class HospitalChoice(BaseModel):
    feature_id: uuid.UUID
