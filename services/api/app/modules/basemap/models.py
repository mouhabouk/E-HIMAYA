"""Satellite background of the maps (migration 0060): the paid provider the administration may choose."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, SmallInteger, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.crypto import EncryptedText
from app.core.db import Base

KEY_CONTEXT = "geo.basemap.api_key"


class Basemap(Base):
    __tablename__ = "basemap"
    __table_args__ = {"schema": "geo"}

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    provider: Mapped[str] = mapped_column(Text)
    url_template: Mapped[str] = mapped_column(Text)
    # Encrypted at rest; never returned by the API, never sent to a browser (the API fetches the tiles).
    api_key: Mapped[str | None] = mapped_column(EncryptedText(KEY_CONTEXT))
    key_header: Mapped[str | None] = mapped_column(Text)
    attribution: Mapped[str] = mapped_column(Text)
    max_zoom: Mapped[int] = mapped_column(SmallInteger, server_default="19")
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[str | None] = mapped_column(Text)
    updated_by_name: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
