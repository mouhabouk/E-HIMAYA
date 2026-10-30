"""Operational thresholds the system administrator or the national committee tunes without a release (phase N, review
point 27, docs/phase-n/design-n.md §9).

One setting, ``operations.thresholds``, holds every number below; a missing entry takes its default. Each has bounds
the platform refuses to leave. Numbers that are protections rather than operations (rate limits, upload sizes, token
lifetimes, signature ages) stay in the code or the environment, as the design explains.
"""

from dataclasses import dataclass
from typing import Any, Literal

Unit = Literal["count", "days", "hours", "metres"]


@dataclass(frozen=True, slots=True)
class Spec:
    group: str
    unit: Unit
    default: int
    low: int
    high: int


SPECS: dict[str, Spec] = {
    # Disasters and command.
    "crisis.disaster_map_max": Spec("crisis", "count", 30, 1, 100),
    "decision.unit_radius_m": Spec("crisis", "metres", 60_000, 1_000, 300_000),
    # Candidate resources considered per kind (straight line), then ranked by travel time.
    "decision.resource_radius_m": Spec("crisis", "metres", 150_000, 1_000, 500_000),
    "forecast.flood_radius_m": Spec("crisis", "metres", 3_000, 100, 50_000),
    # Alerts to the population.
    "alerts.max_days": Spec("alerts", "days", 7, 1, 30),
    "alerts.inbox_days": Spec("alerts", "days", 30, 1, 365),
    # Rooms and field.
    # An app report and an SMS report of an unknown sender are the same report only this close to each other.
    "telephony.sms_match_m": Spec("rooms", "metres", 5_000, 100, 50_000),
    "drones.nearby_m": Spec("rooms", "metres", 20_000, 1_000, 100_000),
    "sensors.suggestion_hours": Spec("rooms", "hours", 6, 1, 72),
    "towers.suggestion_hours": Spec("rooms", "hours", 2, 1, 72),
    "inventory.stale_days": Spec("rooms", "days", 30, 1, 365),
    "coastal.warn_radius_m": Spec("rooms", "metres", 1_000, 100, 20_000),
    # A beach is guarded today when an open point of a beach programme in force is this close.
    "programmes.guard_radius_m": Spec("rooms", "metres", 1_000, 100, 20_000),
    # Doctors and institutions.
    # Each member gets a copy of the key of every medical file in the country: keep the committee small.
    "doctors.committee_max": Spec("partners", "count", 7, 1, 30),
    "orgs.invitation_days": Spec("partners", "days", 7, 1, 60),
    "orgs.reservation_due_soon_days": Spec("partners", "days", 14, 1, 90),
}

DEFAULTS: dict[str, int] = {name: spec.default for name, spec in SPECS.items()}


def validate(value: Any) -> dict[str, int]:
    """Every known threshold, the given ones within their bounds, the others at their default."""
    if not isinstance(value, dict) or not set(value) <= set(SPECS):
        raise ValueError("known thresholds only")
    out = dict(DEFAULTS)
    for name, number in value.items():
        spec = SPECS[name]
        if isinstance(number, bool) or not isinstance(number, int) or not spec.low <= number <= spec.high:
            raise ValueError(f"{name}: an integer between {spec.low} and {spec.high}")
        out[name] = number
    return out
