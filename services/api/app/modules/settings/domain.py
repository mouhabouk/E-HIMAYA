"""National settings (phase 9, docs/api/phase-9-contract.md §2): keys, defaults, who may change them, validation.

Codes never change with the language; the dashboard translates the keys. Defaults here match the seeds of migration
0018 and apply when a row is missing.
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.core.security import Role

SLA_BANDS = "sla.bands"
SLA_CLAIM_DELAY = "sla.claim_delay_s"
SLA_ENFORCED_SINCE = "sla.enforced_since"
ANON_QUOTA = "anonymous.report_quota"
GEO_MAX_ACCURACY = "geo.max_trusted_accuracy_m"
NOTIFY_REAL_SEND = "notify.real_send_enabled"

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


def _int_between(low: int, high: int) -> Callable[[Any], Any]:
    def check(value: Any) -> Any:
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError(f"an integer between {low} and {high}")
        return value

    return check


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
}

# Roles allowed to change each key (national scope required). Missing = read-only.
EDITORS: dict[str, frozenset[Role]] = {
    SLA_BANDS: frozenset({Role.CENTRAL_COMMITTEE}),
    SLA_CLAIM_DELAY: frozenset({Role.CENTRAL_COMMITTEE}),
    ANON_QUOTA: frozenset({Role.CENTRAL_COMMITTEE, Role.SECURITY_ADMIN}),
    GEO_MAX_ACCURACY: frozenset({Role.CENTRAL_COMMITTEE}),
}
# Keys no one may change in phase 9: enabling them needs a formal approval outside the platform (§7.4).
FORMAL_APPROVAL = frozenset({NOTIFY_REAL_SEND})

VALIDATORS: dict[str, Callable[[Any], Any]] = {
    SLA_BANDS: _model(Bands),
    SLA_CLAIM_DELAY: _model(ClaimDelays),
    ANON_QUOTA: _int_between(1, 100),
    GEO_MAX_ACCURACY: _int_between(50, 20_000),
}


def validate(key: str, value: Any) -> Any:
    """The normalised value, or ``ValueError`` when it is not acceptable for ``key``."""
    try:
        return VALIDATORS[key](value)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
