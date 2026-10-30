import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True)]
Name = Annotated[Text, StringConstraints(min_length=3, max_length=200)]
Reason = Annotated[Text, StringConstraints(min_length=5, max_length=1000)]
Kind = Literal["flood", "forest_fire", "storm", "earthquake", "technological", "health", "other"]
Level = Annotated[int, Field(ge=1, le=4)]
Code = Annotated[int, Field(ge=11, le=83)]
Category = Literal["evacuation", "resources", "closure", "shelter", "support", "plan", "public_information", "other"]
Executor = Literal["regional", "central", "partner"]
DirectiveStatus = Literal["issued", "received", "in_progress", "done", "failed"]


class Area(BaseModel):
    """GeoJSON polygon drawn on the map (Polygon or MultiPolygon, WGS 84)."""

    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list[Any]


class Point(BaseModel):
    lat: Annotated[float, Field(ge=-90, le=90)]
    lon: Annotated[float, Field(ge=-180, le=180)]


# --- Axes -----------------------------------------------------------------------------------------------------------


class AxisIn(BaseModel):
    name: Name
    kind: Kind
    level: Level
    gouvernorat_code: Code | None = None
    area: Area | None = None
    plan: Annotated[Text, StringConstraints(max_length=2000)] = ""
    incident_ids: Annotated[list[uuid.UUID], Field(max_length=200)] = Field(default_factory=list)
    # A national axis from the start: its sub-axes (at least one gouvernorat).
    national: bool = False
    gouvernorats: Annotated[list[Code], Field(max_length=24)] = Field(default_factory=list)


class AxisPatch(BaseModel):
    version: int
    name: Name | None = None
    level: Level | None = None
    area: Area | None = None
    plan: Annotated[Text, StringConstraints(max_length=2000)] | None = None
    # The plan as a document of the register (phase L3b); null leaves it, "" in ``clear_plan_document`` removes it.
    plan_document_id: uuid.UUID | None = None
    clear_plan_document: bool = False
    reason: Annotated[Text, StringConstraints(max_length=1000)] = ""


class EscalateIn(BaseModel):
    gouvernorats: Annotated[list[Code], Field(max_length=24)] = Field(default_factory=list)
    reason: Reason


class CloseIn(BaseModel):
    summary: Annotated[Text, StringConstraints(min_length=10, max_length=4000)]


class Figures(BaseModel):
    incidents: int = 0
    incidents_open: int = 0
    deceased: int = 0
    injured: int = 0
    injured_serious: int = 0
    rescued: int = 0
    trapped: int = 0
    evacuated: int = 0
    shelters: int = 0
    shelter_capacity: int = 0
    sheltered: int = 0
    resources: int = 0
    resources_by_kind: dict[str, int] = Field(default_factory=dict)
    volunteers: int = 0
    needs_open: int = 0
    decisions: int = 0
    decisions_done: int = 0
    decisions_failed: int = 0
    done_share: float | None = None
    mean_hours_to_done: float | None = None


class DocRef(BaseModel):
    """A document of the register (phase L3b) an axis points to."""

    id: str
    number: str
    reference: str
    title: str
    kind: str
    status: str


class AxisOut(BaseModel):
    id: str
    number: str
    name: str
    kind: Kind
    scope: Literal["gouvernorat", "national"]
    parent_id: str | None
    gouvernorat_code: int | None
    gouvernorat_name: str | None
    gouvernorats: list[int]
    area: dict[str, Any] | None
    level: int
    plan: str
    plan_document: DocRef | None = None
    # The plans in force of the axis' hazard, national then of its gouvernorats (phase PL1), to open on the screen.
    hazard_plans: list[DocRef] = []
    status: Literal["open", "closed"]
    opened_by_name: str | None
    opened_at: datetime
    closed_by_name: str | None
    closed_at: datetime | None
    closing: dict[str, Any] | None
    next_sitrep_at: datetime | None
    memory_id: str | None
    version: int
    figures: Figures
    children: list["AxisOut"] = Field(default_factory=list)
    # What the caller may do on this axis.
    can_manage: bool = False
    can_command: bool = False
    can_issue: bool = False


class AxisList(BaseModel):
    items: list[AxisOut]


# --- Declaration requests -------------------------------------------------------------------------------------------


class RequestIn(BaseModel):
    name: Name
    kind: Kind
    level: Level
    facts: Annotated[Text, StringConstraints(min_length=10, max_length=4000)]
    incident_ids: Annotated[list[uuid.UUID], Field(max_length=200)] = Field(default_factory=list)
    area: Area | None = None


class DecideIn(BaseModel):
    accept: bool
    reason: Annotated[Text, StringConstraints(max_length=1000)] = ""


class RequestOut(BaseModel):
    id: str
    gouvernorat_code: int
    gouvernorat_name: str | None
    name: str
    kind: Kind
    level: int
    facts: str
    incident_ids: list[str]
    area: dict[str, Any] | None
    status: Literal["pending", "accepted", "rejected"]
    created_by_name: str | None
    created_at: datetime
    decided_by_name: str | None
    decided_at: datetime | None
    decision_reason: str | None
    axis_id: str | None


class RequestList(BaseModel):
    items: list[RequestOut]


# --- Interventions --------------------------------------------------------------------------------------------------


class IncidentOut(BaseModel):
    """An intervention of the axis as the command sees it: the facts, no reporter, no victim identity."""

    id: str
    axis_id: str | None = None
    category: str
    severity: int | None
    status: str
    gouvernorat_code: int | None
    lat: float | None
    lon: float | None
    opened_at: datetime
    # The room's title, for the operations rooms only (it may name a place or a person).
    title: str | None = None
    deceased: int = 0
    injured: int = 0
    rescued: int = 0
    resources: int = 0
    attached_by_name: str | None = None
    attached_at: datetime | None = None


class IncidentList(BaseModel):
    items: list[IncidentOut]


class AttachIn(BaseModel):
    incident_id: uuid.UUID


class DetachIn(BaseModel):
    reason: Reason


# --- Components -----------------------------------------------------------------------------------------------------


class ShelterIn(BaseModel):
    name: Annotated[Text, StringConstraints(min_length=2, max_length=200)]
    location: Point | None = None
    capacity: Annotated[int, Field(ge=0, le=1_000_000)]
    occupants: Annotated[int, Field(ge=0, le=1_000_000)] = 0


class ShelterPatch(BaseModel):
    capacity: Annotated[int, Field(ge=0, le=1_000_000)] | None = None
    occupants: Annotated[int, Field(ge=0, le=1_000_000)] | None = None


class ShelterOut(BaseModel):
    id: str
    axis_id: str
    name: str
    lat: float | None
    lon: float | None
    capacity: int
    occupants: int
    updated_at: datetime


class EvacuationIn(BaseModel):
    name: Annotated[Text, StringConstraints(min_length=2, max_length=200)]
    area: Area | None = None
    evacuated: Annotated[int, Field(ge=0, le=10_000_000)] = 0


class EvacuationPatch(BaseModel):
    evacuated: Annotated[int, Field(ge=0, le=10_000_000)]


class EvacuationOut(BaseModel):
    id: str
    axis_id: str
    name: str
    area: dict[str, Any] | None
    evacuated: int
    updated_at: datetime


class NeedIn(BaseModel):
    label: Annotated[Text, StringConstraints(min_length=2, max_length=200)]
    quantity: Annotated[int, Field(ge=1, le=1_000_000)]


class NeedOut(BaseModel):
    id: str
    axis_id: str
    label: str
    quantity: int
    status: Literal["raised", "met"]
    created_by_name: str | None
    created_at: datetime
    met_at: datetime | None


# --- Recommendations and decisions ----------------------------------------------------------------------------------


class DirectiveIn(BaseModel):
    kind: Literal["recommendation", "decision"]
    category: Category
    body: Annotated[Text, StringConstraints(min_length=5, max_length=4000)]
    area: Area | None = None
    executor: Executor
    executor_name: Annotated[Text, StringConstraints(min_length=2, max_length=200)] | None = None
    due_at: datetime | None = None


class DirectiveStatusIn(BaseModel):
    status: DirectiveStatus
    reason: Annotated[Text, StringConstraints(max_length=1000)] = ""


class DirectiveEventOut(BaseModel):
    status: str
    reason: str | None
    by_name: str | None
    at: datetime


class DirectiveOut(BaseModel):
    id: str
    axis_id: str
    axis_number: str
    number: int
    kind: Literal["recommendation", "decision"]
    category: Category
    body: str
    area: dict[str, Any] | None
    executor: Executor
    executor_name: str | None
    due_at: datetime | None
    status: DirectiveStatus
    status_reason: str | None
    issuer_role: Literal["governor", "minister"]
    issued_by_name: str | None
    issued_at: datetime
    signature: str | None
    key_id: str | None
    overridden_by: str | None
    overdue: bool
    done_at: datetime | None
    events: list[DirectiveEventOut] = Field(default_factory=list)
    can_update: bool = False


class DirectiveList(BaseModel):
    items: list[DirectiveOut]


# --- Situation reports and timeline ---------------------------------------------------------------------------------


class SitrepSend(BaseModel):
    assessment: Annotated[Text, StringConstraints(min_length=5, max_length=4000)]


class SitrepOut(BaseModel):
    id: str
    axis_id: str
    number: int
    figures: dict[str, Any]
    assessment: str
    status: Literal["draft", "sent"]
    created_at: datetime
    sent_by_name: str | None
    sent_at: datetime | None


class EventOut(BaseModel):
    at: datetime
    actor_name: str | None
    kind: str
    payload: dict[str, Any]


class AxisDetail(BaseModel):
    axis: AxisOut
    incidents: list[IncidentOut]
    shelters: list[ShelterOut]
    evacuations: list[EvacuationOut]
    needs: list[NeedOut]
    directives: list[DirectiveOut]
    sitreps: list[SitrepOut]
    timeline: list[EventOut]
    # Documents of the register that concern the axis (its decisions recorded there, plans, instructions).
    documents: list[DocRef] = Field(default_factory=list)


# --- Disasters (phase N) ---------------------------------------------------------------------------------------------


class DisasterArea(BaseModel):
    id: str
    level: int
    area: dict[str, Any] | None


class DisasterMap(BaseModel):
    figures: Figures
    areas: list[DisasterArea]
    incidents: list[IncidentOut]
    shelters: list[ShelterOut]
    evacuations: list[EvacuationOut]


# --- Command (governor, minister) -----------------------------------------------------------------------------------


class GouvernoratState(BaseModel):
    code: int
    name: str
    level: int | None
    axes: int
    incidents_open: int
    resources: int
    # Open interventions of the open axes per engaged resource (design §6): the higher, the heavier.
    weight: float | None
    deceased: int
    evacuated: int
    needs_open: int


class CommandOverview(BaseModel):
    role: Literal["governor", "minister"]
    gouvernorat_code: int | None
    totals: Figures
    axes: list[AxisOut]
    gouvernorats: list[GouvernoratState]
    needs: list[NeedOut]
    directives: list[DirectiveOut]
    sitreps: list[SitrepOut]
    closed: list[AxisOut]
