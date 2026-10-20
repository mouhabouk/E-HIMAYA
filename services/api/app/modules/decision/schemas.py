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
    reason: Bilingual


class RespondersOut(BaseModel):
    incident_id: uuid.UUID
    items: list[Responder]


class AssistantIn(BaseModel):
    question: Annotated[Text, StringConstraints(min_length=3, max_length=1000)]
    lang: Literal["ar", "fr"] = "ar"


class Source(BaseModel):
    kind: Literal["procedure", "incident", "report"]
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
