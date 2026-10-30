# covers: F-SRV-57, F-STF-13
"""The record of a mission (phase S2, docs/phase-s/design-s2.md): the times from the order to the return to the
unit, given by the team's phone or by the room, always in order, the crew and what the mission used."""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.modules.ops import crew_sms, record, record_checks, record_suggest
from tests.test_crew import Staff, _on_shift, new_incident, write
from tests.test_operations import make_resource, random_place


def _iso(at: datetime) -> str:
    return at.isoformat().replace("+00:00", "Z")


def test_rules() -> None:
    now = datetime.now(UTC)
    t = [now - timedelta(minutes=70 - 10 * i) for i in range(len(record.CHAIN))]
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


def test_warnings() -> None:
    """Times that hold but are not credible are flagged for the room, never refused."""
    now = datetime.now(UTC)
    t0 = now - timedelta(hours=10)
    times: dict[str, datetime | None] = {
        "created_at": t0,
        "en_route_at": t0 + timedelta(minutes=2),
        "on_scene_at": t0 + timedelta(minutes=12),
        "left_scene_at": t0 + timedelta(minutes=50),
        "at_hospital_at": t0 + timedelta(minutes=65),
        "back_at_unit_at": t0 + timedelta(minutes=90),
    }
    common: dict[str, Any] = {"status": "released", "released_at": t0, "crew_count": 4, "now": now}
    assert record_checks.warnings(times, distance_m=9000, **common) == []
    # 30 km in two minutes: faster than the road allows; the two buttons pressed together.
    fast = times | {"on_scene_at": t0 + timedelta(minutes=4)}
    assert record_checks.warnings(fast, distance_m=30_000, **common) == ["travel_too_fast"]
    together = times | {"on_scene_at": t0 + timedelta(minutes=2, seconds=5)}
    assert record_checks.warnings(together, distance_m=None, **common) == ["steps_together"]
    late = times | {"en_route_at": t0 + timedelta(minutes=45), "on_scene_at": t0 + timedelta(minutes=48)}
    assert "turnout_long" in record_checks.warnings(late, distance_m=None, **common)
    assert record_checks.warnings(
        times | {"at_hospital_at": t0 + timedelta(minutes=50, seconds=20)}, distance_m=None, **common
    ) == ["transport_instant"]
    no_return = times | {"back_at_unit_at": None}
    assert record_checks.warnings(no_return, distance_m=None, **common | {"crew_count": None}) == [
        "return_missing",
        "crew_missing",
    ]


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

    # Free on the way back ends the mission and frees the vehicle for another one before it reaches the unit.
    mission = (await leader.post(f"{path}/milestone", write(step="available"))).json()
    assert mission["status"] == "released" and mission["released_at"] == mission["available_at"]
    assert mission["available_at"] >= mission["at_hospital_at"]
    vehicles = (await client.get("/api/v1/staff/resources", params={"limit": 500}, headers=operator)).json()["items"]
    assert next(v for v in vehicles if v["id"] == resource["id"])["status"] == "available"
    # Back at the unit is still recorded afterwards, for the return time.
    mission = (await leader.post(f"{path}/milestone", write(step="back_at_unit"))).json()
    assert mission["back_at_unit_at"] >= mission["available_at"] > mission["en_route_at"]
    assert mission["released_at"] == mission["available_at"]
    assert mission["time_sources"] == {f: "app" for f in record.EDITABLE}

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
    assert kinds.count("mission_step") == 4 and "team_record" in kinds
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
    # One second between the departure and the arrival: saved, and flagged for the room to check.
    assert {"travel_too_fast", "steps_together"} & set(saved["record_warnings"])
    # A time the room gave changes without a reason; clearing the hospital time is allowed.
    r = await client.put(url, json={"times": {"left_scene_at": None}}, headers=operator)
    assert r.status_code == 200 and r.json()["left_scene_at"] is None
    # Out of the gouvernorat: not found.
    tunis = staff(["operator"], 11)
    assert (await client.put(url, json={"crew_count": 2}, headers=tunis)).status_code in (403, 404)


def test_times_read_from_the_writing() -> None:
    """Derja, Arabic and French, Arabic-Indic digits; a quantity or a phone number is not a time."""
    text = """خرجنا 14:02 ووصلنا على عين المكان 14h11
غادرنا المكان 14.40، وصلنا للسبيطار 14:55
رجعنا للوحدة ١٥:٢٠ — 2.50 m3 ماء
départ des lieux 14h41. Arrivée urgences 14h56
الهاتف 71123456 الساعة 14:00"""
    written = record_suggest.Written("pasted", text, datetime(2026, 10, 30, 16, 0, tzinfo=UTC))
    read = [
        (step, at.astimezone(record_suggest.TUNIS).strftime("%H:%M")) for step, at, _ in record_suggest.read(written)
    ]
    assert read == [
        ("en_route_at", "14:02"),
        ("on_scene_at", "14:11"),
        ("left_scene_at", "14:40"),
        ("at_hospital_at", "14:55"),
        ("back_at_unit_at", "15:20"),
        ("left_scene_at", "14:41"),
        ("at_hospital_at", "14:56"),
    ]
    # Written at 00:10 about a return at 23:50: the day before.
    late = record_suggest.Written("room_note", "رجعنا 23:50", datetime(2026, 10, 30, 23, 10, tzinfo=UTC))
    assert record_suggest.read(late)[0][1] == datetime(2026, 10, 30, 23, 50, tzinfo=record_suggest.TUNIS)


async def test_times_suggested_to_the_room(client: httpx.AsyncClient, staff: Staff) -> None:
    resource = await make_resource(client, staff)
    incident_id, _ = await new_incident(client, staff, random_place())
    operator = staff(["operator"])
    r = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/assignments", json={"resource_id": resource["id"]}, headers=operator
    )
    assignment: dict[str, Any] = r.json()
    # The next minute: after the order, within the two minutes a clock may be ahead.
    clock = (datetime.now(record_suggest.TUNIS) + timedelta(minutes=1)).strftime("%H:%M")
    r = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/notes", json={"text": f"اللاسلكي: خرجوا {clock}"}, headers=operator
    )
    assert r.status_code == 201, r.text
    url = f"/api/v1/staff/assignments/{assignment['id']}/record/suggestions"
    r = await client.post(url, json={"text": f"وصلنا على عين المكان {clock}"}, headers=operator)
    assert r.status_code == 200, r.text
    got = {s["step"]: s for s in r.json()}
    assert got["en_route_at"]["source"] == "room_note" and got["en_route_at"]["conflict"] is None
    # The arrival without a departure on the record: suggested, with the rule it would break until the departure is in.
    assert got["on_scene_at"]["source"] == "pasted" and got["on_scene_at"]["conflict"] == "time_needs_previous"
    # Nothing was saved.
    record_url = url.removesuffix("/suggestions")
    saved = (await client.get(f"/api/v1/staff/incidents/{incident_id}", headers=operator)).json()
    assert all(a["en_route_at"] is None for a in saved["assignments"])
    assert record_url.endswith("/record")
    tunis = staff(["operator"], 11)
    assert (await client.post(url, json={}, headers=tunis)).status_code in (403, 404)


async def test_snacr_year_from_the_records(client: httpx.AsyncClient, staff: Staff) -> None:
    """The records of the rooms feed SNACR: a year drawn from them, with the parts of the mission and the crew."""
    resource = await make_resource(client, staff)
    incident_id, _ = await new_incident(client, staff, random_place())
    operator = staff(["operator"])
    r = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/assignments", json={"resource_id": resource["id"]}, headers=operator
    )
    assignment = r.json()
    start = datetime.fromisoformat(assignment["created_at"])
    at = [_iso(start + timedelta(seconds=s)) for s in (1, 2, 3, 4, 5, 6)]
    times = dict(zip(record.EDITABLE, at, strict=True))
    r = await client.put(
        f"/api/v1/staff/assignments/{assignment['id']}/record",
        json={"times": times, "crew_count": 5},
        headers=operator,
    )
    assert r.status_code == 200, r.text

    room = staff(["ops_manager"], gouvernorat=None)
    url = "/api/v1/staff/snacr"
    year = start.year
    r = await client.post(f"{url}/datasets/live", params={"year": year}, headers=room)
    assert r.status_code == 201, r.text
    assert r.json()["dataset"]["source"] == "live" and r.json()["dataset"]["rows"] >= 1
    # Built again on each call; a regional account cannot.
    assert (await client.post(f"{url}/datasets/live", params={"year": year}, headers=room)).status_code == 201
    regional = staff(["ops_manager"], gouvernorat=61)
    assert (await client.post(f"{url}/datasets/live", params={"year": year}, headers=regional)).status_code == 403
    analysis = (
        await client.get(f"{url}/analysis", params={"years": str(year), "gouvernorat": 61}, headers=room)
    ).json()
    mission = analysis["mission"]["fire"]
    assert mission["rows"] >= 1 and mission["crew_mean"] is not None and mission["length_median"] is not None
    assert analysis["datasets"][0]["source"] == "live"
    # Never over the Office's file or a [SIM] year.
    r = await client.post(f"{url}/datasets/simulate", params={"year": 2034, "rows": 100}, headers=room)
    assert r.status_code == 201
    assert (await client.post(f"{url}/datasets/live", params={"year": 2034}, headers=room)).json()[
        "detail"
    ] == "year_has_dataset"
    for y in (year, 2034):
        assert (await client.delete(f"{url}/datasets/{y}", headers=room)).status_code == 204
