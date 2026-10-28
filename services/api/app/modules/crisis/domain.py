"""Disaster and crisis axes, the rules without the database (phase L3, docs/phase-l/design-l3.md).

Who may do what (§3), which interventions an axis suggests (§2.3), when the next situation report is due (§2.5),
what a recommendation or a decision signs (§4), and which earlier decision a minister's decision overrides.
"""

import base64
import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.core.security import Principal, Role

KINDS = ("flood", "forest_fire", "storm", "earthquake", "technological", "health", "other")
LEVELS = (1, 2, 3, 4)
CATEGORIES = ("evacuation", "resources", "closure", "shelter", "support", "plan", "public_information", "other")
EXECUTORS = ("regional", "central", "partner")
DIRECTIVE_STATUSES = ("issued", "received", "in_progress", "done", "failed")
FINAL_STATUSES = frozenset({"done", "failed"})
# Status changes the executing room may make; "failed" needs a reason.
NEXT_STATUS: dict[str, frozenset[str]] = {
    "issued": frozenset({"received", "in_progress", "done", "failed"}),
    "received": frozenset({"in_progress", "done", "failed"}),
    "in_progress": frozenset({"done", "failed"}),
    "done": frozenset(),
    "failed": frozenset(),
}

# Incident categories that belong to each kind of axis (suggestions only; the room decides). Rescue calls (sos),
# medical and "other" fit every kind: a flood brings drownings and injuries as well as flooded streets.
_ANY = frozenset({"sos", "medical", "other", "traffic_accident"})
COMPATIBLE: dict[str, frozenset[str]] = {
    "flood": _ANY | {"flood", "drowning", "landslide"},
    "forest_fire": _ANY | {"fire"},
    "storm": _ANY | {"flood", "fire", "landslide", "drowning"},
    "earthquake": _ANY | {"landslide", "fire", "chemical_leak"},
    "technological": _ANY | {"chemical_leak", "fire"},
    "health": _ANY,
    "other": _ANY | {"fire", "flood", "drowning", "landslide", "chemical_leak"},
}
DEFAULT_SITREP_HOURS = {"1": 24, "2": 12, "3": 6, "4": 2}
# Reminder before a directive's deadline (design §5).
REMIND_BEFORE = timedelta(hours=1)


def is_commander(p: Principal) -> bool:
    """The head of the central room: the operations manager with a national scope (decision of 27 October)."""
    return p.is_national and Role.OPS_MANAGER in p.roles


def is_room(p: Principal) -> bool:
    return bool({Role.OPERATOR, Role.OPS_MANAGER} & p.roles)


def is_room_manager(p: Principal) -> bool:
    return Role.OPS_MANAGER in p.roles


def is_governor(p: Principal) -> bool:
    return Role.GOVERNOR in p.roles and p.gouvernorat_code is not None


def is_minister(p: Principal) -> bool:
    return Role.MINISTER in p.roles and p.is_national


def issuer_role(p: Principal) -> str | None:
    """The role a recommendation or a decision is issued under (the minister first when both are held)."""
    if is_minister(p):
        return "minister"
    if is_governor(p):
        return "governor"
    return None


def reads(p: Principal) -> bool:
    return is_room(p) or is_governor(p) or is_minister(p)


def can_manage_axis(p: Principal, gouvernorat: int | None) -> bool:
    """Attach and detach interventions, shelters, evacuations, needs, situation reports: the commander for every
    axis, a regional operations manager for the axes of their gouvernorat."""
    if is_commander(p):
        return True
    return is_room_manager(p) and gouvernorat is not None and p.gouvernorat_code == gouvernorat


def can_issue(p: Principal, gouvernorat: int | None) -> bool:
    """A minister on any axis; a governor on the axes (or sub-axes) of their gouvernorat."""
    if is_minister(p):
        return True
    return is_governor(p) and gouvernorat is not None and p.gouvernorat_code == gouvernorat


def can_update_directive(p: Principal, executor: str, gouvernorat: int | None) -> bool:
    """The executing room updates a directive's status: the regional room of the axis, or the central room."""
    if executor == "central":
        return is_room(p) and p.is_national
    if is_commander(p):
        return True
    return is_room(p) and gouvernorat is not None and p.gouvernorat_code == gouvernorat


def compatible(kind: str, category: str) -> bool:
    return category in COMPATIBLE.get(kind, _ANY)


def sitrep_period(hours: Mapping[str, int] | None, level: int) -> timedelta:
    table = hours or DEFAULT_SITREP_HOURS
    return timedelta(hours=int(table.get(str(level), DEFAULT_SITREP_HOURS[str(level)])))


def axis_number(year: int, n: int) -> str:
    return f"AX-{year}-{n:03d}"


# --- Signatures (design §4) -------------------------------------------------------------------------------------


def signed_payload(
    *,
    directive_id: str,
    axis_number: str,
    number: int,
    kind: str,
    category: str,
    body: str,
    executor: str,
    executor_name: str | None,
    due_at: datetime | None,
    issuer_role: str,
    issued_by: str,
    issued_at: datetime,
) -> bytes:
    """The bytes the server signs: everything the directive says, who issued it, under which role and when."""
    doc = {
        "id": directive_id,
        "axis": axis_number,
        "number": number,
        "kind": kind,
        "category": category,
        "body": body,
        "executor": executor,
        "executor_name": executor_name,
        "due_at": due_at.isoformat() if due_at else None,
        "issuer_role": issuer_role,
        "issued_by": issued_by,
        "issued_at": issued_at.isoformat(),
    }
    return json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(payload: bytes) -> str:
    return base64.b64encode(hashlib.sha256(payload).digest()).decode()


# --- Conflicts (design §4) --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Issued:
    id: str
    kind: str
    category: str
    issuer_role: str
    status: str
    overridden: bool


def overridden_by_minister(new_kind: str, new_category: str, new_role: str, earlier: Iterable[Issued]) -> list[str]:
    """The governor's decisions of the same category, not carried out yet, that a minister's decision overrides."""
    if new_role != "minister" or new_kind != "decision":
        return []
    return [
        d.id
        for d in earlier
        if d.issuer_role == "governor"
        and d.kind == "decision"
        and d.category == new_category
        and d.status not in FINAL_STATUSES
        and not d.overridden
    ]


# --- Figures (design §2.5 and §2.6) -----------------------------------------------------------------------------


def execution_figures(directives: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Decisions issued, carried out, failed, and the mean hours from issue to done."""
    decisions = [d for d in directives if d["kind"] == "decision" and not d.get("overridden_by")]
    done = [d for d in decisions if d["status"] == "done"]
    durations = [
        (d["done_at"] - d["issued_at"]).total_seconds() / 3600 for d in done if d.get("done_at") and d.get("issued_at")
    ]
    return {
        "decisions": len(decisions),
        "decisions_done": len(done),
        "decisions_failed": sum(1 for d in decisions if d["status"] == "failed"),
        "done_share": round(len(done) / len(decisions), 3) if decisions else None,
        "mean_hours_to_done": round(sum(durations) / len(durations), 1) if durations else None,
    }
