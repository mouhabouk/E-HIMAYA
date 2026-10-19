"""ء-حماية / e-Himaya — core API entry point."""

import asyncio
import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.db import dispose_engine, get_sessionmaker
from app.core.events import relay_forever, start_bus, stop_bus
from app.core.logging import configure_logging
from app.modules import models as _models  # noqa: F401  (registers every table for cross-module foreign keys)
from app.modules.ai.pipeline import analyze_forever
from app.modules.ai.router import router as ai_router
from app.modules.audit.router import router as audit_router
from app.modules.content.router import router as content_router
from app.modules.geo.router import router as geo_router
from app.modules.health.router import router as health_router
from app.modules.identity.router import router as identity_router
from app.modules.notify.delivery import deliver_forever
from app.modules.notify.router import router as notify_router
from app.modules.notify.staff_router import router as notify_staff_router
from app.modules.ops.command_router import router as command_router
from app.modules.ops.router import router as ops_router
from app.modules.orgs.router import router as orgs_router
from app.modules.orgs.staff_router import router as orgs_staff_router
from app.modules.reports.live import hub
from app.modules.reports.live import router as live_router
from app.modules.reports.router import router as reports_router
from app.modules.reports.staff_router import router as staff_router
from app.modules.reports.uploads import router as uploads_router
from app.modules.reports.uploads import verify_forever
from app.modules.volunteers.router import router as volunteers_router
from app.modules.volunteers.staff_router import router as volunteers_staff_router

log = structlog.get_logger()
_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info("api.start", version=app.version)
    bus = await start_bus()
    bus.add_listener(hub.on_event)
    workers: list[asyncio.Task[None]] = []
    if get_settings().background_workers:
        sessionmaker = get_sessionmaker()
        workers = [
            asyncio.create_task(relay_forever(sessionmaker), name="outbox-relay"),
            asyncio.create_task(verify_forever(sessionmaker), name="media-verify"),
            asyncio.create_task(analyze_forever(sessionmaker), name="ai-analysis"),
            asyncio.create_task(deliver_forever(sessionmaker), name="notify-delivery"),
        ]
    try:
        yield
    finally:
        for task in workers:
            task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        await stop_bus()
        await dispose_engine()
        log.info("api.stop")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.api_log_level)

    app = FastAPI(
        title="ء-حماية / e-Himaya API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    if settings.api_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.api_cors_origins,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "Accept-Language", "X-Request-ID", "X-Device-Key"],
            max_age=600,
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _REQUEST_ID.match(incoming) else uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id, path=request.url.path)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    routers = (
        health_router,
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
        orgs_router,
        orgs_staff_router,
        ai_router,
        live_router,
        uploads_router,
        audit_router,
    )
    for router in routers:
        app.include_router(router)
    return app


app = create_app()
