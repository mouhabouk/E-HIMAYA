import json
from pathlib import Path

import numpy as np
import pytest

from app import processing
from app.processing import Detection, Letterbox
from tests.conftest import SIZE, cells, fake_detector


def test_letterbox_keeps_aspect_ratio_and_pads_right_and_bottom() -> None:
    image = np.zeros((100, 200, 3), dtype=np.uint8)
    image[:, :, 0] = 255  # pure red (RGB)
    boxed = processing.letterbox(image, (64, 64))
    assert boxed.tensor.shape == (1, 3, 64, 64)
    assert boxed.tensor.dtype == np.float32
    assert boxed.ratio == pytest.approx(0.32)
    assert (boxed.width, boxed.height) == (200, 100)
    # 200 x 100 → 64 x 32: rows 0..31 hold the image, the rest is padding (114).
    assert boxed.tensor[0, 2, 10, 10] == 255  # BGR: red is the last channel
    assert boxed.tensor[0, 0, 10, 10] == 0
    assert np.all(boxed.tensor[0, :, 40:, :] == processing.PAD_VALUE)


def test_letterbox_rejects_non_rgb() -> None:
    with pytest.raises(ValueError):
        processing.letterbox(np.zeros((10, 10), dtype=np.uint8), (64, 64))


def test_yolox_decode_places_boxes_on_the_grid() -> None:
    grid = cells()
    assert len(grid) == 8 * 8 + 4 * 4 + 2 * 2
    raw = np.zeros((len(grid), 7), dtype=np.float32)
    index = grid.index((16, 2, 3))  # stride 16, row 2, col 3 → cell origin (48, 32)
    raw[index] = [0.5, 0.25, np.log(2.0), np.log(1.0), 0.8, 0.5, 0.1]
    boxes, scores = processing.yolox_decode(raw, SIZE)
    cx, cy, w, h = (3 + 0.5) * 16, (2 + 0.25) * 16, 2.0 * 16, 1.0 * 16
    assert boxes[index] == pytest.approx([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2])
    assert scores[index] == pytest.approx([0.4, 0.08])  # objectness x class


def test_yolox_decode_checks_the_number_of_predictions() -> None:
    with pytest.raises(ValueError):
        processing.yolox_decode(np.zeros((10, 7), dtype=np.float32), SIZE)


def test_nms_keeps_the_best_of_overlapping_boxes() -> None:
    boxes = np.array(
        [[0, 0, 10, 10], [1, 1, 10, 10], [20, 20, 30, 30], [0, 0, 10, 10.5]],
        dtype=np.float32,
    )
    scores = np.array([0.6, 0.9, 0.5, 0.3], dtype=np.float32)
    assert processing.nms(boxes, scores, 0.5) == [1, 2]
    assert processing.nms(boxes, scores, 0.96) == [1, 0, 2, 3]
    assert processing.nms(np.zeros((0, 4), dtype=np.float32), np.zeros(0, dtype=np.float32), 0.5) == []


def test_normalise_undoes_the_letterbox_and_clips() -> None:
    boxes = np.array([[16, 8, 48, 24], [-5, -5, 70, 70]], dtype=np.float32)
    out = processing.normalise(boxes, ratio=0.32, width=200, height=100)
    assert out[0] == pytest.approx([0.25, 0.25, 0.75, 0.75])
    assert out[1] == pytest.approx([0, 0, 1, 1])


def test_select_thresholds_per_class_and_ignores_unmapped_classes() -> None:
    boxed = Letterbox(np.zeros((1, 3, 64, 64), np.float32), ratio=1.0, width=64, height=64)
    boxes = np.array([[0, 0, 32, 32], [2, 2, 32, 32], [40, 40, 60, 60], [0, 0, 64, 64]], dtype=np.float32)
    scores = np.array([[0.9, 0.0, 0.99], [0.8, 0.0, 0.0], [0.3, 0.7, 0.0], [0.0, 0.0, 0.0]], dtype=np.float32)
    found = processing.select(
        boxes,
        scores,
        ["fire", "smoke", None],
        letterboxed=boxed,
        min_confidence=0.45,
        iou_threshold=0.5,
        max_per_label=5,
    )
    assert found == [
        Detection("fire", 0.9, (0.0, 0.0, 0.5, 0.5)),
        Detection("smoke", 0.7, (0.625, 0.625, 0.9375, 0.9375)),
    ]


def test_group_matches_the_contract_shape() -> None:
    grouped = processing.group(
        [
            Detection("smoke", 0.5, (0.1, 0.1, 0.2, 0.2)),
            Detection("fire", 0.6, (0.0, 0.0, 0.5, 0.5)),
            Detection("fire", 0.81, (0.1, 0.2, 0.4, 0.6)),
        ]
    )
    assert grouped == [
        {"label": "fire", "confidence": 0.81, "boxes": [[0.1, 0.2, 0.4, 0.6, 0.81], [0.0, 0.0, 0.5, 0.5, 0.6]]},
        {"label": "smoke", "confidence": 0.5, "boxes": [[0.1, 0.1, 0.2, 0.2, 0.5]]},
    ]


def test_detector_end_to_end_on_a_fake_session() -> None:
    index = cells().index((32, 1, 1))
    detector = fake_detector(
        ["person", *([None] * 79)], [(index, 0, 0.95, (32.0, 32.0, 20.0, 16.0)), (index - 1, 5, 0.99, (8, 8, 4, 4))]
    )
    image = np.zeros((48, 64, 3), dtype=np.uint8)  # ratio 1: input pixels = image pixels
    found = detector.detect(image)
    assert len(found) == 1
    assert found[0].label == "person"
    assert found[0].confidence == pytest.approx(0.95)
    assert found[0].box == pytest.approx((22 / 64, 24 / 48, 42 / 64, 40 / 48), abs=1e-4)


def test_score_calibration_is_applied_per_label() -> None:
    index = cells().index((32, 1, 1))
    planted = [(index, 0, 0.36, (32.0, 32.0, 20.0, 16.0)), (index, 1, 0.36, (32.0, 32.0, 20.0, 16.0))]
    detector = fake_detector(["fire", "smoke"], planted, score_power={"fire": 0.5})
    found = {d.label: d.confidence for d in detector.detect(np.zeros((64, 64, 3), dtype=np.uint8))}
    assert found == {"fire": pytest.approx(0.6)}  # 0.36 ** 0.5; smoke stays 0.36 < 0.45


def test_manifest_validation(tmp_path: Path) -> None:
    from app.models import Manifest, ModelUnavailable

    base = {"name": "m", "license": "MIT", "format": "yolox", "input_size": [416, 416], "labels": ["fire", None]}
    for broken in (
        {**base, "format": "detr"},
        {**base, "labels": ["flood"]},
        {**base, "score_power": {"fire": 0}},
        {k: v for k, v in base.items() if k != "license"},
    ):
        (tmp_path / "manifest.json").write_text(json.dumps(broken))
        with pytest.raises(ModelUnavailable):
            Manifest.read(tmp_path)
    (tmp_path / "manifest.json").write_text(json.dumps({**base, "score_power": {"fire": 0.7}}))
    assert Manifest.read(tmp_path).score_power == {"fire": 0.7}
