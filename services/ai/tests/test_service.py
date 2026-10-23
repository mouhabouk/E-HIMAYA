import json
from typing import Any

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import mean_pool, split_sentences
from tests.conftest import AUTH

VALID = {
    "language": "fr",
    "category": "fire",
    "lives_at_risk": True,
    "people_trapped": True,
    "injured_count": 2,
    "deaths_reported": False,
    "hazards": ["gas", "gas", "spreading_fire"],
    "keywords": ["incendie", " immeuble ", ""],
    "summary_ar": "حريق في عمارة مع أشخاص عالقين.",
    "confidence": 0.9,
}


def ollama(handler: Any) -> None:
    app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_service_token_is_required(client: TestClient) -> None:
    assert client.post("/v1/embed", json={"texts": ["x"]}).status_code == 401
    assert client.post("/v1/embed", json={"texts": ["x"]}, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/health/live").status_code == 200


def test_missing_models_answer_503(client: TestClient) -> None:
    assert client.post("/v1/embed", json={"texts": ["x"]}, headers=AUTH).json() == {"detail": "model_unavailable"}
    r = client.post("/v1/translate", json={"texts": ["Bonjour"], "source": "fr"}, headers=AUTH)
    assert r.status_code == 503
    r = client.post("/v1/transcribe", json={"url": "http://seaweedfs:8333/x"}, headers=AUTH)
    assert r.status_code == 503


def test_health_lists_capabilities(client: TestClient) -> None:
    ollama(lambda request: httpx.Response(200, json={"models": [{"name": "qwen3:8b"}]}))
    body = client.get("/v1/health", headers=AUTH).json()
    assert body["transcribe"] == {"ready": False, "model": None, "detail": "not installed"}
    assert body["extract"]["ready"] is True


def test_extract_validates_and_cleans_the_model_output(client: TestClient) -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        return httpx.Response(200, json={"message": {"content": json.dumps(VALID)}})

    ollama(handler)
    r = client.post(
        "/v1/extract",
        json={"text": "Incendie dans un immeuble, deux blessés", "reported_category": "fire"},
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["hazards"] == ["gas", "spreading_fire"]
    assert out["keywords"] == ["incendie", "immeuble"]
    assert out["model"] == "qwen3:8b"
    # Constrained decoding: the JSON schema is sent, the report is delimited as data.
    assert seen[0]["format"]["properties"]["category"]["enum"][0] == "sos"
    assert "<report>" in seen[0]["messages"][1]["content"]
    assert seen[0]["options"]["temperature"] == 0


def test_extract_retries_without_think_for_models_that_refuse_it(client: TestClient) -> None:
    calls: list[bool] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append("think" in body)
        if "think" in body:
            return httpx.Response(400, json={"error": '"llama3" does not support thinking'})
        return httpx.Response(200, json={"message": {"content": json.dumps(VALID)}})

    ollama(handler)
    r = client.post("/v1/extract", json={"text": "x", "reported_category": "other"}, headers=AUTH)
    assert r.status_code == 200 and calls == [True, False]


@pytest.mark.parametrize(
    ("response", "status", "detail"),
    [
        (httpx.Response(200, json={"message": {"content": '{"category": "volcano"}'}}), 502, "invalid_model_output"),
        (httpx.Response(404, json={"error": "model not found"}), 503, "model_unavailable"),
        (httpx.Response(500, json={"error": "boom"}), 503, "model_unavailable"),
    ],
)
def test_extract_failures(client: TestClient, response: httpx.Response, status: int, detail: str) -> None:
    ollama(lambda request: response)
    r = client.post("/v1/extract", json={"text": "x", "reported_category": "other"}, headers=AUTH)
    assert (r.status_code, r.json()["detail"]) == (status, detail)


def test_extract_when_ollama_is_down(client: TestClient) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    ollama(handler)
    r = client.post("/v1/extract", json={"text": "x", "reported_category": "other"}, headers=AUTH)
    assert r.status_code == 503


def test_media_url_must_point_at_the_object_store(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app import models

    monkeypatch.setattr(models.whisper, "get", lambda: object())
    for url in ("http://169.254.169.254/latest/meta-data", "file:///etc/passwd", "http://seaweedfs:8333.evil/x"):
        r = client.post("/v1/transcribe", json={"url": url}, headers=AUTH)
        assert (r.status_code, r.json()["detail"]) == (422, "media_url_not_allowed"), url


def test_undecodable_media_gives_a_stable_code(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from app import models

    fake = SimpleNamespace(feature_extractor=SimpleNamespace(sampling_rate=16000))
    monkeypatch.setattr(models.whisper, "get", lambda: fake)
    ollama(lambda request: httpx.Response(200, content=b"not audio at all" * 1000))
    r = client.post("/v1/transcribe", json={"url": "http://seaweedfs:8333/x.wav"}, headers=AUTH)
    # PyAV's message names the temporary file: it must not reach the caller.
    assert (r.status_code, r.json()["detail"]) == (422, "media_undecodable")


def test_mean_pool_ignores_padding_and_normalizes() -> None:
    hidden = np.array([[[1.0, 0.0], [3.0, 0.0], [100.0, 100.0]], [[0.0, 2.0], [0.0, 2.0], [0.0, 2.0]]])
    pooled = mean_pool(hidden, [2, 3], 2)
    assert np.allclose(pooled, [[1.0, 0.0], [0.0, 1.0]])


def test_split_sentences() -> None:
    assert split_sentences("Le feu avance. Deux blessés!\nVenez vite؟ شكرا") == [
        "Le feu avance.",
        "Deux blessés!",
        "Venez vite؟",
        "شكرا",
    ]


def test_installed_pyav_decodes_audio_for_faster_whisper(tmp_path: Any) -> None:
    # Guards the av pin: a PyAV that drops an argument faster-whisper passes turns every upload into media_undecodable.
    import wave

    from faster_whisper.audio import decode_audio

    path = tmp_path / "tone.wav"
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        tone = (np.sin(2 * np.pi * 440 * np.arange(16000) / 16000) * 8000).astype("<i2")
        out.writeframes(tone.tobytes())
    audio = decode_audio(str(path), sampling_rate=16000)
    assert 15000 < len(audio) <= 16000
