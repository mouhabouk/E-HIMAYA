"""Who opens the decision window, and on what (L4 §3.5 and §5).

* **Full view**: the central room (a national operator or ops manager) on every gouvernorat, and the ops manager of a
  gouvernorat on its own gouvernorat.
* **Delegated view**: any other staff account (the minister, a governor, a committee) only while a delegation is in
  force, and only on its events: the incidents chosen one by one and those attached to the chosen axes. A delegate
  sees neither the general statistics nor any other event, nor the resources and the programmes of the rooms.
* **Who delegates**: a national ops manager to any staff account; the ops manager of a gouvernorat to its governor
  and its local committee, on events of its gouvernorat. A delegated event is always one the delegate may see.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import ApiError
from app.core.db import as_system
from app.core.security import Principal, Role
from app.modules.window.models import WindowDelegation, WindowEvent

CENTRAL_ROOM = frozenset({Role.OPERATOR, Role.OPS_MANAGER})
# What the ops manager of a gouvernorat may open the window to (its governor and its local committee).
REGIONAL_DELEGATES = frozenset({Role.GOVERNOR, Role.LOCAL_COMMITTEE})
DELEGATION_REQUIRED = "window_delegation_required"


def full_view(principal: Principal) -> bool:
    if not principal.is_staff:
        return False
    if principal.is_national:
        return bool(principal.roles & CENTRAL_ROOM)
    return Role.OPS_MANAGER in principal.roles


def may_delegate(principal: Principal) -> bool:
    return principal.is_staff and Role.OPS_MANAGER in principal.roles


def keeps_dictionary(principal: Principal) -> bool:
    """The synonyms of the quick search are kept by the central room."""
    return full_view(principal) and principal.is_national


@dataclass(frozen=True, slots=True)
class Viewer:
    principal: Principal
    full: bool
    # The gouvernorats of the caller's scope: [] = national.
    codes: list[int]
    # Delegated view: the incidents it covers (those chosen and those of the chosen axes) and the chosen axes.
    incident_ids: list[uuid.UUID] | None = None
    axis_ids: list[uuid.UUID] | None = None
    delegation_ids: list[uuid.UUID] = field(default_factory=list)

    @property
    def delegated(self) -> bool:
        return not self.full


def _codes(principal: Principal) -> list[int]:
    return [] if principal.is_national else [principal.gouvernorat_code or 0]


async def in_force(session: AsyncSession, subject: str, now: datetime) -> list[WindowDelegation]:
    async with as_system(session):
        rows = await session.scalars(
            select(WindowDelegation)
            .where(
                WindowDelegation.grantee == subject,
                WindowDelegation.revoked_at.is_(None),
                WindowDelegation.starts_at <= now,
                WindowDelegation.ends_at > now,
            )
            .order_by(WindowDelegation.ends_at)
        )
        return list(rows)


async def viewer(session: AsyncSession, principal: Principal) -> Viewer:
    """The caller's view of the window; 403 ``window_delegation_required`` without a delegation in force."""
    if full_view(principal):
        return Viewer(principal, True, _codes(principal))
    delegations = await in_force(session, principal.subject, datetime.now(UTC))
    if not delegations:
        raise ApiError(status.HTTP_403_FORBIDDEN, DELEGATION_REQUIRED)
    ids = [d.id for d in delegations]
    async with as_system(session):
        events = (
            await session.execute(
                select(WindowEvent.kind, WindowEvent.target_id).where(WindowEvent.delegation_id.in_(ids))
            )
        ).all()
        axes = sorted({t for k, t in events if k == "axis"})
        incidents = {t for k, t in events if k == "incident"}
        if axes:
            attached = await session.scalars(
                text("SELECT incident_id FROM crisis.axis_incident WHERE axis_id = ANY(:axes) AND detached_at IS NULL"),
                {"axes": axes},
            )
            incidents |= set(attached)
    return Viewer(principal, False, _codes(principal), sorted(incidents), axes, ids)
