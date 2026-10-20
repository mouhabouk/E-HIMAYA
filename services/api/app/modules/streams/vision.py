"""Client of the internal vision service (services/vision). Contract: docs/api/phase-6-contract.md §5.

The vision service is optional and may be down or saturated at any time: callers never wait on it inside a request.
Stream watch/unwatch calls are made by the worker (``streams.worker``) with retries; uploaded images are analysed by
the same worker after the media verification.
"""

from typing import Any, Protocol

import httpx

from app.core.config import get_settings


class VisionUnavailable(Exception):
    """The service is down or answered an unexpected status: retry later."""


class VisionBusy(VisionUnavailable):
    """The service already watches VISION_MAX_STREAMS streams (429): retry later."""


class VisionRejected(Exception):
    """The input cannot be processed (undecodable image): do not retry."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class VisionClient(Protocol):
    async def watch(self, stream_id: str, rtsp_url: str, callback_url: str) -> None: ...

    async def unwatch(self, stream_id: str) -> None: ...

    async def detect(self, image: bytes, content_type: str) -> dict[str, Any]: ...


class HttpVisionClient:
    def __init__(self, base_url: str, token: str, timeout_s: float) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url, headers={"Authorization": f"Bearer {token}"}, timeout=httpx.Timeout(timeout_s)
        )

    async def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise VisionUnavailable(type(exc).__name__) from exc
        if response.status_code == 429:
            raise VisionBusy("busy")
        return response

    async def watch(self, stream_id: str, rtsp_url: str, callback_url: str) -> None:
        response = await self._send(
            "PUT", f"/v1/streams/{stream_id}", json={"rtsp_url": rtsp_url, "callback_url": callback_url}
        )
        if response.status_code not in (200, 201, 202, 204):
            raise VisionUnavailable(f"HTTP {response.status_code}")

    async def unwatch(self, stream_id: str) -> None:
        response = await self._send("DELETE", f"/v1/streams/{stream_id}")
        if response.status_code not in (200, 202, 204, 404):
            raise VisionUnavailable(f"HTTP {response.status_code}")

    async def detect(self, image: bytes, content_type: str) -> dict[str, Any]:
        response = await self._send("POST", "/v1/detect", files={"image": ("image", image, content_type)})
        if response.status_code in (400, 413, 415, 422):
            try:
                detail = str(response.json().get("detail", response.status_code))
            except ValueError:
                detail = str(response.status_code)
            raise VisionRejected(detail)
        if response.status_code != 200:
            raise VisionUnavailable(f"HTTP {response.status_code}")
        try:
            data: dict[str, Any] = response.json()
        except ValueError as exc:
            raise VisionUnavailable("invalid_json") from exc
        return data

    async def close(self) -> None:
        await self._http.aclose()


_client: VisionClient | None = None
_default: HttpVisionClient | None = None


def get_vision_client() -> VisionClient | None:
    """None when no vision service is configured: streams and images are simply not analysed."""
    global _default
    if _client is not None:
        return _client
    settings = get_settings()
    if not settings.vision_service_url or settings.vision_api_token is None:
        return None
    if _default is None:
        _default = HttpVisionClient(
            settings.vision_service_url, settings.vision_api_token.get_secret_value(), settings.vision_request_timeout_s
        )
    return _default


def set_vision_client(client: VisionClient | None) -> None:
    """Used by tests to inject a fake service."""
    global _client
    _client = client
