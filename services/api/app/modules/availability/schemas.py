import uuid
from datetime import date, time
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.modules.availability.domain import MAX_SLOTS

Role = Literal["volunteer", "doctor"]
Weekday = Annotated[int, Field(ge=1, le=7)]


class SlotIn(BaseModel):
    kind: Literal["available", "unavailable"]
    weekdays: Annotated[list[Weekday], Field(max_length=7)] = Field(default_factory=list)
    starts_on: date
    ends_on: date | None = None
    from_time: time
    to_time: time

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.ends_on is not None and self.ends_on < self.starts_on:
            raise ValueError("ends_before_start")
        if self.from_time == self.to_time:
            raise ValueError("empty_hours")
        return self


class SlotsIn(BaseModel):
    slots: Annotated[list[SlotIn], Field(max_length=MAX_SLOTS)]


class SlotOut(SlotIn):
    id: uuid.UUID


class SlotsOut(BaseModel):
    role: Role
    slots: list[SlotOut]
    # What the calendar says now: available, unavailable, or nothing planned.
    planned_now: Literal["available", "unavailable"] | None
