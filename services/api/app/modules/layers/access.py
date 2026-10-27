"""Who sees which map layer, and which of its columns (phase L1a, docs/phase-l/design-layers.md §3.3-3.4).

Five audiences instead of the eleven staff roles, so the administrator chooses with buttons:

| audience  | who                                                           |
|-----------|---------------------------------------------------------------|
| citizen   | everyone, without signing in (the citizen's app)              |
| room      | operator, ops_manager                                         |
| field     | field_commander, team_leader                                  |
| command   | local_committee (the governor), central_committee (minister)  |
| support   | every other staff role                                        |

A layer is seen by its audiences once published; a draft, a paused or a deleted layer by its managers only. A
*sensitive* layer (barracks, oil and gas) is seen by the minister alone (``central_committee`` with a national
scope) and by its managers; never by a governor, even during an open crisis axis. A layer limited to some
gouvernorats (``scope``) is seen by the national staff and by the regional staff of those gouvernorats.

Columns: ``fields`` maps a column to the audiences that see it; a column not listed is seen by every audience of the
layer. The managers always see everything. The API answers 404 for a layer a principal may not see.
"""

from collections.abc import Iterable
from typing import Any, Literal

from app.core.security import Principal, Role

Audience = Literal["citizen", "room", "field", "command", "support"]
AUDIENCES: tuple[Audience, ...] = ("citizen", "room", "field", "command", "support")
STAFF_AUDIENCES: tuple[Audience, ...] = ("room", "field", "command", "support")

ROLE_AUDIENCE: dict[Role, Audience] = {
    Role.OPERATOR: "room",
    Role.OPS_MANAGER: "room",
    Role.FIELD_COMMANDER: "field",
    Role.TEAM_LEADER: "field",
    Role.LOCAL_COMMITTEE: "command",
    Role.CENTRAL_COMMITTEE: "command",
}
# Columns shown on a place card besides the extra columns of the file.
CARD_FIELDS = ("phone", "phone2", "address", "delegation", "manager", "hours", "email", "website")


def audiences_of(principal: Principal | None) -> frozenset[Audience]:
    """The audiences a principal belongs to; the citizen's app (no principal) is ``citizen``."""
    if principal is None or not principal.is_staff:
        return frozenset({"citizen"})
    found: set[Audience] = {ROLE_AUDIENCE.get(role, "support") for role in principal.roles}
    return frozenset(found)


def manages(principal: Principal | None) -> bool:
    """The system administrator with a national scope manages every layer (drafts, deleted, sensitive)."""
    return principal is not None and principal.is_national and Role.SYSADMIN in principal.roles


def is_minister(principal: Principal | None) -> bool:
    return principal is not None and principal.is_national and Role.CENTRAL_COMMITTEE in principal.roles


def sees(principal: Principal | None, layer: Any) -> bool:
    """Whether ``principal`` (None: the citizen's app) sees ``layer`` on its maps."""
    if layer.deleted_at is not None:
        return manages(principal)
    if manages(principal):
        return True
    if layer.status != "published":
        return False
    if layer.sensitive:
        return is_minister(principal)
    if not set(layer.audiences) & audiences_of(principal):
        return False
    if layer.scope and principal is not None and principal.is_staff and not principal.is_national:
        return principal.gouvernorat_code in layer.scope
    return True


def visible_fields(principal: Principal | None, layer: Any) -> set[str] | None:
    """The columns hidden from ``principal`` in this layer (None: nothing hidden)."""
    if manages(principal):
        return None
    mine = audiences_of(principal)
    hidden = {name for name, allowed in (layer.fields or {}).items() if not set(allowed) & mine}
    return hidden or None


def strip(props: dict[str, Any], hidden: Iterable[str] | None) -> dict[str, Any]:
    if not hidden:
        return props
    blocked = set(hidden)
    return {k: v for k, v in props.items() if k not in blocked}
