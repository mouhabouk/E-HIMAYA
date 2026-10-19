"""Client of the internal AI inference service (services/ai). Contract: docs/api/phase-3-contract.md §6."""

from typing import Any, Protocol

import httpx

from app.core.config import get_settings


class AiUnavailable(Exception):
    """The service or the model is down: retry later."""


class AiRejected(Exception):
    """The input cannot be processed (undecodable media, invalid output): do not retry."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class AiClient(Protocol):
    async def transcribe(self, url: str) -> dict[str, Any]: ...

    async def translate(self, texts: list[str], source: str) -> dict[str, Any]: ...

    async def embed(self, texts: list[str]) -> dict[str, Any]: ...

    async def extract(self, text: str, reported_category: str) -> dict[str, Any]: ...

    async def health(self) -> dict[str, Any]: ...


class HttpAiClient:
    def __init__(self, base_url: str, token: str, timeout_s: float) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(10, read=timeout_s),
        )

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._http.post(path, json=body)
        except httpx.HTTPError as exc:
            raise AiUnavailable(type(exc).__name__) from exc
        if response.status_code in (502, 422):
            raise AiRejected(str(response.json().get("detail", response.status_code)))
        if response.status_code != 200:
            raise AiUnavailable(f"HTTP {response.status_code}")
        data: dict[str, Any] = response.json()
        return data

    async def transcribe(self, url: str) -> dict[str, Any]:
        return await self._post("/v1/transcribe", {"url": url})

    async def translate(self, texts: list[str], source: str) -> dict[str, Any]:
        return await self._post("/v1/translate", {"texts": texts, "source": source})

    async def embed(self, texts: list[str]) -> dict[str, Any]:
        return await self._post("/v1/embed", {"texts": texts})

    async def extract(self, text: str, reported_category: str) -> dict[str, Any]:
        return await self._post("/v1/extract", {"text": text, "reported_category": reported_category})

    async def health(self) -> dict[str, Any]:
        try:
            response = await self._http.get("/v1/health", timeout=3)
            data: dict[str, Any] = response.json() if response.status_code == 200 else {}
        except (httpx.HTTPError, ValueError):
            data = {}
        return data

    async def close(self) -> None:
        await self._http.aclose()


_client: AiClient | None = None
_default: HttpAiClient | None = None


def get_ai_client() -> AiClient | None:
    """None when no AI service is configured: reports are still scored and grouped by the rules."""
    global _default
    if _client is not None:
        return _client
    settings = get_settings()
    if not settings.ai_service_url or settings.ai_service_token is None:
        return None
    if _default is None:
        _default = HttpAiClient(
            settings.ai_service_url, settings.ai_service_token.get_secret_value(), settings.ai_request_timeout_s
        )
    return _default


def set_ai_client(client: AiClient | None) -> None:
    """Used by tests to inject a fake service."""
    global _client
    _client = client
