"""When a volunteer or a doctor planned to be available, without the database (phase N, design §8).

A slot covers a moment when the moment's local date is within its dates, its weekday is one of the slot's (or the
slot has none) and its local time is within the hours (an end before the start runs past midnight). An unavailable
slot wins over an available one: a planned absence is not overridden by a recurring presence. The same rule is the
SQL function ``identity.planned_state`` (migration 0083) that the call-up uses.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Literal
from zoneinfo import ZoneInfo

TUNIS = ZoneInfo("Africa/Tunis")
ROLES = ("volunteer", "doctor")
KINDS = ("available", "unavailable")
MAX_SLOTS = 20
State = Literal["available", "unavailable"]


@dataclass(frozen=True, slots=True)
class Slot:
    kind: str
    weekdays: tuple[int, ...]
    starts_on: date
    ends_on: date | None
    from_time: time
    to_time: time


def covers(slot: Slot, at: datetime) -> bool:
    local = at.astimezone(TUNIS)
    day, moment = local.date(), local.time().replace(tzinfo=None)
    if day < slot.starts_on or (slot.ends_on is not None and day > slot.ends_on):
        return False
    if slot.weekdays and local.isoweekday() not in slot.weekdays:
        return False
    if slot.from_time <= slot.to_time:
        return slot.from_time <= moment < slot.to_time
    return moment >= slot.from_time or moment < slot.to_time


def planned_state(slots: Iterable[Slot], at: datetime) -> State | None:
    kinds = {s.kind for s in slots if covers(s, at)}
    if "unavailable" in kinds:
        return "unavailable"
    return "available" if "available" in kinds else None
