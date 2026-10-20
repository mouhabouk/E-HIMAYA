"""Runtime configuration (environment variables prefixed ``VISION_``)."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VISION_", env_file=".env", extra="ignore")

    # Bearer token the core API presents on every call but /healthz. Internal service, never exposed publicly.
    api_token: SecretStr = Field(min_length=24)
    # Sent back as X-Vision-Token on POST /internal/vision/detections (contract phase 6 §3).
    callback_token: SecretStr = Field(min_length=24)
    # Models prepared by models/fetch_models.py (one directory per model, each with manifest.json).
    models_dir: Path = Path("/models")
    # "person" can be switched off on small CPUs: fire and smoke keep working with the first model only.
    enabled_models: list[str] = ["fire-smoke", "person"]

    # CPU budget: at most inference_workers frames are analysed at once, each with inference_threads threads.
    inference_workers: int = Field(default=2, ge=1, le=32)
    inference_threads: int = Field(default=2, ge=1, le=32)
    # Detections under this confidence are dropped (the API applies the same floor, VISION_MIN_CONFIDENCE).
    min_confidence: float = Field(default=0.45, ge=0.05, le=0.99)
    nms_iou: float = Field(default=0.5, ge=0.1, le=0.9)
    max_boxes_per_label: int = Field(default=20, ge=1, le=100)

    # POST /v1/detect limits.
    max_image_bytes: int = 10 * 1024 * 1024
    max_image_pixels: int = 40_000_000

    # Live streams (contract phase 6 §5).
    max_streams: int = Field(default=8, ge=1, le=256)
    fps_idle: float = Field(default=1.0, gt=0, le=10)
    fps_pending: float = Field(default=2.0, gt=0, le=10)
    # A stream stays "pending confirmation" (fps_pending) until this many analysed frames in a row are clean.
    pending_clear_frames: int = Field(default=5, ge=1, le=50)
    # Only MediaMTX paths are watched, and detections are only sent to the API (no SSRF through this service).
    rtsp_url_prefix: str = "rtsp://mediamtx:8554/live/"
    callback_url_prefix: str = "http://api:8000/internal/vision/"
    # MediaMTX read credentials (authHTTPAddress: user=vision, password=$VISION_READ_PASSWORD).
    rtsp_user: str = "vision"
    rtsp_password: SecretStr = SecretStr("")
    rtsp_timeout_s: float = Field(default=10.0, gt=0, le=120)
    # Reconnection: exponential backoff from 1 s up to reconnect_max_delay_s; the watcher gives up when no frame
    # could be read for stream_gone_after_s (the publisher has left: MediaMTX answers 404 on DESCRIBE).
    reconnect_max_delay_s: float = Field(default=15.0, ge=1, le=300)
    stream_gone_after_s: float = Field(default=60.0, ge=5, le=3600)
    # Hard cap on a single watch (a drone can stream for hours; the API renews with a new PUT).
    max_watch_s: float = Field(default=6 * 3600, ge=60)
    # Frame attached to a callback with detections: longest side in pixels and JPEG quality.
    frame_max_side: int = Field(default=640, ge=64, le=1920)
    frame_jpeg_quality: int = Field(default=80, ge=30, le=95)
    callback_timeout_s: float = Field(default=5.0, gt=0, le=60)

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
