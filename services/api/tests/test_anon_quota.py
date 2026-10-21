"""Anonymous report quota (phase 9, docs/api/phase-9-contract.md §3): 5 accepted reports per installation, then
registration is required; replays are never counted; SOS is never refused; registered accounts have no quota."""

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_system_sessionmaker
from app.modules.settings import service as settings_service
from tests.conftest import accept_charter, device_headers, report_body

Staff = Callable[..., dict[str, str]]
QUOTA = "anonymous.report_quota"


@pytest.fixture
async def device(client: httpx.AsyncClient) -> dict[str, str]:
    headers = device_headers()
    await accept_charter(client, headers)
    return headers


@pytest.fixture
async def restore_quota() -> AsyncIterator[None]:
    yield
    async with get_system_sessionmaker()() as s, s.begin():
        await s.execute(text("UPDATE platform.setting SET value = '5', version = 1 WHERE key = :k"), {"k": QUOTA})
    settings_service.invalidate()


async def _post(client: httpx.AsyncClient, headers: dict[str, str], **overrides: object) -> httpx.Response:
    return await client.post("/api/v1/reports", json=report_body(**overrides), headers=headers)  # type: ignore[arg-type]


async def _counter(session: AsyncSession, report_id: str) -> int:
    return int(
        await session.scalar(
            text(
                "SELECT a.anon_reports_accepted FROM identity.account a "
                "JOIN reports.report r ON r.user_id = a.user_id WHERE r.id = :id"
            ),
            {"id": report_id},
        )
        or 0
    )


async def test_five_then_refused(client: httpx.AsyncClient, device: dict[str, str], session: AsyncSession) -> None:
    remaining = []
    accepted: list[str] = []
    for _ in range(5):
        r = await _post(client, device)
        assert r.status_code == 201, r.text
        assert r.headers["X-Anon-Quota-Limit"] == "5"
        remaining.append(int(r.headers["X-Anon-Quota-Remaining"]))
        accepted.append(r.json()["id"])
    assert remaining == [4, 3, 2, 1, 0]

    sixth = report_body()
    r = await client.post("/api/v1/reports", json=sixth, headers=device)
    assert (r.status_code, r.json()["detail"]) == (403, "anon_quota_exhausted")
    assert r.headers["X-Anon-Quota-Remaining"] == "0" and r.headers["X-Anon-Quota-Limit"] == "5"
    # Nothing stored for the refused report, and the counter did not move.
    stored = await session.scalar(
        text("SELECT count(*) FROM reports.report WHERE client_uuid = :c"), {"c": sixth["client_uuid"]}
    )
    assert stored == 0
    assert await _counter(session, accepted[0]) == 5
    reached = await session.scalar(
        text(
            "SELECT a.anon_quota_reached_at FROM identity.account a JOIN reports.report r ON r.user_id = a.user_id "
            "WHERE r.id = :id"
        ),
        {"id": accepted[0]},
    )
    assert reached is not None

    quota = await client.get("/api/v1/reports/quota", headers=device)
    assert quota.status_code == 200
    assert quota.json() == {"limit": 5, "used": 5, "remaining": 0}
    assert quota.headers["X-Anon-Quota-Remaining"] == "0"


async def test_replay_not_counted(client: httpx.AsyncClient, device: dict[str, str], session: AsyncSession) -> None:
    bodies = [report_body() for _ in range(5)]
    for body in bodies:
        assert (await client.post("/api/v1/reports", json=body, headers=device)).status_code == 201
    # The app resends the 5th (lost answer) and the 1st: same reports, no error, nothing counted.
    for body in (bodies[4], bodies[0]):
        again = await client.post("/api/v1/reports", json=body, headers=device)
        assert again.status_code == 200, again.text
        assert again.headers["X-Anon-Quota-Remaining"] == "0"
    first = (await client.post("/api/v1/reports", json=bodies[0], headers=device)).json()
    assert await _counter(session, first["id"]) == 5


async def test_concurrent_replay_counts_once(
    client: httpx.AsyncClient, device: dict[str, str], session: AsyncSession
) -> None:
    body = report_body()
    answers = await asyncio.gather(*(client.post("/api/v1/reports", json=body, headers=device) for _ in range(3)))
    assert sorted(r.status_code for r in answers) == [200, 200, 201]
    assert len({r.json()["id"] for r in answers}) == 1
    assert await _counter(session, answers[0].json()["id"]) == 1


async def test_concurrent_last_place(client: httpx.AsyncClient, device: dict[str, str], session: AsyncSession) -> None:
    """Two different reports racing for the last place: one is accepted, the other refused, the counter stops at 5."""
    for _ in range(4):
        assert (await _post(client, device)).status_code == 201
    answers = await asyncio.gather(_post(client, device), _post(client, device))
    assert sorted(r.status_code for r in answers) == [201, 403]
    accepted = next(r for r in answers if r.status_code == 201)
    assert await _counter(session, accepted.json()["id"]) == 5


async def test_sos_beyond_quota_accepted_flagged(
    client: httpx.AsyncClient, device: dict[str, str], session: AsyncSession, staff: Staff
) -> None:
    for _ in range(5):
        assert (await _post(client, device)).status_code == 201
    r = await _post(client, device, category="sos", text=None)
    assert r.status_code == 201, r.text
    assert r.headers["X-Anon-Quota-Remaining"] == "0"
    row = (
        await session.execute(
            text("SELECT needs_verification, verification_reason, sla_band FROM reports.report WHERE id = :id"),
            {"id": r.json()["id"]},
        )
    ).one()
    assert row.needs_verification is True and row.verification_reason == "anonymous_quota"
    # Still critical for the claim deadline: emergency is never delayed.
    assert row.sla_band == "critical"
    assert await _counter(session, r.json()["id"]) == 6
    priority = await session.scalar(
        text("SELECT priority FROM ai.analysis WHERE report_id = :id"), {"id": r.json()["id"]}
    )
    assert priority["verification"]["reason"] == "anonymous_quota"
    item = (await client.get(f"/api/v1/staff/reports/{r.json()['id']}", headers=staff())).json()
    assert item["verification_reason"] == "anonymous_quota"
    # A non-SOS report is still refused afterwards.
    assert (await _post(client, device)).status_code == 403


async def test_registered_user_unaffected(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    await accept_charter(client, citizen)
    for _ in range(7):
        r = await _post(client, citizen)
        assert r.status_code == 201, r.text
        assert "X-Anon-Quota-Remaining" not in r.headers
    quota = await client.get("/api/v1/reports/quota", headers=citizen)
    assert quota.json() == {"limit": None, "used": None, "remaining": None}
    assert "X-Anon-Quota-Limit" not in quota.headers


async def test_quota_from_settings(
    client: httpx.AsyncClient, device: dict[str, str], staff: Staff, restore_quota: None
) -> None:
    central = staff(["central_committee"], gouvernorat=None)
    r = await client.put(
        f"/api/v1/staff/settings/{QUOTA}",
        json={"value": 3, "version": 1, "reason": "test lower quota"},
        headers=central,
    )
    assert r.status_code == 200, r.text
    codes = [(await _post(client, device)).status_code for _ in range(4)]
    assert codes == [201, 201, 201, 403]
    quota = (await client.get("/api/v1/reports/quota", headers=device)).json()
    assert quota == {"limit": 3, "used": 3, "remaining": 0}


async def test_existing_reports_not_counted(
    client: httpx.AsyncClient, device: dict[str, str], session: AsyncSession
) -> None:
    """Counted from the release: reports made before (no counter, migration 0019 has no backfill) do not block."""
    first = await _post(client, device)
    assert first.status_code == 201
    user = await session.scalar(text("SELECT user_id FROM reports.report WHERE id = :id"), {"id": first.json()["id"]})
    # Reports from before phase 9 exist for this installation, but its counter starts at 0.
    await session.execute(text("UPDATE identity.account SET anon_reports_accepted = 0 WHERE user_id = :u"), {"u": user})
    await session.execute(
        text("UPDATE reports.report SET received_at = :old WHERE user_id = :u"),
        {"u": user, "old": datetime.now(UTC) - timedelta(days=30)},
    )
    await session.commit()
    codes = [(await _post(client, device)).status_code for _ in range(6)]
    assert codes == [201, 201, 201, 201, 201, 403]
    default = await session.scalar(
        text(
            "SELECT column_default FROM information_schema.columns WHERE table_schema = 'identity' "
            "AND table_name = 'account' AND column_name = 'anon_reports_accepted'"
        )
    )
    assert default == "0"


async def test_sms_adopted_report_not_counted(
    client: httpx.AsyncClient, device: dict[str, str], session: AsyncSession
) -> None:
    """A report first received by SMS (phase 7) and adopted when the app resends it does not use the quota."""
    from tests.test_telephony import SFAX_SMS, mobile, prefix, send_sms

    client_uuid, pre = prefix()
    sms = await send_sms(client, mobile(), f"EH1 fire {SFAX_SMS} 0m {pre}")
    assert sms.json()["status"] == "created"
    synced = await client.post("/api/v1/reports", json=report_body(client_uuid=client_uuid), headers=device)
    assert synced.status_code == 200 and synced.json()["tracking_code"] == sms.json()["tracking_code"]
    assert synced.headers["X-Anon-Quota-Remaining"] == "5"
    assert await _counter(session, synced.json()["id"]) == 0
