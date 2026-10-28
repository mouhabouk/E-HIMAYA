"""Inputs and answers of the digital dry run (L5a). Every text has a closed length and every choice a closed list:
the scenario is input like any other and is never trusted for being "only an exercise" (design-l5.md §2.4)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.modules.ops.domain import ResourceKind as Equipment

Code = Annotated[int, Field(ge=11, le=83)]
Kind = Literal["report", "development", "shortage", "evacuation", "decision", "information"]
Action = Literal["acknowledged", "dispatched", "escalated", "evacuation", "decision", "note"]
Status = Literal["draft", "submitted", "ready", "running", "stopped", "ended", "closed"]
Decision = Literal["pending", "approved", "refused", "withdrawn"]
Hazard = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=500)]
MAX_NEEDS = 10
MAX_NEED = 50


def _needs(value: dict[str, int]) -> dict[str, int]:
    if len(value) > MAX_NEEDS:
        raise ValueError("too_many_needs")
    if any(n < 1 or n > MAX_NEED for n in value.values()):
        raise ValueError("invalid_need")
    return value


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExerciseIn(_In):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=160)]
    objective: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]
    hazard_key: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")] | None = None
    plan_document_id: uuid.UUID | None = None
    gouvernorats: Annotated[list[Code], Field(min_length=1, max_length=24)]
    planned_start: datetime
    duration_min: Annotated[int, Field(ge=10, le=720)]
    evaluator: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)] | None = None
    evaluator_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None

    @field_validator("gouvernorats")
    @classmethod
    def _distinct(cls, value: list[int]) -> list[int]:
        return sorted(set(value))


class InjectIn(_In):
    offset_min: Annotated[int, Field(ge=0, le=720)]
    gouvernorat_code: Code | None = None
    kind: Kind
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
    body: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""
    needs: dict[Equipment, int] = Field(default_factory=dict)
    expected: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""

    @field_validator("needs")
    @classmethod
    def _check_needs(cls, value: dict[str, int]) -> dict[str, int]:
        return _needs(value)


class GenerateIn(_In):
    """Reports of the scenario made by the generator: a seeded spread over the run, never more than the limit."""

    count: Annotated[int, Field(ge=1, le=300)]
    kinds: Annotated[list[Hazard], Field(min_length=1, max_length=6)] = ["fire", "traffic_accident", "flood"]
    seed: Annotated[int, Field(ge=0, le=2**31 - 1)] = 0


class ApprovalIn(_In):
    decision: Literal["approved", "refused", "withdrawn"]
    reason: Reason | None = None


class StopIn(_In):
    reason: Reason


class ResponseIn(_In):
    action: Action
    text: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""
    resource_ids: Annotated[list[uuid.UUID], Field(max_length=20)] = Field(default_factory=list)


class EvaluationIn(_In):
    plan_followed: Literal["yes", "partly", "no", "not_applicable"]
    score: Annotated[int, Field(ge=0, le=5)]
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""


class CloseIn(_In):
    conclusion: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=4000)]


class StressIn(_In):
    """What a load run against the isolated copy measured (infra/loadtest/drill.js prints it)."""

    environment: Literal["isolated"]
    reports_sent: Annotated[int, Field(ge=0, le=10_000_000)]
    reports_accepted: Annotated[int, Field(ge=0, le=10_000_000)]
    reports_refused: Annotated[int, Field(ge=0, le=10_000_000)]
    errors_5xx: Annotated[int, Field(ge=0, le=10_000_000)]
    peak_per_second: Annotated[float, Field(ge=0, le=100_000)]
    latency_p95_ms: Annotated[float, Field(ge=0, le=600_000)]
    latency_p99_ms: Annotated[float, Field(ge=0, le=600_000)]
    duration_s: Annotated[int, Field(ge=1, le=86_400)]
    attacks_sent: Annotated[int, Field(ge=0, le=10_000_000)] = 0
    attacks_blocked: Annotated[int, Field(ge=0, le=10_000_000)] = 0
    attack_kinds: Annotated[
        list[Literal["sql_injection", "script", "oversize", "malformed", "flood_same_device"]], Field(max_length=5)
    ] = Field(default_factory=list)


# ---------------------------------------------------------------- answers


class ParticipantOut(BaseModel):
    gouvernorat_code: int
    decision: Decision
    reason: str | None
    decided_by_name: str | None
    decided_at: datetime | None


class InjectOut(BaseModel):
    id: uuid.UUID
    offset_min: int
    gouvernorat_code: int | None
    kind: Kind
    title: str
    body: str
    needs: dict[str, int]
    expected: str
    generated: bool


class ExerciseOut(BaseModel):
    id: uuid.UUID
    title: str
    objective: str
    hazard_key: str | None
    plan_document_id: uuid.UUID | None
    gouvernorats: list[int]
    room: str
    planned_start: datetime
    duration_min: int
    evaluator: str | None
    evaluator_name: str | None
    status: Status
    started_at: datetime | None
    ended_at: datetime | None
    stop_reason: str | None
    stopped_by_name: str | None
    conclusion: str | None
    created_by_name: str | None
    created_at: datetime
    participants: list[ParticipantOut]
    injects: int
    # What the caller may do now (the buttons the administrator granted, and their place in the run).
    can_edit: bool = False
    can_submit: bool = False
    can_start: bool = False
    can_stop: bool = False
    can_evaluate: bool = False
    can_close: bool = False
    my_approval: Code | None = None


class BookingOut(BaseModel):
    resource_id: uuid.UUID
    label: str
    kind: str
    released: bool


class ResponseOut(BaseModel):
    id: uuid.UUID
    gouvernorat_code: int
    action: Action
    text: str
    responded_by_name: str | None
    responded_at: datetime
    bookings: list[BookingOut]


class FeedItem(BaseModel):
    inject: InjectOut
    due_at: datetime
    responses: list[ResponseOut]


class FreeResource(BaseModel):
    id: uuid.UUID
    kind: str
    label: str
    unit: str


class FeedOut(BaseModel):
    """The dry run as a participating room sees it: the injects due by now, in its gouvernorat or for all."""

    exercise_id: uuid.UUID
    status: Status
    elapsed_min: int
    remaining_min: int
    items: list[FeedItem]
    # The resources this room may book now inside the dry run, by kind, and one by one.
    free: dict[str, int]
    free_resources: list[FreeResource]


class EvaluationOut(BaseModel):
    plan_followed: str
    score: int
    notes: str
    evaluated_by_name: str | None
    evaluated_at: datetime


class InjectReport(BaseModel):
    inject: InjectOut
    due_at: datetime | None
    answered: bool
    first_answer_min: float | None
    booked: dict[str, int]
    shortfall: dict[str, int]
    evaluation: EvaluationOut | None


class ResourceLine(BaseModel):
    gouvernorat_code: int
    kind: str
    available_at_start: int
    peak_booked: int
    short: int


class ReportOut(BaseModel):
    """The report of the dry run (design-l5.md §2): the rooms, the resources, the load, the security."""

    exercise: ExerciseOut
    injects: list[InjectReport]
    answered: int
    unanswered: int
    median_answer_min: float | None
    plan_followed: dict[str, int]
    mean_score: float | None
    resources: list[ResourceLine]
    stress: list[StressIn]
