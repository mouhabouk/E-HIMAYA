"""People and places exposed on the area of a crisis axis (OS14, docs/phase-os14/design-os14.md): the estimate by
delegation with its range, the places in the core and the ring, the lines cut, who may compute it, the record in the
timeline, the recompute when the area changes, and the same figures in the decision window and the map layer."""

import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crisis import exposure

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/crisis"
NABEUL = 21
# A square around Nabeul town (lon, lat), as in test_crisis.py.
AREA = {
    "type": "Polygon",
    "coordinates": [[[10.60, 36.35], [10.85, 36.35], [10.85, 36.55], [10.60, 36.55], [10.60, 36.35]]],
}
SMALLER = {
    "type": "Polygon",
    "coordinates": [[[10.70, 36.42], [10.76, 36.42], [10.76, 36.48], [10.70, 36.48], [10.70, 36.42]]],
}


def commander(staff: Staff) -> dict[str, str]:
    return staff(["ops_manager"], gouvernorat=None)


def room(staff: Staff) -> dict[str, str]:
    return staff(["ops_manager"], gouvernorat=NABEUL)


def governor(staff: Staff) -> dict[str, str]:
    return staff(["governor"], gouvernorat=NABEUL)


# --- Pure rules -----------------------------------------------------------------------------------------------------


def _d(**kw: float) -> exposure.Delegation:
    base = {"population": 10_000, "area_m2": 100.0, "ring_m2": 50.0, "core_m2": 20.0}
    base.update(kw)
    return exposure.Delegation(1, "د", "D", NABEUL, int(base["population"]), base["area_m2"], base["ring_m2"],
                               base["core_m2"], int(kw.get("built", 0)), int(kw.get("built_ring", 0)),
                               int(kw.get("built_core", 0)))  # fmt: skip


def test_estimate_keeps_a_range() -> None:
    # No place of daily life: both methods give the area share.
    assert exposure.estimate(_d(), core=False) == (5000, 5000, 5000)
    # The town is inside: 18 of 20 places, pulled towards the area share by the prior.
    low, high, mid = exposure.estimate(_d(built=20, built_ring=18, built_core=10), core=False)
    assert low == 5000 and high == round(10_000 * (18 + 5) / 30) and mid == (low + high) // 2
    # The core is inside the ring, never more than the delegation.
    assert exposure.estimate(_d(ring_m2=500.0), core=False)[1] == 10_000
    assert exposure.rounded(12_345) == 12_000 and exposure.rounded(1_234) == 1_200 and exposure.rounded(64) == 60


def test_dedupe_and_groups() -> None:
    a = exposure.Place("Lycée Ibn Khaldoun", "institutes", 36.45, 10.73, False, True)
    b = exposure.Place("lycée  ibn khaldoun", "institutes", 36.4502, 10.7302, True, True)
    c = exposure.Place("Lycée Ibn Khaldoun", "institutes", 36.60, 10.73, False, True)  # 17 km away: another one
    kept = exposure.dedupe([a, b, c])
    assert len(kept) == 2 and kept[0].core
    assert exposure.group_of("elderly_homes") == "elderly" and exposure.group_of("pharmacies") is None
    result = exposure.summarise(
        [_d()],
        kept,
        [("railways", "", 1.2, True), ("railways", "", 0.8, True), ("roads", "RN1", 0.01, False)],
        ring_m=1000,
        core_km2=2.0,
        ring_km2=5.0,
        layers=[("institutes", True)],
        at=datetime(2026, 11, 13, tzinfo=UTC),
    )
    assert result["groups"]["education"]["count"] == 2 and result["groups"]["education"]["core"] == 1
    assert result["lines"] == [{"layer": "railways", "name": "", "km": 2.0, "cut": True}]  # the 10 m stub is dropped
    assert result["brief"]["education"] == 2 and result["brief"]["lines_cut"] == 1
    assert result["population"]["estimate"] == 5000


# --- Through the API ------------------------------------------------------------------------------------------------


async def _layer(session: AsyncSession, stem: str) -> uuid.UUID:
    key = f"osm_{stem}"
    await session.execute(
        text(
            "INSERT INTO geo.layer (key, name, icon, colour, created_by, updated_by) "
            'VALUES (:k, \'{"ar": "t", "fr": "t", "en": "t"}\', \'pin\', \'#283593\', \'os14-test\', \'os14-test\') '
            "ON CONFLICT (key) DO NOTHING"
        ),
        {"k": key},
    )
    return uuid.UUID(str(await session.scalar(text("SELECT id FROM geo.layer WHERE key = :k"), {"k": key})))


async def _place(session: AsyncSession, stem: str, name: str, lon: float, lat: float, shape: str | None = None) -> None:
    await session.execute(
        text(
            "INSERT INTO geo.layer_feature (layer_id, ref, name, location, shape) VALUES (:l, :r, :n, "
            "CAST(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) AS geography), "
            "CAST(ST_GeomFromText(:s, 4326) AS geography))"
        ),
        {"l": await _layer(session, stem), "r": str(uuid.uuid4()), "n": name, "lon": lon, "lat": lat, "s": shape},
    )


@pytest.fixture
async def places(session: AsyncSession) -> AsyncIterator[str]:
    tag = uuid.uuid4().hex[:6]
    await _place(session, "hospitals", f"المستشفى الجهوي {tag}", 10.735, 36.45)
    await _place(session, "elderly_homes", f"دار المسنين {tag}", 10.70, 36.40)
    await _place(session, "schools", f"مدرسة الوفاء {tag}", 10.74, 36.46)
    await _place(session, "schools", f"مدرسة الوفاء {tag}", 10.7401, 36.4601)  # the same school twice
    await _place(session, "schools", f"مدرسة بعيدة {tag}", 10.95, 36.70)  # outside the footprint and the ring
    await _place(session, "worship", f"جامع {tag}", 10.73, 36.45)
    await _place(session, "railways", f"خط {tag}", 10.73, 36.45, "LINESTRING(10.55 36.45, 10.95 36.45)")
    await session.commit()
    yield tag
    # The places, and the layers this test created, leave with it: other tests read the layers.
    await session.execute(text("DELETE FROM geo.layer_feature WHERE name LIKE :t"), {"t": f"%{tag}"})
    await session.execute(
        text(
            "DELETE FROM geo.layer l WHERE l.created_by = 'os14-test' "
            "AND NOT EXISTS (SELECT 1 FROM geo.layer_feature f WHERE f.layer_id = l.id)"
        )
    )
    await session.commit()


async def test_estimate_record_rights_and_readers(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession, places: str
) -> None:
    opened = await client.post(
        f"{URL}/axes",
        json={
            "name": "فيضانات نابل، أكتوبر 2026",
            "kind": "flood",
            "level": 3,
            "gouvernorat_code": NABEUL,
            "area": AREA,
        },
        headers=commander(staff),
    )
    assert opened.status_code == 201, opened.text
    axis = opened.json()["id"]

    state = (await client.get(f"{URL}/axes/{axis}/exposure", headers=governor(staff))).json()
    assert state["estimate"] is None and state["has_area"] and not state["can_compute"]
    assert state["default_ring_m"] == 1000 and state["rings"] == [0, 500, 1000, 2000, 5000]
    # The governor reads, the room computes.
    assert (await client.post(f"{URL}/axes/{axis}/exposure", json={}, headers=governor(staff))).status_code == 403
    assert (
        await client.post(f"{URL}/axes/{axis}/exposure", json={"ring_m": 750}, headers=room(staff))
    ).status_code == 422
    r = await client.post(f"{URL}/axes/{axis}/exposure", json={}, headers=room(staff))
    assert r.status_code == 200, r.text
    est = r.json()
    assert est["ring_m"] == 1000 and est["area_km2"] > est["core_km2"] > 400
    assert est["population"]["low"] <= est["population"]["estimate"] <= est["population"]["high"]
    assert est["population"]["estimate"] > 10_000 and est["population"]["core"] <= est["population"]["estimate"]
    names = {d["name_ar"] for d in est["delegations"]}
    assert "نابل" in names
    health = [p["name"] for p in est["groups"]["health"]["items"]]
    assert f"المستشفى الجهوي {places}" in health
    schools = [p for p in est["groups"]["education"]["items"] if places in p["name"]]
    assert [p["name"] for p in schools] == [f"مدرسة الوفاء {places}"]  # one, the far one is out
    assert schools[0]["zone"] == "core"
    assert any(f"دار المسنين {places}" == p["name"] for p in est["groups"]["elderly"]["items"])
    line = next(x for x in est["lines"] if x["name"] == f"خط {places}")
    assert line["cut"] and 20 < line["km"] < 30  # 0.25° of longitude plus the ring on both sides
    assert est["ring"]["type"] == "MultiPolygon"
    assert not est["stale"]

    # The governor reads the estimate (no author), the timeline keeps the figures only.
    read = (await client.get(f"{URL}/axes/{axis}/exposure", headers=governor(staff))).json()
    assert read["estimate"]["population"] == est["population"] and read["estimate"]["computed_by"] is None
    detail = (await client.get(f"{URL}/axes/{axis}", headers=room(staff))).json()
    event = next(e for e in detail["timeline"] if e["kind"] == "exposure")
    assert set(event["payload"]) == {"brief"} and event["payload"]["brief"]["population"] == est["brief"]["population"]

    # A new area recomputes with the same ring, and the decision window shows the new figures.
    axis_row = (await client.get(f"{URL}/axes/{axis}", headers=room(staff))).json()["axis"]
    patched = await client.patch(
        f"{URL}/axes/{axis}", json={"version": axis_row["version"], "area": SMALLER}, headers=room(staff)
    )
    assert patched.status_code == 200, patched.text
    again = (await client.get(f"{URL}/axes/{axis}/exposure", headers=room(staff))).json()["estimate"]
    assert again["ring_m"] == 1000 and again["core_km2"] < 50 and not again["stale"]
    assert again["population"]["estimate"] < est["population"]["estimate"]
    now = (await client.get("/api/v1/staff/window/now", headers=room(staff))).json()
    row = next(a for a in now["axes"] if a["id"] == axis)
    assert row["exposure"]["population"] == again["brief"]["population"] and row["exposure"]["ring_m"] == 1000

    # The optional layer of the interactive map lists it.
    layer = (await client.get(f"{URL}/exposure/map", headers=room(staff))).json()
    assert axis in [i["axis_id"] for i in layer["items"]]


async def test_no_area_no_estimate(client: httpx.AsyncClient, staff: Staff) -> None:
    opened = await client.post(
        f"{URL}/axes",
        json={"name": "عاصفة دون حيّز", "kind": "storm", "level": 2, "gouvernorat_code": NABEUL},
        headers=commander(staff),
    )
    assert opened.status_code == 201, opened.text
    axis = opened.json()["id"]
    state = (await client.get(f"{URL}/axes/{axis}/exposure", headers=room(staff))).json()
    assert not state["has_area"] and state["default_ring_m"] == 0
    r = await client.post(f"{URL}/axes/{axis}/exposure", json={}, headers=room(staff))
    assert r.status_code == 409 and r.json()["detail"] == "axis_no_area"
