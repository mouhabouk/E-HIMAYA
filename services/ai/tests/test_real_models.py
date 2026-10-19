"""Checks against the real models (CI job "AI · real models"): run with ``pytest -m models``.

Needs AI_MODELS_DIR prepared by models/fetch_models.py, a running Ollama with the profile's language model
(AI_OLLAMA_URL, AI_LLM_MODEL) and speech samples in AI_TEST_AUDIO_DIR (generated with espeak-ng in CI).
"""

import functools
import os
import threading
import time
from collections.abc import Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from tests.conftest import AUTH

pytestmark = pytest.mark.models


def arabic(text: str) -> bool:
    return any("؀" <= ch <= "ۿ" for ch in text)


@pytest.fixture(scope="module")
def media_server() -> Iterator[str]:
    directory = os.environ["AI_TEST_AUDIO_DIR"]
    handler = functools.partial(SimpleHTTPRequestHandler, directory=directory)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}/"
    get_settings().media_url_prefix = base
    yield base
    server.shutdown()


def test_health_reports_every_capability_ready(client: TestClient) -> None:
    body = client.get("/v1/health", headers=AUTH).json()
    assert all(capability["ready"] for capability in body.values()), body


def test_french_speech_is_transcribed(client: TestClient, media_server: str) -> None:
    started = time.perf_counter()
    r = client.post("/v1/transcribe", json={"url": f"{media_server}fr.wav"}, headers=AUTH)
    elapsed = time.perf_counter() - started
    assert r.status_code == 200, r.text
    body = r.json()
    print(f"\n  fr ({body['duration_s']:.1f}s audio, {elapsed:.1f}s): {body['text']}")
    assert body["language"] == "fr"
    assert "incendie" in body["text"].lower()


def test_english_speech_is_transcribed(client: TestClient, media_server: str) -> None:
    r = client.post("/v1/transcribe", json={"url": f"{media_server}en.wav"}, headers=AUTH)
    assert r.status_code == 200, r.text
    print(f"\n  en: {r.json()['text']}")
    assert r.json()["language"] == "en"
    assert "fire" in r.json()["text"].lower()


def test_arabic_speech_is_transcribed_in_arabic_script(client: TestClient, media_server: str) -> None:
    r = client.post("/v1/transcribe", json={"url": f"{media_server}ar.wav", "language": "ar"}, headers=AUTH)
    assert r.status_code == 200, r.text
    print(f"\n  ar: {r.json()['text']}")
    assert arabic(r.json()["text"])


def test_corrupted_media_is_refused(client: TestClient, media_server: str) -> None:
    r = client.post("/v1/transcribe", json={"url": f"{media_server}garbage.wav"}, headers=AUTH)
    assert (r.status_code, r.json()["detail"]) == (422, "media_undecodable")


@pytest.mark.parametrize(
    ("source", "text", "expected"),
    [
        ("fr", "Il y a un incendie dans la forêt près de la route.", "حريق"),
        ("en", "There is a fire in the forest near the road.", "حريق"),
    ],
)
def test_translation_to_arabic(client: TestClient, source: str, text: str, expected: str) -> None:
    r = client.post("/v1/translate", json={"texts": [text, "Merci."], "source": source}, headers=AUTH)
    assert r.status_code == 200, r.text
    translated = r.json()["texts"]
    print(f"\n  {text} → {translated[0]}")
    assert len(translated) == 2 and arabic(translated[0])
    assert expected in translated[0]


def test_embeddings_are_multilingual(client: TestClient) -> None:
    texts = [
        "حريق كبير في الغابة",
        "Un grand incendie dans la forêt",
        "Une inondation a coupé la route",
    ]
    r = client.post("/v1/embed", json={"texts": texts}, headers=AUTH)
    assert r.status_code == 200, r.text
    vectors = np.array(r.json()["vectors"])
    assert vectors.shape == (3, 768)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-3)
    fire_fire, fire_flood = float(vectors[0] @ vectors[1]), float(vectors[1] @ vectors[2])
    print(f"\n  similarity fire(ar)/fire(fr) {fire_fire:.3f}, fire/flood {fire_flood:.3f}")
    assert fire_fire > fire_flood


def test_extraction_reads_lives_at_risk(client: TestClient) -> None:
    started = time.perf_counter()
    r = client.post(
        "/v1/extract",
        json={
            "text": "Feu dans un immeuble à Sfax, deux enfants sont bloqués au 3e étage!",
            "reported_category": "fire",
        },
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    print(f"\n  extraction ({time.perf_counter() - started:.1f}s): {body}")
    assert body["category"] == "fire"
    assert body["lives_at_risk"] or body["people_trapped"]
