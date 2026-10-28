"""Drones as read-only sources (L5b, docs/phase-l/design-l5.md §3.3): the register and its scope, the publish token
shown once, the work areas and no-fly zones a room draws, the positions the reader beside MediaMTX relays (and every
way a point is refused), the alerts they raise once per cool-down, and their acknowledgement.

The last test is permanent: nothing may ever send a command to a drone. It fails if a drone route other than the
read-only ones below appears, or if MAVLink command names or a drone-control library show up in the code."""

import os
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from fastapi.routing import APIRoute, iter_route_contexts
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.drones import domain
from app.modules.drones.models import DroneAlert
from app.modules.streams.models import LiveStream

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/drones"
TELEMETRY = "/internal/drones/telemetry"
GATEWAY = {"X-Gateway-Token": "test-sensor-gateway-token-0001"}
JENDOUBA, BIZERTE = 32, 23


def _square(lat: float, lon: float, half: float) -> list[list[float]]:
    return [[lon - half, lat - half], [lon + half, lat - half], [lon + half, lat + half], [lon - half, lat + half]]


async def _register(client: httpx.AsyncClient, staff: Staff, gouvernorat: int = JENDOUBA) -> dict[str, Any]:
    r = await client.post(
        URL, json={"label": "درون الحماية 1 [SIM]"}, headers=staff(["ops_manager"], gouvernorat=gouvernorat)
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def _point(at: datetime, lat: float, lon: float, **extra: Any) -> dict[str, Any]:
    return {"at": at.isoformat(), "lat": lat, "lon": lon, **extra}


def test_rules_free_of_the_database() -> None:
    assert domain.camera_reach_m(None) == 300 and domain.camera_reach_m(200) == 600
    assert domain.camera_reach_m(5000) == 3000
    # The low battery is told once, when it crosses the threshold.
    assert domain.battery_alert(None, 20) and domain.battery_alert(30, 24.9)
    assert not domain.battery_alert(24, 20) and not domain.battery_alert(30, None) and not domain.battery_alert(30, 25)


async def test_register_scope_and_token_shown_once(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    created = await _register(client, staff)
    drone = created["drone"]
    assert created["publish_token"] and created["publish_url_rtsp"].endswith(f"live/{drone['id']}")
    assert drone["last"] is None and drone["camera_view"] is None and drone["open_alerts"] == 0
    stream = await session.get(LiveStream, uuid.UUID(drone["id"]))
    assert stream is not None and stream.source == "drone" and stream.gouvernorat_code == JENDOUBA
    logs = (await session.scalars(select(AuditLog).where(AuditLog.target == f"stream:{drone['id']}"))).all()
    assert logs and all(created["publish_token"] not in str(log.details) for log in logs)
    mine = (await client.get(URL, headers=staff(["operator"], gouvernorat=JENDOUBA))).json()
    assert drone["id"] in {d["id"] for d in mine["items"]} and mine["can_register"] is False
    assert all("publish_token" not in d for d in mine["items"])
    other = (await client.get(URL, headers=staff(["operator"], gouvernorat=BIZERTE))).json()
    assert drone["id"] not in {d["id"] for d in other["items"]}
    central = (await client.get(URL, headers=staff(["operator"], gouvernorat=None))).json()
    assert drone["id"] in {d["id"] for d in central["items"]}
    r = await client.get(f"{URL}/{drone['id']}/track", headers=staff(["operator"], gouvernorat=BIZERTE))
    assert r.status_code == 404
    # Only the operations manager registers, in their own gouvernorat.
    body = {"label": "x [SIM]"}
    assert (await client.post(URL, json=body, headers=staff(["operator"], gouvernorat=JENDOUBA))).status_code == 403
    manager = staff(["ops_manager"], gouvernorat=JENDOUBA)
    r = await client.post(URL, json=body | {"gouvernorat_code": BIZERTE}, headers=manager)
    assert r.status_code == 403


async def test_zones_telemetry_alerts_and_acknowledgement(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    drone = (await _register(client, staff))["drone"]
    manager = staff(["ops_manager"], gouvernorat=JENDOUBA)
    operator = staff(["operator"], gouvernorat=JENDOUBA)
    work = {"kind": "work", "name": "غابة عين دراهم [SIM]", "ring": _square(36.78, 8.69, 0.05)}
    r = await client.post(f"{URL}/zones", json=work, headers=manager)
    assert r.status_code == 201, r.text
    assert r.json()["ring"][0] == r.json()["ring"][-1] and len(r.json()["ring"]) == 5
    no_fly = {"kind": "no_fly", "name": "منطقة محظورة [SIM]", "ring": _square(36.91, 8.70, 0.01), "margin_m": 2000}
    zone = (await client.post(f"{URL}/zones", json=no_fly, headers=manager)).json()
    # A self-crossing ring, a ring outside Tunisia, an operator, another gouvernorat: refused.
    bow = {**work, "ring": [[8.6, 36.7], [8.8, 36.9], [8.8, 36.7], [8.6, 36.9]]}
    assert (await client.post(f"{URL}/zones", json=bow, headers=manager)).json()["detail"] == "invalid_area"
    far = {**work, "ring": _square(48.85, 2.35, 0.1)}
    assert (await client.post(f"{URL}/zones", json=far, headers=manager)).status_code == 422
    assert (await client.post(f"{URL}/zones", json=work, headers=operator)).status_code == 403
    assert (
        await client.post(f"{URL}/zones", json=work | {"gouvernorat_code": BIZERTE}, headers=manager)
    ).status_code == 403
    assert zone["id"] in {z["id"] for z in (await client.get(f"{URL}/zones", headers=operator)).json()}
    other_room = staff(["operator"], gouvernorat=BIZERTE)
    assert zone["id"] not in {z["id"] for z in (await client.get(f"{URL}/zones", headers=other_room)).json()}

    now = datetime.now(UTC)
    camera = {"heading_deg": 90.0, "sensor_az_deg": 0.0, "sensor_hfov_deg": 60.0, "alt_m": 200.0}
    points = [
        _point(now - timedelta(seconds=30), 36.78, 8.69, battery_pct=30.0),  # inside the work area
        _point(now - timedelta(seconds=20), 36.885, 8.70, battery_pct=24.0),  # out of it, 1.7 km from the no-fly zone
        _point(now - timedelta(seconds=10), 36.91, 8.70, battery_pct=20.0, **camera),  # inside the no-fly zone
        _point(now - timedelta(hours=1), 36.78, 8.69),  # too old
    ]
    body = {"stream_id": drone["id"], "points": points}
    assert (await client.post(TELEMETRY, json=body)).status_code in (401, 403)
    r = await client.post(TELEMETRY, json=body, headers=GATEWAY)
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["accepted"] == 3 and result["rejected"] == {"bad_time": 1}
    assert result["alerts"] == ["near_no_fly", "left_work_area", "low_battery", "in_no_fly"]
    # The same points again are replays; a later point outside the work area is within the cool-down.
    again = {"stream_id": drone["id"], "points": [*points[:3], _point(now, 36.90, 8.60)]}
    result = (await client.post(TELEMETRY, json=again, headers=GATEWAY)).json()
    assert result == {"accepted": 1, "rejected": {"replay": 3}, "alerts": []}
    # Not a drone: the reader is told so.
    camera_stream = (await session.scalars(select(LiveStream.id).where(LiveStream.source != "drone").limit(1))).first()
    if camera_stream is not None:
        wrong = {"stream_id": str(camera_stream), "points": points[:1]}
        assert (await client.post(TELEMETRY, json=wrong, headers=GATEWAY)).status_code == 404

    listed = (await client.get(URL, headers=operator)).json()
    mine = next(d for d in listed["items"] if d["id"] == drone["id"])
    assert mine["last"]["lat"] == 36.90 and mine["open_alerts"] == 4 and mine["camera_view"] is None
    track = (await client.get(f"{URL}/{drone['id']}/track", headers=operator)).json()["items"]
    assert [p["lat"] for p in track] == [36.78, 36.885, 36.91, 36.90]
    alerts = (await client.get(f"{URL}/alerts", headers=operator)).json()
    ours = [a for a in alerts if a["drone_id"] == drone["id"]]
    assert {a["kind"] for a in ours} == set(domain.ALERT_KINDS)
    near = next(a for a in ours if a["kind"] == "near_no_fly")
    assert near["zone_name"] == no_fly["name"] and 1000 < near["detail"]["distance_m"] < 2000
    other_alerts = (await client.get(f"{URL}/alerts", headers=other_room)).json()
    assert drone["id"] not in {a["drone_id"] for a in other_alerts}
    # Another room cannot acknowledge (it reads as missing); the drone's room can, once.
    assert (await client.post(f"{URL}/alerts/{near['id']}/ack", headers=other_room)).status_code == 404
    assert (await client.post(f"{URL}/alerts/{near['id']}/ack", headers=operator)).status_code == 204
    alert = await session.get(DroneAlert, near["id"])
    assert alert is not None and alert.acknowledged_at is not None
    open_now = (await client.get(f"{URL}/alerts?open_only=true", headers=operator)).json()
    assert near["id"] not in {a["id"] for a in open_now}

    # The camera's cone is drawn from the newest point that carries the camera's direction and opening.
    cone = {"stream_id": drone["id"], "points": [_point(now + timedelta(seconds=5), 36.80, 8.70, **camera)]}
    assert (await client.post(TELEMETRY, json=cone, headers=GATEWAY)).json()["accepted"] == 1
    mine = next(d for d in (await client.get(URL, headers=operator)).json()["items"] if d["id"] == drone["id"])
    view = mine["camera_view"]
    assert view[0] == view[-1] == [8.70, 36.80] and all(p[0] >= 8.70 for p in view)

    # Switching a zone off; the reader beside MediaMTX lists the drones on air.
    edit = {"name": no_fly["name"], "ring": no_fly["ring"], "margin_m": 0, "active": False}
    r = await client.put(f"{URL}/zones/{zone['id']}", json=edit, headers=manager)
    assert r.status_code == 200 and r.json()["active"] is False
    stream = await session.get(LiveStream, uuid.UUID(drone["id"]))
    assert stream is not None
    stream.status = "live"
    await session.commit()
    live = (await client.get("/internal/drones/live", headers=GATEWAY)).json()
    assert drone["id"] in live["items"]


# ---------------------------------------------------------------- permanent: no command path to a drone, ever

# Every drone route there is. A new one fails here until it is shown to send nothing to a drone.
READ_ONLY = {
    ("GET", "/api/v1/staff/drones"),
    ("POST", "/api/v1/staff/drones"),  # registers a stream; MediaMTX receives its video
    ("GET", "/api/v1/staff/drones/{drone_id}/track"),
    ("GET", "/api/v1/staff/drones/alerts"),
    ("POST", "/api/v1/staff/drones/alerts/{alert_id}/ack"),  # the room's own record
    ("GET", "/api/v1/staff/drones/zones"),
    ("POST", "/api/v1/staff/drones/zones"),  # the room's own map
    ("PUT", "/api/v1/staff/drones/zones/{zone_id}"),
    ("GET", "/internal/drones/live"),
    ("POST", "/internal/drones/telemetry"),  # positions coming in
}
_COMMAND = re.compile(
    "|".join(
        (
            r"\bCOMMAND_(LONG|INT|ACK)\b",
            r"\bMAV_CMD_\w+",
            r"\bSET_MODE\b",
            r"\bSET_POSITION_TARGET_\w+",
            r"\bMISSION_(ITEM|COUNT|START)\w*",
            r"\barm_?disarm\b",
            r"\b(py)?mavlink\b",
            r"\bdronekit\b",
            r"\bmavsdk\b",
            r"\bdji[_-]?sdk\b",
        )
    ),
    re.IGNORECASE,
)
_CODE = {".py", ".ts", ".tsx", ".js", ".mjs", ".go", ".rs", ".c", ".cpp", ".java", ".kt", ".swift", ".dart"}
_SKIP = {"node_modules", ".venv", "venv", "dist", "build", ".git", "__pycache__", ".mypy_cache", "coverage"}


def test_no_command_path_to_a_drone_ever() -> None:
    drone_routes = {
        (method, context.original_route.path)
        for context in iter_route_contexts(list(app.routes))
        if isinstance(context.original_route, APIRoute) and "drone" in context.original_route.path
        for method in context.original_route.methods or ()
        if method != "HEAD"
    }
    assert drone_routes == READ_ONLY
    root = Path(__file__).resolve().parents[3]
    found: list[str] = []
    for folder in ("services", "apps", "packages", "infra"):
        for dirpath, dirnames, filenames in os.walk(root / folder):
            dirnames[:] = [d for d in dirnames if d not in _SKIP]
            for name in filenames:
                path = Path(dirpath) / name
                if path.suffix not in _CODE or path.resolve() == Path(__file__).resolve():
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                found += [f"{path.relative_to(root)}: {m.group(0)}" for m in _COMMAND.finditer(text)]
    assert not found, found
