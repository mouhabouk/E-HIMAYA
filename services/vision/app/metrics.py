"""Prometheus metrics (``GET /metrics``, bearer token like every other route)."""

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, disable_created_metrics

# No *_created series: they double the output for no use here.
disable_created_metrics()  # type: ignore[no-untyped-call]

REGISTRY = CollectorRegistry(auto_describe=True)

INFERENCE_SECONDS = Histogram(
    "vision_inference_seconds",
    "ONNX Runtime time per frame and model",
    ["model"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.2, 0.4, 0.8, 1.6, 3.2),
    registry=REGISTRY,
)
FRAMES = Counter("vision_frames_analysed_total", "Frames analysed", ["source"], registry=REGISTRY)
DETECTIONS = Counter(
    "vision_detections_total", "Frames with at least one detection, by label", ["label"], registry=REGISTRY
)
CALLBACKS = Counter(
    "vision_callbacks_total", "Detection callbacks to the API, by outcome", ["outcome"], registry=REGISTRY
)
STREAMS = Gauge("vision_streams_active", "Streams being watched", registry=REGISTRY)
STREAM_ENDS = Counter("vision_stream_ends_total", "Watches that ended, by reason", ["reason"], registry=REGISTRY)
RECONNECTS = Counter("vision_stream_reconnects_total", "RTSP reconnection attempts", registry=REGISTRY)
REJECTED = Counter(
    "vision_streams_rejected_total", "PUT /v1/streams refused because every slot is busy", registry=REGISTRY
)
