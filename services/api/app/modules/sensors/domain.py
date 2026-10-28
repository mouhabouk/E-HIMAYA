"""Rules of the sensors (L5b, docs/phase-l/design-l5.md §3.1), free of the database.

A reading is signed by its sensor with HMAC-SHA256 over ``"<sensor>|<at>|<value>"``, the three strings exactly as
sent (``at`` in ISO 8601 with its offset, ``value`` a decimal such as ``"12.5"``), in lower-case hex. Signing the
strings, not a parsed number, keeps the check identical whatever language the sensor's firmware is written in.
"""

import hashlib
import hmac
import math
import re
import secrets
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal

KEY_CONTEXT = "sensor.device.key"
KEY_BYTES = 32
# A reading dated further than this from the server's clock is refused (old replay, or a clock gone astray).
CLOCK_SKEW = timedelta(minutes=10)
MAX_BATCH = 500
_VALUE = re.compile(r"^-?\d{1,7}(\.\d{1,4})?$")
_SIG = re.compile(r"^[0-9a-f]{64}$")


class Kind(StrEnum):
    RAIN_1H = "rain_1h"
    WATER_LEVEL = "water_level"
    TEMPERATURE = "temperature"


Level = Literal["normal", "watch", "alarm"]
State = Literal["normal", "watch", "alarm", "silent", "disabled"]

UNITS: dict[Kind, str] = {Kind.RAIN_1H: "mm", Kind.WATER_LEVEL: "m", Kind.TEMPERATURE: "°C"}
# The plausible range of a reading; anything outside is a fault, not an alarm.
RANGES: dict[Kind, tuple[float, float]] = {
    Kind.RAIN_1H: (0.0, 300.0),
    Kind.WATER_LEVEL: (-10.0, 100.0),
    Kind.TEMPERATURE: (-30.0, 60.0),
}
METRICS: dict[Kind, str] = {
    Kind.RAIN_1H: "sensor_rain_1h",
    Kind.WATER_LEVEL: "sensor_water_level",
    Kind.TEMPERATURE: "sensor_temperature",
}
HAZARDS: dict[Kind, str] = {Kind.RAIN_1H: "heavy_rain", Kind.WATER_LEVEL: "flood", Kind.TEMPERATURE: "heat_wave"}
SEVERITY: dict[str, str] = {"watch": "medium", "alarm": "high"}
_RANK: dict[str, int] = {"normal": 0, "watch": 1, "alarm": 2}


def new_key() -> str:
    return secrets.token_hex(KEY_BYTES)


def message(sensor: str, at: str, value: str) -> bytes:
    return f"{sensor}|{at}|{value}".encode()


def sign(key: str, sensor: str, at: str, value: str) -> str:
    return hmac.new(bytes.fromhex(key), message(sensor, at, value), hashlib.sha256).hexdigest()


def signature_valid(key: str, sensor: str, at: str, value: str, signature: str) -> bool:
    if not _SIG.match(signature):
        return False
    return hmac.compare_digest(sign(key, sensor, at, value), signature)


def parse_value(raw: str, kind: Kind) -> float | None:
    """The reading as a number, or None when it is not a plain decimal in the sensor's plausible range."""
    if not _VALUE.match(raw):
        return None
    value = float(raw)
    low, high = RANGES[kind]
    return value if math.isfinite(value) and low <= value <= high else None


def parse_at(raw: str, now: datetime) -> datetime | None:
    """The reading's time, or None when it has no offset or is too far from the server's clock."""
    if len(raw) > 40:
        return None
    try:
        at = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if at.tzinfo is None or abs(at - now) > CLOCK_SKEW:
        return None
    return at


def level_of(value: float, watch: float, alarm: float) -> Level:
    if value >= alarm:
        return "alarm"
    if value >= watch:
        return "watch"
    return "normal"


def rises(before: str, after: str) -> bool:
    return _RANK[after] > _RANK[before]


def state_of(*, enabled: bool, level: str, last_at: datetime | None, silent_after_min: int, now: datetime) -> State:
    """What the room sees: a sensor that sent nothing for its silence delay is "silent", whatever its last level."""
    if not enabled:
        return "disabled"
    if last_at is None or now - last_at > timedelta(minutes=silent_after_min):
        return "silent"
    return level  # type: ignore[return-value]
