"""ء-حماية / e-Himaya — core API entry point."""

import asyncio
import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import metrics
from app.core.access import ApiError
from app.core.config import get_settings
from app.core.db import dispose_engine, get_system_sessionmaker
from app.core.events import relay_forever, start_bus, stop_bus
from app.core.logging import configure_logging
from app.modules import models as _models  # noqa: F401  (registers every table for cross-module foreign keys)
from app.modules.access import accounts
from app.modules.access.router import router as access_router
from app.modules.access.worker import breakglass_forever
from app.modules.ai.pipeline import analyze_forever
from app.modules.ai.router import router as ai_router
from app.modules.analytics.library import router as analytics_library_router
from app.modules.analytics.router import router as analytics_router
from app.modules.analytics.worker import analytics_forever
from app.modules.appinfo.router import router as appinfo_router
from app.modules.audit.router import router as audit_router
from app.modules.contact.router import router as contact_router
from app.modules.contact.router import staff_router as contact_staff_router
from app.modules.content.guide import router as guide_router
from app.modules.content.router import router as content_router
from app.modules.decision.procedures import procedures_forever
from app.modules.decision.router import router as decision_router
from app.modules.evidence.router import router as evidence_router
from app.modules.evidence.worker import evidence_forever
from app.modules.forecast.router import router as forecast_router
from app.modules.geo.router import router as geo_router
from app.modules.health.router import metrics_router
from app.modules.health.router import router as health_router
from app.modules.identity.internal import router as identity_internal_router
from app.modules.identity.router import router as identity_router
from app.modules.knowledge.indexer import knowledge_forever
from app.modules.knowledge.router import router as knowledge_router
from app.modules.layers.router import public_router as layers_router
from app.modules.layers.router import router as layers_staff_router
from app.modules.notify.delivery import deliver_forever
from app.modules.notify.router import router as notify_router
from app.modules.notify.staff_router import router as notify_staff_router
from app.modules.ops.command_router import router as command_router
from app.modules.ops.router import router as ops_router
from app.modules.orgs.router import router as orgs_router
from app.modules.orgs.staff_router import router as orgs_staff_router
from app.modules.privacy.retention import retention_forever
from app.modules.privacy.router import router as privacy_router
from app.modules.reports.jurisdiction import sla_forever
from app.modules.reports.live import hub
from app.modules.reports.live import router as live_router
from app.modules.reports.router import router as reports_router
from app.modules.reports.staff_router import router as staff_router
from app.modules.reports.uploads import router as uploads_router
from app.modules.reports.uploads import verify_forever
from app.modules.rewards.consumer import rewards_forever
from app.modules.rewards.router import router as rewards_router
from app.modules.rewards.staff_router import router as rewards_staff_router
from app.modules.settings import service as platform_settings
from app.modules.settings.router import router as settings_router
from app.modules.streams.internal import router as streams_internal_router
from app.modules.streams.router import router as streams_router
from app.modules.streams.staff_router import router as streams_staff_router
from app.modules.streams.worker import ingest_forever, streams_forever, vision_images_forever
from app.modules.telephony.internal import router as telephony_internal_router
from app.modules.telephony.staff_router import router as telephony_staff_router
from app.modules.telephony.worker import ari_events_forever, endpoints_forever, recordings_forever
from app.modules.volunteers.router import router as volunteers_router
from app.modules.volunteers.staff_router import router as volunteers_staff_router
from app.modules.weather.router import router as weather_router
from app.modules.weather.staff_router import router as weather_staff_router
from app.modules.weather.worker import weather_forever

log = structlog.get_logger()
_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")
# JSON API: nothing may be rendered, framed or scripted from its responses (A3).
_API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
}
# Swagger UI and ReDoc (development only) load their scripts from a CDN: no CSP on those pages.
_DOCS_PATHS = ("/docs", "/redoc")

WorkerLoop = Callable[[async_sessionmaker[AsyncSession]], Coroutine[Any, Any, None]]
# Background loops run by the worker role (PROCESS_ROLE=worker|all). Each one must be safe to run in
# several processes at once (row locks with SKIP LOCKED, leases or advisory locks). Modules add theirs here.
WORKER_LOOPS: list[tuple[str, WorkerLoop]] = [
    ("outbox-relay", relay_forever),
    ("media-verify", verify_forever),
    ("ai-analysis", analyze_forever),
    ("notify-delivery", deliver_forever),
    ("retention", retention_forever),
    ("stream-segments", ingest_forever),
    ("stream-lifecycle", streams_forever),
    ("vision-images", vision_images_forever),
    ("weather-grid", weather_forever),
    ("procedures-index", procedures_forever),
    ("telephony-events", ari_events_forever),
    ("telephony-recordings", recordings_forever),
    ("telephony-endpoints", endpoints_forever),
    ("knowledge", knowledge_forever),
    ("analytics", analytics_forever),
    ("rewards", rewards_forever),
    ("sla-escalation", sla_forever),
    ("breakglass", breakglass_forever),
    ("evidence", evidence_forever),
]
# Paths a worker-role process still serves: probes and the metrics scrape, never SOS traffic.
_WORKER_PATHS = ("/health/", "/metrics")


def start_worker_loops(sessionmaker: async_sessionmaker[AsyncSession]) -> list[asyncio.Task[None]]:
    return [asyncio.create_task(loop(sessionmaker), name=name) for name, loop in WORKER_LOOPS]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    log.info("api.start", version=app.version, process_role=settings.process_role)
    bus = await start_bus()
    bus.add_listener(hub.on_event)
    bus.add_listener(platform_settings.on_event)
    workers: list[asyncio.Task[None]] = []
    if settings.background_workers and settings.process_role in ("worker", "all"):
        # Worker loops act for no principal: system database scope (row-level security, phase 9 §9.1).
        workers = start_worker_loops(get_system_sessionmaker())
    try:
        yield
    finally:
        for task in workers:
            task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        await stop_bus()
        await dispose_engine()
        log.info("api.stop")


# Version of the HTTP contract (docs/api/README.md): /api/v1 only grows; the minor number follows the phase.
API_VERSION = "1.10.0"


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.api_log_level)

    production = settings.app_env == "production"
    app = FastAPI(
        title="ء-حماية / e-Himaya API",
        version=API_VERSION,
        lifespan=lifespan,
        # Interactive documentation and the schema are development aids; production does not publish them.
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
    )
    headers = dict(_SECURITY_HEADERS)
    if production:
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    if settings.api_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.api_cors_origins,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "Accept-Language", "X-Request-ID", "X-Device-Key"],
            # Anonymous report quota (phase 9 §3), read by the app after each report.
            expose_headers=["X-Anon-Quota-Limit", "X-Anon-Quota-Remaining"],
            max_age=600,
        )

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        # Errors naming more than a code, e.g. 409 already_claimed with the claiming room.
        return JSONResponse({"detail": exc.detail, **exc.extra}, status_code=exc.status_code, headers=exc.headers)

    @app.middleware("http")
    async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _REQUEST_ID.match(incoming) else uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id, path=request.url.path)
        if settings.process_role == "worker" and not request.url.path.startswith(_WORKER_PATHS):
            response: Response = JSONResponse({"detail": "worker_process"}, status_code=503)
        else:
            area = "reports" if request.url.path.startswith("/api/v1/reports") else "other"
            try:
                response = await call_next(request)
            except Exception:
                metrics.HTTP_SERVER_ERRORS.labels(area=area).inc()
                raise
            if response.status_code >= 500:
                metrics.HTTP_SERVER_ERRORS.labels(area=area).inc()
        response.headers["X-Request-ID"] = request_id
        response.headers.update(headers)
        # Answers carry personal data: no browser or proxy keeps them unless an endpoint says otherwise (ASVS V8.2.1).
        response.headers.setdefault("Cache-Control", "no-store")
        if not request.url.path.startswith(_DOCS_PATHS) or production:
            response.headers["Content-Security-Policy"] = _API_CSP
        return response

    routers = (
        health_router,
        metrics_router,
        geo_router,
        identity_router,
        reports_router,
        staff_router,
        ops_router,
        command_router,
        volunteers_router,
        volunteers_staff_router,
        notify_router,
        notify_staff_router,
        content_router,
        guide_router,
        contact_router,
        contact_staff_router,
        orgs_router,
        orgs_staff_router,
        ai_router,
        live_router,
        uploads_router,
        streams_router,
        streams_staff_router,
        streams_internal_router,
        audit_router,
        privacy_router,
        weather_router,
        weather_staff_router,
        forecast_router,
        decision_router,
        telephony_staff_router,
        telephony_internal_router,
        knowledge_router,
        analytics_router,
        analytics_library_router,
        rewards_router,
        rewards_staff_router,
        settings_router,
        access_router,
        evidence_router,
        appinfo_router,
        layers_router,
        layers_staff_router,
        identity_internal_router,
    )
    for router in routers:
        app.include_router(router)
    app.include_router(accounts.router)
    return app


app = create_app()
