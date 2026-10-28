"""The drone position reader beside MediaMTX (L5b, docs/phase-l/design-l5.md §3.3) [SIM until the type is known].

It only reads. Every ``TELEMETRY_POLL_S`` it asks the API which drone streams are on air, opens each one from MediaMTX
(MPEG-TS over SRT, which keeps the KLV data stream; RTSP in FFmpeg drops it), decodes the MISB ST 0601 packets
(app.klv) and posts the positions in small batches to ``POST /internal/drones/telemetry``. The API stores them, moves
the drone on the map and raises the zone and battery alerts. Nothing is ever sent to a drone, from here or anywhere.

``python -m app.telemetry serve`` runs the reader. ``python -m app.telemetry simulate`` plays a [SIM] track for one
registered drone (a lap around a point, the battery running down), through the same KLV encoding and decoding, posted
the same way: it stands in for a drone until the Office's type is known (no flight simulator is used).
"""

import argparse
import contextlib
import math
import sys
import threading
import time
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import structlog
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app import klv

log = structlog.get_logger()

Point = dict[str, Any]
Post = Callable[[str, list[Point]], None]
MAX_POINTS = 200


class TelemetrySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TELEMETRY_", extra="ignore")

    api_url: str = Field(default="http://api:8000", pattern=r"^https?://")
    # The API's SENSOR_GATEWAY_TOKEN: the same guard as the sensors' gateway (local network only).
    gateway_token: SecretStr
    # How a drone's stream is read from MediaMTX; {id} is the stream, {password} VISION_READ_PASSWORD.
    source: str = "srt://mediamtx:8890?streamid=read:live/{id}:vision:{password}"
    read_password: SecretStr = SecretStr("")
    poll_s: float = Field(default=15.0, ge=1)
    batch_s: float = Field(default=2.0, gt=0, le=60)
    timeout_s: float = Field(default=10.0, gt=0, le=60)


def point_of(fields: klv.Fields) -> Point | None:
    """The API's point of a decoded packet; None without a time or a position."""
    if fields.at is None or fields.lat is None or fields.lon is None:
        return None
    point: Point = {"at": fields.at.isoformat(), "lat": round(fields.lat, 7), "lon": round(fields.lon, 7)}
    for name in ("alt_m", "heading_deg", "sensor_az_deg", "sensor_hfov_deg"):
        value = getattr(fields, name)
        if value is not None:
            point[name] = round(value, 2)
    return point


def points_of(chunks: Iterable[bytes]) -> Iterator[Point]:
    for chunk in chunks:
        for packet in klv.packets(chunk):
            fields = klv.decode(packet)
            point = point_of(fields) if fields else None
            if point is not None:
                yield point


@contextlib.contextmanager
def data_of(source: str, timeout_s: float) -> Iterator[Iterator[bytes]]:
    """The KLV data packets of a stream (MediaMTX) or a recorded MPEG-TS [SIM]."""
    import av

    container = av.open(source, timeout=(timeout_s, timeout_s))
    try:
        streams = [s for s in container.streams.data if s.name in ("klv", "smpte_klv")] or list(container.streams.data)
        if not streams:
            raise LookupError("no KLV data stream")

        def chunks() -> Iterator[bytes]:
            for packet in container.demux(streams):
                if packet.size:
                    yield bytes(packet)

        yield chunks()
    finally:
        container.close()


def follow(drone_id: str, points: Iterable[Point], post: Post, batch_s: float, clock: Callable[[], float]) -> int:
    """Post the points of one drone in batches (every ``batch_s`` or MAX_POINTS). Returns how many were posted."""
    batch: list[Point] = []
    due = clock() + batch_s
    sent = 0
    for point in points:
        batch.append(point)
        if len(batch) >= MAX_POINTS or clock() >= due:
            post(drone_id, batch)
            sent, batch, due = sent + len(batch), [], clock() + batch_s
    if batch:
        post(drone_id, batch)
        sent += len(batch)
    return sent


class Api:
    def __init__(self, settings: TelemetrySettings) -> None:
        self.settings = settings
        self.client = httpx.Client(
            base_url=settings.api_url.rstrip("/"),
            headers={"X-Gateway-Token": settings.gateway_token.get_secret_value()},
            timeout=settings.timeout_s,
        )

    def live(self) -> list[str]:
        r = self.client.get("/internal/drones/live")
        r.raise_for_status()
        return [str(i) for i in r.json()["items"]]

    def post(self, drone_id: str, points: list[Point]) -> None:
        for attempt in range(3):
            try:
                r = self.client.post("/internal/drones/telemetry", json={"stream_id": drone_id, "points": points})
            except httpx.HTTPError as exc:
                log.warning("telemetry.api_unreachable", error=type(exc).__name__, attempt=attempt)
            else:
                if r.status_code == 200:
                    result = r.json()
                    if result.get("rejected") or result.get("alerts"):
                        log.info("telemetry.posted", drone=drone_id, **result)
                    return
                log.warning("telemetry.api_refused", drone=drone_id, status=r.status_code)
                if r.status_code < 500:
                    return
            time.sleep(min(2.0**attempt, 10.0))


def serve(settings: TelemetrySettings) -> int:
    api = Api(settings)
    running: dict[str, threading.Thread] = {}

    def read(drone_id: str) -> None:
        source = settings.source.format(id=drone_id, password=settings.read_password.get_secret_value())
        try:
            with data_of(source, settings.timeout_s) as chunks:
                sent = follow(drone_id, points_of(chunks), api.post, settings.batch_s, time.monotonic)
            log.info("telemetry.stream_ended", drone=drone_id, points=sent)
        except Exception as exc:  # the stream ended or carries no KLV: tried again at the next poll
            log.warning("telemetry.source_error", drone=drone_id, error=type(exc).__name__)

    while True:
        try:
            for drone_id in api.live():
                if drone_id not in running or not running[drone_id].is_alive():
                    running[drone_id] = threading.Thread(target=read, args=(drone_id,), daemon=True)
                    running[drone_id].start()
        except httpx.HTTPError as exc:
            log.warning("telemetry.live_unavailable", error=type(exc).__name__)
        time.sleep(settings.poll_s)


# ---------------------------------------------------------------- [SIM] a track for drills and tests


def simulated_track(
    lat: float, lon: float, start: datetime, minutes: float, every_s: float, radius_m: float = 1500.0
) -> Iterator[tuple[klv.Fields, float]]:
    """A lap around (lat, lon) at 120 m, the camera looking to the right; (fields, battery %) every ``every_s``."""
    steps = max(int(minutes * 60 / every_s), 2)
    for i in range(steps):
        angle = 2 * math.pi * i / steps
        north, east = radius_m * math.cos(angle), radius_m * math.sin(angle)
        fields = klv.Fields(
            at=start + timedelta(seconds=i * every_s),
            lat=lat + north / 111_320,
            lon=lon + east / (111_320 * math.cos(math.radians(lat))),
            alt_m=120.0,
            heading_deg=(math.degrees(angle) + 90) % 360,
            sensor_az_deg=90.0,
            sensor_hfov_deg=60.0,
        )
        yield fields, round(60.0 - 45.0 * i / (steps - 1), 1)


def simulate(api: Api, drone_id: str, lat: float, lon: float, minutes: float, every_s: float) -> int:
    sent = 0
    for fields, battery in simulated_track(lat, lon, datetime.now(UTC), minutes, every_s):
        decoded = klv.decode(klv.encode(fields))
        point = point_of(decoded) if decoded else None
        if point is None:
            continue
        api.post(drone_id, [{**point, "battery_pct": battery, "mode": "SIM"}])
        sent += 1
        time.sleep(every_s)
    return sent


def main() -> int:
    parser = argparse.ArgumentParser(prog="app.telemetry")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="read the drones' positions from MediaMTX and relay them to the API")
    sim = sub.add_parser("simulate", help="[SIM] play a track for one registered drone")
    sim.add_argument("--drone", required=True, help="the drone's id, as the dashboard shows it")
    sim.add_argument("--lat", type=float, required=True)
    sim.add_argument("--lon", type=float, required=True)
    sim.add_argument("--minutes", type=float, default=10.0)
    sim.add_argument("--every", type=float, default=2.0)
    args = parser.parse_args()
    settings = TelemetrySettings()
    if args.command == "serve":
        return serve(settings)
    simulate(Api(settings), args.drone, args.lat, args.lon, args.minutes, args.every)
    return 0


if __name__ == "__main__":
    sys.exit(main())
