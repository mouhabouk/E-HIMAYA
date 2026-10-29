"""The reference edge program of a watch tower (L5b, docs/phase-l/design-l5.md §3.2) [SIM until the field trial].

It runs on the small computer beside the tower's camera (a Raspberry Pi), on the local network only:

1. reads the camera's picture (RTSP on the local network, or a recorded video for tests and drills [SIM]);
2. runs the same fire and smoke detector as the vision service, about one frame a second;
3. keeps the last 5 analysed frames; a label at the alert confidence in 3 of them (the newest included) is
   *confirmed*, the room's own rule (app.modules.streams.domain in the API);
4. signs the event with the tower's key and posts it, with a JPEG of the confirming frame, to the gateway beside
   MediaMTX (``POST /events``), which relays it to the API. One event per label every ``EDGE_COOLDOWN_S`` at most.

The signature is HMAC-SHA256 over ``"<tower>|<at>|<label>|<confidence>|<hits>|<frames>|<frame_sha256>"`` (the
strings as sent), the same as the API checks. The video itself still goes to MediaMTX from the camera, as in phase 9;
this program sends no picture but the confirming frame, and never takes an order from anywhere.

Run: ``python -m app.edge`` with ``EDGE_TOWER``, ``EDGE_KEY`` (shown once in the dashboard), ``EDGE_SOURCE`` and
``EDGE_GATEWAY_URL`` (docs/sensor-gateway.md, "Watch towers").
"""

import base64
import contextlib
import hashlib
import hmac
import io
import os
import secrets
import sys
import time
from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
import numpy as np
import structlog
from numpy.typing import NDArray
from PIL import Image
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.processing import Detection

log = structlog.get_logger()

ALERT_LABELS = ("fire", "smoke")
FRAMES = 5
HITS = 3
Frame = NDArray[np.uint8]
Detect = Callable[[Frame], list[Detection]]
Post = Callable[[dict[str, str]], None]


class EdgeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EDGE_", extra="ignore")

    # The tower's code and its key (64 hex characters), as the dashboard showed them once.
    tower: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{1,39}$")
    key: SecretStr
    # rtsp://… of the camera on the local network, or a recorded video file [SIM].
    source: str
    # The gateway beside MediaMTX, e.g. http://10.0.0.5:8088.
    gateway_url: str = Field(pattern=r"^https?://")
    fps: float = Field(default=1.0, gt=0, le=10)
    alert_confidence: float = Field(default=0.6, ge=0.45, le=1)
    cooldown_s: float = Field(default=300.0, ge=10)
    frame_max_side: int = Field(default=640, ge=64, le=1920)
    frame_jpeg_quality: int = Field(default=80, ge=30, le=95)
    timeout_s: float = Field(default=10.0, gt=0, le=60)
    # A recorded video is played once (tests) or again and again (drills).
    loop: bool = False

    @field_validator("key")
    @classmethod
    def _hex_key(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if len(raw) != 64 or any(c not in "0123456789abcdef" for c in raw):
            raise ValueError("EDGE_KEY must be the 64 lower-case hex characters shown in the dashboard")
        return value


def sign(key: str, tower: str, at: str, label: str, confidence: str, hits: str, frames: str, sha: str) -> str:
    message = f"{tower}|{at}|{label}|{confidence}|{hits}|{frames}|{sha}".encode()
    return hmac.new(bytes.fromhex(key), message, hashlib.sha256).hexdigest()


def jpeg(frame: Frame, max_side: int, quality: int) -> bytes:
    image = Image.fromarray(frame)
    image.thumbnail((max_side, max_side), Image.Resampling.BILINEAR)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def event(
    settings: EdgeSettings, label: str, confidence: float, hits: int, frame: bytes, model: str, at: datetime
) -> dict[str, str]:
    stamp = at.isoformat(timespec="seconds")
    shown = f"{min(max(confidence, 0.0), 1.0):.2f}"
    sha = hashlib.sha256(frame).hexdigest() if frame else ""
    key = settings.key.get_secret_value()
    return {
        "tower": settings.tower,
        "at": stamp,
        "label": label,
        "confidence": shown,
        "hits": str(hits),
        "frames": str(FRAMES),
        "model": model[:80],
        "frame_jpeg_b64": base64.b64encode(frame).decode("ascii") if frame else "",
        "sig": sign(key, settings.tower, stamp, label, shown, str(hits), str(FRAMES), sha),
    }


@dataclass
class Confirmer:
    """The last FRAMES analysed frames; a label is confirmed when the newest frame and HITS of them reach the alert
    confidence, then rests for ``cooldown_s`` (the clock of the frames: video time for a recording)."""

    alert: float
    cooldown_s: float
    window: deque[dict[str, float]] = field(default_factory=lambda: deque(maxlen=FRAMES))
    last_sent: dict[str, float] = field(default_factory=dict)

    def add(self, detections: list[Detection], t: float) -> dict[str, tuple[float, int]]:
        best = {
            label: max((d.confidence for d in detections if d.label == label), default=0.0) for label in ALERT_LABELS
        }
        self.window.append(best)
        if len(self.window) < FRAMES:
            return {}
        out: dict[str, tuple[float, int]] = {}
        for label in ALERT_LABELS:
            hits = sum(1 for f in self.window if f[label] >= self.alert)
            if best[label] < self.alert or hits < HITS:
                continue
            if t - self.last_sent.get(label, -self.cooldown_s) < self.cooldown_s:
                continue
            self.last_sent[label] = t
            out[label] = (best[label], hits)
        return out


@contextlib.contextmanager
def frames_of(source: str, timeout_s: float) -> Iterator[Iterator[tuple[float, Callable[[], Frame]]]]:
    """(time in seconds, lazily decoded RGB frame) of a camera (RTSP over TCP) or a recorded video."""
    import av

    live = source.startswith(("rtsp://", "rtsps://"))
    options = {"rtsp_transport": "tcp", "max_delay": "500000"} if live else {}
    container = av.open(source, options=options, timeout=(timeout_s, timeout_s))
    try:
        stream = container.streams.video[0]
        stream.thread_count = 1
        started = time.monotonic()

        def frames() -> Iterator[tuple[float, Callable[[], Frame]]]:
            for frame in container.decode(stream):
                t = time.monotonic() - started if live or frame.time is None else float(frame.time)

                def convert(f: Any = frame) -> Frame:
                    return np.asarray(f.to_ndarray(format="rgb24"), dtype=np.uint8)

                yield t, convert

        yield frames()
    finally:
        container.close()


def watch(
    settings: EdgeSettings,
    frames: Iterator[tuple[float, Callable[[], Frame]]],
    detect: Detect,
    post: Post,
    model: str,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    """Analyse about ``fps`` frames a second and post the confirmed events. Returns how many were posted."""
    confirmer = Confirmer(settings.alert_confidence, settings.cooldown_s)
    every = 1.0 / settings.fps
    due = 0.0
    sent = 0
    for t, decode in frames:
        if t < due:
            continue
        due = t + every
        frame = decode()
        for label, (confidence, hits) in confirmer.add(detect(frame), t).items():
            picture = jpeg(frame, settings.frame_max_side, settings.frame_jpeg_quality)
            post(event(settings, label, confidence, hits, picture, model, now()))
            sent += 1
            log.info("edge.event", tower=settings.tower, label=label, confidence=round(confidence, 2), hits=hits)
    return sent


def gateway_post(settings: EdgeSettings) -> Post:
    def post(body: dict[str, str]) -> None:
        # The gateway queues on disk and answers 202; a refusal is logged by reason, never with the key.
        for attempt in range(5):
            try:
                r = httpx.post(f"{settings.gateway_url.rstrip('/')}/events", json=body, timeout=settings.timeout_s)
            except httpx.HTTPError as exc:
                log.warning("edge.gateway_unreachable", error=type(exc).__name__, attempt=attempt)
            else:
                if r.status_code == 202:
                    return
                log.warning("edge.gateway_refused", status=r.status_code, attempt=attempt)
                if r.status_code in (403, 413, 422):
                    return
            time.sleep(min(2.0**attempt, 30.0))

    return post


def main() -> int:
    # The edge computer serves no API: the vision service's own tokens are set to values it never uses.
    os.environ.setdefault("VISION_API_TOKEN", secrets.token_urlsafe(32))
    os.environ.setdefault("VISION_CALLBACK_TOKEN", secrets.token_urlsafe(32))
    from app.models import Detectors

    settings = EdgeSettings()
    detectors = Detectors()
    post = gateway_post(settings)
    while True:
        try:
            with frames_of(settings.source, settings.timeout_s) as frames:
                watch(settings, frames, lambda f: detectors.detect(f), post, detectors.name())
        except Exception as exc:  # the camera dropped: try again shortly
            log.warning("edge.source_error", error=type(exc).__name__)
        if not settings.loop and not settings.source.startswith(("rtsp://", "rtsps://")):
            return 0
        time.sleep(2.0)


if __name__ == "__main__":
    sys.exit(main())
