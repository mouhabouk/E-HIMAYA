"""Rules of the watch towers (L5b, docs/phase-l/design-l5.md §3.2), free of the database.

The edge computer of a tower (a Raspberry Pi beside the camera) runs the fire and smoke detector on the camera's
picture and keeps the last frames. When a label is in ``hits`` of the last ``frames`` frames (3 of 5), it signs an
event with HMAC-SHA256 over::

    "<tower>|<at>|<label>|<confidence>|<hits>|<frames>|<frame_sha256>"

the strings exactly as sent (``at`` ISO 8601 with its offset, ``confidence`` a decimal such as ``"0.87"``,
``frame_sha256`` the lower-case hex SHA-256 of the JPEG sent with it, or empty without one), in lower-case hex. The key
is the tower's 32-byte key in hex, the same scheme as the sensors (app.modules.sensors.domain).
"""

import hashlib
import hmac
import math
import re

from app.modules.sensors.domain import CLOCK_SKEW, new_key, parse_at
from app.modules.streams.domain import CONFIRM_FRAMES, CONFIRM_HITS

KEY_CONTEXT = "reports.camera_tower.key"
LABELS = ("fire", "smoke")
METRICS = {"fire": "tower_fire", "smoke": "tower_smoke"}
_CONFIDENCE = re.compile(r"^(0(\.\d{1,4})?|1(\.0{1,4})?)$")
_COUNT = re.compile(r"^\d{1,2}$")
_SIG = re.compile(r"^[0-9a-f]{64}$")
_SHA = re.compile(r"^([0-9a-f]{64})?$")

__all__ = ["CLOCK_SKEW", "CONFIRM_FRAMES", "CONFIRM_HITS", "new_key", "parse_at"]


def message(tower: str, at: str, label: str, confidence: str, hits: str, frames: str, frame_sha256: str) -> bytes:
    return f"{tower}|{at}|{label}|{confidence}|{hits}|{frames}|{frame_sha256}".encode()


def sign(key: str, tower: str, at: str, label: str, confidence: str, hits: str, frames: str, frame_sha256: str) -> str:
    return hmac.new(
        bytes.fromhex(key), message(tower, at, label, confidence, hits, frames, frame_sha256), hashlib.sha256
    ).hexdigest()


def signature_valid(key: str, signature: str, *fields: str) -> bool:
    if not _SIG.match(signature) or len(fields) != 7 or not _SHA.match(fields[6]):
        return False
    return hmac.compare_digest(sign(key, *fields), signature)


def parse_confidence(raw: str) -> float | None:
    if not _CONFIDENCE.match(raw):
        return None
    value = float(raw)
    return value if math.isfinite(value) else None


def parse_confirmation(hits: str, frames: str) -> tuple[int, int] | None:
    """(hits, frames) when the event meets the room's own rule (at least 3 of the last 5 frames), else None."""
    if not _COUNT.match(hits) or not _COUNT.match(frames):
        return None
    h, f = int(hits), int(frames)
    if f != CONFIRM_FRAMES or not CONFIRM_HITS <= h <= f:
        return None
    return h, f


def wedge(lat: float, lon: float, bearing_deg: int, fov_deg: int, range_m: int, steps: int = 16) -> list[list[float]]:
    """The field of view as a closed GeoJSON ring of [lon, lat] (a full circle when the camera turns all round)."""
    earth = 6_371_000.0
    full = fov_deg >= 360
    start = 0.0 if full else bearing_deg - fov_deg / 2
    span = 360.0 if full else float(fov_deg)
    ring: list[list[float]] = [] if full else [[lon, lat]]
    for i in range(steps + 1):
        angle = math.radians(start + span * i / steps)
        d = range_m / earth
        lat1, lon1 = math.radians(lat), math.radians(lon)
        lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(angle))
        lon2 = lon1 + math.atan2(
            math.sin(angle) * math.sin(d) * math.cos(lat1), math.cos(d) - math.sin(lat1) * math.sin(lat2)
        )
        ring.append([round(math.degrees(lon2), 6), round(math.degrees(lat2), 6)])
    ring.append(ring[0])
    return ring
