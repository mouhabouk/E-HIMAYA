import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Unit = Literal["ha", "bale", "bag"]


class ItemOut(BaseModel):
    id: uuid.UUID
    code: str | None
    label_ar: str
    label_fr: str | None
    unit: Unit | None
    sort: int
    active: bool
    updated_by_name: str | None
    updated_at: datetime


class ListOut(BaseModel):
    key: str
    name_ar: str
    name_fr: str
    name_en: str
    items: list[ItemOut]


class ListsOut(BaseModel):
    lists: list[ListOut]
    can_manage: bool


class ItemIn(BaseModel):
    code: str | None = Field(default=None, max_length=20)
    label_ar: str = Field(min_length=1, max_length=160)
    label_fr: str | None = Field(default=None, max_length=160)
    unit: Unit | None = None
    sort: int | None = Field(default=None, ge=0, le=100_000)


class ItemPatch(BaseModel):
    code: str | None = Field(default=None, max_length=20)
    label_ar: str | None = Field(default=None, min_length=1, max_length=160)
    label_fr: str | None = Field(default=None, max_length=160)
    unit: Unit | None = None
    sort: int | None = Field(default=None, ge=0, le=100_000)
    active: bool | None = None
