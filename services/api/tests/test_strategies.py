"""The strategies menu (docs/phase-s/design-s.md §2.2): the items the national system administrator adds, each seen
by every staff member or by the roles it names."""

from collections.abc import Callable

import httpx

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/strategies"
GABES = 81


def _item(**over: object) -> dict[str, object]:
    body: dict[str, object] = {
        "name": {"ar": "[SIM] الاستراتيجية الوطنية للحد من المخاطر", "fr": "[SIM] SNRRC 2030", "en": "[SIM] NDRR"},
        "summary": {"ar": "الأهداف والمحاور"},
        "body": {"ar": "## المحاور\n\n1. الفهم\n2. الحوكمة"},
        "icon": "flag",
        "tone": "teal",
        "position": 10,
    }
    body.update(over)
    return body


async def test_the_administrator_adds_an_item_the_staff_reads(client: httpx.AsyncClient, staff: Staff) -> None:
    admin = staff(["sysadmin"], gouvernorat=None)
    for headers in (staff(["sysadmin"], gouvernorat=GABES), staff(["central_committee"], gouvernorat=None)):
        r = await client.put(f"{URL}/srrc_test", json=_item(), headers=headers)
        assert r.status_code == 403, r.text
    r = await client.put(f"{URL}/srrc_test", json=_item(), headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["updated_at"] and r.json()["tone"] == "teal"
    # Neither a page text nor a link; an unknown role; a link to another scheme.
    assert (await client.put(f"{URL}/empty_test", json=_item(body={}), headers=admin)).status_code == 422
    assert (await client.put(f"{URL}/x_test", json=_item(roles=["citizen"]), headers=admin)).status_code == 422
    bad = _item(body={}, link="javascript:alert(1)")
    assert (await client.put(f"{URL}/x_test", json=bad, headers=admin)).status_code == 422
    r = await client.put(f"{URL}/link_test", json=_item(body={}, link="/snacr", roles=["governor"]), headers=admin)
    assert r.status_code == 200, r.text

    operator = staff(["operator"], gouvernorat=GABES)
    seen = (await client.get(URL, headers=operator)).json()
    keys = {i["key"] for i in seen["items"]}
    assert "srrc_test" in keys and "link_test" not in keys and seen["can_manage"] is False
    assert (await client.get(f"{URL}/srrc_test", headers=operator)).json()["body"]["ar"].startswith("## المحاور")
    assert (await client.get(f"{URL}/link_test", headers=operator)).status_code == 404
    governor = staff(["governor"], gouvernorat=GABES)
    assert "link_test" in {i["key"] for i in (await client.get(URL, headers=governor)).json()["items"]}

    # Switched off: gone from the menu, still listed for the administrator.
    assert (await client.put(f"{URL}/srrc_test", json=_item(active=False), headers=admin)).status_code == 200
    assert "srrc_test" not in {i["key"] for i in (await client.get(URL, headers=operator)).json()["items"]}
    listed = (await client.get(URL, headers=admin)).json()
    assert listed["can_manage"] is True and "srrc_test" in {i["key"] for i in listed["items"]}

    for key in ("srrc_test", "link_test"):
        assert (await client.delete(f"{URL}/{key}", headers=admin)).status_code == 204
    assert (await client.delete(f"{URL}/srrc_test", headers=admin)).status_code == 404
