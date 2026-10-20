"""Request and response bodies (contract: docs/api/phase-6-contract.md §3 and §5)."""

from typing import Literal

from pydantic import BaseModel, Field

Label = Literal["fire", "smoke", "person"]


class LabelDetection(BaseModel):
    label: Label
    confidence: float = Field(ge=0, le=1)
    # [[x1, y1, x2, y2, confidence], …], coordinates normalised 0..1 of the image, best box first.
    boxes: list[list[float]]


class DetectOut(BaseModel):
    model: str
    detections: list[LabelDetection]


class ModelInfo(BaseModel):
    name: str
    version: str
    license: str
    source: str | None
    sha256: str | None
    labels: list[Label]


class ModelOut(BaseModel):
    name: str
    version: str
    license: str
    labels: list[Label]
    models: list[ModelInfo]


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    model: str | None
    detail: str | None
    streams: int
    max_streams: int


class StreamIn(BaseModel):
    rtsp_url: str = Field(max_length=512)
    callback_url: str = Field(max_length=512)


class StreamOut(BaseModel):
    stream_id: str
    state: Literal["started", "updated"]
    streams: int
    max_streams: int


class DetectionCallback(BaseModel):
    """Body of POST /internal/vision/detections (sent by this service; documented here for the tests)."""

    stream_id: str
    at: str
    model: str
    detections: list[LabelDetection]
    frame_jpeg_b64: str | None
