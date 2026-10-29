"""Task list read from a plan (docs/phase-l/design-l5.md §2.3, AI2)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

State = Literal["queued", "reading", "review", "approved", "failed"]
Review = Literal["suggested", "accepted", "edited", "deleted", "added"]
Status = Literal["todo", "doing", "done", "not_applicable"]


class PlanRef(BaseModel):
    id: str
    number: str
    title: str


class TaskOut(BaseModel):
    id: str
    position: int
    action: str
    owner: str
    resource: str
    page: int | None
    # The passage of the plan the model rested the task on, and whether it was found on that page.
    quote: str
    quote_found: bool | None
    origin: Literal["ai", "manual"]
    review: Review
    # What the model suggested, when the reviewer changed it.
    suggested: dict[str, str | int | None] | None
    status: Status
    note: str
    # Names are shown to the operations rooms only (as on the axis).
    status_by_name: str | None
    status_at: datetime | None


class Counts(BaseModel):
    suggested: int = 0
    kept: int = 0
    deleted: int = 0
    todo: int = 0
    doing: int = 0
    done: int = 0
    not_applicable: int = 0


class ChecklistOut(BaseModel):
    id: str | None
    state: State | None
    error: str | None
    plan: PlanRef | None
    # The plans this list can be read from: the axis's plan in force and the plans of its hazard, or the dry run's.
    plans: list[PlanRef]
    model: str | None
    pages: int | None
    pages_read: int | None
    requested_by_name: str | None
    requested_at: datetime | None
    read_at: datetime | None
    approved_by_name: str | None
    approved_at: datetime | None
    version: int
    tasks: list[TaskOut]
    counts: Counts
    # The local model's reading is switched on in the AI settings (AI-01) and a model is configured.
    reading_available: bool
    can_review: bool
    can_follow: bool


class ReadIn(BaseModel):
    document_id: uuid.UUID
    # The list's version when one exists: reading again replaces suggestions not approved yet.
    version: int | None = None


class TaskIn(BaseModel):
    action: str = Field(min_length=3, max_length=400)
    owner: str = Field(default="", max_length=160)
    resource: str = Field(default="", max_length=160)
    page: int | None = Field(default=None, ge=1, le=2000)


class ReviewIn(BaseModel):
    decision: Literal["accept", "edit", "delete"]
    # With "edit": the task as the reviewer writes it.
    task: TaskIn | None = None


class ApproveIn(BaseModel):
    version: int


class FollowIn(BaseModel):
    status: Status
    note: str = Field(default="", max_length=500)
