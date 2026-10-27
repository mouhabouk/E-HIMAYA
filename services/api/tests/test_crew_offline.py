# covers: F-STF-07, F-APP-38
"""Staff app without network (phase P4d, docs/phase-p4/design-staff.md §9): steps kept on the phone keep the phone's
time, the vehicle's positions during the mission, the signed EH2 text messages through the SMS gateway, the data-only
mission push, and the reporter told that the team is on its way, then there (F-APP-38)."""

import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notify.providers import FcmPush, Push
from app.modules.ops import crew_sms
from tests.test_crew import Staff, write
from tests.test_crew_field import _incident, _mission

SMS_SECRET = "test-sms-inbound-secret-000001"


def _iso(at: datetime) -> str:
    return at.astimezone(UTC).isoformat().replace("+00:00", "Z")


async def _sms(client: httpx.AsyncClient, body: str, sender: str = "+21698000111") -> dict[str, Any]:
    raw = json.dumps({"message_id": uuid.uuid4().hex, "from": sender, "text": body}).encode()
    ts = str(int(time.time()))
    mac = hmac.new(SMS_SECRET.encode(), ts.encode() + b"." + raw, hashlib.sha256).hexdigest()
    headers = {"X-Timestamp": ts, "X-Signature": f"sha256={mac}", "Content-Type": "application/json"}
    r = await client.post("/internal/sms/inbound", content=raw, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


def _eh2(key: str, device: str, assignment: str, event: str, client_id: str, at: datetime | None = None) -> str:
    """The message the phone writes (apps/mobile/lib/staff/staff_sms.dart)."""
    ts = str(int((at or datetime.now(UTC)).timestamp()))
    parts = [device.replace("-", ""), assignment.replace("-", ""), event, ts, client_id.replace("-", "")]
    signature = crew_sms.sign(key, "|".join(["EH2", *parts]))
    return " ".join(["EH2", *parts, signature])


async def test_late_steps_keep_the_phone_time(client: httpx.AsyncClient, staff: Staff) -> None:
    leader, path, incident_id, _ = await _mission(client, staff, on_scene=False)
    mission = (await leader.get("/missions")).json()["items"][0]
    ordered = datetime.fromisoformat(mission["created_at"])

    # Kept on the phone without network, sent later: the step keeps the phone's time.
    en_route = ordered + (datetime.now(UTC) - ordered) / 2
    r = await leader.post(f"{path}/status", write(status="en_route", device_at=_iso(en_route)))
    assert datetime.fromisoformat(r.json()["en_route_at"]) == en_route
    # A clock before the last step, or in the future, is not believed: the server's time.
    before = datetime.now(UTC)
    r = await leader.post(f"{path}/status", write(status="on_scene", device_at=_iso(ordered)))
    assert datetime.fromisoformat(r.json()["on_scene_at"]) >= before

    detail = await _incident(client, staff, incident_id)
    assert detail["assignments"][0]["en_route_at"] is not None


async def test_positions_of_the_vehicle(client: httpx.AsyncClient, staff: Staff) -> None:
    leader, path, incident_id, place = await _mission(client, staff, on_scene=False)
    assert (await leader.post(f"{path}/status", write(status="en_route"))).status_code == 200
    now = datetime.now(UTC)
    near = {"lat": place["lat"] + 0.01, "lon": place["lon"], "accuracy_m": 12.0}
    points = [
        {**near, "at": _iso(now - timedelta(seconds=30))},
        {"lat": place["lat"] + 0.005, "lon": place["lon"], "at": _iso(now - timedelta(seconds=1))},
        {"lat": 48.85, "lon": 2.35, "at": _iso(now)},  # outside Tunisia
        {**near, "at": _iso(now + timedelta(hours=1))},  # in the future
    ]
    r = await leader.post(f"{path}/positions", {"points": points})
    assert r.status_code == 200, r.text
    assert r.json() == {"accepted": 2}
    # The same points again (the phone resent its queue): nothing new.
    assert (await leader.post(f"{path}/positions", {"points": points[:2]})).json() == {"accepted": 0}
    assert (await leader.post(f"{path}/positions", {"points": []})).status_code == 422

    position = (await _incident(client, staff, incident_id))["assignments"][0]["position"]
    assert position["lat"] == points[1]["lat"] and 400 <= position["distance_m"] <= 700
    assert datetime.fromisoformat(position["at"]) == datetime.fromisoformat(points[1]["at"])


async def test_signed_text_messages(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    leader, path, incident_id, _ = await _mission(client, staff, on_scene=False)
    assignment = path.removeprefix("/missions/")
    r = await leader.post("/devices/current/sms-key")
    assert r.status_code == 200, r.text
    key = r.json()["key"]
    assert (await leader.post("/devices/current/sms-key")).json()["key"] == key  # the same key every time
    assert leader.device is not None

    cid = str(uuid.uuid4())
    message = _eh2(key, leader.device, assignment, "en_route", cid)
    assert len(message) <= 160
    assert await _sms(client, message) == {"status": "applied", "tracking_code": None, "reason": None}
    assert (await _sms(client, message))["status"] == "duplicate"
    # The phone sends the same write over the internet once it is back: applied once.
    r = await leader.post(f"{path}/status", {"client_id": cid, "status": "en_route"})
    assert r.status_code == 200 and r.json()["status"] == "en_route"

    forged = _eh2("not-the-key", leader.device, assignment, "on_scene", str(uuid.uuid4()))
    assert (await _sms(client, forged))["reason"] == "invalid_signature"
    old = _eh2(key, leader.device, assignment, "on_scene", str(uuid.uuid4()), datetime.now(UTC) - timedelta(hours=13))
    assert (await _sms(client, old))["reason"] == "too_old"
    tampered = _eh2(key, leader.device, assignment, "ack", str(uuid.uuid4())).replace(" ack ", " released ")
    assert (await _sms(client, tampered))["reason"] == "invalid_signature"

    danger = _eh2(key, leader.device, assignment, "danger", str(uuid.uuid4()))
    assert (await _sms(client, danger))["status"] == "applied"
    # A step the mission does not allow is ignored, never retried by the gateway.
    wrong = _eh2(key, leader.device, assignment, "en_route", str(uuid.uuid4()))
    assert (await _sms(client, wrong)) == {"status": "ignored", "tracking_code": None, "reason": "invalid_transition"}

    detail = await _incident(client, staff, incident_id)
    [alert] = detail["alerts"]
    assert alert["kind"] == "danger" and alert["via"] == "sms" and alert["items"] == []
    via = (
        await session.execute(
            text("SELECT kind, via FROM ops.crew_event WHERE assignment_id = :a ORDER BY received_at"),
            {"a": assignment},
        )
    ).all()
    assert [tuple(v) for v in via] == [("status", "sms"), ("alert", "sms")]
    actions = (
        await session.execute(
            text("SELECT action FROM audit.log WHERE target = :t AND action LIKE 'crew.sms_%' ORDER BY id"),
            {"t": f"assignment:{assignment}"},
        )
    ).scalars()
    assert list(actions) == ["crew.sms_en_route", "crew.sms_danger"]

    # A revoked phone's messages are ignored.
    await session.execute(text("UPDATE ops.staff_device SET revoked_at = now() WHERE id = :d"), {"d": leader.device})
    await session.commit()
    gone = _eh2(key, leader.device, assignment, "on_scene", str(uuid.uuid4()))
    assert (await _sms(client, gone))["reason"] == "unknown_device"


async def test_reporter_told_the_team_is_coming(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    leader, path, incident_id, _ = await _mission(client, staff, on_scene=False)
    report_id = (await _incident(client, staff, incident_id))["reports"][0]["id"]
    code = (
        await session.execute(text("SELECT tracking_code FROM reports.report WHERE id = :r"), {"r": report_id})
    ).scalar_one()

    tracked = (await client.get(f"/api/v1/reports/track/{code}")).json()
    assert tracked["team_en_route_at"] is None and tracked["team_on_scene_at"] is None
    assert (await leader.post(f"{path}/status", write(status="en_route"))).status_code == 200
    assert (await leader.post(f"{path}/status", write(status="on_scene"))).status_code == 200
    tracked = (await client.get(f"/api/v1/reports/track/{code}")).json()
    assert tracked["team_en_route_at"] <= tracked["team_on_scene_at"]

    pushes = (
        await session.execute(
            text(
                "SELECT o.payload FROM notify.outbox o JOIN reports.report r ON r.user_id = o.user_id "
                "WHERE r.id = :r AND o.payload->>'type' = 'team_status' ORDER BY o.id"
            ),
            {"r": report_id},
        )
    ).scalars()
    payloads = list(pushes)
    assert [p["data"]["team"] for p in payloads] == ["en_route", "on_scene"]
    assert payloads[0]["body"]["ar"] == "الفريق في الطريق إليك."
    assert set(payloads[0]["data"]) == {"report_id", "tracking_code", "team", "redacted"}


def test_mission_push_is_data_only_on_android() -> None:
    push = FcmPush({"client_email": "x", "token_uri": "x", "private_key": "x", "project_id": "p"})
    android = Push("t", "android", "مهمة جديدة", "افتح التطبيق", {"type": "mission"}, True, True, data_only=True)
    message = push.message(android)["message"]
    assert "notification" not in message and message["android"] == {"priority": "high", "ttl": "600s"}
    assert message["data"] == {"type": "mission", "title": "مهمة جديدة", "body": "افتح التطبيق"}
    ios = Push("t", "ios", "مهمة جديدة", "افتح التطبيق", {"type": "mission"}, True, True, data_only=True)
    assert push.message(ios)["message"]["notification"]["title"] == "مهمة جديدة"
