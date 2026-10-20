"""ء-حماية / e-Himaya — internal computer vision service (contract: docs/api/phase-6-contract.md §5).

Detects fire, smoke and people in report images (``POST /v1/detect``) and in live streams relayed by MediaMTX
(``PUT/DELETE /v1/streams/{stream_id}``), and posts stream detections back to the API. Called only by the core API
(bearer token). It never decides anything: confirmation and alerting stay with the API and a human (FR-C-11).
"""

import hmac
import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

import anyio
import structlog
from fastapi import Depends, FastAPI, File, Header, HTTPException, Path, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app import imaging, processing
from app.config import get_settings
from app.imaging import ImageRejected
from app.metrics import DETECTIONS, FRAMES, REGISTRY, REJECTED
from app.models import Busy, Detectors, ModelUnavailable
from app.schemas import DetectOut, HealthOut, ModelOut, StreamIn, StreamOut
from app.streams import FrameSource, StreamManager, TooManyStreams, rtsp_frames

log = structlog.get_logger()

# An upload waits at most this long for a free inference worker (streams keep theirs), then 503 busy.
DETECT_WAIT_S = 20.0
STREAM_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def create_app(source: FrameSource = rtsp_frames) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings = get_settings()
        logging.basicConfig(level=settings.log_level)
        app.state.detectors = Detectors()
        app.state.streams = StreamManager(app.state.detectors, source)
        # Load the models at start-up (well under a second) so that the first frame does not pay for it.
        await anyio.to_thread.run_sync(app.state.detectors.ready)
        try:
            yield
        finally:
            await anyio.to_thread.run_sync(app.state.streams.shutdown)

    app = FastAPI(title="e-Himaya Vision", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)

    @app.exception_handler(ModelUnavailable)
    async def _unavailable(_: Request, exc: ModelUnavailable) -> JSONResponse:
        return JSONResponse({"detail": "model_unavailable"}, status_code=503, headers={"Retry-After": "30"})

    @app.exception_handler(Busy)
    async def _busy(_: Request, exc: Busy) -> JSONResponse:
        return JSONResponse({"detail": "busy"}, status_code=503, headers={"Retry-After": "5"})

    @app.exception_handler(ImageRejected)
    async def _rejected(_: Request, exc: ImageRejected) -> JSONResponse:
        status = 413 if str(exc) == "image_too_large" else 415 if "type" in str(exc) else 422
        return JSONResponse({"detail": str(exc)}, status_code=status)

    def detectors(request: Request) -> Detectors:
        return request.app.state.detectors  # type: ignore[no-any-return]

    def streams(request: Request) -> StreamManager:
        return request.app.state.streams  # type: ignore[no-any-return]

    @app.get("/healthz", response_model=HealthOut)
    async def health(request: Request) -> HealthOut:
        """Liveness and readiness in one: always 200 while the process serves; ``degraded`` without a model."""
        found = detectors(request)
        ready = await anyio.to_thread.run_sync(found.ready)
        return HealthOut(
            status="ok" if ready else "degraded",
            model=found.name() if ready else None,
            detail=None if ready else found.error,
            streams=len(streams(request)),
            max_streams=get_settings().max_streams,
        )

    @app.get("/v1/model", response_model=ModelOut, dependencies=[Depends(authorized)])
    async def model(request: Request) -> dict[str, Any]:
        return await anyio.to_thread.run_sync(detectors(request).describe)

    @app.post("/v1/detect", response_model=DetectOut, dependencies=[Depends(authorized)])
    async def detect(
        request: Request,
        image: Annotated[UploadFile, File(description="JPEG, PNG or WebP image")],
        content_length: Annotated[int | None, Header()] = None,
    ) -> DetectOut:
        settings = get_settings()
        if content_length is not None and content_length > settings.max_image_bytes + 64 * 1024:
            raise HTTPException(413, "image_too_large")
        found = detectors(request)
        found.get()  # fail fast (503) before decoding
        payload = await image.read(settings.max_image_bytes + 1)
        if len(payload) > settings.max_image_bytes:
            raise HTTPException(413, "image_too_large")
        if not payload:
            raise HTTPException(422, "image_empty")
        pixels = await anyio.to_thread.run_sync(imaging.decode, payload, image.content_type, settings.max_image_pixels)
        found_detections = await anyio.to_thread.run_sync(found.detect, pixels, DETECT_WAIT_S)
        FRAMES.labels(source="upload").inc()
        for label in {d.label for d in found_detections}:
            DETECTIONS.labels(label=label).inc()
        return DetectOut.model_validate({"model": found.name(), "detections": processing.group(found_detections)})

    @app.put("/v1/streams/{stream_id}", status_code=202, response_model=StreamOut, dependencies=[Depends(authorized)])
    async def watch(request: Request, body: StreamIn, stream_id: Annotated[str, Path(max_length=64)]) -> StreamOut:
        settings = get_settings()
        if not STREAM_ID.match(stream_id):
            raise HTTPException(422, "invalid_stream_id")
        if not body.rtsp_url.startswith(settings.rtsp_url_prefix) or "@" in body.rtsp_url:
            raise HTTPException(422, "rtsp_url_not_allowed")
        if not body.callback_url.startswith(settings.callback_url_prefix):
            raise HTTPException(422, "callback_url_not_allowed")
        detectors(request).get()  # 503 when no model: the API retries later
        try:
            state = streams(request).start(stream_id, body.rtsp_url, body.callback_url)
        except TooManyStreams:
            REJECTED.inc()
            return JSONResponse(  # type: ignore[return-value]
                {"detail": "too_many_streams"}, status_code=429, headers={"Retry-After": "30"}
            )
        return StreamOut(
            stream_id=stream_id, state=state, streams=len(streams(request)), max_streams=settings.max_streams
        )

    @app.delete("/v1/streams/{stream_id}", status_code=204, dependencies=[Depends(authorized)])
    async def unwatch(request: Request, stream_id: Annotated[str, Path(max_length=64)]) -> Response:
        streams(request).stop(stream_id)  # idempotent: unknown stream is fine
        return Response(status_code=204)

    @app.get("/v1/streams", dependencies=[Depends(authorized)])
    async def watched(request: Request) -> dict[str, Any]:
        return {"streams": streams(request).list(), "max_streams": get_settings().max_streams}

    @app.get("/metrics", dependencies=[Depends(authorized)])
    async def metrics() -> Response:
        return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

    return app


def authorized(authorization: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().api_token.get_secret_value()
    given = authorization[7:].strip() if authorization and authorization.lower().startswith("bearer ") else ""
    if not hmac.compare_digest(given.encode(), expected.encode()):
        raise HTTPException(401, "invalid_token")


app = create_app()
