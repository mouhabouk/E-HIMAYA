# covers: F-SRV-57, F-STF-13
"""The record of a mission (phase S2, docs/phase-s/design-s2.md): the times from the order to the return to the
unit, given by the team's phone or by the room, always in order, the crew and what the mission used."""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.modules.ops import crew_sms, record
from tests.test_crew import Staff, _on_shift, new_incident, write
from tests.test_operations import make_resource, random_place


def _iso(at: datetime) -> str:
    return at.isoformat().replace("+00:00", "Z")


def test_rules() -> None:
    now = datetime.now(UTC)
    t = [now - timedelta(minutes=60 - 10 * i) for i in range(6)]
    times: dict[str, datetime | None] = dict(zip(record.CHAIN, t, strict=True))
    assert record.broken_rule(times, now) is None
    assert record.broken_rule(times | {"on_scene_at": t[0] - timedelta(minutes=1)}, now) == "times_out_of_order"
    assert record.broken_rule(times | {"back_at_unit_at": now + timedelta(minutes=10)}, now) == "time_in_future"
    assert record.broken_rule(times | {"left_scene_at": None}, now) == "time_needs_previous"
    assert record.broken_rule(times | {"en_route_at": None, "on_scene_at": None}, now) == "time_needs_previous"
    same = {f: t[1] for f in record.EDITABLE} | {"created_at": t[0]}
    assert record.broken_rule(same, now) == "return_before_departure"
    assert record.broken_rule(times | {"back_at_unit_at": t[0] + timedelta(hours=80)}, now + timedelta(days=4)) == (
        "mission_too_long"
    )
    # Hospital is optional, the return needs only the departure.
    assert record.broken_rule(times | {"at_hospital_at": None}, now) is None
    assert record.check_consumables({"water_m3": 3.5, "foam_l": 0}) == {"water_m3": 3.5}
    # The later steps also go by text message when there is no internet, under 160 characters.
    sms = f"EH2 {'a' * 32} {'b' * 32} back_at_unit 1793350000 {'c' * 32} {'d' * 16}"
    parsed = crew_sms.parse(sms)
    assert parsed is not None and parsed.event == "back_at_unit" and len(sms) < 160


async def test_team_records_the_mission(client: httpx.AsyncClient, staff: Staff) -> None:
    leader, resource = await _on_shift(client, staff)
    incident_id, _ = await new_incident(client, staff, random_place())
    operator = staff(["operator"])
    r = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/assignments",
        json={"resource_id": resource["id"], "order": "حادث مرور"},
        headers=operator,
    )
    assignment = r.json()
    path = f"/missions/{assignment['id']}"
    mission = (await leader.post(f"{path}/ack", write())).json()
    assert mission["crew_count"] == 4  # the shift's crew until the leader says otherwise

    # No step after the arrival before the arrival, and the steps in order.
    assert (await leader.post(f"{path}/milestone", write(step="left_scene"))).json()["detail"] == "invalid_transition"
    await leader.post(f"{path}/status", write(status="en_route"))
    await leader.post(f"{path}/status", write(status="on_scene"))
    r = await leader.post(f"{path}/milestone", write(step="at_hospital"))
    assert r.json()["detail"] == "time_needs_previous"
    left = write(step="left_scene")
    mission = (await leader.post(f"{path}/milestone", left)).json()
    assert mission["left_scene_at"] and mission["status"] == "on_scene"
    assert (await leader.post(f"{path}/milestone", left)).json()["left_scene_at"] == mission["left_scene_at"]
    mission = (await leader.post(f"{path}/milestone", write(step="at_hospital"))).json()
    assert mission["at_hospital_at"] >= mission["left_scene_at"] >= mission["on_scene_at"]

    r = await leader.post(f"{path}/record", write(crew_count=5, consumables={"water_m3": 3.5, "fuel_l": 20}))
    assert r.json()["crew_count"] == 5 and r.json()["consumables"] == {"water_m3": 3.5, "fuel_l": 20}
    assert (await leader.post(f"{path}/record", write(consumables={"sand": 1}))).status_code == 422
    assert (await leader.post(f"{path}/record", write(consumables={"water_m3": 5000}))).json()[
        "detail"
    ] == "consumable_out_of_range"

    # Back at the unit ends the mission and frees the vehicle.
    mission = (await leader.post(f"{path}/milestone", write(step="back_at_unit"))).json()
    assert mission["status"] == "released" and mission["back_at_unit_at"] > mission["en_route_at"]
    assert mission["released_at"] == mission["back_at_unit_at"]
    assert mission["time_sources"] == {f: "app" for f in record.EDITABLE}
    vehicles = (await client.get("/api/v1/staff/resources", params={"limit": 500}, headers=operator)).json()["items"]
    assert next(v for v in vehicles if v["id"] == resource["id"])["status"] == "available"

    # The room corrects a time the team gave: with a reason, and in order.
    url = f"/api/v1/staff/assignments/{assignment['id']}/record"
    earlier = mission["en_route_at"]  # the team pressed "on scene" late: it came with the departure
    r = await client.put(url, json={"times": {"on_scene_at": earlier}}, headers=operator)
    assert r.json()["detail"] == "correction_reason_required"
    before_departure = _iso(datetime.fromisoformat(mission["en_route_at"]) - timedelta(minutes=5))
    r = await client.put(
        url, json={"times": {"on_scene_at": before_departure}, "reason": "خطأ في الضغط"}, headers=operator
    )
    assert r.json()["detail"] == "times_out_of_order"
    future = _iso(datetime.now(UTC) + timedelta(hours=1))
    r = await client.put(url, json={"times": {"back_at_unit_at": future}, "reason": "تصحيح"}, headers=operator)
    assert r.json()["detail"] == "time_in_future"
    assert (await client.put(url, json={"times": {"on_scene_at": None}}, headers=operator)).json()[
        "detail"
    ] == "time_required"
    r = await client.put(
        url,
        json={"times": {"on_scene_at": earlier}, "crew_count": 6, "reason": "تأخر الضغط على الزر في المكان"},
        headers=operator,
    )
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["crew_count"] == 6 and saved["time_sources"]["on_scene_at"] == "room"
    assert saved["time_sources"]["en_route_at"] == "app"
    detail = (await client.get(f"/api/v1/staff/incidents/{incident_id}", headers=operator)).json()
    kinds = [e["kind"] for e in detail["timeline"]]
    assert kinds.count("mission_step") == 3 and "team_record" in kinds
    saved_event = next(e for e in detail["timeline"] if e["kind"] == "record_saved")
    assert saved_event["payload"]["reason"] == "تأخر الضغط على الزر في المكان"
    assert list(saved_event["payload"]["times"]) == ["on_scene_at"]


async def test_room_records_a_team_without_the_app(client: httpx.AsyncClient, staff: Staff) -> None:
    resource = await make_resource(client, staff)
    incident_id, _ = await new_incident(client, staff, random_place())
    operator = staff(["operator"])
    r = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/assignments", json={"resource_id": resource["id"]}, headers=operator
    )
    assignment: dict[str, Any] = r.json()
    url = f"/api/v1/staff/assignments/{assignment['id']}/record"
    start = datetime.fromisoformat(assignment["created_at"])
    at = [_iso(start + timedelta(seconds=s)) for s in (1, 2, 3, 4)]
    r = await client.put(url, json={"times": {"on_scene_at": at[1]}}, headers=operator)
    assert r.json()["detail"] == "time_needs_previous"
    r = await client.put(
        url,
        json={
            "times": {"en_route_at": at[0], "on_scene_at": at[1], "left_scene_at": at[2], "back_at_unit_at": at[3]},
            "crew_count": 3,
            "consumables": {"powder_kg": 12, "extinguishers": 2},
        },
        headers=operator,
    )
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["status"] == "released" and saved["released_at"] == saved["back_at_unit_at"]
    assert saved["at_hospital_at"] is None and saved["crew_count"] == 3
    assert set(saved["time_sources"].values()) == {"room"}
    # A time the room gave changes without a reason; clearing the hospital time is allowed.
    r = await client.put(url, json={"times": {"left_scene_at": None}}, headers=operator)
    assert r.status_code == 200 and r.json()["left_scene_at"] is None
    # Out of the gouvernorat: not found.
    tunis = staff(["operator"], 11)
    assert (await client.put(url, json={"crew_count": 2}, headers=tunis)).status_code in (403, 404)
