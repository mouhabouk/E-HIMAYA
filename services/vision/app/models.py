"""Detectors, loaded lazily from ``VISION_MODELS_DIR`` (prepared by ``models/fetch_models.py``).

Each model directory holds ``model.onnx`` and ``manifest.json``::

    {"name": "ehimaya-fire-smoke-yolox-tiny", "version": "3.0.0", "license": "Apache-2.0",
     "format": "yolox", "input_size": [416, 416], "labels": ["fire", "smoke"], "sha256": "…", …}

``labels`` maps every output class of the network to one of ``fire|smoke|person``, or ``null`` to ignore it
(the COCO person model has 80 classes, only class 0 is used). Models run with ONNX Runtime (MIT) on the CPU
with a bounded number of threads. A missing or corrupt model only disables detection (503); it never crashes
the service.
"""

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import structlog
from numpy.typing import NDArray

from app import processing
from app.config import get_settings
from app.metrics import INFERENCE_SECONDS
from app.processing import Detection

log = structlog.get_logger()

LABELS = ("fire", "smoke", "person")
FORMATS = ("yolox",)


class ModelUnavailable(Exception):
    """The model files are not installed or failed to load."""


class Busy(Exception):
    """Every inference worker stayed busy for longer than the caller accepts to wait."""


@dataclass(frozen=True, slots=True)
class Manifest:
    directory: Path
    name: str
    version: str
    license: str
    format: str
    input_size: tuple[int, int]
    labels: list[str | None]
    sha256: str | None
    # Per-label calibration ``score ** power`` (monotonic): maps the network's scores onto the API thresholds
    # (VISION_MIN_CONFIDENCE 0.45, VISION_ALERT_CONFIDENCE 0.6). Fitted on eval/calibration.json, see EVALUATION.md.
    score_power: dict[str, float]
    data: dict[str, Any] = field(repr=False)

    @classmethod
    def read(cls, directory: Path) -> "Manifest":
        try:
            data = json.loads((directory / "manifest.json").read_text())
        except (OSError, ValueError) as exc:
            raise ModelUnavailable(f"{directory.name}: manifest.json missing or invalid") from exc
        try:
            labels = [None if label is None else str(label) for label in data["labels"]]
            manifest = cls(
                directory=directory,
                name=str(data["name"]),
                version=str(data.get("version", "0")),
                license=str(data["license"]),
                format=str(data["format"]),
                input_size=(int(data["input_size"][0]), int(data["input_size"][1])),
                labels=labels,
                sha256=data.get("sha256"),
                score_power={str(k): float(v) for k, v in (data.get("score_power") or {}).items()},
                data=data,
            )
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise ModelUnavailable(f"{directory.name}: manifest.json incomplete ({exc})") from exc
        if manifest.format not in FORMATS:
            raise ModelUnavailable(f"{directory.name}: unsupported format {manifest.format!r}")
        if any(not 0.05 <= power <= 20 for power in manifest.score_power.values()):
            raise ModelUnavailable(f"{directory.name}: score_power out of range")
        if unknown := {label for label in labels if label is not None} - set(LABELS):
            raise ModelUnavailable(f"{directory.name}: unknown labels {sorted(unknown)}")
        return manifest


class OnnxDetector:
    """One ONNX network and its manifest. ``session.run`` is thread-safe: one session serves every worker."""

    def __init__(self, manifest: Manifest, session: Any) -> None:
        self.manifest = manifest
        self._session = session
        self._input = session.get_inputs()[0].name

    @classmethod
    def load(cls, directory: Path) -> "OnnxDetector":
        import onnxruntime as ort

        manifest = Manifest.read(directory)
        path = directory / str(manifest.data.get("file", "model.onnx"))
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise ModelUnavailable(f"{directory.name}: {path.name} missing") from exc
        if manifest.sha256 and hashlib.sha256(payload).hexdigest() != manifest.sha256:
            raise ModelUnavailable(f"{directory.name}: {path.name} does not match its SHA-256")
        settings = get_settings()
        options = ort.SessionOptions()
        options.intra_op_num_threads = settings.inference_threads
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        try:
            session = ort.InferenceSession(payload, sess_options=options, providers=["CPUExecutionProvider"])
        except Exception as exc:  # corrupted file, unsupported opset…
            raise ModelUnavailable(f"{directory.name}: cannot load ({type(exc).__name__})") from exc
        shape = session.get_inputs()[0].shape
        if list(shape[2:]) != list(manifest.input_size):
            raise ModelUnavailable(f"{directory.name}: input {shape} does not match manifest {manifest.input_size}")
        return cls(manifest, session)

    def detect(self, image: NDArray[np.uint8]) -> list[Detection]:
        settings = get_settings()
        boxed = processing.letterbox(image, self.manifest.input_size)
        started = time.perf_counter()
        raw = self._session.run(None, {self._input: boxed.tensor})[0][0].astype(np.float32)
        INFERENCE_SECONDS.labels(model=self.manifest.name).observe(time.perf_counter() - started)
        if raw.shape[1] != 5 + len(self.manifest.labels):
            raise ModelUnavailable(
                f"{self.manifest.name}: {raw.shape[1] - 5} classes, manifest has labels for {len(self.manifest.labels)}"
            )
        boxes, scores = processing.yolox_decode(raw, self.manifest.input_size)
        for index, label in enumerate(self.manifest.labels):
            power = self.manifest.score_power.get(label or "")
            if power is not None:
                scores[:, index] = np.power(np.clip(scores[:, index], 0.0, 1.0), power)
        return processing.select(
            boxes,
            scores,
            self.manifest.labels,
            letterboxed=boxed,
            min_confidence=settings.min_confidence,
            iou_threshold=settings.nms_iou,
            max_per_label=settings.max_boxes_per_label,
        )


class Detectors:
    """The enabled models (``VISION_ENABLED_MODELS``), loaded once on first use; retried after a failure."""

    RETRY_AFTER_S = 30.0

    def __init__(self) -> None:
        self._models: list[OnnxDetector] | None = None
        self._error: str | None = None
        self._failed_at = 0.0
        self._lock = threading.Lock()
        # Shared by the uploads and every stream thread: bounds the CPU to workers x threads.
        self._slots = threading.BoundedSemaphore(get_settings().inference_workers)

    def get(self) -> list[OnnxDetector]:
        if self._models is not None:
            return self._models
        with self._lock:
            if self._models is not None:
                return self._models
            if self._error and time.monotonic() - self._failed_at < self.RETRY_AFTER_S:
                raise ModelUnavailable(self._error)
            settings = get_settings()
            try:
                models = [OnnxDetector.load(settings.models_dir / name) for name in settings.enabled_models]
                if not models:
                    raise ModelUnavailable("no model enabled")
            except ModelUnavailable as exc:
                self._error, self._failed_at = str(exc), time.monotonic()
                log.warning("vision.model_unavailable", reason=str(exc))
                raise
            self._models, self._error = models, None
            log.info("vision.models_loaded", models=[m.manifest.name for m in models])
            return models

    def ready(self) -> bool:
        try:
            self.get()
        except ModelUnavailable:
            return False
        return True

    @property
    def error(self) -> str | None:
        return self._error

    def detect(self, image: NDArray[np.uint8], wait_s: float | None = None) -> list[Detection]:
        """Every enabled model on one frame, inside the shared pool of ``VISION_INFERENCE_WORKERS`` slots."""
        models = self.get()
        if not self._slots.acquire(timeout=wait_s if wait_s is not None else -1):
            raise Busy
        try:
            detections: list[Detection] = []
            for model in models:
                detections.extend(model.detect(image))
            return detections
        finally:
            self._slots.release()

    def name(self) -> str:
        """``model`` field of the responses and callbacks, e.g. ``fire-smoke@1.0.0+person@0.1.1``."""
        return "+".join(f"{m.manifest.name}@{m.manifest.version}" for m in self.get())

    def describe(self) -> dict[str, Any]:
        models = self.get()
        labels = sorted({label for m in models for label in m.manifest.labels if label}, key=LABELS.index)
        return {
            "name": self.name(),
            "version": "+".join(m.manifest.version for m in models),
            "license": " AND ".join(sorted({m.manifest.license for m in models})),
            "labels": labels,
            "models": [
                {
                    "name": m.manifest.name,
                    "version": m.manifest.version,
                    "license": m.manifest.license,
                    "source": m.manifest.data.get("source"),
                    "sha256": m.manifest.sha256,
                    "labels": sorted({label for label in m.manifest.labels if label}),
                }
                for m in models
            ],
        }

    def reset(self) -> None:
        with self._lock:
            self._models, self._error, self._failed_at = None, None, 0.0
