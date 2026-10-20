"""Live dashboard feed over WebSocket (NFR-01: a report shows on the dashboard within seconds).

Protocol (docs/api/phase-2-contract.md §5): the first client message carries the access token; the
server then pushes the events the user's geographic scope allows. Tokens are renewed in-band.
"""

import asyncio
import time
from collections.abc import Callable
from typing import Any

import structlog
from anyio import to_thread
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status

from app.core.config import get_settings
from app.core.security import Principal, Role, get_token_verifier
from app.modules.reports.staff_router import READ_ROLES
from app.modules.telephony.domain import CALL_ROLES, mask_number

log = structlog.get_logger()
router = APIRouter()

AUTH_TIMEOUT_S = 10
QUEUE_SIZE = 500
CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_TOO_SLOW = 4408
CLOSE_TRY_LATER = 1013
# Institutions events (phase 4) also go to the institutions auditor, who does not read reports;
# notification events (phase 5) go to those who write them; levels and directives to every staff member.
EDITOR_ROLES = frozenset({Role.CONTENT_EDITOR, Role.OPS_MANAGER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE})


class _Rejected(Exception):
    def __init__(self, code: int) -> None:
        self.code = code


class LiveClient:
    def __init__(self, websocket: WebSocket, principal: Principal, expires_at: float) -> None:
        self.websocket = websocket
        self.principal = principal
        self.expires_at = expires_at
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(QUEUE_SIZE)

    @property
    def reads_reports(self) -> bool:
        return bool(self.principal.roles & frozenset(READ_ROLES))

    def allowed(self, audience: str) -> bool:
        roles = self.principal.roles
        if audience == "reports":
            return self.reads_reports
        if audience == "orgs":
            return self.reads_reports or Role.ORG_AUDITOR in roles
        if audience == "editors":
            return bool(roles & EDITOR_ROLES)
        return True

    def can_see(self, gouvernorat_code: int | None) -> bool:
        if self.principal.is_national:
            return True
        return gouvernorat_code is not None and self.principal.can_access_gouvernorat(gouvernorat_code)


class LiveHub:
    def __init__(self) -> None:
        self._clients: set[LiveClient] = set()

    @property
    def size(self) -> int:
        return len(self._clients)

    def add(self, client: LiveClient) -> None:
        self._clients.add(client)

    def discard(self, client: LiveClient) -> None:
        self._clients.discard(client)

    async def on_event(self, subject: str, payload: dict[str, Any]) -> None:
        route = _route(subject, payload)
        if route is None:
            return
        audience, visible = route
        message = {"type": subject, **payload}
        masked = _masked_call(message) if subject.startswith("call.") else message
        for client in list(self._clients):
            if not client.allowed(audience) or not visible(client):
                continue
            try:
                client.queue.put_nowait(message if client.principal.roles & CALL_ROLES else masked)
            except asyncio.QueueFull:
                # A client that cannot keep up is disconnected; it reconnects and reloads the list.
                self.discard(client)
                asyncio.get_running_loop().create_task(_close(client.websocket, CLOSE_TOO_SLOW))


def _in(gouvernorat: int | None) -> Callable[[LiveClient], bool]:
    return lambda client: client.can_see(gouvernorat)


def _among(codes: list[int] | None, everywhere_when_empty: bool = True) -> Callable[[LiveClient], bool]:
    def visible(client: LiveClient) -> bool:
        if client.principal.is_national:
            return True
        if not codes:
            return everywhere_when_empty
        return client.principal.gouvernorat_code in codes

    return visible


def _masked_call(message: dict[str, Any]) -> dict[str, Any]:
    """Telephony events (phase 7) for readers without call access: the caller number keeps its last 2 digits."""
    call = message.get("call")
    if not isinstance(call, dict) or not call.get("caller_number"):
        return message
    number = call["caller_number"]
    return {**message, "call": {**call, "caller_number": mask_number(number), "caller_masked": True}}


def _codes(payload: dict[str, Any], fallback: int | None) -> Callable[[LiveClient], bool]:
    """Phase 9 §5.6: national, or the client's code in ``gouvernorat_codes`` (lead + participants + critical
    candidates); an empty list is national only. Events published before phase 9 fall back to one gouvernorat."""
    if "gouvernorat_codes" in payload:
        return _among(payload.get("gouvernorat_codes"), everywhere_when_empty=False)
    return _in(fallback)


def _rooms(*rooms: Any) -> Callable[[LiveClient], bool]:
    """National, or one of the rooms named (``g:<code>``; ``central`` is national)."""
    codes = []
    for room in rooms:
        if isinstance(room, str) and room.startswith("g:") and room[2:].isdigit():
            codes.append(int(room[2:]))
    return _among(codes, everywhere_when_empty=False)


def _late_scope(payload: dict[str, Any]) -> Callable[[LiveClient], bool]:
    """``report.late``: national, and the room the report belongs to (its claim, else its gouvernorat)."""
    report = payload.get("report") or {}
    code = report.get("gouvernorat_code")
    return _rooms(report.get("claimed_room"), f"g:{code}" if code is not None else None)


def _breakglass_scope(payload: dict[str, Any]) -> Callable[[LiveClient], bool]:
    holder = payload.get("subject")

    def visible(client: LiveClient) -> bool:
        principal = client.principal
        return principal.subject == holder or (Role.SECURITY_ADMIN in principal.roles and principal.is_national)

    return visible


def _call_scope(subject: str, payload: dict[str, Any]) -> Callable[[LiveClient], bool]:
    # A ringing call not located yet is in the shared queue every operator sees; once answered or ended an unlocated
    # call is national only, plus the operator who took it (phase 9 §5.6). Operators always see the calls they took.
    code = payload.get("gouvernorat_code")
    operator = (payload.get("call") or {}).get("operator_user_id")
    shared = subject == "call.ringing" and code is None

    def visible(client: LiveClient) -> bool:
        if shared or client.principal.subject == operator:
            return True
        return client.can_see(code) if code is not None else client.principal.is_national

    return visible


def _route(subject: str, payload: dict[str, Any]) -> tuple[str, Callable[[LiveClient], bool]] | None:
    """Who may receive an event: an audience (``reports``, ``orgs``, ``staff``, ``editors``) and a scope test."""
    if subject in ("report.created", "report.status_changed", "report.enriched", "report.claimed"):
        return "reports", _codes(payload, payload.get("report", {}).get("gouvernorat_code"))
    if subject == "report.late":
        return "reports", _late_scope(payload)
    if subject == "report.escalation":
        return "reports", _rooms(payload.get("from_room"), payload.get("to_room"))
    if subject == "incident.updated":
        return "reports", _codes(payload, payload.get("incident", {}).get("gouvernorat_code"))
    if subject == "media.stored":
        return "reports", _in(payload.get("gouvernorat_code"))
    if subject in ("stream.started", "stream.ended", "stream.location", "stream.alert", "stream.recording"):
        # Live streams (phase 6) are scoped like the reports they belong to (fixed sources by their gouvernorat).
        return "reports", _in(payload.get("gouvernorat_code"))
    if subject in ("call.ringing", "call.answered", "call.ended", "call.recording"):
        return "reports", _call_scope(subject, payload)
    if subject in ("assignment.updated", "callout.updated", "resource_request.updated"):
        return "reports", _codes(payload, payload.get("gouvernorat_code"))
    if subject == "resource.updated":
        return "reports", _codes(payload, payload.get("resource", {}).get("gouvernorat_code"))
    if subject == "volunteer.updated":
        return "reports", _in(payload.get("volunteer", {}).get("gouvernorat_code"))
    if subject == "org.updated":
        return "orgs", _in(payload.get("org", {}).get("gouvernorat_code"))
    if subject == "certificate.updated":
        return "orgs", _in(payload.get("certificate", {}).get("gouvernorat_code"))
    if subject in ("oplevel.changed", "settings.changed"):
        # Every staff member sees the national situation and the platform settings (not personal data).
        return "staff", lambda client: True
    if subject.startswith("breakglass."):
        # Break-glass grants (phase 9 §6.1): the national security admins and the holder only.
        return "staff", _breakglass_scope(payload)
    if subject == "directive.issued":
        directive = payload.get("directive", {})
        return "staff", _among(directive.get("gouvernorat_codes"))
    if subject == "weather.suggestion":
        # Suggested weather alerts (phase 7) go to those who write alerts, scoped to the suggestion's gouvernorats.
        return "editors", _among(payload.get("suggestion", {}).get("gouvernorat_codes"))
    if subject in ("analytics.report_ready", "analytics.report_failed"):
        # Reports repository (phase 8): only the creator and the recipients of the document are told.
        recipients = set(payload.get("recipients") or [])
        return "staff", lambda client: client.principal.subject in recipients
    if subject in ("notification.updated", "alert.issued"):
        area = payload.get("message", {}).get("area", {})
        if area.get("polygon"):
            # Phase 9 §5.6: editors whose gouvernorat the polygon intersects (computed by notify), national always.
            return "editors", _among(payload.get("gouvernorat_codes"), everywhere_when_empty=False)
        return "editors", _among(area.get("gouvernorat_codes"))
    return None


hub = LiveHub()


async def _close(websocket: WebSocket, code: int) -> None:
    try:
        await websocket.close(code)
    except Exception:  # already closed
        log.debug("live.close_failed", code=code)


async def _authenticate(message: Any) -> tuple[Principal, float]:
    if not isinstance(message, dict) or message.get("type") != "auth" or not isinstance(message.get("token"), str):
        raise _Rejected(CLOSE_UNAUTHORIZED)
    try:
        principal = await to_thread.run_sync(get_token_verifier().verify, message["token"])
    except HTTPException as exc:
        codes = {status.HTTP_403_FORBIDDEN: CLOSE_FORBIDDEN, status.HTTP_503_SERVICE_UNAVAILABLE: CLOSE_TRY_LATER}
        raise _Rejected(codes.get(exc.status_code, CLOSE_UNAUTHORIZED)) from exc
    if not principal.is_staff or not principal.roles:
        raise _Rejected(CLOSE_FORBIDDEN)
    return principal, float(principal.claims["exp"])


def _origin_allowed(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")
    allowed = get_settings().api_cors_origins
    return origin is None or not allowed or origin.rstrip("/") in allowed


async def _sender(client: LiveClient) -> None:
    while True:
        message = await client.queue.get()
        await client.websocket.send_json(message)


@router.websocket("/api/v1/staff/live")
async def live(websocket: WebSocket) -> None:
    if not _origin_allowed(websocket):
        await websocket.close(CLOSE_FORBIDDEN)
        return
    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_json(), AUTH_TIMEOUT_S)
        principal, expires_at = await _authenticate(first)
    except (TimeoutError, ValueError, WebSocketDisconnect):
        await _close(websocket, CLOSE_UNAUTHORIZED)
        return
    except _Rejected as rejected:
        await _close(websocket, rejected.code)
        return

    client = LiveClient(websocket, principal, expires_at)
    hub.add(client)
    sender = asyncio.create_task(_sender(client))
    await websocket.send_json({"type": "ready"})
    try:
        while True:
            remaining = client.expires_at - time.time()
            if remaining <= 0:
                await _close(websocket, CLOSE_UNAUTHORIZED)
                return
            try:
                message = await asyncio.wait_for(websocket.receive_json(), remaining)
            except TimeoutError:
                continue  # loop re-checks expiry
            if isinstance(message, dict) and message.get("type") == "ping":
                await client.queue.put({"type": "pong"})
            elif isinstance(message, dict) and message.get("type") == "auth":
                renewed, renewed_exp = await _authenticate(message)
                if renewed.subject != client.principal.subject:
                    raise _Rejected(CLOSE_FORBIDDEN)
                client.principal, client.expires_at = renewed, renewed_exp
    except _Rejected as rejected:
        await _close(websocket, rejected.code)
    except (WebSocketDisconnect, ValueError):
        pass
    finally:
        hub.discard(client)
        sender.cancel()
