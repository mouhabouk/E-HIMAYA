"""Address warnings, OS8 (docs/phase-os8/design-os8.md): the register, the warnings of an incident, the team, the
citizen's consent and the reading of a personal mark's owner."""

import secrets
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

import httpx

from app.modules.address_warnings import service
from tests.test_crew import _on_shift
from tests.test_operations import new_incident

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/address-warnings"
ME = "/api/v1/me/address-warnings"
SFAX = 61
M_PER_DEG_LAT = 111_000


def _place() -> dict[str, float]:
    # Inside Sfax gouvernorat, in an area of its own: the marks of these tests must not meet other tests' incidents.
    return {"lat": 34.95 + secrets.randbelow(1000) / 10_000, "lon": 10.40 + secrets.randbelow(1000) / 10_000}


def _north(place: dict[str, float], metres: float) -> dict[str, float]:
    return {"lat": place["lat"] + metres / M_PER_DEG_LAT, "lon": place["lon"]}


async def _mark(client: httpx.AsyncClient, headers: dict[str, str], **body: Any) -> dict[str, Any]:
    r = await client.post(f"{URL}/markers", json={"address": "نهج التجربة عدد 1", **body}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


# ---------------------------------------------------------------- pure rules


def test_hours_and_months() -> None:
    assert service.in_hours(None, None, 0)
    assert service.in_hours(450, 1050, 600) and not service.in_hours(450, 1050, 1300)
    # Across midnight (22:00 to 06:00).
    assert (
        service.in_hours(1320, 360, 1400) and service.in_hours(1320, 360, 60) and not service.in_hours(1320, 360, 720)
    )
    assert service.add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert service.add_months(date(2026, 11, 12), 12) == date(2027, 11, 12)
    assert service.minutes_now(datetime(2026, 11, 12, 20, 40, tzinfo=UTC)) == 21 * 60 + 40


# ---------------------------------------------------------------- categories and register


async def test_categories_are_seeded_and_set_by_the_central_room(client: httpx.AsyncClient, staff: Staff) -> None:
    cats = (await client.get(f"{URL}/categories", headers=staff(["operator"], SFAX))).json()
    keys = [c["key"] for c in cats]
    assert keys[:3] == ["gas", "chem", "fuel"] and {"mob", "oxy", "deaf"} <= set(keys)
    gas = next(c for c in cats if c["key"] == "gas")
    assert gas["radius_m"] == 150 and "fire" in gas["critical_with"] and not gas["personal"]
    body = {"radius_m": 150, "review_months": 12, "team": True, "critical_with": ["fire", "chemical_leak"]}
    # A regional manager may not change national settings; an operator may not either.
    assert (
        await client.put(f"{URL}/categories/gas", json=body, headers=staff(["ops_manager"], SFAX))
    ).status_code == 403
    assert (await client.put(f"{URL}/categories/gas", json=body, headers=staff(["operator"], None))).status_code == 403
    r = await client.put(f"{URL}/categories/gas", json=body, headers=staff(["ops_manager"], None, name="رئيس القاعة"))
    assert r.status_code == 200, r.text
    assert r.json()["updated_by_name"] == "رئيس القاعة"
    bad = {**body, "critical_with": ["earthquake"]}
    assert (
        await client.put(f"{URL}/categories/gas", json=bad, headers=staff(["ops_manager"], None))
    ).status_code == 422


async def test_the_room_keeps_its_register(client: httpx.AsyncClient, staff: Staff) -> None:
    room = staff(["operator"], SFAX, name="عون القاعة")
    place = _place()
    m = await _mark(client, room, category="dog", location=place, description="كلبا حراسة طليقان", source="report")
    assert m["status"] == "active" and m["gouvernorat_code"] == SFAX and not m["review_due"]
    assert m["created_by_name"] == "عون القاعة"
    # A personal category is never added by a room, and an unknown one is refused.
    for category in ("mob", "nope"):
        body = {"category": category, "location": place, "address": "نهج", "description": "وصف"}
        assert (await client.post(f"{URL}/markers", json=body, headers=room)).status_code == 422
    # A regional room adds nothing outside its gouvernorat, and does not read another's register.
    tunis = {"lat": 36.8065, "lon": 10.1815}
    body = {"category": "gas", "location": tunis, "address": "نهج", "description": "قوارير"}
    r = await client.post(f"{URL}/markers", json=body, headers=room)
    assert r.status_code == 403 and r.json()["detail"] == "outside_gouvernorat"
    other = (await client.get(f"{URL}/markers", headers=staff(["operator"], 11))).json()
    assert all(x["id"] != m["id"] for x in other["items"])
    page = (await client.get(f"{URL}/markers", headers=room)).json()
    assert any(x["id"] == m["id"] for x in page["items"]) and page["counts"]["active"] >= 1
    # Edit, then archive with a reason (a reason is required).
    r = await client.patch(f"{URL}/markers/{m['id']}", json={"hours": {"start": 450, "end": 1050}}, headers=room)
    assert r.status_code == 200 and r.json()["hours"] == {"start": 450, "end": 1050}
    assert (await client.post(f"{URL}/markers/{m['id']}/archive", json={}, headers=room)).status_code == 422
    r = await client.post(f"{URL}/markers/{m['id']}/archive", json={"reason": "زال الخطر"}, headers=room)
    assert r.status_code == 200 and r.json()["status"] == "archived" and r.json()["decision_reason"] == "زال الخطر"
    assert (await client.post(f"{URL}/markers/{m['id']}/confirm", json={}, headers=room)).status_code == 409
    # A committee reads the register but changes nothing.
    assert (await client.get(f"{URL}/markers", headers=staff(["local_committee"], SFAX))).status_code == 200
    body = {"category": "gas", "location": place, "address": "نهج", "description": "قوارير"}
    assert (await client.post(f"{URL}/markers", json=body, headers=staff(["local_committee"], SFAX))).status_code == 403


# ---------------------------------------------------------------- the warnings of an incident


async def test_an_incident_shows_the_marks_around_it(client: httpx.AsyncClient, staff: Staff) -> None:
    room = staff(["operator"], SFAX, name="رئيس القاعة الجهوية")
    place = _place()
    gas = await _mark(client, room, category="gas", location=_north(place, 40), description="قوارير غاز · 120 قارورة")
    dog = await _mark(client, room, category="dog", location=_north(place, 60), description="كلب طليق")
    # Outside its circle (dog: 80 m): not shown.
    far = await _mark(client, room, category="dog", location=_north(place, 300), description="كلب بعيد")
    # A nursery whose hours never include now: shown greyed, never critical.
    now = service.minutes_now()
    start, end = (now + 120) % 1440, (now + 180) % 1440
    occ = await _mark(
        client,
        room,
        category="occ",
        location=_north(place, 100),
        description="روضة أطفال · 40 طفلا",
        hours={"start": start, "end": end},
    )
    # Past its review date: not shown until it is confirmed.
    old = await _mark(
        client, room, category="coll", location=_north(place, 20), description="سقف متداع", review_on="2026-01-01"
    )
    assert old["review_due"]
    incident_id, _ = await new_incident(client, staff, {**place, "accuracy_m": 10.0})
    r = await client.get(f"{URL}/incidents/{incident_id}", headers=room)
    assert r.status_code == 200, r.text
    out = r.json()
    ids = [w["marker_id"] for w in out["items"]]
    assert out["incident_kind"] == "fire"
    assert ids == [gas["id"], dog["id"], occ["id"]], ids
    first = out["items"][0]
    assert first["critical"] and 30 <= first["distance_m"] <= 50 and first["source"] == "room"
    assert not out["items"][1]["critical"]  # a dog is never critical
    assert out["items"][2]["off_hours"] and not out["items"][2]["critical"]
    assert far["id"] not in ids and old["id"] not in ids and out["unread"] == 3
    # Confirmed, the old mark comes back.
    r = await client.post(f"{URL}/markers/{old['id']}/confirm", json={}, headers=room)
    assert r.status_code == 200 and not r.json()["review_due"]
    out = (await client.get(f"{URL}/incidents/{incident_id}", headers=room)).json()
    assert old["id"] in [w["marker_id"] for w in out["items"]]
    # «Read»: one, then all; the reader's name is kept.
    r = await client.post(f"{URL}/incidents/{incident_id}/ack", json={"marker_ids": [gas["id"]]}, headers=room)
    assert r.status_code == 200 and r.json()["unread"] == 3
    w = next(x for x in r.json()["items"] if x["marker_id"] == gas["id"])
    assert w["room_ack_by"] == "رئيس القاعة الجهوية" and w["room_ack_at"]
    r = await client.post(f"{URL}/incidents/{incident_id}/ack", json={}, headers=room)
    assert r.json()["unread"] == 0
    # A mark that is not a warning of this incident cannot be marked read.
    r = await client.post(f"{URL}/incidents/{incident_id}/ack", json={"marker_ids": [far["id"]]}, headers=room)
    assert r.status_code == 422
    # Another gouvernorat's room does not read this incident.
    assert (await client.get(f"{URL}/incidents/{incident_id}", headers=staff(["operator"], 11))).status_code == 404


# ---------------------------------------------------------------- the citizen and the personal marks


async def test_a_citizen_consents_and_withdraws(
    client: httpx.AsyncClient, staff: Staff, citizen: dict[str, str]
) -> None:
    place = _place()
    home = _north(place, 30)
    body = {
        "location": home,
        "address": "نهج فرحات حشاد عدد 31 · الطابق 2",
        "needs": [{"category": "oxy", "description": "جهاز أكسجين منزلي يعمل باستمرار"}],
    }
    r = await client.put(ME, json=body, headers=citizen)
    assert r.status_code == 200, r.text
    mine = r.json()
    assert [n["category"] for n in mine["needs"]] == ["oxy"] and {c["key"] for c in mine["categories"]} == {
        "mob",
        "oxy",
        "deaf",
    }
    # A room category cannot be set by a citizen.
    bad = {**body, "needs": [{"category": "gas", "description": "قوارير"}]}
    assert (await client.put(ME, json=bad, headers=citizen)).status_code == 422
    room = staff(["operator"], SFAX, name="رئيس القاعة")
    # The register never lists personal marks: only their count.
    page = (await client.get(f"{URL}/markers", headers=room)).json()
    assert all(x["category"] not in ("mob", "oxy", "deaf") for x in page["items"]) and page["counts"]["personal"] >= 1
    incident_id, _ = await new_incident(client, staff, {**place, "accuracy_m": 10.0})
    out = (await client.get(f"{URL}/incidents/{incident_id}", headers=room)).json()
    oxy = next(w for w in out["items"] if w["category"] == "oxy")
    assert oxy["personal"] and oxy["critical"] and oxy["description"] == "جهاز أكسجين منزلي يعمل باستمرار"
    assert oxy["source_ref"] is None and not oxy["revealed"]
    # The name and phone: with a reason only, kept, and shown to the owner (when and why, never who).
    url = f"{URL}/incidents/{incident_id}/reveal/{oxy['marker_id']}"
    assert (await client.post(url, json={}, headers=room)).status_code == 422
    assert (await client.post(url, json={"reason": "x"}, headers=staff(["local_committee"], SFAX))).status_code == 403
    r = await client.post(url, json={"reason": "للاتصال والتأكد من وجوده في المنزل"}, headers=room)
    assert r.status_code == 200, r.text
    out = (await client.get(f"{URL}/incidents/{incident_id}", headers=room)).json()
    assert next(w for w in out["items"] if w["category"] == "oxy")["revealed"]
    rows = (await client.get(f"{URL}/reveals", headers=room)).json()
    assert rows[0]["reason"] == "للاتصال والتأكد من وجوده في المنزل" and rows[0]["by_name"] == "رئيس القاعة"
    mine = (await client.get(ME, headers=citizen)).json()
    assert mine["reveals"][0]["reason"] == "للاتصال والتأكد من وجوده في المنزل" and "by_name" not in mine["reveals"][0]
    # A personal mark is never edited by the room.
    r = await client.patch(f"{URL}/markers/{oxy['marker_id']}", json={"description": "تغيير"}, headers=room)
    assert r.status_code == 404
    # Withdrawn: gone from the room at once.
    r = await client.delete(ME, headers=citizen)
    assert r.status_code == 200 and r.json()["needs"] == []
    out = (await client.get(f"{URL}/incidents/{incident_id}", headers=room)).json()
    assert all(w["category"] != "oxy" for w in out["items"])


async def test_a_guest_cannot_consent(client: httpx.AsyncClient) -> None:
    from tests.conftest import accept_charter, device_headers

    guest = device_headers()
    await accept_charter(client, guest)
    body = {"location": _place(), "address": "نهج", "needs": [{"category": "deaf", "description": "لا أسمع"}]}
    r = await client.put(ME, json=body, headers=guest)
    assert r.status_code == 403 and r.json()["detail"] == "registration_required"


# ---------------------------------------------------------------- the team


async def test_the_team_reads_its_warnings_and_proposes_a_mark(client: httpx.AsyncClient, staff: Staff) -> None:
    room = staff(["operator"], SFAX, name="رئيس القاعة")
    place = _place()
    gas = await _mark(client, room, category="gas", location=_north(place, 30), description="قوارير غاز")
    hidden = await _mark(
        client, room, category="dog", location=_north(place, 40), description="للقاعة فقط", team_visible=False
    )
    incident_id, _ = await new_incident(client, staff, {**place, "accuracy_m": 10.0})
    leader, resource = await _on_shift(client, staff)
    r = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/assignments",
        json={"resource_id": resource["id"], "order": "إطفاء"},
        headers=room,
    )
    assert r.status_code == 201, r.text
    path = f"/missions/{r.json()['id']}/address-warnings"
    r = await leader.get(path)
    assert r.status_code == 200, r.text
    ids = [w["marker_id"] for w in r.json()["items"]]
    assert gas["id"] in ids and hidden["id"] not in ids and r.json()["unread"] == len(ids)
    r = await leader.post(f"{path}/ack", {})
    assert r.status_code == 200 and r.json()["unread"] == 0
    assert next(w for w in r.json()["items"] if w["marker_id"] == gas["id"])["team_ack_by"] == "سامي الطرابلسي"
    # The room sees that the team read it.
    out = (await client.get(f"{URL}/incidents/{incident_id}", headers=room)).json()
    assert next(w for w in out["items"] if w["marker_id"] == gas["id"])["team_ack_at"]
    # A mark from the scene: pending, not shown, until the room approves it.
    r = await leader.post(f"{path}/propose", {"category": "coll", "description": "شرفة متشققة فوق المدخل"})
    assert r.status_code == 201, r.text
    proposal = r.json()
    assert proposal["status"] == "pending" and proposal["source"] == "team"
    assert proposal["incident_id"] == incident_id
    assert (await leader.post(f"{path}/propose", {"category": "deaf", "description": "x x"})).status_code == 422
    out = (await client.get(f"{URL}/incidents/{incident_id}", headers=room)).json()
    assert proposal["id"] not in [w["marker_id"] for w in out["items"]]
    pending = (await client.get(f"{URL}/markers", params={"status": "pending"}, headers=room)).json()
    assert proposal["id"] in [x["id"] for x in pending["items"]]
    r = await client.post(f"{URL}/markers/{proposal['id']}/approve", json={}, headers=room)
    assert r.status_code == 200 and r.json()["status"] == "active" and r.json()["decided_by_name"] == "رئيس القاعة"
    out = (await client.get(f"{URL}/incidents/{incident_id}", headers=room)).json()
    assert proposal["id"] in [w["marker_id"] for w in out["items"]]
    # Another leader's mission is not found.
    other, _ = await _on_shift(client, staff)
    assert (await other.get(path)).status_code == 404
