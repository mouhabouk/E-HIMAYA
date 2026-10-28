import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Effect = Literal["grant", "hide"]
TargetKind = Literal["user", "role"]


class Names(BaseModel):
    ar: str
    fr: str
    en: str


class FeatureOut(BaseModel):
    key: str
    kind: Literal["page", "tab", "button"]
    names: Names
    parent: str | None
    group: str | None
    nav: str | None
    flags: list[str]
    roles: list[str]
    act_as: str | None
    grantable: bool
    routes: list[str]


class Mine(BaseModel):
    """What the administrator's rules change for the caller: the dashboard opens and hides accordingly."""

    granted: list[str]
    hidden: list[str]
    # The role each granted feature lends on its own routes (the dashboard shows its buttons accordingly).
    lent: dict[str, str]


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
