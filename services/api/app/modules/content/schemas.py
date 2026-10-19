import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

Hazard = Literal[
    "fire",
    "flood",
    "traffic_accident",
    "medical",
    "drowning",
    "landslide",
    "chemical_leak",
    "heat_wave",
    "storm",
    "earthquake",
    "other",
]
Item = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class TipText(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] = ""
    do: list[Item] = Field(default_factory=list, max_length=15)
    dont: list[Item] = Field(default_factory=list, max_length=15)

    @property
    def complete(self) -> bool:
        return bool(self.title and (self.do or self.dont))


class TipContent(BaseModel):
    ar: TipText = Field(default_factory=TipText)
    fr: TipText = Field(default_factory=TipText)
    en: TipText = Field(default_factory=TipText)


class TipIn(BaseModel):
    hazard: Hazard
    position: int = Field(default=0, ge=0, le=1000)
    content: TipContent
    version: int | None = None


class TipOut(BaseModel):
    id: uuid.UUID
    hazard: Hazard
    position: int
    status: Literal["draft", "published"]
    content: TipContent
    version: int
    updated_at: datetime
    published_at: datetime | None


class PublicTip(BaseModel):
    id: uuid.UUID
    hazard: Hazard
    position: int
    content: TipContent
    updated_at: datetime


class PublicTips(BaseModel):
    revision: int
    items: list[PublicTip]
