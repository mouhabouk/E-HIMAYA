"""National settings (phase 9, docs/api/phase-9-contract.md §2): keys, defaults, who may change them, validation.

Codes never change with the language; the dashboard translates the keys. Defaults here match the seeds of migration
0018 and apply when a row is missing.
"""

from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.core.security import Role
from app.modules.settings import thresholds

SLA_BANDS = "sla.bands"
SLA_CLAIM_DELAY = "sla.claim_delay_s"
SLA_ENFORCED_SINCE = "sla.enforced_since"
ANON_QUOTA = "anonymous.report_quota"
GEO_MAX_ACCURACY = "geo.max_trusted_accuracy_m"
NOTIFY_REAL_SEND = "notify.real_send_enabled"
# Phase 10 §5.1: an alert is published by someone other than its author (emergency override aside).
ALERTS_FOUR_EYES = "alerts.four_eyes"
# Phase A (docs/phase-a/design.md §3): the app release the phones compare themselves with, and the words the
# system administrator adds to the built-in list of the respectful-language filter.
APP_RELEASE = "app.release"
MODERATION_EXTRA_TERMS = "moderation.extra_terms"
# Phase B1: days to answer a request for access to information (law 2016-22, art. 14), to be confirmed by the
# Office's legal service.
CONTACT_ACCESS_INFO_DAYS = "contact.access_info_days"
# Phase B2: longest live location share (minutes) and longest safety check (hours).
SAFETY_LIVE_MAX_MINUTES = "safety.live_max_minutes"
SAFETY_CHECK_MAX_HOURS = "safety.check_max_hours"
# Phase B2: the 72-hour location history, off until the Office's legal review (design-b2 §6).
SAFETY_LOCATION_HISTORY = "safety.location_history"
# Phase L3 (design-l3 §2): hours between two situation reports of a disaster or crisis axis, per level 1 to 4.
CRISIS_SITREP_HOURS = "crisis.sitrep_hours"
# Self-learning (docs/learning.md §3): which trainings of the training centre run on their own, and every how many
# days. All off by default: the system administrator turns them on.
LEARNING_SCHEDULE = "learning.schedule"
# Phase N (review point 27): the operational thresholds, see ``thresholds``.
THRESHOLDS = "operations.thresholds"
LEARNING_TASKS = (
    "report_category",
    "report_lives",
    "report_rejected",
    "derja_words",
    "fire_smoke",
    "command_ranker",
)

BANDS = ("critical", "high", "normal", "low")


class Bands(BaseModel):
    """Lower bounds of ``reports.report.priority_score`` (0–100) per SLA band; below ``normal`` = ``low``."""

    model_config = ConfigDict(extra="forbid")

    critical: int = Field(ge=1, le=100)
    high: int = Field(ge=1, le=100)
    normal: int = Field(ge=1, le=100)

    @model_validator(mode="after")
    def _ordered(self) -> "Bands":
        if not self.critical > self.high > self.normal:
            raise ValueError("bands must decrease from critical to normal")
        return self


class ClaimDelays(BaseModel):
    """Seconds a report may wait for a claim before it is late, per band."""

    model_config = ConfigDict(extra="forbid")

    critical: int = Field(ge=15, le=3600)
    high: int = Field(ge=15, le=3600)
    normal: int = Field(ge=15, le=3600)
    low: int = Field(ge=15, le=3600)

    @model_validator(mode="after")
    def _ordered(self) -> "ClaimDelays":
        if not self.critical <= self.high <= self.normal <= self.low:
            raise ValueError("delays must not decrease from critical to low")
        return self


class ReleaseNotes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ar: str = Field(default="", max_length=2000)
    fr: str = Field(default="", max_length=2000)
    en: str = Field(default="", max_length=2000)


class AppRelease(BaseModel):
    """Latest Android build offered to the phones, and the oldest build still allowed to run (addition 3)."""

    model_config = ConfigDict(extra="forbid")

    latest_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    latest_build: int = Field(ge=1, le=1_000_000)
    min_build: int = Field(ge=1, le=1_000_000)
    notes: ReleaseNotes = Field(default_factory=ReleaseNotes)
    # server: stage 1, the APK is downloaded from our server; play: stage 2, the store listing.
    channel: Literal["server", "play"] = "server"
    download_url: str | None = Field(default=None, pattern=r"^https://", max_length=500)

    @model_validator(mode="after")
    def _consistent(self) -> "AppRelease":
        if self.min_build > self.latest_build:
            raise ValueError("min_build must not exceed latest_build")
        if self.channel == "server" and self.latest_build > 1 and not self.download_url:
            raise ValueError("a server release needs its download_url")
        return self


def _terms(value: Any) -> Any:
    if not isinstance(value, list) or len(value) > 500:
        raise ValueError("a list of at most 500 words")
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str) or not 2 <= len(item.strip()) <= 64:
            raise ValueError("each word has 2 to 64 characters")
        if item.strip() not in cleaned:
            cleaned.append(item.strip())
    return cleaned


def _int_between(low: int, high: int) -> Callable[[Any], Any]:
    def check(value: Any) -> Any:
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError(f"an integer between {low} and {high}")
        return value

    return check


def _sitrep_hours(value: Any) -> Any:
    if not isinstance(value, dict) or set(value) != {"1", "2", "3", "4"}:
        raise ValueError("hours for each level 1 to 4")
    for hours in value.values():
        if isinstance(hours, bool) or not isinstance(hours, int) or not 1 <= hours <= 72:
            raise ValueError("an integer between 1 and 72 hours per level")
    return {k: int(value[k]) for k in ("1", "2", "3", "4")}


def _learning_schedule(value: Any) -> Any:
    if not isinstance(value, dict) or not set(value) <= set(LEARNING_TASKS):
        raise ValueError("a schedule per known training")
    out: dict[str, dict[str, Any]] = {}
    for key, entry in value.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("enabled"), bool):
            raise ValueError("enabled: true or false")
        every = entry.get("every_days")
        if isinstance(every, bool) or not isinstance(every, int) or not 1 <= every <= 90:
            raise ValueError("every_days: an integer between 1 and 90")
        out[key] = {"enabled": entry["enabled"], "every_days": every}
    return {k: out.get(k, {"enabled": False, "every_days": 7}) for k in LEARNING_TASKS}


def _boolean(value: Any) -> Any:
    if not isinstance(value, bool):
        raise ValueError("expected true or false")
    return value


def _model(model: type[BaseModel]) -> Callable[[Any], Any]:
    def check(value: Any) -> Any:
        return model.model_validate(value).model_dump()

    return check


DEFAULTS: dict[str, Any] = {
    SLA_BANDS: {"critical": 85, "high": 70, "normal": 40},
    SLA_CLAIM_DELAY: {"critical": 60, "high": 90, "normal": 120, "low": 180},
    SLA_ENFORCED_SINCE: None,
    ANON_QUOTA: 5,
    GEO_MAX_ACCURACY: 1000,
    NOTIFY_REAL_SEND: False,
    ALERTS_FOUR_EYES: True,
    APP_RELEASE: {
        "latest_version": "0.2.0",
        "latest_build": 1,
        "min_build": 1,
        "notes": {"ar": "", "fr": "", "en": ""},
        "channel": "server",
        "download_url": None,
    },
    MODERATION_EXTRA_TERMS: [],
    CONTACT_ACCESS_INFO_DAYS: 20,
    SAFETY_LIVE_MAX_MINUTES: 480,
    SAFETY_CHECK_MAX_HOURS: 24,
    SAFETY_LOCATION_HISTORY: False,
    CRISIS_SITREP_HOURS: {"1": 24, "2": 12, "3": 6, "4": 2},
    LEARNING_SCHEDULE: {key: {"enabled": False, "every_days": 7} for key in LEARNING_TASKS},
    THRESHOLDS: thresholds.DEFAULTS,
}

# Roles allowed to change each key (national scope required). Missing = read-only.
EDITORS: dict[str, frozenset[Role]] = {
    SLA_BANDS: frozenset({Role.CENTRAL_COMMITTEE}),
    SLA_CLAIM_DELAY: frozenset({Role.CENTRAL_COMMITTEE}),
    ANON_QUOTA: frozenset({Role.CENTRAL_COMMITTEE, Role.SECURITY_ADMIN}),
    GEO_MAX_ACCURACY: frozenset({Role.CENTRAL_COMMITTEE}),
    ALERTS_FOUR_EYES: frozenset({Role.SECURITY_ADMIN}),
    APP_RELEASE: frozenset({Role.SYSADMIN}),
    MODERATION_EXTRA_TERMS: frozenset({Role.SYSADMIN, Role.CONTENT_EDITOR}),
    CONTACT_ACCESS_INFO_DAYS: frozenset({Role.CENTRAL_COMMITTEE}),
    SAFETY_LIVE_MAX_MINUTES: frozenset({Role.SYSADMIN}),
    SAFETY_CHECK_MAX_HOURS: frozenset({Role.SYSADMIN}),
    SAFETY_LOCATION_HISTORY: frozenset({Role.SYSADMIN}),
    CRISIS_SITREP_HOURS: frozenset({Role.SYSADMIN}),
    LEARNING_SCHEDULE: frozenset({Role.SYSADMIN, Role.AI_ADMIN}),
    THRESHOLDS: frozenset({Role.SYSADMIN, Role.CENTRAL_COMMITTEE}),
}
# Keys no one may change in phase 9: enabling them needs a formal approval outside the platform (§7.4).
FORMAL_APPROVAL = frozenset({NOTIFY_REAL_SEND})

VALIDATORS: dict[str, Callable[[Any], Any]] = {
    SLA_BANDS: _model(Bands),
    SLA_CLAIM_DELAY: _model(ClaimDelays),
    ANON_QUOTA: _int_between(1, 100),
    GEO_MAX_ACCURACY: _int_between(50, 20_000),
    ALERTS_FOUR_EYES: _boolean,
    APP_RELEASE: _model(AppRelease),
    MODERATION_EXTRA_TERMS: _terms,
    CONTACT_ACCESS_INFO_DAYS: _int_between(1, 60),
    SAFETY_LIVE_MAX_MINUTES: _int_between(15, 1440),
    SAFETY_CHECK_MAX_HOURS: _int_between(1, 72),
    SAFETY_LOCATION_HISTORY: _boolean,
    CRISIS_SITREP_HOURS: _sitrep_hours,
    LEARNING_SCHEDULE: _learning_schedule,
    THRESHOLDS: thresholds.validate,
}


def validate(key: str, value: Any) -> Any:
    """The normalised value, or ``ValueError`` when it is not acceptable for ``key``."""
    try:
        return VALIDATORS[key](value)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
