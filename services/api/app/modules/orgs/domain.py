"""Institution vocabulary and rules: kinds, roles, identifiers, classification (FR-B-003), alerts.

Pure functions, so the rules can be read and tested on their own. The classification thresholds are a
working model to validate against the official text (مجلة السلامة والوقاية من أخطار الحريق والانفجار
والفزع بالبنايات) with the Protection Civile: they live here only, and clients never hard-code them.
"""

import calendar
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import Literal


class OrgStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class OrgKind(StrEnum):
    """Activity of the institution (addition 12): a working list until the Office validates it [SIM]."""

    HEALTH = "health"
    INDUSTRIAL = "industrial"
    ENERGY = "energy"
    TOURISM = "tourism"
    EDUCATION = "education"
    SOCIAL_CARE = "social_care"
    PUBLIC_ADMIN = "public_admin"
    CULTURE_SPORT = "culture_sport"
    COMMERCIAL = "commercial"
    TRANSPORT = "transport"
    RELIGIOUS = "religious"
    OTHER = "other"


class OrgRole(StrEnum):
    ADMIN = "admin"
    EDITOR = "editor"
    MEMBER = "member"


_ROLE_RANK = {OrgRole.MEMBER: 0, OrgRole.EDITOR: 1, OrgRole.ADMIN: 2}


def role_allows(role: OrgRole, needed: OrgRole) -> bool:
    return _ROLE_RANK[role] >= _ROLE_RANK[needed]


IdentifierType = Literal["mf", "rne"]
TeamRole = Literal["representative", "member"]
HazmatUnit = Literal["kg", "t", "l", "m3"]
EquipmentKind = Literal[
    "extinguisher",
    "fire_hose_reel",
    "sprinkler",
    "smoke_detector",
    "alarm_panel",
    "emergency_lighting",
    "fire_door",
    "other",
]
FeatureKind = Literal["evacuation_point", "water_point", "alarm"]
DocumentKind = Literal["safety_file", "safety_plan", "sds", "other", "maintenance_photo"]
ActivityKind = Literal["drill", "event"]
CertificateStatus = Literal["draft", "submitted", "approved", "rejected", "revoked"]

# Registration review by the institutions auditor (FR-B-001): decision → (allowed from, result).
REVIEW_TRANSITIONS: dict[str, tuple[OrgStatus, OrgStatus]] = {
    "approve": (OrgStatus.PENDING_REVIEW, OrgStatus.ACTIVE),
    "reject": (OrgStatus.PENDING_REVIEW, OrgStatus.REJECTED),
    "suspend": (OrgStatus.ACTIVE, OrgStatus.SUSPENDED),
    "reinstate": (OrgStatus.SUSPENDED, OrgStatus.ACTIVE),
}

MAX_ORGS_PER_ACCOUNT = 5
MAX_PENDING_INVITATIONS = 20
INVITATION_DAYS = 7
MAX_FEATURES = 200
FEATURE_MAX_DISTANCE_M = 2000
TRAINING_EXPIRING_DAYS = 60
MAINTENANCE_DUE_DAYS = 30
CERTIFICATE_MAX_YEARS = 5

# ---------------------------------------------------------------- identifiers and contacts

# Matricule fiscal: 7 digits and a control letter, optionally /<VAT code>/<category>/<establishment no.>.
_MF = re.compile(r"^\d{7}[A-Z](/[A-Z]/[A-Z]/\d{3})?$")
# Unique identifier of the national business register (RNE): 7 digits and a letter.
_RNE = re.compile(r"^\d{7}[A-Z]$")
_PHONE = re.compile(r"^\+216\d{8}$")
_UN = re.compile(r"^\d{4}$")


def normalize_identifier(identifier_type: IdentifierType, raw: str) -> str | None:
    """Upper-case, without spaces; None when the format is wrong."""
    value = re.sub(r"\s+", "", raw).upper()
    pattern = _MF if identifier_type == "mf" else _RNE
    return value if pattern.match(value) else None


def normalize_phone(raw: str) -> str | None:
    value = re.sub(r"[\s.-]", "", raw)
    if re.fullmatch(r"\d{8}", value):
        value = "+216" + value
    elif value.startswith("00216"):
        value = "+" + value[2:]
    return value if _PHONE.match(value) else None


def valid_un_number(value: str) -> bool:
    return bool(_UN.match(value))


# ---------------------------------------------------------------- documents

DOCUMENT_TYPES: dict[str, frozenset[str]] = {
    "safety_file": frozenset({"application/pdf"}),
    "safety_plan": frozenset({"application/pdf", "image/vnd.dwg", "image/vnd.dxf"}),
    "sds": frozenset({"application/pdf"}),
    "other": frozenset({"application/pdf"}),
    # Phase P2b: the photo taken on the phone when a maintenance is recorded.
    "maintenance_photo": frozenset({"image/jpeg", "image/png"}),
}
DOCUMENT_MAX_BYTES = 50 * 1024 * 1024
PHOTO_MAX_BYTES = 10 * 1024 * 1024
CAD_MAX_BYTES = 100 * 1024 * 1024
CAD_TYPES = frozenset({"image/vnd.dwg", "image/vnd.dxf"})


def document_max_bytes(content_type: str) -> int:
    if content_type in CAD_TYPES:
        return CAD_MAX_BYTES
    return PHOTO_MAX_BYTES if content_type.startswith("image/") else DOCUMENT_MAX_BYTES


# ---------------------------------------------------------------- dates


def add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def training_status(last: date | None, valid_months: int, today: date) -> tuple[str, date | None]:
    """valid | expiring (within 60 days) | expired | unknown, with the expiry date."""
    if last is None:
        return "unknown", None
    expires = add_months(last, valid_months)
    if expires < today:
        return "expired", expires
    if expires <= today + timedelta(days=TRAINING_EXPIRING_DAYS):
        return "expiring", expires
    return "valid", expires


def maintenance_status(last: date | None, interval_months: int, today: date) -> tuple[str, date | None]:
    """ok | due_soon (within 30 days) | overdue | unknown, with the next maintenance date."""
    if last is None:
        return "unknown", None
    due = add_months(last, interval_months)
    if due < today:
        return "overdue", due
    if due <= today + timedelta(days=MAINTENANCE_DUE_DAYS):
        return "due_soon", due
    return "ok", due


# ---------------------------------------------------------------- classification (FR-B-003)

HIGH_RISE_M = 28.0
# ERP categories by maximum number of people present: (minimum capacity, category), highest first.
ERP_CATEGORIES = ((1501, 1), (701, 2), (301, 3), (51, 4), (0, 5))

Requirement = Literal[
    "safety_file", "safety_plan", "safety_team", "training", "hazmat_sds", "equipment", "evacuation_points"
]
_BASE: tuple[Requirement, ...] = ("safety_file", "safety_team", "equipment")
_HIGH_RISK: tuple[Requirement, ...] = ("safety_plan", "training", "evacuation_points")


@dataclass(frozen=True, slots=True)
class Classification:
    family: Literal["high_rise", "industrial", "erp", "workplace"]
    category: int | None
    high_rise: bool
    required: tuple[Requirement, ...]
    provisional: bool = True


def classify(
    *, kind: str, capacity: int | None, height_m: float | None, receives_public: bool, hazmat_count: int
) -> Classification:
    high_rise = height_m is not None and height_m > HIGH_RISE_M
    category: int | None = None
    if high_rise:
        family: Literal["high_rise", "industrial", "erp", "workplace"] = "high_rise"
    elif kind == OrgKind.INDUSTRIAL or hazmat_count > 0:
        family = "industrial"
    elif receives_public:
        family = "erp"
        people = capacity or 0
        category = next(cat for minimum, cat in ERP_CATEGORIES if people >= minimum)
    else:
        family = "workplace"

    required: list[Requirement] = list(_BASE)
    if family in ("high_rise", "industrial") or (family == "erp" and category is not None and category <= 3):
        required += _HIGH_RISK
    if family == "industrial" and hazmat_count > 0:
        required.append("hazmat_sds")
    return Classification(family=family, category=category, high_rise=high_rise, required=tuple(required))


@dataclass(frozen=True, slots=True)
class Facts:
    """What the completeness check needs to know about an institution's registers."""

    stored_document_kinds: frozenset[str]
    representative: bool
    team_members: int  # excluding the representative
    training_statuses: tuple[str, ...]
    hazmat_without_sds: int
    equipment_statuses: tuple[str, ...]
    evacuation_points: int


def missing(required: Iterable[Requirement], facts: Facts) -> list[Requirement]:
    checks: dict[Requirement, bool] = {
        "safety_file": "safety_file" in facts.stored_document_kinds,
        "safety_plan": "safety_plan" in facts.stored_document_kinds,
        "safety_team": facts.representative and facts.team_members >= 1,
        "training": bool(facts.training_statuses)
        and "expired" not in facts.training_statuses
        and "unknown" not in facts.training_statuses,
        "hazmat_sds": facts.hazmat_without_sds == 0,
        "equipment": bool(facts.equipment_statuses) and "overdue" not in facts.equipment_statuses,
        "evacuation_points": facts.evacuation_points >= 1,
    }
    return [item for item in required if not checks[item]]


# ---------------------------------------------------------------- kind fields (addition 12, design P2 §2.2)

# Who sees a field: the public (nearest places), the institution and the Office's institutions auditor, or the
# operations room only on a report near the institution (always logged). Members always see their own fields.
Visibility = Literal["public", "org_office", "incident"]
FieldType = Literal["int", "bool", "text"]


@dataclass(frozen=True, slots=True)
class KindField:
    key: str
    type: FieldType
    visibility: Visibility
    maximum: int = 1_000_000  # int: largest value; text: longest length


# Working model [SIM]: the fields of each kind and their visibility, to validate with the Office. Nothing is
# required yet; the classification keeps deciding the safety requirements.
KIND_FIELDS: dict[OrgKind, tuple[KindField, ...]] = {
    OrgKind.HEALTH: (
        KindField("reception_phone", "text", "public", 20),
        KindField("beds", "int", "org_office", 10_000),
        KindField("icu", "bool", "org_office"),
        KindField("oxygen_hours", "int", "org_office", 10_000),
        KindField("generator", "bool", "org_office"),
        KindField("helipad", "bool", "org_office"),
        KindField("non_ambulatory", "int", "incident", 10_000),
    ),
    OrgKind.INDUSTRIAL: (
        KindField("workers_per_shift", "int", "org_office", 100_000),
        KindField("self_fire_fighting", "bool", "org_office"),
        KindField("tanks", "int", "incident", 1_000),
    ),
    OrgKind.ENERGY: (
        KindField("fuel_types", "text", "org_office", 200),
        KindField("storage_m3", "int", "incident", 10_000_000),
        KindField("shutoff_valves", "bool", "incident"),
    ),
    OrgKind.TOURISM: (
        KindField("rooms", "int", "org_office", 10_000),
        KindField("guest_languages", "text", "org_office", 200),
        KindField("pool_or_beach", "bool", "org_office"),
        KindField("occupancy_pct", "int", "incident", 100),
    ),
    OrgKind.EDUCATION: (
        KindField("students", "int", "org_office", 100_000),
        KindField("age_range", "text", "org_office", 50),
        KindField("boarding", "bool", "org_office"),
        KindField("students_special_needs", "int", "incident", 10_000),
    ),
    OrgKind.SOCIAL_CARE: (
        KindField("residents", "int", "org_office", 10_000),
        KindField("night_watch", "bool", "org_office"),
        KindField("non_ambulatory", "int", "incident", 10_000),
    ),
    OrgKind.PUBLIC_ADMIN: (
        KindField("staff", "int", "org_office", 100_000),
        KindField("archive", "bool", "org_office"),
    ),
    OrgKind.CULTURE_SPORT: (
        KindField("seated_capacity", "int", "org_office", 200_000),
        KindField("stands", "bool", "org_office"),
    ),
    OrgKind.COMMERCIAL: (
        KindField("shops", "int", "org_office", 10_000),
        KindField("underground_parking", "bool", "incident"),
    ),
    OrgKind.TRANSPORT: (
        KindField("daily_passengers", "int", "org_office", 10_000_000),
        KindField("emergency_exits", "int", "org_office", 1_000),
    ),
    OrgKind.RELIGIOUS: (KindField("peak_times", "text", "org_office", 200),),
    OrgKind.OTHER: (),
}

# What each kind of reader may see, beyond the institution's own members who see everything.
VISIBLE_TO: dict[str, frozenset[Visibility]] = {
    "public": frozenset({"public"}),
    "auditor": frozenset({"public", "org_office"}),
    "member": frozenset({"public", "org_office", "incident"}),
    "incident": frozenset({"public", "org_office", "incident"}),
}


def clean_kind_fields(kind: OrgKind, raw: Mapping[str, object]) -> dict[str, object] | str:
    """The answers kept for ``kind`` (unknown keys and empty values dropped), or the key of the first bad value."""
    specs = {f.key: f for f in KIND_FIELDS[kind]}
    kept: dict[str, object] = {}
    for key, value in raw.items():
        spec = specs.get(key)
        if spec is None or value is None or value == "":
            continue
        if spec.type == "bool":
            if not isinstance(value, bool):
                return key
        elif spec.type == "int":
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= spec.maximum:
                return key
        elif not isinstance(value, str) or len(value.strip()) > spec.maximum:
            return key
        kept[key] = value.strip() if isinstance(value, str) else value
    return kept


def visible_kind_fields(kind: str, values: dict[str, object], reader: str) -> dict[str, object]:
    allowed = VISIBLE_TO[reader]
    specs = KIND_FIELDS.get(OrgKind(kind), ())
    return {f.key: values[f.key] for f in specs if f.key in values and f.visibility in allowed}


def readiness(required: Iterable[str], missing_items: Iterable[str]) -> int:
    """Share of the safety requirements met, in percent (the ring on «My institution»)."""
    wanted = list(required)
    if not wanted:
        return 100
    return round(100 * (len(wanted) - len(set(missing_items))) / len(wanted))


# ---------------------------------------------------------------- sensitive sites (BR-20)

SENSITIVE_RADIUS_M = 300.0
# Kinds whose occupants need help to leave: a report nearby weighs as much as a building open to the public.
_VULNERABLE_KINDS = frozenset({OrgKind.EDUCATION, OrgKind.HEALTH, OrgKind.SOCIAL_CARE})


def sensitivity(classification: Classification, kind: str, hazmat_count: int) -> tuple[float, str]:
    """Value of the ``sensitive_sites`` priority component for a report near this institution."""
    if hazmat_count > 0:
        return 1.0, "hazmat"
    if classification.family == "high_rise":
        return 0.8, "high_rise"
    if classification.family == "erp" and classification.category is not None and classification.category <= 2:
        return 0.8, "large_public"
    if classification.family == "erp" or kind in _VULNERABLE_KINDS:
        return 0.6, "public"
    return 0.4, "nearby"
