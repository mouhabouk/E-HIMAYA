from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["approved", "pending", "changed", "withdrawn", "shadow"]


class Table(BaseModel):
    """One table of figures, already worded and formatted in the reader's language (the PDF prints the same)."""

    key: str
    title: str
    measured_on: date | None = None
    simulated: bool = False
    columns: list[str]
    rows: list[list[str]]
    # Rows whose sample is too small to say much (index into rows).
    small_rows: list[int] = []
    note: str | None = None


class Threshold(BaseModel):
    key: str
    label: str
    value: float | bool | None


class DecisionOut(BaseModel):
    decision: Literal["approved", "withdrawn"]
    version: str
    thresholds: dict[str, float | bool | None]
    reference: str
    note: str
    decided_by_name: str
    decided_at: datetime


class CardOut(BaseModel):
    id: str
    name: str
    family: Literal["vision", "language", "tabular"]
    version: str
    licences: list[str]
    simulated: bool
    status: Status
    status_label: str
    use: str
    limits: str
    data: str
    measures: list[Table]
    thresholds: list[Threshold]
    decisions: list[DecisionOut]
    can_decide: bool
    can_train: bool


class CardsOut(BaseModel):
    items: list[CardOut]
    generated_at: datetime


class DecisionIn(BaseModel):
    decision: Literal["approved", "withdrawn"]
    # The version the committee saw on the card: refused if the model changed since (model_changed).
    version: str = Field(min_length=1, max_length=80)
    reference: str = Field(min_length=3, max_length=200)
    note: str = Field(default="", max_length=500)


class TrainIn(BaseModel):
    seed: int = Field(default=7, ge=0, le=1_000_000)
