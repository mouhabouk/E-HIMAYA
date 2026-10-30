import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.layers import access, domain

Audience = Literal["public", "staff"]
Status = Literal["draft", "published", "paused"]
Group = Literal["citizen", "room", "field", "command", "support"]
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


Fields = dict[str, list[Group]]


def _fields(value: Fields | None) -> Fields | None:
    if value is None:
        return None
    if len(value) > domain.MAX_EXTRA_COLUMNS + len(access.CARD_FIELDS) or any(not 1 <= len(k) <= 64 for k in value):
        raise ValueError("invalid columns")
    return {k: sorted(set(v)) for k, v in value.items()}


def _scope(value: list[int] | None) -> list[int] | None:
    if value is None:
        return None
    if len(value) > 24 or any(not 1 <= v <= 99 for v in value):
        raise ValueError("invalid gouvernorats")
    return sorted(set(value))


class Actions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call: bool = True
    directions: bool = True


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
    # Approximate, invented places for trials: shown with the amber [SIM] mark (migration 0035).
    simulated: bool = False
    staff_only: StaffOnly = Field(default_factory=lambda: ["manager"])
    editors_allowed: bool = False
    reason: str = Field(min_length=5, max_length=500)
    # Phase L1a: a new layer is a draft until the administrator publishes it. Without ``audiences``, the
    # ``audience`` above decides (public: citizens and staff; staff: staff only); without ``fields``, ``staff_only``.
    status: Status = "draft"
    audiences: list[Group] | None = None
    scope: list[int] = Field(default_factory=list)
    default_on: bool = True
    sensitive: bool = False
    fields: Fields | None = None
    actions: Actions = Field(default_factory=Actions)

    _v_icon = field_validator("icon")(_icon)
    _v_colour = field_validator("colour")(_colour)
    _v_staff_only = field_validator("staff_only")(_staff_only)
    _v_fields = field_validator("fields")(_fields)
    _v_scope = field_validator("scope")(_scope)


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
    simulated: bool | None = None
    staff_only: StaffOnly | None = None
    editors_allowed: bool | None = None
    enabled: bool | None = None
    status: Status | None = None
    audiences: list[Group] | None = None
    scope: list[int] | None = None
    default_on: bool | None = None
    sensitive: bool | None = None
    fields: Fields | None = None
    actions: Actions | None = None
    group_key: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{1,39}$")

    _v_icon = field_validator("icon")(_icon)
    _v_colour = field_validator("colour")(_colour)
    _v_staff_only = field_validator("staff_only")(_staff_only)
    _v_fields = field_validator("fields")(_fields)
    _v_scope = field_validator("scope")(_scope)


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
    simulated: bool
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
    # Correct the places by hand (phase N): managers, and content editors on the layers opened to them.
    can_edit: bool = False
    status: Status
    audiences: list[Group]
    scope: list[int]
    default_on: bool
    sensitive: bool
    fields: dict[str, list[str]]
    actions: Actions
    # "point", "line", "area" or "mixed": what the places are (none yet: "point").
    geometry: str
    quality: dict[str, int]
    deleted_at: datetime | None
    delete_reason: str | None
    purge_at: datetime | None
    # Phase UI-3b: the group it shows in (its own, or the one its key suggests).
    group: str


class GroupIn(BaseModel):
    """A new group of the layer panel (system administrator)."""

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")
    name: Names
    icon: str
    tone: str
    position: int = Field(default=0, ge=0, le=999)
    sensitive: bool = False


class GroupPatch(BaseModel):
    name: Names | None = None
    icon: str | None = None
    tone: str | None = None
    position: int | None = Field(default=None, ge=0, le=999)


class GroupOut(BaseModel):
    key: str
    name: Names
    icon: str
    tone: str
    position: int
    sensitive: bool
    layer_count: int


class LayersOut(BaseModel):
    # Phase UI-3b: the groups holding a layer the caller sees (all of them for the administrator), in order.
    groups: list[GroupOut] = Field(default_factory=list)
    items: list[LayerOut]
    deleted: list[LayerOut] = Field(default_factory=list)
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
    geometry: str = "point"
    name_status: str = "official"
    suggested_name: str | None = None
    name_confidence: str | None = None
    name_source: str | None = None
    source_url: str | None = None
    snapshot_at: str | None = None
    possible_duplicate: bool = False
    deleted_at: datetime | None = None
    delete_reason: str | None = None


class FeaturesOut(BaseModel):
    items: list[FeatureOut]
    truncated: bool


# ---------------------------------------------------------------- phase L1a: deleting, revisions, review


class Revision(BaseModel):
    number: int
    action: str
    reason: str | None
    created_by_name: str | None
    created_at: datetime
    changes: list[str]


class RevisionsOut(BaseModel):
    items: list[Revision]


ReviewAction = Literal["accept", "edit", "reject", "keep", "merge"]


class ReviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    action: ReviewAction
    # "edit": the name to keep; "merge": the place this one duplicates (it is deleted, the other one stays).
    name: str | None = Field(default=None, min_length=1, max_length=domain.MAX_NAME_LENGTH)
    into: uuid.UUID | None = None


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReviewItem] = Field(default_factory=list, max_length=500)
    # Accept every suggested name of these confidences at once ("high", "confirmed"…).
    accept_confidence: list[Literal["confirmed", "high", "medium", "low", "review"]] = Field(default_factory=list)
    reason: str = Field(min_length=5, max_length=500)


class ReviewOut(BaseModel):
    accepted: int
    edited: int
    rejected: int
    kept: int
    merged: int


class ReviewQueue(BaseModel):
    items: list[FeatureOut]
    counts: dict[str, int]
    total: int


class Shapes(BaseModel):
    """A GeoJSON ``FeatureCollection`` of the lines and areas in a map area, simplified for the zoom."""

    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[dict[str, Any]]
    truncated: bool = False


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
    simulated: bool
    count: int
    data_version: int
    # "units": Civil Protection centres, from the units directory (phase 5), always in step with operations.
    origin: Literal["file", "units"]
    # Phase L1a: shown at once on the map, and the buttons of a place's card.
    default_on: bool = True
    actions: Actions = Field(default_factory=Actions)


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
    # "Nearest to me on the road" (phase L1b): distance and time by car, and the engine ("fallback": an estimate).
    road_m: float | None = None
    road_s: float | None = None
    road_engine: str | None = None


class PublicFeatures(BaseModel):
    layer: str
    data_version: int
    items: list[PublicFeature]
    truncated: bool = False
