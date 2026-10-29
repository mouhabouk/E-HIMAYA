"""What happened after each decision (AI5c, docs/phase-ai5/design-ai5.md §7.3): ``command_decision.outcome``.

Once an incident is closed, each decision taken on it is linked to what followed, read from the incident itself:

* ``closed_after_min``: minutes from the decision to the closing of the incident;
* ``result``: the closing evaluation's outcome (``ops.incident.evaluation``), when the room filled it in;
* ``assignments_after`` and ``first_on_scene_min``: the orders given after the decision, and how long until the first
  of them was on the scene;
* ``escalated``: the incident ended at a higher operational level than the one the decision was taken at;
* ``needed_later``: for a proposal of resources, whether a resource of that kind was sent after all after the
  decision. A rejected proposal of resources followed by the same resources is a lesson for the ranking (ranker.py).

An incident that is reopened and closed again is linked again (``closed_at`` changes). Counts and minutes only.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.decision.models import CommandDecision
from app.modules.ops.models import Assignment, Incident, OpLevel, Resource

BATCH = 500
LEVELS = [level.value for level in OpLevel]
# An assignment of the incident: created, on scene, cancelled, kind of resource.
Order = tuple[datetime, datetime | None, datetime | None, str | None]


def resource_kind(key: str) -> str | None:
    """The resource kind a proposal is about: ``resources:ambulance`` (rules) or ``order:dispatch:ambulance``."""
    parts = key.split(":")
    if parts[0] == "resources" and len(parts) == 2 and parts[1] != "location":
        return parts[1]
    if parts[:2] == ["order", "dispatch"] and len(parts) == 3:
        return parts[2]
    return None


def _minutes(start: datetime, end: datetime) -> float:
    return round((end - start).total_seconds() / 60, 1)


def outcome_of(row: CommandDecision, incident: Incident, orders: list[Order]) -> dict[str, Any]:
    """The outcome of one decided row, from the incident's assignments."""
    assert row.decided_at is not None and incident.closed_at is not None
    after = [o for o in orders if o[0] >= row.decided_at and o[2] is None]
    arrivals = [o[1] for o in after if o[1] is not None]
    level_then = row.features.get("op_level")
    level_now = incident.op_level.value if isinstance(incident.op_level, OpLevel) else str(incident.op_level)
    kind = resource_kind(row.key)
    return {
        "closed_at": incident.closed_at.isoformat(),
        "closed_after_min": _minutes(row.decided_at, incident.closed_at),
        "result": (incident.evaluation or {}).get("outcome"),
        "assignments_after": len(after),
        "first_on_scene_min": _minutes(row.decided_at, min(arrivals)) if arrivals else None,
        "escalated": (
            LEVELS.index(level_now) > LEVELS.index(level_then) if level_then in LEVELS and level_now in LEVELS else None
        ),
        "needed_later": any(o[3] == kind for o in after) if kind else None,
    }


async def link(session: AsyncSession, limit: int = BATCH) -> int:
    """Outcomes of the decided rows of closed incidents that have none yet, or an older one (a bounded batch)."""
    rows = (
        await session.execute(
            select(CommandDecision, Incident)
            .join(Incident, Incident.id == CommandDecision.incident_id)
            .where(
                CommandDecision.decided_at.is_not(None),
                Incident.status == "closed",
                Incident.closed_at.is_not(None),
                or_(
                    CommandDecision.outcome.is_(None),
                    cast(CommandDecision.outcome["closed_at"].astext, DateTime(timezone=True)) != Incident.closed_at,
                ),
            )
            .order_by(CommandDecision.decided_at)
            .limit(limit)
        )
    ).all()
    orders: dict[Any, list[Order]] = {}
    for row, incident in rows:
        if incident.id not in orders:
            orders[incident.id] = [
                (created, on_scene, cancelled, kind)
                for created, on_scene, cancelled, kind in (
                    await session.execute(
                        select(Assignment.created_at, Assignment.on_scene_at, Assignment.cancelled_at, Resource.kind)
                        .outerjoin(Resource, Resource.id == Assignment.resource_id)
                        .where(Assignment.incident_id == incident.id)
                    )
                ).all()
            ]
        row.outcome = outcome_of(row, incident, orders[incident.id])
    await session.flush()
    return len(rows)


async def link_all(session: AsyncSession, rounds: int = 40) -> int:
    """Batches of ``link`` until none is left (at most ``rounds`` batches)."""
    total = 0
    for _ in range(rounds):
        linked = await link(session)
        total += linked
        if linked < BATCH:
            break
    return total
