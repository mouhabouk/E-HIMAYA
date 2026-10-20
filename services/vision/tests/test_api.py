import io
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_settings
from tests.conftest import AUTH, jpeg

STREAM = {"rtsp_url": "rtsp://mediamtx:8554/live/abc", "callback_url": "http://api:8000/internal/vision/detections"}
PROTECTED = [
    ("GET", "/v1/model"),
    ("POST", "/v1/detect"),
    ("PUT", "/v1/streams/abc"),
    ("DELETE", "/v1/streams/abc"),
    ("GET", "/v1/streams"),
    ("GET", "/metrics"),
]


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), (0, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_health_is_public_and_degraded_without_models(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded"
    assert body["model"] is None
    assert "manifest.json" in body["detail"]
    assert body["max_streams"] == 8


def test_health_ok_with_models(model_client: TestClient) -> None:
    body = model_client.get("/healthz").json()
    assert body["status"] == "ok"
    assert body["model"] == "fake-fire@1.0.0"


@pytest.mark.parametrize(("method", "path"), PROTECTED)
@pytest.mark.parametrize("header", [None, "Bearer wrong-token", "Basic dGVzdA=="])
def test_every_route_but_health_needs_the_token(client: TestClient, method: str, path: str, header: str | None) -> None:
    headers = {"Authorization": header} if header else {}
    r = client.request(method, path, headers=headers)
    assert r.status_code == 401
    assert r.json() == {"detail": "invalid_token"}


def test_model_and_detect_are_503_without_models(client: TestClient) -> None:
    r = client.get("/v1/model", headers=AUTH)
    assert r.status_code == 503
    assert r.json() == {"detail": "model_unavailable"}
    assert r.headers["retry-after"] == "30"
    r = client.post("/v1/detect", files={"image": ("a.jpg", jpeg(), "image/jpeg")}, headers=AUTH)
    assert r.status_code == 503
    r = client.put("/v1/streams/abc", json=STREAM, headers=AUTH)
    assert r.status_code == 503


def test_model_describes_labels_and_licences(model_client: TestClient) -> None:
    body = model_client.get("/v1/model", headers=AUTH).json()
    assert body["name"] == "fake-fire@1.0.0"
    assert body["license"] == "Apache-2.0"
    assert body["labels"] == ["fire", "smoke"]
    assert body["models"][0]["source"] == "tests"


def test_detect_returns_normalised_boxes(model_client: TestClient) -> None:
    r = model_client.post("/v1/detect", files={"image": ("a.jpg", jpeg(64, 48), "image/jpeg")}, headers=AUTH)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["model"] == "fake-fire@1.0.0"
    [fire] = body["detections"]
    assert fire["label"] == "fire"
    assert fire["confidence"] == pytest.approx(0.9)
    [[x1, y1, x2, y2, conf]] = fire["boxes"]
    assert (x1, y1, x2, y2) == pytest.approx((22 / 64, 24 / 48, 42 / 64, 40 / 48), abs=1e-3)
    assert conf == pytest.approx(0.9)
    metrics = model_client.get("/metrics", headers=AUTH).text
    assert 'vision_detections_total{label="fire"}' in metrics


def test_detect_accepts_png_and_octet_stream(model_client: TestClient) -> None:
    r = model_client.post("/v1/detect", files={"image": ("a.png", png(), "image/png")}, headers=AUTH)
    assert r.status_code == 200
    r = model_client.post("/v1/detect", files={"image": ("a", jpeg(), "application/octet-stream")}, headers=AUTH)
    assert r.status_code == 200


@pytest.mark.parametrize(
    ("payload", "content_type", "status", "detail"),
    [
        (b"GIF89a" + b"\0" * 100, "image/gif", 415, "unsupported_media_type"),
        (b"%PDF-1.7 not an image", "image/jpeg", 415, "unsupported_media_type"),
        (b"RIFF\0\0\0\0WAVEfmt ", "image/webp", 415, "unsupported_media_type"),
        (png(), "image/jpeg", 415, "content_type_mismatch"),
        (jpeg()[:40], "image/jpeg", 422, "image_undecodable"),
        (jpeg(8, 8), "image/jpeg", 422, "image_too_small"),
        (b"", "image/jpeg", 422, "image_empty"),
    ],
)
def test_detect_rejects_bad_uploads(
    model_client: TestClient, payload: bytes, content_type: str, status: int, detail: str
) -> None:
    r = model_client.post("/v1/detect", files={"image": ("x", payload, content_type)}, headers=AUTH)
    assert r.status_code == status, r.text
    assert r.json() == {"detail": detail}


def test_detect_limits_bytes_and_pixels(model_client: TestClient) -> None:
    settings = get_settings()
    settings.max_image_bytes = 2000
    big = jpeg(400, 400) + b"\0" * 3000
    r = model_client.post("/v1/detect", files={"image": ("a.jpg", big, "image/jpeg")}, headers=AUTH)
    assert r.status_code == 413
    assert r.json() == {"detail": "image_too_large"}
    settings.max_image_bytes = 10_000_000
    settings.max_image_pixels = 100 * 100
    r = model_client.post("/v1/detect", files={"image": ("a.jpg", jpeg(200, 100), "image/jpeg")}, headers=AUTH)
    assert r.status_code == 413


def test_detect_requires_the_image_field(model_client: TestClient) -> None:
    r = model_client.post("/v1/detect", files={"file": ("a.jpg", jpeg(), "image/jpeg")}, headers=AUTH)
    assert r.status_code == 422


@contextmanager
def endless_source(url: str) -> Iterator[Iterator[Callable[[], np.ndarray]]]:
    def frames() -> Iterator[Callable[[], np.ndarray]]:
        import time

        while True:
            time.sleep(0.05)
            yield lambda: np.zeros((48, 64, 3), dtype=np.uint8)

    yield frames()


@pytest.fixture
def stream_client(model_client: TestClient) -> TestClient:
    manager = model_client.app.state.streams  # type: ignore[attr-defined]
    manager.source = endless_source
    manager.transport = httpx.MockTransport(lambda _request: httpx.Response(204))
    return model_client


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ({**STREAM, "rtsp_url": "rtsp://evil:8554/live/abc"}, "rtsp_url_not_allowed"),
        ({**STREAM, "rtsp_url": "rtsp://mediamtx:8554/live/abc@evil"}, "rtsp_url_not_allowed"),
        ({**STREAM, "rtsp_url": "file:///etc/passwd"}, "rtsp_url_not_allowed"),
        ({**STREAM, "callback_url": "http://169.254.169.254/latest"}, "callback_url_not_allowed"),
    ],
)
def test_stream_urls_are_restricted(stream_client: TestClient, body: dict[str, str], detail: str) -> None:
    r = stream_client.put("/v1/streams/abc", json=body, headers=AUTH)
    assert r.status_code == 422
    assert r.json() == {"detail": detail}


def test_stream_id_is_validated(stream_client: TestClient) -> None:
    r = stream_client.put("/v1/streams/a.b", json=STREAM, headers=AUTH)
    assert r.status_code == 422


def test_streams_are_bounded_and_idempotent(stream_client: TestClient) -> None:
    get_settings().max_streams = 2
    first = stream_client.put("/v1/streams/s1", json=STREAM, headers=AUTH)
    assert first.status_code == 202
    assert first.json() == {"stream_id": "s1", "state": "started", "streams": 1, "max_streams": 2}
    again = stream_client.put("/v1/streams/s1", json=STREAM, headers=AUTH)
    assert again.status_code == 202
    assert again.json()["state"] == "updated"
    assert stream_client.put("/v1/streams/s2", json=STREAM, headers=AUTH).status_code == 202
    full = stream_client.put("/v1/streams/s3", json=STREAM, headers=AUTH)
    assert full.status_code == 429
    assert full.json() == {"detail": "too_many_streams"}
    assert full.headers["retry-after"] == "30"
    listed = stream_client.get("/v1/streams", headers=AUTH).json()
    assert sorted(s["stream_id"] for s in listed["streams"]) == ["s1", "s2"]

    assert stream_client.delete("/v1/streams/s1", headers=AUTH).status_code == 204
    assert stream_client.delete("/v1/streams/s1", headers=AUTH).status_code == 204  # idempotent
    assert stream_client.put("/v1/streams/s3", json=STREAM, headers=AUTH).status_code == 202
    assert "vision_streams_rejected_total 1.0" in stream_client.get("/metrics", headers=AUTH).text


def test_shutdown_stops_every_watcher(stream_client: TestClient) -> None:
    stream_client.put("/v1/streams/s1", json=STREAM, headers=AUTH)
    manager = stream_client.app.state.streams  # type: ignore[attr-defined]
    watch = manager._watches["s1"]
    manager.shutdown(timeout_s=5)
    assert watch.thread is not None and not watch.thread.is_alive()
    assert len(manager) == 0
