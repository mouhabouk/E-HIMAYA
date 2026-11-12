"""Informing the partner bodies by phone, OS20: request and response bodies."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.modules.decision.schemas import Bilingual

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]
Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Text500 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9+ ]{3,20}$")]
Agency = Annotated[str, StringConstraints(pattern=r"^[a-z_]{2,30}$")]
Category = Literal["civil", "security", "ministry", "regional", "public"]
Kind = Literal["internal", "external"]
Result = Literal["answered", "no_answer", "busy", "wrong_number"]
Via = Literal["softphone", "manual"]


class Point(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


# ---------------------------------------------------------------- the contact system


class OfficialIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    role: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    phones: list[Phone] = Field(min_length=1, max_length=4)
    email: Short | None = None
    duty: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    position: int = Field(default=1, ge=1, le=50)


class OfficialPatch(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)] | None = None
    role: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    phones: list[Phone] | None = Field(default=None, min_length=1, max_length=4)
    email: Short | None = None
    duty: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    position: int | None = Field(default=None, ge=1, le=50)


class OfficialOut(BaseModel):
    id: uuid.UUID
    body_id: uuid.UUID
    name: str
    role: str | None
    phones: list[str]
    email: str | None
    duty: str | None
    position: int
    status: str
    updated_at: datetime
    updated_by_name: str | None


class BodyIn(BaseModel):
    #: Empty for a national body (central room only); a regional room adds bodies of its own gouvernorat.
    gouvernorat_code: int | None = Field(default=None, ge=1, le=99)
    category: Category
    kind: Kind = "external"
    agency: Agency | None = None
    name: Name
    domain: Short | None = None
    address: Short | None = None
    location: Point | None = None
    public_phone: Phone | None = None
    officials: list[OfficialIn] = Field(default_factory=list, max_length=10)
    #: The report from which a missing body was added.
    origin_incident_id: uuid.UUID | None = None


class BodyPatch(BaseModel):
    category: Category | None = None
    name: Name | None = None
    domain: Short | None = None
    address: Short | None = None
    location: Point | None = None
    public_phone: Phone | None = None
    version: int


class BodyOut(BaseModel):
    id: uuid.UUID
    gouvernorat_code: int | None
    category: str
    kind: str
    agency: str | None
    name: str
    domain: str | None
    address: str | None
    location: Point | None
    public_phone: str | None
    status: str
    created_by_name: str | None
    updated_at: datetime
    updated_by_name: str | None
    version: int
    #: The caller's room keeps this body (regional: its gouvernorat; central: the national bodies).
    editable: bool
    officials: list[OfficialOut]


# ---------------------------------------------------------------- a report


class LevelIn(BaseModel):
    level: Literal[1, 2]
    note: Short | None = None


class LevelOut(BaseModel):
    level: int
    note: str | None
    set_by_name: str | None
    set_at: datetime


class PartyIn(BaseModel):
    body_id: uuid.UUID
    official_id: uuid.UUID | None = None
    suggested: bool = False
    reason: Short | None = None


class PartiesIn(BaseModel):
    parties: list[PartyIn] = Field(min_length=1, max_length=30)


class PartyPatch(BaseModel):
    official_id: uuid.UUID


class CallIn(BaseModel):
    official_id: uuid.UUID | None = None
    number: Phone
    via: Via
    #: The softphone call (telephony) when the call was placed from the room's softphone.
    telephony_call_id: uuid.UUID | None = None
    duration_s: int | None = Field(default=None, ge=0, le=86_400)
    result: Result
    asked: Text500 | None = None
    promised: Text500 | None = None
    eta_min: int | None = Field(default=None, ge=0, le=1440)
    note: Text500 | None = None
    #: Remind the room to call back in so many minutes (0: no reminder).
    follow_up_min: int = Field(default=0, ge=0, le=240)


class CallOut(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    party_id: uuid.UUID
    body_name: str
    official_id: uuid.UUID | None
    official_name: str | None
    number: str
    via: str
    telephony_call_id: uuid.UUID | None
    duration_s: int | None
    result: str
    asked: str | None
    promised: str | None
    eta_min: int | None
    note: str | None
    follow_up_at: datetime | None
    follow_up_done_at: datetime | None
    follow_up_due: bool
    by_name: str | None
    at: datetime
    incident_title: str | None = None
    incident_category: str | None = None


class PartyOut(BaseModel):
    id: uuid.UUID
    body_id: uuid.UUID
    official_id: uuid.UUID | None
    body_name: str
    official_name: str | None
    official_role: str | None
    #: The official's phones (contact system now), then the body's public number.
    phones: list[str]
    public_phone: str | None
    agency: str | None
    category: str | None
    suggested: bool
    reason: str | None
    added_by_name: str | None
    added_at: datetime
    removed_at: datetime | None
    #: The result of the last call; empty: not called yet.
    last_result: str | None
    calls: list[CallOut]


class Suggestion(BaseModel):
    agency: str
    kind: Kind
    #: The body of the contact system (the gouvernorat's, else the national one); empty when it is missing.
    body_id: uuid.UUID | None
    name: str
    public_phone: str | None
    reason: Bilingual
    missing: bool
    in_report: bool


class IncidentLiaison(BaseModel):
    incident_id: uuid.UUID
    gouvernorat_code: int | None
    level: LevelOut | None
    parties: list[PartyOut]
    suggestions: list[Suggestion]


class UsedBefore(BaseModel):
    body_id: uuid.UUID
    official_id: uuid.UUID | None
    body_name: str
    official_name: str | None
    times: int
    last_incident_id: uuid.UUID
    last_at: datetime


class HistoryParty(BaseModel):
    body_id: uuid.UUID
    official_id: uuid.UUID | None
    body_name: str
    official_name: str | None
    official_role: str | None
    last_result: str | None
    calls: int


class HistoryRow(BaseModel):
    incident_id: uuid.UUID
    title: str | None
    category: str
    gouvernorat_code: int | None
    status: str
    opened_at: datetime
    level: int | None
    parties: list[HistoryParty]


class PickerOut(BaseModel):
    suggestions: list[Suggestion]
    #: Bodies informed in earlier reports of the same kind.
    used_before: list[UsedBefore]
    #: Earlier reports and the parties informed in them, newest first.
    history: list[HistoryRow]
