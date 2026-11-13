import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Effect = Literal["grant", "hide", "suspend"]
TargetKind = Literal["user", "role", "everyone"]


class Names(BaseModel):
    ar: str
    fr: str
    en: str


class FeatureOut(BaseModel):
    key: str
    kind: Literal["page", "tab", "button", "system"]
    names: Names
    parent: str | None
    group: str | None
    nav: str | None
    flags: list[str]
    roles: list[str]
    act_as: str | None
    grantable: bool
    routes: list[str]


class SystemMessage(BaseModel):
    """What the users of a suspended system read in its place (one language at least)."""

    ar: str = Field(default="", max_length=300)
    fr: str = Field(default="", max_length=300)
    en: str = Field(default="", max_length=300)


class Announcement(BaseModel):
    """The system administrator's message, shown at once (phase 5)."""

    tone: Literal["info", "warn"]
    ar: str
    fr: str
    en: str


class Mine(BaseModel):
    """What the administrator's rules change for the caller: the dashboard opens and hides accordingly."""

    granted: list[str]
    hidden: list[str]
    # The role each granted feature lends on its own routes (the dashboard shows its buttons accordingly).
    lent: dict[str, str]
    # Phase 5: the administrator's message for the dashboard.
    announcement: Announcement | None = None
    # The systems suspended for the caller (2026-11-13), with the administrator's message.
    suspended: dict[str, "SystemMessage"] = {}


class Hidden(BaseModel):
    """The windows and buttons of the field app, the citizen app or the portal hidden from the caller (phase 5)."""

    hidden: list[str]
    announcement: Announcement | None = None


class RuleIn(BaseModel):
    feature_key: str = Field(min_length=2, max_length=80)
    effect: Effect
    target_kind: TargetKind
    target: str = Field(min_length=1, max_length=255)
    target_name: str | None = Field(default=None, max_length=200)
    gouvernorat_code: int | None = None
    reason: str = Field(min_length=5, max_length=500)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    # A «suspend» rule's message (2026-11-13); ignored for the others.
    message: SystemMessage | None = None


class RuleOut(BaseModel):
    id: uuid.UUID
    feature_key: str
    effect: Effect
    target_kind: TargetKind
    target: str
    target_name: str | None
    gouvernorat_code: int | None
    reason: str
    starts_at: datetime | None
    ends_at: datetime | None
    created_by_name: str | None
    created_at: datetime
    revoked_at: datetime | None
    revoked_by_name: str | None
    revoke_reason: str | None
    message: SystemMessage | None = None
    state: Literal["active", "scheduled", "ended", "revoked"]


class RevokeIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class PreviewRow(BaseModel):
    key: str
    default: bool
    hidden: bool
    granted: bool
    refused: str | None
    open: bool


# ---------------------------------------------------------------- profiles (OS3, Yamen 2026-11-11)

ProfileMode = Literal["read", "write"]


class ProfileItem(BaseModel):
    page: str = Field(min_length=2, max_length=80, pattern=r"^[a-z_]+$")
    mode: ProfileMode


class ProfileIn(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    items: list[ProfileItem] = Field(min_length=1, max_length=60)


class ProfileItemOut(ProfileItem):
    known: bool
    names: Names | None = None
    features: list[str]


class ProfileOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    builtin: bool
    items: list[ProfileItemOut]
    active_assignments: int
    updated_at: datetime


class AssignIn(BaseModel):
    target_kind: Literal["user", "role"]
    target: str = Field(min_length=1, max_length=255)
    target_name: str | None = Field(default=None, max_length=200)
    gouvernorat_code: int | None = None
    reason: str = Field(min_length=5, max_length=500)
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class Skipped(BaseModel):
    feature_key: str
    reason: str


class AssignmentOut(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID | None
    target_kind: TargetKind
    target: str
    target_name: str | None
    gouvernorat_code: int | None
    reason: str
    starts_at: datetime | None
    ends_at: datetime | None
    created_by_name: str | None
    created_at: datetime
    state: str
    features: list[str]
    skipped: list[Skipped] = []


# ---------------------------------------------------------------- systems (Yamen 2026-11-13)


class SystemPage(BaseModel):
    key: str
    kind: Literal["page", "tab"]
    names: Names
    nav: str | None
    flags: list[str]


class SystemOut(BaseModel):
    """One of the 20 systems of the menu: its pages and the rules set on it as a whole."""

    key: str
    number: int
    block: str
    names: Names
    pages: list[SystemPage]
    planned: list[str]
    rules: list[RuleOut]


class SystemGrantIn(AssignIn):
    """Every page of the system, read only (its pages and tabs) or read and write (its buttons too)."""

    mode: ProfileMode
