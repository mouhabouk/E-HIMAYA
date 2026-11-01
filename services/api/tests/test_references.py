"""The Office's reference lists (Yamen, 2026-11-01): read by every staff member, kept by the central room; an item is
renamed or retired, never deleted; the lists are exported as a workbook or as CSV."""

import io
from collections.abc import Callable

import httpx
from openpyxl import load_workbook
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/references"


async def test_reference_lists(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    operator = staff(["operator"], gouvernorat=21)
    r = await client.get(URL, headers=operator)
    assert r.status_code == 200
    body = r.json()
    lists = {rl["key"]: rl for rl in body["lists"]}
    assert body["can_manage"] is False
    assert list(lists)[:2] == ["vehicle_type", "agent_status"]
    vehicles = {i["code"]: i["label_ar"] for i in lists["vehicle_type"]["items"]}
    assert vehicles["8"] == "شاحنة إطفاء حرائق الغابات" and len(vehicles) == 39
    assert [i["label_ar"] for i in lists["agent_status"]["items"]][:2] == ["إجازة سنوية", "إجازة مرض"]
    crops = {i["label_ar"]: (i["code"], i["unit"]) for i in lists["crop_loss"]["items"]}
    assert crops["تبن"] == ("6", "bale") and crops["قمح"] == ("1", "ha")
    for key in ("agent_post", "vehicle_state", "vehicle_situation", "accident_party", "fire_nature",
                "programme_place", "intervention_field", "forest_place", "agri_place", "damage_unit"):  # fmt: skip
        assert lists[key]["items"], key

    # Only the central room changes them.
    r = await client.post(f"{URL}/agent_status/items", json={"label_ar": "عطلة استثنائية"}, headers=operator)
    assert r.status_code == 403
    local = staff(["local_committee"], gouvernorat=21)
    assert (await client.post(f"{URL}/agent_status/items", json={"label_ar": "x"}, headers=local)).status_code == 403
    central = staff(["central_committee"], gouvernorat=None)
    assert (await client.get(URL, headers=central)).json()["can_manage"] is True
    r = await client.post(f"{URL}/agent_status/items", json={"label_ar": " عطلة استثنائية "}, headers=central)
    assert r.status_code == 201, r.text
    added = r.json()
    assert added["label_ar"] == "عطلة استثنائية" and added["sort"] == 80 and added["active"] is True
    r = await client.post(f"{URL}/agent_status/items", json={"label_ar": "عطلة استثنائية"}, headers=central)
    assert r.status_code == 409 and r.json()["detail"] == "reference_exists"
    assert (await client.post(f"{URL}/nothing/items", json={"label_ar": "x"}, headers=central)).status_code == 404
    r = await client.patch(f"{URL}/items/{added['id']}", json={"label_fr": "Congé exceptionnel", "active": False},
                           headers=central)  # fmt: skip
    assert r.status_code == 200 and r.json()["active"] is False and r.json()["label_fr"] == "Congé exceptionnel"
    listed = (await client.get(URL, headers=operator)).json()["lists"]
    retired = [i for rl in listed if rl["key"] == "agent_status" for i in rl["items"] if i["id"] == added["id"]]
    assert retired and retired[0]["active"] is False  # still readable

    # Exports.
    xlsx = await client.get(f"{URL}/export", headers=operator)
    wb = load_workbook(io.BytesIO(xlsx.content))
    assert wb.sheetnames[0] == "vehicle_type" and wb["vehicle_type"]["A1"].value == "أصناف الوسائل"
    csv = await client.get(f"{URL}/export", params={"format": "csv", "key": "crop_loss"}, headers=operator)
    lines = csv.content.decode("utf-8-sig").splitlines()
    assert lines[0] == "list,code,label_ar,label_fr,unit,active" and lines[1] == "crop_loss,1,قمح,,ha,1"
    log = await session.execute(
        text("SELECT action FROM audit.log WHERE target = :t ORDER BY id"), {"t": f"ref_item:{added['id']}"}
    )
    actions = log.scalars().all()
    assert actions == ["references.item_added", "references.item_changed"]

    await session.execute(text("DELETE FROM ref.item WHERE id = :i"), {"i": added["id"]})
    await session.commit()
