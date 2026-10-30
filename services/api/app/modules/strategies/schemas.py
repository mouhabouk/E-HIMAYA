from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.core.security import REALM_ROLES, Realm

Lang = Literal["ar", "fr", "en"]
Tone = Literal["navy", "red", "teal", "green", "sky", "orange", "purple", "amber", "pink", "slate"]
# A page of the dashboard ("/snacr") or an official site; never a script or another scheme.
LINK = r"^(/[A-Za-z0-9/_\-]{0,200}|https://[^\s]{4,500})$"


class ItemIn(BaseModel):
    name: dict[Lang, Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]]
    summary: dict[Lang, Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]] = Field(
        default_factory=dict
    )
    body: dict[Lang, Annotated[str, StringConstraints(max_length=20_000)]] = Field(default_factory=dict)
    link: Annotated[str, StringConstraints(pattern=LINK)] | None = None
    icon: Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9]{2,40}$")] = "insights"
    tone: Tone = "purple"
    roles: list[str] = Field(default_factory=list, max_length=20)
    position: Annotated[int, Field(ge=0, le=999)] = 100
    active: bool = True

    @field_validator("roles")
    @classmethod
    def _staff_roles(cls, roles: list[str]) -> list[str]:
        staff = {r.value for r in REALM_ROLES[Realm.STAFF]}
        unknown = [r for r in roles if r not in staff]
        if unknown:
            raise ValueError(f"unknown roles: {', '.join(unknown)}")
        return sorted(set(roles))


class ItemOut(BaseModel):
    key: str
    name: dict[str, str]
    summary: dict[str, str]
    body: dict[str, str]
    link: str | None
    icon: str
    tone: str
    roles: list[str]
    position: int
    active: bool
    updated_by_name: str | None
    updated_at: datetime


class ItemsOut(BaseModel):
    items: list[ItemOut]
    can_manage: bool
