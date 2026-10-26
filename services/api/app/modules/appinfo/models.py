import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.crypto import EncryptedText
from app.core.db import Base


class AppRating(Base):
    """A rating of the app (phase P5b, F-APP-143): 1 to 5 stars and an optional remark, encrypted."""

    __tablename__ = "app_rating"
    __table_args__ = {"schema": "feedback"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.account.user_id", ondelete="CASCADE")
    )
    stars: Mapped[int] = mapped_column(SmallInteger)
    remark: Mapped[str | None] = mapped_column("remark_enc", EncryptedText("feedback.app_rating.remark"))
    platform: Mapped[str | None] = mapped_column(Text)
    build: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[str | None] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(Text, server_default="ar")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
