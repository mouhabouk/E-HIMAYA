import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.core.security import Role

Text = Annotated[str, StringConstraints(strip_whitespace=True)]
GrantState = Literal["active", "pending_review", "reviewed"]


# ---------------------------------------------------------------- break-glass (§6.1)


class GrantIn(BaseModel):
    target_kind: Literal["report", "incident", "gouvernorat"]
    target_id: uuid.UUID | None = None
    gouvernorat_code: int | None = None
    # Checked by the service so a missing or short justification answers 422 breakglass_justification_required.
    justification: str | None = Field(default=None, max_length=5000)
    duration_min: int = Field(default=60, ge=15, le=240)


class GrantOut(BaseModel):
    id: uuid.UUID
    subject: str
    subject_name: str | None
    target_kind: str
    target_id: uuid.UUID | None
    gouvernorat_code: int | None
    justification: str
    granted_at: datetime
    expires_at: datetime
    ended_at: datetime | None
    revoked_at: datetime | None
    state: GrantState
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_outcome: Literal["justified", "unjustified"] | None
    review_note: str | None


class GrantPage(BaseModel):
    items: list[GrantOut]
    next_cursor: str | None


class ReviewIn(BaseModel):
    outcome: Literal["justified", "unjustified"]
    note: Annotated[Text, StringConstraints(max_length=1000)] | None = None


# ---------------------------------------------------------------- regional account administration (§6.2)

ScopeLevel = Literal["gouvernorat", "national"]
Username = Annotated[
    str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=64, pattern=r"^[a-z0-9._-]+$")
]
Name = Annotated[Text, StringConstraints(min_length=1, max_length=100)]


class AccountOut(BaseModel):
    id: str
    username: str
    email: str | None
    first_name: str | None
    last_name: str | None
    enabled: bool
    roles: list[Role]
    scope_level: ScopeLevel | None
    gouvernorat_code: int | None
    mfa_configured: bool


class AccountPage(BaseModel):
    items: list[AccountOut]
    next_cursor: str | None


class AccountIn(BaseModel):
    username: Username
    email: Annotated[Text, StringConstraints(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
    first_name: Name
    last_name: Name
    roles: list[Role] = Field(min_length=1, max_length=11)
    scope_level: ScopeLevel
    gouvernorat_code: int | None = None


class AccountPatch(BaseModel):
    roles: list[Role] | None = Field(default=None, min_length=1, max_length=11)
    enabled: bool | None = None
