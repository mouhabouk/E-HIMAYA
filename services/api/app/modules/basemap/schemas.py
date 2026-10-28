from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.basemap.domain import Provider


class TileSource(BaseModel):
    tiles: list[str]
    attribution: str
    max_zoom: int


class BasemapOut(BaseModel):
    """What a map needs to draw the satellite and hybrid views (no key, ever)."""

    source: Literal["open", "paid"]
    satellite: TileSource
    labels: TileSource
    # The open source stays the fallback of every paid tile.
    open: TileSource


class SettingsOut(BaseModel):
    configured: bool
    provider: Provider | None
    url_template: str | None
    key_hint: str | None
    key_header: str | None
    attribution: str | None
    max_zoom: int
    enabled: bool
    last_test_ok: bool | None
    last_test_at: datetime | None
    updated_by_name: str | None
    updated_at: datetime | None


class SettingsIn(BaseModel):
    provider: Provider
    url_template: str = Field(min_length=12, max_length=1000)
    # None keeps the stored key, "" removes it.
    api_key: str | None = Field(default=None, max_length=2000)
    key_header: str | None = Field(default=None, pattern=r"^[A-Za-z][A-Za-z0-9-]{1,63}$")
    attribution: str = Field(min_length=2, max_length=300)
    max_zoom: int = Field(default=19, ge=1, le=22)
    enabled: bool = False


class TestOut(BaseModel):
    ok: bool
    status: int | None
    content_type: str | None
    ms: int
    error: str | None
