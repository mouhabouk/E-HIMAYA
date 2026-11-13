"""Follow-ups of OS3 (docs/phase-os3/design-os3b.md; Yamen 2026-11-13): the repositioning order on the staff app and
its steps (OS3-1), the turnout measured per unit (OS3-2), the cost of maintenance and the monthly report of the fleet
(OS3-3), the neighbouring gouvernorats for the central room (OS3-4)."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import as_system
from app.modules.inventory import report
from tests.test_crew import Leader, write
from tests.test_fleet import BEJA, SFAX, URL, Staff, _clear, _unit, _vehicle

JENDOUBA = 32


async def test_the_crew_gets_the_repositioning_order(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    home = await _unit(client, staff, SFAX, 34.74, 10.76)
    host = await _unit(client, staff, SFAX, 35.03, 11.0)
    vehicle = await _vehicle(client, staff, home, "ambulance")
    leader = Leader(client, staff)
    await leader.register(push_token=f"fcm-{secrets.token_hex(4)}")
    r = await leader.post("/shifts", write(resource_id=vehicle["id"], crew_size=3))
    assert r.status_code == 201, r.text
    room = staff(["operator"], gouvernorat=SFAX, name="منير الكاتب")

    # The room sends the ambulance as reinforcement: an order to the crew, and the phone rings.
    r = await client.post(
        f"{URL}/vehicles/{vehicle['id']}/state",
        json={"state": "reinforcement", "host_unit_id": host["id"], "suggested_gain": 46_000, "note": "تغطية"},
        headers=room,
    )
    assert r.status_code == 200, r.text
    phone = (await leader.get("/repositions")).json()["items"]
    assert len(phone) == 1
    order = phone[0]
    assert order["kind"] == "reinforce" and order["state"] == "sent" and order["pushed"]
    assert order["from_unit_id"] == home["id"] and order["to_unit_id"] == host["id"]
    assert order["gain_population"] == 46_000 and order["to_point"] is not None
    async with as_system(session):
        rung = await session.scalar(
            text(
                "SELECT count(*) FROM notify.outbox WHERE channel = 'staff_push' AND payload->>'type' = 'reposition' "
                "AND payload->'data'->>'order_id' = :id"
            ),
            {"id": order["id"]},
        )
    assert rung == 1

    # The room sees it; nobody opened it after the threshold: flagged.
    listed = (await client.get("/api/v1/staff/coverage/orders", headers=room)).json()
    mine = next(o for o in listed["items"] if o["id"] == order["id"])
    assert mine["overdue"] is False and listed["ack_minutes"] == 2
    async with as_system(session):
        await session.execute(
            text("UPDATE ops.reposition_order SET created_at = now() - interval '5 minutes' WHERE id = :id"),
            {"id": order["id"]},
        )
        await session.commit()
    listed = (await client.get("/api/v1/staff/coverage/orders", params={"open": True}, headers=room)).json()
    assert next(o for o in listed["items"] if o["id"] == order["id"])["overdue"] is True

    # The leader arrives: seeing and leaving are filled too, once.
    r = await leader.post(f"/repositions/{order['id']}/arrived", {})
    assert r.status_code == 200, r.text
    done = r.json()
    assert done["state"] == "arrived" and done["seen_at"] and done["departed_at"] and done["overdue"] is False
    assert done["seen_by_name"] == "سامي الطرابلسي"
    again = (await leader.post(f"/repositions/{order['id']}/seen", {})).json()
    assert again["seen_at"] == done["seen_at"]
    # Another team's leader does not see it; a regional room of another gouvernorat neither.
    stranger = Leader(client, staff)
    await stranger.register()
    other = await _vehicle(client, staff, home, "ambulance")
    assert (await stranger.post("/shifts", write(resource_id=other["id"], crew_size=2))).status_code == 201
    assert (await stranger.post(f"/repositions/{order['id']}/seen", {})).status_code == 404
    beja = (await client.get("/api/v1/staff/coverage/orders", headers=staff(["operator"], gouvernorat=BEJA))).json()
    assert order["id"] not in {o["id"] for o in beja["items"]}

    # Back to its unit: a return order; then a breakdown on the way closes it.
    r = await client.post(f"{URL}/vehicles/{vehicle['id']}/state", json={"state": "ready"}, headers=room)
    assert r.status_code == 200, r.text
    back = next(o for o in (await leader.get("/repositions")).json()["items"] if o["kind"] == "return")
    assert back["from_unit_id"] == host["id"] and back["to_unit_id"] == home["id"] and back["state"] == "sent"
    assert (await leader.post(f"/repositions/{back['id']}/seen", {})).json()["state"] == "seen"
    r = await client.post(
        f"{URL}/vehicles/{vehicle['id']}/state", json={"state": "broken", "fault": "عطب في المكابح"}, headers=room
    )
    assert r.status_code == 200, r.text
    closed = next(o for o in (await leader.get("/repositions")).json()["items"] if o["id"] == back["id"])
    assert closed["state"] == "closed" and closed["close_reason"] == "state"
    assert (await leader.post(f"/repositions/{back['id']}/arrived", {})).json()["detail"] == "order_closed"
    # A room's account cannot step an order; a leader without a shift neither.
    assert (await client.post(f"/api/v1/crew/repositions/{back['id']}/seen", json={}, headers=room)).status_code == 403


async def test_turnout_is_measured_per_unit(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    from tests.test_operations import new_report

    await _clear(session, BEJA)
    quick = await _unit(client, staff, BEJA, 36.812, 9.250)
    slow = await _unit(client, staff, BEJA, 36.692, 9.610)
    a = await _vehicle(client, staff, quick, "ambulance")
    b = await _vehicle(client, staff, slow, "ambulance")
    rep = await new_report(client, {"lat": 36.73, "lon": 9.18})
    r = await client.post(
        f"/api/v1/staff/reports/{rep['id']}/incident",
        json={"action": "new", "override_reason": "حادث منفصل للاختبار"},
        headers=staff(["operator"], gouvernorat=None),
    )
    assert r.status_code == 200, r.text
    incident = r.json()["incident_id"]
    async with as_system(session):
        for vehicle, seconds, n in ((a, 60, 25), (b, 300, 5)):
            for i in range(n):
                await session.execute(
                    text(
                        "INSERT INTO ops.assignment (incident_id, kind, resource_id, status, created_by, created_at, "
                        "en_route_at, released_at) VALUES (:inc, 'resource', :res, 'released', 'test', "
                        "now() - make_interval(days => :d), now() - make_interval(days => :d) + "
                        "make_interval(secs => :s), now() - make_interval(days => :d) + interval '1 hour')"
                    ),
                    {"inc": incident, "res": vehicle["id"], "d": 1 + i, "s": seconds + i},
                )
        await session.commit()
    out = (await client.get("/api/v1/staff/coverage", headers=staff(["operator"], gouvernorat=BEJA))).json()
    assert out["turnout_mode"] == "measured"
    units = {u["id"]: u for u in out["units"]}
    assert units[quick["id"]]["turnout_source"] == "measured" and units[quick["id"]]["turnout_missions"] == 25
    assert 1.0 < units[quick["id"]]["turnout_minutes"] < 1.3 and units[quick["id"]]["turnout_p90_minutes"]
    # Five missions are not enough: the default two minutes.
    assert units[slow["id"]]["turnout_source"] == "default" and units[slow["id"]]["turnout_minutes"] == 2.0
    assert units[slow["id"]]["turnout_missions"] == 5
    async with as_system(session):
        await session.execute(text("DELETE FROM ops.assignment WHERE incident_id = :i"), {"i": incident})
        await session.commit()
    await _clear(session, BEJA)


def test_days_in_states() -> None:
    start, end = report.month_bounds("2026-10")
    assert start == datetime(2026, 9, 30, 23, tzinfo=UTC) and end == datetime(2026, 10, 31, 23, tzinfo=UTC)
    assert report.months_back("2026-02", 3) == ["2025-12", "2026-01", "2026-02"]
    day = timedelta(days=1)
    entered = start - 400 * day
    # Broken for 3 days, then 2 days in the workshop, in a 31-day month: 26 of 31 ready.
    log = [
        report.Change(start + 10 * day, "ready", "broken"),
        report.Change(start + 13 * day, "broken", "maintenance"),
        report.Change(start + 15 * day, "maintenance", "ready"),
    ]
    fleet, down = report.days_in_states(log, "ready", entered, start, end)
    assert round(fleet) == 31 and round(down) == 5
    assert report.readiness(fleet, down) == 83.9
    # In the workshop since before the month and never out: down all month; decommissioned midway: out of the fleet.
    assert report.days_in_states(
        [report.Change(start - day, "ready", "maintenance")], "maintenance", entered, start, end
    ) == (
        31.0,
        31.0,
    )
    fleet, down = report.days_in_states(
        [report.Change(start + 6 * day, "ready", "retired")], "retired", entered, start, end
    )
    assert (round(fleet), down) == (6, 0.0)
    # Entered the register on the 21st.
    assert round(report.days_in_states([], "ready", start + 20 * day, start, end)[0]) == 11
    assert report.readiness(0.0, 0.0) is None


async def test_maintenance_cost_and_monthly_report(client: httpx.AsyncClient, staff: Staff) -> None:
    unit = await _unit(client, staff, SFAX, 34.74, 10.76)
    vehicle = await _vehicle(client, staff, unit, "fire_engine")
    workshop = staff(["maintenance_officer"], gouvernorat=SFAX, name="هالة الصيانة")
    r = await client.post(
        f"{URL}/vehicles/{vehicle['id']}/maintenance",
        json={"workshop": "ورشة صفاقس", "reason": "مضخة"},
        headers=workshop,
    )
    assert r.status_code == 200, r.text
    r = await client.post(
        f"{URL}/vehicles/{vehicle['id']}/maintenance/end",
        json={"odometer_km": 12_500, "maint_kind": "repair", "cost_parts": "1240.500", "cost_labour": 380},
        headers=workshop,
    )
    assert r.status_code == 200, r.text
    log = (await client.get(f"{URL}/vehicle-events", params={"vehicle_id": vehicle["id"]}, headers=workshop)).json()
    stay = next(e for e in log["items"] if e["kind"] == "maintenance_end")
    assert Decimal(stay["cost_parts"]) == Decimal("1240.5") and stay["maint_kind"] == "repair"
    assert stay["cost_by_name"] == "هالة الصيانة" and stay["cost_at"]
    # The invoice of the outside workshop arrives later.
    r = await client.post(
        f"{URL}/vehicle-events/{stay['id']}/cost",
        json={
            **{k: stay[k] for k in ("maint_kind", "cost_parts", "cost_labour")},
            "cost_external": "900",
            "invoice_ref": "ف-2026-1187",
        },
        headers=workshop,
    )
    assert r.status_code == 200, r.text
    assert Decimal(r.json()["cost_external"]) == 900 and r.json()["invoice_ref"] == "ف-2026-1187"
    start = next(e for e in log["items"] if e["kind"] == "maintenance_start")
    assert (
        await client.post(f"{URL}/vehicle-events/{start['id']}/cost", json={"cost_parts": 1}, headers=workshop)
    ).status_code == 409
    assert (await client.post(f"{URL}/vehicle-events/{stay['id']}/cost", json={}, headers=workshop)).status_code == 422
    room = staff(["operator"], gouvernorat=SFAX)
    assert (
        await client.post(f"{URL}/vehicle-events/{stay['id']}/cost", json={"cost_parts": 1}, headers=room)
    ).status_code == 403
    assert (
        await client.post(
            f"{URL}/vehicle-events/{stay['id']}/cost",
            json={"cost_parts": 1},
            headers=staff(["maintenance_officer"], gouvernorat=BEJA),
        )
    ).status_code == 404  # another gouvernorat's log is out of sight

    # The monthly report: this month's costs and entries in Sfax.
    out = await client.get(f"{URL}/fleet-report", headers=room)
    assert out.status_code == 200, out.text
    body = out.json()
    assert len(body["months"]) == 6 and body["months"][-1] == body["month"]
    sfax = next(row for row in body["rows"] if row["gouvernorat_code"] == SFAX)
    assert [row["gouvernorat_code"] for row in body["rows"]] == [SFAX] and body["total"] is None
    assert Decimal(sfax["cost_total"]) >= Decimal("2520.5") and sfax["workshop_entries"] >= 1
    assert sfax["vehicles"] >= 1 and sfax["readiness_pct"] is not None and sfax["point"] is not None
    assert len(sfax["series"]) == 6 and body["red_below"] == 80 and body["amber_below"] == 85
    assert any(c["resource_id"] == vehicle["id"] for c in body["costly"]) or len(body["costly"]) == 5
    national = (
        await client.get(f"{URL}/fleet-report", headers=staff(["maintenance_officer"], gouvernorat=None))
    ).json()
    assert national["total"] is None or national["total"]["gouvernorat_code"] == 0
    assert (await client.get(f"{URL}/fleet-report", params={"gouvernorat": BEJA}, headers=room)).status_code == 403
    assert (await client.get(f"{URL}/fleet-report", params={"month": "2099-01"}, headers=room)).status_code == 422


async def test_neighbouring_units_for_the_central_room(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    await _clear(session, BEJA)
    await _clear(session, JENDOUBA)
    beja = await _unit(client, staff, BEJA, 36.692, 9.610)  # Medjez El Bab, no ambulance
    bou_salem = await _unit(client, staff, JENDOUBA, 36.780, 8.950)  # Jendouba, 7 km from Amdoun (Béja)
    ambulance = await _vehicle(client, staff, bou_salem, "ambulance")
    room = staff(["operator"], gouvernorat=BEJA)
    assert (await client.get("/api/v1/staff/coverage", params={"neighbours": True}, headers=room)).json()[
        "detail"
    ] == "national_only"
    central = staff(["operator"], gouvernorat=None)
    alone = (await client.get("/api/v1/staff/coverage", params={"gouvernorat": BEJA}, headers=central)).json()
    assert not alone["neighbours"] and bou_salem["id"] not in {u["id"] for u in alone["units"]}
    out = (
        await client.get("/api/v1/staff/coverage", params={"gouvernorat": BEJA, "neighbours": True}, headers=central)
    ).json()
    assert out["neighbours"] and out["neighbour_m"] == 40_000
    units = {u["id"]: u for u in out["units"]}
    assert units[bou_salem["id"]]["neighbour"] and units[bou_salem["id"]]["gouvernorat_code"] == JENDOUBA
    assert not units[beja["id"]]["neighbour"]
    medical = next(f for f in out["families"] if f["family"] == "medical")
    before = next(f for f in alone["families"] if f["family"] == "medical")
    # The neighbour's ambulance counts on top of Béja's own (other tests may have left some there).
    assert medical["ready"] == before["ready"] + 1
    assert medical["covered_pct"] > medical["own_pct"] == before["covered_pct"]
    amdoun = next(d for d in out["delegations"] if d["id"] == 3101)["families"]["medical"]
    assert amdoun["covered"] and amdoun["neighbour"] and amdoun["unit_name"] == bou_salem["name_ar"]
    # A suggestion may bring the neighbour's ambulance to a unit of Béja; the central room sends it.
    move = next((s for s in out["suggestions"] if s["family"] == "medical"), None)
    if move is not None:
        assert move["from_gouvernorat_code"] == JENDOUBA and move["to_unit_id"] == beja["id"]
        r = await client.post(
            f"{URL}/vehicles/{ambulance['id']}/state",
            json={"state": "reinforcement", "host_unit_id": beja["id"], "suggested_gain": move["gain_population"]},
            headers=central,
        )
        assert r.status_code == 200, r.text
        orders = (await client.get("/api/v1/staff/coverage/orders", headers=room)).json()["items"]
        assert any(o["resource_id"] == ambulance["id"] and o["host_gouvernorat_code"] == BEJA for o in orders)
    await _clear(session, BEJA)
    await _clear(session, JENDOUBA)
    assert uuid.UUID(ambulance["id"])
