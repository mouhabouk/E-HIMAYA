import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.modules.decision.domain import Confidence, RecommendationKind

Text = Annotated[str, StringConstraints(strip_whitespace=True)]


class Bilingual(BaseModel):
    ar: str
    fr: str


class LatLon(BaseModel):
    lat: float
    lon: float


class Action(BaseModel):
    """A button wired to an existing flow of the dashboard; nothing is applied until the operator confirms it."""

    type: Literal["open_assignment", "open_alert_form", "call", "show_route"]
    label: Bilingual | None = None
    # open_assignment
    resource_id: uuid.UUID | None = None
    order: str | None = None
    # open_alert_form: a draft of the phase 5 alert form (MessageIn fields)
    prefill: dict[str, Any] | None = None
    # call
    number: str | None = None
    volunteer_id: uuid.UUID | None = None
    report_id: uuid.UUID | None = None
    # show_route
    from_: LatLon | None = Field(default=None, alias="from", serialization_alias="from")
    to: LatLon | None = None
    profile: Literal["car", "truck"] | None = None

    model_config = {"populate_by_name": True}


class Recommendation(BaseModel):
    kind: RecommendationKind
    title: Bilingual
    rationale: Bilingual
    inputs: dict[str, Any]
    confidence: Confidence
    actions: list[Action] = Field(default_factory=list)


class Recommendations(BaseModel):
    incident_id: uuid.UUID
    generated_at: datetime
    items: list[Recommendation]
    # Inputs from the simulated weather provider or a simulated forecast (WEATHER_PROVIDER=sim).
    simulated: bool = False
    # "Every recommendation is shown with its justification and inputs, and a human decides."
    notice: Bilingual


class RouteOut(BaseModel):
    distance_m: int
    duration_s: int
    geometry: dict[str, Any]
    engine: Literal["osrm", "valhalla", "fallback"]
    simulated: bool
    attribution: str | None = None
    fallback_reason: Literal["not_configured", "engine_unavailable", "no_route"] | None = None
    assumptions: list[str] | None = None


class Responder(BaseModel):
    id: str
    kind: Literal["unit", "committee", "agency", "institution"]
    name: str
    name_fr: str | None = None
    role: str | None = None
    organization: str | None = None
    phone: str | None = None
    email: str | None = None
    gouvernorat_code: int | None = None
    distance_m: int | None = None
    # A unit (L4 §10): its place, and the road distance and time to the incident ("fallback" engine = an estimate).
    lat: float | None = None
    lon: float | None = None
    road_m: int | None = None
    road_s: int | None = None
    engine: str | None = None
    reason: Bilingual


class RespondersOut(BaseModel):
    incident_id: uuid.UUID
    items: list[Responder]


class AssistantIn(BaseModel):
    question: Annotated[Text, StringConstraints(min_length=3, max_length=1000)]
    lang: Literal["ar", "fr"] = "ar"


class Source(BaseModel):
    kind: Literal["procedure", "incident", "report", "memory"]
    id: str
    title: str
    excerpt: str
    # Public references behind a procedure passage.
    references: list[dict[str, str]] = Field(default_factory=list)


class AssistantOut(BaseModel):
    answer: str
    # True when the model found the answer in the sources; False: the answer says it does not know.
    supported: bool
    sources: list[Source]
    model: str
    notice: Bilingual


# ---------------------------------------------------------------- commander's assistant (AI5a)

CommandKind = Literal["resources", "volunteers", "route", "escalation", "alert", "responders", "note"]
CommandStatus = Literal["proposed", "adopted", "modified", "rejected", "expired"]
ReasonCode = Literal["not_needed", "already_done", "wrong_resource", "too_slow", "unsafe", "wrong_reading", "other"]


class Track(BaseModel):
    """What commanders did with the same proposal in incidents of the same category (the assistant's memory)."""

    decided: int
    adopted: int
    modified: int
    rejected: int
    top_reason: ReasonCode | None = None


class Reading(BaseModel):
    """How a commander's text was read (orders.py)."""

    intent: Literal["question", "order"]
    action: Literal["dispatch", "alert", "escalate", "volunteers", "call", "route", "note"] | None = None
    resource_kind: str | None = None
    count: int | None = None
    level: Literal["crisis", "disaster"] | None = None
    reader: Literal["rules", "model", "combined"]


class CommandCard(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    origin: Literal["rules", "order"]
    kind: CommandKind
    key: str
    title: Bilingual
    rationale: Bilingual
    confidence: Confidence
    inputs: dict[str, Any]
    actions: list[Action]
    status: CommandStatus
    command_text: str | None = None
    model: str | None = None
    simulated: bool
    track: Track
    created_at: datetime
    decided_at: datetime | None = None
    decided_by_name: str | None = None
    # Indices of the actions the commander kept, and their note.
    kept_actions: list[int] | None = None
    note: str | None = None
    reason_code: ReasonCode | None = None


class CommandBoard(BaseModel):
    incident_id: uuid.UUID
    generated_at: datetime
    # Open proposals, then the latest decisions on this incident.
    proposals: list[CommandCard]
    decided: list[CommandCard]
    simulated: bool = False
    notice: Bilingual


class CommandTextIn(BaseModel):
    text: Annotated[Text, StringConstraints(min_length=3, max_length=1000)]
    lang: Literal["ar", "fr"] = "ar"


class CommandTextOut(BaseModel):
    reading: Reading
    # True when the language model failed and the rules alone read the text.
    fallback: bool = False
    answer: AssistantOut | None = None
    card: CommandCard | None = None


class DecideIn(BaseModel):
    verdict: Literal["adopt", "modify", "reject"]
    # modify: the indices of the card's actions the commander keeps (others are dropped).
    kept_actions: list[Annotated[int, Field(ge=0, lt=50)]] | None = Field(default=None, max_length=50)
    note: Annotated[Text, StringConstraints(max_length=500)] | None = None
    reason_code: ReasonCode | None = None
