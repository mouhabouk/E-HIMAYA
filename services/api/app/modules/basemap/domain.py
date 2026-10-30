"""Satellite background of the maps (docs/phase-r/design-basemap.md).

* Open source, on by default and without a key: Sentinel-2 cloudless by EOX (CC BY-NC-SA 4.0, attribution required;
  the civil protection's use is not commercial), with the place names of CARTO above it in the hybrid view.
* On a network without internet, both come from the Office's own map server instead (BASEMAP_OPEN_* and
  BASEMAP_LABEL_* settings, docs/offline-maps.md): open_source() and label_source() return what is in force.
* Paid source, at the administration's choice: the tile address and licence key of the provider it contracts with,
  kept by the API. The browser never receives the key: it asks the API for each tile with a signed, short-lived
  address, and the API fetches the tile from the provider. Should the provider fail, the tile comes from the open
  source instead (a redirect), so the map never goes blank.
"""

import base64
import hmac
import re
import time
from typing import Literal
from urllib.parse import quote

from app.core.config import get_settings
from app.core.crypto import get_cipher

Provider = Literal["esri", "maxar", "mapbox", "google", "other"]

OPEN_TILES = "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg"
OPEN_ATTRIBUTION = (
    "Sentinel-2 cloudless – s2maps.eu by EOX IT Services GmbH "
    "(contains modified Copernicus Sentinel data 2020), CC BY-NC-SA 4.0"
)
OPEN_MAX_ZOOM = 15
LABEL_TILES = [
    f"https://{s}.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{{z}}/{{x}}/{{y}}.png" for s in "abcd"
]
LABEL_ATTRIBUTION = "© OpenStreetMap contributors © CARTO"
LABEL_MAX_ZOOM = 20

# The tile the connection test asks for: Tunisia at zoom 6.
TEST_TILE = (6, 33, 25)
TOKEN_SECONDS = 12 * 3600
_TOKEN_CONTEXT = "geo.basemap.tile_token"  # noqa: S105 (a key derivation context, not a secret)
_TOKEN = re.compile(r"^(\d{10})\.([A-Za-z0-9_-]{22,64})$")
_PLACEHOLDERS = ("{z}", "{x}", "{y}")


def open_source() -> tuple[list[str], str, int]:
    """Tile addresses, attribution and deepest zoom of the open satellite background in force."""
    s = get_settings()
    tiles = s.basemap_open_tiles.split() if s.basemap_open_tiles else [OPEN_TILES]
    return tiles, s.basemap_open_attribution or OPEN_ATTRIBUTION, s.basemap_open_max_zoom or OPEN_MAX_ZOOM


def label_source() -> tuple[list[str], str, int]:
    """Tile addresses, attribution and deepest zoom of the place names drawn over the imagery (hybrid)."""
    s = get_settings()
    tiles = s.basemap_label_tiles.split() if s.basemap_label_tiles else LABEL_TILES
    return tiles, s.basemap_label_attribution or LABEL_ATTRIBUTION, s.basemap_label_max_zoom or LABEL_MAX_ZOOM


def open_tile(z: int, x: int, y: int) -> str:
    return open_source()[0][0].replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y))


def check_template(url_template: str, has_key: bool, key_header: str | None) -> None:
    """Raises ``ValueError(code)`` when the provider's address cannot serve tiles."""
    if not url_template.startswith("https://"):
        raise ValueError("basemap_url_https")
    if any(p not in url_template for p in _PLACEHOLDERS):
        raise ValueError("basemap_url_placeholders")
    if has_key and not key_header and "{key}" not in url_template:
        raise ValueError("basemap_key_unused")
    if "{key}" in url_template and not has_key:
        raise ValueError("basemap_key_missing")


def tile_url(url_template: str, z: int, x: int, y: int, key: str | None) -> str:
    url = url_template.replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y))
    return url.replace("{key}", quote(key or "", safe=""))


def _mac(expires: int) -> str:
    digest = get_cipher().blind_index(str(expires), context=_TOKEN_CONTEXT)
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def tile_token(now: float | None = None) -> str:
    """``<expiry>.<mac>``: opens the tile address of the API for twelve hours (any staff member, no identity)."""
    expires = int(now if now is not None else time.time()) + TOKEN_SECONDS
    return f"{expires}.{_mac(expires)}"


def tile_token_valid(token: str, now: float | None = None) -> bool:
    match = _TOKEN.match(token)
    if match is None:
        return False
    expires = int(match.group(1))
    if expires < (now if now is not None else time.time()):
        return False
    return hmac.compare_digest(match.group(2), _mac(expires))


def key_hint(key: str | None) -> str | None:
    """The last four characters, to recognise the key in the settings without showing it."""
    if not key:
        return None
    return "••••" + key[-4:] if len(key) > 8 else "••••"
