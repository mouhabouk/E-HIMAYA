import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Kind = Literal["vehicle", "equipment", "skill"]
Family = Literal["vehicles", "equipment", "boats", "air", "ppe"]
VehicleState = Literal["ready", "assigned", "maintenance", "broken"]
WritableState = Literal["ready", "maintenance", "broken"]
Availability = Literal["on_duty", "rest", "leave"]
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
    maintenance: int = 0
    broken: int = 0


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
    maintenance: int = 0
    broken: int = 0


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
    state: WritableState = "ready"
    year: int | None = Field(default=None, ge=1950, le=2100)
    notes: str | None = Field(default=None, max_length=500)
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
    version: int
    updated_at: datetime


class StockIn(BaseModel):
    unit_id: uuid.UUID
    category_key: str = Field(max_length=40)
    specs: dict[str, SpecValue] = Field(default_factory=dict)
    qty_ready: int = Field(default=0, ge=0, le=100_000)
    qty_broken: int = Field(default=0, ge=0, le=100_000)
    notes: str | None = Field(default=None, max_length=500)
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
    action: Literal["create", "update", "delete", "import"]
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
    format: Literal["xlsx", "csv"]
    gouvernorat_code: int
    applied: bool
    vehicles: ImportCounts
    stock: ImportCounts
    agents: ImportCounts
    errors: list[ProblemOut]
    warnings: list[ProblemOut]


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
