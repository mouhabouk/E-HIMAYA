"""Client of the MediaMTX control API (v3), used to kick the publisher of a stopped or over-long stream.

The API answers only to the internal user ``MEDIAMTX_API_USER`` / ``MEDIAMTX_API_PASSWORD`` (MediaMTX asks
/internal/mediamtx/auth with ``action=api``). Without the API configured, a stopped stream is still refused at its
next publish attempt, but a running publisher keeps sending until it disconnects: callers log that.
"""

from typing import Protocol
from urllib.parse import quote

import httpx
import structlog

from app.core.config import get_settings

log = structlog.get_logger()

# MediaMTX source type of a publisher → kick endpoint (API v3, MediaMTX ≥ 1.20).
_KICK = {
    "webRTCSession": "/v3/webrtc/sessions/kick/{id}",
    "rtspSession": "/v3/rtsp/sessions/kick/{id}",
    "rtspsSession": "/v3/rtsps/sessions/kick/{id}",
    "rtmpConn": "/v3/rtmp/conns/kick/{id}",
    "rtmpsConn": "/v3/rtmps/conns/kick/{id}",
    "srtConn": "/v3/srt/conns/kick/{id}",
    "moqSession": "/v3/moq/sessions/kick/{id}",
}


class MediamtxClient(Protocol):
    async def kick(self, path: str) -> bool:
        """Disconnect the publisher of ``path``; True when one was kicked."""
        ...


class HttpMediamtxClient:
    def __init__(self, base_url: str, user: str, password: str) -> None:
        self._http = httpx.AsyncClient(base_url=base_url, auth=(user, password), timeout=httpx.Timeout(5))

    async def kick(self, path: str) -> bool:
        try:
            response = await self._http.get(f"/v3/paths/get/{quote(path, safe='/')}")
            if response.status_code == 404:
                return False
            response.raise_for_status()
            source = response.json().get("source") or {}
            endpoint = _KICK.get(str(source.get("type")))
            if endpoint is None or not source.get("id"):
                return False
            kicked = await self._http.post(endpoint.format(id=quote(str(source["id"]), safe="")))
            return kicked.status_code == 200
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("mediamtx.kick_failed", path=path, error=type(exc).__name__)
            return False

    async def close(self) -> None:
        await self._http.aclose()


_client: MediamtxClient | None = None
_default: HttpMediamtxClient | None = None


def get_mediamtx() -> MediamtxClient | None:
    global _default
    if _client is not None:
        return _client
    settings = get_settings()
    if not settings.mediamtx_api_url or settings.mediamtx_api_password is None:
        return None
    if _default is None:
        _default = HttpMediamtxClient(
            settings.mediamtx_api_url, settings.mediamtx_api_user, settings.mediamtx_api_password.get_secret_value()
        )
    return _default


def set_mediamtx(client: MediamtxClient | None) -> None:
    """Used by tests to inject a fake MediaMTX."""
    global _client
    _client = client


async def kick(path: str) -> None:
    """Best effort: never raises, never blocks a request for more than the client timeout."""
    client = get_mediamtx()
    if client is None:
        log.info("mediamtx.kick_skipped", path=path, reason="api_not_configured")
        return
    if await client.kick(path):
        log.info("mediamtx.kicked", path=path)
