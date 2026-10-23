import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.layers import domain

Audience = Literal["public", "staff"]
Mode = Literal["merge", "replace"]
Change = Literal["new", "updated", "unchanged", "removed"]


class Names(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ar: str = Field(min_length=1, max_length=100)
    fr: str = Field(min_length=1, max_length=100)
    en: str = Field(min_length=1, max_length=100)


def _icon(value: str | None) -> str | None:
    if value is not None and value not in domain.ICONS:
        raise ValueError("unknown icon")
    return value


def _colour(value: str | None) -> str | None:
    if value is not None and value.upper() not in domain.PALETTE:
        raise ValueError("colour outside the palette")
    return value.upper() if value is not None else None


StaffOnly = list[str]


def _staff_only(value: StaffOnly | None) -> StaffOnly | None:
    if value is None:
        return None
    if len(value) > 30 or any(not 1 <= len(v) <= 64 for v in value):
        raise ValueError("invalid staff-only columns")
    return sorted(set(value))


class LayerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")
    name: Names
    icon: str
    colour: str
    audience: Audience = "staff"
    source: str = Field(default="", max_length=200)
    licence: str = Field(default="", max_length=200)
    to_verify: bool = True
    staff_only: StaffOnly = Field(default_factory=lambda: ["manager"])
    editors_allowed: bool = False
    reason: str = Field(min_length=5, max_length=500)

    _v_icon = field_validator("icon")(_icon)
    _v_colour = field_validator("colour")(_colour)
    _v_staff_only = field_validator("staff_only")(_staff_only)


class LayerPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    reason: str = Field(min_length=5, max_length=500)
    name: Names | None = None
    icon: str | None = None
    colour: str | None = None
    audience: Audience | None = None
    source: str | None = Field(default=None, max_length=200)
    licence: str | None = Field(default=None, max_length=200)
    to_verify: bool | None = None
    staff_only: StaffOnly | None = None
    editors_allowed: bool | None = None
    enabled: bool | None = None

    _v_icon = field_validator("icon")(_icon)
    _v_colour = field_validator("colour")(_colour)
    _v_staff_only = field_validator("staff_only")(_staff_only)


class LastImport(BaseModel):
    id: uuid.UUID
    status: str
    at: datetime
    by: str | None


class LayerOut(BaseModel):
    id: uuid.UUID
    key: str
    name: Names
    icon: str
    colour: str
    audience: Audience
    source: str
    licence: str
    to_verify: bool
    staff_only: list[str]
    editors_allowed: bool
    enabled: bool
    version: int
    data_version: int
    feature_count: int
    hidden_count: int
    updated_by_name: str | None
    updated_at: datetime
    last_import: LastImport | None
    can_manage: bool
    can_import: bool


class LayersOut(BaseModel):
    items: list[LayerOut]
    can_manage: bool
    icons: list[str]
    palette: list[str]
    limits: dict[str, int]


class ImportOut(BaseModel):
    id: uuid.UUID
    file_name: str
    format: str
    mode: Mode
    status: str
    counts: dict[str, int]
    rejected: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    reason: str | None
    created_by_name: str | None
    created_at: datetime
    applied_at: datetime | None
    undone_at: datetime | None
    expired: bool
    can_apply: bool
    can_undo: bool


class PreviewPoint(BaseModel):
    ref: str
    name: str
    lat: float
    lon: float
    change: Change


class ImportDetail(ImportOut):
    points: list[PreviewPoint]


class ImportsOut(BaseModel):
    items: list[ImportOut]


class ReasonIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=5, max_length=500)


Props = dict[str, str]


def _props(value: Props | None) -> Props | None:
    if value is None:
        return None
    if len(value) > domain.MAX_EXTRA_COLUMNS + len(domain.PROPS_KEYS):
        raise ValueError("too many columns")
    if any(not 1 <= len(k) <= 64 or len(v) > domain.MAX_VALUE_LENGTH for k, v in value.items()):
        raise ValueError("invalid column")
    return {k: v for k, v in value.items() if v != ""}


def _phone(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    number = domain.normalize_phone(value)
    if number is None:
        raise ValueError("phone_invalid")
    return number


class FeatureIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref: str | None = Field(default=None, min_length=1, max_length=domain.MAX_REF_LENGTH)
    name: str = Field(min_length=1, max_length=domain.MAX_NAME_LENGTH)
    kind: str | None = Field(default=None, max_length=64)
    phone: str | None = None
    lat: float = Field(ge=domain.LAT_RANGE[0], le=domain.LAT_RANGE[1])
    lon: float = Field(ge=domain.LON_RANGE[0], le=domain.LON_RANGE[1])
    props: Props = Field(default_factory=dict)
    reason: str = Field(min_length=5, max_length=500)

    _v_phone = field_validator("phone")(_phone)
    _v_props = field_validator("props")(_props)


class FeaturePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    reason: str = Field(min_length=5, max_length=500)
    name: str | None = Field(default=None, min_length=1, max_length=domain.MAX_NAME_LENGTH)
    kind: str | None = Field(default=None, max_length=64)
    phone: str | None = None
    lat: float | None = Field(default=None, ge=domain.LAT_RANGE[0], le=domain.LAT_RANGE[1])
    lon: float | None = Field(default=None, ge=domain.LON_RANGE[0], le=domain.LON_RANGE[1])
    props: Props | None = None
    hidden: bool | None = None

    _v_phone = field_validator("phone")(_phone)
    _v_props = field_validator("props")(_props)


class FeatureOut(BaseModel):
    id: uuid.UUID
    ref: str
    name: str
    kind: str | None
    phone: str | None
    lat: float
    lon: float
    gouvernorat_code: int | None
    delegation_id: int | None
    props: dict[str, Any]
    hidden: bool
    version: int
    updated_at: datetime


class FeaturesOut(BaseModel):
    items: list[FeatureOut]
    truncated: bool


# ---------------------------------------------------------------- public (the app)


class PublicLayer(BaseModel):
    key: str
    name: str
    names: Names
    icon: str
    colour: str
    source: str
    licence: str
    to_verify: bool
    count: int
    data_version: int
    # "units": Civil Protection centres, from the units directory (phase 5), always in step with operations.
    origin: Literal["file", "units"]


class PublicLayers(BaseModel):
    items: list[PublicLayer]


class PublicFeature(BaseModel):
    id: uuid.UUID
    name: str
    kind: str | None
    phone: str | None
    lat: float
    lon: float
    gouvernorat_code: int | None
    props: dict[str, Any]
    distance_m: float | None = None


class PublicFeatures(BaseModel):
    layer: str
    data_version: int
    items: list[PublicFeature]
    truncated: bool = False
