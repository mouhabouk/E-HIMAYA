import base64
import io
import json
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import httpx
import numpy as np
import pytest
from PIL import Image

from app.config import get_settings
from app.models import Detectors
from app.processing import Detection
from app.schemas import DetectionCallback
from app.streams import SourceError, StreamManager, Watch, Watcher, with_credentials
from tests.conftest import fake_detector

FIRE = Detection("fire", 0.8, (0.1, 0.2, 0.4, 0.6))
PERSON = Detection("person", 0.9, (0.5, 0.5, 0.7, 0.9))
CALLBACK = "http://api:8000/internal/vision/detections"


class ScriptedDetectors(Detectors):
    """Returns the scripted detections frame after frame (then nothing)."""

    def __init__(self, script: list[list[Detection]]) -> None:
        super().__init__()
        self.script = list(script)
        self.analysed = 0
        self._models = [fake_detector(["fire", "smoke"], [], name="scripted")]

    def detect(self, image: np.ndarray, wait_s: float | None = None) -> list[Detection]:
        self.analysed += 1
        return self.script.pop(0) if self.script else []


class Recorder:
    def __init__(self, status: int = 204) -> None:
        self.requests: list[httpx.Request] = []
        self.status = status

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status)

    @property
    def bodies(self) -> list[dict[str, Any]]:
        return [json.loads(r.content) for r in self.requests]


def source(frames: int, delay: float = 0.005, fail_opens: int = 0) -> Callable[[str], Any]:
    """Fake RTSP source: the first ``fail_opens`` connections fail, the next one gives ``frames`` frames and ends
    (publisher gone), every later one fails like MediaMTX answering 404 for a path that is no longer published."""
    state = {"opens": 0, "urls": []}

    @contextmanager
    def open_(url: str) -> Iterator[Iterator[Callable[[], np.ndarray]]]:
        state["opens"] += 1
        state["urls"].append(url)
        if state["opens"] != fail_opens + 1:
            raise SourceError("connection_refused")

        def generate() -> Iterator[Callable[[], np.ndarray]]:
            for n in range(frames):
                if delay:
                    time.sleep(delay)
                frame = np.zeros((96, 128, 3), dtype=np.uint8)
                frame[..., 0] = n % 256
                yield lambda frame=frame: frame

        yield generate()

    open_.state = state  # type: ignore[attr-defined]
    return open_


def run_watcher(script: list[list[Detection]], frames: int, recorder: Recorder, **overrides: Any) -> tuple[Watch, str]:
    settings = get_settings()
    frame_source = overrides.pop("frame_source", None) or source(frames)
    for key, value in {"fps_idle": 1000.0, "fps_pending": 1000.0, "stream_gone_after_s": 5.0, **overrides}.items():
        setattr(settings, key, value)
    ended: list[str] = []
    watch = Watch(stream_id="s1", rtsp_url="rtsp://mediamtx:8554/live/s1", callback_url=CALLBACK)
    watcher = Watcher(
        watch,
        ScriptedDetectors(script),
        frame_source,
        settings,
        lambda _w, reason: ended.append(reason),
        httpx.MockTransport(recorder),
    )
    thread = threading.Thread(target=watcher.run)
    thread.start()
    thread.join(10)
    assert not thread.is_alive()
    return watch, ended[0]


def test_callback_payload_matches_the_contract() -> None:
    recorder = Recorder()
    run_watcher([[FIRE]], frames=1, recorder=recorder, stream_gone_after_s=0.01)
    [request] = recorder.requests
    assert request.url == CALLBACK
    assert request.headers["X-Vision-Token"] == get_settings().callback_token.get_secret_value()
    body = DetectionCallback.model_validate_json(request.content).model_dump()
    assert body["stream_id"] == "s1"
    assert body["model"] == "scripted@1.0.0"
    assert body["detections"] == [
        {"label": "fire", "confidence": 0.8, "boxes": [[0.1, 0.2, 0.4, 0.6, 0.8]]},
    ]
    assert body["at"].endswith("+00:00")
    # A downscaled JPEG of the frame is attached when something is detected.
    frame = Image.open(io.BytesIO(base64.b64decode(body["frame_jpeg_b64"])))
    assert frame.format == "JPEG"
    assert frame.size == (128, 96)


def test_frame_is_downscaled_to_the_configured_side() -> None:
    recorder = Recorder()
    run_watcher([[FIRE]], frames=1, recorder=recorder, stream_gone_after_s=0.01, frame_max_side=64)
    frame = Image.open(io.BytesIO(base64.b64decode(recorder.bodies[0]["frame_jpeg_b64"])))
    assert frame.size == (64, 48)


def test_nothing_is_sent_while_nothing_is_seen() -> None:
    recorder = Recorder()
    watch, reason = run_watcher([], frames=5, recorder=recorder, stream_gone_after_s=0.01)
    assert watch.frames == 5
    assert recorder.requests == []
    assert reason == "gone"


def test_pending_streams_report_every_frame_until_clean() -> None:
    """After a fire, every analysed frame is posted (empty ones too) until 5 clean frames in a row."""
    recorder = Recorder()
    script = [[], [FIRE], [], [FIRE], [], [], [], [], [], [], []]
    watch, _ = run_watcher(script, frames=len(script), recorder=recorder, stream_gone_after_s=0.01)
    labels = [[d["label"] for d in body["detections"]] for body in recorder.bodies]
    # frame 0 clean (not sent), 1 fire, 2 clean, 3 fire, 4-8 clean (5 → pending cleared), 9-10 not sent.
    assert labels == [["fire"], [], ["fire"], [], [], [], [], []]
    assert [b["frame_jpeg_b64"] is None for b in recorder.bodies] == [False, True, False, True, True, True, True, True]
    assert watch.pending is False


def test_pending_doubles_the_frame_rate() -> None:
    """1 fps idle, 2 fps while pending: count analysed frames over a fixed number of source frames."""
    recorder = Recorder()
    script = [[FIRE]] + [[]] * 100
    idle_watch, _ = run_watcher(
        [],
        frames=40,
        recorder=recorder,
        fps_idle=20.0,
        fps_pending=40.0,
        frame_source=source(40, delay=0.01),
        stream_gone_after_s=0.01,
    )
    pending_watch, _ = run_watcher(
        script,
        frames=40,
        recorder=recorder,
        fps_idle=20.0,
        fps_pending=40.0,
        frame_source=source(40, delay=0.01),
        pending_clear_frames=50,
        stream_gone_after_s=0.01,
    )
    # 40 frames at ~100/s = ~0.4 s: ~8 analysed at 20/s, ~16 at 40/s (scheduling noise allowed).
    assert 4 <= idle_watch.frames <= 12
    assert pending_watch.frames >= idle_watch.frames * 1.5


def test_person_only_frames_are_rate_limited() -> None:
    recorder = Recorder()
    run_watcher([[PERSON]] * 6, frames=6, recorder=recorder, stream_gone_after_s=0.01)
    assert len(recorder.requests) == 1
    assert recorder.bodies[0]["detections"][0]["label"] == "person"


def test_reconnects_with_backoff_then_gives_up() -> None:
    frame_source = source(frames=2, fail_opens=2)
    started = time.monotonic()
    watch, reason = run_watcher(
        [],
        frames=2,
        recorder=Recorder(),
        frame_source=frame_source,
        stream_gone_after_s=1.5,
        reconnect_max_delay_s=1.0,
    )
    elapsed = time.monotonic() - started
    # Two failed opens (1 s apart), one connection with 2 frames then EOF, failed reopens: gone 1.5 s after the
    # last frame.
    assert frame_source.state["opens"] >= 4  # type: ignore[attr-defined]
    assert watch.frames == 2
    assert reason == "gone"
    assert elapsed >= 3.0


def test_rtsp_credentials_are_injected() -> None:
    settings = get_settings()
    settings.rtsp_password = type(settings.rtsp_password)("p@ss/w:rd")
    frame_source = source(frames=1)
    run_watcher([], frames=1, recorder=Recorder(), frame_source=frame_source, stream_gone_after_s=0.01)
    assert frame_source.state["urls"][0] == "rtsp://vision:p%40ss%2Fw%3Ard@mediamtx:8554/live/s1"  # type: ignore[attr-defined]
    assert with_credentials("rtsp://h/x", "u", "") == "rtsp://h/x"


def test_api_rejection_stops_the_watch() -> None:
    recorder = Recorder(status=404)
    watch, reason = run_watcher([[FIRE]] * 10, frames=10, recorder=recorder)
    assert reason == "rejected_by_api"
    assert watch.frames == 1


def test_callback_failures_do_not_stop_the_watch() -> None:
    def broken(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("api down")

    settings = get_settings()
    settings.fps_idle = settings.fps_pending = 1000.0
    settings.stream_gone_after_s = 0.01
    ended: list[str] = []
    watch = Watch(stream_id="s1", rtsp_url="rtsp://mediamtx:8554/live/s1", callback_url=CALLBACK)
    watcher = Watcher(
        watch,
        ScriptedDetectors([[FIRE]] * 3),
        source(3),
        settings,
        lambda _w, r: ended.append(r),
        httpx.MockTransport(broken),
    )
    watcher.run()
    assert watch.frames == 3
    assert ended == ["gone"]


def test_max_watch_duration() -> None:
    _watch, reason = run_watcher(
        [], frames=10_000, recorder=Recorder(), max_watch_s=0.2, frame_source=source(10_000, delay=0.001)
    )
    assert reason == "max_duration"


def test_manager_frees_the_slot_when_a_stream_ends() -> None:
    settings = get_settings()
    settings.fps_idle = 1000.0
    settings.stream_gone_after_s = 0.01
    settings.max_streams = 1
    manager = StreamManager(ScriptedDetectors([]), source(frames=3), httpx.MockTransport(Recorder()))
    assert manager.start("a", "rtsp://mediamtx:8554/live/a", CALLBACK) == "started"
    deadline = time.monotonic() + 5
    while len(manager) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert len(manager) == 0
    assert manager.start("b", "rtsp://mediamtx:8554/live/b", CALLBACK) == "started"
    manager.shutdown(2)


def test_restart_with_another_url_replaces_the_watch() -> None:
    settings = get_settings()
    settings.fps_idle = 10.0
    manager = StreamManager(ScriptedDetectors([]), source(frames=10_000, delay=0.01), httpx.MockTransport(Recorder()))
    manager.start("a", "rtsp://mediamtx:8554/live/a", CALLBACK)
    first = manager._watches["a"]
    assert manager.start("a", "rtsp://mediamtx:8554/live/a2", CALLBACK) == "started"
    assert first.stop.is_set()
    assert manager._watches["a"].rtsp_url.endswith("/a2")
    manager.shutdown(2)
    assert len(manager) == 0


@pytest.mark.parametrize("error", [ValueError("boom")])
def test_a_crashing_watcher_reports_error_and_frees_its_slot(error: Exception) -> None:
    class Exploding(ScriptedDetectors):
        def detect(self, image: np.ndarray, wait_s: float | None = None) -> list[Detection]:
            raise error

    get_settings().fps_idle = 1000.0
    manager = StreamManager(Exploding([]), source(frames=3), httpx.MockTransport(Recorder()))
    manager.start("a", "rtsp://mediamtx:8554/live/a", CALLBACK)
    deadline = time.monotonic() + 5
    while len(manager) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert len(manager) == 0
