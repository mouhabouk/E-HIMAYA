"""The field layers of the interactive map (Yamen 2026-11-13, docs/phase-ml/design-ml.md §7): the places of the
periodic inspections for the inspector general, the vehicles' last positions and the PAR teams for the inspector
general, the head of the room and the field commander only; the system administrator reveals or hides each one."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx

from app.modules.features import registry
from tests.test_crew import Staff, write
from tests.test_crew_field import _mission
from tests.test_features import revoke, rule

URL = "/api/v1/staff/field-map"
SFAX = 61


def _iso(at: datetime) -> str:
    return at.astimezone(UTC).isoformat().replace("+00:00", "Z")


def test_the_catalogue_names_the_three_layers() -> None:
    import app.main  # noqa: F401 - installs the registry

    reg = registry.get()
    roles = {key: {r.value for r in reg.features[key].roles} for key in ("map.inspections", "map.vehicles", "map.par")}
    assert roles == {
        "map.inspections": {"inspector_general"},
        "map.vehicles": {"inspector_general", "ops_manager", "field_commander"},
        "map.par": {"inspector_general", "ops_manager", "field_commander"},
    }
    for key, path in (("map.inspections", "/inspections"), ("map.vehicles", "/vehicles"), ("map.par", "/par")):
        chain = reg.match("GET", f"/field-map{path}")
        assert [f.key for f in chain][:2] == [key, "map"]


async def test_who_reads_each_layer(client: httpx.AsyncClient, staff: Staff) -> None:
    general = staff(["inspector_general"], gouvernorat=None)
    head = staff(["ops_manager"], SFAX)
    commander = staff(["field_commander"], SFAX)
    operator = staff(["operator"], SFAX)
    committee = staff(["local_committee"], SFAX)
    for path in ("/vehicles", "/par"):
        for headers in (general, head, commander):
            r = await client.get(f"{URL}{path}", headers=headers)
            assert r.status_code == 200, (path, r.text)
        for headers in (operator, committee):
            assert (await client.get(f"{URL}{path}", headers=headers)).status_code == 403, path
    r = await client.get(f"{URL}/inspections", headers=general)
    assert r.status_code == 200, r.text
    assert {"items", "unplaced"} <= set(r.json())
    for headers in (head, commander, operator):
        assert (await client.get(f"{URL}/inspections", headers=headers)).status_code == 403


async def test_the_vehicle_and_its_team_where_the_phone_last_was(client: httpx.AsyncClient, staff: Staff) -> None:
    leader, path, incident_id, place = await _mission(client, staff, on_scene=False)
    assert (await leader.post(f"{path}/status", write(status="en_route"))).status_code == 200
    at = datetime.now(UTC) - timedelta(seconds=5)
    lat, lon = round(place["lat"] + 0.004, 6), round(place["lon"], 6)
    fix = {"lat": lat, "lon": lon, "accuracy_m": 8.0, "at": _iso(at)}
    assert (await leader.post(f"{path}/positions", {"points": [fix]})).json() == {"accepted": 1}
    r = await leader.post(f"{path}/par/enter", {"zone": "hot"})
    assert r.status_code == 200, r.text
    team_id = r.json()["team"]["id"]
    crew = [m["key"] for m in r.json()["team"]["members"]]

    head = staff(["ops_manager"], SFAX)
    vehicles = (await client.get(f"{URL}/vehicles", headers=head)).json()
    mine = next(v for v in vehicles["items"] if v["incident_id"] == incident_id)
    assert mine["location"] == {"lat": lat, "lon": lon}
    assert datetime.fromisoformat(mine["at"]) == at
    teams = (await client.get(f"{URL}/par", headers=head)).json()["items"]
    team = next(t for t in teams if t["id"] == team_id)
    assert team["location_source"] == "crew" and team["location"] == {"lat": lat, "lon": lon}
    assert team["status"] == "ok" and team["zone"] == "hot" and team["members"] == len(crew)

    # Another gouvernorat's room does not see them.
    tunis = staff(["ops_manager"], 11)
    assert all(v["id"] != mine["id"] for v in (await client.get(f"{URL}/vehicles", headers=tunis)).json()["items"])
    assert all(t["id"] != team_id for t in (await client.get(f"{URL}/par", headers=tunis)).json()["items"])

    # The units and resources layer draws the vehicle where it is for the head of the room, at its unit for an
    # operator (Yamen 2026-11-13: «لرئيس القاعة والقائد الميداني دون سواهما»).
    def drawn(geo: dict[str, object]) -> list[float]:
        features = geo["features"]
        assert isinstance(features, list)
        return next(f["geometry"]["coordinates"] for f in features if f["properties"].get("id") == mine["id"])

    seen_by_head = drawn((await client.get("/api/v1/staff/resources/map", headers=head)).json())
    assert seen_by_head == [lon, lat]
    seen_by_operator = drawn(
        (await client.get("/api/v1/staff/resources/map", headers=staff(["operator"], SFAX))).json()
    )
    assert seen_by_operator != [lon, lat]

    # Out of the zone, the team leaves the layer.
    r = await leader.post(f"{path}/par/exit", {"members": crew})
    assert r.status_code == 200, r.text
    teams = (await client.get(f"{URL}/par", headers=head)).json()["items"]
    assert all(t["id"] != team_id for t in teams)


async def test_the_administrator_hides_and_reveals(client: httpx.AsyncClient, staff: Staff) -> None:
    sub = f"fm-{uuid.uuid4()}"
    commander = staff(["field_commander"], SFAX, sub=sub)
    operator_sub = f"fm-{uuid.uuid4()}"
    operator = staff(["operator"], SFAX, sub=operator_sub)
    assert (await client.get(f"{URL}/vehicles", headers=commander)).status_code == 200

    # Hidden from this commander: refused, and the layer is listed as hidden for the dashboard.
    r = await rule(client, staff, feature_key="map.vehicles", effect="hide", target_kind="user", target=sub)
    assert r.status_code == 201, r.text
    hidden = r.json()
    r = await client.get(f"{URL}/vehicles", headers=commander)
    assert (r.status_code, r.json()["detail"]) == (403, "feature_hidden")
    assert "map.vehicles" in (await client.get("/api/v1/staff/features/mine", headers=commander)).json()["hidden"]
    assert (await client.get(f"{URL}/par", headers=commander)).status_code == 200

    # Revealed to an operator: the layer opens for that account only.
    r = await rule(client, staff, feature_key="map.par", effect="grant", target_kind="user", target=operator_sub)
    assert r.status_code == 201, r.text
    granted = r.json()
    assert (await client.get(f"{URL}/par", headers=operator)).status_code == 200
    assert (await client.get(f"{URL}/par", headers=staff(["operator"], SFAX))).status_code == 403

    await revoke(client, staff, hidden["id"])
    await revoke(client, staff, granted["id"])
    assert (await client.get(f"{URL}/vehicles", headers=commander)).status_code == 200
    assert (await client.get(f"{URL}/par", headers=operator)).status_code == 403
