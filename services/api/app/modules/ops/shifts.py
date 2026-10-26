"""Shifts of the staff app (phase P4a, docs/phase-p4/design-staff.md §4.2): which team leader holds a vehicle.

Kept apart from ``ops.crew`` so the room's assignment flow (``ops.interventions``) can attach the shift and ring the
leader's phone without importing the staff app's endpoints.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notify import outbox
from app.modules.ops.models import Assignment, Shift, StaffDevice

MISSION_TITLE = outbox.localized("مهمة جديدة", "Nouvelle mission", "New mission")
MISSION_BODY = outbox.localized(
    "افتح التطبيق لقراءة أمر التكليف.", "Ouvrez l'application pour lire l'ordre.", "Open the app to read the order."
)


async def open_shift_of_resource(session: AsyncSession, resource_id: uuid.UUID) -> Shift | None:
    return await session.scalar(select(Shift).where(Shift.resource_id == resource_id, Shift.ended_at.is_(None)))


async def attach(session: AsyncSession, assignment: Assignment) -> None:
    """A vehicle on shift is ordered: the assignment remembers the shift and the leader's phone rings.

    The push carries the assignment id only; the app fetches the mission with the leader's identity."""
    if assignment.resource_id is None:
        return
    shift = await open_shift_of_resource(session, assignment.resource_id)
    if shift is None:
        return
    assignment.shift_id = shift.id
    device = await session.get(StaffDevice, shift.device_id)
    if device is not None and device.revoked_at is None and device.push_token:
        outbox.staff_push(
            session,
            device.push_token,
            device.platform,
            "mission",
            {"assignment_id": str(assignment.id)},
            title=MISSION_TITLE,
            body=MISSION_BODY,
        )
