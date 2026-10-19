from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketDisconnect

from app.core.db import get_sessionmaker
from app.core.events import LocalBus, relay_pending
from app.main import app
from app.modules.reports.live import hub
from tests.conftest import STAFF_ISS, TokenFactory, accept_charter, report_body

URL = "/api/v1/staff/live"


def _staff_token(make_token: TokenFactory, gouvernorat: int | None = 61, **kwargs: Any) -> str:
    scope: dict[str, Any] = {"gouvernorat_code": str(gouvernorat)} if gouvernorat else {"scope_level": "national"}
    return make_token(issuer=STAFF_ISS, roles=kwargs.pop("roles", ["operator"]), **scope, **kwargs)


def _event(gouvernorat: int | None, marker: str) -> dict[str, Any]:
    return {"report": {"id": marker, "gouvernorat_code": gouvernorat}}


def _close_code(ws: Any) -> int:
    with pytest.raises(WebSocketDisconnect) as exc:
        ws.receive_json()
    return exc.value.code


def test_first_message_must_authenticate() -> None:
    with TestClient(app).websocket_connect(URL) as ws:
        ws.send_json({"type": "hello"})
        assert _close_code(ws) == 4401


def test_reporters_are_refused(make_token: TokenFactory) -> None:
    with TestClient(app).websocket_connect(URL) as ws:
        ws.send_json({"type": "auth", "token": make_token(roles=["citizen"])})
        assert _close_code(ws) == 4403


def test_events_are_filtered_by_scope(make_token: TokenFactory) -> None:
    with TestClient(app).websocket_connect(URL) as ws:
        ws.send_json({"type": "auth", "token": _staff_token(make_token, 61)})
        assert ws.receive_json() == {"type": "ready"}
        assert hub.size >= 1
        ws.portal.call(hub.on_event, "report.created", _event(11, "tunis"))
        ws.portal.call(hub.on_event, "report.created", _event(None, "outside"))
        ws.portal.call(hub.on_event, "report.status_changed", _event(61, "sfax"))
        ws.portal.call(hub.on_event, "media.stored", {"report_id": "r1", "gouvernorat_code": 61, "media": {}})
        assert ws.receive_json() == {"type": "report.status_changed", **_event(61, "sfax")}
        assert ws.receive_json()["type"] == "media.stored"
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}


def test_national_scope_sees_everything(make_token: TokenFactory) -> None:
    with TestClient(app).websocket_connect(URL) as ws:
        ws.send_json({"type": "auth", "token": _staff_token(make_token, None, roles=["central_committee"])})
        assert ws.receive_json() == {"type": "ready"}
        ws.portal.call(hub.on_event, "report.created", _event(None, "outside"))
        assert ws.receive_json()["report"]["id"] == "outside"


def test_token_renewal_must_keep_the_same_user(make_token: TokenFactory) -> None:
    with TestClient(app).websocket_connect(URL) as ws:
        ws.send_json({"type": "auth", "token": _staff_token(make_token, 61, sub="user-a")})
        assert ws.receive_json() == {"type": "ready"}
        ws.send_json({"type": "auth", "token": _staff_token(make_token, 61, sub="user-a")})
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}
        ws.send_json({"type": "auth", "token": _staff_token(make_token, 61, sub="user-b")})
        assert _close_code(ws) == 4403


def test_expired_session_is_closed(make_token: TokenFactory) -> None:
    with TestClient(app).websocket_connect(URL) as ws:
        ws.send_json({"type": "auth", "token": _staff_token(make_token, 61, expires_in=1)})
        assert ws.receive_json() == {"type": "ready"}
        assert _close_code(ws) == 4401


async def test_outbox_relay_publishes_once(
    client: httpx.AsyncClient, citizen: dict[str, str], session: AsyncSession
) -> None:
    await accept_charter(client, citizen)
    report_id = (await client.post("/api/v1/reports", json=report_body(), headers=citizen)).json()["id"]

    received: list[tuple[str, dict[str, Any]]] = []

    async def listener(subject: str, payload: dict[str, Any]) -> None:
        received.append((subject, payload))

    bus = LocalBus()
    bus.add_listener(listener)
    while await relay_pending(get_sessionmaker(), bus):
        pass
    ours = [p for s, p in received if s == "report.created" and p["report"]["id"] == report_id]
    assert len(ours) == 1
    pending = await session.scalar(text("SELECT count(*) FROM events.outbox WHERE published_at IS NULL"))
    assert pending == 0
    assert await relay_pending(get_sessionmaker(), bus) == 0


async def test_failed_publish_is_retried(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    await accept_charter(client, citizen)
    await client.post("/api/v1/reports", json=report_body(), headers=citizen)

    class DownBus(LocalBus):
        async def publish(self, subject: str, payload: dict[str, Any], msg_id: str) -> None:
            raise ConnectionError("nats down")

    assert await relay_pending(get_sessionmaker(), DownBus()) == 0
    assert await relay_pending(get_sessionmaker(), LocalBus()) >= 1
