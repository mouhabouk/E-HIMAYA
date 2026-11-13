import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Kind = Literal["vehicle", "equipment", "skill"]
Family = Literal["vehicles", "equipment", "boats", "air", "ppe"]
VehicleState = Literal["ready", "assigned", "reinforcement", "broken", "maintenance", "retired"]
RoomState = Literal["ready", "reinforcement", "broken"]
WritableState = Literal["ready", "maintenance", "broken"]
Availability = Literal["on_duty", "rest", "leave", "sick", "training", "mission"]
SpecValue = float | int | bool


class Names(BaseModel):
    ar: str = Field(min_length=1, max_length=100)
    fr: str = Field(min_length=1, max_length=100)
    en: str = Field(min_length=1, max_length=100)


class SpecDef(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,29}$")
    unit: str = Field(default="", max_length=12)
    type: Literal["number", "bool"] = "number"
    name: Names


class CategoryOut(BaseModel):
    key: str
    kind: Kind
    family: Family | None
    name: dict[str, str]
    specs: list[SpecDef]
    levels: int
    position: int
    active: bool


class CatalogueOut(BaseModel):
    items: list[CategoryOut]
    can_manage: bool


class CategoryIn(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")
    kind: Kind
    family: Family | None = None
    name: Names
    specs: list[SpecDef] = Field(default_factory=list, max_length=8)
    levels: int = Field(default=0, ge=0, le=5)
    position: int = Field(default=0, ge=0, le=999)


class CategoryPatch(BaseModel):
    family: Family | None = None
    name: Names | None = None
    specs: list[SpecDef] | None = Field(default=None, max_length=8)
    levels: int | None = Field(default=None, ge=0, le=5)
    position: int | None = Field(default=None, ge=0, le=999)
    active: bool | None = None


# ---------------------------------------------------------------- units and overview


class UnitRow(BaseModel):
    id: uuid.UUID
    name_ar: str
    name_fr: str
    kind: str
    gouvernorat_code: int
    vehicles: int
    vehicles_ready: int
    equipment_ready: int
    equipment_broken: int
    agents: int
    agents_on_duty: int
    verified_at: datetime | None
    verified_by_name: str | None
    # Not confirmed for more than 30 days (or never): the regional room gets a monthly reminder.
    stale: bool
    can_edit: bool


class UnitsOut(BaseModel):
    items: list[UnitRow]


class Tally(BaseModel):
    ready: int = 0
    assigned: int = 0
    reinforcement: int = 0
    maintenance: int = 0
    broken: int = 0
    retired: int = 0


class GouvernoratRow(BaseModel):
    code: int
    name_ar: str
    name_fr: str
    name_en: str
    units: int
    stale_units: int
    vehicles: Tally
    equipment: Tally
    agents: int
    agents_on_duty: int


class CategoryTotal(BaseModel):
    key: str
    kind: Kind
    ready: int = 0
    assigned: int = 0
    reinforcement: int = 0
    maintenance: int = 0
    broken: int = 0
    retired: int = 0


class SkillTotal(BaseModel):
    key: str
    agents: int = 0
    # On duty with a valid certificate.
    ready: int = 0
    expired: int = 0


class OverviewOut(BaseModel):
    gouvernorats: list[GouvernoratRow]
    categories: list[CategoryTotal]
    skills: list[SkillTotal]
    # Whether the caller may open the lists (governors and the minister see the counts only).
    can_list: bool
    can_edit: bool
    can_see_names: bool


# ---------------------------------------------------------------- register


class ReasonIn(BaseModel):
    reason: str = Field(default="", max_length=500)


class VehicleIn(BaseModel):
    unit_id: uuid.UUID
    category_key: str = Field(max_length=40)
    label: str = Field(min_length=1, max_length=60)
    code: str | None = Field(default=None, max_length=40)
    specs: dict[str, SpecValue] = Field(default_factory=dict)
    # The state of a new card only: afterwards the rooms set it (POST .../state), the maintenance department sends
    # it to the workshop or decommissions it (OS3).
    state: WritableState = "ready"
    year: int | None = Field(default=None, ge=1950, le=2100)
    notes: str | None = Field(default=None, max_length=500)
    plate: str | None = Field(default=None, max_length=30)
    odometer_km: int | None = Field(default=None, ge=0, le=5_000_000)
    acquired_on: date | None = None
    reason: str = Field(default="", max_length=500)
    version: int | None = None


class VehicleOut(BaseModel):
    id: uuid.UUID
    unit_id: uuid.UUID
    unit_name: str
    gouvernorat_code: int
    category_key: str | None
    kind: str
    label: str
    code: str | None
    specs: dict[str, Any]
    state: VehicleState
    year: int | None
    notes: str | None
    plate: str | None = None
    odometer_km: int | None = None
    acquired_on: date | None = None
    # Reinforcement: the unit where it waits and since when.
    stationed_unit_id: uuid.UUID | None = None
    stationed_unit_name: str | None = None
    stationed_gouvernorat_code: int | None = None
    stationed_since: datetime | None = None
    fault: str | None = None
    workshop: str | None = None
    maint_reason: str | None = None
    maint_since: datetime | None = None
    maint_until: date | None = None
    retired_on: date | None = None
    retire_decision: str | None = None
    retire_reason: str | None = None
    version: int
    updated_at: datetime


class StockIn(BaseModel):
    unit_id: uuid.UUID
    category_key: str = Field(max_length=40)
    specs: dict[str, SpecValue] = Field(default_factory=dict)
    qty_ready: int = Field(default=0, ge=0, le=100_000)
    qty_broken: int = Field(default=0, ge=0, le=100_000)
    notes: str | None = Field(default=None, max_length=500)
    # Carried by a vehicle of the same unit (R3).
    vehicle_id: uuid.UUID | None = None
    reason: str = Field(default="", max_length=500)
    version: int | None = None


class StockOut(BaseModel):
    id: uuid.UUID
    unit_id: uuid.UUID
    unit_name: str
    gouvernorat_code: int
    category_key: str
    specs: dict[str, Any]
    qty_ready: int
    qty_broken: int
    notes: str | None
    vehicle_id: uuid.UUID | None = None
    vehicle_label: str | None = None
    version: int
    updated_at: datetime


class SkillIn(BaseModel):
    skill_key: str = Field(max_length=40)
    level: int = Field(default=0, ge=0, le=5)
    cert_expires: date | None = None


class SkillOut(SkillIn):
    # The certificate has expired (or there is none for a speciality that needs one).
    expired: bool


class AgentIn(BaseModel):
    unit_id: uuid.UUID
    matricule: str = Field(min_length=2, max_length=30)
    full_name: str = Field(min_length=2, max_length=120)
    rank: str | None = Field(default=None, max_length=60)
    phone: str | None = Field(default=None, max_length=30)
    availability: Availability = "on_duty"
    skills: list[SkillIn] = Field(default_factory=list, max_length=20)
    notes: str | None = Field(default=None, max_length=500)
    reason: str = Field(default="", max_length=500)
    version: int | None = None


class AgentOut(BaseModel):
    id: uuid.UUID
    unit_id: uuid.UUID
    unit_name: str
    gouvernorat_code: int
    # Personal data: returned to the operations rooms only (null for the others).
    matricule: str | None
    full_name: str | None
    phone: str | None
    rank: str | None
    availability: Availability
    skills: list[SkillOut]
    notes: str | None
    version: int
    updated_at: datetime


class VehiclesOut(BaseModel):
    items: list[VehicleOut]
    can_edit: bool
    # OS3: the operations rooms set the operational state; the maintenance department the workshop.
    can_set_state: bool = False
    can_maintain: bool = False


class VehicleStateIn(BaseModel):
    state: RoomState
    # Reinforcement: the unit where the vehicle waits (proposed from there).
    host_unit_id: uuid.UUID | None = None
    # Broken: what the crew found (required).
    fault: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=500)
    # A repositioning suggested by the live coverage (OS3): the population it brings within the target, logged.
    suggested_gain: int | None = Field(default=None, ge=0, le=20_000_000)
    version: int | None = None


class MaintenanceIn(BaseModel):
    workshop: str = Field(min_length=2, max_length=200)
    reason: str = Field(min_length=3, max_length=500)
    until: date | None = None
    version: int | None = None


Money = Annotated[Decimal, Field(ge=0, le=10_000_000, max_digits=12, decimal_places=3)]
MaintKind = Literal["repair", "periodic", "accident"]


class CostIn(BaseModel):
    """OS3-3: what a stay in the workshop cost, in dinars (three decimals): at the exit or later."""

    maint_kind: MaintKind | None = None
    cost_parts: Money | None = None
    cost_labour: Money | None = None
    cost_external: Money | None = None
    invoice_ref: str | None = Field(default=None, max_length=60)


class MaintenanceEndIn(CostIn):
    note: str | None = Field(default=None, max_length=500)
    odometer_km: int | None = Field(default=None, ge=0, le=5_000_000)
    version: int | None = None


class RetireIn(BaseModel):
    decision: str = Field(min_length=2, max_length=80)
    retired_on: date
    reason: str = Field(min_length=5, max_length=500)
    version: int | None = None


class VehicleEventOut(BaseModel):
    id: uuid.UUID
    resource_id: uuid.UUID
    label: str
    plate: str | None
    unit_name: str
    gouvernorat_code: int
    kind: Literal["state", "maintenance_start", "maintenance_end", "retire", "reinforce", "reinforce_end"]
    from_state: str
    to_state: str
    details: dict[str, Any]
    created_by_name: str | None
    created_at: datetime
    # OS3-3: the cost of the stay in the workshop (``maintenance_end`` only).
    maint_kind: MaintKind | None = None
    cost_parts: Decimal | None = None
    cost_labour: Decimal | None = None
    cost_external: Decimal | None = None
    invoice_ref: str | None = None
    cost_by_name: str | None = None
    cost_at: datetime | None = None


class VehicleEventsOut(BaseModel):
    items: list[VehicleEventOut]


# ---------------------------------------------------------------- OS3-1: repositioning orders

OrderState = Literal["sent", "seen", "departed", "arrived", "closed"]


class RepositionOrderOut(BaseModel):
    id: uuid.UUID
    resource_id: uuid.UUID
    label: str
    plate: str | None
    kind: Literal["reinforce", "return"]
    from_unit_id: uuid.UUID
    from_unit: str
    to_unit_id: uuid.UUID
    to_unit: str
    from_point: list[float] | None
    to_point: list[float] | None
    gouvernorat_code: int
    host_gouvernorat_code: int | None
    note: str | None
    gain_population: int | None
    leader_name: str | None
    pushed: bool
    created_by_name: str | None
    created_at: datetime
    seen_at: datetime | None
    seen_by_name: str | None
    departed_at: datetime | None
    arrived_at: datetime | None
    closed_at: datetime | None
    close_reason: Literal["replaced", "state", "maintenance", "retired"] | None
    state: OrderState
    # Not seen by the crew after ``coverage.order_ack_minutes``.
    overdue: bool


class RepositionOrdersOut(BaseModel):
    items: list[RepositionOrderOut]
    ack_minutes: int


class RepositionStepIn(BaseModel):
    # The phone's time of the step, kept when it arrives late (no network); the server's time otherwise.
    at: datetime | None = None


# ---------------------------------------------------------------- OS3-3: monthly report of the fleet


class FleetMonth(BaseModel):
    month: str
    readiness_pct: float | None
    cost_total: Decimal


class FleetReportRow(BaseModel):
    gouvernorat_code: int
    name_ar: str
    name_fr: str
    point: list[float] | None
    vehicles: int
    vehicle_days: float
    down_days: float
    readiness_pct: float | None
    workshop_entries: int
    retired: int
    cost_parts: Decimal
    cost_labour: Decimal
    cost_external: Decimal
    cost_total: Decimal
    cost_per_vehicle: Decimal | None
    series: list[FleetMonth]


class FleetCostlyVehicle(BaseModel):
    resource_id: uuid.UUID
    label: str
    plate: str | None
    gouvernorat_code: int
    cost_total: Decimal
    stays: int


class FleetReportOut(BaseModel):
    month: str
    months: list[str]
    rows: list[FleetReportRow]
    total: FleetReportRow | None
    costly: list[FleetCostlyVehicle]
    red_below: int
    amber_below: int
    computed_at: datetime


class StockListOut(BaseModel):
    items: list[StockOut]
    can_edit: bool


class AgentsOut(BaseModel):
    items: list[AgentOut]
    can_edit: bool
    can_see_names: bool
    can_export_names: bool


class RevisionOut(BaseModel):
    id: uuid.UUID
    entity: Literal["vehicle", "stock", "agent"]
    entity_id: uuid.UUID
    action: Literal["create", "update", "delete", "import", "transfer_out", "transfer_in"]
    snapshot: dict[str, Any]
    reason: str | None
    created_by_name: str | None
    created_at: datetime


class RevisionsOut(BaseModel):
    items: list[RevisionOut]


# ---------------------------------------------------------------- import


class ProblemOut(BaseModel):
    code: str
    entity: str
    line: int | None = None
    value: str | None = None


class ImportCounts(BaseModel):
    new: int = 0
    changed: int = 0
    unchanged: int = 0


class ImportOut(BaseModel):
    format: Literal["xlsx", "csv", "json"]
    gouvernorat_code: int
    applied: bool
    vehicles: ImportCounts
    stock: ImportCounts
    agents: ImportCounts
    errors: list[ProblemOut]
    warnings: list[ProblemOut]
    # R4b: the columns of the file by sheet, those that match no field (to map them on screen), and the fields.
    headings: dict[str, list[str]] = Field(default_factory=dict)
    unknown: dict[str, list[str]] = Field(default_factory=dict)
    fields: dict[str, list[str]] = Field(default_factory=dict)


Heading = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
FieldKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]


class ImportProfileIn(BaseModel):
    """A mapping kept by name (R4b). The fields are checked against the register's by the API."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
    mapping: dict[Literal["vehicles", "stock", "agents"], dict[Heading, FieldKey]] = Field(max_length=3)
    # The central room may keep a profile for every room; a regional room keeps its own.
    shared: bool = False


class ImportProfileOut(BaseModel):
    id: uuid.UUID
    name: str
    gouvernorat_code: int | None
    mapping: dict[str, dict[str, str]]
    created_by_name: str | None
    created_at: datetime
    can_delete: bool


# ---------------------------------------------------------------- search (phase R2)


class SearchIn(BaseModel):
    """One question across the gouvernorats the caller sees: "the fire trucks of 2000 L or more", "the divers"."""

    what: Literal["vehicles", "stock", "agents"]
    # The catalogue key: a vehicle or equipment category, or a speciality for the staff.
    category: str | None = Field(default=None, max_length=40)
    # A range [min, max] (either end may be null) or an exact value, by specification key.
    specs: dict[str, list[float | None] | bool | float] = Field(default_factory=dict, max_length=10)
    ready_only: bool = False
    min_level: int | None = Field(default=None, ge=1, le=5)
    valid_cert: bool = False
    gouvernorats: list[int] | None = Field(default=None, max_length=30)
    # RS1: only the units inside the area of a crisis axis (its sub-axes included), widened by a margin.
    axis_id: uuid.UUID | None = None
    margin_km: float = Field(default=0, ge=0, le=50)


class SearchUnit(BaseModel):
    id: uuid.UUID
    name_ar: str
    name_fr: str
    lat: float | None
    lon: float | None
    total: int
    ready: int


class SearchGouvernorat(BaseModel):
    code: int
    name_ar: str
    name_fr: str
    name_en: str
    # A point inside the gouvernorat where the map writes its count.
    lat: float | None
    lon: float | None
    total: int
    ready: int
    units: list[SearchUnit]


class SearchAxis(BaseModel):
    """The axis a search was confined to (RS1); ``by_area`` False: the axis has no drawn area, its gouvernorats
    were searched instead."""

    id: uuid.UUID
    number: str
    by_area: bool
    margin_km: float


class SearchOut(BaseModel):
    """Counts only, grouped by gouvernorat and unit: no name, no matricule, no phone, whoever asks."""

    what: Literal["vehicles", "stock", "agents"]
    total: int
    ready: int
    gouvernorats: list[SearchGouvernorat]
    axis: SearchAxis | None = None


# ---------------------------------------------------------------- R3: transfers between gouvernorats

TransferStatus = Literal["pending", "accepted", "refused", "cancelled"]


class TransferIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to_gouvernorat: int = Field(ge=11, le=83)
    effective_on: date | None = None
    reason: str = Field(min_length=5, max_length=500)


class TransferAcceptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_id: uuid.UUID
    reason: str = Field(default="", max_length=500)


class TransferDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=5, max_length=500)


class TransferOut(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    # Personal data: the operations rooms only (null for the others).
    matricule: str | None
    full_name: str | None
    rank: str | None
    skills: list[str]
    from_gouvernorat: int
    from_unit_name: str
    to_gouvernorat: int
    to_unit_name: str | None
    effective_on: date | None
    status: TransferStatus
    reason: str
    decision_reason: str | None
    requested_by_name: str | None
    requested_at: datetime
    decided_by_name: str | None
    decided_at: datetime | None
    # What the caller may do: the joining room decides, the leaving room may cancel while it is pending.
    can_decide: bool
    can_cancel: bool
