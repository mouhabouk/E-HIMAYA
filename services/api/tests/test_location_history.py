"""Location history for 72 hours (phase B2, docs/phase-b/design-b2.md §6, addition 7b §2): off for the platform until
the legal review, own consent, points deleted after 72 hours or at once when turned off, staff search for a report
with a reason, audited and notified."""

import secrets
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_system_sessionmaker
from app.modules.safety import history
from app.modules.settings import service as settings_service
from tests.conftest import TokenFactory, accept_charter, bearer, report_body

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/safety/history"
POINT = {"lat": 36.8065, "lon": 10.1815, "accuracy_m": 20.0}


async def _set_feature(on: bool) -> None:
    async with get_system_sessionmaker()() as s, s.begin():
        await s.execute(
            text("UPDATE platform.setting SET value = CAST(:v AS jsonb) WHERE key = 'safety.location_history'"),
            {"v": "true" if on else "false"},
        )
    settings_service.invalidate("safety.location_history")


@pytest.fixture
async def feature_on() -> AsyncIterator[None]:
    await _set_feature(True)
    try:
        yield
    finally:
        await _set_feature(False)


async def _person(client: httpx.AsyncClient, make_token: TokenFactory) -> tuple[dict[str, str], str]:
    headers = bearer(make_token(roles=["citizen"]))
    phone = f"+2165{secrets.randbelow(10_000_000):07d}"
    profile = {
        "first_name": "Hela",
        "last_name": "Test",
        "cin": f"{secrets.randbelow(100_000_000):08d}",
        "phone": phone,
        "gouvernorat_code": 61,
        "delegation_id": 6101,
        "locale": "ar",
    }
    assert (await client.put("/api/v1/me/profile", json=profile, headers=headers)).status_code == 200
    return headers, phone


def _on(**overrides: Any) -> dict[str, Any]:
    return {"enabled": True, "hours": 72, "notice_version": history.NOTICE_VERSION, **overrides}


async def test_off_for_the_platform_by_default(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    headers, _ = await _person(client, make_token)
    state = (await client.get(URL, headers=headers)).json()
    assert state == {"available": False, "enabled": False, "until": None, "notice_version": history.NOTICE_VERSION}
    r = await client.put(URL, json=_on(), headers=headers)
    assert r.status_code == 403 and r.json()["detail"] == "feature_off"
    r = await client.post(
        f"{URL}/points", json={"points": [{"location": POINT, "at": "2026-10-23T10:00:00Z"}]}, headers=headers
    )
    assert r.status_code == 403
    # Turning off always works.
    assert (await client.put(URL, json={"enabled": False}, headers=headers)).status_code == 200


async def test_consent_points_and_turning_off(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession, feature_on: None
) -> None:
    headers, _ = await _person(client, make_token)
    r = await client.put(URL, json=_on(notice_version=None), headers=headers)
    assert r.status_code == 422 and r.json()["detail"] == "consent_required"
    r = await client.put(URL, json=_on(hours=12), headers=headers)
    assert r.status_code == 200, r.text
    until = datetime.fromisoformat(r.json()["until"])
    assert timedelta(hours=11, minutes=59) < until - datetime.now(UTC) <= timedelta(hours=12)
    now = datetime.now(UTC)
    points = [
        {"location": {**POINT, "lat": 36.81}, "at": now.isoformat()},
        # Before it was turned on, or in the future: ignored.
        {"location": POINT, "at": (now - timedelta(minutes=10)).isoformat()},
        {"location": POINT, "at": (now + timedelta(hours=1)).isoformat()},
    ]
    stored = (await client.post(f"{URL}/points", json={"points": points}, headers=headers)).json()
    assert stored["stored"] == 1
    raw = await session.scalar(text("SELECT position_enc FROM safety.location_point ORDER BY id DESC LIMIT 1"))
    assert raw is not None and b"36.81" not in bytes(raw)
    consent = await session.scalar(
        text(
            "SELECT count(*) FROM identity.consent c JOIN safety.location_history h ON h.owner_id = c.user_id "
            "WHERE c.purpose = 'location_history' AND c.withdrawn_at IS NULL AND c.charter_version = :v"
        ),
        {"v": history.NOTICE_VERSION},
    )
    assert consent and consent >= 1

    # Off: every point goes at once and the consent is withdrawn.
    owner = await session.scalar(text("SELECT owner_id FROM safety.location_point ORDER BY id DESC LIMIT 1"))
    assert (await client.put(URL, json={"enabled": False}, headers=headers)).json()["enabled"] is False
    assert (
        await session.scalar(text("SELECT count(*) FROM safety.location_point WHERE owner_id = :o"), {"o": owner}) == 0
    )
    withdrawn = await session.scalar(
        text(
            "SELECT count(*) FROM identity.consent "
            "WHERE user_id = :o AND purpose = 'location_history' AND withdrawn_at IS NULL"
        ),
        {"o": owner},
    )
    assert withdrawn == 0
    r = await client.post(f"{URL}/points", json={"points": points[:1]}, headers=headers)
    assert r.status_code == 409 and r.json()["detail"] == "history_off"


async def test_points_kept_72_hours(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession, feature_on: None
) -> None:
    headers, _ = await _person(client, make_token)
    await client.put(URL, json=_on(), headers=headers)
    now = datetime.now(UTC)
    await client.post(f"{URL}/points", json={"points": [{"location": POINT, "at": now.isoformat()}]}, headers=headers)
    owner = await session.scalar(text("SELECT owner_id FROM safety.location_point ORDER BY id DESC LIMIT 1"))
    async with get_system_sessionmaker()() as s, s.begin():
        await history.purge_points(s, get_settings(), now + timedelta(hours=71))
    assert (
        await session.scalar(text("SELECT count(*) FROM safety.location_point WHERE owner_id = :o"), {"o": owner}) == 1
    )
    async with get_system_sessionmaker()() as s, s.begin():
        while await history.purge_points(s, get_settings(), now + timedelta(hours=73)):
            pass
    assert (
        await session.scalar(text("SELECT count(*) FROM safety.location_point WHERE owner_id = :o"), {"o": owner}) == 0
    )


async def test_staff_search_needs_a_report_and_a_reason(
    client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff, session: AsyncSession, feature_on: None
) -> None:
    missing, phone = await _person(client, make_token)
    await client.put(URL, json=_on(), headers=missing)
    now = datetime.now(UTC)
    await client.post(f"{URL}/points", json={"points": [{"location": POINT, "at": now.isoformat()}]}, headers=missing)
    relative = bearer(make_token(roles=["citizen"]))
    await accept_charter(client, relative)
    report = (await client.post("/api/v1/reports", json=report_body(category="other"), headers=relative)).json()
    body = {
        "phone": phone,
        "report_id": report["id"],
        "reason": f"Personne disparue signalée par sa sœur ({secrets.token_hex(4)})",
    }
    operator = staff(gouvernorat=61)
    r = await client.post("/api/v1/staff/safety/history/search", json=body, headers=operator)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["found"] and out["enabled"] and len(out["points"]) == 1 and out["points"][0]["lat"] == POINT["lat"]
    audited = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'safety.history_search' AND reason = :r"),
        {"r": body["reason"]},
    )
    assert audited == 1
    told = await session.scalar(
        text(
            "SELECT count(*) FROM notify.outbox WHERE payload->>'type' = 'safety_history_viewed' "
            "AND payload->'data'->>'report_id' = :r"
        ),
        {"r": report["id"]},
    )
    assert told == 1
    # Short reason, unknown report, report of another gouvernorat, a role that may not search.
    assert (
        await client.post("/api/v1/staff/safety/history/search", json={**body, "reason": "x"}, headers=operator)
    ).status_code == 422
    unknown = {**body, "report_id": "00000000-0000-4000-8000-000000000000"}
    assert (await client.post("/api/v1/staff/safety/history/search", json=unknown, headers=operator)).status_code == 404
    assert (
        await client.post("/api/v1/staff/safety/history/search", json=body, headers=staff(gouvernorat=11))
    ).status_code == 404
    assert (
        await client.post("/api/v1/staff/safety/history/search", json=body, headers=staff(roles=["content_editor"]))
    ).status_code == 403
    # Nobody with that number: audited, nothing found.
    r = await client.post(
        "/api/v1/staff/safety/history/search", json={**body, "phone": "+21629999999"}, headers=operator
    )
    assert r.json() == {"found": False, "enabled": False, "points": []}
