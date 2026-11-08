"""Personnel management, phase H1 (docs/phase-h/design-h.md): the personnel department keeps the administrative file
(rank, appointment, transfer, sanction, reward) and the absences of its gouvernorat's staff; the central department
every gouvernorat and the transfers between them. The operations rooms read the staff with the kind and dates of
their absence and the general strength, never the sanctions, rewards, references or notes, and record nothing."""

import secrets
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import httpx

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/personnel"
GABES, BIZERTE = 61, 23


async def _unit(client: httpx.AsyncClient, staff: Staff, code: int) -> dict[str, Any]:
    lat, lon = (33.88, 10.1) if code == GABES else (37.27, 9.87)
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


def _officer(staff: Staff, code: int | None = GABES) -> dict[str, str]:
    return staff(["personnel_officer"], gouvernorat=code)


async def _agent(
    client: httpx.AsyncClient, staff: Staff, unit: dict[str, Any], category: str = "intervention", **extra: Any
) -> dict[str, Any]:
    r = await client.post(
        f"{URL}/agents",
        json={
            "unit_id": unit["id"],
            "matricule": f"P{secrets.token_hex(4).upper()}",
            "full_name": f"عون {secrets.token_hex(2)}",
            "rank": "عريف",
            "category": category,
            "phone": "+21698000000",
            **extra,
        },
        headers=_officer(staff, unit["gouvernorat_code"]),
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def test_only_the_personnel_department_records(client: httpx.AsyncClient, staff: Staff) -> None:
    unit = await _unit(client, staff, GABES)
    agent = await _agent(client, staff, unit)
    assert agent["category"] == "intervention" and agent["phone"] == "+21698000000"
    body = {"agent_id": agent["id"], "kind": "annual", "starts_on": "2026-12-01", "ends_on": "2026-12-10"}
    for roles in (["operator"], ["ops_manager"], ["sysadmin"], ["governor"]):
        headers = staff(roles, gouvernorat=GABES)
        assert (await client.post(f"{URL}/absences", json=body, headers=headers)).status_code == 403
        assert (await client.get(f"{URL}/agents/{agent['id']}", headers=headers)).status_code == 403
    # The rooms read the staff; the governor and the technical accounts do not.
    assert (await client.get(f"{URL}/agents", headers=staff(["operator"], gouvernorat=GABES))).status_code == 200
    for roles in (["governor"], ["sysadmin"], ["regional_account_admin"]):
        assert (await client.get(f"{URL}/agents", headers=staff(roles, gouvernorat=GABES))).status_code == 403
    # Another gouvernorat's department cannot record for Gabès.
    r = await client.post(f"{URL}/absences", json=body, headers=_officer(staff, BIZERTE))
    assert r.status_code in (403, 404)
    r = await client.post(f"{URL}/absences", json=body, headers=_officer(staff))
    assert r.status_code == 201, r.text


async def test_absences_overlap_change_and_cancel(client: httpx.AsyncClient, staff: Staff) -> None:
    unit = await _unit(client, staff, GABES)
    agent = await _agent(client, staff, unit)
    officer = _officer(staff)
    body = {
        "agent_id": agent["id"],
        "kind": "sick",
        "starts_on": "2027-01-05",
        "ends_on": "2027-01-09",
        "reference": "شهادة 1234",
        "note": "تسلّمت الشهادة",
    }
    r = await client.post(f"{URL}/absences", json=body, headers=officer)
    assert r.status_code == 201, r.text
    absence = r.json()
    assert absence["days"] == 5 and absence["reference"] == "شهادة 1234"
    overlap = {**body, "kind": "mission", "starts_on": "2027-01-09", "ends_on": "2027-01-12"}
    r = await client.post(f"{URL}/absences", json=overlap, headers=officer)
    assert r.status_code == 409 and r.json()["detail"] == "absence_overlap"
    backwards = {**body, "starts_on": "2027-02-10", "ends_on": "2027-02-01"}
    assert (await client.post(f"{URL}/absences", json=backwards, headers=officer)).status_code == 422
    # Back early: the leave is shortened, then the mission fits.
    r = await client.patch(
        f"{URL}/absences/{absence['id']}",
        json={**body, "ends_on": "2027-01-07", "version": absence["version"]},
        headers=officer,
    )
    assert r.status_code == 200 and r.json()["days"] == 3
    stale = {**body, "version": absence["version"]}
    assert (await client.patch(f"{URL}/absences/{absence['id']}", json=stale, headers=officer)).status_code == 409
    assert (await client.post(f"{URL}/absences", json=overlap, headers=officer)).status_code == 201
    r = await client.post(f"{URL}/absences/{absence['id']}/cancel", json={"reason": "خطأ في التسجيل"}, headers=officer)
    assert r.status_code == 200 and r.json()["cancelled_at"]
    listed = (await client.get(f"{URL}/absences?start=2027-01-01&end=2027-01-31", headers=officer)).json()
    mine = [a for a in listed["items"] if a["agent_id"] == agent["id"]]
    assert [a["kind"] for a in mine] == ["mission"]


async def test_the_room_sees_the_kind_never_the_reference(client: httpx.AsyncClient, staff: Staff) -> None:
    unit = await _unit(client, staff, GABES)
    agent = await _agent(client, staff, unit)
    today = date.today()
    body = {
        "agent_id": agent["id"],
        "kind": "sick",
        "starts_on": (today - timedelta(days=1)).isoformat(),
        "ends_on": (today + timedelta(days=2)).isoformat(),
        "reference": "شهادة 77",
        "note": "ملاحظة",
    }
    assert (await client.post(f"{URL}/absences", json=body, headers=_officer(staff))).status_code == 201
    room = staff(["operator"], gouvernorat=GABES)
    rows = (await client.get(f"{URL}/agents?unit_id={unit['id']}", headers=room)).json()
    assert rows["can_edit"] is False
    (row,) = rows["items"]
    assert row["absence"]["kind"] == "sick" and row["phone"] is None
    absences = (await client.get(f"{URL}/absences?agent_id={agent['id']}", headers=room)).json()["items"]
    assert absences and all(a["reference"] is None and a["note"] is None for a in absences)
    officer_view = (await client.get(f"{URL}/absences?agent_id={agent['id']}", headers=_officer(staff))).json()
    assert officer_view["items"][0]["reference"] == "شهادة 77"
    # Bizerte's room does not see Gabès's staff.
    other = await client.get(f"{URL}/agents?unit_id={unit['id']}", headers=staff(["operator"], gouvernorat=BIZERTE))
    assert other.json()["items"] == []


async def test_the_file_moves_rank_post_and_unit(client: httpx.AsyncClient, staff: Staff) -> None:
    unit = await _unit(client, staff, GABES)
    other_unit = await _unit(client, staff, GABES)
    agent = await _agent(client, staff, unit)
    officer = _officer(staff)
    today = date.today().isoformat()

    async def event(**body: Any) -> httpx.Response:
        return await client.post(f"{URL}/agents/{agent['id']}/events", json=body, headers=officer)

    r = await event(kind="rank", effective_on=today, title="رقيب", reference="قرار 12")
    assert r.status_code == 201, r.text
    rank_event = r.json()
    assert (await event(kind="appointment", effective_on=today, title="سائق")).status_code == 201
    r = await event(kind="transfer", effective_on=today, unit_id=other_unit["id"], reference="مذكرة 3")
    assert r.status_code == 201 and r.json()["from_unit_id"] == unit["id"]
    assert (await event(kind="sanction", effective_on=today, title="توبيخ", note="تأخير")).status_code == 201
    assert (await event(kind="reward", effective_on=today, title="تنويه")).status_code == 201
    future = (date.today() + timedelta(days=3)).isoformat()
    assert (await event(kind="rank", effective_on=future, title="وكيل")).json()["detail"] == "effective_in_future"
    assert (await event(kind="sanction", effective_on=today)).json()["detail"] == "title_required"
    assert (await event(kind="transfer", effective_on=today, unit_id=other_unit["id"])).status_code == 422

    file = (await client.get(f"{URL}/agents/{agent['id']}", headers=officer)).json()
    assert file["agent"]["rank"] == "رقيب" and file["agent"]["post"] == "سائق"
    assert file["agent"]["unit_id"] == other_unit["id"]
    assert {e["kind"] for e in file["events"]} == {"rank", "appointment", "transfer", "sanction", "reward"}

    # An older decision recorded late goes into the file without changing the current rank.
    old = (date.today() - timedelta(days=400)).isoformat()
    assert (await event(kind="rank", effective_on=old, title="عون أول")).status_code == 201
    row = (await client.get(f"{URL}/agents?unit_id={other_unit['id']}", headers=officer)).json()["items"][0]
    assert row["rank"] == "رقيب"

    # Cancelling the latest rank puts the previous one back.
    r = await client.post(f"{URL}/events/{rank_event['id']}/cancel", json={"reason": "قرار ملغى"}, headers=officer)
    assert r.status_code == 200 and r.json()["cancel_reason"] == "قرار ملغى"
    row = (await client.get(f"{URL}/agents?unit_id={other_unit['id']}", headers=officer)).json()["items"][0]
    assert row["rank"] == "عريف"


async def test_between_gouvernorats_the_central_department_moves_the_file(
    client: httpx.AsyncClient, staff: Staff
) -> None:
    gabes = await _unit(client, staff, GABES)
    bizerte = await _unit(client, staff, BIZERTE)
    agent = await _agent(client, staff, gabes)
    today = date.today().isoformat()
    body = {"agent_id": agent["id"], "kind": "annual", "starts_on": today, "ends_on": today}
    assert (await client.post(f"{URL}/absences", json=body, headers=_officer(staff))).status_code == 201
    transfer = {"kind": "transfer", "effective_on": today, "unit_id": bizerte["id"]}
    r = await client.post(f"{URL}/agents/{agent['id']}/events", json=transfer, headers=_officer(staff))
    assert r.status_code == 403 and r.json()["detail"] == "central_only"
    central = _officer(staff, None)
    r = await client.post(f"{URL}/agents/{agent['id']}/events", json=transfer, headers=central)
    assert r.status_code == 201, r.text
    # The file followed: Bizerte's department sees it whole, Gabès's no longer.
    file = await client.get(f"{URL}/agents/{agent['id']}", headers=_officer(staff, BIZERTE))
    assert file.status_code == 200 and len(file.json()["absences"]) == 1
    assert (await client.get(f"{URL}/agents/{agent['id']}", headers=_officer(staff))).status_code in (403, 404)


async def test_general_strength(client: httpx.AsyncClient, staff: Staff) -> None:
    unit = await _unit(client, staff, GABES)
    agents = [await _agent(client, staff, unit) for _ in range(3)]
    await _agent(client, staff, unit, category="room")
    await _agent(client, staff, unit, category="admin")
    today = date.today().isoformat()
    officer = _officer(staff)
    for agent, kind in zip(agents[:2], ("mission", "annual"), strict=True):
        body = {"agent_id": agent["id"], "kind": kind, "starts_on": today, "ends_on": today}
        assert (await client.post(f"{URL}/absences", json=body, headers=officer)).status_code == 201
    r = await client.get(f"{URL}/strength?on={today}", headers=staff(["ops_manager"], gouvernorat=GABES))
    assert r.status_code == 200, r.text
    (row,) = [u for u in r.json()["units"] if u["unit_id"] == unit["id"]]
    assert row["intervention"] == {"total": 3, "absent": 2, "present": 1, "by_kind": {"annual": 1, "mission": 1}}
    assert row["room"]["present"] == 1 and row["admin"]["present"] == 1
    assert r.json()["total"]["intervention"]["total"] >= 3


async def test_units_to_choose_from(client: httpx.AsyncClient, staff: Staff) -> None:
    unit = await _unit(client, staff, GABES)
    await _unit(client, staff, BIZERTE)
    units = (await client.get(f"{URL}/units", headers=_officer(staff))).json()
    assert unit["id"] in {u["id"] for u in units}
    assert {u["gouvernorat_code"] for u in units} == {GABES}
