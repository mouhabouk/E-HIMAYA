"""Contract check run in CI against the real AI service: the core API's client and schemas accept its answers.

cd services/api && uv run python ../ai/tests/api_contract_check.py http://127.0.0.1:8100 <token> <audio-url>
"""

import asyncio
import sys

from app.modules.ai.client import HttpAiClient
from app.modules.reports.schemas import Extraction


async def main(base_url: str, token: str, audio_url: str) -> None:
    client = HttpAiClient(base_url, token, timeout_s=600)
    transcript = await client.transcribe(audio_url)
    assert transcript["text"] and transcript["language"] in ("ar", "fr", "en"), transcript
    translated = await client.translate(["Un incendie près de l'école."], "fr")
    assert len(translated["texts"]) == 1, translated
    embedded = await client.embed(["حريق"])
    assert len(embedded["vectors"][0]) == 768
    extraction = await client.extract("Accident sur la route de Gabès, trois blessés.", "traffic_accident")
    extraction.pop("model")
    Extraction.model_validate(extraction)
    print("API ↔ AI service contract: OK")
    print(f"  transcript: {transcript['text']!r} ({transcript['language']})")
    print(f"  translation: {translated['texts'][0]!r}")
    print(f"  extraction: {extraction}")
    await client.close()


if __name__ == "__main__":
    asyncio.run(main(*sys.argv[1:4]))
