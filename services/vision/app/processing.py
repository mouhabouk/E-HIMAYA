"""Pre- and post-processing of the detectors, in plain NumPy (no Ultralytics or other AGPL code).

Coordinates leaving this module are normalised to 0..1 of the original image, ``[x1, y1, x2, y2]``,
the format of ``reports.stream_detection.boxes`` (contract phase 6 §1).
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from PIL import Image

Array = NDArray[np.float32]

YOLOX_STRIDES = (8, 16, 32)
PAD_VALUE = 114


@dataclass(frozen=True, slots=True)
class Letterbox:
    """An image resized into the model input without distortion, padded right and bottom (YOLOX layout)."""

    tensor: Array  # 1 x 3 x H x W, float32, 0..255, BGR channel order
    ratio: float  # input pixels per original pixel
    width: int  # original size
    height: int


@dataclass(frozen=True, slots=True)
class Detection:
    label: str
    confidence: float
    box: tuple[float, float, float, float]  # normalised x1, y1, x2, y2


def letterbox(image: NDArray[np.uint8], size: tuple[int, int]) -> Letterbox:
    """RGB ``H x W x 3`` uint8 → padded BGR tensor of ``size`` (height, width)."""
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("expected an RGB image H x W x 3")
    height, width = int(image.shape[0]), int(image.shape[1])
    if height < 1 or width < 1:
        raise ValueError("empty image")
    target_h, target_w = size
    ratio = min(target_h / height, target_w / width)
    new_w, new_h = max(1, round(width * ratio)), max(1, round(height * ratio))
    resized = np.asarray(Image.fromarray(image).resize((new_w, new_h), Image.Resampling.BILINEAR))
    canvas = np.full((target_h, target_w, 3), PAD_VALUE, dtype=np.uint8)
    canvas[:new_h, :new_w] = resized
    tensor = canvas[:, :, ::-1].transpose(2, 0, 1)[np.newaxis].astype(np.float32)
    return Letterbox(tensor=np.ascontiguousarray(tensor), ratio=ratio, width=width, height=height)


def yolox_decode(raw: Array, size: tuple[int, int], strides: tuple[int, ...] = YOLOX_STRIDES) -> tuple[Array, Array]:
    """Raw YOLOX head output ``N x (5 + C)`` → boxes ``N x 4`` (x1, y1, x2, y2 in input pixels), scores ``N x C``.

    The grid layout follows the YOLOX paper (anchor-free, one prediction per cell and stride, cells in row-major
    order, strides from finest to coarsest): centre = (offset + cell) * stride, size = exp(log_size) * stride.
    """
    height, width = size
    grids = []
    scales = []
    for stride in strides:
        rows, cols = height // stride, width // stride
        ys, xs = np.meshgrid(np.arange(rows), np.arange(cols), indexing="ij")
        grids.append(np.stack((xs, ys), axis=-1).reshape(-1, 2))
        scales.append(np.full((rows * cols, 1), stride))
    grid = np.concatenate(grids).astype(np.float32)
    scale = np.concatenate(scales).astype(np.float32)
    if raw.shape[0] != grid.shape[0]:
        raise ValueError(f"unexpected number of predictions {raw.shape[0]} for input {size}")
    centre = (raw[:, 0:2] + grid) * scale
    half = np.exp(np.clip(raw[:, 2:4], -10.0, 10.0)) * scale / 2
    boxes = np.concatenate((centre - half, centre + half), axis=1)
    scores = raw[:, 4:5] * raw[:, 5:]  # objectness x class probability
    return boxes.astype(np.float32), scores.astype(np.float32)


def nms(boxes: Array, scores: Array, iou_threshold: float) -> list[int]:
    """Greedy non-maximum suppression; returns the kept indices, best score first."""
    if boxes.shape[0] == 0:
        return []
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = np.maximum(x2 - x1, 0) * np.maximum(y2 - y1, 0)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        best = int(order[0])
        keep.append(best)
        rest = order[1:]
        width = np.maximum(0.0, np.minimum(x2[best], x2[rest]) - np.maximum(x1[best], x1[rest]))
        height = np.maximum(0.0, np.minimum(y2[best], y2[rest]) - np.maximum(y1[best], y1[rest]))
        inter = width * height
        union = areas[best] + areas[rest] - inter
        iou = np.where(union > 0, inter / np.maximum(union, 1e-9), 0.0)
        order = rest[iou <= iou_threshold]
    return keep


def normalise(boxes: Array, ratio: float, width: int, height: int) -> Array:
    """Boxes in model-input pixels → 0..1 of the original image, clipped."""
    scaled = boxes / ratio
    scaled[:, [0, 2]] /= width
    scaled[:, [1, 3]] /= height
    clipped: Array = np.clip(scaled, 0.0, 1.0).astype(np.float32)
    return clipped


def select(
    boxes: Array,
    scores: Array,
    labels: list[str | None],
    *,
    letterboxed: Letterbox,
    min_confidence: float,
    iou_threshold: float,
    max_per_label: int,
) -> list[Detection]:
    """Per-class threshold and NMS. Classes mapped to ``None`` (e.g. the 79 other COCO classes) are ignored."""
    detections: list[Detection] = []
    for index, label in enumerate(labels):
        if label is None:
            continue
        class_scores = scores[:, index]
        mask = class_scores >= min_confidence
        if not mask.any():
            continue
        candidate_boxes = normalise(boxes[mask].copy(), letterboxed.ratio, letterboxed.width, letterboxed.height)
        candidate_scores = class_scores[mask]
        # Degenerate boxes (fully outside the image after clipping) are dropped.
        valid = (candidate_boxes[:, 2] > candidate_boxes[:, 0]) & (candidate_boxes[:, 3] > candidate_boxes[:, 1])
        candidate_boxes, candidate_scores = candidate_boxes[valid], candidate_scores[valid]
        for kept in nms(candidate_boxes, candidate_scores, iou_threshold)[:max_per_label]:
            x1, y1, x2, y2 = (round(float(v), 4) for v in candidate_boxes[kept])
            detections.append(Detection(label, round(float(candidate_scores[kept]), 4), (x1, y1, x2, y2)))
    return detections


def group(detections: list[Detection]) -> list[dict[str, object]]:
    """Contract shape: one entry per label, ``confidence`` = best box, ``boxes`` = ``[[x1,y1,x2,y2,conf], …]``."""
    by_label: dict[str, list[Detection]] = {}
    for detection in detections:
        by_label.setdefault(detection.label, []).append(detection)
    grouped: list[dict[str, object]] = []
    for label, items in sorted(by_label.items()):
        items.sort(key=lambda d: d.confidence, reverse=True)
        grouped.append(
            {
                "label": label,
                "confidence": items[0].confidence,
                "boxes": [[*d.box, d.confidence] for d in items],
            }
        )
    return grouped
