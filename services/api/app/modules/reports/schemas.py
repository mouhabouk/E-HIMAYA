import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, Field, StringConstraints

from app.modules.medical.schemas import LockedFileIn
from app.modules.orgs.schemas import OrganizationCard, OrgRef
from app.modules.reports.domain import LAT_MAX, LAT_MIN, LON_MAX, LON_MIN, Category, Lang, Status


class LocationIn(BaseModel):
    lat: float = Field(ge=LAT_MIN, le=LAT_MAX)
    lon: float = Field(ge=LON_MIN, le=LON_MAX)
    accuracy_m: float | None = Field(default=None, ge=0, le=100_000)


class LocationOut(BaseModel):
    lat: float
    lon: float
    accuracy_m: float | None


BloodGroup = Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class MedicalFile(BaseModel):
    """The 7b medical file, kept on the phone and attached to one report only when the user ticks it (phase B2).
    Every field is optional; free texts are short."""

    model_config = {"extra": "forbid"}

    sex: Literal["female", "male"] | None = None
    birth_date: date | None = None
    blood_group: BloodGroup | None = None
    treatment_card: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    allergies: Short | None = None
    conditions: Short | None = None
    medications: Short | None = None
    other: Short | None = None
    contact_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    contact_phone: Annotated[str, StringConstraints(pattern=r"^\+?[0-9]{6,15}$")] | None = None


class ReportIn(BaseModel):
    client_uuid: uuid.UUID
    category: Category
    text: str | None = Field(default=None, max_length=4000)
    lang: Lang | None = None
    location: LocationIn
    created_at: AwareDatetime
    # Report made on behalf of an institution the caller is a member of (FR-A-080).
    organization_id: uuid.UUID | None = None
    # Phase B2: the reporter's medical file, only when they ticked "attach my medical file to this report". From phase
    # C1-b the app sends here only the emergency card (the fields the reporter chose to leave readable)…
    medical: MedicalFile | None = None
    # …and the rest locked on the phone for the doctors (docs/phase-c/design-medical-axis.md §12).
    medical_locked: LockedFileIn | None = None


class ReportOrganization(BaseModel):
    id: uuid.UUID
    name: str


class MediaOut(BaseModel):
    id: uuid.UUID
    kind: str
    bytes: int | None
    sha256: str
    content_type: str | None
    status: str
    created_at: datetime


class StaffMediaOut(MediaOut):
    url: str | None = None
    # Why the verification worker quarantined the file (declared type does not match its bytes, …).
    rejection_reason: str | None = None


class ReportOut(BaseModel):
    id: uuid.UUID
    tracking_code: str
    client_uuid: uuid.UUID | None
    category: Category
    status: Status
    text: str | None
    lang: str | None
    location: LocationOut
    gouvernorat_code: int | None
    created_at: datetime
    received_at: datetime
    updated_at: datetime
    media: list[MediaOut]
    organization: ReportOrganization | None = None


class ReportPage(BaseModel):
    items: list[ReportOut]
    next_before: datetime | None


class CategoryOut(BaseModel):
    code: Category
    label: str


class HistoryEntry(BaseModel):
    status: Status
    at: datetime


class TrackOut(BaseModel):
    tracking_code: str
    status: Status
    received_at: datetime
    updated_at: datetime
    history: list[HistoryEntry]


# ---------------------------------------------------------------- staff


AnalysisState = Literal["pending", "running", "done", "failed"]
GeoState = Literal["trusted", "pending", "contradictory", "verified"]
SlaBand = Literal["critical", "high", "normal", "low"]
EscalationState = Literal["none", "late", "central_responding", "referred", "referral_accepted", "referral_refused"]
EscalationKind = Literal[
    "late", "central_claim", "referral", "referral_accepted", "referral_refused", "geo_verified", "claim_released"
]


class StaffReport(BaseModel):
    id: uuid.UUID
    tracking_code: str
    category: Category
    status: Status
    text: str | None
    lang: str | None
    # Arabic translation of a French or English text (FR-A-045); null for Arabic texts.
    text_ar: str | None = None
    location: LocationOut
    gouvernorat_code: int | None
    delegation_id: int | None
    reporter_kind: Literal["citizen", "organization", "anonymous"]
    media_count: int
    created_at: datetime
    received_at: datetime
    updated_at: datetime
    # AI layer 1 (phase 3): suggestions for the operator, never applied automatically (BR-06, BR-11).
    priority_score: int | None = None
    credibility_score: int | None = None
    analysis_state: AnalysisState | None = None
    lives_at_risk: bool | None = None
    suggested_category: Category | None = None
    incident_id: uuid.UUID | None = None
    has_suggestion: bool = False
    # Institution the report was made on behalf of (phase 4, FR-A-080).
    organization: OrgRef | None = None
    # Accepted beyond the anonymous budget or quota, or while the rate limiter ran degraded: check before dispatch.
    needs_verification: bool = False
    verification_reason: Literal["anonymous_budget", "anonymous_quota", "limiter_degraded"] | None = None
    # Jurisdiction, claim and SLA (phase 9 §4.6).
    geo_state: GeoState = "trusted"
    geo_candidates: list[int] = Field(default_factory=list)
    claimed_room: str | None = None
    claimed_by_name: str | None = None
    claimed_at: datetime | None = None
    sla_band: SlaBand | None = None
    sla_due_at: datetime | None = None
    escalation_state: EscalationState = "none"
    late: bool = False


class StaffHistoryEntry(BaseModel):
    status: Status
    at: datetime
    actor: str
    note: str | None


class Reporter(BaseModel):
    kind: Literal["citizen", "organization", "anonymous"]
    # Identity hidden outside the handling operations room (§1.3): names null, phone reduced to its last two digits.
    masked: bool = False
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None


class ReporterContextOut(BaseModel):
    reporter_gouvernorat_code: int | None
    source: Literal["profile", "none"]


class EscalationOut(BaseModel):
    kind: EscalationKind
    from_room: str | None
    to_room: str | None
    actor_name: str | None
    at: datetime
    reason: str | None


class ScoreComponent(BaseModel):
    key: str
    # Priority: value 0..1 (null = no data yet), weight and points; credibility: points only.
    value: float | None = None
    weight: int | None = None
    points: float
    detail: dict[str, Any]


class ExplainedScore(BaseModel):
    score: int
    components: list[ScoreComponent]


class Extraction(BaseModel):
    language: str
    category: Category
    lives_at_risk: bool
    people_trapped: bool
    injured_count: int
    deaths_reported: bool
    hazards: list[str]
    keywords: list[str]
    summary_ar: str
    confidence: float


class Suggestion(BaseModel):
    kind: Literal["incident", "report"]
    incident_id: uuid.UUID | None
    report_id: uuid.UUID
    tracking_code: str
    score: float
    distance_m: float
    minutes: float
    similarity: float | None
    reasons: list[str]
    matching_reports: int


class Transcript(BaseModel):
    media_id: uuid.UUID
    kind: str
    text: str | None
    language: str | None
    language_probability: float | None
    duration_s: float | None
    translation_ar: str | None
    error: str | None
    model: str | None


class AnalysisOut(BaseModel):
    state: AnalysisState
    attempts: int
    language: str | None
    # transcribe / extract / translate / embed: done | skipped | failed | unavailable | disabled
    steps: dict[str, str]
    extraction: Extraction | None
    priority: ExplainedScore | None
    credibility: ExplainedScore | None
    suggestion: Suggestion | None
    transcripts: list[Transcript]
    models: dict[str, str]
    updated_at: datetime


class StaffReportDetail(StaffReport):
    history: list[StaffHistoryEntry]
    media: list[StaffMediaOut]
    reporter: Reporter
    allowed_transitions: list[Status]
    analysis: AnalysisOut | None = None
    # What responders need about that institution (registers, representative, evacuation points).
    organization_card: OrganizationCard | None = None
    escalations: list[EscalationOut] = Field(default_factory=list)
    reporter_context: ReporterContextOut | None = None
    # Phase B2: the reporter attached their medical file (opened with GET …/medical, audited).
    medical_attached: bool = False


class MedicalOut(BaseModel):
    data: MedicalFile
    attached_at: datetime
    # Phase C1-b: the rest of the file is locked for the doctors (the operations room reads the card only).
    locked: bool = False


class StaffReportPage(BaseModel):
    items: list[StaffReport]
    next_cursor: str | None


class StatusChangeIn(BaseModel):
    status: Status
    note: str | None = Field(default=None, max_length=1000)


class GouvernoratCount(BaseModel):
    code: int | None
    count: int


class Kpis(BaseModel):
    since: datetime
    total: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    by_gouvernorat: list[GouvernoratCount]
    avg_first_response_s: float | None
    # Reports with priority >= 70, and reports still waiting for their AI analysis.
    high_priority: int = 0
    analysis_pending: int = 0
    # Institutions hub (phase 4): registrations and certificates waiting for the auditor, in scope.
    orgs_pending_review: int = 0
    certificates_submitted: int = 0


class QuotaOut(BaseModel):
    """Anonymous report quota (phase 9 §3); all null for registered accounts (no quota)."""

    limit: int | None
    used: int | None
    remaining: int | None


Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=500)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class ReleaseIn(BaseModel):
    reason: Reason


class DirectiveSpec(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=150)]
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
    urgency: Literal["normal", "urgent"] = "normal"


class ReferIn(BaseModel):
    to_gouvernorat_code: int
    reason: Reason
    directive: DirectiveSpec | None = None


class ReferralAcceptIn(BaseModel):
    note: Note | None = None


class ReferralRefuseIn(BaseModel):
    reason: Reason


class GeoVerifyIn(BaseModel):
    gouvernorat_code: int
    reason: Reason
