import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Kind = Literal["important", "critical", "other"]


class PlaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: Kind = "important"
    note: str | None = Field(default=None, max_length=2000)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class PlaceUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: Kind
    note: str | None = Field(default=None, max_length=2000)


class PlaceOut(BaseModel):
    id: uuid.UUID
    name: str
    kind: Kind
    note: str | None
    lat: float
    lon: float
    gouvernorat_code: int
    delegation_id: int | None
    created_by_name: str | None
    created_at: datetime
    updated_by_name: str | None
    updated_at: datetime
