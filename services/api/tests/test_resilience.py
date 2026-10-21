"""Phase 10 §2.2 (NFR-02): the paths an SOS takes keep working when a dependency is down.

* Valkey unreachable: the report is accepted, the limiter falls back to local counters, the session check fails open
  and is counted;
* NATS absent: the report is accepted and its event waits in ``events.outbox`` until a publisher drains it;
* the AI service is down: the report is accepted, ranked by the rules, and its analysis is retried later;
* the identity provider's keys are unreachable: an anonymous SOS still works, staff get ``503
  identity_provider_unavailable`` (never 500).
"""

from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import metrics, ratelimit, security, sessions
from app.core.db import get_system_sessionmaker
from app.core.events import open_payload, relay_pending
from app.modules.ai.client import AiUnavailable
from tests.aihelpers import FakeAi, analyse
from tests.conftest import PUBLIC_ISS, STAFF_ISS, device_headers, report_body
from tests.test_hardening import BrokenLimiter, Staff, _consent


async def _anonymous_sos(client: httpx.AsyncClient) -> dict[str, Any]:
    headers = device_headers()
    assert await _consent(client, headers) == 201
    r = await client.post("/api/v1/reports", json=report_body(category="sos"), headers=headers)
    assert r.status_code == 201, r.text
    return dict(r.json())


class _BrokenRevocations:
    async def set(self, subject: str, not_before: int) -> None:
        raise ConnectionError("valkey down")

    async def get(self, subject: str) -> int | None:
        raise ConnectionError("valkey down")


async def test_valkey_down(client: httpx.AsyncClient, staff: Staff) -> None:
    ratelimit.set_limiter(BrokenLimiter())
    sessions.set_store(_BrokenRevocations())
    before = metrics.REGISTRY.get_sample_value("ehimaya_session_check_degraded_total") or 0.0

    await _anonymous_sos(client)
    assert ratelimit.is_degraded()
    # Staff keep working; the skipped revocation check is counted (alert SessionCheckDegraded).
    assert (await client.get("/api/v1/staff/reports?limit=1", headers=staff())).status_code == 200
    assert (metrics.REGISTRY.get_sample_value("ehimaya_session_check_degraded_total") or 0.0) > before


class _NoNats:
    async def publish(self, subject: str, payload: dict[str, Any], msg_id: str) -> None:
        raise ConnectionError("nats down")


class _Recorder:
    def __init__(self) -> None:
        self.ids: list[str] = []

    async def publish(self, subject: str, payload: dict[str, Any], msg_id: str) -> None:
        self.ids.append(msg_id)


async def test_nats_down(client: httpx.AsyncClient, session: AsyncSession) -> None:
    start = await session.scalar(text("SELECT coalesce(max(id), 0) FROM events.outbox"))
    report = await _anonymous_sos(client)
    rows = (
        await session.execute(
            text("SELECT id, payload, published_at FROM events.outbox WHERE subject = 'report.created' AND id > :s"),
            {"s": start},
        )
    ).all()
    (row,) = [r for r in rows if open_payload(r.payload)["report"]["id"] == report["id"]]
    assert row.published_at is None

    assert await relay_pending(get_system_sessionmaker(), _NoNats()) == 0  # type: ignore[arg-type]
    session.expire_all()
    assert await session.scalar(text("SELECT published_at FROM events.outbox WHERE id = :id"), {"id": row.id}) is None

    # Back up: the event goes out, in order, without being lost.
    bus = _Recorder()
    while await relay_pending(get_system_sessionmaker(), bus):  # type: ignore[arg-type]
        pass
    assert str(row.id) in bus.ids


async def test_ai_down(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    report = await _anonymous_sos(client)
    ai = FakeAi()
    for step in ("transcribe", "translate", "embed", "extract"):
        ai.fail[step] = AiUnavailable("connection refused")
    assert await analyse(report["id"], ai)
    row = (
        await session.execute(
            text("SELECT state, next_attempt_at > now() AS later FROM ai.analysis WHERE report_id = :id"),
            {"id": report["id"]},
        )
    ).one()
    assert (row.state, row.later) == ("pending", True)
    detail = (await client.get(f"/api/v1/staff/reports/{report['id']}", headers=staff(gouvernorat=None))).json()
    assert detail["priority_score"] is not None  # ranked by the rules meanwhile


@pytest.fixture
def jwks_down() -> Iterator[None]:
    def unreachable(token: str, issuer: str) -> Any:
        raise ConnectionError("keycloak unreachable")

    previous = security.get_token_verifier()
    security.set_token_verifier(security.TokenVerifier([PUBLIC_ISS, STAFF_ISS], "ehimaya-api", unreachable))
    try:
        yield
    finally:
        security.set_token_verifier(previous)


@pytest.mark.usefixtures("jwks_down")
async def test_identity_provider_down(client: httpx.AsyncClient, staff: Staff) -> None:
    await _anonymous_sos(client)
    errors = metrics.REGISTRY.get_sample_value("ehimaya_http_server_errors_total", {"area": "other"}) or 0.0
    r = await client.get("/api/v1/staff/reports?limit=1", headers=staff())
    assert (r.status_code, r.json()["detail"]) == (503, "identity_provider_unavailable")
    # Counted for the alerts; the intake (area "reports") stays clean.
    assert metrics.REGISTRY.get_sample_value("ehimaya_http_server_errors_total", {"area": "other"}) == errors + 1
