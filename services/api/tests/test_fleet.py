"""OS3 (docs/phase-os3/design-os3.md): one register, three hands. The maintenance department keeps the vehicle cards,
the workshop and the decommissioning; the operations rooms set the operational state (at the unit, reinforcement,
broken); the personnel department the staff. The live coverage of a gouvernorat, its alerts and its repositioning
suggestions; the permission profiles the system administrator grants (read only, or read and write)."""

import secrets
import uuid
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import as_system
from app.modules.inventory import domain

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/inventory"
SFAX, BEJA = 61, 31


async def _unit(client: httpx.AsyncClient, staff: Staff, code: int, lat: float, lon: float) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/staff/units",
        json={
            "name_ar": f"وحدة {secrets.token_hex(3)}",
            "name_fr": f"Unité {secrets.token_hex(3)}",
            "kind": "unit",
            "gouvernorat_code": code,
            "location": {"lat": lat, "lon": lon},
        },
        headers=staff(["ops_manager"], gouvernorat=code),
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def _plate() -> str:
    return f"{secrets.randbelow(900) + 100} تونس {secrets.randbelow(9000) + 1000}"


async def _vehicle(
    client: httpx.AsyncClient, staff: Staff, unit: dict[str, Any], category: str = "fire_engine", **extra: Any
) -> dict[str, Any]:
    r = await client.post(
        f"{URL}/vehicles",
        json={
            "unit_id": unit["id"],
            "category_key": category,
            "label": f"{category[:3]}-{secrets.token_hex(3)}",
            "code": f"ADM-{secrets.token_hex(4)}",
            "plate": _plate(),
            "odometer_km": 12_000,
            "acquired_on": "2019-05-02",
            **extra,
        },
        headers=staff(["maintenance_officer"], gouvernorat=unit["gouvernorat_code"]),
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def test_plate_numbers() -> None:
    assert domain.normal_plate(" 123  تونس 4567 ") == "123 تونس 4567"
    assert domain.normal_plate("12تونس 7") == "12 تونس 7"
    assert domain.normal_plate("") is None
    for wrong in ("TU 123", "1234 تونس 1", "123 تونس 12345"):
        try:
            domain.normal_plate(wrong)
        except ValueError:
            continue
        raise AssertionError(wrong)
    assert domain.vehicle_state("available", None, True) == "reinforcement"
    assert domain.vehicle_state("out_of_service", "retired") == "retired"


async def test_the_card_belongs_to_the_maintenance_department(client: httpx.AsyncClient, staff: Staff) -> None:
    unit = await _unit(client, staff, SFAX, 34.74, 10.76)
    created = await _vehicle(client, staff, unit)
    assert created["state"] == "ready" and created["odometer_km"] == 12_000
    assert created["acquired_on"] == "2019-05-02" and " تونس " in created["plate"]
    body = {
        "unit_id": unit["id"],
        "category_key": "fire_engine",
        "label": f"x-{secrets.token_hex(3)}",
        "plate": created["plate"],
    }
    room = staff(["ops_manager", "operator"], gouvernorat=SFAX)
    maintenance = staff(["maintenance_officer"], gouvernorat=SFAX)
    # The rooms no longer write the card, here or through the older resources route.
    assert (await client.post(f"{URL}/vehicles", json=body, headers=room)).status_code == 403
    legacy = {"unit_id": unit["id"], "kind": "fire_engine", "label": "x"}
    assert (await client.post("/api/v1/staff/resources", json=legacy, headers=room)).status_code == 403
    # One plate, one administrative number in the country; a plate is a Tunisian plate; the odometer only goes up.
    assert (await client.post(f"{URL}/vehicles", json=body, headers=maintenance)).json()["detail"] == "plate_taken"
    body["plate"] = "AB-12"
    assert (await client.post(f"{URL}/vehicles", json=body, headers=maintenance)).json()["detail"] == "plate_invalid"
    body["plate"], body["code"] = None, created["code"]
    assert (await client.post(f"{URL}/vehicles", json=body, headers=maintenance)).json()["detail"] == "code_taken"
    update = {**created, "unit_id": unit["id"], "odometer_km": 11_000, "reason": "تحيين العداد"}
    r = await client.patch(f"{URL}/vehicles/{created['id']}", json=update, headers=maintenance)
    assert r.json()["detail"] == "odometer_decrease"
    update["odometer_km"], update["state"] = 15_500, "broken"
    r = await client.patch(f"{URL}/vehicles/{created['id']}", json=update, headers=maintenance)
    assert r.status_code == 200, r.text
    # The card's state is not changed by an update: the rooms and the workshop actions do that.
    assert r.json()["odometer_km"] == 15_500 and r.json()["state"] == "ready"
    # Another gouvernorat's maintenance department does not see it.
    other = staff(["maintenance_officer"], gouvernorat=BEJA)
    assert (await client.patch(f"{URL}/vehicles/{created['id']}", json=update, headers=other)).status_code in (403, 404)
    listing = (await client.get(f"{URL}/vehicles", params={"unit_id": unit["id"]}, headers=room)).json()
    assert listing["can_edit"] is False and listing["can_set_state"] is True and listing["can_maintain"] is False
    listing = (await client.get(f"{URL}/vehicles", params={"unit_id": unit["id"]}, headers=maintenance)).json()
    assert listing["can_edit"] is True and listing["can_set_state"] is False


async def test_the_rooms_set_the_state_and_the_workshop_the_rest(client: httpx.AsyncClient, staff: Staff) -> None:
    home = await _unit(client, staff, SFAX, 34.74, 10.76)
    host = await _unit(client, staff, SFAX, 34.43, 10.73)
    vehicle = await _vehicle(client, staff, home, "ambulance")
    vid = vehicle["id"]
    room = staff(["operator"], gouvernorat=SFAX)
    maintenance = staff(["maintenance_officer"], gouvernorat=SFAX)
    state = f"{URL}/vehicles/{vid}/state"
    # The maintenance department does not set the operational state; the room does.
    assert (await client.post(state, json={"state": "broken", "fault": "عطب"}, headers=maintenance)).status_code == 403
    assert (await client.post(state, json={"state": "reinforcement"}, headers=room)).status_code == 422
    r = await client.post(
        state, json={"state": "reinforcement", "host_unit_id": host["id"], "suggested_gain": 4200}, headers=room
    )
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "reinforcement" and r.json()["stationed_unit_id"] == host["id"]
    # Another gouvernorat's room may not send it anywhere.
    beja = await _unit(client, staff, BEJA, 36.81, 9.25)
    central = staff(["operator"], gouvernorat=None)
    regional = await client.post(state, json={"state": "reinforcement", "host_unit_id": beja["id"]}, headers=room)
    assert regional.status_code in (403, 404)
    # The central room sends it between gouvernorats; Béja's room then sees it and proposes it.
    r = await client.post(state, json={"state": "reinforcement", "host_unit_id": beja["id"]}, headers=central)
    assert r.status_code == 200, r.text
    beja_room = staff(["operator"], gouvernorat=BEJA)
    seen = (await client.get(f"{URL}/vehicles", params={"unit_id": beja["id"]}, headers=beja_room)).json()["items"]
    assert [v["id"] for v in seen] == [vid] and seen[0]["stationed_unit_name"] == beja["name_ar"]
    r = await client.post(state, json={"state": "broken", "fault": "  "}, headers=beja_room)
    assert r.json()["detail"] == "fault_required"
    r = await client.post(state, json={"state": "broken", "fault": "تسرب في المكابح"}, headers=beja_room)
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "broken" and r.json()["stationed_unit_id"] is None
    # The workshop: the room can no longer touch it until the department takes it back.
    workshop = {"workshop": "ورشة صفاقس", "reason": "تغيير المكابح", "until": str(date.today() + timedelta(days=5))}
    r = await client.post(f"{URL}/vehicles/{vid}/maintenance", json=workshop, headers=room)
    assert r.status_code == 403
    r = await client.post(f"{URL}/vehicles/{vid}/maintenance", json=workshop, headers=maintenance)
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "maintenance" and r.json()["workshop"] == "ورشة صفاقس"
    assert (await client.post(state, json={"state": "ready"}, headers=room)).json()["detail"] == "vehicle_maintenance"
    end = await client.post(f"{URL}/vehicles/{vid}/maintenance/end", json={"odometer_km": 16_000}, headers=maintenance)
    assert end.status_code == 200, end.text
    assert end.json()["state"] == "ready" and end.json()["fault"] is None and end.json()["odometer_km"] == 16_000
    retire = {"decision": "قرار 2026/114", "retired_on": str(date.today()), "reason": "انتهاء العمر الافتراضي"}
    r = await client.post(f"{URL}/vehicles/{vid}/retire", json=retire, headers=maintenance)
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "retired" and r.json()["retire_decision"] == "قرار 2026/114"
    assert (await client.post(state, json={"state": "ready"}, headers=room)).json()["detail"] == "vehicle_retired"
    again = await client.post(f"{URL}/vehicles/{vid}/retire", json=retire, headers=maintenance)
    assert again.json()["detail"] == "vehicle_retired"
    events = (await client.get(f"{URL}/vehicle-events", params={"vehicle_id": vid}, headers=room)).json()["items"]
    assert [e["kind"] for e in events][::-1] == [
        "reinforce",
        "reinforce",
        "reinforce_end",
        "maintenance_start",
        "maintenance_end",
        "retire",
    ]
    assert events[-1]["details"]["suggested_gain"] == 4200


async def test_a_reinforcement_is_proposed_from_its_host(client: httpx.AsyncClient, staff: Staff) -> None:
    from tests.conftest import SFAX as SFAX_POINT
    from tests.test_decision import new_incident

    home = await _unit(client, staff, SFAX, 34.43, 10.73)
    host = await _unit(client, staff, SFAX, 34.741, 10.761)
    vehicle = await _vehicle(client, staff, home, "rescue_vehicle")
    room = staff(["operator"], gouvernorat=SFAX)
    r = await client.post(
        f"{URL}/vehicles/{vehicle['id']}/state",
        json={"state": "reinforcement", "host_unit_id": host["id"]},
        headers=room,
    )
    assert r.status_code == 200, r.text
    incident = await new_incident(client, staff, SFAX_POINT, SFAX, category="traffic_accident")
    rec = (await client.get(f"/api/v1/staff/incidents/{incident}/recommendations", headers=room)).json()
    candidates = [c for item in rec["items"] for c in item.get("inputs", {}).get("candidates", [])]
    mine = next(c for c in candidates if c["resource_id"] == vehicle["id"])
    assert mine["unit"] == host["name_ar"] and mine["distance_m"] < 5_000


async def _clear(session: AsyncSession, code: int) -> None:
    async with as_system(session):
        await session.execute(
            text(
                "UPDATE ops.resource r SET stationed_unit_id = NULL, stationed_since = NULL FROM ops.unit u "
                "WHERE u.id = r.stationed_unit_id AND u.gouvernorat_code = :g"
            ),
            {"g": code},
        )
        await session.execute(
            text(
                "DELETE FROM ops.resource r USING ops.unit u WHERE u.id = r.unit_id AND u.gouvernorat_code = :g "
                "AND NOT EXISTS (SELECT 1 FROM ops.assignment a WHERE a.resource_id = r.id)"
            ),
            {"g": code},
        )
        await session.execute(
            text(
                "DELETE FROM ops.unit u WHERE u.gouvernorat_code = :g "
                "AND NOT EXISTS (SELECT 1 FROM ops.resource r WHERE r.unit_id = u.id OR r.stationed_unit_id = u.id)"
            ),
            {"g": code},
        )
        await session.commit()


async def test_live_coverage_alerts_and_repositioning(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    await _clear(session, BEJA)
    north = await _unit(client, staff, BEJA, 36.812, 9.250)  # Béja Nord
    east = await _unit(client, staff, BEJA, 36.692, 9.610)  # Medjez El Bab
    pair = [(await _vehicle(client, staff, north, "ambulance"))["id"] for _ in range(2)]
    room = staff(["operator"], gouvernorat=BEJA)
    out = (await client.get("/api/v1/staff/coverage", headers=room)).json()
    assert out["gouvernorat_code"] == BEJA and len(out["delegations"]) == 9
    medical = next(f for f in out["families"] if f["family"] == "medical")
    assert medical["ready"] == 2 and 0 < medical["covered_pct"] < 100
    assert not [a for a in out["alerts"] if a["family"] == "medical"]
    medjez = next(d for d in out["delegations"] if d["id"] == 3105)
    assert medjez["families"]["medical"]["covered"] is False
    # Both ambulances wait in Béja Nord: moving one to Medjez El Bab covers more people.
    move = next(s for s in out["suggestions"] if s["family"] == "medical")
    assert move["to_unit_id"] == east["id"] and move["gain_population"] > 0 and move["newly_covered"]
    # The room accepts the suggestion: one ambulance waits in Medjez El Bab as reinforcement.
    r = await client.post(
        f"{URL}/vehicles/{move['vehicle_id']}/state",
        json={"state": "reinforcement", "host_unit_id": east["id"], "suggested_gain": move["gain_population"]},
        headers=room,
    )
    assert r.status_code == 200, r.text
    # The other goes to the workshop: what the plan covers and no ready ambulance covers is an alert.
    other = next(v for v in pair if v != move["vehicle_id"])
    r = await client.post(
        f"{URL}/vehicles/{other}/maintenance",
        json={"workshop": "ورشة باجة", "reason": "مراجعة دورية"},
        headers=staff(["maintenance_officer"], gouvernorat=BEJA),
    )
    assert r.status_code == 200, r.text
    out = (await client.get("/api/v1/staff/coverage", headers=room)).json()
    alerts = [a for a in out["alerts"] if a["family"] == "medical"]
    assert alerts and all(a["population"] > 0 for a in alerts)
    # The central room names the gouvernorat; a regional room only its own.
    assert (
        await client.get("/api/v1/staff/coverage", headers=staff(["operator"], gouvernorat=None))
    ).status_code == 422
    assert (await client.get("/api/v1/staff/coverage", params={"gouvernorat": SFAX}, headers=room)).status_code == 403
    national = await client.get(
        "/api/v1/staff/coverage", params={"gouvernorat": BEJA}, headers=staff(["operator"], gouvernorat=None)
    )
    assert national.status_code == 200
    await _clear(session, BEJA)


async def test_profiles_read_only_and_read_write(client: httpx.AsyncClient, staff: Staff) -> None:
    admin = staff(["sysadmin"], gouvernorat=None)
    sub = f"inspector-{uuid.uuid4()}"
    inspector = staff(["org_auditor"], gouvernorat=None, sub=sub)
    unit = await _unit(client, staff, SFAX, 34.74, 10.76)
    vehicle = await _vehicle(client, staff, unit)
    assert (await client.get(f"{URL}/vehicles", headers=inspector)).status_code == 403
    profiles = (await client.get("/api/v1/staff/features/profiles", headers=admin)).json()
    fleet = next(p for p in profiles if p["builtin"] and p["items"][0]["page"] == "fleet")
    assert fleet["items"][0]["mode"] == "read" and "fleet.edit" not in fleet["items"][0]["features"]
    grant = {"target_kind": "user", "target": sub, "target_name": "المتفقد العام", "reason": "اطلاع التفقدية"}
    r = await client.post(f"/api/v1/staff/features/profiles/{fleet['id']}/assign", json=grant, headers=admin)
    assert r.status_code == 201, r.text
    read_only = r.json()
    assert "fleet" in read_only["features"] and "fleet.edit" not in read_only["features"]
    assert (await client.get(f"{URL}/vehicles", headers=inspector)).status_code == 200
    card = {"unit_id": unit["id"], "category_key": "fire_engine", "label": f"z-{secrets.token_hex(3)}"}
    assert (await client.post(f"{URL}/vehicles", json=card, headers=inspector)).status_code == 403
    # A profile of his own: the fleet read and write.
    body = {"name": f"تفقد {secrets.token_hex(3)}", "items": [{"page": "fleet", "mode": "write"}]}
    r = await client.post("/api/v1/staff/features/profiles", json=body, headers=admin)
    assert r.status_code == 201, r.text
    write = r.json()
    assert "fleet.edit" in write["items"][0]["features"]
    r = await client.post(f"/api/v1/staff/features/profiles/{write['id']}/assign", json=grant, headers=admin)
    assert r.status_code == 201, r.text
    assert (await client.post(f"{URL}/vehicles", json=card, headers=inspector)).status_code == 201
    # In use: not deleted; revoked: the reads and writes close again.
    assert (await client.delete(f"/api/v1/staff/features/profiles/{write['id']}", headers=admin)).status_code == 409
    for assignment in (read_only["id"], r.json()["id"]):
        revoke = await client.post(
            f"/api/v1/staff/features/profile-assignments/{assignment}/revoke",
            json={"reason": "انتهاء المهمة"},
            headers=admin,
        )
        assert revoke.status_code == 204
    assert (await client.get(f"{URL}/vehicles", headers=inspector)).status_code == 403
    assert (await client.delete(f"/api/v1/staff/features/profiles/{write['id']}", headers=admin)).status_code == 204
    # The ceiling holds: personal data never reaches a governor; a profile that grants nothing is refused.
    personnel = next(p for p in profiles if p["builtin"] and p["items"][0]["page"] == "personnel")
    governor = {"target_kind": "role", "target": "governor", "reason": "تجربة السقف"}
    r = await client.post(f"/api/v1/staff/features/profiles/{personnel['id']}/assign", json=governor, headers=admin)
    assert r.status_code == 422 and r.json()["detail"] == "profile_grants_nothing"
    # Only the national system administrator manages profiles.
    assert (await client.get("/api/v1/staff/features/profiles", headers=staff(["operator"]))).status_code == 403
    assert vehicle["id"]
