# covers: FR-B-008
"""Prevention certificate and the institution's reports, phase P3b: request or scheduled visit, on-site inspection,
automatic comparison report, decision with reservations and deadlines, the [SIM] certificate, the annual report
(docs/phase-p3/design-prevention.md)."""

import uuid
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orgs import domain
from tests.conftest import FakeStore, TokenFactory, bearer
from tests.test_orgs import active_org, add_member, complete, signing_key  # noqa: F401  (signing_key is a fixture)

Staff = Callable[..., dict[str, str]]
User = Callable[..., dict[str, str]]

pytestmark = pytest.mark.usefixtures("signing_key")
TODAY = date.today()


@pytest.fixture
def user(make_token: TokenFactory) -> User:
    def _user(email: str | None = None) -> dict[str, str]:
        email = email or f"u{uuid.uuid4().hex[:10]}@example.tn"
        token = make_token(roles=["citizen"], email=email, email_verified=True, name=f"User {email.split('@')[0]}")
        return bearer(token)

    return _user


def auditor(staff: Staff, gouvernorat: int = 61) -> dict[str, str]:
    return staff(["org_auditor"], gouvernorat=gouvernorat, name="Leila Auditor")


async def ready_org(
    client: httpx.AsyncClient, user: User, staff: Staff, store: FakeStore, email: str | None = None
) -> tuple[dict[str, str], str]:
    admin = user(email) if email else user()
    org_id = await active_org(client, staff, admin)
    await complete(client, admin, store, org_id)
    return admin, org_id


async def inspected(
    client: httpx.AsyncClient, user: User, staff: Staff, store: FakeStore, email: str | None = None
) -> tuple[dict[str, str], str, dict[str, Any]]:
    """An institution whose requested visit was scheduled and inspected, with one non-conformity on site."""
    admin, org_id = await ready_org(client, user, staff, store, email)
    visit = (await client.post(f"/api/v1/orgs/{org_id}/prevention/visits", json={}, headers=admin)).json()
    body = {"scheduled_on": TODAY.isoformat(), "inspector_name": "Cdt Ben Salah"}
    r = await client.post(f"/api/v1/staff/prevention/visits/{visit['id']}/schedule", json=body, headers=auditor(staff))
    assert r.status_code == 200, r.text
    items = [{"key": i["key"], "result": "conform"} for i in r.json()["checklist"] if not i["key"].startswith("site.")]
    items.append({"key": "site.exits", "result": "nonconform", "observed": "Issue B encombrée"})
    inspection = {"inspected_on": TODAY.isoformat(), "attendees": "Directeur, responsable sécurité", "items": items}
    r = await client.post(
        f"/api/v1/staff/prevention/visits/{visit['id']}/inspection", json=inspection, headers=auditor(staff)
    )
    assert r.status_code == 200, r.text
    return admin, org_id, dict(r.json())


def test_checklist_and_comparison_follow_the_declaration() -> None:
    declared: dict[str, Any] = {
        "org": {"capacity": 120, "floors": 2, "height_m": 9.0, "address": "Rue 1"},
        "classification": {"family": "erp", "category": 4},
        "hazmat": [{"name": "Chlore", "un_number": "1017", "quantity": "200.000", "unit": "kg"}],
        "equipment": [{"kind": "extinguisher", "count": 6}, {"kind": "extinguisher", "count": 2}],
        "features": [{"kind": "evacuation_point"}, {"kind": "water_point"}],
        "team": [{"full_name": "Sami", "team_role": "representative"}, {"full_name": "Ali", "team_role": "member"}],
        "documents": [{"kind": "safety_file", "title": "Dossier", "version": 2, "sha256": "a" * 64}],
        "completeness": {"ok": True, "missing": []},
    }
    items = {i.key: i.declared for i in domain.prevention_checklist(declared)}
    assert items["building.capacity"] == 120 and items["classification.category"] == 4
    assert items["hazmat.0"] == "Chlore (UN 1017): 200 kg"
    assert items["equipment.extinguisher"] == 8 and items["evacuation.points"] == 1
    assert items["safety_team.representative"] == "Sami" and items["safety_team.members"] == 1
    assert items["documents.safety_file"] == "Dossier v2" and items["documents.safety_plan"] is None
    assert [k for k in items if k.startswith("site.")] == [f"site.{c}" for c in domain.SITE_CHECKS]

    all_conform = {k: domain.Finding("conform") for k in items}
    report = domain.comparison_report(declared, all_conform)
    assert (report["conform"], report["nonconform"], report["not_checked"]) == (len(items), 0, 0)
    assert report["suggested"] == "approved"
    # Items not recorded count as not checked; a non-conformity suggests reservations.
    report = domain.comparison_report(declared, {"site.alarm": domain.Finding("nonconform", note="Muette")})
    assert (report["nonconform"], report["not_checked"]) == (1, len(items) - 1)
    assert report["suggested"] == "approved_with_reservations"
    assert domain.reservation_state(TODAY, False, False, TODAY) == "open"
    assert domain.reservation_state(TODAY - timedelta(days=1), True, False, TODAY) == "overdue"
    assert domain.reservation_state(TODAY - timedelta(days=1), True, True, TODAY) == "lifted"


async def test_request_schedule_inspect_and_approve_with_reservations(
    client: httpx.AsyncClient, user: User, staff: Staff, fake_store: FakeStore, session: AsyncSession
) -> None:
    email = f"p{uuid.uuid4().hex[:10]}@example.tn"
    admin, org_id = await ready_org(client, user, staff, fake_store, email)
    base = f"/api/v1/orgs/{org_id}/prevention"

    # Only an admin asks, once at a time.
    editor = await add_member(client, admin, org_id, user, "editor")
    assert (await client.post(f"{base}/visits", json={}, headers=editor)).status_code == 403
    r = await client.post(f"{base}/visits", json={"note": "Avant la saison"}, headers=admin)
    assert r.status_code == 201, r.text
    visit = r.json()
    assert visit["status"] == "requested" and visit["origin"] == "request"
    assert visit["request_note"] == "Avant la saison"
    assert (await client.post(f"{base}/visits", json={}, headers=admin)).json()["detail"] == "visit_open"

    # The auditor sees it in the queue and schedules it; a past date is refused.
    queue = (await client.get("/api/v1/staff/prevention/visits?status=requested", headers=auditor(staff))).json()
    assert visit["id"] in [v["id"] for v in queue["items"]]
    vid = visit["id"]
    past = {"scheduled_on": (TODAY - timedelta(days=1)).isoformat()}
    r = await client.post(f"/api/v1/staff/prevention/visits/{vid}/schedule", json=past, headers=auditor(staff))
    assert r.json()["detail"] == "invalid_scheduled_on"
    soon = {"scheduled_on": (TODAY + timedelta(days=3)).isoformat(), "inspector_name": "Cdt Ben Salah"}
    r = await client.post(f"/api/v1/staff/prevention/visits/{vid}/schedule", json=soon, headers=auditor(staff))
    assert r.status_code == 200 and r.json()["status"] == "scheduled"
    assert any(i["key"] == "site.exits" for i in r.json()["checklist"])
    alerts = (await client.get(f"/api/v1/orgs/{org_id}/summary", headers=admin)).json()["alerts"]
    assert {"kind": "visit_scheduled", "ref": vid, "since": soon["scheduled_on"]} in alerts
    mails = await session.scalar(
        text("SELECT count(*) FROM notify.outbox WHERE channel = 'email' AND address = :a"), {"a": email}
    )
    assert mails == 1

    # The inspection: unknown items and a non-conformity without detail are refused.
    url = f"/api/v1/staff/prevention/visits/{vid}/inspection"
    on = TODAY.isoformat()
    bad = {"inspected_on": on, "items": [{"key": "site.pool", "result": "conform"}]}
    assert (await client.post(url, json=bad, headers=auditor(staff))).json()["detail"] == "unknown_item"
    bare = {"inspected_on": on, "items": [{"key": "site.alarm", "result": "nonconform"}]}
    assert (await client.post(url, json=bare, headers=auditor(staff))).json()["detail"] == "finding_detail_required"
    future = {"inspected_on": (TODAY + timedelta(days=1)).isoformat(), "items": []}
    assert (await client.post(url, json=future, headers=auditor(staff))).json()["detail"] == "invalid_inspected_on"
    found = {
        "inspected_on": on,
        "attendees": "Directeur",
        "items": [
            {"key": "building.capacity", "result": "nonconform", "observed": "160"},
            {"key": "site.alarm", "result": "nonconform", "note": "Sirène muette"},
            {"key": "evacuation.points", "result": "conform"},
        ],
    }
    r = await client.post(url, json=found, headers=auditor(staff))
    assert r.status_code == 200, r.text
    inspected_visit = r.json()
    comparison = inspected_visit["comparison"]
    assert inspected_visit["status"] == "inspected" and inspected_visit["has_report"] is True
    assert (comparison["conform"], comparison["nonconform"]) == (1, 2)
    assert comparison["suggested"] == "approved_with_reservations"
    capacity = next(i for i in comparison["items"] if i["key"] == "building.capacity")
    assert capacity["observed"] == "160" and capacity["declared"] is not None

    # The decision: reservations are needed with "approved with reservations", and their deadline is checked.
    decide = f"/api/v1/staff/prevention/visits/{vid}/decision"
    valid_until = (TODAY + timedelta(days=365)).isoformat()
    body: dict[str, Any] = {"decision": "approved_with_reservations", "valid_until": valid_until, "reservations": []}
    assert (await client.post(decide, json=body, headers=auditor(staff))).json()["detail"] == "reservations_required"
    body["reservations"] = [{"text": "Réparer la sirène", "due_on": TODAY.isoformat(), "item_key": "site.alarm"}]
    assert (await client.post(decide, json=body, headers=auditor(staff))).json()["detail"] == "invalid_due_on"
    due = (TODAY + timedelta(days=30)).isoformat()
    body["reservations"] = [
        {"text": "Réparer la sirène", "due_on": due, "item_key": "site.alarm"},
        {"text": "Mettre à jour la capacité déclarée", "due_on": (TODAY + timedelta(days=10)).isoformat()},
    ]
    r = await client.post(decide, json=body, headers=auditor(staff))
    assert r.status_code == 200, r.text
    decided = r.json()
    assert decided["status"] == "decided" and decided["decided_by_name"] == "Leila Auditor"
    assert decided["checklist"] == []
    cert = decided["certificate"]
    assert cert["kind"] == "prevention" and cert["code"].startswith("EHP-") and cert["status"] == "approved"
    assert cert["valid_until"] == valid_until and cert["key_id"]
    assert [r["state"] for r in decided["reservations"]] == ["open", "open"]
    assert (await client.post(decide, json=body, headers=auditor(staff))).json()["detail"] == "invalid_transition"

    # Public verification of the prevention certificate, and the counter reads its code.
    public = (await client.get(f"/api/v1/public/certificates/{cert['code']}")).json()
    assert public["valid"] is True and public["kind"] == "prevention" and public["with_reservations"] is True
    counter = await client.get(f"/api/v1/staff/certificates/lookup?code={cert['code']}", headers=auditor(staff))
    assert counter.status_code == 200 and counter.json()["valid"] is True

    # The institution sees it all; the safety certificate list is untouched.
    visits = (await client.get(f"{base}/visits", headers=editor)).json()
    assert visits[0]["certificate"]["code"] == cert["code"] and visits[0]["certificate"]["needs_update"] is False
    safety = (await client.get(f"/api/v1/orgs/{org_id}/certificates", headers=admin)).json()
    assert all(c["kind"] == "safety" for c in safety)
    report = (await client.get(f"{base}/visits/{vid}/report", headers=editor)).json()
    assert report["url"]
    kinds = [a["kind"] for a in (await client.get(f"/api/v1/orgs/{org_id}/summary", headers=admin)).json()["alerts"]]
    assert kinds.count("reservation_due_soon") == 1

    # The institution answers a reservation, the auditor lifts it.
    first = decided["reservations"][0]
    respond = f"{base}/reservations/{first['id']}/response"
    member = await add_member(client, admin, org_id, user, "member")
    assert (await client.post(respond, json={"note": "x"}, headers=member)).status_code == 403
    r = await client.post(respond, json={"note": "Sirène remplacée le 3"}, headers=editor)
    assert r.status_code == 200 and r.json()["state"] == "responded"
    lift = f"/api/v1/staff/prevention/reservations/{first['id']}/lift"
    assert (await client.post(lift, json={}, headers=staff(["operator"]))).status_code == 403
    r = await client.post(lift, json={"note": "Vérifié"}, headers=auditor(staff))
    assert r.status_code == 200 and r.json()["state"] == "lifted" and r.json()["lifted_by_name"] == "Leila Auditor"
    assert (await client.post(lift, json={}, headers=auditor(staff))).json()["detail"] == "reservation_lifted"
    assert (await client.post(respond, json={"note": "y"}, headers=editor)).json()["detail"] == "reservation_lifted"

    # Overdue: the deadline passed and the reservation is still there.
    second = decided["reservations"][1]
    await session.execute(
        text("UPDATE org.prevention_reservation SET due_on = :d WHERE id = :i"),
        {"d": TODAY - timedelta(days=2), "i": second["id"]},
    )
    await session.commit()
    alerts = (await client.get(f"/api/v1/orgs/{org_id}/summary", headers=admin)).json()["alerts"]
    assert any(a["kind"] == "reservation_overdue" and a["ref"] == second["id"] for a in alerts)
    staff_view = (await client.get(f"/api/v1/staff/prevention/visits/{vid}", headers=auditor(staff))).json()
    assert [r["state"] for r in staff_view["reservations"]] == ["overdue", "lifted"]

    # A new visit can be asked once this one is decided; an approval supersedes the previous prevention certificate.
    assert (await client.post(f"{base}/visits", json={}, headers=admin)).status_code == 201


async def test_refusal_needs_a_reason_and_issues_nothing(
    client: httpx.AsyncClient, user: User, staff: Staff, fake_store: FakeStore
) -> None:
    admin, org_id, visit = await inspected(client, user, staff, fake_store)
    assert visit["comparison"]["nonconform"] == 1
    decide = f"/api/v1/staff/prevention/visits/{visit['id']}/decision"
    r = await client.post(decide, json={"decision": "refused"}, headers=auditor(staff))
    assert r.json()["detail"] == "reason_required"
    with_reservation = {
        "decision": "refused",
        "reason": "Issues encombrées",
        "reservations": [{"text": "x", "due_on": (TODAY + timedelta(days=5)).isoformat()}],
    }
    r = await client.post(decide, json=with_reservation, headers=auditor(staff))
    assert r.json()["detail"] == "reservations_not_allowed"
    r = await client.post(decide, json={"decision": "refused", "reason": "Issues encombrées"}, headers=auditor(staff))
    assert r.status_code == 200, r.text
    assert r.json()["decision"] == "refused" and r.json()["certificate"] is None
    visits = (await client.get(f"/api/v1/orgs/{org_id}/prevention/visits", headers=admin)).json()
    assert visits[0]["decision_reason"] == "Issues encombrées" and visits[0]["has_report"] is True


async def test_plain_approval_and_supersession(
    client: httpx.AsyncClient, user: User, staff: Staff, fake_store: FakeStore
) -> None:
    _admin, org_id, visit = await inspected(client, user, staff, fake_store)
    body = {"decision": "approved", "valid_until": (TODAY + timedelta(days=200)).isoformat()}
    with_reservation = body | {"reservations": [{"text": "x", "due_on": (TODAY + timedelta(days=5)).isoformat()}]}
    decide = f"/api/v1/staff/prevention/visits/{visit['id']}/decision"
    r = await client.post(decide, json=with_reservation, headers=auditor(staff))
    assert r.json()["detail"] == "reservations_not_allowed"
    r = await client.post(decide, json=body | {"valid_until": TODAY.isoformat()}, headers=auditor(staff))
    assert r.json()["detail"] == "invalid_valid_until"
    first = (await client.post(decide, json=body, headers=auditor(staff))).json()["certificate"]
    public = (await client.get(f"/api/v1/public/certificates/{first['code']}")).json()
    assert public["valid"] is True and public["with_reservations"] is False

    # A visit scheduled by the Office, without a request; the new certificate replaces the first one.
    r = await client.post(
        f"/api/v1/staff/orgs/{org_id}/prevention/visits",
        json={"scheduled_on": TODAY.isoformat()},
        headers=auditor(staff),
    )
    assert r.status_code == 201 and r.json()["origin"] == "scheduled"
    vid = r.json()["id"]
    inspection = {"inspected_on": TODAY.isoformat(), "items": []}
    await client.post(f"/api/v1/staff/prevention/visits/{vid}/inspection", json=inspection, headers=auditor(staff))
    second = (
        await client.post(f"/api/v1/staff/prevention/visits/{vid}/decision", json=body, headers=auditor(staff))
    ).json()["certificate"]
    assert second["code"] != first["code"]
    public = (await client.get(f"/api/v1/public/certificates/{first['code']}")).json()
    assert public["valid"] is False and public["superseded"] is True
    staff_visits = (await client.get(f"/api/v1/staff/orgs/{org_id}/prevention/visits", headers=auditor(staff))).json()
    assert len(staff_visits) == 2


async def test_cancel_scope_and_roles(
    client: httpx.AsyncClient, user: User, staff: Staff, fake_store: FakeStore
) -> None:
    admin, org_id = await ready_org(client, user, staff, fake_store)
    visit = (await client.post(f"/api/v1/orgs/{org_id}/prevention/visits", json={}, headers=admin)).json()
    vid = visit["id"]
    # Out of scope: another gouvernorat does not see it; a reader cannot schedule.
    assert (await client.get(f"/api/v1/staff/prevention/visits/{vid}", headers=auditor(staff, 11))).status_code == 404
    soon = {"scheduled_on": TODAY.isoformat()}
    r = await client.post(f"/api/v1/staff/prevention/visits/{vid}/schedule", json=soon, headers=staff(["operator"]))
    assert r.status_code == 403
    r = await client.post(f"/api/v1/staff/orgs/{org_id}/prevention/visits", json=soon, headers=auditor(staff))
    assert r.json()["detail"] == "visit_open"
    # Inspecting needs a scheduled visit.
    inspection = {"inspected_on": TODAY.isoformat(), "items": []}
    r = await client.post(f"/api/v1/staff/prevention/visits/{vid}/inspection", json=inspection, headers=auditor(staff))
    assert r.json()["detail"] == "invalid_transition"

    # The institution withdraws its request.
    withdraw = f"/api/v1/orgs/{org_id}/prevention/visits/{vid}/cancel"
    r = await client.post(withdraw, json={}, headers=admin)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert (await client.post(withdraw, json={}, headers=admin)).json()["detail"] == "invalid_transition"

    # The Office cancels a scheduled visit, with a reason; the institution cannot cancel it once scheduled.
    r = await client.post(f"/api/v1/staff/orgs/{org_id}/prevention/visits", json=soon, headers=auditor(staff))
    vid = r.json()["id"]
    assert (await client.post(f"/api/v1/orgs/{org_id}/prevention/visits/{vid}/cancel", json={}, headers=admin)).json()[
        "detail"
    ] == "invalid_transition"
    cancel = f"/api/v1/staff/prevention/visits/{vid}/cancel"
    assert (await client.post(cancel, json={}, headers=auditor(staff))).json()["detail"] == "reason_required"
    r = await client.post(cancel, json={"reason": "Report demandé"}, headers=auditor(staff))
    assert r.json()["status"] == "cancelled" and r.json()["cancel_reason"] == "Report demandé"
    queue = (await client.get("/api/v1/staff/prevention/visits?status=nope", headers=auditor(staff))).json()
    assert queue["detail"] == "invalid_status"


async def test_annual_report(client: httpx.AsyncClient, user: User, staff: Staff, fake_store: FakeStore) -> None:
    admin, org_id, visit = await inspected(client, user, staff, fake_store)
    base = f"/api/v1/orgs/{org_id}"
    drill = {"kind": "drill", "title": "Évacuation", "starts_on": TODAY.isoformat(), "participants": 40}
    assert (await client.post(f"{base}/activities", json=drill, headers=admin)).status_code == 201
    body = {
        "decision": "approved_with_reservations",
        "valid_until": (TODAY + timedelta(days=300)).isoformat(),
        "reservations": [{"text": "Dégager l'issue B", "due_on": (TODAY + timedelta(days=20)).isoformat()}],
    }
    await client.post(f"/api/v1/staff/prevention/visits/{visit['id']}/decision", json=body, headers=auditor(staff))

    r = await client.get(f"{base}/annual-report?year={TODAY.year}", headers=admin)
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["year"] == TODAY.year and report["participants"] == 40 and len(report["drills"]) == 1
    assert len(report["visits"]) == 1 and report["visits"][0]["decision"] == "approved_with_reservations"
    assert report["reservations"] == {"opened": 1, "lifted": 0, "open": 1, "overdue": 0}
    assert [c["kind"] for c in report["certificates"]] == ["prevention"]
    assert sum(report["training"].values()) >= 1
    assert (await client.get(f"{base}/annual-report?year={TODAY.year + 1}", headers=admin)).json()[
        "detail"
    ] == "invalid_year"
    assert (await client.get(f"{base}/annual-report?year={TODAY.year}", headers=user())).status_code == 404
