"""Live-stream vocabulary and the tokens that open MediaMTX paths (docs/api/phase-6-contract.md).

* Publish token: 32 random bytes, base64url (43 characters). Only its keyed hash is stored (a blind index of
  ``app.core.crypto``, so the database never holds a usable token).
* Viewer token: ``<expiry>.<mac>`` where the MAC binds the token to one path and its expiry (stateless, 5 minutes to
  start a WHEP or HLS session). Keys are domain-separated sub-keys of FIELD_ENCRYPTION_KEY version 1.
"""

import base64
import hmac
import re
import secrets
import uuid
from enum import StrEnum

from app.core.crypto import get_cipher


class Source(StrEnum):
    APP = "app"
    DRONE = "drone"
    CAMERA = "camera"
    SIM = "sim"


class StreamStatus(StrEnum):
    PENDING = "pending"
    LIVE = "live"
    ENDED = "ended"
    EXPIRED = "expired"
    REJECTED = "rejected"


class EndReason(StrEnum):
    PUBLISHER_STOPPED = "publisher_stopped"
    STAFF_STOPPED = "staff_stopped"
    MAX_DURATION = "max_duration"
    TOKEN_EXPIRED = "token_expired"  # noqa: S105 (an end reason, not a secret)
    ERROR = "error"


FIXED_SOURCES = frozenset({Source.DRONE, Source.CAMERA, Source.SIM})
ACTIVE = (StreamStatus.PENDING.value, StreamStatus.LIVE.value)
# A fixed source whose publisher dropped may reconnect (flaky drone links); one stopped by staff may not.
RECONNECTABLE = frozenset({EndReason.PUBLISHER_STOPPED.value, EndReason.ERROR.value})
VISION_LABELS = ("fire", "smoke", "person")
ALERT_LABELS = ("fire", "smoke")
# Confirmation window: a label is confirmed in CONFIRM_HITS of the last CONFIRM_FRAMES analysed frames.
CONFIRM_FRAMES = 5
CONFIRM_HITS = 3
# Citizen location updates closer than this are ignored; dashboards get at most one stream.location per interval.
LOCATION_MIN_INTERVAL_S = 3
LOCATION_EVENT_INTERVAL_S = 10

_PATH = re.compile(r"^live/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$")
_PUBLISH_CONTEXT = "reports.live_stream.publish_token"
_VIEWER_CONTEXT = "reports.live_stream.viewer_token"
_VIEWER_TOKEN = re.compile(r"^(\d{10})\.([A-Za-z0-9_-]{22,64})$")


def path_of(stream_id: uuid.UUID) -> str:
    return f"live/{stream_id}"


def stream_id_of(path: str) -> uuid.UUID | None:
    """The stream id of a MediaMTX path ``live/<uuid>`` (leading slash tolerated), else None."""
    match = _PATH.match(path.strip().lstrip("/"))
    return uuid.UUID(match.group(1)) if match else None


def new_publish_token() -> str:
    return secrets.token_urlsafe(32)


def publish_token_hash(token: str) -> bytes:
    return get_cipher().blind_index(token, context=_PUBLISH_CONTEXT)


def publish_token_matches(token: str, stored: bytes | None) -> bool:
    return stored is not None and bool(token) and hmac.compare_digest(publish_token_hash(token), bytes(stored))


def _viewer_mac(path: str, expires: int) -> str:
    digest = get_cipher().blind_index(f"{path}|{expires}", context=_VIEWER_CONTEXT)
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def viewer_token(path: str, expires: int) -> str:
    """Token opening ``path`` for reading until the unix time ``expires``."""
    return f"{expires}.{_viewer_mac(path, expires)}"


def viewer_token_valid(token: str, path: str, now: float) -> bool:
    match = _VIEWER_TOKEN.match(token)
    if match is None:
        return False
    expires = int(match.group(1))
    return expires >= now and hmac.compare_digest(match.group(2), _viewer_mac(path, expires))
