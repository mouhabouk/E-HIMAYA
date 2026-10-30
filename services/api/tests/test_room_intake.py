"""Reports an operations room enters by hand (phase N, docs/phase-n/design-n.md §5): telephone, radio or in person,
a report like the others, held by the room that entered it, inside its gouvernorat."""

from collections.abc import Callable

import httpx

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/reports"
NABEUL, SOUSSE = 21, 51
# Nabeul town and Sousse town.
IN_NABEUL = {"lat": 36.4513, "lon": 10.7357}
IN_SOUSSE = {"lat": 35.8256, "lon": 10.6369}


async def test_a_room_enters_a_report_by_phone(client: httpx.AsyncClient, staff: Staff) -> None:
    agent = staff(["operator"], gouvernorat=NABEUL, name="عون القاعة")
    entered = await client.post(
        URL,
        json={"category": "fire", "location": IN_NABEUL, "channel": "phone", "text": "دخان كثيف قرب السوق البلدي"},
        headers=agent,
    )
    assert entered.status_code == 201, entered.text
    report = entered.json()
    assert report["tracking_code"].split("-")[2] == "21"
    assert report["source"] == "room" and report["intake_channel"] == "phone"
    assert report["gouvernorat_code"] == NABEUL and report["status"] == "received"
    # The room that wrote it down holds it; the AI baseline gave it a priority and the claim deadline a band.
    assert report["claimed_room"] == f"g:{NABEUL}"
    assert report["priority_score"] is not None and report["sla_band"] is not None
    # It is listed with the other reports of the room.
    listed = (await client.get(URL, headers=agent, params={"q": report["tracking_code"]})).json()
    assert report["id"] in [r["id"] for r in listed["items"]]


async def test_inside_its_gouvernorat_and_for_the_rooms_only(client: httpx.AsyncClient, staff: Staff) -> None:
    body = {"category": "flood", "location": IN_SOUSSE, "channel": "radio"}
    outside = await client.post(URL, json=body, headers=staff(["ops_manager"], gouvernorat=NABEUL))
    assert outside.status_code == 422 and outside.json()["detail"] == "outside_gouvernorat"
    central = await client.post(URL, json=body, headers=staff(["operator"], gouvernorat=None))
    # The central room enters a report anywhere; the gouvernorat's room answers it.
    assert central.status_code == 201 and central.json()["claimed_room"] is None
    assert central.json()["gouvernorat_code"] == SOUSSE
    for roles in (["field_commander"], ["local_committee"], ["governor"]):
        refused = await client.post(URL, json=body, headers=staff(roles, gouvernorat=SOUSSE))
        assert refused.status_code == 403, roles
    sea = await client.post(
        URL, json={**body, "location": {"lat": 37.55, "lon": 11.6}}, headers=staff(["operator"], gouvernorat=None)
    )
    assert sea.status_code == 422 and sea.json()["detail"] == "outside_tunisia"
    bad = await client.post(URL, json={**body, "channel": "pigeon"}, headers=staff(["operator"], gouvernorat=SOUSSE))
    assert bad.status_code == 422


async def test_the_list_takes_several_gouvernorats(client: httpx.AsyncClient, staff: Staff) -> None:
    """Phase N (design §6): the national map and list filter on several gouvernorats at once."""
    central = staff(["operator"], gouvernorat=None)
    ids = {}
    for name, place in (("nabeul", IN_NABEUL), ("sousse", IN_SOUSSE)):
        r = await client.post(
            URL, json={"category": "medical", "location": place, "channel": "in_person"}, headers=central
        )
        ids[name] = r.json()["id"]
    both = (
        await client.get(URL, params={"gouvernorat_code": f"{NABEUL},{SOUSSE}", "limit": 500}, headers=central)
    ).json()
    assert {ids["nabeul"], ids["sousse"]} <= {r["id"] for r in both["items"]}
    one = (await client.get(URL, params={"gouvernorat_code": str(SOUSSE), "limit": 500}, headers=central)).json()
    assert ids["sousse"] in {r["id"] for r in one["items"]} and ids["nabeul"] not in {r["id"] for r in one["items"]}
    bad = await client.get(URL, params={"gouvernorat_code": "21,x"}, headers=central)
    assert bad.status_code == 422 and bad.json()["detail"] == "unknown_gouvernorat"
