"""Live dashboard feed over WebSocket (NFR-01: a report shows on the dashboard within seconds).

Protocol (docs/api/phase-2-contract.md §5): the first client message carries the access token; the
server then pushes the events the user's geographic scope allows. Tokens are renewed in-band.
"""

import asyncio
import time
from typing import Any

import structlog
from anyio import to_thread
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status

from app.core.config import get_settings
from app.core.security import Principal, get_token_verifier
from app.modules.reports.staff_router import READ_ROLES

log = structlog.get_logger()
router = APIRouter()

AUTH_TIMEOUT_S = 10
QUEUE_SIZE = 500
CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_TOO_SLOW = 4408
CLOSE_TRY_LATER = 1013


class _Rejected(Exception):
    def __init__(self, code: int) -> None:
        self.code = code


class LiveClient:
    def __init__(self, websocket: WebSocket, principal: Principal, expires_at: float) -> None:
        self.websocket = websocket
        self.principal = principal
        self.expires_at = expires_at
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(QUEUE_SIZE)

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
        if subject in ("report.created", "report.status_changed"):
            gouvernorat = payload.get("report", {}).get("gouvernorat_code")
        elif subject == "media.stored":
            gouvernorat = payload.get("gouvernorat_code")
        else:
            return
        message = {"type": subject, **payload}
        for client in list(self._clients):
            if not client.can_see(gouvernorat):
                continue
            try:
                client.queue.put_nowait(message)
            except asyncio.QueueFull:
                # A client that cannot keep up is disconnected; it reconnects and reloads the list.
                self.discard(client)
                asyncio.get_running_loop().create_task(_close(client.websocket, CLOSE_TOO_SLOW))


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
    if not principal.is_staff or not principal.roles & frozenset(READ_ROLES):
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
