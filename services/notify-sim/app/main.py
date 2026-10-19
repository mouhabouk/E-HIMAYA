# ┏━━ SIMULATION ━━ HTTP surface of the channels simulator: FCM HTTP v1 + OAuth, SMS gateway, inspection API, inbox
# ┃ PRODUCTION: remove the notify-sim service from infra/compose.yml; set FCM_SERVICE_ACCOUNT (Firebase console >
# ┃   Project settings > Service accounts > Generate new private key, base64), FCM_API_URL=https://fcm.googleapis.com,
# ┃   SMS_HTTP_URL and SMS_HTTP_TOKEN (SMS provider contract) in .env.
# ┗━━━━━━━━━━━━━━━━
"""SIMULATION — e-Himaya channels simulator (development and tests only, never in production).

Run:  uvicorn --factory app.main:create_app --port 8090
"""

import hmac
import html
import json
import logging
import secrets
import time
from collections.abc import Callable
from typing import Annotated, Any, Literal
from urllib.parse import parse_qs

from fastapi import FastAPI, Header, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

from . import fcm, sms
from .account import load_or_create
from .config import Settings, get_settings
from .inbox import INBOX_HTML
from .store import Store

log = logging.getLogger("notify_sim")

UNAUTHENTICATED = (
    "Request had invalid authentication credentials. Expected OAuth 2 access token, login cookie or other valid "
    "authentication credential."
)


def _bearer(authorization: str | None) -> str:
    if authorization and authorization[:7].lower() == "bearer ":
        return authorization[7:].strip()
    return ""


def create_app(settings: Settings | None = None, clock: Callable[[], float] = time.time) -> FastAPI:
    """Build the simulator. The service account is created (or loaded) here, so the app is ready without lifespan."""
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)
    account = load_or_create(settings)
    tokens = fcm.AccessTokens()
    store = Store(capacity=settings.max_messages, clock=clock)
    log.info("service account ready: %s (project %s)", settings.service_account_file, account.project_id)

    app = FastAPI(title="e-Himaya notify-sim (SIMULATION)", version="0.1.0", docs_url=None, redoc_url=None)
    app.state.settings, app.state.account, app.state.tokens, app.state.store = settings, account, tokens, store

    # ------------------------------------------------------------------ Google OAuth 2.0 (JWT bearer grant)

    @app.post("/oauth2/token")
    async def oauth_token(request: Request) -> JSONResponse:
        form = parse_qs((await request.body()).decode("utf-8", "replace"))
        grant_type, assertion = form.get("grant_type", [""])[0], form.get("assertion", [""])[0]
        if grant_type != fcm.JWT_BEARER:
            return JSONResponse(
                {"error": "unsupported_grant_type", "error_description": "Invalid grant_type: " + grant_type}, 400
            )
        try:
            fcm.verify_assertion(assertion, account, clock())
        except fcm.InvalidGrant as exc:
            return JSONResponse({"error": "invalid_grant", "error_description": str(exc)}, 400)
        return JSONResponse(
            {"access_token": tokens.issue(clock()), "expires_in": fcm.ACCESS_TOKEN_TTL, "token_type": "Bearer"},
            headers={"Cache-Control": "no-store"},
        )

    # ------------------------------------------------------------------ FCM HTTP v1

    @app.post("/v1/projects/{project}/messages:send")
    async def fcm_send(
        project: str, request: Request, authorization: Annotated[str | None, Header()] = None
    ) -> JSONResponse:
        if not tokens.valid(_bearer(authorization), clock()):
            return JSONResponse(
                fcm.google_error(401, "UNAUTHENTICATED", UNAUTHENTICATED),
                401,
                headers={"WWW-Authenticate": 'Bearer realm="https://accounts.google.com/"'},
            )
        if project != account.project_id:
            return JSONResponse(fcm.google_error(404, "NOT_FOUND", "Requested entity was not found."), 404)
        try:
            payload = json.loads(await request.body())
        except ValueError:
            return JSONResponse(
                fcm.google_error(400, "INVALID_ARGUMENT", "Invalid JSON payload received."), status_code=400
            )
        try:
            parsed = fcm.parse_send_request(payload)
        except fcm.InvalidArgument as exc:
            return JSONResponse(exc.body(), 400)
        if parsed.token is not None and parsed.token.startswith(fcm.UNREGISTERED_PREFIX):
            return JSONResponse(fcm.unregistered_body(), 404)
        if parsed.validate_only:
            return JSONResponse({"name": f"projects/{project}/messages/fake_message_id"})
        message_id = f"0:{int(clock() * 1000)}%{secrets.token_hex(8)}"
        item = store.add(
            "push",
            message_id,
            token=parsed.token,
            title=parsed.title,
            body=parsed.body,
            data=parsed.data,
            android_channel=parsed.android_channel,
            priority=parsed.priority,
        )
        log.info("push #%d to %s: %s", item.seq, parsed.token, parsed.title)
        return JSONResponse({"name": f"projects/{project}/messages/{message_id}"})

    # ------------------------------------------------------------------ SMS gateway

    @app.post("/sms/send")
    async def sms_send(request: Request, authorization: Annotated[str | None, Header()] = None) -> JSONResponse:
        if not hmac.compare_digest(_bearer(authorization).encode(), settings.sms_token.encode()):
            return JSONResponse({"error": "unauthorized"}, 401, headers={"WWW-Authenticate": "Bearer"})
        try:
            body: Any = json.loads(await request.body())
        except ValueError:
            return JSONResponse({"error": "invalid_request"}, 400)
        error = sms.validate(body)
        if error:
            return JSONResponse({"error": error}, 400)
        if body["to"] in settings.sms_fail_numbers:
            return JSONResponse({"error": "operator_unavailable"}, 503)
        parts = sms.segments(body["text"])
        message_id = f"sms-{secrets.token_hex(12)}"
        item = store.add(
            "sms", message_id, to=body["to"], text=body["text"], segments=parts.count, encoding=parts.encoding
        )
        log.info("sms #%d to %s (%d %s segments)", item.seq, body["to"], parts.count, parts.encoding)
        return JSONResponse({"id": message_id, "segments": parts.count, "encoding": parts.encoding})

    # ------------------------------------------------------------------ inspection

    @app.get("/api/messages")
    async def list_messages(
        channel: Literal["push", "sms"] | None = None,
        token: str | None = None,
        to: str | None = None,
        after: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ) -> dict[str, Any]:
        page = store.query(channel=channel, token=token, to=to, after=after, limit=limit)
        return {"items": [item.as_json() for item in page.items], "last_seq": page.last_seq}

    @app.delete("/api/messages", status_code=204)
    async def clear_messages() -> Response:
        store.clear()
        return Response(status_code=204)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    page = (
        INBOX_HTML.replace("{{project}}", html.escape(account.project_id))
        .replace("{{public_url}}", html.escape(settings.public_url))
        .replace("{{fail_numbers}}", html.escape(", ".join(sorted(settings.sms_fail_numbers)) or "—"))
    )

    @app.get("/", response_class=HTMLResponse)
    async def inbox() -> HTMLResponse:
        return HTMLResponse(
            page,
            headers={
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; "
                "script-src 'unsafe-inline'; connect-src 'self'; img-src data:",
                "Cache-Control": "no-store",
            },
        )

    return app
