"""Crew accountability in danger zones, OS7 (docs/phase-os7/design-os7.md)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Zone = Literal["hot", "warm"]
Situation = Literal["controlled", "progress", "not_controlled"]
AwayWhy = Literal["air", "water_fuel", "care", "rest", "other"]
PauseWhy = Literal["danger_over", "defensive", "ops_stopped", "comms_failure", "other"]
AutoEvent = Literal["collapse", "defensive", "evacuation", "severity"]
CheckAllWhy = Literal["collapse", "defensive", "evacuation", "commander"]
TeamStatus = Literal["ok", "soon", "late", "alarm", "missing", "paused", "out"]
MemberKey = Field(pattern=r"^m[0-9]{1,2}$")


# ---------------------------------------------------------------- settings


class SettingIn(BaseModel):
    hot_s: Literal[300, 600, 900]
    warm_s: Literal[600, 900, 1200]
    grace_s: int = Field(ge=30, le=180)
    auto_events: list[AutoEvent] = Field(default_factory=list, max_length=4)


class SettingOut(SettingIn):
    gouvernorat_code: int | None
    remind_s: int
    updated_at: datetime | None = None
    updated_by_name: str | None = None


# ---------------------------------------------------------------- teams


class MemberOut(BaseModel):
    key: str
    name: str
    role: str | None = None
    away_why: AwayWhy | None = None
    away_at: datetime | None = None


class TeamOut(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    incident_id: uuid.UUID
    label: str
    task: str | None
    zone: Zone
    status: TeamStatus
    interval_s: int
    due_at: datetime | None
    remaining_s: int | None
    last_confirmed_at: datetime
    next_at: datetime | None
    paused_at: datetime | None
    pause_reason: str | None
    out_at: datetime | None
    out_count: int | None
    entered_at: datetime
    leader_name: str | None
    members: list[MemberOut]
    present: int
    away: int


class MissingOut(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    team_label: str
    resource: str
    carrier: str
    place: str | None
    reported_at: datetime
    reported_by_name: str | None
    replacement_at: datetime | None
    recovered_at: datetime | None
    recovered_by_name: str | None


class SitrepOut(BaseModel):
    id: int
    team_id: uuid.UUID
    team_label: str
    at: datetime
    situation: Situation
    reinforcement: bool
    text: str | None
    voice_seconds: int | None
    edited: bool
    by_name: str | None


class EventOut(BaseModel):
    at: datetime
    kind: str
    text: str
    by_name: str | None
    team_id: uuid.UUID | None


class ClosureOut(BaseModel):
    closed_at: datetime
    closed_by_name: str | None
    automatic: bool
    summary: dict[str, int]


class Kpis(BaseModel):
    agents_in: int
    teams_in: int
    not_confirmed: int
    missing_open: int


class Board(BaseModel):
    incident_id: uuid.UUID
    incident_kind: str
    incident_status: str
    gouvernorat_code: int | None
    settings: SettingOut
    kpis: Kpis
    teams: list[TeamOut]
    missing: list[MissingOut]
    sitreps: list[SitrepOut]
    events: list[EventOut]
    all_out: bool
    closure: ClosureOut | None
    now: datetime


class IncidentRow(BaseModel):
    incident_id: uuid.UUID
    incident_kind: str
    gouvernorat_code: int | None
    teams_in: int
    agents_in: int
    alarms: int
    missing_open: int
    last_sitrep: Situation | None
    closed: bool


# ---------------------------------------------------------------- the room's actions


class TeamsIn(BaseModel):
    """One team, or every team of the incident inside the zone."""

    team_id: uuid.UUID | None = None


class NextIn(TeamsIn):
    at: datetime


class PauseIn(TeamsIn):
    reason: PauseWhy
    detail: str | None = Field(default=None, max_length=300)


class CheckAllIn(BaseModel):
    reason: CheckAllWhy


# ---------------------------------------------------------------- the team leader's phone


class EnterIn(BaseModel):
    zone: Zone
    task: str | None = Field(default=None, max_length=200)


class AwayIn(BaseModel):
    member: str = MemberKey
    why: AwayWhy


class MemberIn(BaseModel):
    member: str = MemberKey


class MissingIn(BaseModel):
    resource: str = Field(min_length=2, max_length=80)
    member: str = MemberKey
    place: str | None = Field(default=None, max_length=200)


class SitrepIn(BaseModel):
    situation: Situation
    reinforcement: bool = False
    text: str | None = Field(default=None, max_length=2000)
    # A dictated message: its length and the text the transcription gave, before the leader corrected it.
    voice_seconds: int | None = Field(default=None, ge=1, le=600)
    transcript: str | None = Field(default=None, max_length=2000)


class ExitIn(BaseModel):
    members: list[str] = Field(min_length=1, max_length=20)


class MissionPar(BaseModel):
    """What the team leader's phone shows for one mission."""

    enabled: bool = True
    settings: SettingOut
    team: TeamOut | None
    missing: list[MissingOut]
    last_sitrep: SitrepOut | None
    closed: bool
    resources: list[str]
    now: datetime
