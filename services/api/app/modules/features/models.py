import uuid
from datetime import datetime

from sqlalchemy import DateTime, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class FeatureRule(Base):
    """A grant or a hiding of a catalogue feature for one account or one role (L4 §8), set by the administrator."""

    __tablename__ = "feature_rule"
    __table_args__ = {"schema": "access"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    feature_key: Mapped[str] = mapped_column(Text)
    # grant | hide
    effect: Mapped[str] = mapped_column(Text)
    # user (target = the account's subject) | role (target = the role)
    target_kind: Mapped[str] = mapped_column(Text)
    target: Mapped[str] = mapped_column(Text)
    target_name: Mapped[str | None] = mapped_column(Text)
    # A role rule limited to one gouvernorat; None = every gouvernorat.
    gouvernorat_code: Mapped[int | None] = mapped_column(SmallInteger)
    reason: Mapped[str] = mapped_column(Text)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_name: Mapped[str | None] = mapped_column(Text)
    revoke_reason: Mapped[str | None] = mapped_column(Text)
