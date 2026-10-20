"""Client of the local language model (Ollama, the same server and model family as the AI layer, phase 3).

The incident assistant asks for a JSON object constrained by a schema (``format``), at temperature 0, without the
model's reasoning mode. Every failure maps to ``LlmUnavailable`` (503 ``assistant_unavailable``) or ``LlmRejected``
(an answer that is not the expected JSON: treated as "no supported answer", never shown raw).
"""

from typing import Any, Protocol

import httpx

from app.core.config import get_settings


class LlmUnavailable(Exception):
    """Ollama is unreachable, not configured, or the model is not pulled."""


class LlmRejected(Exception):
    """The model answered something that is not the requested JSON."""


class LlmClient(Protocol):
    model: str

    async def chat_json(self, system: str, user: str, schema: dict[str, Any]) -> str: ...


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout_s: float, num_ctx: int) -> None:
        self.model = model
        self._num_ctx = num_ctx
        self._http = httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(10, read=timeout_s))

    async def chat_json(self, system: str, user: str, schema: dict[str, Any]) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "format": schema,
            "stream": False,
            "think": False,
            "keep_alive": "30m",
            "options": {"temperature": 0, "num_ctx": self._num_ctx},
        }
        try:
            response = await self._http.post("/api/chat", json=body)
            if response.status_code == 400 and "think" in response.text:
                # Models without a reasoning mode refuse the "think" option.
                body.pop("think")
                response = await self._http.post("/api/chat", json=body)
        except httpx.HTTPError as exc:
            raise LlmUnavailable(type(exc).__name__) from exc
        if response.status_code == 404:
            raise LlmUnavailable(f"model {self.model} not pulled")
        if response.status_code != 200:
            raise LlmUnavailable(f"HTTP {response.status_code}")
        try:
            content = response.json().get("message", {}).get("content", "")
        except ValueError as exc:
            raise LlmRejected("invalid_json") from exc
        if not isinstance(content, str) or not content.strip():
            raise LlmRejected("empty_answer")
        return content

    async def close(self) -> None:
        await self._http.aclose()


_client: LlmClient | None = None
_default: OllamaClient | None = None


def get_llm() -> LlmClient | None:
    """None when no Ollama server is configured (the assistant answers 503 assistant_unavailable)."""
    global _default
    if _client is not None:
        return _client
    settings = get_settings()
    if not settings.ollama_url:
        return None
    if _default is None:
        _default = OllamaClient(
            settings.ollama_url, settings.assistant_model, settings.assistant_timeout_s, settings.assistant_num_ctx
        )
    return _default


def set_llm(client: LlmClient | None) -> None:
    """Used by tests to inject a fake model."""
    global _client
    _client = client
