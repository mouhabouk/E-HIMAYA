# covers: the camera bridge (Yamen 2026-11-01, docs/guides/camera-bridge.md)
"""A thermal or fire-detecting camera sends its own alarm through a bridge, signed with the camera's key: it goes
through the same staged pre-alert as a fire the vision service confirmed, or to the room at once."""

import base64
import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.streams.camera_events import sign
from tests.conftest import FakeStore, TokenFactory, bearer
from tests.test_phase_d import TUNIS, Staff, User, active_org, pending


@pytest.fixture
def user(make_token: TokenFactory) -> User:
    def _user(email: str | None = None) -> dict[str, str]:
        email = email or f"u{uuid.uuid4().hex[:10]}@example.tn"
        return bearer(make_token(roles=["citizen"], email=email, email_verified=True, name="User"))

    return _user


JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200


async def camera(
    client: httpx.AsyncClient, staff: Staff, user: User, monitored_by: str = "owner"
) -> tuple[str, dict[str, str], str, str]:
    admin = user()
    org_id = await active_org(client, staff, admin, location=TUNIS)
    r = await client.post(
        "/api/v1/staff/streams",
        json={
            "source": "camera",
            "label": "Hikvision DS-2TD thermique",
            "gouvernorat_code": 11,
            "org_id": org_id,
            "monitored_by": monitored_by,
            **TUNIS,
        },
        headers=staff(["ops_manager"], gouvernorat=11),
    )
    assert r.status_code == 201, r.text
    assert len(r.json()["event_key"]) == 64
    return org_id, admin, r.json()["id"], r.json()["event_key"]


def event(
    cam: str,
    key: str,
    *,
    at: datetime | None = None,
    label: str = "fire",
    frame: bytes | None = JPEG,
    temperature: str = "87.5",
    sig: str | None = None,
) -> dict[str, Any]:
    at_s = (at or datetime.now(UTC)).isoformat()
    sha = hashlib.sha256(frame).hexdigest() if frame else ""
    body: dict[str, Any] = {
        "camera": cam,
        "at": at_s,
        "label": label,
        "confidence": "1",
        "temperature": temperature,
        "vendor_event": "TMA",
        "sig": sig or sign(key, cam, at_s, label, "1", temperature, sha),
    }
    if frame:
        body["frame_jpeg_b64"] = base64.b64encode(frame).decode()
    return body


async def test_a_thermal_alarm_opens_the_staged_prealert(
    client: httpx.AsyncClient, staff: Staff, user: User, session: AsyncSession, fake_store: FakeStore
) -> None:
    org_id, admin, cam, key = await camera(client, staff, user)
    body = event(cam, key)
    r = await client.post("/api/v1/camera-events", json=body)
    assert r.status_code == 202, r.text
    assert r.json() == {"accepted": True, "alerted": True}
    (alert,) = await pending(client, admin, org_id)
    assert alert["stage"] == "owner" and alert["has_frame"] and alert["stream_id"] == cam
    # The same alarm again is a replay; a second alarm within the cool-down is kept but raises nothing.
    assert (await client.post("/api/v1/camera-events", json=body)).status_code == 409
    later = event(cam, key, at=datetime.now(UTC) + timedelta(seconds=5), frame=None)
    r = await client.post("/api/v1/camera-events", json=later)
    assert r.status_code == 202 and r.json()["alerted"] is False
    rows = (
        await session.execute(
            text("SELECT alerted, temperature_c, vendor_event FROM reports.camera_event WHERE stream_id = :s"),
            {"s": cam},
        )
    ).all()
    assert sorted(r.alerted for r in rows) == [False, True] and rows[0].temperature_c == 87.5


async def test_a_device_the_civil_protection_follows_reports_at_once(
    client: httpx.AsyncClient, staff: Staff, user: User, fake_store: FakeStore
) -> None:
    org_id, admin, cam, key = await camera(client, staff, user, monitored_by="room")
    r = await client.post("/api/v1/camera-events", json=event(cam, key, label="smoke", temperature=""))
    assert r.status_code == 202 and r.json()["alerted"] is True
    listed = (await client.get(f"/api/v1/orgs/{org_id}/prealerts", headers=admin)).json()
    (row,) = [p for p in listed if p["stream_id"] == cam]
    assert row["stage"] == "room" and row["state"] == "escalated" and row["report_id"]


async def test_wrong_signature_clock_and_stale_alarms(
    client: httpx.AsyncClient, staff: Staff, user: User, fake_store: FakeStore
) -> None:
    org_id, admin, cam, key = await camera(client, staff, user)
    other = "ab" * 32
    assert (await client.post("/api/v1/camera-events", json=event(cam, other))).status_code == 401
    assert (await client.post("/api/v1/camera-events", json=event(str(uuid.uuid4()), key))).status_code == 401
    ahead = event(cam, key, at=datetime.now(UTC) + timedelta(minutes=20))
    assert (await client.post("/api/v1/camera-events", json=ahead)).status_code == 422
    # Kept by the bridge while the line was down: stored, but too old to alert anyone.
    stale = event(cam, key, at=datetime.now(UTC) - timedelta(hours=1))
    r = await client.post("/api/v1/camera-events", json=stale)
    assert r.status_code == 202 and r.json()["alerted"] is False
    assert await pending(client, admin, org_id) == []


async def test_heartbeat_and_key_renewal(
    client: httpx.AsyncClient, staff: Staff, user: User, session: AsyncSession
) -> None:
    _, _, cam, key = await camera(client, staff, user)
    at = datetime.now(UTC).isoformat()
    beat = {"camera": cam, "at": at, "sig": sign(key, cam, at, "heartbeat")}
    assert (await client.post("/api/v1/camera-events/heartbeat", json=beat)).status_code == 204
    seen = await session.scalar(text("SELECT bridge_seen_at FROM reports.live_stream WHERE id = :s"), {"s": cam})
    assert seen is not None
    # Another gouvernorat's manager cannot renew it; the renewed key replaces the old one at once.
    url = f"/api/v1/staff/streams/{cam}/event-key"
    # Row-level security hides the camera from another gouvernorat (404); without it, the scope check refuses (403).
    assert (await client.post(url, headers=staff(["ops_manager"], gouvernorat=21))).status_code in (403, 404)
    r = await client.post(url, headers=staff(["ops_manager"], gouvernorat=11))
    assert r.status_code == 200 and r.json()["key"] != key
    at = datetime.now(UTC).isoformat()
    old = {"camera": cam, "at": at, "sig": sign(key, cam, at, "heartbeat")}
    assert (await client.post("/api/v1/camera-events/heartbeat", json=old)).status_code == 401
