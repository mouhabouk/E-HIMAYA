"""ء-حماية / e-Himaya — internal AI inference service.

Called only by the core API (bearer service token). Stateless: the API owns the data and the analysis
pipeline; this service turns audio into text, translates French and English into Arabic, embeds text and
asks the local language model for a structured reading of a report.
"""

import hmac
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

import anyio
import httpx
import structlog
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app import extract as llm
from app import models
from app.config import get_settings
from app.media import MediaError, downloaded
from app.models import ModelUnavailable
from app.schemas import (
    CapabilityHealth,
    EmbedIn,
    EmbedOut,
    ExtractIn,
    ExtractOut,
    HealthOut,
    Segment,
    TranscribeIn,
    TranscribeOut,
    TranslateIn,
    TranslateOut,
)

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    app.state.http = httpx.AsyncClient()
    limit = max(settings.concurrency, 1)
    app.state.limits = {name: anyio.CapacityLimiter(limit) for name in ("whisper", "translate", "embed", "llm")}
    try:
        yield
    finally:
        await app.state.http.aclose()


app = FastAPI(title="e-Himaya AI", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)


def authorized(authorization: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().service_token.get_secret_value()
    given = authorization[7:].strip() if authorization and authorization.lower().startswith("bearer ") else ""
    if not hmac.compare_digest(given.encode(), expected.encode()):
        raise HTTPException(401, "invalid_service_token")


Authorized = Annotated[None, Depends(authorized)]


@app.exception_handler(ModelUnavailable)
async def _unavailable(_: Request, exc: ModelUnavailable) -> JSONResponse:
    log.warning("ai.model_unavailable", reason=str(exc))
    return JSONResponse({"detail": "model_unavailable"}, status_code=503)


@app.exception_handler(MediaError)
async def _media(_: Request, exc: MediaError) -> JSONResponse:
    return JSONResponse({"detail": exc.code}, status_code=422)


async def _run(request: Request, limiter: str, fn: Any, *args: Any) -> Any:
    return await anyio.to_thread.run_sync(fn, *args, limiter=request.app.state.limits[limiter])


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/health", response_model=HealthOut)
async def health(request: Request, _: Authorized) -> HealthOut:
    def capability(lazy: Any) -> CapabilityHealth:
        name = lazy.manifest_name()
        return CapabilityHealth(ready=name is not None, model=name, detail=None if name else "not installed")

    ready, detail = await llm.llm_ready(request.app.state.http)
    return HealthOut(
        transcribe=capability(models.whisper),
        translate_fr=capability(models.translators["fr"]),
        translate_en=capability(models.translators["en"]),
        embed=capability(models.embedder),
        extract=CapabilityHealth(ready=ready, model=get_settings().llm_model, detail=detail),
    )


@app.post("/v1/transcribe", response_model=TranscribeOut)
async def transcribe(request: Request, body: TranscribeIn, _: Authorized) -> TranscribeOut:
    models.whisper.get()  # fail fast (503) before downloading the media
    async with downloaded(body.url, request.app.state.http) as path:
        try:
            result = await _run(request, "whisper", models.whisper.transcribe, path, body.language)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except ModelUnavailable:
            raise
        except Exception as exc:
            # Undecodable or corrupted media: not retryable.
            log.warning("ai.transcribe_failed", error=type(exc).__name__, detail=str(exc)[:200])
            raise HTTPException(422, "media_undecodable") from exc
    return TranscribeOut(
        text=result.text,
        language=result.language,
        language_probability=result.language_probability,
        duration_s=result.duration_s,
        segments=[Segment(start=s, end=e, text=t) for s, e, t in result.segments],
        model=models.whisper.manifest_name() or "whisper",
    )


@app.post("/v1/translate", response_model=TranslateOut)
async def translate(request: Request, body: TranslateIn, _: Authorized) -> TranslateOut:
    translator = models.translators[body.source]
    texts = [t[:5000] for t in body.texts]
    result = await _run(request, "translate", translator.translate, texts)
    return TranslateOut(texts=result, model=translator.manifest_name() or translator.directory)


@app.post("/v1/embed", response_model=EmbedOut)
async def embed(request: Request, body: EmbedIn, _: Authorized) -> EmbedOut:
    vectors = await _run(request, "embed", models.embedder.embed, [t[:5000] for t in body.texts])
    return EmbedOut(
        vectors=[[round(float(x), 6) for x in row] for row in vectors],
        dim=int(vectors.shape[1]),
        model=models.embedder.manifest_name() or "embed",
    )


@app.post("/v1/extract", response_model=ExtractOut)
async def extract(request: Request, body: ExtractIn, _: Authorized) -> ExtractOut:
    async with request.app.state.limits["llm"]:
        try:
            extraction, model = await llm.extract(body.text, body.reported_category, request.app.state.http)
        except ValueError as exc:
            raise HTTPException(502, str(exc)) from exc
    return ExtractOut(**extraction.model_dump(), model=model)
