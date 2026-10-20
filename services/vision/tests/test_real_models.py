"""Checks against the real detectors (CI job "Vision · real models"): run with ``pytest -m models``.

Needs VISION_MODELS_DIR prepared by models/fetch_models.py. Images come from the pinned evaluation sample
(eval/samples.json, Open Images test split, CC BY 2.0), downloaded once into eval/cache and checked by SHA-256.
"""

import io
import json
import statistics
import time
from pathlib import Path

import av
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_settings
from app.models import Detectors
from app.streams import StreamManager, rtsp_frames
from eval.evaluate import fetch
from tests.conftest import AUTH

pytestmark = pytest.mark.models

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = json.loads((ROOT / "eval" / "samples.json").read_text())["samples"]
CACHE = ROOT / "eval" / "cache"
# Quality floor on a slice of the held-out sample (EVALUATION.md has the full numbers): a regression of the
# model or of the pre/post-processing fails CI.
MIN_FIRE_RECALL = 0.75
MAX_FIRE_FALSE_POSITIVE_RATE = 0.4


def image(sample: dict) -> bytes:
    CACHE.mkdir(exist_ok=True)
    return fetch(sample, CACHE)


def group(name: str, count: int) -> list[dict]:
    return [s for s in SAMPLES if s["group"] == name][:count]


@pytest.fixture(scope="module")
def detectors() -> Detectors:
    get_settings.cache_clear()
    found = Detectors()
    assert found.ready(), found.error
    return found


def test_health_and_model(client: TestClient) -> None:
    assert client.get("/healthz").json()["status"] == "ok"
    body = client.get("/v1/model", headers=AUTH).json()
    assert body["labels"] == ["fire", "smoke", "person"]
    assert body["license"] == "Apache-2.0"
    assert all(m["sha256"] for m in body["models"])


def test_fire_recall_and_false_positives(detectors: Detectors) -> None:
    from app.imaging import decode

    def fire_found(sample: dict) -> bool:
        detections = detectors.detect(decode(image(sample), "image/jpeg", 40_000_000))
        return any(d.label == "fire" and d.confidence >= 0.45 for d in detections)

    positives = group("fire", 40)
    negatives = group("hard_negative", 40) + group("person", 20)
    recall = sum(map(fire_found, positives)) / len(positives)
    false_positive_rate = sum(map(fire_found, negatives)) / len(negatives)
    print(f"\n  fire recall {recall:.2f} on {len(positives)}, false positive rate {false_positive_rate:.2f}")
    assert recall >= MIN_FIRE_RECALL
    assert false_positive_rate <= MAX_FIRE_FALSE_POSITIVE_RATE


def test_detect_endpoint_on_a_real_photo(client: TestClient) -> None:
    sample = group("fire", 1)[0]
    r = client.post("/v1/detect", files={"image": ("a.jpg", image(sample), "image/jpeg")}, headers=AUTH)
    assert r.status_code == 200, r.text
    body = r.json()
    print(f"\n  {sample['id']}: {body}")
    for detection in body["detections"]:
        for x1, y1, x2, y2, confidence in detection["boxes"]:
            assert 0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1 and confidence >= 0.45


def test_people_are_found(detectors: Detectors) -> None:
    from app.imaging import decode

    positives = group("person", 20)
    found = sum(
        any(d.label == "person" for d in detectors.detect(decode(image(s), "image/jpeg", 40_000_000)))
        for s in positives
    )
    assert found / len(positives) >= 0.7


def test_cpu_latency_per_720p_frame(detectors: Detectors) -> None:
    frame = np.asarray(Image.open(io.BytesIO(image(group("fire", 1)[0]))).convert("RGB").resize((1280, 720)))
    detectors.detect(frame)
    times = []
    for _ in range(10):
        started = time.perf_counter()
        detectors.detect(frame)
        times.append(time.perf_counter() - started)
    median = statistics.median(times)
    print(f"\n  720p frame, every model: median {median * 1000:.0f} ms")
    assert median < 1.0  # 1 frame/s per stream must hold on one worker


def test_stream_pipeline_with_real_decoding(tmp_path: Path, detectors: Detectors) -> None:
    """A real video file (MPEG-4, encoded here with PyAV) through the real decoder, detectors and callback code."""
    sample = group("fire", 1)[0]
    still = Image.open(io.BytesIO(image(sample))).convert("RGB").resize((640, 480))
    video = tmp_path / "fire.mp4"
    with av.open(str(video), mode="w") as container:
        stream = container.add_stream("mpeg4", rate=10)
        stream.width, stream.height, stream.pix_fmt = 640, 480, "yuv420p"
        for _ in range(30):  # 3 s
            for packet in stream.encode(av.VideoFrame.from_image(still)):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)

    settings = get_settings()
    settings.fps_idle, settings.fps_pending, settings.stream_gone_after_s = 1000.0, 1000.0, 0.5
    settings.max_watch_s = 5.0  # a file can be reopened after its end, unlike a stream whose publisher left
    received: list[dict] = []

    def api(request: httpx.Request) -> httpx.Response:
        received.append(json.loads(request.content))
        return httpx.Response(204)

    manager = StreamManager(detectors, rtsp_frames, httpx.MockTransport(api))
    manager.start("real", str(video), "http://api:8000/internal/vision/detections")
    deadline = time.monotonic() + 60
    while len(manager) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert len(manager) == 0
    print(f"\n  {len(received)} callbacks, first: {received[0]['detections'] if received else None}")
    assert received, "the fire frames produced no callback"
    assert any(d["label"] == "fire" for body in received for d in body["detections"])
    assert received[0]["frame_jpeg_b64"]
