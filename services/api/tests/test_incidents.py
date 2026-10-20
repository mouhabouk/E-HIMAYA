"""Grouping reports into incidents (FR-C-02, BR-10, BR-11): suggestions, confirm, split, merge, scope."""

import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.aihelpers import FakeAi, Staff, analyse, create, detail, spot
from tests.conftest import TUNIS, TokenFactory, accept_charter, bearer, outbox_events

pytestmark = pytest.mark.usefixtures("isolated_window")


async def reporter(client: httpx.AsyncClient, make_token: TokenFactory) -> dict[str, str]:
    headers = bearer(make_token(roles=["citizen"]))
    await accept_charter(client, headers)
    return headers


async def link(client: httpx.AsyncClient, headers: dict[str, str], report_id: str, **body: Any) -> httpx.Response:
    return await client.post(f"/api/v1/staff/reports/{report_id}/incident", json=body, headers=headers)


async def test_nearby_reports_of_the_same_event_are_suggested_and_corroborate(
    client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff
) -> None:
    here = spot()
    base = (here["lat"], here["lon"])
    first = await create(client, await reporter(client, make_token), location=here, text="نار في غابة")
    second = await create(client, await reporter(client, make_token), location=spot(base, east_m=150), text="حريق")
    far = await create(client, await reporter(client, make_token), location=spot(base, east_m=3000), text="حريق")
    flood = await create(client, await reporter(client, make_token), category="flood", location=spot(base, east_m=100))

    d = await detail(client, staff, second["id"])
    suggestion = d["analysis"]["suggestion"]
    assert d["has_suggestion"] and suggestion["kind"] == "report" and suggestion["report_id"] == first["id"]
    assert suggestion["reasons"] == ["same_category", "within_radius", "within_window"]
    assert 100 < suggestion["distance_m"] < 200
    credibility = {c["key"]: c for c in d["analysis"]["credibility"]["components"]}
    assert credibility["corroborated"]["detail"]["reporters"] == 1
    reporters = next(c for c in d["analysis"]["priority"]["components"] if c["key"] == "reporters")
    assert reporters["detail"]["reporters"] == 2

    # 3 km away is another event; a flood next door is another type (BR-10).
    assert (await detail(client, staff, far["id"]))["analysis"]["suggestion"] is None
    assert (await detail(client, staff, flood["id"]))["analysis"]["suggestion"] is None

    # The earlier report learns about the corroboration once the later one has been analysed.
    assert await analyse(second["id"], None)
    earlier = await detail(client, staff, first["id"])
    assert any(c["key"] == "corroborated" for c in earlier["analysis"]["credibility"]["components"])


async def test_semantically_close_reports_are_suggested(
    client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff, fake_ai: FakeAi
) -> None:
    here = spot()
    base = (here["lat"], here["lon"])
    a = await create(
        client, await reporter(client, make_token), category="chemical_leak", location=here, text="odeur de gaz toxique"
    )
    b = await create(
        client, await reporter(client, make_token), category="other", location=spot(base, east_m=2500), text="ريحة غاز"
    )
    assert (await detail(client, staff, b["id"]))["analysis"]["suggestion"] is None
    assert await analyse(a["id"], fake_ai) and await analyse(b["id"], fake_ai)
    suggestion = (await detail(client, staff, b["id"]))["analysis"]["suggestion"]
    assert suggestion is not None and suggestion["report_id"] == a["id"]
    assert suggestion["reasons"] == ["similar_content"] and suggestion["similarity"] == 1.0


async def test_confirm_split_and_dissolve(
    client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff, session: AsyncSession
) -> None:
    here = spot()
    base = (here["lat"], here["lon"])
    first = await create(client, await reporter(client, make_token), location=here)
    second = await create(client, await reporter(client, make_token), location=spot(base, east_m=120))
    operator = staff(gouvernorat=61)

    r = await link(client, operator, second["id"], action="accept_suggestion")
    assert r.status_code == 200, r.text
    incident_id = r.json()["incident_id"]
    assert incident_id and r.json()["analysis"]["suggestion"] is None
    incident = (await client.get(f"/api/v1/staff/incidents/{incident_id}", headers=operator)).json()
    assert {x["id"] for x in incident["reports"]} == {first["id"], second["id"]}
    assert incident["report_count"] == 2 and incident["reporter_count"] == 2 and incident["status"] == "open"
    assert incident["category"] == "fire" and incident["gouvernorat_code"] == 61
    assert abs(incident["centroid"]["lat"] - here["lat"]) < 0.01
    assert [e["kind"] for e in incident["timeline"]] == ["created", "report_linked", "report_linked"]
    assert incident["severity"] == max(x["priority_score"] for x in incident["reports"])

    # A third report nearby is now suggested the incident itself.
    third = await create(client, await reporter(client, make_token), location=spot(base, east_m=60))
    suggestion = (await detail(client, staff, third["id"]))["analysis"]["suggestion"]
    assert suggestion["kind"] == "incident" and suggestion["incident_id"] == incident_id
    assert suggestion["matching_reports"] == 2
    assert (await link(client, operator, third["id"], action="accept_suggestion")).json()["incident_id"] == incident_id

    listed = (await client.get("/api/v1/staff/incidents", headers=operator)).json()["items"]
    assert next(i for i in listed if i["id"] == incident_id)["report_count"] == 3

    # Split: detach reports one by one; an empty incident is dissolved.
    for report in (third, second, first):
        r = await client.delete(f"/api/v1/staff/reports/{report['id']}/incident", headers=operator)
        assert r.status_code == 200 and r.json()["incident_id"] is None
    incident = (await client.get(f"/api/v1/staff/incidents/{incident_id}", headers=operator)).json()
    assert incident["status"] == "dissolved" and incident["report_count"] == 0
    assert (await client.delete(f"/api/v1/staff/reports/{first['id']}/incident", headers=operator)).status_code == 409

    audited = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action IN ('incident.link', 'incident.unlink') AND target = :t"),
        {"t": f"report:{second['id']}"},
    )
    assert audited == 2
    updates = [e for e in await outbox_events(session, "incident.updated") if e["incident"]["id"] == incident_id]
    assert len(updates) >= 5


async def test_new_link_and_merge(client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff) -> None:
    operator = staff(gouvernorat=61)
    a = await create(client, await reporter(client, make_token), location=spot())
    b = await create(client, await reporter(client, make_token), location=spot())
    c = await create(client, await reporter(client, make_token), location=spot())
    first = (await link(client, operator, a["id"], action="new")).json()["incident_id"]
    second = (await link(client, operator, b["id"], action="new")).json()["incident_id"]
    r = await link(client, operator, c["id"], action="link", incident_id=first)
    assert r.json()["incident_id"] == first
    assert (await link(client, operator, c["id"], action="link")).status_code == 422
    assert (await link(client, operator, c["id"], action="accept_suggestion")).status_code == 409

    # Merging is a lead-room decision (phase 9 §1.2): the operator is refused, the room's ops manager merges.
    r = await client.post(f"/api/v1/staff/incidents/{first}/merge", json={"incident_id": second}, headers=operator)
    assert r.status_code == 403
    manager = staff(roles=["ops_manager"], gouvernorat=61)
    r = await client.post(f"/api/v1/staff/incidents/{first}/merge", json={"incident_id": second}, headers=manager)
    assert r.status_code == 200, r.text
    assert {x["id"] for x in r.json()["reports"]} == {a["id"], b["id"], c["id"]}
    merged = (await client.get(f"/api/v1/staff/incidents/{second}", headers=operator)).json()
    assert merged["status"] == "merged" and merged["merged_into"] == first
    assert (await link(client, operator, a["id"], action="link", incident_id=second)).status_code == 409
    again = await client.post(f"/api/v1/staff/incidents/{first}/merge", json={"incident_id": first}, headers=manager)
    assert again.status_code == 422


async def test_dismissed_suggestion_is_not_proposed_again(
    client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff
) -> None:
    here = spot()
    await create(client, await reporter(client, make_token), location=here)
    second = await create(
        client, await reporter(client, make_token), location=spot((here["lat"], here["lon"]), east_m=50)
    )
    operator = staff(gouvernorat=61)
    r = await client.post(f"/api/v1/staff/reports/{second['id']}/suggestion/dismiss", headers=operator)
    assert r.status_code == 200 and r.json()["analysis"]["suggestion"] is None and not r.json()["has_suggestion"]
    assert await analyse(second["id"], None)
    assert (await detail(client, staff, second["id"]))["analysis"]["suggestion"] is None
    again = await client.post(f"/api/v1/staff/reports/{second['id']}/suggestion/dismiss", headers=operator)
    assert again.status_code == 409


async def test_incident_closes_when_all_its_reports_are_closed(
    client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff
) -> None:
    operator = staff(gouvernorat=61)
    a = await create(client, await reporter(client, make_token), location=spot())
    b = await create(client, await reporter(client, make_token), location=spot())
    incident_id = (await link(client, operator, a["id"], action="new")).json()["incident_id"]
    await link(client, operator, b["id"], action="link", incident_id=incident_id)
    for report_id, path in ((a["id"], ("in_progress", "closed")), (b["id"], ("rejected",))):
        for target in path:
            r = await client.post(
                f"/api/v1/staff/reports/{report_id}/status", json={"status": target}, headers=operator
            )
            assert r.status_code == 200, r.text
    incident = (await client.get(f"/api/v1/staff/incidents/{incident_id}", headers=operator)).json()
    assert incident["status"] == "closed" and incident["closed_at"] is not None
    assert incident["timeline"][-1]["kind"] == "closed"
    assert (await client.get("/api/v1/staff/incidents?status=bogus", headers=operator)).status_code == 422


async def test_incidents_respect_scope_and_roles(
    client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff
) -> None:
    tunis_reporter = await reporter(client, make_token)
    in_tunis = await create(client, tunis_reporter, location=TUNIS)
    in_sfax = await create(client, await reporter(client, make_token), location=spot())
    tunis_incident = (await link(client, staff(gouvernorat=11), in_tunis["id"], action="new")).json()["incident_id"]

    sfax_operator = staff(gouvernorat=61)
    assert (await client.get(f"/api/v1/staff/incidents/{tunis_incident}", headers=sfax_operator)).status_code == 404
    r = await link(client, sfax_operator, in_sfax["id"], action="link", incident_id=tunis_incident)
    assert r.status_code == 404
    assert (await link(client, sfax_operator, in_tunis["id"], action="new")).status_code == 404
    listed = (await client.get("/api/v1/staff/incidents", headers=sfax_operator)).json()["items"]
    assert tunis_incident not in {i["id"] for i in listed}

    committee = staff(roles=["local_committee"], gouvernorat=61)
    assert (await link(client, committee, in_sfax["id"], action="new")).status_code == 403
    assert (await client.get("/api/v1/staff/incidents", headers=committee)).status_code == 200
    assert (await link(client, sfax_operator, str(uuid.uuid4()), action="new")).status_code == 404
