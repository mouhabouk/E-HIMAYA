import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints

from app.modules.orgs.domain import (
    ActivityKind,
    CertificateKind,
    CertificateStatus,
    ChangeSection,
    DocumentKind,
    EquipmentKind,
    FeatureKind,
    HazmatUnit,
    IdentifierType,
    InspectionResult,
    InspectionSection,
    OrgKind,
    OrgRole,
    OrgStatus,
    ReservationState,
    TeamRole,
    VisitDecision,
    VisitOrigin,
    VisitStatus,
)
from app.modules.reports.domain import LAT_MAX, LAT_MIN, LON_MAX, LON_MIN

Text200 = Field(default=None, max_length=200)


class Point(BaseModel):
    lat: float = Field(ge=LAT_MIN, le=LAT_MAX)
    lon: float = Field(ge=LON_MIN, le=LON_MAX)


class Person(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None


class OrgIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    kind: OrgKind
    identifier_type: IdentifierType
    identifier: str = Field(min_length=1, max_length=24)
    activity_sector: str | None = Text200
    activity_type: str | None = Text200
    capacity: int | None = Field(default=None, ge=0, le=1_000_000)
    floors: int | None = Field(default=None, ge=0, le=300)
    height_m: float | None = Field(default=None, ge=0, le=1000)
    receives_public: bool = False
    address: str | None = Field(default=None, max_length=300)
    location: Point
    manager: Person = Field(default_factory=Person)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=20)
    # Answers to the fields of the kind (``GET /public/org-kinds``); unknown keys are dropped.
    kind_fields: dict[str, int | bool | str | None] = Field(default_factory=dict, max_length=40)


class OrgUpdate(OrgIn):
    version: int = Field(ge=1)


class ClassificationOut(BaseModel):
    family: Literal["high_rise", "industrial", "erp", "workplace"]
    category: int | None
    high_rise: bool
    required: list[str]
    provisional: bool


class Completeness(BaseModel):
    ok: bool
    missing: list[str]


class Alert(BaseModel):
    kind: Literal[
        "training_expired",
        "training_expiring",
        "maintenance_overdue",
        "maintenance_due_soon",
        # Phase P3a: the current certificate (``ref`` is its id).
        "certificate_expiring",
        "certificate_expired",
        "certificate_needs_update",
        # Phase P3b: a visit to come (``ref`` the visit), a reservation's deadline (``ref`` the reservation) and the
        # current prevention certificate (``ref`` the certificate).
        "visit_scheduled",
        "reservation_due_soon",
        "reservation_overdue",
        "prevention_expiring",
        "prevention_expired",
    ]
    ref: uuid.UUID
    since: date | None


class Review(BaseModel):
    reason: str | None
    at: datetime | None


class OrgCard(BaseModel):
    """Fields shared by the member and staff views."""

    id: uuid.UUID
    status: OrgStatus
    version: int
    name: str
    kind: OrgKind
    identifier_type: IdentifierType
    identifier: str
    activity_sector: str | None
    activity_type: str | None
    capacity: int | None
    floors: int | None
    height_m: float | None
    receives_public: bool
    address: str | None
    location: Point
    gouvernorat_code: int | None
    delegation_id: int | None
    manager: Person
    contact_email: str | None
    contact_phone: str | None
    classification: ClassificationOut
    completeness: Completeness
    # Share of the safety requirements met, in percent (addition 12).
    readiness: int
    # Only the fields this reader may see (members: all; auditor: public and institution-and-Office).
    kind_fields: dict[str, int | bool | str]
    # Migrated from a kind with no equivalent: the auditor picks the right one.
    kind_review: bool
    alerts: list[Alert]
    review: Review
    created_at: datetime
    updated_at: datetime


class OrgOut(OrgCard):
    my_role: OrgRole


class MyOrg(BaseModel):
    id: uuid.UUID
    name: str
    kind: OrgKind
    status: OrgStatus
    my_role: OrgRole
    alerts_count: int


# ---------------------------------------------------------------- members


class MemberOut(BaseModel):
    user_id: uuid.UUID
    display_name: str | None
    email: str | None
    role: OrgRole
    joined_at: datetime


class MemberRoleIn(BaseModel):
    role: OrgRole


class InvitationIn(BaseModel):
    email: EmailStr
    role: OrgRole = OrgRole.MEMBER


class InvitationOut(BaseModel):
    id: uuid.UUID
    email: str
    role: OrgRole
    expires_at: datetime
    created_at: datetime


class InvitationCreated(InvitationOut):
    token: str
    accept_url: str


class InvitationPreview(BaseModel):
    org_name: str
    role: OrgRole
    email: str
    expires_at: datetime


class InvitationAccepted(BaseModel):
    org_id: uuid.UUID
    role: OrgRole


# ---------------------------------------------------------------- safety team, registers, features


class TeamMemberIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    team_role: TeamRole = "member"
    position: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    last_training_on: date | None = None
    training_valid_months: int = Field(default=24, ge=1, le=120)


class TeamMemberOut(TeamMemberIn):
    id: uuid.UUID
    training_status: Literal["valid", "expiring", "expired", "unknown"]
    training_expires_on: date | None


class HazmatIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    un_number: str | None = Field(default=None, max_length=4)
    hazard_class: str | None = Field(default=None, max_length=8)
    quantity: float = Field(ge=0, le=1e11)
    unit: HazmatUnit
    storage_location: str | None = Text200
    sds_document_id: uuid.UUID | None = None


class HazmatOut(HazmatIn):
    id: uuid.UUID


class EquipmentIn(BaseModel):
    kind: EquipmentKind
    count: int = Field(ge=0, le=100_000)
    location: str | None = Text200
    last_maintenance_on: date | None = None
    maintenance_interval_months: int = Field(default=12, ge=1, le=120)


class EquipmentOut(EquipmentIn):
    id: uuid.UUID
    maintenance_status: Literal["ok", "due_soon", "overdue", "unknown"]
    next_maintenance_on: date | None


class FeatureIn(BaseModel):
    kind: FeatureKind
    label: str | None = Field(default=None, max_length=120)
    location: Point


class FeatureOut(FeatureIn):
    id: uuid.UUID


# ---------------------------------------------------------------- documents


class DocumentIn(BaseModel):
    kind: DocumentKind
    title: str = Field(min_length=1, max_length=200)


class DocumentTitleIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class DocumentVersionOut(BaseModel):
    version: int
    filename: str | None
    content_type: str
    bytes: int | None
    sha256: str
    status: Literal["uploading", "verifying", "stored", "rejected"]
    uploaded_at: datetime
    uploaded_by: str | None
    note: str | None


class DocumentOut(BaseModel):
    id: uuid.UUID
    kind: DocumentKind
    title: str
    current_version: DocumentVersionOut | None
    versions_count: int


class DownloadOut(BaseModel):
    url: str


# ---------------------------------------------------------------- certificates


class CertificateChange(BaseModel):
    """A substantive difference between the certified snapshot and the institution today (phase P3a)."""

    section: ChangeSection
    field: str
    certified: Any
    current: Any


class StampOut(BaseModel):
    """A paper certificate stamped by hand at a regional administration (phase P3a)."""

    id: uuid.UUID
    place: str
    gouvernorat_code: int | None
    stamped_on: date
    note: str | None
    stamped_by_name: str | None
    recorded_at: datetime
    has_photo: bool
    # The comparison with the institution when it was stamped; empty when it matched.
    changes: list[CertificateChange] = Field(default_factory=list)


class StampIn(BaseModel):
    place: str = Field(min_length=1, max_length=200)
    stamped_on: date
    note: str | None = Field(default=None, max_length=500)


class PublicStamp(BaseModel):
    place: str
    stamped_on: date


class CertificateOut(BaseModel):
    id: uuid.UUID
    code: str
    kind: CertificateKind = "safety"
    status: CertificateStatus
    superseded: bool
    created_at: datetime
    submitted_at: datetime | None
    reviewed_at: datetime | None
    review_reason: str | None
    valid_until: date | None
    fingerprint: str
    pdf_sha256: str
    verify_url: str
    key_id: str | None = None
    revoked_at: datetime | None = None
    revoke_reason: str | None = None
    # Phase P3a, on the current approved certificate only: substantive changes since it was certified.
    needs_update: bool | None = None
    changes: list[CertificateChange] = Field(default_factory=list)
    stamps: list[StampOut] = Field(default_factory=list)


class PublicCertificate(BaseModel):
    code: str
    kind: CertificateKind = "safety"
    status: Literal["submitted", "approved", "rejected", "revoked"]
    valid: bool
    superseded: bool
    org_name: str
    org_kind: OrgKind
    gouvernorat_code: int | None
    classification: dict[str, Any]
    issued_at: datetime | None
    valid_until: date | None
    fingerprint: str
    pdf_sha256: str
    signature_valid: bool
    # Phase 10 §4.1: the signing key, and the revocation (its reason is never public).
    key_id: str | None = None
    revoked: bool = False
    revoked_at: datetime | None = None
    # Phase P3a: where and when the paper certificate was stamped (never by whom).
    stamps: list[PublicStamp] = Field(default_factory=list)
    # Phase P3b, prevention certificate: granted with reservations (their text is not public).
    with_reservations: bool = False


class SigningKeyOut(BaseModel):
    algorithm: Literal["Ed25519"]
    public_key: str | None  # base64 of the raw 32-byte public key; null when signing is not configured
    signed_message: str  # how the signed message is built from the certificate fields
    key_id: str | None = None  # first 16 hex characters of the SHA-256 of public_key
    # Earlier keys whose certificates stay verifiable (phase 10 §4.1): {key_id: base64 raw public key}.
    previous_keys: dict[str, str] = {}
    # Printed on every certificate: what it is and what it is not, in ar/fr/en.
    disclaimer: dict[str, str] = {}


# ---------------------------------------------------------------- reports of the institution


class OrgReport(BaseModel):
    id: uuid.UUID
    tracking_code: str
    category: str
    status: str
    text: str | None
    received_at: datetime
    updated_at: datetime
    reporter_display_name: str | None


class OrgReportPage(BaseModel):
    items: list[OrgReport]
    next_cursor: str | None


class SummaryTeamMember(BaseModel):
    full_name: str
    team_role: TeamRole
    phone: str | None
    training_status: str


class SummaryHazmat(BaseModel):
    name: str
    un_number: str | None
    quantity: float
    unit: HazmatUnit


class OrgSummary(BaseModel):
    """Short card for the mobile app (FR-A-081)."""

    id: uuid.UUID
    name: str
    kind: OrgKind
    status: OrgStatus
    capacity: int | None
    address: str | None
    location: Point
    classification: ClassificationOut
    readiness: int
    missing: list[str]
    kind_fields: dict[str, int | bool | str]
    team: list[SummaryTeamMember]
    hazmat_count: int
    hazmat: list[SummaryHazmat]
    alerts_count: int
    alerts: list[Alert]
    # Phase P2b: Office messages waiting for this institution's read acknowledgement.
    messages_pending: int = 0


# ---------------------------------------------------------------- Office messages, awareness, activities (P2b)


class OrgMessage(BaseModel):
    """An Office message addressed to the institution, with its acknowledgement."""

    id: uuid.UUID
    topic: str | None
    title: dict[str, str]
    body: dict[str, str]
    published_at: datetime
    ack_required: bool
    acked_at: datetime | None
    acked_by: str | None


class AwarenessTip(BaseModel):
    id: uuid.UUID
    hazard: str
    content: dict[str, Any]
    updated_at: datetime


class ActivityIn(BaseModel):
    kind: ActivityKind
    title: str = Field(min_length=1, max_length=120)
    starts_on: date
    ends_on: date | None = None
    participants: int | None = Field(default=None, ge=0, le=1_000_000)
    notes: str | None = Field(default=None, max_length=1000)


class ActivityOut(ActivityIn):
    id: uuid.UUID
    created_by: str | None
    created_at: datetime


class StaffActivity(ActivityOut):
    org_id: uuid.UUID
    org_name: str
    org_kind: OrgKind
    gouvernorat_code: int | None


class MaintenanceIn(BaseModel):
    done_on: date
    note: str | None = Field(default=None, max_length=500)
    document_id: uuid.UUID | None = None


class MaintenanceOut(BaseModel):
    id: uuid.UUID
    equipment_id: uuid.UUID
    done_on: date
    note: str | None
    document_id: uuid.UUID | None
    # Stored version of the photo, to download it; None while it is being checked or when there is none.
    photo_version: int | None
    recorded_by: str | None
    recorded_at: datetime


# ---------------------------------------------------------------- staff


class StaffOrg(BaseModel):
    id: uuid.UUID
    name: str
    kind: OrgKind
    status: OrgStatus
    identifier_type: IdentifierType
    identifier: str
    gouvernorat_code: int | None
    capacity: int | None
    location: Point
    classification: ClassificationOut
    kind_review: bool
    hazmat_count: int
    alerts_count: int
    certificate_status: Literal["none", "draft", "submitted", "approved", "rejected", "revoked", "expired"]
    certificate_valid_until: date | None
    created_at: datetime


class StaffOrgPage(BaseModel):
    items: list[StaffOrg]
    next_cursor: str | None


class StaffMember(BaseModel):
    display_name: str | None
    email: str | None
    role: OrgRole


class StaffOrgDetail(OrgCard):
    team: list[TeamMemberOut]
    hazmat: list[HazmatOut]
    equipment: list[EquipmentOut]
    features: list[FeatureOut]
    documents: list[DocumentOut]
    members: list[StaffMember]
    certificates: list[CertificateOut]
    # Phase P2b.
    activities: list[ActivityOut] = Field(default_factory=list)
    maintenance: list[MaintenanceOut] = Field(default_factory=list)


class OrgReviewIn(BaseModel):
    decision: Literal["approve", "reject", "suspend", "reinstate"]
    reason: str | None = Field(default=None, max_length=1000)
    # On approval the auditor may correct the kind (addition 6 bis); fields of the old kind not in the new are dropped.
    kind: OrgKind | None = None


class KindFieldOut(BaseModel):
    key: str
    type: Literal["int", "bool", "text"]
    visibility: Literal["public", "org_office", "incident"]
    maximum: int


class KindOut(BaseModel):
    kind: OrgKind
    fields: list[KindFieldOut]


class CertificateReviewIn(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str | None = Field(default=None, max_length=1000)
    valid_until: date | None = None


class CertificateRevokeIn(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class CertificateQueueItem(BaseModel):
    id: uuid.UUID
    code: str
    status: CertificateStatus
    org_id: uuid.UUID
    org_name: str
    gouvernorat_code: int | None
    submitted_at: datetime | None
    completeness: Completeness


CounterReason = Literal["not_approved", "revoked", "superseded", "expired", "signature", "org_inactive"]


class CounterView(BaseModel):
    """What the agent at the counter of a regional administration sees after scanning a certificate (phase P3a)."""

    certificate: CertificateOut
    valid: bool
    reasons: list[CounterReason]
    signature_valid: bool
    can_stamp: bool
    org_id: uuid.UUID
    org_name: str
    org_kind: OrgKind
    org_status: OrgStatus
    org_address: str | None
    gouvernorat_code: int | None


class CertificateQueuePage(BaseModel):
    items: list[CertificateQueueItem]
    next_cursor: str | None


class OrgRef(BaseModel):
    id: uuid.UUID
    name: str
    kind: OrgKind


class OrganizationCard(BaseModel):
    """What responders need about the institution a report comes from (FR-A-080)."""

    id: uuid.UUID
    name: str
    kind: OrgKind
    capacity: int | None
    address: str | None
    location: Point
    classification: ClassificationOut
    representative: Person | None
    hazmat: list[HazmatIn]
    features: list[FeatureOut]
    # All the fields of the kind, including those shown only on a report near the institution.
    kind_fields: dict[str, int | bool | str]


# ---------------------------------------------------------------- prevention visit (phase P3b)


class ChecklistItemOut(BaseModel):
    key: str
    section: InspectionSection
    declared: Any


class InspectionItemIn(BaseModel):
    key: str = Field(min_length=1, max_length=60)
    result: InspectionResult
    observed: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=500)


class InspectionIn(BaseModel):
    inspected_on: date
    attendees: str | None = Field(default=None, max_length=500)
    items: list[InspectionItemIn] = Field(default_factory=list, max_length=300)


class InspectionItemOut(ChecklistItemOut):
    result: InspectionResult
    observed: str | None
    note: str | None


class ComparisonReport(BaseModel):
    """What was declared against what the inspector found, computed by the server (design-prevention.md §3)."""

    items: list[InspectionItemOut]
    conform: int
    nonconform: int
    not_checked: int
    missing: list[str]
    changes: list[CertificateChange]
    suggested: Literal["approved", "approved_with_reservations"]


class ReservationIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    due_on: date
    item_key: str | None = Field(default=None, max_length=60)


class ReservationOut(BaseModel):
    id: uuid.UUID
    visit_id: uuid.UUID
    item_key: str | None
    text: str
    due_on: date
    state: ReservationState
    response_note: str | None
    responded_by_name: str | None
    responded_at: datetime | None
    lifted_by_name: str | None
    lift_note: str | None
    lifted_at: datetime | None


class VisitRequestIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class VisitScheduleIn(BaseModel):
    scheduled_on: date
    inspector_name: str | None = Field(default=None, max_length=120)


class VisitDecisionIn(BaseModel):
    decision: VisitDecision
    reason: str | None = Field(default=None, max_length=1000)
    valid_until: date | None = None
    reservations: list[ReservationIn] = Field(default_factory=list, max_length=50)


class VisitCancelIn(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ReservationResponseIn(BaseModel):
    note: str = Field(min_length=1, max_length=1000)


class ReservationLiftIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class VisitOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    origin: VisitOrigin
    status: VisitStatus
    request_note: str | None
    requested_by_name: str | None
    requested_at: datetime | None
    scheduled_on: date | None
    inspector_name: str | None
    inspected_on: date | None
    attendees: str | None
    comparison: ComparisonReport | None
    decision: VisitDecision | None
    decision_reason: str | None
    decided_by_name: str | None
    decided_at: datetime | None
    certificate: CertificateOut | None
    reservations: list[ReservationOut]
    has_report: bool
    cancel_reason: str | None
    cancelled_at: datetime | None
    created_at: datetime


class VisitPhotoOut(BaseModel):
    """A photo taken on site (phase P4c); ``url`` is a short-lived link."""

    id: uuid.UUID
    item_key: str | None
    content_type: str
    bytes: int
    created_by_name: str | None
    device_at: datetime | None
    created_at: datetime
    url: str | None = None


class VisitSignatures(BaseModel):
    """The two signatures of an inspection made on a phone (phase P4c); the URLs are short-lived."""

    inspector_name: str | None
    inspector_url: str | None
    representative_name: str | None
    representative_role: str | None
    representative_url: str | None


class StaffVisit(VisitOut):
    org_name: str
    org_kind: OrgKind
    org_status: OrgStatus
    gouvernorat_code: int | None
    # The grid to fill, from the institution's declaration today; empty once the visit is decided or cancelled.
    checklist: list[ChecklistItemOut] = Field(default_factory=list)
    # Phase P4c: the inspector who took the visit on a phone, the photos and the signatures from the site.
    inspector_on_phone: bool = False
    photos: list[VisitPhotoOut] = Field(default_factory=list)
    signatures: VisitSignatures | None = None


class FieldVisit(StaffVisit):
    """A visit as the inspector's phone sees it (phase P4c): the institution's address and place, and whether the
    visit is the inspector's own."""

    org_address: str | None
    org_location: Point | None
    mine: bool
    taken_by_other: bool


# A signature drawn on the phone, as a PNG in base64 (a few kilobytes; at most 200 KB once decoded).
SignaturePng = Annotated[str, StringConstraints(min_length=20, max_length=280_000)]


class FieldInspectionIn(InspectionIn):
    """The grid filled on the phone, with the phone's id for it (a resent inspection is applied once), its clock,
    and the two signatures (design-staff.md §8.4)."""

    client_id: uuid.UUID
    device_at: datetime | None = None
    representative_name: str = Field(min_length=1, max_length=120)
    representative_role: str | None = Field(default=None, max_length=120)
    inspector_signature: SignaturePng
    representative_signature: SignaturePng


class StaffVisitPage(BaseModel):
    items: list[StaffVisit]
    next_cursor: str | None


class AnnualCount(BaseModel):
    valid: int
    expiring: int
    expired: int
    unknown: int


class AnnualReservations(BaseModel):
    opened: int
    lifted: int
    open: int
    overdue: int


class AnnualReport(BaseModel):
    """The institution's year (F-APP-132): drills, maintenance, training, visits, reservations, certificates."""

    year: int
    org_id: uuid.UUID
    org_name: str
    generated_on: date
    drills: list[ActivityOut]
    events: list[ActivityOut]
    participants: int
    maintenance: int
    training: AnnualCount
    visits: list[VisitOut]
    reservations: AnnualReservations
    certificates: list[CertificateOut]
    stamps: int
    reports: int
