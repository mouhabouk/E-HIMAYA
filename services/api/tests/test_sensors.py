"""Sensors of the local network (L5b, docs/phase-l/design-l5.md §3.0 and §3.1): the register and its scope, the key
shown once, signed readings relayed by the gateway beside MediaMTX (and every way a reading is refused), the levels,
"silent", and a crossed threshold that becomes a suggestion in the alert centre, never a message by itself."""

import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.sensors import domain
from app.modules.weather.models import AlertSuggestion

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/sensors"
INGEST = "/internal/sensors/readings"
GATEWAY = {"X-Gateway-Token": "test-sensor-gateway-token-0001"}
GABES, BIZERTE = 61, 23


def _code() -> str:
    return f"SIM-{secrets.token_hex(4)}"


async def _create(
    client: httpx.AsyncClient, staff: Staff, *, kind: str = "rain_1h", code: int = GABES, **extra: Any
) -> dict[str, Any]:
    body = {
        "code": _code(),
        "name": "مقياس مطر وادي قابس [SIM]",
        "kind": kind,
        "lat": 33.88,
        "lon": 10.1,
        "provider": "INM [SIM]",
        "watch_threshold": 20,
        "alarm_threshold": 40,
        **extra,
    }
    r = await client.post(URL, json=body, headers=staff(["ops_manager"], gouvernorat=code))
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def _reading(sensor: str, key: str, value: str, at: datetime | None = None) -> dict[str, str]:
    stamp = (at or datetime.now(UTC)).isoformat(timespec="seconds")
    return {"sensor": sensor, "at": stamp, "value": value, "sig": domain.sign(key, sensor, stamp, value)}


def test_signature_is_over_the_strings_as_sent() -> None:
    key = domain.new_key()
    sig = domain.sign(key, "S1", "2026-10-28T20:00:00+01:00", "12.5")
    assert domain.signature_valid(key, "S1", "2026-10-28T20:00:00+01:00", "12.5", sig)
    assert not domain.signature_valid(key, "S1", "2026-10-28T20:00:00+01:00", "12.50", sig)
    assert not domain.signature_valid(domain.new_key(), "S1", "2026-10-28T20:00:00+01:00", "12.5", sig)
    assert not domain.signature_valid(key, "S1", "2026-10-28T20:00:00+01:00", "12.5", sig.upper())
    assert domain.parse_value("1e3", domain.Kind.RAIN_1H) is None
    assert domain.parse_value("-1", domain.Kind.RAIN_1H) is None
    assert domain.parse_value("NaN", domain.Kind.TEMPERATURE) is None
    assert domain.parse_value("41.25", domain.Kind.TEMPERATURE) == 41.25
    now = datetime.now(UTC)
    assert domain.parse_at(now.replace(tzinfo=None).isoformat(), now) is None
    assert domain.parse_at((now - timedelta(hours=1)).isoformat(), now) is None
    assert domain.level_of(20, 20, 40) == "watch"
    assert domain.state_of(
        enabled=True, level="alarm", last_at=now - timedelta(hours=2), silent_after_min=30, now=now
    ) == ("silent")


async def test_register_scope_and_key_shown_once(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    created = await _create(client, staff)
    sensor, key = created["sensor"], created["key"]
    assert len(key) == 64 and sensor["state"] == "silent" and sensor["unit"] == "mm"
    # The key is never listed again, nor written to the audit log.
    listed = (await client.get(URL, headers=staff(["operator"], gouvernorat=GABES))).json()
    mine = next(s for s in listed["items"] if s["id"] == sensor["id"])
    assert "key" not in mine and listed["can_manage"] is False
    logs = (await session.scalars(select(AuditLog).where(AuditLog.target == sensor["id"]))).all()
    assert logs and all(key not in str(log.details) for log in logs)
    # Another gouvernorat's room does not see it; the central room does.
    other = (await client.get(URL, headers=staff(["operator"], gouvernorat=BIZERTE))).json()
    assert sensor["id"] not in {s["id"] for s in other["items"]}
    central = (await client.get(URL, headers=staff(["operator"], gouvernorat=None))).json()
    assert sensor["id"] in {s["id"] for s in central["items"]}
    # Only the operations manager registers, in their own gouvernorat; the code is unique; thresholds are ordered.
    body = {
        "code": _code(),
        "name": "x [SIM]",
        "kind": "water_level",
        "lat": 37.27,
        "lon": 9.87,
        "provider": "وزارة الفلاحة",
        "watch_threshold": 3,
        "alarm_threshold": 2,
    }
    assert (await client.post(URL, json=body, headers=staff(["operator"], gouvernorat=GABES))).status_code == 403
    manager = staff(["ops_manager"], gouvernorat=GABES)
    assert (await client.post(URL, json=body, headers=manager)).status_code == 422
    body |= {"watch_threshold": 2, "alarm_threshold": 3, "gouvernorat_code": BIZERTE}
    assert (await client.post(URL, json=body, headers=manager)).status_code == 403
    body |= {"gouvernorat_code": None, "code": sensor["code"].lower()}
    assert (await client.post(URL, json=body, headers=manager)).status_code == 409
    # Out of scope: a manager of another gouvernorat cannot edit it (it reads as missing).
    edit = {
        "name": "مقياس [SIM]",
        "lat": 33.9,
        "lon": 10.1,
        "provider": "INM",
        "silent_after_min": 15,
        "enabled": True,
        "watch_threshold": 25,
        "alarm_threshold": 50,
    }
    r = await client.put(f"{URL}/{sensor['id']}", json=edit, headers=staff(["ops_manager"], gouvernorat=BIZERTE))
    assert r.status_code == 404
    r = await client.put(f"{URL}/{sensor['id']}", json=edit, headers=manager)
    assert r.status_code == 200 and r.json()["watch_threshold"] == 25
    # Rotation: a new key, and the old one no longer signs.
    rotated = await client.post(f"{URL}/{sensor['id']}/key", headers=manager)
    assert rotated.status_code == 200 and rotated.json()["key"] != key
    r = await client.post(INGEST, json={"readings": [_reading(sensor["code"], key, "1")]}, headers=GATEWAY)
    assert r.json()["rejected"] == {"bad_signature": 1}


async def test_gateway_is_local_and_token_bound(client: httpx.AsyncClient, staff: Staff) -> None:
    created = await _create(client, staff)
    body = {"readings": [_reading(created["sensor"]["code"], created["key"], "3")]}
    assert (await client.post(INGEST, json=body)).status_code == 401
    assert (await client.post(INGEST, json=body, headers={"X-Gateway-Token": "x" * 30})).status_code == 401
    outside = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=("203.0.113.9", 4000)), base_url="http://api.test"
    )
    async with outside:
        assert (await outside.post(INGEST, json=body, headers=GATEWAY)).status_code == 403
    r = await client.post(INGEST, json=body, headers=GATEWAY)
    assert r.status_code == 200 and r.json() == {"accepted": 1, "rejected": {}, "suggestions": 0}


async def test_readings_rated_refused_and_suggested(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    created = await _create(client, staff)
    sensor, key = created["sensor"], created["key"]
    code = sensor["code"]
    now = datetime.now(UTC)
    tampered = _reading(code, key, "5", now - timedelta(minutes=4)) | {"value": "50"}
    batch = [
        _reading(code, key, "5", now - timedelta(minutes=5)),
        _reading(code, key, "25", now - timedelta(minutes=1)),
        tampered,
        _reading(code, key, "5", now - timedelta(minutes=30)),
        _reading(code, key, "999", now - timedelta(minutes=3)),
        _reading("NOPE-1", key, "5"),
    ]
    r = await client.post(INGEST, json={"readings": batch}, headers=GATEWAY)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["accepted"] == 2 and out["suggestions"] == 1
    assert out["rejected"] == {"bad_signature": 1, "bad_time": 1, "bad_value": 1, "unknown_sensor": 1}
    # A replay of an accepted reading is refused.
    r = await client.post(INGEST, json={"readings": [batch[0]]}, headers=GATEWAY)
    assert r.json()["rejected"] == {"replay": 1}
    listed = (await client.get(URL, headers=staff(["operator"], gouvernorat=GABES))).json()
    mine = next(s for s in listed["items"] if s["id"] == sensor["id"])
    assert mine["state"] == "watch" and mine["last_value"] == 25
    hist = (await client.get(f"{URL}/{sensor['id']}/readings", headers=staff(["operator"], gouvernorat=GABES))).json()
    assert [i["value"] for i in hist["items"]] == [5, 25]
    suggestions = (
        await session.scalars(
            select(AlertSuggestion).where(AlertSuggestion.evidence["sensor_id"].astext == sensor["id"])
        )
    ).all()
    assert len(suggestions) == 1
    first = suggestions[0]
    assert first.metric == "sensor_rain_1h" and first.severity == "medium" and first.status == "pending"
    assert first.simulated and first.gouvernorat_codes == [GABES] and first.hazard == "heavy_rain"
    # Still at watch: no second suggestion; up to alarm: a stronger one.
    await client.post(INGEST, json={"readings": [_reading(code, key, "30")]}, headers=GATEWAY)
    r = await client.post(
        INGEST,
        json={"readings": [_reading(code, key, "45", datetime.now(UTC) + timedelta(seconds=1))]},
        headers=GATEWAY,
    )
    assert r.json()["suggestions"] == 1
    session.expire_all()
    severities = sorted(
        s.severity
        for s in await session.scalars(
            select(AlertSuggestion).where(AlertSuggestion.evidence["sensor_id"].astext == sensor["id"])
        )
    )
    assert severities == ["high", "medium"]
    # The suggestion is visible to the editors of the gouvernorat, in the existing alert centre.
    page = await client.get("/api/v1/staff/weather/suggestions", headers=staff(["content_editor"], gouvernorat=GABES))
    assert page.status_code == 200, page.text
    assert {s["metric"] for s in page.json()["items"]} >= {"sensor_rain_1h"}
