"""Rules of the drones as read-only sources (L5b, docs/phase-l/design-l5.md §3.3), free of the database.

A drone is never sent anything: the pilot alone flies it. The system reads where it is (from its own stream through
MediaMTX, or a bridge on the local network) and tells the room when it leaves its work area, nears or enters a no-fly
zone, or runs low on battery.
"""

from datetime import timedelta
from typing import Literal

from app.modules.towers.domain import wedge

AlertKind = Literal["left_work_area", "near_no_fly", "in_no_fly", "low_battery"]
ALERT_KINDS: tuple[AlertKind, ...] = ("left_work_area", "near_no_fly", "in_no_fly", "low_battery")
LOW_BATTERY_PCT = 25.0
# The same alert of the same drone (and zone) is not repeated sooner than this.
ALERT_COOLDOWN = timedelta(minutes=5)
MAX_POINTS = 200
# A point dated further than this from the server's clock is refused (old replay, or a clock gone astray).
CLOCK_SKEW = timedelta(minutes=10)
TRACK_MINUTES_MAX = 24 * 60

__all__ = ["wedge"]


def camera_reach_m(alt_m: float | None) -> int:
    """How far the camera's cone is drawn on the map: about three times the height, between 300 m and 3 km."""
    return int(min(max((alt_m or 100.0) * 3, 300.0), 3000.0))


def battery_alert(before: float | None, now: float | None) -> bool:
    """True once, when the battery crosses the low threshold (not on every point below it)."""
    if now is None or now >= LOW_BATTERY_PCT:
        return False
    return before is None or before >= LOW_BATTERY_PCT
