# covers: F-STF-01, F-STF-02, F-STF-03, F-STF-04
"""Staff app of team leaders (phase P4a, docs/phase-p4/design-staff.md §4): device, shift, missions, steps, first
field report, casualties, the room's view and the remote wipe."""

import uuid
from collections.abc import Callable
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_operations import make_resource, new_report, random_place, report_status

Staff = Callable[..., dict[str, str]]


class Leader:
    """A team leader of Sfax (61) with a stable account, and their registered phone."""

    def __init__(self, client: httpx.AsyncClient, staff: Staff, gouvernorat: int = 61) -> None:
        self.client = client
        self.sub = str(uuid.uuid4())
        self.headers = staff(["team_leader"], gouvernorat, sub=self.sub, name="سامي الطرابلسي")
        self.device: str | None = None

    async def register(self, push_token: str | None = "fcm-token-leader") -> dict[str, Any]:  # noqa: S107
        r = await self.client.post(
            "/api/v1/crew/devices",
            json={"platform": "android", "label": "Galaxy A15", "app_build": 1, "push_token": push_token},
            headers=self.headers,
        )
        assert r.status_code == 201, r.text
        self.device = r.json()["id"]
        return r.json()  # type: ignore[no-any-return]

    @property
    def h(self) -> dict[str, str]:
        assert self.device is not None
        return {**self.headers, "X-Staff-Device": self.device}

    async def post(self, path: str, body: dict[str, Any] | None = None) -> httpx.Response:
        return await self.client.post(f"/api/v1/crew{path}", json=body or {}, headers=self.h)

    async def get(self, path: str) -> httpx.Response:
        return await self.client.get(f"/api/v1/crew{path}", headers=self.h)


async def new_incident(client: httpx.AsyncClient, staff: Staff, location: dict[str, float]) -> tuple[str, str]:
    """A new incident even next to another test's open one (random places of the shared database can meet)."""
    report = await new_report(client, location)
    r = await client.post(
        f"/api/v1/staff/reports/{report['id']}/incident",
        json={"action": "new", "override_reason": "حادث منفصل للاختبار"},
        headers=staff(["operator"]),
    )
    assert r.status_code == 200, r.text
    return r.json()["incident_id"], report["id"]


def write(**fields: Any) -> dict[str, Any]:
    return {"client_id": str(uuid.uuid4()), "device_at": "2026-10-26T21:00:00Z", **fields}


async def _on_shift(client: httpx.AsyncClient, staff: Staff) -> tuple[Leader, dict[str, Any]]:
    leader = Leader(client, staff)
    await leader.register()
    resource = await make_resource(client, staff)
    r = await leader.post("/shifts", write(resource_id=resource["id"], crew_size=4, crew_names="علي، منير"))
    assert r.status_code == 201, r.text
    return leader, resource


async def test_device_and_shift(client: httpx.AsyncClient, staff: Staff) -> None:
    leader = Leader(client, staff)
    # Only team leaders, only with a gouvernorat, only with a registered phone.
    assert (
        await client.post("/api/v1/crew/devices", json={"platform": "android"}, headers=staff(["operator"]))
    ).status_code == 403
    national = staff(["team_leader"], None)
    r = await client.post("/api/v1/crew/devices", json={"platform": "android"}, headers=national)
    assert r.json()["detail"] == "regional_account_required"
    assert (await client.get("/api/v1/crew/me", headers=leader.headers)).json()["detail"] == "device_required"
    device = await leader.register()
    assert device["holder_name"] == "سامي الطرابلسي" and device["revoked_at"] is None

    me = (await leader.get("/me")).json()
    assert me["gouvernorat_code"] == 61 and me["shift"] is None and me["device"]["id"] == leader.device

    resource = await make_resource(client, staff)
    vehicles = (await leader.get("/resources")).json()
    mine = next(v for v in vehicles if v["id"] == resource["id"])
    assert mine["on_shift"] is False and mine["unit_name"]
    # A vehicle of another gouvernorat is not offered and cannot be taken.
    tunis = Leader(client, staff, gouvernorat=11)
    await tunis.register()
    assert resource["id"] not in [v["id"] for v in (await tunis.get("/resources")).json()]
    r = await tunis.post("/shifts", write(resource_id=resource["id"], crew_size=3))
    assert r.status_code == 404

    r = await leader.post("/shifts", write(resource_id=resource["id"], crew_size=4))
    assert r.status_code == 201, r.text
    shift = r.json()
    assert shift["resource"]["id"] == resource["id"] and shift["crew_size"] == 4
    assert (await leader.post("/shifts", write(resource_id=resource["id"], crew_size=4))).json()[
        "detail"
    ] == "shift_open"
    other = Leader(client, staff)
    await other.register()
    assert (await other.post("/shifts", write(resource_id=resource["id"], crew_size=2))).json()[
        "detail"
    ] == "resource_on_shift"
    assert next(v for v in (await other.get("/resources")).json() if v["id"] == resource["id"])["on_shift"] is True

    me = (await leader.get("/me")).json()
    assert me["shift"]["id"] == shift["id"] and me["device"]["on_shift"] is True
    teams = (await client.get("/api/v1/staff/shifts", headers=staff(["operator"]))).json()
    assert any(t["id"] == shift["id"] and t["leader_name"] == "سامي الطرابلسي" for t in teams)
    assert shift["id"] not in [
        t["id"] for t in (await client.get("/api/v1/staff/shifts", headers=staff(["operator"], 11))).json()
    ]

    r = await leader.post("/shifts/current/end")
    assert r.status_code == 200 and r.json()["ended_at"]
    assert (await leader.get("/me")).json()["shift"] is None


async def test_mission_steps_report_and_casualties(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    leader, resource = await _on_shift(client, staff)
    place = random_place()
    incident_id, report_id = await new_incident(client, staff, place)
    operator = staff(["operator"])
    r = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/assignments",
        json={"resource_id": resource["id"], "order": "حريق مستودع، التوجه فورا"},
        headers=operator,
    )
    assert r.status_code == 201, r.text
    assignment = r.json()
    assert assignment["crew"]["leader_name"] == "سامي الطرابلسي" and assignment["crew"]["crew_size"] == 4
    assert assignment["crew"]["acknowledged_at"] is None

    # The leader's phone rang: a content-free urgent push with the assignment id only.
    push = (
        await session.execute(
            text("SELECT address, payload FROM notify.outbox WHERE channel = 'staff_push' ORDER BY id DESC LIMIT 1")
        )
    ).one()
    assert push.address == "fcm-token-leader"
    assert push.payload["data"] == {"assignment_id": assignment["id"], "redacted": "1"}
    assert push.payload["type"] == "mission" and "حريق" not in str(push.payload)

    missions = (await leader.get("/missions")).json()["items"]
    mission = next(m for m in missions if m["id"] == assignment["id"])
    assert mission["status"] == "ordered" and mission["order"] == "حريق مستودع، التوجه فورا"
    assert mission["incident"]["id"] == incident_id and mission["incident"]["location"]
    path = f"/missions/{assignment['id']}"

    ack = write()
    assert (await leader.post(f"{path}/ack", ack)).json()["acknowledged_at"]
    assert (await leader.post(f"{path}/ack", ack)).status_code == 200  # sent twice, applied once

    # Not on scene yet: no first report.
    early = write(category="fire", severity=2)
    assert (await leader.post(f"{path}/first-report", early)).json()["detail"] == "not_on_scene"

    en_route = write(status="en_route", lat=place["lat"] + 0.05, lon=place["lon"])
    r = await leader.post(f"{path}/status", en_route)
    assert r.json()["status"] == "en_route" and r.json()["distance_m"] > 5000
    again = await leader.post(f"{path}/status", en_route)
    assert again.status_code == 200 and again.json()["status"] == "en_route"
    r = await leader.post(f"{path}/status", write(status="released"))
    assert r.json()["detail"] == "invalid_transition"
    r = await leader.post(f"{path}/status", write(status="on_scene", lat=place["lat"], lon=place["lon"]))
    assert r.json()["status"] == "on_scene" and r.json()["distance_m"] < 150
    assert await report_status(client, staff, report_id) == "intervened"

    bad = write(category="fire", classification="rockfall", severity=3)
    assert (await leader.post(f"{path}/first-report", bad)).json()["detail"] == "invalid_classification"
    first = write(
        category="fire",
        classification="industrial_fire",
        severity=3,
        backup_needed=True,
        backup_note="شاحنة مياه إضافية",
        crew_danger=True,
    )
    r = await leader.post(f"{path}/first-report", first)
    assert r.status_code == 200, r.text
    report = r.json()["field_report"]
    assert report["severity"] == 3 and report["crew_danger"] and report["backup_note"] == "شاحنة مياه إضافية"

    plus = write(injured=2, trapped=1)
    assert (await leader.post(f"{path}/casualties", plus)).json()["casualties"]["injured"] == 2
    assert (await leader.post(f"{path}/casualties", plus)).json()["casualties"]["injured"] == 2
    r = await leader.post(f"{path}/casualties", write(injured=-5, rescued=1, trapped=-1))
    counts = r.json()["casualties"]
    assert (counts["injured"], counts["rescued"], counts["trapped"], counts["deceased"]) == (0, 1, 0, 0)
    assert (await leader.post(f"{path}/casualties", write(injured=99))).status_code == 422

    r = await leader.post(
        f"{path}/transports", write(triage="red", age_band="adult", sex="male", hospital="مستشفى الحبيب بورقيبة")
    )
    assert r.status_code == 200 and r.json()["transports"][0]["triage"] == "red"
    assert (
        await leader.post(f"{path}/transports", write(triage="blue", age_band="adult", sex="male", hospital="x"))
    ).status_code == 422

    # The shift cannot end while the vehicle is on a mission.
    assert (await leader.post("/shifts/current/end")).json()["detail"] == "mission_active"
    r = await leader.post(f"{path}/status", write(status="released"))
    assert r.json()["status"] == "released"
    vehicles = (await client.get("/api/v1/staff/resources", headers=operator)).json()["items"]
    assert next(v for v in vehicles if v["id"] == resource["id"])["status"] == "available"
    # The ended mission stays on the phone for a while.
    assert assignment["id"] in [m["id"] for m in (await leader.get("/missions")).json()["items"]]

    # The room sees the team, the first report, the counters and the transport in the incident card.
    detail = (await client.get(f"/api/v1/staff/incidents/{incident_id}", headers=operator)).json()
    card = next(a for a in detail["assignments"] if a["id"] == assignment["id"])
    assert card["crew"]["acknowledged_at"] and card["status"] == "released"
    assert (
        detail["field_reports"][0]["crew_danger"] and detail["field_reports"][0]["resource_label"] == resource["label"]
    )
    assert detail["casualties"]["rescued"] == 1
    assert detail["transports"][0]["hospital"] == "مستشفى الحبيب بورقيبة"
    kinds = {e["kind"] for e in detail["timeline"]}
    assert {"crew_ack", "assignment_status", "field_report", "casualties", "transport"} <= kinds
    steps = [e for e in detail["timeline"] if e["kind"] == "assignment_status"]
    assert [e["payload"]["status"] for e in steps] == ["en_route", "on_scene", "released"]

    # Every write is in the audit log under the leader's account.
    actions = (
        (
            await session.execute(
                text("SELECT action FROM audit.log WHERE actor = :a ORDER BY id"), {"a": f"ehimaya-staff:{leader.sub}"}
            )
        )
        .scalars()
        .all()
    )
    assert {
        "crew.shift_start",
        "crew.ack",
        "crew.status",
        "crew.first_report",
        "crew.casualties",
        "crew.transport",
    } <= set(actions)


async def test_missions_belong_to_the_vehicle_on_shift(client: httpx.AsyncClient, staff: Staff) -> None:
    leader, _ = await _on_shift(client, staff)
    other_vehicle = await make_resource(client, staff)
    incident_id, _ = await new_incident(client, staff, random_place())
    r = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/assignments",
        json={"resource_id": other_vehicle["id"]},
        headers=staff(["operator"]),
    )
    other = r.json()
    assert other["crew"] is None  # no shift on that vehicle
    assert other["id"] not in [m["id"] for m in (await leader.get("/missions")).json()["items"]]
    assert (await leader.post(f"/missions/{other['id']}/ack", write())).status_code == 404
    assert (await leader.post(f"/missions/{other['id']}/status", write(status="en_route"))).status_code == 404

    # A shift started on a vehicle already on a mission takes that mission over.
    late = Leader(client, staff)
    await late.register()
    assert (await late.post("/shifts", write(resource_id=other_vehicle["id"], crew_size=2))).status_code == 201
    assert other["id"] in [m["id"] for m in (await late.get("/missions")).json()["items"]]


async def test_remote_wipe(client: httpx.AsyncClient, staff: Staff) -> None:
    leader, _ = await _on_shift(client, staff)
    admin = staff(["regional_account_admin"], 61)
    devices = (await client.get("/api/v1/staff/crew-devices", headers=admin)).json()
    row = next(d for d in devices if d["id"] == leader.device)
    assert row["on_shift"] is True and row["holder_name"] == "سامي الطرابلسي"
    # Another gouvernorat's administrator neither sees nor revokes it; an operator cannot.
    tunis_admin = staff(["regional_account_admin"], 11)
    assert leader.device not in [
        d["id"] for d in (await client.get("/api/v1/staff/crew-devices", headers=tunis_admin)).json()
    ]
    assert (
        await client.post(f"/api/v1/staff/crew-devices/{leader.device}/revoke", headers=tunis_admin)
    ).status_code == 404
    assert (
        await client.post(f"/api/v1/staff/crew-devices/{leader.device}/revoke", headers=staff(["operator"]))
    ).status_code == 403

    r = await client.post(f"/api/v1/staff/crew-devices/{leader.device}/revoke", headers=admin)
    assert r.status_code == 200 and r.json()["revoked_at"]
    r = await leader.get("/me")
    assert r.status_code == 410 and r.json()["detail"] == "device_revoked"
    # The shift on that phone is over; the leader registers the phone again after signing in.
    await leader.register()
    assert (await leader.get("/me")).json()["shift"] is None
    # Someone else's device id is not accepted.
    stranger = Leader(client, staff)
    r = await client.get("/api/v1/crew/me", headers={**stranger.headers, "X-Staff-Device": leader.device or ""})
    assert r.json()["detail"] == "device_unknown"
