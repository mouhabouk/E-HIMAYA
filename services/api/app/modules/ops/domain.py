"""Operations vocabulary: units, resources, assignments, call-outs, incident classification (FR-C-09)."""

from typing import Literal

from app.modules.reports.domain import Category

UnitKind = Literal["directorate", "unit", "advanced_post"]
ResourceKind = Literal[
    "fire_engine",
    "water_tanker",
    "ambulance",
    "rescue_vehicle",
    "heavy_equipment",
    "drone",
    "large_extinguisher",
    "boat",
    "command_vehicle",
    "other",
]
ResourceStatus = Literal["available", "assigned", "out_of_service"]
AssignmentStatus = Literal["ordered", "en_route", "on_scene", "released", "cancelled"]
CalloutStatus = Literal["open", "filled", "cancelled", "closed"]
TargetStatus = Literal["sent", "accepted", "declined", "expired", "arrived"]
Outcome = Literal["resolved", "false_alarm", "transferred"]

ACTIVE_ASSIGNMENT = ("ordered", "en_route", "on_scene")
ASSIGNMENT_TRANSITIONS: dict[str, frozenset[str]] = {
    "ordered": frozenset({"en_route", "on_scene", "cancelled"}),
    "en_route": frozenset({"on_scene", "cancelled"}),
    "on_scene": frozenset({"released"}),
    "released": frozenset(),
    "cancelled": frozenset(),
}

# Incident classification (تصنيف الحادث) per category; "other" is always allowed.
CLASSIFICATIONS: dict[Category, tuple[str, ...]] = {
    Category.FIRE: ("forest_fire", "residential_fire", "industrial_fire", "vehicle_fire"),
    Category.FLOOD: ("river_flood", "urban_flood", "flash_flood"),
    Category.TRAFFIC_ACCIDENT: ("road_accident", "chemical_road_accident", "rail_accident"),
    Category.DROWNING: ("beach", "dam_or_lake", "well"),
    Category.LANDSLIDE: ("landslide", "rockfall", "building_collapse"),
    Category.CHEMICAL_LEAK: ("industrial_leak", "transport_leak", "gas_leak"),
    Category.MEDICAL: ("cardiac", "trauma", "mass_casualty"),
    Category.SOS: (),
    Category.OTHER: (),
}


def classification_allowed(category: Category, value: str) -> bool:
    return value == "other" or value in CLASSIFICATIONS[category]
