"""Incidents across gouvernorats (phase 9, docs/api/phase-9-contract.md §5): one incident file with one lead and
participating gouvernorats, the duplicate guard, the command level, field actions kept with the regions, resource
requests between gouvernorats, and the timeline of every step."""

from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import outbox_events
from tests.scopehelpers import (
    KASSERINE,
    REASON,
    SIDI_BOUZID,
    Staff,
    border_points,
    group,
    incident,
    new_report,
    unit_with_resource,
)


async def border_fire(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> tuple[str, dict[str, Any], dict[str, Any], tuple[dict[str, float], dict[str, float]]]:
    """A fire reported on both sides of the Kasserine / Sidi Bouzid border: Kasserine opens the incident, Sidi Bouzid
    links its report to it (found by the nearby-incidents search). Returns (incident id, both reports, points)."""
    k_point, s_point = await border_points(session)
    k_report = await new_report(client, k_point, category="fire")
    s_report = await new_report(client, s_point, category="fire")
    assert (k_report["gouvernorat_code"], s_report["gouvernorat_code"]) == (KASSERINE, SIDI_BOUZID)
    kasserine = staff(gouvernorat=KASSERINE)
    r = await group(client, kasserine, k_report["id"], action="new")
    assert r.status_code == 200, r.text
    incident_id = r.json()["incident_id"]
    sidi_bouzid = staff(gouvernorat=SIDI_BOUZID)
    # Before the link Sidi Bouzid does not read Kasserine's incident, but the search shows its summary.
    assert (await client.get(f"/api/v1/staff/incidents/{incident_id}", headers=sidi_bouzid)).status_code == 404
    r = await client.get(f"/api/v1/staff/reports/{s_report['id']}/nearby-incidents", headers=sidi_bouzid)
    assert r.status_code == 200, r.text
    nearby = {i["id"]: i for i in r.json()}
    assert incident_id in nearby
    assert nearby[incident_id]["lead_gouvernorat_code"] == KASSERINE
    assert "reports" not in nearby[incident_id] and "reporter" not in nearby[incident_id]
    r = await group(client, sidi_bouzid, s_report["id"], action="link", incident_id=incident_id)
    assert r.status_code == 200, r.text
    return incident_id, k_report, s_report, (k_point, s_point)


async def test_one_incident_one_lead(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    incident_id, k_report, s_report, _ = await border_fire(client, staff, session)
    for code in (KASSERINE, SIDI_BOUZID):
        body = await incident(client, staff(gouvernorat=code), incident_id)
        assert body["lead_gouvernorat_code"] == KASSERINE == body["gouvernorat_code"]
        assert body["participating_gouvernorats"] == [SIDI_BOUZID]
        assert {r["id"] for r in body["reports"]} == {k_report["id"], s_report["id"]}
    # A participant changes the command level to central (§5.3).
    assert body["command_level"] == "central"
    # A third room still sees nothing.
    assert (
        await client.get(f"/api/v1/staff/incidents/{incident_id}", headers=staff(gouvernorat=61))
    ).status_code == 404
    rows = (
        await session.execute(
            text("SELECT gouvernorat_code, role FROM ops.incident_gouvernorat WHERE incident_id = :i ORDER BY role"),
            {"i": incident_id},
        )
    ).all()
    assert [(r.gouvernorat_code, r.role) for r in rows] == [(KASSERINE, "lead"), (SIDI_BOUZID, "participating")]


async def test_possible_duplicate(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    incident_id, _, _, (_, s_point) = await border_fire(client, staff, session)
    second = await new_report(client, s_point, category="fire")
    sidi_bouzid = staff(gouvernorat=SIDI_BOUZID)
    r = await group(client, sidi_bouzid, second["id"], action="new")
    assert r.status_code == 409
    assert r.json() == {"detail": "possible_duplicate", "incident_ids": [incident_id]}
    # A competing incident needs a reason, which is audited and kept on the new incident's timeline.
    r = await group(client, sidi_bouzid, second["id"], action="new", override_reason="foyer distinct au nord")
    assert r.status_code == 200, r.text
    other = await incident(client, sidi_bouzid, r.json()["incident_id"])
    override = next(e for e in other["timeline"] if e["kind"] == "duplicate_override")
    assert override["payload"]["reason"] == "foyer distinct au nord"
    assert override["payload"]["incident_ids"] == [incident_id]


async def test_lead_does_not_flip(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    incident_id, _, _, (_, s_point) = await border_fire(client, staff, session)
    sidi_bouzid = staff(gouvernorat=SIDI_BOUZID)
    for _ in range(3):
        report = await new_report(client, s_point, category="fire")
        r = await group(client, sidi_bouzid, report["id"], action="link", incident_id=incident_id)
        assert r.status_code == 200, r.text
    body = await incident(client, sidi_bouzid, incident_id)
    # Four Sidi Bouzid reports against one from Kasserine: the lead stays Kasserine (no majority rule any more).
    assert body["lead_gouvernorat_code"] == KASSERINE
    # Only the national room transfers the lead; the old lead becomes participating.
    url = f"/api/v1/staff/incidents/{incident_id}/lead"
    r = await client.post(url, json={"gouvernorat_code": SIDI_BOUZID, "reason": REASON}, headers=sidi_bouzid)
    assert r.status_code == 403
    manager = staff(["ops_manager"], gouvernorat=None, name="Hela Mansour")
    r = await client.post(url, json={"gouvernorat_code": 99, "reason": REASON}, headers=manager)
    assert (r.status_code, r.json()["detail"]) == (422, "invalid_gouvernorat")
    r = await client.post(url, json={"gouvernorat_code": SIDI_BOUZID, "reason": REASON}, headers=manager)
    assert r.status_code == 200, r.text
    assert (r.json()["lead_gouvernorat_code"], r.json()["participating_gouvernorats"]) == (SIDI_BOUZID, [KASSERINE])
    transfer = next(e for e in r.json()["timeline"] if e["kind"] == "lead_transferred")
    assert transfer["actor"] == "Hela Mansour" and transfer["payload"]["reason"] == REASON


async def test_participants_and_command_level(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    incident_id, _, _, _ = await border_fire(client, staff, session)
    lead_manager = staff(["ops_manager"], gouvernorat=KASSERINE)
    url = f"/api/v1/staff/incidents/{incident_id}/participants"
    r = await client.post(url, json={"gouvernorat_code": 41, "reason": REASON}, headers=lead_manager)
    assert r.status_code == 200, r.text
    assert sorted(r.json()["participating_gouvernorats"]) == [41, SIDI_BOUZID]
    # A participating room does not manage participants; a gouvernorat with member reports cannot be removed.
    r = await client.post(
        url, json={"gouvernorat_code": 40, "reason": REASON}, headers=staff(["ops_manager"], gouvernorat=SIDI_BOUZID)
    )
    assert r.status_code == 403
    r = await client.request("DELETE", f"{url}/{SIDI_BOUZID}", json={"reason": REASON}, headers=lead_manager)
    assert (r.status_code, r.json()["detail"]) == (409, "participant_active")
    r = await client.request("DELETE", f"{url}/41", json={"reason": REASON}, headers=lead_manager)
    assert r.status_code == 200 and r.json()["participating_gouvernorats"] == [SIDI_BOUZID]
    # Command level: national only, manual until set back to automatic.
    level = f"/api/v1/staff/incidents/{incident_id}/command-level"
    assert (
        await client.post(level, json={"level": "regional", "reason": REASON}, headers=lead_manager)
    ).status_code == 403
    committee = staff(["central_committee"], gouvernorat=None)
    r = await client.post(level, json={"level": "regional", "reason": REASON}, headers=committee)
    assert r.status_code == 200, r.text
    assert (r.json()["command_level"], r.json()["command_level_manual"]) == ("regional", True)
    r = await client.post(level, json={"level": None, "reason": REASON}, headers=committee)
    assert (r.json()["command_level"], r.json()["command_level_manual"]) == ("central", False)
    kinds = [e["kind"] for e in r.json()["timeline"]]
    assert {"participant_added", "participant_removed", "command_level_changed"} <= set(kinds)


async def test_national_cannot_dispatch(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    incident_id, _, _, (k_point, _) = await border_fire(client, staff, session)
    resource = await unit_with_resource(client, staff, KASSERINE, k_point)
    for role in ("operator", "ops_manager"):
        national = staff([role], gouvernorat=None)
        r = await client.post(
            f"/api/v1/staff/incidents/{incident_id}/assignments", json={"resource_id": resource["id"]}, headers=national
        )
        assert (r.status_code, r.json()["detail"]) == (403, "field_action_regional_only")
        r = await client.post(
            f"/api/v1/staff/incidents/{incident_id}/callouts",
            json={"skill": "first_aid", "requested": 1},
            headers=national,
        )
        assert (r.status_code, r.json()["detail"]) == (403, "field_action_regional_only")
    # The lead room dispatches its own resource.
    r = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/assignments",
        json={"resource_id": resource["id"]},
        headers=staff(gouvernorat=KASSERINE),
    )
    assert r.status_code in {200, 201}, r.text


async def test_resource_not_owned(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    incident_id, _, _, (_, s_point) = await border_fire(client, staff, session)
    other = await unit_with_resource(client, staff, SIDI_BOUZID, s_point)
    r = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/assignments",
        json={"resource_id": other["id"]},
        headers=staff(gouvernorat=KASSERINE),
    )
    assert (r.status_code, r.json()["detail"]) == (403, "resource_not_owned")


async def test_resource_request_approved_refused_and_central(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    incident_id, _, _, (_, s_point) = await border_fire(client, staff, session)
    engine = await unit_with_resource(client, staff, SIDI_BOUZID, s_point)
    kasserine = staff(gouvernorat=KASSERINE, name="Amine Kasserine")
    url = f"/api/v1/staff/incidents/{incident_id}/resource-requests"
    body = {"to_gouvernorat_code": SIDI_BOUZID, "resource_kind": "fire_engine", "quantity": 1, "reason": REASON}
    r = await client.post(url, json=body, headers=kasserine)
    assert r.status_code == 201, r.text
    request = r.json()
    assert (request["status"], request["from_room"]) == ("pending", f"g:{KASSERINE}")
    # Incoming for Sidi Bouzid, outgoing for Kasserine, invisible to a third room.
    sb_manager = staff(["ops_manager"], gouvernorat=SIDI_BOUZID, name="Rania Sidi Bouzid")
    incoming = await client.get("/api/v1/staff/resource-requests", params={"direction": "incoming"}, headers=sb_manager)
    assert request["id"] in {i["id"] for i in incoming.json()["items"]}
    outgoing = await client.get("/api/v1/staff/resource-requests", params={"direction": "outgoing"}, headers=kasserine)
    assert request["id"] in {i["id"] for i in outgoing.json()["items"]}
    assert (
        await client.get(f"/api/v1/staff/resource-requests/{request['id']}", headers=staff(gouvernorat=61))
    ).status_code == 404
    # The requester cannot approve its own request; the owning region does.
    approve = f"/api/v1/staff/resource-requests/{request['id']}/approve"
    r = await client.post(
        approve, json={"resource_ids": [engine["id"]]}, headers=staff(["ops_manager"], gouvernorat=KASSERINE)
    )
    assert r.status_code == 403
    r = await client.post(approve, json={"resource_ids": [engine["id"]], "note": "en route"}, headers=sb_manager)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"
    assignment = (
        await session.execute(
            text("SELECT status, request_id FROM ops.assignment WHERE incident_id = :i AND resource_id = :r"),
            {"i": incident_id, "r": engine["id"]},
        )
    ).one()
    assert (assignment.status, str(assignment.request_id)) == ("ordered", request["id"])
    r = await client.post(approve, json={"resource_ids": [engine["id"]]}, headers=sb_manager)
    assert (r.status_code, r.json()["detail"]) == (409, "request_not_pending")
    # A second request refused with its reason.
    r = await client.post(url, json=body, headers=kasserine)
    refused = await client.post(
        f"/api/v1/staff/resource-requests/{r.json()['id']}/refuse",
        json={"reason": "plus de moyens"},
        headers=sb_manager,
    )
    assert refused.status_code == 200 and refused.json()["status"] == "refused"
    # Central command level: the central committee decides a pending request.
    r = await client.post(url, json=body, headers=kasserine)
    committee = staff(["central_committee"], gouvernorat=None)
    second_engine = await unit_with_resource(client, staff, SIDI_BOUZID, s_point)
    r = await client.post(
        f"/api/v1/staff/resource-requests/{r.json()['id']}/approve",
        json={"resource_ids": [second_engine["id"]]},
        headers=committee,
    )
    assert r.status_code == 200, r.text
    detail = await incident(client, kasserine, incident_id)
    entries = {e["kind"]: e for e in detail["timeline"]}
    assert {"resource_requested", "resource_request_approved", "resource_request_refused"} <= set(entries)
    assert entries["resource_request_refused"]["payload"]["reason"] == "plus de moyens"
    assert entries["resource_request_refused"]["actor"] == "Rania Sidi Bouzid"
    assert len(detail["resource_requests"]) == 3


async def test_timeline_entries_have_actor_reason(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    incident_id, _, _, _ = await border_fire(client, staff, session)
    detail = await incident(client, staff(gouvernorat=None), incident_id)
    added = next(e for e in detail["timeline"] if e["kind"] == "participant_added")
    assert added["actor"] and added["at"]
    assert added["payload"]["gouvernorat_code"] == SIDI_BOUZID and added["payload"]["reason"] == "report_linked"
    for entry in detail["timeline"]:
        assert entry["actor"] and entry["at"], entry


async def test_live_payload_carries_gouvernorat_codes(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    incident_id, _, _, _ = await border_fire(client, staff, session)
    events = await outbox_events(session, "incident.updated")
    mine = [e for e in events if e.get("incident", {}).get("id") == incident_id]
    assert mine, events[-3:]
    assert set(mine[-1]["gouvernorat_codes"]) >= {KASSERINE, SIDI_BOUZID}
