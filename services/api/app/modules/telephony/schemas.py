"""Request and response bodies of the telephony endpoints (docs/api/phase-7-contract.md §4 and §5)."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator


class IceServer(BaseModel):
    urls: list[str]


class CredentialsOut(BaseModel):
    ws_url: str
    sip_uri: str
    username: str
    password: str
    expires_at: datetime
    ice_servers: list[IceServer]


class CallOut(BaseModel):
    id: uuid.UUID
    direction: str
    source: str
    # Full number for operators, ops managers and field commanders; last 2 digits only for the other readers.
    caller_number: str | None
    caller_masked: bool
    started_at: datetime
    answered_at: datetime | None
    ended_at: datetime | None
    duration_s: float | None
    operator_user_id: str | None
    queue: str | None
    status: str
    end_reason: str | None
    report_id: uuid.UUID | None
    incident_id: uuid.UUID | None
    tracking_code: str | None
    gouvernorat_code: int | None
    recording_media_id: uuid.UUID | None
    transferred_to: str | None
    simulated: bool


class CallPage(BaseModel):
    items: list[CallOut]
    next_cursor: str | None


class RecordingOut(BaseModel):
    media_id: uuid.UUID
    sha256: str
    bytes: int | None
    duration_s: float | None
    created_at: datetime


class CallDetail(CallOut):
    recording: RecordingOut | None
    transfer_198_available: bool


TrackingCode = Annotated[str, StringConstraints(pattern=r"^EH-\d{2}-\d{2}-\d{7}$")]


class LinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: uuid.UUID | None = None
    tracking_code: TrackingCode | None = None
    incident_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "LinkIn":
        given = [v for v in (self.report_id, self.tracking_code, self.incident_id) if v is not None]
        if len(given) != 1:
            raise ValueError("give exactly one of report_id, tracking_code, incident_id")
        return self


PhoneText = Annotated[str, StringConstraints(min_length=3, max_length=24, pattern=r"^[0-9+ ().-]+$")]


class DialIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: PhoneText | None = None
    report_id: uuid.UUID | None = None
    volunteer_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "DialIn":
        given = [v for v in (self.number, self.report_id, self.volunteer_id) if v is not None]
        if len(given) != 1:
            raise ValueError("give exactly one of number, report_id, volunteer_id")
        return self


class InviteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: PhoneText | None = None
    volunteer_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "InviteIn":
        if (self.number is None) == (self.volunteer_id is None):
            raise ValueError("give exactly one of number, volunteer_id")
        return self


class ConferenceOut(BaseModel):
    id: uuid.UUID
    room: str
    join_uri: str
    incident_id: uuid.UUID
    created_at: datetime
    ended_at: datetime | None
    active: bool


class ConferenceList(BaseModel):
    items: list[ConferenceOut]


class InviteOut(BaseModel):
    status: str
    number_masked: str


# ---------------------------------------------------------------- internal: SMS gateway, simulation


class SmsInboundIn(BaseModel):
    """Webhook body of the SMS gateway (any extra provider field is ignored)."""

    message_id: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    sender: Annotated[str, StringConstraints(min_length=3, max_length=32)] = Field(alias="from")
    to: Annotated[str, StringConstraints(max_length=32)] | None = None
    text: Annotated[str, StringConstraints(max_length=1600)]
    received_at: AwareDatetime | None = None

    model_config = ConfigDict(populate_by_name=True)


class SmsInboundOut(BaseModel):
    # created: a new report; duplicate: an existing report (gateway retry or repeated SMS); ignored: not a report.
    status: str
    tracking_code: str | None = None
    reason: str | None = None


class SimCall(BaseModel):
    id: uuid.UUID
    status: str
    end_reason: str | None
    recording_state: str
    recording_media_id: uuid.UUID | None
    started_at: datetime
    simulated: bool


class SimCallList(BaseModel):
    items: list[SimCall]
    simulated: bool


def as_json(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
