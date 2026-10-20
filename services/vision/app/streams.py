"""Live stream watching (contract phase 6 §5): read an RTSP path of MediaMTX, analyse 1 frame/s (2 frames/s while a
fire or smoke detection awaits confirmation) and post the detections to the API.

One thread per watched stream (at most ``VISION_MAX_STREAMS``). Decoding is single-threaded per stream and the
inference itself goes through the shared, bounded worker pool of :mod:`app.models`, so CPU and memory stay bounded
whatever the number of PUTs: only the latest decoded frame is kept, and only when it is due for analysis.

The API decides what a detection means (3 of the last 5 analysed frames ≥ VISION_ALERT_CONFIDENCE = confirmed).
To let it count, every analysed frame is posted while a stream is "pending" — including frames where nothing was
found — and a stream leaves "pending" after ``VISION_PENDING_CLEAR_FRAMES`` clean frames in a row.
"""

import contextlib
import functools
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol
from urllib.parse import quote, urlsplit, urlunsplit

import httpx
import numpy as np
import structlog
from numpy.typing import NDArray

from app import imaging, processing
from app.config import Settings, get_settings
from app.metrics import CALLBACKS, DETECTIONS, FRAMES, RECONNECTS, STREAM_ENDS, STREAMS
from app.models import Detectors, ModelUnavailable
from app.processing import Detection

log = structlog.get_logger()

ALERT_LABELS = frozenset({"fire", "smoke"})
# Frames with only people in them are reported at most this often (a citizen filming is always in the picture).
PERSON_ONLY_INTERVAL_S = 10.0
# Largest frame side kept after decoding (bounded memory; the detectors work at 416-640 px anyway).
DECODE_MAX_SIDE = 1280

Frame = NDArray[np.uint8]
# A decoded frame, converted to RGB only when it is due for analysis (most frames of a 30 fps stream are not).
LazyFrame = Callable[[], Frame]
EndReason = Literal["stopped", "gone", "max_duration", "rejected_by_api", "error", "shutdown"]


class SourceError(Exception):
    """The stream could not be opened or broke while reading (retryable)."""


class FrameSource(Protocol):
    def __call__(self, url: str) -> AbstractContextManager[Iterator[LazyFrame]]: ...


@contextlib.contextmanager
def rtsp_frames(url: str) -> Iterator[Iterator[LazyFrame]]:
    """Decoded RGB frames of an RTSP stream, with PyAV (FFmpeg). TCP transport, bounded open/read timeouts."""
    import av

    settings = get_settings()
    try:
        container = av.open(
            url,
            options={"rtsp_transport": "tcp", "max_delay": "500000"},
            timeout=(settings.rtsp_timeout_s, settings.rtsp_timeout_s),
        )
    except (av.FFmpegError, OSError) as exc:
        raise SourceError(type(exc).__name__) from exc
    try:
        if not container.streams.video:
            raise SourceError("no_video_track")
        stream = container.streams.video[0]
        stream.thread_count = 1  # bounded CPU: one decoding thread per stream

        def convert(frame: Any) -> Frame:
            scale = min(1.0, DECODE_MAX_SIDE / max(frame.width, frame.height, 1))
            width = max(2, int(frame.width * scale) // 2 * 2)
            height = max(2, int(frame.height * scale) // 2 * 2)
            return np.asarray(frame.to_ndarray(format="rgb24", width=width, height=height), dtype=np.uint8)

        def frames() -> Iterator[LazyFrame]:
            try:
                for frame in container.decode(stream):
                    yield functools.partial(convert, frame)
            except (av.FFmpegError, OSError) as exc:
                raise SourceError(type(exc).__name__) from exc

        yield frames()
    finally:
        container.close()


def with_credentials(url: str, user: str, password: str) -> str:
    """rtsp://host/path → rtsp://user:password@host/path (MediaMTX read credentials of the vision service)."""
    if not password:
        return url
    parts = urlsplit(url)
    netloc = f"{quote(user, safe='')}:{quote(password, safe='')}@{parts.hostname}"
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, ""))


@dataclass
class Watch:
    stream_id: str
    rtsp_url: str
    callback_url: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    frames: int = 0
    callbacks: int = 0
    pending: bool = False
    connected: bool = False
    stop: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None

    def summary(self) -> dict[str, Any]:
        return {
            "stream_id": self.stream_id,
            "started_at": self.started_at.isoformat(),
            "connected": self.connected,
            "pending": self.pending,
            "frames_analysed": self.frames,
            "callbacks": self.callbacks,
        }


class Watcher:
    """Body of one stream thread."""

    def __init__(
        self,
        watch: Watch,
        detectors: Detectors,
        source: FrameSource,
        settings: Settings,
        on_exit: Callable[[Watch, EndReason], None],
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.watch = watch
        self.detectors = detectors
        self.source = source
        self.settings = settings
        self.on_exit = on_exit
        self.transport = transport
        self._clean_in_a_row = 0
        self._last_person_only = 0.0

    def run(self) -> None:
        reason: EndReason = "error"
        client = httpx.Client(
            timeout=self.settings.callback_timeout_s, follow_redirects=False, transport=self.transport
        )
        try:
            reason = self._loop(client)
        except Exception:  # never let a stream thread die silently
            log.exception("vision.stream_crashed", stream_id=self.watch.stream_id)
        finally:
            client.close()
            self.watch.connected = False
            self.on_exit(self.watch, reason)

    def _loop(self, client: httpx.Client) -> EndReason:
        settings, watch = self.settings, self.watch
        started = last_frame = time.monotonic()
        delay = 1.0
        url = with_credentials(watch.rtsp_url, settings.rtsp_user, settings.rtsp_password.get_secret_value())
        while not watch.stop.is_set():
            try:
                with self.source(url) as frames:
                    due = 0.0
                    for frame in frames:
                        now = time.monotonic()
                        last_frame, delay = now, 1.0
                        watch.connected = True
                        if watch.stop.is_set():
                            return "stopped"
                        if now - started > settings.max_watch_s:
                            return "max_duration"
                        if now < due:
                            continue  # decoded but not analysed (1 or 2 frames per second only)
                        if self._analyse(frame(), client) == "rejected":
                            return "rejected_by_api"
                        fps = settings.fps_pending if watch.pending else settings.fps_idle
                        due = now + 1.0 / fps
                log.info("vision.stream_eof", stream_id=watch.stream_id)
            except SourceError as exc:
                log.info("vision.stream_unavailable", stream_id=watch.stream_id, reason=str(exc))
            except ModelUnavailable:
                log.warning("vision.stream_model_unavailable", stream_id=watch.stream_id)
            watch.connected = False
            if watch.stop.is_set():
                return "stopped"
            if time.monotonic() - last_frame > settings.stream_gone_after_s:
                return "gone"  # the publisher left (MediaMTX answers 404) or the path never came up
            if time.monotonic() - started > settings.max_watch_s:
                return "max_duration"
            RECONNECTS.inc()
            watch.stop.wait(delay)
            delay = min(delay * 2, settings.reconnect_max_delay_s)
        return "stopped"

    def _analyse(self, frame: Frame, client: httpx.Client) -> str:
        watch = self.watch
        was_pending = watch.pending
        detections = self.detectors.detect(frame)
        watch.frames += 1
        FRAMES.labels(source="stream").inc()
        for label in {d.label for d in detections}:
            DETECTIONS.labels(label=label).inc()

        alert = any(d.label in ALERT_LABELS for d in detections)
        if alert:
            watch.pending, self._clean_in_a_row = True, 0
        elif watch.pending:
            self._clean_in_a_row += 1
            if self._clean_in_a_row >= self.settings.pending_clear_frames:
                watch.pending = False

        now = time.monotonic()
        if not (alert or was_pending):
            if not detections or now - self._last_person_only < PERSON_ONLY_INTERVAL_S:
                return "skipped"
            self._last_person_only = now
        return self._post(client, frame, detections)

    def _post(self, client: httpx.Client, frame: Frame, detections: list[Detection]) -> str:
        settings = self.settings
        payload = {
            "stream_id": self.watch.stream_id,
            "at": datetime.now(UTC).isoformat(),
            "model": self.detectors.name(),
            "detections": processing.group(detections),
            "frame_jpeg_b64": imaging.jpeg_b64(frame, settings.frame_max_side, settings.frame_jpeg_quality)
            if detections
            else None,
        }
        try:
            response = client.post(
                self.watch.callback_url,
                json=payload,
                headers={"X-Vision-Token": settings.callback_token.get_secret_value()},
            )
        except httpx.HTTPError as exc:
            CALLBACKS.labels(outcome="error").inc()
            log.warning("vision.callback_failed", stream_id=self.watch.stream_id, error=type(exc).__name__)
            return "failed"
        self.watch.callbacks += 1
        if response.status_code in (404, 409, 410):
            # The API no longer knows this stream as live: stop spending CPU on it.
            CALLBACKS.labels(outcome="rejected").inc()
            log.info("vision.callback_rejected", stream_id=self.watch.stream_id, status=response.status_code)
            return "rejected"
        outcome = "ok" if response.is_success else "error"
        CALLBACKS.labels(outcome=outcome).inc()
        if not response.is_success:
            log.warning("vision.callback_status", stream_id=self.watch.stream_id, status=response.status_code)
        return outcome


class TooManyStreams(Exception):
    pass


class StreamManager:
    def __init__(
        self,
        detectors: Detectors,
        source: FrameSource = rtsp_frames,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.detectors = detectors
        self.source = source
        self.transport = transport  # tests: httpx.MockTransport
        self._watches: dict[str, Watch] = {}
        self._lock = threading.Lock()
        self._closed = False

    def __len__(self) -> int:
        return len(self._watches)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [w.summary() for w in self._watches.values()]

    def start(self, stream_id: str, rtsp_url: str, callback_url: str) -> Literal["started", "updated"]:
        settings = get_settings()
        with self._lock:
            if self._closed:
                raise TooManyStreams
            current = self._watches.get(stream_id)
            if current is not None and current.rtsp_url == rtsp_url and not current.stop.is_set():
                current.callback_url = callback_url  # idempotent PUT
                return "updated"
            if current is not None:
                current.stop.set()
                del self._watches[stream_id]
            if len(self._watches) >= settings.max_streams:
                raise TooManyStreams
            watch = Watch(stream_id=stream_id, rtsp_url=rtsp_url, callback_url=callback_url)
            watcher = Watcher(watch, self.detectors, self.source, settings, self._ended, self.transport)
            watch.thread = threading.Thread(target=watcher.run, name=f"stream-{stream_id[:8]}", daemon=True)
            self._watches[stream_id] = watch
            STREAMS.set(len(self._watches))
            watch.thread.start()
        log.info("vision.stream_watch", stream_id=stream_id)
        return "started"

    def stop(self, stream_id: str) -> bool:
        with self._lock:
            watch = self._watches.pop(stream_id, None)
            STREAMS.set(len(self._watches))
        if watch is None:
            return False
        watch.stop.set()
        return True

    def _ended(self, watch: Watch, reason: EndReason) -> None:
        with self._lock:
            if self._watches.get(watch.stream_id) is watch:
                del self._watches[watch.stream_id]
            STREAMS.set(len(self._watches))
        if self._closed and reason == "stopped":
            reason = "shutdown"
        STREAM_ENDS.labels(reason=reason).inc()
        log.info("vision.stream_end", stream_id=watch.stream_id, reason=reason, frames=watch.frames)

    def shutdown(self, timeout_s: float = 10.0) -> None:
        """Graceful stop: every watcher is asked to stop and joined (bounded by the RTSP read timeout)."""
        with self._lock:
            self._closed = True
            watches = list(self._watches.values())
        for watch in watches:
            watch.stop.set()
        deadline = time.monotonic() + timeout_s
        for watch in watches:
            if watch.thread is not None:
                watch.thread.join(max(0.0, deadline - time.monotonic()))
