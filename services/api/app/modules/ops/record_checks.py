"""Times of a mission that hold but are not credible (phase S2, docs/phase-s/design-s2.md §6): a vehicle faster than
the road allows, two steps pressed together, a return never given. Shown to the room as warnings to check; they never
block a write, because a real mission can be unusual."""

from datetime import datetime, timedelta

#: Straight-line speed from the unit to the scene above which the travel time is not credible.
MAX_SPEED_KMH = 130
#: Below this distance the speed is not judged (the unit next to the scene).
SPEED_FROM_M = 2000
INSTANT = timedelta(seconds=30)
TRANSPORT_INSTANT = timedelta(seconds=60)
TURNOUT_LONG = timedelta(minutes=30)
ON_SCENE_LONG = timedelta(hours=12)
RETURN_LONG = timedelta(hours=6)
RETURN_DUE = timedelta(hours=3)

WARNINGS = (
    "travel_too_fast",
    "steps_together",
    "turnout_long",
    "on_scene_long",
    "transport_instant",
    "return_long",
    "return_missing",
    "crew_missing",
)


def warnings(
    times: dict[str, datetime | None],
    *,
    status: str,
    released_at: datetime | None,
    crew_count: int | None,
    distance_m: float | None,
    now: datetime,
) -> list[str]:
    """The warnings of a mission's record, in the order of the mission."""
    out: list[str] = []
    created, departure, arrival = times.get("created_at"), times.get("en_route_at"), times.get("on_scene_at")
    left, hospital, back = times.get("left_scene_at"), times.get("at_hospital_at"), times.get("back_at_unit_at")
    if status == "cancelled":
        return out
    if created and departure and departure - created > TURNOUT_LONG:
        out.append("turnout_long")
    if departure and arrival:
        travel = arrival - departure
        if distance_m is not None and distance_m >= SPEED_FROM_M and travel.total_seconds() > 0:
            if distance_m / 1000 / (travel.total_seconds() / 3600) > MAX_SPEED_KMH:
                out.append("travel_too_fast")
        if travel < INSTANT and (distance_m is None or distance_m > 500) and "travel_too_fast" not in out:
            out.append("steps_together")
    if arrival and left and left - arrival > ON_SCENE_LONG:
        out.append("on_scene_long")
    if left and hospital and hospital - left < TRANSPORT_INSTANT:
        out.append("transport_instant")
    last_out = hospital or left or arrival
    if back and last_out and back - last_out > RETURN_LONG:
        out.append("return_long")
    if back is None and released_at is not None and now - released_at > RETURN_DUE:
        out.append("return_missing")
    if status == "released" and crew_count is None:
        out.append("crew_missing")
    return out
