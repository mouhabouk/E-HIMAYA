import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class AnomalyOut(BaseModel):
    """An indicator out of its habit (AI4), with its explanation in the reader's language. Figures only."""

    id: uuid.UUID
    indicator: Literal["reports", "arrival", "completion"]
    gouvernorat_code: int
    gouvernorat_name: str | None
    delegation_id: int | None
    delegation_name: str | None
    day: date
    value: float
    mean: float
    std: float
    z: float
    baseline: Literal["season", "recent"]
    points: int
    n: int
    higher: bool
    text: str
    raised_at: datetime


class AnomaliesOut(BaseModel):
    # False when the AI settings switched the detection off (AI-01).
    enabled: bool
    items: list[AnomalyOut]
