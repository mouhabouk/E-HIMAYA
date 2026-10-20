"""Report jurisdiction (phase 9, docs/api/phase-9-contract.md §4): location assessment, geo-verification queue, claim,
reporter context. The incident's location decides who handles a report, never the reporter's residence."""

from collections.abc import Callable
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports import geo
from tests.conftest import SFAX, TokenFactory, accept_charter, bearer, device_headers, report_body
from tests.test_profile import random_cin

Staff = Callable[..., dict[str, str]]

GABES = {"lat": 33.8815, "lon": 10.0982, "accuracy_m": 10.0}
# Inside Kasserine (42), 400 m from Sidi Bouzid (43).
BORDER = {"lat": 34.94311, "lon": 9.03255}
OFFSHORE = {"lat": 34.70, "lon": 10.86, "accuracy_m": 10.0}


async def new_report(
    client: httpx.AsyncClient, location: dict[str, float], headers: dict[str, str] | None = None, **overrides: Any
) -> dict[str, Any]:
    if headers is None:
        headers = device_headers()
        await accept_charter(client, headers)
    r = await client.post("/api/v1/reports", json=report_body(location, **overrides), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def detail(client: httpx.AsyncClient, headers: dict[str, str], report_id: str) -> httpx.Response:
    return await client.get(f"/api/v1/staff/reports/{report_id}", headers=headers)


async def claim(client: httpx.AsyncClient, headers: dict[str, str], report_id: str) -> httpx.Response:
    return await client.post(f"/api/v1/staff/reports/{report_id}/claim", headers=headers)


async def listed(client: httpx.AsyncClient, headers: dict[str, str], report_id: str, **params: Any) -> bool:
    r = await client.get("/api/v1/staff/reports", params={"limit": 500, **params}, headers=headers)
    assert r.status_code == 200, r.text
    return report_id in {i["id"] for i in r.json()["items"]}


async def citizen_of(client: httpx.AsyncClient, make_token: TokenFactory, gouvernorat: int, delegation: int) -> Any:
    headers = bearer(make_token(roles=["citizen"]))
    profile = {
        "first_name": "Sami",
        "last_name": "Gharbi",
        "cin": random_cin(),
        "phone": "+21697000112",
        "gouvernorat_code": gouvernorat,
        "delegation_id": delegation,
        "locale": "fr",
    }
    assert (await client.put("/api/v1/me/profile", json=profile, headers=headers)).status_code == 200
    await accept_charter(client, headers)
    return headers


# ---------------------------------------------------------------- assessment


@pytest.mark.parametrize(
    ("point", "accuracy", "source", "expected"),
    [
        (SFAX, 8.0, "app", ("trusted", 61, [], None)),
        (BORDER, 100.0, "app", ("trusted", 42, [], None)),
        (BORDER, 600.0, "app", ("contradictory", None, [42, 43], "accuracy_crosses_border")),
        (OFFSHORE, 10.0, "app", ("pending", None, [61], "outside_boundaries")),
        (SFAX, 5000.0, "app", ("pending", None, [61], "low_accuracy")),
        (SFAX, None, "app", ("pending", None, [61], "accuracy_missing")),
        (SFAX, None, "portal", ("trusted", 61, [], None)),
        (OFFSHORE, None, "portal", ("pending", None, [61], "outside_boundaries")),
    ],
)
async def test_assessment_cases(
    session: AsyncSession, point: dict[str, float], accuracy: float | None, source: str, expected: tuple[Any, ...]
) -> None:
    found = await geo.assess(session, point["lat"], point["lon"], accuracy, source)
    assert (found.state, found.gouvernorat_code, found.candidates, found.reason) == expected


async def test_tracking_code_keeps_phase_2_format(session: AsyncSession) -> None:
    offshore = await geo.assess(session, OFFSHORE["lat"], OFFSHORE["lon"], 10.0, "app")
    assert offshore.tracking_gouvernorat == 61
    crossing = await geo.assess(session, BORDER["lat"], BORDER["lon"], 600.0, "app")
    assert crossing.tracking_gouvernorat == 42


async def test_null_gouvernorat_for_pending(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    report = await new_report(client, {"lat": SFAX["lat"], "lon": SFAX["lon"]})
    assert report["gouvernorat_code"] is None and report["tracking_code"].split("-")[2] == "61"
    sfax = staff(gouvernorat=61)
    # Not critical: national only until verified.
    assert (await detail(client, sfax, report["id"])).status_code == 404
    assert not await listed(client, sfax, report["id"])
    national = staff(gouvernorat=None)
    body = (await detail(client, national, report["id"])).json()
    assert (body["geo_state"], body["geo_candidates"], body["gouvernorat_code"]) == ("pending", [61], None)


async def test_pending_goes_to_queue(client: httpx.AsyncClient, staff: Staff) -> None:
    pending = await new_report(client, {"lat": SFAX["lat"], "lon": SFAX["lon"]}, category="fire")
    critical = await new_report(client, {"lat": SFAX["lat"], "lon": SFAX["lon"]}, category="sos", text=None)
    trusted = await new_report(client, SFAX)
    national = staff(gouvernorat=None)
    r = await client.get("/api/v1/staff/reports/geo-queue", params={"limit": 500}, headers=national)
    assert r.status_code == 200, r.text
    ids = [i["id"] for i in r.json()["items"]]
    assert pending["id"] in ids and critical["id"] in ids and trusted["id"] not in ids
    # Critical first.
    assert ids.index(critical["id"]) < ids.index(pending["id"])
    # Pagination keeps the order.
    first = (await client.get("/api/v1/staff/reports/geo-queue", params={"limit": 1}, headers=national)).json()
    assert first["next_cursor"]
    second = await client.get(
        "/api/v1/staff/reports/geo-queue", params={"limit": 1, "cursor": first["next_cursor"]}, headers=national
    )
    assert second.status_code == 200 and second.json()["items"][0]["id"] != first["items"][0]["id"]
    # National queue only.
    r = await client.get("/api/v1/staff/reports/geo-queue", headers=staff(gouvernorat=61))
    assert (r.status_code, r.json()["detail"]) == (403, "national_scope_required")
    # Filters on the normal list.
    assert await listed(client, national, pending["id"], geo_state="pending,contradictory")
    assert not await listed(client, national, trusted["id"], geo_state="pending")
    assert (await client.get("/api/v1/staff/reports?geo_state=bogus", headers=national)).status_code == 422


async def test_critical_pending_visible_to_candidates(client: httpx.AsyncClient, staff: Staff) -> None:
    crossing = {**BORDER, "accuracy_m": 600.0}
    fire = await new_report(client, crossing, category="fire")
    sos = await new_report(client, crossing, category="sos", text=None)
    kasserine, sidi_bouzid, sfax = staff(gouvernorat=42), staff(gouvernorat=43), staff(gouvernorat=61)
    for room in (kasserine, sidi_bouzid):
        assert (await detail(client, room, fire["id"])).status_code == 404
        assert not await listed(client, room, fire["id"])
        assert (await detail(client, room, sos["id"])).status_code == 200
        assert await listed(client, room, sos["id"])
    assert (await detail(client, sfax, sos["id"])).status_code == 404
    assert not await listed(client, sfax, sos["id"])
    # A candidate room may claim the critical report so it is not delayed by the verification.
    r = await claim(client, kasserine, sos["id"])
    assert r.status_code == 200, r.text
    assert r.json()["claimed_room"] == "g:42"
    r = await claim(client, kasserine, fire["id"])
    assert r.status_code == 404


async def test_geo_verify_refers(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    sos = await new_report(client, {**BORDER, "accuracy_m": 600.0}, category="sos", text=None)
    kasserine, sidi_bouzid = staff(gouvernorat=42), staff(gouvernorat=43)
    assert (await claim(client, kasserine, sos["id"])).status_code == 200
    url = f"/api/v1/staff/reports/{sos['id']}/geo-verify"
    # Regional rooms cannot verify; national committees and operations can.
    r = await client.post(url, json={"gouvernorat_code": 43, "reason": "appel du témoin"}, headers=kasserine)
    assert (r.status_code, r.json()["detail"]) == (403, "action_not_allowed")
    verifier = staff(["central_committee"], gouvernorat=None, name="Hela Mansour")
    r = await client.post(url, json={"gouvernorat_code": 99, "reason": "appel du témoin"}, headers=verifier)
    assert (r.status_code, r.json()["detail"]) == (422, "invalid_gouvernorat")
    r = await client.post(url, json={"gouvernorat_code": 43, "reason": "appel du témoin"}, headers=verifier)
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["geo_state"], body["gouvernorat_code"], body["escalation_state"]) == ("verified", 43, "referred")
    assert [(e["kind"], e["to_room"], e["actor_name"]) for e in body["escalations"]] == [
        ("geo_verified", "g:43", "Hela Mansour"),
        ("referral", "g:43", "Hela Mansour"),
    ]
    assert all(e["reason"] == "appel du témoin" and e["at"] for e in body["escalations"])
    r = await client.post(url, json={"gouvernorat_code": 42, "reason": "deuxième avis"}, headers=verifier)
    assert (r.status_code, r.json()["detail"]) == (409, "geo_not_pending")
    # The verified room accepts and takes the claim over from the candidate room.
    accepted = await client.post(
        f"/api/v1/staff/reports/{sos['id']}/referral/accept", json={"note": "équipe en route"}, headers=sidi_bouzid
    )
    assert accepted.status_code == 200, accepted.text
    assert (accepted.json()["claimed_room"], accepted.json()["escalation_state"]) == ("g:43", "referral_accepted")
    audited = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'report.geo_verify' AND target = :t"),
        {"t": f"report:{sos['id']}"},
    )
    assert audited == 1


async def test_geo_verify_without_claim_does_not_refer(client: httpx.AsyncClient, staff: Staff) -> None:
    report = await new_report(client, OFFSHORE, category="drowning")
    national = staff(gouvernorat=None)
    r = await client.post(
        f"/api/v1/staff/reports/{report['id']}/geo-verify",
        json={"gouvernorat_code": 61, "reason": "au large de Sfax"},
        headers=national,
    )
    assert r.status_code == 200, r.text
    assert r.json()["escalation_state"] == "none" and [e["kind"] for e in r.json()["escalations"]] == ["geo_verified"]
    # Now an ordinary Sfax report.
    assert (await detail(client, staff(gouvernorat=61), report["id"])).status_code == 200


# ---------------------------------------------------------------- reporter elsewhere


async def test_reporter_elsewhere_location_decides(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory
) -> None:
    """A Sfax resident reports a fire in Gabès: Gabès handles it, Sfax does not even see it."""
    resident = await citizen_of(client, make_token, 61, 6101)
    report = await new_report(client, GABES, headers=resident)
    assert report["gouvernorat_code"] == 81
    sfax, gabes = staff(gouvernorat=61), staff(gouvernorat=81)
    assert (await detail(client, sfax, report["id"])).status_code == 404
    assert not await listed(client, sfax, report["id"])
    assert (await claim(client, sfax, report["id"])).status_code == 404
    assert (await claim(client, gabes, report["id"])).status_code == 200
    body = (await detail(client, gabes, report["id"])).json()
    assert body["reporter_context"] == {"reporter_gouvernorat_code": 61, "source": "profile"}
    assert body["reporter"]["first_name"] == "Sami"


async def test_reporter_context_restricted(client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory) -> None:
    resident = await citizen_of(client, make_token, 61, 6101)
    report = await new_report(client, GABES, headers=resident)
    gabes = staff(gouvernorat=81)
    for headers in (
        gabes,
        staff(["field_commander"], gouvernorat=81),
        staff(["local_committee"], gouvernorat=81),
        staff(gouvernorat=None),
        staff(["central_committee"], gouvernorat=None),
    ):
        body = (await detail(client, headers, report["id"])).json()
        assert body["reporter_context"] is None
        assert body["reporter"]["masked"] is True and body["reporter"]["phone"] == "+216••••••12"
    assert (await claim(client, gabes, report["id"])).status_code == 200
    for headers in (staff(["field_commander"], gouvernorat=81), staff(gouvernorat=None)):
        assert (await detail(client, headers, report["id"])).json()["reporter_context"] is None
    anonymous = await new_report(client, GABES)
    assert (await claim(client, gabes, anonymous["id"])).status_code == 200
    body = (await detail(client, gabes, anonymous["id"])).json()
    assert body["reporter_context"] == {"reporter_gouvernorat_code": None, "source": "none"}


# ---------------------------------------------------------------- claim


async def test_claim_idempotent_and_conflict(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    report = await new_report(client, SFAX)
    first = staff(gouvernorat=61, name="Rim Ayari")
    r = await claim(client, first, report["id"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["claimed_room"], body["claimed_by_name"]) == ("g:61", "Rim Ayari") and body["claimed_at"]
    # Same room again (another operator of the room): unchanged.
    again = await claim(client, staff(gouvernorat=61), report["id"])
    assert again.status_code == 200 and again.json()["claimed_by_name"] == "Rim Ayari"
    claims = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'report.claim' AND target = :t"),
        {"t": f"report:{report['id']}"},
    )
    assert claims == 1
    # Another room: 409 naming the holder.
    other = await claim(client, staff(gouvernorat=None), report["id"])
    assert other.status_code == 409
    assert other.json() == {"detail": "already_claimed", "claimed_room": "g:61", "claimed_by_name": "Rim Ayari"}
    status = await client.post(
        f"/api/v1/staff/reports/{report['id']}/status", json={"status": "in_progress"}, headers=staff(gouvernorat=None)
    )
    assert status.status_code == 409 and status.json()["detail"] == "already_claimed"
    # Claimed filter.
    assert await listed(client, first, report["id"], claimed="true")
    assert not await listed(client, first, report["id"], claimed="false")


async def test_implicit_claim_on_status(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    report = await new_report(client, SFAX)
    url = f"/api/v1/staff/reports/{report['id']}/status"
    # The central room may not take a fresh regional report.
    r = await client.post(url, json={"status": "in_progress"}, headers=staff(gouvernorat=None))
    assert (r.status_code, r.json()["detail"]) == (409, "claim_required")
    r = await client.post(url, json={"status": "in_progress"}, headers=staff(["field_commander"], gouvernorat=61))
    assert (r.status_code, r.json()["detail"]) == (403, "action_not_allowed")
    r = await client.post(url, json={"status": "in_progress"}, headers=staff(gouvernorat=61))
    assert r.status_code == 200, r.text
    assert r.json()["claimed_room"] == "g:61" and r.json()["status"] == "in_progress"
    details = await session.scalar(
        text("SELECT details FROM audit.log WHERE action = 'report.claim' AND target = :t"),
        {"t": f"report:{report['id']}"},
    )
    assert details["implicit"] is True and details["room"] == "g:61"


async def test_release(client: httpx.AsyncClient, staff: Staff) -> None:
    report = await new_report(client, SFAX)
    claimed = await claim(client, staff(gouvernorat=61), report["id"])
    assert claimed.status_code == 200
    url = f"/api/v1/staff/reports/{report['id']}/claim"
    body = {"reason": "mauvais secteur"}
    r = await client.request("DELETE", url, json=body, headers=staff(gouvernorat=61))
    assert (r.status_code, r.json()["detail"]) == (403, "action_not_allowed")
    r = await client.request("DELETE", url, json=body, headers=staff(["ops_manager"], gouvernorat=11))
    assert r.status_code == 404
    r = await client.request("DELETE", url, json={"reason": "x"}, headers=staff(["ops_manager"], gouvernorat=61))
    assert r.status_code == 422
    r = await client.request("DELETE", url, json=body, headers=staff(["ops_manager"], gouvernorat=61, name="Ali Ben"))
    assert r.status_code == 200, r.text
    released = r.json()
    assert released["claimed_room"] is None
    assert [(e["kind"], e["from_room"], e["actor_name"], e["reason"]) for e in released["escalations"]] == [
        ("claim_released", "g:61", "Ali Ben", "mauvais secteur")
    ]
    # The SLA clock does not restart.
    assert released["sla_due_at"] == claimed.json()["sla_due_at"]
    r = await client.request("DELETE", url, json=body, headers=staff(["ops_manager"], gouvernorat=61))
    assert (r.status_code, r.json()["detail"]) == (409, "not_claimed")


async def test_committee_cannot_triage(client: httpx.AsyncClient, staff: Staff) -> None:
    report = await new_report(client, SFAX)
    for roles in (["local_committee"], ["central_committee"]):
        headers = staff(roles, gouvernorat=61)
        assert (await claim(client, headers, report["id"])).status_code == 403
        r = await client.post(
            f"/api/v1/staff/reports/{report['id']}/status", json={"status": "in_progress"}, headers=headers
        )
        assert r.status_code == 403
