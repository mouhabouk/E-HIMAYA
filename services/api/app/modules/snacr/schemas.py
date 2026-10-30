import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.modules.snacr.domain import Family, Hazard, Priority, Zone


class DatasetOut(BaseModel):
    id: uuid.UUID
    year: int
    source: Literal["office", "simulated"]
    simulated: bool
    file_name: str | None
    rows: int
    quality: dict[str, Any]
    imported_by_name: str | None
    imported_at: datetime


class Method(BaseModel):
    goal: int
    urban: int
    periurban: int
    targets: dict[Family, dict[Zone, int]]
    review_months: int
    validity_years: int


class Figures(BaseModel):
    rows: int
    completeness_pct: float | None
    recorded_pct: float | None
    compliance_pct: float | None


class FamilyFigures(Figures):
    arrival_median: float | None = None
    arrival_p90: float | None = None
    departure_median: float | None = None
    departure_p90: float | None = None
    target: int | None = None


class DelegationAnalysis(Figures):
    id: int
    gouvernorat_code: int
    name_ar: str
    name_fr: str
    population: int | None
    area_km2: float | None
    zone: Zone
    annual: int
    rate_per_1000: float | None
    frequency_level: int | None
    coverage_level: int | None
    priority: Priority | None
    families: dict[Family, FamilyFigures]


class GouvernoratAnalysis(Figures):
    code: int
    unmatched: int
    annual: int
    rate_per_1000: float | None
    families: dict[Family, FamilyFigures]


class Totals(Figures):
    unmatched: int
    annual: int
    population: int | None
    rate_per_1000: float | None


class YearCount(BaseModel):
    year: int
    families: dict[Family, int]


class SubtypeCount(BaseModel):
    subtype: str
    rows: int


class DatasetUse(BaseModel):
    year: int
    simulated: bool
    rows: int


class Analysis(BaseModel):
    years: list[int]
    codes: list[int]
    simulated: bool
    datasets: list[DatasetUse]
    method: Method
    breaks: list[float]
    totals: Totals
    by_year: list[YearCount]
    gouvernorats: list[GouvernoratAnalysis]
    delegations: list[DelegationAnalysis]
    matrix: list[list[int]] = Field(description="Délégations by frequency level (rows 1-5) and coverage level (1-5)")
    month: dict[Family, list[int]]
    weekday_hour: dict[Family, list[list[int]]]
    subtypes: dict[Family, list[SubtypeCount]]


class UnmatchedName(BaseModel):
    gouvernorat_code: int
    raw: str
    rows: int


class AliasIn(BaseModel):
    gouvernorat_code: int = Field(ge=11, le=83)
    raw: str = Field(min_length=1, max_length=120)
    delegation_id: int


class AliasOut(BaseModel):
    id: uuid.UUID
    gouvernorat_code: int
    raw: str
    delegation_id: int
    created_by_name: str | None
    created_at: datetime


class AliasCreated(BaseModel):
    alias: AliasOut
    rows_fixed: int


class SpecialRiskIn(BaseModel):
    gouvernorat_code: int = Field(ge=11, le=83)
    hazard: Hazard
    probability: int = Field(ge=1, le=5)
    gravity: int = Field(ge=1, le=5)
    note: str | None = Field(default=None, max_length=500)


class SpecialRiskOut(BaseModel):
    id: uuid.UUID
    gouvernorat_code: int
    hazard: Hazard
    probability: int
    gravity: int
    level: Priority
    note: str | None
    simulated: bool
    updated_by_name: str | None
    updated_at: datetime | None


class Reference(BaseModel):
    code: str
    title: str
    use: str
    url: str | None = None


class Overview(BaseModel):
    datasets: list[DatasetOut]
    default_years: list[int]
    method: Method
    references: list[Reference]
    can_import: bool
    can_edit_national: bool


class PlanIn(BaseModel):
    gouvernorat_code: int | None = Field(default=None, ge=11, le=83)
    years: list[int] = Field(default_factory=list, max_length=5)


class Objective(BaseModel):
    kind: Literal["coverage", "data", "names", "special"]
    gouvernorat_code: int
    delegation_id: int | None = None
    delegation: str | None = None
    family: Family | None = None
    hazard: Hazard | None = None
    target_min: int | None = None
    from_pct: float | None = None
    to_pct: float | None = None
    rows: int | None = None


class PlanSummary(BaseModel):
    id: uuid.UUID
    gouvernorat_code: int | None
    version: int
    years: list[int]
    status: Literal["draft", "approved", "superseded"]
    simulated: bool
    created_by_name: str | None
    created_at: datetime
    approved_by_name: str | None
    approved_at: datetime | None
    review_due: datetime | None
    valid_until: datetime | None
    objectives: int
    can_approve: bool


class PlanOut(PlanSummary):
    objective_list: list[Objective]
    special_risks: list[SpecialRiskOut]
    references: list[Reference]


class ImportOut(BaseModel):
    dataset: DatasetOut
