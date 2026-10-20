import io
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

os.environ.setdefault("VISION_API_TOKEN", "test-api-token-test-api-token-0001")
os.environ.setdefault("VISION_CALLBACK_TOKEN", "test-callback-token-test-callback-01")
os.environ.setdefault("VISION_MODELS_DIR", "/nonexistent-models")

from app.config import get_settings
from app.models import Manifest, OnnxDetector
from app.processing import YOLOX_STRIDES

AUTH = {"Authorization": f"Bearer {os.environ['VISION_API_TOKEN']}"}
SIZE = (64, 64)


def cells(size: tuple[int, int] = SIZE) -> list[tuple[int, int, int]]:
    """(stride, row, col) of every YOLOX prediction, in output order."""
    return [(s, r, c) for s in YOLOX_STRIDES for r in range(size[0] // s) for c in range(size[1] // s)]


class FakeSession:
    """Stands in for onnxruntime.InferenceSession: returns a raw YOLOX output with planted predictions.

    ``plant`` = [(prediction index, class index, score, (cx, cy, w, h) in input pixels)].
    """

    def __init__(self, num_classes: int, plant: list[tuple[int, int, float, tuple[float, float, float, float]]]):
        self.num_classes = num_classes
        self.plant = plant
        self.calls = 0

    def get_inputs(self) -> list[Any]:
        class Input:
            name = "images"
            shape = (1, 3, *SIZE)

        return [Input()]

    def run(self, _outputs: Any, feeds: dict[str, np.ndarray]) -> list[np.ndarray]:
        assert feeds["images"].shape == (1, 3, *SIZE)
        self.calls += 1
        grid = cells()
        raw = np.zeros((len(grid), 5 + self.num_classes), dtype=np.float32)
        raw[:, 2:4] = -5  # tiny boxes everywhere, objectness 0
        for index, cls, score, (cx, cy, w, h) in self.plant:
            stride, row, col = grid[index]
            raw[index, 0], raw[index, 1] = cx / stride - col, cy / stride - row
            raw[index, 2], raw[index, 3] = np.log(w / stride), np.log(h / stride)
            raw[index, 4] = 1.0
            raw[index, 5 + cls] = score
        return [raw[np.newaxis]]


def fake_detector(
    labels: list[str | None], plant: list[Any], name: str = "fake", score_power: dict[str, float] | None = None
) -> OnnxDetector:
    manifest = Manifest(
        directory=Path("/fake"),
        name=name,
        version="1.0.0",
        license="Apache-2.0",
        format="yolox",
        input_size=SIZE,
        labels=labels,
        sha256=None,
        score_power=score_power or {},
        data={"source": "tests"},
    )
    return OnnxDetector(manifest, FakeSession(len(labels), plant))


def jpeg(width: int = 64, height: int = 48, color: tuple[int, int, int] = (200, 80, 20)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def fresh_settings() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def fire_detector() -> OnnxDetector:
    # A 64 x 64 input: one fire box in the centre (cell 0 of stride 32 covers it).
    index = cells().index((32, 1, 1))
    return fake_detector(["fire", "smoke"], [(index, 0, 0.9, (32.0, 32.0, 20.0, 16.0))], name="fake-fire")


@pytest.fixture
def model_client(client: TestClient, fire_detector: OnnxDetector) -> TestClient:
    detectors = client.app.state.detectors  # type: ignore[attr-defined]
    detectors._models = [fire_detector]
    return client
