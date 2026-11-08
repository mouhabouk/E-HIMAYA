import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["intervention", "room", "admin"]
AbsenceKind = Literal[
    "sick", "rest", "annual", "compensatory", "paternity", "maternity", "mission", "training", "other"
]
EventKind = Literal["rank", "appointment", "transfer", "sanction", "reward"]


class UnitOut(BaseModel):
    id: uuid.UUID
    name: str
    gouvernorat_code: int


class AbsenceBrief(BaseModel):
    """What the operations rooms see of an absence: its kind and dates, never its reference or note."""

    id: uuid.UUID
    kind: AbsenceKind
    starts_on: date
    ends_on: date


class AgentRow(BaseModel):
    id: uuid.UUID
    matricule: str
    full_name: str
    rank: str | None
    post: str | None
    category: Category
    unit_id: uuid.UUID
    unit_name: str
    gouvernorat_code: int
    # The personnel department only.
    phone: str | None
    # The absence of the day asked for; none: present.
    absence: AbsenceBrief | None
    version: int


class AgentsOut(BaseModel):
    on: date
    items: list[AgentRow]
    can_edit: bool


class AgentIn(BaseModel):
    unit_id: uuid.UUID
    matricule: str = Field(min_length=2, max_length=30)
    full_name: str = Field(min_length=2, max_length=120)
    rank: str | None = Field(default=None, max_length=60)
    post: str | None = Field(default=None, max_length=80)
    category: Category = "intervention"
    phone: str | None = Field(default=None, max_length=30)


class AgentEdit(BaseModel):
    """The identity of a member of staff; the rank, the function and the unit change through the file's events."""

    matricule: str = Field(min_length=2, max_length=30)
    full_name: str = Field(min_length=2, max_length=120)
    category: Category
    phone: str | None = Field(default=None, max_length=30)
    version: int


class EventIn(BaseModel):
    kind: EventKind
    effective_on: date
    # rank: the new rank; appointment: the function; sanction or reward: its kind. Not used by a transfer.
    title: str | None = Field(default=None, max_length=120)
    # transfer: the unit joined (required); appointment: a unit of the same gouvernorat (optional).
    unit_id: uuid.UUID | None = None
    reference: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=1000)


class EventOut(BaseModel):
    id: uuid.UUID
    kind: EventKind
    effective_on: date
    title: str | None
    unit_id: uuid.UUID | None
    unit_name: str | None
    from_unit_id: uuid.UUID | None
    from_unit_name: str | None
    reference: str | None
    note: str | None
    created_by_name: str | None
    created_at: datetime
    cancelled_at: datetime | None
    cancelled_by_name: str | None
    cancel_reason: str | None


class AbsenceIn(BaseModel):
    agent_id: uuid.UUID
    kind: AbsenceKind
    starts_on: date
    ends_on: date
    reference: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=1000)
    # Required by a change (optimistic locking), ignored by a creation.
    version: int | None = None


class AbsenceOut(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    matricule: str
    full_name: str
    unit_id: uuid.UUID
    unit_name: str
    gouvernorat_code: int
    kind: AbsenceKind
    starts_on: date
    ends_on: date
    days: int
    # The personnel department only (null for the operations rooms).
    reference: str | None
    note: str | None
    created_by_name: str | None
    created_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    version: int


class AbsencesOut(BaseModel):
    start: date
    end: date
    items: list[AbsenceOut]
    can_edit: bool


class AgentFile(BaseModel):
    agent: AgentRow
    events: list[EventOut]
    absences: list[AbsenceOut]


class ReasonIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class Count(BaseModel):
    total: int
    absent: int
    present: int
    by_kind: dict[str, int]


class StrengthRow(BaseModel):
    unit_id: uuid.UUID | None
    unit_name: str
    gouvernorat_code: int | None
    # Intervention staff present are the ones a room may call; room (logistics) and administrative staff are counted
    # on their own lines and never among those ready to intervene.
    intervention: Count
    room: Count
    admin: Count


class StrengthOut(BaseModel):
    on: date
    units: list[StrengthRow]
    total: StrengthRow
