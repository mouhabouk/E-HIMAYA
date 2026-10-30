"""Reading and replacing a person's availability calendar (phase N, design §8)."""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.availability import domain, schemas
from app.modules.availability.models import AvailabilitySlot
from app.modules.doctors.models import Doctor
from app.modules.volunteers.models import Volunteer


async def slots_of(session: AsyncSession, user_id: uuid.UUID, role: str) -> list[AvailabilitySlot]:
    return list(
        await session.scalars(
            select(AvailabilitySlot)
            .where(AvailabilitySlot.user_id == user_id, AvailabilitySlot.role == role)
            .order_by(AvailabilitySlot.starts_on, AvailabilitySlot.from_time, AvailabilitySlot.id)
        )
    )


def _slot(s: AvailabilitySlot) -> domain.Slot:
    return domain.Slot(s.kind, tuple(s.weekdays), s.starts_on, s.ends_on, s.from_time, s.to_time)


def out(role: str, slots: list[AvailabilitySlot], at: datetime | None = None) -> schemas.SlotsOut:
    return schemas.SlotsOut(
        role=role,
        slots=[
            schemas.SlotOut(
                id=s.id,
                kind=s.kind,
                weekdays=list(s.weekdays),
                starts_on=s.starts_on,
                ends_on=s.ends_on,
                from_time=s.from_time,
                to_time=s.to_time,
            )
            for s in slots
        ],
        planned_now=domain.planned_state([_slot(s) for s in slots], at or datetime.now(UTC)),
    )


async def require_role(session: AsyncSession, user_id: uuid.UUID, role: str) -> None:
    """Only a declared volunteer or a registered doctor keeps a calendar under that role."""
    found: Volunteer | Doctor | None = await session.get(Volunteer if role == "volunteer" else Doctor, user_id)
    if found is None or found.status == "withdrawn":
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"not_a_{role}")


async def replace(
    session: AsyncSession, user_id: uuid.UUID, role: str, body: schemas.SlotsIn
) -> list[AvailabilitySlot]:
    await session.execute(
        delete(AvailabilitySlot).where(AvailabilitySlot.user_id == user_id, AvailabilitySlot.role == role)
    )
    for s in body.slots:
        session.add(
            AvailabilitySlot(
                user_id=user_id,
                role=role,
                kind=s.kind,
                weekdays=sorted(set(s.weekdays)),
                starts_on=s.starts_on,
                ends_on=s.ends_on,
                from_time=s.from_time,
                to_time=s.to_time,
            )
        )
    await session.flush()
    return await slots_of(session, user_id, role)
