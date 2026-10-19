"""Live positions of ready volunteers (FR-A-022), kept in Valkey only (architecture: «مواقع المتطوعين
اللحظية: Valkey — خلال الجاهزية فقط، دون أرشفة»).

A position is stored with an expiry equal to the end of readiness and deleted when readiness ends; it
is never written to PostgreSQL. Without Valkey (development, tests) an in-process store is used.

Keys: ``vol:pos:<user_id>`` (JSON, expires with readiness) and the geo index ``vol:geo``; index members
whose position key has expired are pruned when they are met.
"""

import json
import math
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from redis.asyncio import Redis, from_url

from app.core.config import get_settings

GEO_KEY = "vol:geo"


def _pos_key(user_id: uuid.UUID) -> str:
    return f"vol:pos:{user_id}"


@dataclass(frozen=True, slots=True)
class Fix:
    lat: float
    lon: float
    accuracy_m: float | None
    at: datetime


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (haversine)."""
    r = 6_371_008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _text(value: Any) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


class PresenceStore(Protocol):
    async def put(self, user_id: uuid.UUID, fix: Fix, until: datetime) -> None: ...

    async def get_many(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, Fix]: ...

    async def clear(self, user_id: uuid.UUID) -> None: ...

    async def nearby(self, lat: float, lon: float, radius_m: float, limit: int) -> list[tuple[uuid.UUID, float]]: ...

    async def within(self, bbox: tuple[float, float, float, float]) -> dict[uuid.UUID, Fix]: ...


class MemoryPresence:
    def __init__(self) -> None:
        self._fixes: dict[uuid.UUID, tuple[Fix, float]] = {}

    def _live(self) -> dict[uuid.UUID, Fix]:
        now = time.time()
        for user_id in [u for u, (_, until) in self._fixes.items() if until <= now]:
            del self._fixes[user_id]
        return {u: f for u, (f, _) in self._fixes.items()}

    async def put(self, user_id: uuid.UUID, fix: Fix, until: datetime) -> None:
        self._fixes[user_id] = (fix, until.timestamp())

    async def get_many(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, Fix]:
        live = self._live()
        return {u: live[u] for u in user_ids if u in live}

    async def clear(self, user_id: uuid.UUID) -> None:
        self._fixes.pop(user_id, None)

    async def nearby(self, lat: float, lon: float, radius_m: float, limit: int) -> list[tuple[uuid.UUID, float]]:
        found = [(u, distance_m(lat, lon, f.lat, f.lon)) for u, f in self._live().items()]
        return sorted((x for x in found if x[1] <= radius_m), key=lambda x: x[1])[:limit]

    async def within(self, bbox: tuple[float, float, float, float]) -> dict[uuid.UUID, Fix]:
        min_lon, min_lat, max_lon, max_lat = bbox
        return {u: f for u, f in self._live().items() if min_lon <= f.lon <= max_lon and min_lat <= f.lat <= max_lat}


class ValkeyPresence:
    def __init__(self, client: Redis) -> None:
        self._client = client

    async def put(self, user_id: uuid.UUID, fix: Fix, until: datetime) -> None:
        value = json.dumps({"lat": fix.lat, "lon": fix.lon, "acc": fix.accuracy_m, "at": fix.at.isoformat()})
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.set(_pos_key(user_id), value, exat=int(until.timestamp()))
            pipe.geoadd(GEO_KEY, (fix.lon, fix.lat, str(user_id)))
            await pipe.execute()

    async def get_many(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, Fix]:
        if not user_ids:
            return {}
        values = await self._client.mget([_pos_key(u) for u in user_ids])
        out: dict[uuid.UUID, Fix] = {}
        for user_id, raw in zip(user_ids, values, strict=True):
            if raw:
                data = json.loads(raw)
                out[user_id] = Fix(data["lat"], data["lon"], data["acc"], datetime.fromisoformat(data["at"]))
        return out

    async def clear(self, user_id: uuid.UUID) -> None:
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.delete(_pos_key(user_id))
            pipe.zrem(GEO_KEY, str(user_id))
            await pipe.execute()

    async def _live(self, members: list[uuid.UUID]) -> dict[uuid.UUID, Fix]:
        fixes = await self.get_many(members)
        stale = [str(u) for u in members if u not in fixes]
        if stale:
            await self._client.zrem(GEO_KEY, *stale)
        return fixes

    async def nearby(self, lat: float, lon: float, radius_m: float, limit: int) -> list[tuple[uuid.UUID, float]]:
        raw = await self._client.geosearch(
            GEO_KEY,
            longitude=lon,
            latitude=lat,
            radius=radius_m,
            unit="m",
            sort="ASC",
            withdist=True,
            count=limit * 3,
        )
        pairs: list[Any] = list(raw)
        members = [(uuid.UUID(_text(m)), float(d)) for m, d in pairs]
        live = await self._live([u for u, _ in members])
        return [(u, d) for u, d in members if u in live][:limit]

    async def within(self, bbox: tuple[float, float, float, float]) -> dict[uuid.UUID, Fix]:
        min_lon, min_lat, max_lon, max_lat = bbox
        center_lon, center_lat = (min_lon + max_lon) / 2, (min_lat + max_lat) / 2
        width = distance_m(center_lat, min_lon, center_lat, max_lon)
        height = distance_m(min_lat, center_lon, max_lat, center_lon)
        raw = await self._client.geosearch(
            GEO_KEY,
            longitude=center_lon,
            latitude=center_lat,
            width=max(width, 1),
            height=max(height, 1),
            unit="m",
            count=5000,
        )
        members = [uuid.UUID(_text(m)) for m in raw]
        return await self._live(members)


_store: PresenceStore | None = None


def get_presence() -> PresenceStore:
    global _store
    if _store is None:
        url = get_settings().valkey_url
        _store = ValkeyPresence(from_url(url, socket_timeout=2)) if url else MemoryPresence()
    return _store


def set_presence(store: PresenceStore | None) -> None:
    global _store
    _store = store


def now() -> datetime:
    return datetime.now(UTC)
