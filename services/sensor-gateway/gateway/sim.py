"""SIMULATION [SIM]: sensors that sign readings like real ones, for tests, demonstrations and dry runs.

``SIM_SENSORS`` lists them as ``CODE:KEY:KIND`` separated by commas (the key the dashboard showed once when the
sensor was registered). A scenario gives each step's value; one step is sent every ``--every`` seconds.
"""

import hashlib
import hmac
import json
import time
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime

KINDS = ("rain_1h", "water_level", "temperature")


def sign(key: str, sensor: str, at: str, value: str) -> str:
    """HMAC-SHA256 over "<sensor>|<at>|<value>" in lower-case hex: what a real sensor's firmware computes."""
    return hmac.new(bytes.fromhex(key), f"{sensor}|{at}|{value}".encode(), hashlib.sha256).hexdigest()


def reading(code: str, key: str, value: float, at: datetime | None = None) -> dict[str, str]:
    stamp = (at or datetime.now(UTC)).isoformat(timespec="seconds")
    shown = f"{value:.1f}"
    return {"sensor": code, "at": stamp, "value": shown, "sig": sign(key, code, stamp, shown)}


# Scenario → kind → value at step i of n (n ≥ 2).
SCENARIOS: dict[str, dict[str, Callable[[int, int], float]]] = {
    # A storm: rain rises to 60 mm/h, the wadi follows to 4.5 m, the air cools.
    "storm": {
        "rain_1h": lambda i, n: 60.0 * i / (n - 1),
        "water_level": lambda i, n: 0.8 + 3.7 * i / (n - 1),
        "temperature": lambda i, n: 24.0 - 6.0 * i / (n - 1),
    },
    # A heat wave: temperatures climb to 47 °C; dry.
    "heat": {
        "rain_1h": lambda i, n: 0.0,
        "water_level": lambda i, n: 0.6,
        "temperature": lambda i, n: 33.0 + 14.0 * i / (n - 1),
    },
    # A calm day: nothing crosses a threshold.
    "calm": {
        "rain_1h": lambda i, n: 0.0,
        "water_level": lambda i, n: 0.7,
        "temperature": lambda i, n: 22.0 + (i % 3) * 0.5,
    },
}


def parse_sensors(raw: str) -> list[tuple[str, str, str]]:
    out = []
    for item in raw.split(","):
        if not item.strip():
            continue
        code, key, kind = (part.strip() for part in item.split(":"))
        if kind not in KINDS or len(bytes.fromhex(key)) != 32:
            raise ValueError(f"SIM_SENSORS: {code}")
        out.append((code, key, kind))
    if not out:
        raise ValueError("SIM_SENSORS is empty")
    return out


def run(gateway_url: str, sensors: list[tuple[str, str, str]], scenario: str, steps: int, every_s: float) -> None:
    curve = SCENARIOS[scenario]
    for i in range(steps):
        batch = [reading(code, key, curve[kind](i, steps)) for code, key, kind in sensors]
        request = urllib.request.Request(  # noqa: S310 (an operator-given http(s) address)
            f"{gateway_url.rstrip('/')}/readings",
            data=json.dumps({"readings": batch}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            print(f"[SIM] step {i + 1}/{steps}: {response.status} {[r['value'] for r in batch]}")
        if i + 1 < steps:
            time.sleep(every_s)
