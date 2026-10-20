"""Request and response bodies of the rewards endpoints (docs/api/phase-8-contract.md §3)."""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.modules.reports.domain import Category
from app.modules.rewards.domain import Distinction, Level, NominationKind, Reason, SubjectKind

Text = Annotated[str, StringConstraints(strip_whitespace=True)]
ReasonText = Annotated[Text, StringConstraints(min_length=3, max_length=1000)]
RuleReason = Literal["report_verified", "report_helped_rescue", "accurate_category", "volunteer_mission"]
BadgeStatusName = Literal["pending", "confirmed", "rejected", "revoked"]
NominationStatus = Literal["proposed", "approved", "rejected"]


class Localized(BaseModel):
    ar: str
    fr: str
    en: str


# ---------------------------------------------------------------- citizen


class HistoryItem(BaseModel):
    id: int
    delta: int
    reason: Reason
    report_id: uuid.UUID | None
    tracking_code: str | None
    intervention_id: uuid.UUID | None
    multiplier: float | None
    # The daily cap reduced this award (its delta may be 0).
    capped: bool
    created_at: datetime


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    next_cursor: str | None


class BadgeOut(BaseModel):
    id: uuid.UUID
    level: Level
    confirmed_at: datetime | None


class NextBadge(BaseModel):
    level: Level
    threshold: int
    missing_points: int


class MyCertificate(BaseModel):
    id: uuid.UUID
    code: str
    distinction: Distinction
    year: int
    issued_at: datetime
    verify_url: str


class MyRewards(BaseModel):
    anonymous: bool
    balance: int
    # Automatic awards held while their gouvernorat is at operational level "disaster".
    pending_points: int
    paused: bool
    daily_cap: int
    badges: list[BadgeOut]
    current_badge: Level | None
    next_badge: NextBadge | None
    history: list[HistoryItem]
    history_next_cursor: str | None
    certificates: list[MyCertificate]
    prizes_notice: Localized
    safety_notice: Localized


class DownloadOut(BaseModel):
    url: str


class PublicCertificate(BaseModel):
    """What anyone holding a certificate code may learn: nothing beyond initials, distinction and date."""

    code: str
    valid: bool
    initials: str
    distinction: Distinction
    distinction_label: dict[str, str]
    date: date


# ---------------------------------------------------------------- staff: settings and rules


class Thresholds(BaseModel):
    bronze: int
    silver: int
    gold: int
    ambassador: int


class SettingsOut(BaseModel):
    daily_cap: int
    thresholds: Thresholds
    paused_gouvernorats: list[int]


class RuleOut(BaseModel):
    id: uuid.UUID
    reason: RuleReason
    category: Category | None
    points: int | None
    multiplier: float | None
    enabled: bool
    is_default: bool
    description: dict[str, str]
    updated_at: datetime
    updated_by: str | None


def _check_value(reason: str | None, points: int | None, multiplier: float | None) -> None:
    if reason == "accurate_category" and points is not None:
        raise ValueError("accurate_category takes a multiplier")
    if reason is not None and reason != "accurate_category" and multiplier is not None:
        raise ValueError("this reason takes points")


class RuleIn(BaseModel):
    reason: RuleReason
    category: Category
    points: int | None = Field(default=None, ge=0, le=5000)
    multiplier: float | None = Field(default=None, ge=1.0, le=3.0)
    enabled: bool = True

    @model_validator(mode="after")
    def _value(self) -> "RuleIn":
        _check_value(self.reason, self.points, self.multiplier)
        if (self.points if self.reason != "accurate_category" else self.multiplier) is None:
            raise ValueError("points or multiplier required")
        return self


class RulePatch(BaseModel):
    points: int | None = Field(default=None, ge=0, le=5000)
    multiplier: float | None = Field(default=None, ge=1.0, le=3.0)
    enabled: bool | None = None


# ---------------------------------------------------------------- staff: citizens and ledger


class Contact(BaseModel):
    first_name: str | None
    last_name: str | None
    phone: str | None


class CitizenItem(BaseModel):
    citizen_id: uuid.UUID
    pseudonym: str
    gouvernorat_code: int | None
    balance: int
    pending_points: int
    badges: list[Level]
    contact: Contact | None = None


class CitizenPage(BaseModel):
    items: list[CitizenItem]
    next_cursor: str | None


class StaffHistoryItem(HistoryItem):
    created_by: str | None
    note: str | None
    revoked: bool


class CitizenDetail(CitizenItem):
    history: list[StaffHistoryItem]


class AdjustIn(BaseModel):
    delta: int = Field(ge=-5000, le=5000)
    reason: ReasonText

    @model_validator(mode="after")
    def _non_zero(self) -> "AdjustIn":
        if self.delta == 0:
            raise ValueError("delta must not be 0")
        return self


class ReasonIn(BaseModel):
    reason: ReasonText


class OptionalReasonIn(BaseModel):
    reason: ReasonText | None = None


# ---------------------------------------------------------------- staff: badges


class BadgeItem(BaseModel):
    id: uuid.UUID
    citizen_id: uuid.UUID
    pseudonym: str
    level: Level
    status: BadgeStatusName
    balance: int
    awarded_at: datetime
    decided_at: datetime | None
    decided_by: str | None
    reason: str | None


class BadgePage(BaseModel):
    items: list[BadgeItem]
    next_cursor: str | None


# ---------------------------------------------------------------- staff: nominations


class Evidence(BaseModel):
    report_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    intervention_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)


class NominationIn(BaseModel):
    kind: NominationKind
    subject_kind: SubjectKind
    subject_id: uuid.UUID
    year: int = Field(ge=2020, le=2100)
    reason: Annotated[Text, StringConstraints(min_length=10, max_length=3000)]
    evidence: Evidence = Field(default_factory=Evidence)


class NominationPatch(BaseModel):
    reason: Annotated[Text, StringConstraints(min_length=10, max_length=3000)] | None = None
    evidence: Evidence | None = None


class NominationOut(BaseModel):
    id: uuid.UUID
    kind: NominationKind
    subject_kind: SubjectKind
    subject_id: uuid.UUID | None
    # Pseudonym for people, name for institutions; null once anonymised.
    subject_label: str | None
    gouvernorat_code: int | None
    year: int
    reason: str | None
    evidence: Evidence
    status: NominationStatus
    proposed_by: str
    decided_by: str | None
    decided_at: datetime | None
    decision_reason: str | None
    created_at: datetime


class NominationPage(BaseModel):
    items: list[NominationOut]
    next_cursor: str | None


# ---------------------------------------------------------------- staff: certificates


class CertificateIn(BaseModel):
    badge_award_id: uuid.UUID | None = None
    nomination_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _one_source(self) -> "CertificateIn":
        if (self.badge_award_id is None) == (self.nomination_id is None):
            raise ValueError("give badge_award_id or nomination_id")
        return self


class CertificateOut(BaseModel):
    id: uuid.UUID
    code: str
    kind: Literal["badge", "nomination"]
    distinction: Distinction
    subject_label: str | None
    initials: str
    year: int
    issued_at: datetime
    issued_by: str
    revoked_at: datetime | None
    revoked_reason: str | None
    verify_url: str


class CertificatePage(BaseModel):
    items: list[CertificateOut]
    next_cursor: str | None


# ---------------------------------------------------------------- staff: rescue flag and leaderboard


class RescueIn(BaseModel):
    report_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    note: Annotated[Text, StringConstraints(max_length=1000)] | None = None


class RescueResult(BaseModel):
    report_id: uuid.UUID
    status: Literal["applied", "queued", "duplicate", "skipped"]
    reason: str | None = None


class RescueOut(BaseModel):
    awarded: list[RescueResult]


class LeaderboardItem(BaseModel):
    rank: int
    pseudonym: str
    points: int
    gouvernorat_code: int | None


class LeaderboardOut(BaseModel):
    scope: Literal["gouvernorat", "national"]
    gouvernorat_code: int | None
    year: int
    items: list[LeaderboardItem]
