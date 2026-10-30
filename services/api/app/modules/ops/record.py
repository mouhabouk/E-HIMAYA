"""The record of a mission (phase S2, docs/phase-s/design-s2.md): its times from the order to the return to the
unit, the agents on it and what it used. They are the indicators of the risk analysis and coverage plan (SNACR).

The team's phone gives each time as it happens. The room fills in what the team could not give, and corrects a time,
with a reason when the time came from the team. The times follow one another, and the return to the unit always comes
after the departure."""

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action
from app.core.security import Principal
from app.modules.audit import service as audit
from app.modules.ops import interventions, resources, schemas, scope
from app.modules.ops import service as incidents
from app.modules.ops.models import Assignment, Incident, TimelineEvent
from app.modules.reports.domain import Status

#: The times of a mission, in the order they happen: the order (fixed), the departure, the arrival on scene, the
#: departure from the scene, the arrival at the hospital and the return to the unit.
CHAIN = ("created_at", "en_route_at", "on_scene_at", "left_scene_at", "at_hospital_at", "back_at_unit_at")
EDITABLE = CHAIN[1:]
#: A time needs the one before it: no hospital without leaving the scene, no return without a departure.
NEEDS = {"on_scene_at": "en_route_at", "left_scene_at": "on_scene_at", "at_hospital_at": "left_scene_at"}
NEEDS_RETURN = "en_route_at"
#: The steps the team's phone gives after the arrival on scene.
MILESTONES = {"left_scene": "left_scene_at", "at_hospital": "at_hospital_at", "back_at_unit": "back_at_unit_at"}
#: A phone or a computer a little ahead of the server.
FUTURE_SKEW = timedelta(minutes=2)
#: The longest a mission lasts, from the order to the return.
MAX_MISSION = timedelta(hours=72)
#: The room completes and corrects the record up to a week after the mission ended.
EDIT_WINDOW = timedelta(days=7)
#: What a mission uses, with its largest credible amount.
CONSUMABLES: dict[str, int] = {
    "water_m3": 1000,
    "foam_l": 20000,
    "powder_kg": 5000,
    "co2_kg": 2000,
    "extinguishers": 200,
    "oxygen_l": 50000,
    "fuel_l": 5000,
    "sandbags": 20000,
    "absorbent_kg": 5000,
}


def _now() -> datetime:
    return datetime.now(UTC)


def times_of(assignment: Assignment) -> dict[str, datetime | None]:
    return {field: getattr(assignment, field) for field in CHAIN}


def broken_rule(times: dict[str, datetime | None], now: datetime) -> str | None:
    """The first rule the times break, as an error code; ``None`` when they hold."""
    for field, before in NEEDS.items():
        if times.get(field) is not None and times.get(before) is None:
            return "time_needs_previous"
    if times.get("back_at_unit_at") is not None and times.get(NEEDS_RETURN) is None:
        return "time_needs_previous"
    previous: datetime | None = None
    for field in CHAIN:
        at = times.get(field)
        if at is None:
            continue
        if at.tzinfo is None:
            return "time_without_zone"
        if at > now + FUTURE_SKEW:
            return "time_in_future"
        if previous is not None and at < previous:
            return "times_out_of_order"
        previous = at
    start = times.get("created_at")
    if start is not None and any((t := times.get(f)) is not None and t - start > MAX_MISSION for f in EDITABLE):
        return "mission_too_long"
    back, departure = times.get("back_at_unit_at"), times.get("en_route_at")
    if back is not None and departure is not None and back <= departure:
        return "return_before_departure"
    return None


def check_consumables(values: Mapping[Any, float]) -> dict[str, float]:
    """The amounts kept: known kinds, above zero, below the largest credible amount."""
    kept: dict[str, float] = {}
    for key, value in values.items():
        ceiling = CONSUMABLES.get(key)
        if ceiling is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "consumable_unknown")
        if value < 0 or value > ceiling:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "consumable_out_of_range")
        if value > 0:
            kept[key] = round(float(value), 2)
    return kept


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _timeline(session: AsyncSession, assignment: Assignment, kind: str, actor: str, **payload: Any) -> None:
    session.add(
        TimelineEvent(
            incident_id=assignment.incident_id,
            kind=kind,
            actor=actor,
            payload={"assignment_id": str(assignment.id), **payload},
        )
    )


async def _release(session: AsyncSession, assignment: Assignment, actor: str, at: datetime, source: str) -> None:
    """Back at the unit ends the mission when no one has ended it yet: the vehicle is free again."""
    if assignment.status == "on_scene":
        await interventions._set_assignment_status(session, assignment, "released", actor, at=at, source=source)


async def milestone(
    session: AsyncSession, assignment: Assignment, step: str, at: datetime, actor: str, source: str
) -> bool:
    """A step the team gives after the arrival on scene; ``False`` when the step was already given."""
    field = MILESTONES[step]
    if assignment.status not in ("on_scene", "released"):
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    if getattr(assignment, field) is not None:
        return False
    times = times_of(assignment) | {field: at}
    rule = broken_rule(times, max(_now(), at))
    if rule is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, rule)
    setattr(assignment, field, at)
    assignment.time_sources = {**(assignment.time_sources or {}), field: source}
    _timeline(session, assignment, "mission_step", actor, step=step, at=at.isoformat(), source=source)
    if step == "back_at_unit":
        await _release(session, assignment, actor, at, source)
    await session.flush()
    return True


def team_record(assignment: Assignment, crew_count: int | None, consumables: Mapping[Any, float] | None) -> None:
    """The crew and what it used, as the team gives them; the room's corrections come later."""
    if crew_count is not None:
        assignment.crew_count = crew_count
    if consumables is not None:
        assignment.consumables = check_consumables(consumables)


async def save(
    session: AsyncSession, principal: Principal, assignment_id: uuid.UUID, body: schemas.RecordIn
) -> Assignment:
    """The room completes or corrects the record of a mission."""
    assignment = await session.get(Assignment, assignment_id, with_for_update=True)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    incident = await incidents.get_in_scope(session, principal, assignment.incident_id)
    own = scope.regional_only(principal)
    await scope.check_incident(session, principal, incident, Action.ASSIGNMENT_STATUS)
    if assignment.resource_id is not None:
        await interventions._owned_resource(session, own, assignment.resource_id)
    if assignment.status == "cancelled":
        raise HTTPException(status.HTTP_409_CONFLICT, "assignment_cancelled")
    now = _now()
    if assignment.released_at is not None and now - assignment.released_at > EDIT_WINDOW:
        raise HTTPException(status.HTTP_409_CONFLICT, "record_closed")
    actor = audit.name_of(principal) or audit.actor_of(principal)
    before = times_of(assignment)
    given = body.times.model_dump(exclude_unset=True) if body.times is not None else {}
    after = before | given
    if before["en_route_at"] is not None and after["en_route_at"] is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "time_required")
    if before["on_scene_at"] is not None and after["on_scene_at"] is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "time_required")
    rule = broken_rule(after, now)
    if rule is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, rule)
    sources = dict(assignment.time_sources or {})
    changed = {f: after[f] for f in EDITABLE if after[f] != before[f]}
    corrected = [f for f in changed if before[f] is not None and sources.get(f, "room") != "room"]
    if corrected and not (body.reason or "").strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "correction_reason_required")
    # A time the room gives for a step the status has not reached moves the mission on, as the status buttons do.
    if changed.get("en_route_at") is not None and assignment.status == "ordered":
        await interventions._set_assignment_status(session, assignment, "en_route", actor, at=changed["en_route_at"])
    if changed.get("on_scene_at") is not None and assignment.status in ("ordered", "en_route"):
        await interventions._set_assignment_status(session, assignment, "on_scene", actor, at=changed["on_scene_at"])
        await interventions.advance_reports(session, incident.id, Status.INTERVENED)
    for field, value in changed.items():
        setattr(assignment, field, value)
        if value is None:
            sources.pop(field, None)
        else:
            sources[field] = "room"
    assignment.time_sources = sources
    if changed.get("back_at_unit_at") is not None:
        await _release(session, assignment, actor, changed["back_at_unit_at"], "room")
        assignment.time_sources = {**assignment.time_sources, "back_at_unit_at": "room"}
    if assignment.released_at is not None and assignment.on_scene_at is not None:
        assignment.released_at = max(assignment.released_at, assignment.on_scene_at)
    crew_before, used_before = assignment.crew_count, dict(assignment.consumables or {})
    if "crew_count" in body.model_fields_set:
        assignment.crew_count = body.crew_count
    if body.consumables is not None:
        assignment.consumables = check_consumables(body.consumables)
    if not changed and crew_before == assignment.crew_count and used_before == assignment.consumables:
        return assignment
    _timeline(
        session,
        assignment,
        "record_saved",
        actor,
        times={f: {"from": _iso(before[f]), "to": _iso(v)} for f, v in changed.items()},
        crew_count=assignment.crew_count,
        consumables=assignment.consumables,
        reason=(body.reason or "").strip() or None,
    )
    await session.flush()
    await interventions.announce_assignment(session, assignment)
    if assignment.resource_id is not None:
        await resources.announce(session, assignment.resource_id)
    found = await session.get(Incident, assignment.incident_id)
    if found is not None:
        await interventions.announce_incident(session, found)
    return assignment
