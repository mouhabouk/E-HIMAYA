"""The decision window (L4, docs/phase-l/design-l4.md §3 and §5): the quick search reads dialect, places and references;
figures are aggregated with the small counts hidden and no personal data; two periods or two gouvernorats compare
side by side; reports export in PDF and XLSX and are audited; the minister, governors and committees see the window
only through a delegation, on its events only; saved searches and the dictionary of the central room."""

import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.access import keycloak
from app.modules.window import service
from tests.test_accounts import FakeDirectory

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/window"
NABEUL, SOUSSE = 21, 51
# Periods no other test writes in, so the counts are exact.
JULY_A = ("2011-07-01", "2011-07-31")
JULY_B = ("2012-07-01", "2012-07-31")


@pytest.fixture
def directory() -> Iterator[FakeDirectory]:
    fake = FakeDirectory()
    keycloak.set_directory(fake)
    yield fake
    keycloak.set_directory(None)


def room(staff: Staff, code: int = NABEUL) -> dict[str, str]:
    return staff(["ops_manager"], gouvernorat=code)


def central(staff: Staff) -> dict[str, str]:
    return staff(["ops_manager"], gouvernorat=None)


async def incident(
    session: AsyncSession, day: str, *, code: int = NABEUL, category: str = "fire", injured: int = 0
) -> str:
    incident_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO ops.incident (id, category, severity, centroid, gouvernorat_code, title, opened_at) "
            "VALUES (:id, :c, 3, ST_SetSRID(ST_MakePoint(10.73, 36.45), 4326)::geography, :g, "
            "'[SIM] منزل السيد فلان', :at)"
        ),
        {"id": incident_id, "c": category, "g": code, "at": datetime.fromisoformat(f"{day}T10:00+01:00")},
    )
    if injured:
        await session.execute(
            text("INSERT INTO ops.casualty_count (incident_id, injured_light) VALUES (:id, :n)"),
            {"id": incident_id, "n": injured},
        )
    await session.commit()
    return str(incident_id)


async def seed(session: AsyncSession) -> dict[str, list[str]]:
    """July 2011 in Nabeul: six fires (one injured each) and two floods; one fire in Sousse. July 2012: three fires."""
    a = [await incident(session, f"2011-07-{d:02d}", injured=1) for d in range(1, 7)]
    a += [await incident(session, "2011-07-10", category="flood") for _ in range(2)]
    sousse = [await incident(session, "2011-07-12", code=SOUSSE)]
    b = [await incident(session, "2012-07-05") for _ in range(3)]
    return {"a": a, "sousse": sousse, "b": b}


@pytest.fixture
async def seeded(session: AsyncSession) -> dict[str, list[str]]:
    old = "SELECT id FROM ops.incident WHERE opened_at >= '2011-01-01' AND opened_at < '2013-01-01'"
    await session.execute(text(f"DELETE FROM crisis.axis_incident WHERE incident_id IN ({old})"))  # noqa: S608
    await session.execute(text("DELETE FROM ops.incident WHERE opened_at >= '2011-01-01' AND opened_at < '2013-01-01'"))
    await session.commit()
    return await seed(session)


# ---------------------------------------------------------------- the quick search


async def test_quick_search_reads_dialect_places_and_references(session: AsyncSession) -> None:
    vocab = await service.vocabulary(session)
    assert service.norm("الحَريقة") == service.norm("الحريقه")
    crit, understood = service.interpret("كسيدة في نابل", vocab, words_allowed=True)
    assert crit.categories == {"traffic_accident"} and crit.gouvernorats == {NABEUL}
    assert [u.kind for u in understood] == ["category", "gouvernorat"]  # "في" (in) is left out
    crit, understood = service.interpret("حريق غابة", vocab, words_allowed=True)
    assert crit.classifications == {"forest_fire"} and not crit.categories
    crit, understood = service.interpret("الحرايق 1a2b3c4d", vocab, words_allowed=True)
    assert crit.categories == {"fire"} and crit.refs == {"1a2b3c4d"}
    # A delegate's unknown words search nothing (no title search outside the full view).
    crit, understood = service.interpret("فلان حريق", vocab, words_allowed=False)
    assert not crit.words and understood[0].kind == "unmatched" and crit.categories == {"fire"}


# ---------------------------------------------------------------- the full view


async def test_search_floors_small_counts_and_shows_no_personal_data(
    client: httpx.AsyncClient, staff: Staff, seeded: dict[str, list[str]]
) -> None:
    params = {"from": JULY_A[0], "to": JULY_A[1]}
    r = await client.get(f"{URL}/search", params=params, headers=room(staff))
    assert r.status_code == 200, r.text
    body = r.json()
    fig = body["figures"]
    assert (fig["incidents"], fig["injured"], body["gouvernorats"]) == (8, 6, [NABEUL])
    cells = {c["key"]: c["count"] for c in fig["by_category"]}
    assert cells == {"fire": 6, "flood": None}  # two floods: fewer than 5, hidden
    assert len(body["items"]) == 8 and not body["delegated"]
    assert all("title" not in item for item in body["items"])
    assert "فلان" not in r.text
    r = await client.get(f"{URL}/search", params={**params, "q": "حرايق نابل"}, headers=room(staff))
    assert r.json()["figures"]["incidents"] == 6
    ref = seeded["a"][0].replace("-", "")[:8]
    r = await client.get(f"{URL}/search", params={**params, "q": ref}, headers=room(staff))
    assert [i["id"] for i in r.json()["items"]] == [seeded["a"][0]]
    r = await client.get(
        f"{URL}/search", params={**params, "category": "fire,flood", "severity": "3"}, headers=room(staff)
    )
    assert r.json()["figures"]["incidents"] == 8
    # A regional room asks for another gouvernorat: refused.
    r = await client.get(f"{URL}/search", params={**params, "gouvernorats": str(SOUSSE)}, headers=room(staff))
    assert (r.status_code, r.json()["detail"]) == (403, "out_of_scope")
    # The central room sees both.
    r = await client.get(f"{URL}/search", params=params, headers=central(staff))
    assert r.json()["figures"]["incidents"] == 9


async def test_compare_two_periods_and_two_gouvernorats(
    client: httpx.AsyncClient, staff: Staff, seeded: dict[str, list[str]]
) -> None:
    params = {"a_from": JULY_A[0], "a_to": JULY_A[1], "b_from": JULY_B[0], "b_to": JULY_B[1], "category": "fire"}
    r = await client.get(f"{URL}/compare", params=params, headers=room(staff))
    assert r.status_code == 200, r.text
    rows = {(x["metric"], x["key"]): x for x in r.json()["rows"]}
    assert rows[("incidents", None)]["a"] == 6 and rows[("incidents", None)]["b"] is None  # 3: hidden
    assert rows[("incidents", None)]["delta"] is None
    assert r.json()["a"]["programmes"] is not None
    r = await client.get(
        f"{URL}/compare",
        params={"mode": "gouvernorats", "from": JULY_A[0], "to": JULY_A[1], "a_gouvernorat": 21, "b_gouvernorat": 51},
        headers=central(staff),
    )
    assert r.status_code == 200, r.text
    assert r.json()["a"]["figures"]["incidents"] == 8 and r.json()["b"]["figures"]["incidents"] is None
    r = await client.get(
        f"{URL}/compare",
        params={"mode": "gouvernorats", "from": JULY_A[0], "to": JULY_A[1], "a_gouvernorat": 21, "b_gouvernorat": 51},
        headers=room(staff),
    )
    assert r.status_code == 403


async def test_exports_are_audited(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession, seeded: dict[str, list[str]]
) -> None:
    filters = {"from": JULY_A[0], "to": JULY_A[1]}
    r = await client.post(
        f"{URL}/export",
        json={"kind": "search", "format": "xlsx", "lang": "fr", "filters": filters},
        headers=room(staff),
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
    compare = {"filters": filters, "a_from": JULY_A[0], "a_to": JULY_A[1], "b_from": JULY_B[0], "b_to": JULY_B[1]}
    r = await client.post(
        f"{URL}/export",
        json={"kind": "compare", "format": "pdf", "lang": "ar", "compare": compare},
        headers=room(staff),
    )
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    n = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'window.export' AND details->>'format' IN ('xlsx', 'pdf')")
    )
    assert int(n or 0) >= 2


async def test_now_for_the_room(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    await incident(session, datetime.now(UTC).date().isoformat())
    r = await client.get(f"{URL}/now", headers=room(staff))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["open_total"] >= 1 and body["resources"] is not None and body["progress"] is not None
    assert [p["gouvernorat_code"] for p in body["progress"]] == [NABEUL]


# ---------------------------------------------------------------- delegations


async def axis_with(session: AsyncSession, incident_ids: list[str], code: int = NABEUL) -> str:
    axis_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO crisis.axis (id, number, name, kind, scope, gouvernorat_code, level, opened_by) "
            "VALUES (:id, :n, '[SIM] حرائق نابل', 'forest_fire', 'gouvernorat', :g, 3, 'test')"
        ),
        {"id": axis_id, "n": f"AX-T-{axis_id.hex[:8]}", "g": code},
    )
    for incident_id in incident_ids:
        await session.execute(
            text("INSERT INTO crisis.axis_incident (axis_id, incident_id, attached_by) VALUES (:a, :i, 'test')"),
            {"a": axis_id, "i": incident_id},
        )
    await session.commit()
    return str(axis_id)


async def test_delegation_opens_the_window_on_its_events_only(
    client: httpx.AsyncClient,
    staff: Staff,
    session: AsyncSession,
    directory: FakeDirectory,
    seeded: dict[str, list[str]],
) -> None:
    gov_id = directory.add("gov.nabeul", NABEUL, {"governor"})
    other_id = directory.add("gov.sousse", SOUSSE, {"governor"})
    op_id = directory.add("op.nabeul", NABEUL, {"operator"})
    governor = staff(["governor"], gouvernorat=NABEUL, sub=gov_id)
    params = {"from": JULY_A[0], "to": JULY_A[1]}
    # Without a delegation the governor does not open the window.
    r = await client.get(f"{URL}/search", params=params, headers=governor)
    assert (r.status_code, r.json()["detail"]) == (403, "window_delegation_required")
    assert (await client.get(f"{URL}/access", headers=governor)).json()["delegated"] is False

    r = await client.get(f"{URL}/delegates", headers=room(staff))
    assert {d["id"] for d in r.json()} == {gov_id}
    axis_id = await axis_with(session, seeded["a"][:2])
    ends = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    grant = {"grantee": gov_id, "reason": "[SIM] متابعة حرائق نابل", "ends_at": ends}
    for grantee, code in ((other_id, "delegate_not_allowed"), (op_id, "delegate_not_allowed")):
        r = await client.post(
            f"{URL}/delegations",
            json={**grant, "grantee": grantee, "events": [{"kind": "axis", "id": axis_id}]},
            headers=room(staff),
        )
        assert (r.status_code, r.json()["detail"]) == (422, code)
    r = await client.post(
        f"{URL}/delegations",
        json={**grant, "events": [{"kind": "incident", "id": seeded["sousse"][0]}]},
        headers=room(staff),
    )
    assert (r.status_code, r.json()["detail"]) == (422, "event_out_of_scope")
    r = await client.post(
        f"{URL}/delegations", json={**grant, "events": [{"kind": "axis", "id": axis_id}]}, headers=room(staff)
    )
    assert r.status_code == 201, r.text
    delegation = r.json()
    assert delegation["state"] == "active" and delegation["events"][0]["label"].endswith("[SIM] حرائق نابل")
    # The operator of the room does not delegate.
    r = await client.post(
        f"{URL}/delegations", json={**grant, "events": []}, headers=staff(["operator"], gouvernorat=NABEUL)
    )
    assert r.status_code in (403, 422)

    r = await client.get(f"{URL}/search", params=params, headers=governor)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["delegated"] and sorted(i["id"] for i in body["items"]) == sorted(seeded["a"][:2])
    assert body["figures"]["incidents"] is None  # two interventions: under the floor
    r = await client.get(f"{URL}/now", headers=governor)
    assert r.status_code == 200 and r.json()["resources"] is None and r.json()["progress"] is None
    assert [a["id"] for a in r.json()["axes"]] == [axis_id]
    access_out = (await client.get(f"{URL}/access", headers=governor)).json()
    assert access_out["delegated"] and not access_out["full"] and len(access_out["delegations"]) == 1

    # An event added later, then the delegation withdrawn before its end.
    r = await client.post(
        f"{URL}/delegations/{delegation['id']}/events",
        json={"events": [{"kind": "incident", "id": seeded["a"][5]}]},
        headers=room(staff),
    )
    assert r.status_code == 200 and len(r.json()["events"]) == 2
    r = await client.get(f"{URL}/search", params=params, headers=governor)
    assert len(r.json()["items"]) == 3
    r = await client.post(
        f"{URL}/delegations/{delegation['id']}/revoke", json={"reason": "[SIM] انتهت المتابعة"}, headers=room(staff)
    )
    assert r.status_code == 200 and r.json()["state"] == "revoked"
    assert (await client.get(f"{URL}/search", params=params, headers=governor)).status_code == 403
    # Another gouvernorat's room does not see it.
    r = await client.get(f"{URL}/delegations", params={"include_ended": True}, headers=room(staff, SOUSSE))
    assert delegation["id"] not in {d["id"] for d in r.json()}

    actions = [
        a
        for (a,) in (
            await session.execute(
                text("SELECT action FROM audit.log WHERE target = :t OR details->'delegations' ? :d ORDER BY seq"),
                {"t": f"delegation:{delegation['id']}", "d": delegation["id"]},
            )
        ).all()
    ]
    assert actions[0] == "window.delegation_grant" and "window.delegate_view" in actions
    assert "window.delegation_add" in actions and actions[-1] == "window.delegation_revoke"


# ---------------------------------------------------------------- saved searches and the dictionary


async def test_saved_searches_and_the_dictionary(
    client: httpx.AsyncClient, staff: Staff, seeded: dict[str, list[str]]
) -> None:
    me = room(staff)
    query = {"q": "حريق", "from": JULY_A[0], "to": JULY_A[1]}
    r = await client.post(
        f"{URL}/searches", json={"name": "[SIM] حرائق جويلية", "kind": "search", "query": query}, headers=me
    )
    assert r.status_code == 201, r.text
    saved = r.json()
    assert [s["name"] for s in (await client.get(f"{URL}/searches", headers=me)).json()] == ["[SIM] حرائق جويلية"]
    # Another account sees and deletes nothing of it.
    other = room(staff)
    assert (await client.get(f"{URL}/searches", headers=other)).json() == []
    assert (await client.delete(f"{URL}/searches/{saved['id']}", headers=other)).status_code == 404
    assert (await client.delete(f"{URL}/searches/{saved['id']}", headers=me)).status_code == 204

    words = {"meaning": "fire", "words": ["حريقة", "نار", "شعلة", "لهيب"]}
    assert (await client.post(f"{URL}/synonyms", json=words, headers=me)).status_code == 403
    r = await client.post(f"{URL}/synonyms", json=words, headers=central(staff))
    assert r.status_code == 200, r.text
    r = await client.get(f"{URL}/search", params={"q": "لهيب", "from": JULY_A[0], "to": JULY_A[1]}, headers=me)
    assert r.json()["understood"][0]["kind"] == "category" and r.json()["figures"]["incidents"] == 6
