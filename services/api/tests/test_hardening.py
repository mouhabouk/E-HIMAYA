"""Phase 5.5 hardening: anonymous abuse controls (A1), degraded rate limiter (A2), content-free personal pushes
(A8), process roles (B1) and the Prometheus endpoint (B2)."""

import asyncio
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import main
from app.core import metrics, ratelimit
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.modules.notify import delivery
from app.modules.notify.providers import Push
from app.modules.reports import router as reports_router
from tests.conftest import TokenFactory, accept_charter, device_headers, report_body
from tests.test_notifications import alert_body, citizen_headers, drain, info_body, pushes_to, register, user_of

Staff = Callable[..., dict[str, str]]
METRICS_TOKEN = "metrics-token-metrics-token-0001"


class BrokenLimiter:
    """Stands in for an unreachable Valkey."""

    def __init__(self) -> None:
        self.broken = True
        self.calls = 0
        self.inner = ratelimit.MemoryLimiter()

    async def hit(self, key: str, limit: int, window_s: int) -> int | None:
        self.calls += 1
        if self.broken:
            raise ConnectionError("valkey down")
        return await self.inner.hit(key, limit, window_s)


@pytest.fixture
def limits(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    def _set(**values: int) -> None:
        for name, value in values.items():
            monkeypatch.setattr(get_settings(), name, value)

    return _set


def metric(name: str, labels: dict[str, str] | None = None) -> float:
    return metrics.REGISTRY.get_sample_value(name, labels or {}) or 0.0


async def _consent(client: httpx.AsyncClient, headers: dict[str, str]) -> int:
    r = await client.post(
        "/api/v1/consents", json={"charter_version": "2026-10", "locale": "ar", "platform": "android"}, headers=headers
    )
    return r.status_code


# ---------------------------------------------------------------- A1: per-address limits


async def test_new_anonymous_identities_are_limited_per_address(
    client: httpx.AsyncClient, citizen: dict[str, str], limits: Callable[..., None]
) -> None:
    limits(anon_identity_per_ip=3)
    devices = [device_headers() for _ in range(4)]
    assert [await _consent(client, d) for d in devices[:3]] == [201, 201, 201]
    r = await client.post(
        "/api/v1/consents",
        json={"charter_version": "2026-10", "locale": "ar", "platform": "android"},
        headers=devices[3],
    )
    assert r.status_code == 429 and r.json()["detail"] == "rate_limited" and int(r.headers["Retry-After"]) >= 1
    # Known devices keep working, and registered citizens are never limited per address.
    assert (await client.post("/api/v1/reports", json=report_body(), headers=devices[0])).status_code == 201
    await accept_charter(client, citizen)
    assert (await client.post("/api/v1/reports", json=report_body(), headers=citizen)).status_code == 201


async def test_anonymous_consents_and_devices_are_limited_per_address(
    client: httpx.AsyncClient, make_token: TokenFactory, limits: Callable[..., None]
) -> None:
    limits(anon_consent_per_ip=2, anon_device_per_ip=2)
    assert [await _consent(client, device_headers()) for _ in range(3)] == [201, 201, 429]

    def device(n: int) -> dict[str, Any]:
        return {"token": f"tok-{n}-" + "d" * 30, "platform": "android", "locale": "ar"}

    anon = [device_headers() for _ in range(3)]
    codes = [(await client.put("/api/v1/devices", json=device(i), headers=h)).status_code for i, h in enumerate(anon)]
    assert codes == [204, 204, 429]
    # A registered citizen on the same address is only limited per account.
    citizen = citizen_headers(make_token)
    assert (await client.put("/api/v1/devices", json=device(9), headers=citizen)).status_code == 204
    assert await _consent(client, citizen) == 201


async def test_anonymous_reports_are_limited_per_address(
    client: httpx.AsyncClient, citizen: dict[str, str], limits: Callable[..., None]
) -> None:
    limits(anon_report_per_ip=2)
    first, second = device_headers(), device_headers()
    await accept_charter(client, first)
    await accept_charter(client, second)
    codes = [(await client.post("/api/v1/reports", json=report_body(), headers=h)).status_code for h in (first, first)]
    assert codes == [201, 201]
    r = await client.post("/api/v1/reports", json=report_body(), headers=second)
    assert r.status_code == 429
    await accept_charter(client, citizen)
    assert (await client.post("/api/v1/reports", json=report_body(), headers=citizen)).status_code == 201


# ---------------------------------------------------------------- A1: global anonymous budget


async def test_reports_beyond_the_anonymous_budget_are_accepted_and_flagged(
    client: httpx.AsyncClient,
    citizen: dict[str, str],
    staff: Staff,
    session: AsyncSession,
    limits: Callable[..., None],
    isolated_window: None,
) -> None:
    limits(anon_report_budget=2)
    before = metric("ehimaya_anonymous_budget_exceeded_total")
    ids = []
    for _ in range(3):
        device = device_headers()
        await accept_charter(client, device)
        r = await client.post("/api/v1/reports", json=report_body(category="flood"), headers=device)
        assert r.status_code == 201  # never rejected
        assert "needs_verification" not in r.json()  # the reporter is not told
        ids.append(r.json()["id"])
    await accept_charter(client, citizen)
    citizen_report = (await client.post("/api/v1/reports", json=report_body(), headers=citizen)).json()["id"]
    assert metric("ehimaya_anonymous_budget_exceeded_total") == before + 1

    operator = staff()
    flagged = (
        await client.get("/api/v1/staff/reports", params={"needs_verification": "true"}, headers=operator)
    ).json()["items"]
    flagged_ids = {item["id"] for item in flagged}
    assert ids[2] in flagged_ids and not {ids[0], ids[1], citizen_report} & flagged_ids
    item = next(i for i in flagged if i["id"] == ids[2])
    assert item["needs_verification"] is True and item["verification_reason"] == "anonymous_budget"
    others = (
        await client.get("/api/v1/staff/reports", params={"needs_verification": "false"}, headers=operator)
    ).json()["items"]
    assert citizen_report in {i["id"] for i in others} and ids[2] not in {i["id"] for i in others}
    detail = (await client.get(f"/api/v1/staff/reports/{ids[2]}", headers=operator)).json()
    assert detail["needs_verification"] is True

    # Ranked lower: the rules priority is halved while the report is unverified.
    row = (
        await session.execute(
            text(
                "SELECT r.priority_score, a.priority FROM reports.report r "
                "JOIN ai.analysis a ON a.report_id = r.id WHERE r.id = :id"
            ),
            {"id": ids[2]},
        )
    ).one()
    raw = sum(c["points"] for c in row[1]["components"])
    assert row[1]["verification"] == {"reason": "anonymous_budget", "factor": 0.5}
    assert row[0] == round(round(min(raw, 100)) * 0.5)


# ---------------------------------------------------------------- A2: degraded limiter


async def test_limiter_falls_back_in_process_when_valkey_fails(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = BrokenLimiter()
    ratelimit.set_limiter(broken)
    monkeypatch.setattr(reports_router, "TRACK_LIMIT", 3)
    codes = [(await client.get("/api/v1/reports/track/EH-26-61-0000001")).status_code for _ in range(4)]
    assert 429 not in codes[:3] and codes[3] == 429  # still limited: never fails open
    assert broken.calls == 1  # Valkey is not retried on every request during an outage
    assert ratelimit.is_degraded() and metric("ehimaya_ratelimit_degraded") == 1

    ready = await client.get("/health/ready")
    assert ready.status_code == 200  # SOS traffic keeps flowing
    assert ready.json()["checks"]["rate_limiter"].startswith("degraded")

    broken.broken = False
    monkeypatch.setattr(ratelimit, "_retry_at", 0.0)
    await client.get("/api/v1/reports/track/EH-26-61-0000001")
    assert not ratelimit.is_degraded() and metric("ehimaya_ratelimit_degraded") == 0
    assert (await client.get("/health/ready")).json()["checks"]["rate_limiter"] == "ok"


async def test_report_creation_is_flagged_not_refused_while_degraded(
    client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff, monkeypatch: pytest.MonkeyPatch
) -> None:
    ratelimit.set_limiter(BrokenLimiter())
    monkeypatch.setattr(reports_router, "CREATE_LIMIT", 2)
    await accept_charter(client, citizen)
    responses = [await client.post("/api/v1/reports", json=report_body(), headers=citizen) for _ in range(3)]
    assert [r.status_code for r in responses] == [201, 201, 201]
    detail = (await client.get(f"/api/v1/staff/reports/{responses[2].json()['id']}", headers=staff())).json()
    assert detail["needs_verification"] is True and detail["verification_reason"] == "limiter_degraded"
    first = (await client.get(f"/api/v1/staff/reports/{responses[0].json()['id']}", headers=staff())).json()
    assert first["needs_verification"] is False


async def test_memory_limiter_is_bounded() -> None:
    limiter = ratelimit.MemoryLimiter(max_keys=3)
    for n in range(10):
        await limiter.hit(f"k{n}", 5, 60)
    assert len(limiter) == 3
    assert await limiter.hit("k9", 2, 60) is None and await limiter.hit("k9", 2, 60) is not None


# ---------------------------------------------------------------- A8: content-free personal pushes


async def test_personal_pushes_carry_no_personal_text(
    client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff, channels: Any
) -> None:
    token = "tok-status-" + "s" * 30
    await client.put("/api/v1/devices", json={"token": token, "platform": "android", "locale": "ar"}, headers=citizen)
    await accept_charter(client, citizen)
    report = (await client.post("/api/v1/reports", json=report_body(), headers=citizen)).json()
    r = await client.post(
        f"/api/v1/staff/reports/{report['id']}/status",
        json={"status": "in_progress", "note": "فريق في الطريق إلى نهج الحبيب"},
        headers=staff(["operator"]),
    )
    assert r.status_code == 200, r.text
    while await delivery.run_outbox(get_sessionmaker()):
        pass
    push = next(p for (p,) in channels.push.sent if isinstance(p, Push) and p.token == token)
    assert (push.title, push.body) == ("ء-حماية", "لديك تحديث جديد")
    assert push.data == {
        "type": "report_status",
        "report_id": report["id"],
        "tracking_code": report["tracking_code"],
        "status": "in_progress",
        "redacted": "1",
    }
    assert "دخان" not in str(push) and "الحبيب" not in str(push)


async def test_one_user_notification_is_redacted_but_public_alerts_are_not(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, channels: Any
) -> None:
    headers = citizen_headers(make_token)
    token = await register(client, headers, (34.7406, 10.7603))
    editor = staff(["content_editor"], gouvernorat=None)
    body = info_body(
        audience="user",
        user_id=await user_of(token),
        title={"ar": "موعدك يوم الإثنين", "fr": "Votre rendez-vous lundi"},
        body={"ar": "نهج الحرية 12", "fr": "12 rue de la Liberté"},
    )
    message = (await client.post("/api/v1/staff/notifications", json=body, headers=editor)).json()
    await client.post(f"/api/v1/staff/notifications/{message['id']}/publish", headers=editor)
    await drain()
    (push,) = pushes_to(channels.push, token, message["id"])
    assert (push.title, push.body) == ("e-Himaya", "Vous avez une nouvelle mise à jour")
    assert push.data == {"type": "info", "id": message["id"], "redacted": "1"}
    # The full text stays available in the authenticated inbox.
    inbox = (await client.get("/api/v1/notifications", headers=headers)).json()["items"]
    assert any(i["id"] == message["id"] for i in inbox)

    publisher = staff(["local_committee"], gouvernorat=61)
    alert = (
        await client.post(
            "/api/v1/staff/notifications", json=alert_body(area={"gouvernorat_codes": [61]}), headers=publisher
        )
    ).json()
    await client.post(f"/api/v1/staff/notifications/{alert['id']}/publish", headers=publisher)
    await drain()
    (public,) = pushes_to(channels.push, token, alert["id"])
    assert (public.title, public.body) == ("Alerte pluies abondantes", "Évitez les oueds")
    assert "redacted" not in public.data


# ---------------------------------------------------------------- B1: process roles


async def test_worker_role_serves_no_sos_traffic(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "process_role", "worker")
    r = await client.post("/api/v1/reports", json=report_body(), headers=device_headers())
    assert r.status_code == 503 and r.json()["detail"] == "worker_process"
    assert (await client.get("/health/live")).status_code == 200
    ready = (await client.get("/health/ready")).json()
    assert ready["process_role"] == "worker"


@pytest.mark.parametrize(("role", "runs"), [("api", False), ("worker", True), ("all", True)])
async def test_background_loops_follow_the_process_role(monkeypatch: pytest.MonkeyPatch, role: str, runs: bool) -> None:
    started: list[str] = []

    async def loop(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        started.append("loop")
        await asyncio.Event().wait()

    monkeypatch.setattr(main, "WORKER_LOOPS", [("test-loop", loop)])
    monkeypatch.setattr(get_settings(), "background_workers", True)
    monkeypatch.setattr(get_settings(), "process_role", role)
    async with main.lifespan(main.app):
        await asyncio.sleep(0.01)
    assert started == (["loop"] if runs else [])


# ---------------------------------------------------------------- B2: metrics


async def test_metrics_require_the_token(
    client: httpx.AsyncClient, citizen: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (await client.get("/metrics")).status_code == 404  # disabled without METRICS_TOKEN
    monkeypatch.setattr(get_settings(), "metrics_token", SecretStr(METRICS_TOKEN))
    assert (await client.get("/metrics")).status_code == 404
    assert (await client.get("/metrics", headers={"Authorization": "Bearer wrong"})).status_code == 404

    labels = {"reporter_kind": "citizen"}
    before = metric("ehimaya_report_ingest_seconds_count", labels)
    await accept_charter(client, citizen)
    assert (await client.post("/api/v1/reports", json=report_body(), headers=citizen)).status_code == 201
    assert metric("ehimaya_report_ingest_seconds_count", labels) == before + 1

    r = await client.get("/metrics", headers={"Authorization": f"Bearer {METRICS_TOKEN}"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    for name in (
        "ehimaya_report_ingest_seconds_bucket",
        'ehimaya_outbox_backlog{outbox="events"}',
        'ehimaya_outbox_oldest_age_seconds{outbox="notify"}',
        "ehimaya_ai_queue_depth",
        "ehimaya_ratelimit_degraded",
        "ehimaya_anonymous_budget_exceeded_total",
    ):
        assert name in r.text, name
    assert metric("ehimaya_ai_queue_depth") >= 1  # the new report waits for its analysis


async def test_notify_failures_are_counted_by_channel(
    client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff, channels: Any
) -> None:
    from app.modules.notify.providers import Result

    async def failing(*args: Any) -> Result:
        return Result(ok=False, error="http_500")

    channels.push.send = failing
    before = metric("ehimaya_notify_failures_total", {"channel": "push"})
    await client.put(
        "/api/v1/devices",
        json={"token": "tok-fail-" + "f" * 30, "platform": "android", "locale": "ar"},
        headers=citizen,
    )
    await accept_charter(client, citizen)
    report = (await client.post("/api/v1/reports", json=report_body(), headers=citizen)).json()
    await client.post(f"/api/v1/staff/reports/{report['id']}/status", json={"status": "in_progress"}, headers=staff())
    await delivery.run_outbox(get_sessionmaker())
    assert metric("ehimaya_notify_failures_total", {"channel": "push"}) >= before + 1
