"""The daily drowning risk of a beach, by declared rules (docs/phase-l/design-l1b-coastal.md §2).

A score from 0 to 100 for the bathing hours (10:00 to 19:00, Tunis time) of one day, from the marine weather (waves,
current), the weather (an onshore wind, the heat), the season, what is known of the beach (crowd, lifeguards) and
past drownings near it. Each rule that gives points is returned as a factor, so the card says *why* a beach is red.
The thresholds are one settings row (coastal.settings) that the Office changes; the defaults are below. The score
supports a decision: it never sends a public alert by itself.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

DEFAULT_RULES: dict[str, Any] = {
    # [upper bound of the wave height in metres, points]; the last band has no upper bound.
    "waves": [[0.5, 0], [1.0, 10], [1.5, 25], [2.5, 40], [None, 55]],
    "onshore_angle_deg": 60,
    "onshore_kmh": 25,
    "onshore_points": 10,
    "strong_onshore_kmh": 40,
    "strong_onshore_points": 15,
    "current_kmh": 1.8,
    "current_points": 10,
    "season_months": [6, 7, 8, 9],
    "hot_c": 30,
    "season_points": 10,
    "crowd_high_points": 5,
    "unguarded_points": 10,
    "incident_radius_m": 500,
    "incident_years": 5,
    "incident_points": 5,
    "incident_max": 15,
    "yellow": 35,
    "red": 60,
    "first_hour": 10,
    "last_hour": 19,
}
LEVELS = ("green", "yellow", "red")


def rules_of(stored: dict[str, Any] | None) -> dict[str, Any]:
    """The defaults overridden by the stored settings (unknown keys are ignored)."""
    out = dict(DEFAULT_RULES)
    for key, value in (stored or {}).items():
        if key in DEFAULT_RULES and value is not None:
            out[key] = value
    return out


@dataclass(frozen=True, slots=True)
class DayInputs:
    """The worst values of the bathing hours of one day (None: unknown)."""

    day: date
    wave_height_m: float | None = None
    current_kmh: float | None = None
    sea_temp_c: float | None = None
    max_temperature_c: float | None = None
    # The strongest wind of the day that blows from the sea (km/h), and its direction (from).
    onshore_wind_kmh: float | None = None
    onshore_wind_from_deg: float | None = None
    max_wind_kmh: float | None = None
    crowd: str | None = None  # "high" | "medium" | "low"
    guarded: bool | None = None
    incidents: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "wave_height_m": self.wave_height_m,
            "current_kmh": self.current_kmh,
            "sea_temp_c": self.sea_temp_c,
            "max_temperature_c": self.max_temperature_c,
            "onshore_wind_kmh": self.onshore_wind_kmh,
            "max_wind_kmh": self.max_wind_kmh,
            "crowd": self.crowd,
            "guarded": self.guarded,
            "incidents": self.incidents,
        }


@dataclass(frozen=True, slots=True)
class Risk:
    score: int
    level: str
    factors: list[dict[str, Any]]


def angle_between(a: float, b: float) -> float:
    """The smaller angle between two bearings, in degrees (0 to 180)."""
    d = abs(a - b) % 360.0
    return 360.0 - d if d > 180.0 else d


def is_onshore(wind_from_deg: float | None, seaward_deg: float | None, rules: dict[str, Any]) -> bool:
    """A wind blowing from the open sea towards the beach (the wind direction is where it comes from)."""
    if wind_from_deg is None or seaward_deg is None:
        return False
    return angle_between(wind_from_deg, seaward_deg) < float(rules["onshore_angle_deg"])


def level_of(score: int, rules: dict[str, Any]) -> str:
    if score >= int(rules["red"]):
        return "red"
    if score >= int(rules["yellow"]):
        return "yellow"
    return "green"


def assess(inputs: DayInputs, rules: dict[str, Any]) -> Risk:
    factors: list[dict[str, Any]] = []

    def add(code: str, points: int, value: Any = None) -> None:
        if points:
            factors.append({"code": code, "points": points, "value": value})

    if inputs.wave_height_m is not None:
        for upper, points in rules["waves"]:
            if upper is None or inputs.wave_height_m < float(upper):
                add("waves", int(points), round(inputs.wave_height_m, 1))
                break
    if inputs.onshore_wind_kmh is not None:
        if inputs.onshore_wind_kmh > float(rules["strong_onshore_kmh"]):
            add("onshore_wind", int(rules["strong_onshore_points"]), round(inputs.onshore_wind_kmh))
        elif inputs.onshore_wind_kmh > float(rules["onshore_kmh"]):
            add("onshore_wind", int(rules["onshore_points"]), round(inputs.onshore_wind_kmh))
    if inputs.current_kmh is not None and inputs.current_kmh > float(rules["current_kmh"]):
        add("current", int(rules["current_points"]), round(inputs.current_kmh, 1))
    in_season = inputs.day.month in rules["season_months"]
    hot = inputs.max_temperature_c is not None and inputs.max_temperature_c > float(rules["hot_c"])
    if in_season or hot:
        add("season", int(rules["season_points"]), round(inputs.max_temperature_c or 0) if hot else inputs.day.month)
    if inputs.crowd == "high":
        add("crowd", int(rules["crowd_high_points"]), "high")
    if in_season and inputs.guarded is False:
        add("unguarded", int(rules["unguarded_points"]), False)
    if inputs.incidents > 0:
        points = min(inputs.incidents * int(rules["incident_points"]), int(rules["incident_max"]))
        add("past_drownings", points, inputs.incidents)
    score = max(0, min(100, sum(int(f["points"]) for f in factors)))
    return Risk(score=score, level=level_of(score, rules), factors=factors)
