"""Domain events: transactional outbox + relay to NATS JetStream + in-process fan-out.

1. ``emit`` writes an ``events.outbox`` row in the caller's transaction, so an event exists if and only
   if the change it describes was committed.
2. ``relay_pending`` (run by every API instance; ``SKIP LOCKED`` shares the work) publishes pending rows
   to the bus and marks them published. JetStream de-duplicates on ``Nats-Msg-Id`` = outbox id.
3. Every instance subscribes to the bus and hands events to local listeners (dashboard WebSockets).
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Protocol

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings

log = structlog.get_logger()

SUBJECT_PREFIX = "ehimaya."
STREAM_NAME = "EHIMAYA"

Listener = Callable[[str, dict[str, Any]], Awaitable[None]]


async def emit(session: AsyncSession, subject: str, payload: dict[str, Any]) -> None:
    """Queue an event inside the current transaction (the caller commits)."""
    await session.execute(
        text("INSERT INTO events.outbox (subject, payload) VALUES (:subject, CAST(:payload AS jsonb))"),
        {"subject": subject, "payload": json.dumps(payload, default=str, ensure_ascii=False)},
    )


class EventBus(Protocol):
    async def publish(self, subject: str, payload: dict[str, Any], msg_id: str) -> None: ...

    def add_listener(self, listener: Listener) -> None: ...

    async def close(self) -> None: ...


class LocalBus:
    """Single-process bus used when NATS is not configured (development, tests)."""

    def __init__(self) -> None:
        self._listeners: list[Listener] = []

    def add_listener(self, listener: Listener) -> None:
        self._listeners.append(listener)

    async def publish(self, subject: str, payload: dict[str, Any], msg_id: str) -> None:
        await _dispatch(self._listeners, subject, payload)

    async def close(self) -> None:
        self._listeners.clear()


class NatsBus:
    def __init__(self) -> None:
        self._listeners: list[Listener] = []
        self._nc: Any = None
        self._js: Any = None

    async def connect(self, url: str) -> None:
        import nats
        from nats.js.api import StreamConfig
        from nats.js.errors import BadRequestError

        self._nc = await nats.connect(url, name="ehimaya-api", max_reconnect_attempts=-1, reconnect_time_wait=2)
        self._js = self._nc.jetstream()
        config = StreamConfig(
            name=STREAM_NAME,
            subjects=[f"{SUBJECT_PREFIX}>"],
            max_age=7 * 24 * 3600,
            duplicate_window=2 * 60,
        )
        try:
            await self._js.add_stream(config)
        except BadRequestError:
            await self._js.update_stream(config)
        await self._nc.subscribe(f"{SUBJECT_PREFIX}>", cb=self._on_message)

    async def _on_message(self, msg: Any) -> None:
        try:
            payload = json.loads(msg.data)
        except ValueError:
            log.warning("events.bad_message", subject=msg.subject)
            return
        await _dispatch(self._listeners, msg.subject.removeprefix(SUBJECT_PREFIX), payload)

    def add_listener(self, listener: Listener) -> None:
        self._listeners.append(listener)

    async def publish(self, subject: str, payload: dict[str, Any], msg_id: str) -> None:
        data = json.dumps(payload, default=str, ensure_ascii=False).encode()
        await self._js.publish(f"{SUBJECT_PREFIX}{subject}", data, headers={"Nats-Msg-Id": msg_id}, timeout=5)

    async def close(self) -> None:
        if self._nc is not None:
            await self._nc.drain()
            self._nc = None


async def _dispatch(listeners: list[Listener], subject: str, payload: dict[str, Any]) -> None:
    for listener in listeners:
        try:
            await listener(subject, payload)
        except Exception:
            log.exception("events.listener_failed", subject=subject)


_bus: EventBus | None = None


async def start_bus() -> EventBus:
    global _bus
    url = get_settings().nats_url
    if url:
        bus = NatsBus()
        await bus.connect(url)
        _bus = bus
    else:
        _bus = LocalBus()
    return _bus


def get_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = LocalBus()
    return _bus


async def stop_bus() -> None:
    global _bus
    if _bus is not None:
        await _bus.close()
    _bus = None


async def relay_pending(sessionmaker: async_sessionmaker[AsyncSession], bus: EventBus, batch: int = 200) -> int:
    """Publish one batch of pending outbox rows. Returns how many were published."""
    async with sessionmaker() as session, session.begin():
        rows = (
            await session.execute(
                text(
                    "SELECT id, subject, payload FROM events.outbox WHERE published_at IS NULL "
                    "ORDER BY id LIMIT :batch FOR UPDATE SKIP LOCKED"
                ),
                {"batch": batch},
            )
        ).all()
        published: list[int] = []
        for row in rows:
            try:
                await bus.publish(row.subject, row.payload, msg_id=str(row.id))
            except Exception:
                log.warning("events.publish_failed", outbox_id=row.id, subject=row.subject)
                await session.execute(
                    text("UPDATE events.outbox SET attempts = attempts + 1 WHERE id = :id"), {"id": row.id}
                )
                break  # keep order: retry this row first on the next pass
            published.append(row.id)
        if published:
            await session.execute(
                text("UPDATE events.outbox SET published_at = :now WHERE id = ANY(:ids)"),
                {"now": datetime.now(UTC), "ids": published},
            )
    return len(published)


async def relay_forever(sessionmaker: async_sessionmaker[AsyncSession], idle_s: float = 0.5) -> None:
    while True:
        try:
            count = await relay_pending(sessionmaker, get_bus())
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("events.relay_failed")
            count = 0
        if count == 0:
            await asyncio.sleep(idle_s)
