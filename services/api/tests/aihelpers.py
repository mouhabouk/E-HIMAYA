"""Helpers shared by the AI and incident tests: a fake AI service, report factories, random places."""

import math
import random
import uuid
from collections.abc import Callable
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_sessionmaker
from app.modules.ai import pipeline
from tests.conftest import FakeStore, report_body

Staff = Callable[..., dict[str, str]]
VECTOR = [1.0] + [0.0] * 767


def spot(base: tuple[float, float] | None = None, east_m: float = 0.0) -> dict[str, float]:
    """A random point inland in the gouvernorat of Sfax, or ``east_m`` metres east of ``base``."""
    if base is None:
        return {
            "lat": round(random.uniform(34.55, 34.95), 6),
            "lon": round(random.uniform(10.25, 10.55), 6),
            "accuracy_m": 10.0,
        }
    lat, lon = base
    return {"lat": lat, "lon": lon + east_m / (111_320 * math.cos(math.radians(lat))), "accuracy_m": 10.0}


class FakeAi:
    """In-process stand-in for services/ai with programmable answers."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.fail: dict[str, Exception] = {}
        self.extraction: dict[str, Any] = {
            "language": "fr",
            "category": "fire",
            "lives_at_risk": True,
            "people_trapped": True,
            "injured_count": 2,
            "deaths_reported": False,
            "hazards": ["gas"],
            "keywords": ["incendie", "immeuble"],
            "summary_ar": "حريق في عمارة مع طفلين عالقين.",
            "confidence": 0.9,
        }
        self.vector = VECTOR
        self.transcript = {"text": "Il y a le feu au deuxième étage.", "language": "fr"}
        self.on_extract: Callable[[], Any] | None = None

    def _check(self, name: str, arg: Any) -> None:
        self.calls.append((name, arg))
        if name in self.fail:
            raise self.fail[name]

    async def transcribe(self, url: str) -> dict[str, Any]:
        self._check("transcribe", url)
        return {
            **self.transcript,
            "language_probability": 0.97,
            "duration_s": 4.2,
            "segments": [{}],
            "model": "whisper-test",
        }

    async def translate(self, texts: list[str], source: str) -> dict[str, Any]:
        self._check("translate", (texts, source))
        return {"texts": [f"ترجمة: {t}" for t in texts], "model": f"opus-mt-{source}-ar"}

    async def embed(self, texts: list[str]) -> dict[str, Any]:
        self._check("embed", texts)
        return {"vectors": [self.vector for _ in texts], "dim": len(self.vector), "model": "e5-test"}

    async def extract(self, text: str, reported_category: str) -> dict[str, Any]:
        self._check("extract", text)
        if self.on_extract is not None:
            await self.on_extract()
        return {**self.extraction, "model": "qwen3-test"}

    async def health(self) -> dict[str, Any]:
        return {"extract": {"ready": True, "model": "qwen3-test"}}


async def create(client: httpx.AsyncClient, headers: dict[str, str], **kwargs: Any) -> dict[str, Any]:
    r = await client.post("/api/v1/reports", json=report_body(**kwargs), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def analyse(report_id: str, ai: Any, store: FakeStore | None = None) -> bool:
    return await pipeline.analyze_one(get_sessionmaker(), ai, store or FakeStore(), only=uuid.UUID(report_id))


async def detail(client: httpx.AsyncClient, staff: Staff, report_id: str) -> dict[str, Any]:
    r = await client.get(f"/api/v1/staff/reports/{report_id}", headers=staff(gouvernorat=None))
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


async def add_audio(session: AsyncSession, store: FakeStore, report_id: str, kind: str = "audio") -> str:
    key = f"uploads/{uuid.uuid4().hex}"
    store.objects[key] = b"fake-audio"
    media_id = await session.scalar(
        text(
            "INSERT INTO reports.media (report_id, kind, object_key, sha256, bytes, content_type, status, stored_at) "
            "VALUES (:r, :k, :key, :sha, 10, 'audio/mp4', 'stored', now()) RETURNING id"
        ),
        {"r": report_id, "k": kind, "key": key, "sha": "0" * 64},
    )
    await pipeline.enqueue(session, uuid.UUID(report_id))
    await session.commit()
    return str(media_id)
