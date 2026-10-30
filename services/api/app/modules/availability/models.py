"""Availability calendar of volunteers and doctors (migration 0083, phase N, docs/phase-n/design-n.md §8)."""

import uuid
from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, ForeignKey, SmallInteger, Text, Time, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AvailabilitySlot(Base):
    """A period the person is available, or not: every day between two dates, or on some weekdays only."""

    __tablename__ = "availability_slot"
    __table_args__ = {"schema": "identity"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.account.user_id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    # ISO weekdays (1 Monday … 7 Sunday); empty: every day of the dates.
    weekdays: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), server_default="{}")
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    # Local time of Tunisia; a slot whose end is before its start runs past midnight.
    from_time: Mapped[time] = mapped_column(Time)
    to_time: Mapped[time] = mapped_column(Time)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
