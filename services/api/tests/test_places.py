# covers: FR-M-10
"""Saved places of the operations rooms (phase M, docs/phase-m/design-m.md §7)."""

from collections.abc import Callable

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import SFAX, TUNIS

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/places"


async def test_a_room_keeps_its_places(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    sfax_room = staff(["operator"], gouvernorat=61)
    body = {"name": " Dépôt de carburant ", "kind": "critical", "note": "Accès par la route de Gabès", **SFAX}
    body.pop("accuracy_m", None)
    r = await client.post(URL, json=body, headers=sfax_room)
    assert r.status_code == 201, r.text
    place = r.json()
    assert place["name"] == "Dépôt de carburant" and place["gouvernorat_code"] == 61
    assert place["delegation_id"] == 6114

    # Another gouvernorat is out of scope; the sea and abroad are refused.
    tunis = {k: v for k, v in TUNIS.items() if k != "accuracy_m"}
    assert (await client.post(URL, json={**body, **tunis}, headers=sfax_room)).json()["detail"] == "out_of_scope"
    sea = {**body, "lat": 34.70, "lon": 10.86}
    assert (await client.post(URL, json=sea, headers=sfax_room)).json()["detail"] == "outside_tunisia"
    assert (await client.post(URL, json={**body, "kind": "secret"}, headers=sfax_room)).status_code == 422

    # Critical places first; the Tunis room does not see Sfax's, the central room does.
    await client.post(URL, json={**body, "name": "École", "kind": "important", "note": None}, headers=sfax_room)
    listed = (await client.get(URL, headers=sfax_room)).json()
    mine = [p for p in listed if p["gouvernorat_code"] == 61]
    assert [p["kind"] for p in mine][:1] == ["critical"]
    assert place["id"] not in {
        p["id"] for p in (await client.get(URL, headers=staff(["operator"], gouvernorat=11))).json()
    }
    central = staff(["ops_manager"], gouvernorat=None)
    assert place["id"] in {p["id"] for p in (await client.get(URL, headers=central)).json()}

    r = await client.put(
        f"{URL}/{place['id']}", json={"name": "Dépôt", "kind": "other", "note": " "}, headers=sfax_room
    )
    assert r.status_code == 200 and r.json()["kind"] == "other" and r.json()["note"] is None
    tunis_room = staff(["operator"], gouvernorat=11)
    assert (await client.delete(f"{URL}/{place['id']}", headers=tunis_room)).status_code == 404
    assert (await client.delete(f"{URL}/{place['id']}", headers=sfax_room)).status_code == 204
    assert (await client.get(URL, headers=staff(["citizen"], gouvernorat=61))).status_code == 403
    logged = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE target = :t"), {"t": f"place:{place['id']}"}
    )
    assert logged == 3
