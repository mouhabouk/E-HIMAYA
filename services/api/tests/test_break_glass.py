"""Break-glass access (phase 9, docs/api/phase-9-contract.md §6.1): a justified, time-boxed, read-only grant, its
expiry by the worker loop, revocation, and the review by a security administrator who is not the holder."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_system_sessionmaker
from app.modules.access import worker
from tests.conftest import SFAX, TokenFactory, outbox_events
from tests.scopehelpers import Staff, new_report
from tests.test_access import citizen_report

URL = "/api/v1/staff/break-glass"
JUSTIFICATION = "Victime transférée depuis Gabès, besoin du dossier pour guider les secours."
GABES = 81


def holder(staff: Staff, subject: str, **claims: Any) -> dict[str, str]:
    return staff(gouvernorat=GABES, sub=subject, name="Amel Gabès", **claims)


async def grant(client: httpx.AsyncClient, headers: dict[str, str], **body: Any) -> httpx.Response:
    return await client.post(URL, json={"justification": JUSTIFICATION, "duration_min": 15, **body}, headers=headers)


async def test_grant_lifecycle(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    report = await new_report(client, SFAX)
    subject = str(uuid.uuid4())
    gabes = holder(staff, subject)
    detail = f"/api/v1/staff/reports/{report['id']}"
    assert (await client.get(detail, headers=gabes)).status_code == 404
    # Validation: a real justification, a known target.
    r = await grant(client, gabes, target_kind="report", target_id=report["id"], justification="urgent")
    assert (r.status_code, r.json()["detail"]) == (422, "breakglass_justification_required")
    r = await grant(client, gabes, target_kind="report", target_id=str(uuid.uuid4()))
    assert (r.status_code, r.json()["detail"]) == (422, "invalid_target")
    r = await grant(client, gabes, target_kind="report", target_id=report["id"], duration_min=600)
    assert r.status_code == 422
    # Technical roles cannot ask for operational data.
    r = await grant(client, staff(["sysadmin"], gouvernorat=None), target_kind="report", target_id=report["id"])
    assert r.status_code == 403
    r = await grant(client, gabes, target_kind="report", target_id=report["id"])
    assert r.status_code == 201, r.text
    body = r.json()
    assert (body["state"], body["subject"], body["subject_name"]) == ("active", subject, "Amel Gabès")
    assert (await client.get(detail, headers=gabes)).status_code == 200
    # Listed for the holder (active), not for another regional user.
    mine = (await client.get(URL, params={"status": "active"}, headers=gabes)).json()["items"]
    assert body["id"] in {g["id"] for g in mine}
    others = (await client.get(URL, headers=staff(gouvernorat=GABES))).json()["items"]
    assert body["id"] not in {g["id"] for g in others}
    events = await outbox_events(session, "breakglass.granted")
    assert any(e["grant"]["id"] == body["id"] for e in events)
    audited = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'breakglass.grant' AND details->>'grant_id' = :g"),
        {"g": body["id"]},
    )
    assert audited == 1


async def test_write_still_refused(client: httpx.AsyncClient, staff: Staff) -> None:
    report = await new_report(client, SFAX)
    subject = str(uuid.uuid4())
    gabes = holder(staff, subject, roles=["ops_manager"])
    r = await grant(client, gabes, target_kind="gouvernorat", gouvernorat_code=61)
    assert r.status_code == 201, r.text
    url = f"/api/v1/staff/reports/{report['id']}"
    assert (await client.get(url, headers=gabes)).status_code == 200
    # The list shows the granted gouvernorat's reports too.
    listed = (await client.get("/api/v1/staff/reports", params={"limit": 500}, headers=gabes)).json()["items"]
    assert report["id"] in {i["id"] for i in listed}
    for method, path, body in (
        ("POST", f"{url}/claim", None),
        ("POST", f"{url}/status", {"status": "in_progress"}),
        ("POST", f"{url}/incident", {"action": "new", "override_reason": "accès exceptionnel"}),
    ):
        r = await client.request(method, path, json=body, headers=gabes)
        assert r.status_code in {403, 404, 409}, (path, r.text)
        assert r.status_code != 200


async def test_expiry_and_review(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    report = await new_report(client, SFAX)
    subject = str(uuid.uuid4())
    gabes = holder(staff, subject)
    r = await grant(client, gabes, target_kind="report", target_id=report["id"])
    grant_id = r.json()["id"]
    # Expiry: the worker ends it; the report is out of reach again.
    await session.execute(
        text(
            "UPDATE access.break_glass_grant SET granted_at = now() - interval '16 minutes', "
            "expires_at = now() - interval '1 minute' WHERE id = :g"
        ),
        {"g": grant_id},
    )
    await session.commit()
    ended, _ = await worker.run_once(get_system_sessionmaker())
    assert ended >= 1
    assert (await client.get(f"/api/v1/staff/reports/{report['id']}", headers=gabes)).status_code == 404
    pending = (await client.get(URL, params={"status": "pending_review"}, headers=gabes)).json()["items"]
    assert grant_id in {g["id"] for g in pending}
    # Review: a national security admin, never the holder, once.
    review = f"{URL}/{grant_id}/review"
    r = await client.post(review, json={"outcome": "justified"}, headers=staff(["operator"], gouvernorat=None))
    assert r.status_code == 403
    self_admin = staff(["security_admin", "operator"], gouvernorat=None, sub=subject)
    r = await client.post(review, json={"outcome": "justified"}, headers=self_admin)
    assert (r.status_code, r.json()["detail"]) in {(403, "breakglass_self_review"), (404, "not_found")}
    security = staff(["security_admin"], gouvernorat=None, name="Karim Sécurité")
    every = (await client.get(URL, params={"status": "pending_review", "limit": 100}, headers=security)).json()
    assert grant_id in {g["id"] for g in every["items"]}
    r = await client.post(review, json={"outcome": "unjustified", "note": "aucun lien avec Gabès"}, headers=security)
    assert r.status_code == 200, r.text
    assert (r.json()["state"], r.json()["review_outcome"], r.json()["reviewed_by"]) == (
        "reviewed",
        "unjustified",
        "Karim Sécurité",
    )
    r = await client.post(review, json={"outcome": "justified"}, headers=security)
    assert (r.status_code, r.json()["detail"]) == (409, "already_reviewed")


async def test_review_overdue_is_flagged(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    report = await new_report(client, SFAX)
    gabes = holder(staff, str(uuid.uuid4()))
    grant_id = (await grant(client, gabes, target_kind="report", target_id=report["id"])).json()["id"]
    long_ago = datetime.now(UTC) - timedelta(hours=80)
    await session.execute(
        text("UPDATE access.break_glass_grant SET granted_at = :g0, expires_at = :t, ended_at = :t WHERE id = :g"),
        {"g0": long_ago - timedelta(minutes=15), "t": long_ago, "g": grant_id},
    )
    await session.commit()
    _, overdue = await worker.run_once(get_system_sessionmaker())
    assert overdue >= 1
    events = await outbox_events(session, "breakglass.review_overdue")
    assert any(e["grant"]["id"] == grant_id for e in events)
    # Flagged once.
    await worker.run_once(get_system_sessionmaker())
    events = await outbox_events(session, "breakglass.review_overdue")
    assert sum(e["grant"]["id"] == grant_id for e in events) == 1


async def test_revoke(client: httpx.AsyncClient, staff: Staff) -> None:
    report = await new_report(client, SFAX)
    subject = str(uuid.uuid4())
    gabes = holder(staff, subject)
    grant_id = (await grant(client, gabes, target_kind="report", target_id=report["id"])).json()["id"]
    # Somebody else cannot revoke it (not disclosed).
    assert (await client.post(f"{URL}/{grant_id}/revoke", headers=staff(gouvernorat=GABES))).status_code == 404
    r = await client.post(f"{URL}/{grant_id}/revoke", headers=gabes)
    assert r.status_code == 200 and r.json()["state"] == "pending_review" and r.json()["revoked_at"]
    assert (await client.get(f"/api/v1/staff/reports/{report['id']}", headers=gabes)).status_code == 404
    r = await client.post(f"{URL}/{grant_id}/revoke", headers=gabes)
    assert (r.status_code, r.json()["detail"]) == (409, "grant_not_active")


@pytest.mark.parametrize("kind", ["incident", "gouvernorat"])
async def test_grant_targets(client: httpx.AsyncClient, staff: Staff, kind: str) -> None:
    report = await new_report(client, SFAX)
    gabes = holder(staff, str(uuid.uuid4()))
    body: dict[str, Any] = {"target_kind": kind}
    if kind == "incident":
        r = await client.post(
            f"/api/v1/staff/reports/{report['id']}/incident",
            json={"action": "new", "override_reason": "independent test incident"},
            headers=staff(gouvernorat=61),
        )
        incident_id = r.json()["incident_id"]
        body["target_id"] = incident_id
        url = f"/api/v1/staff/incidents/{incident_id}"
    else:
        body["gouvernorat_code"] = 61
        url = f"/api/v1/staff/reports/{report['id']}"
    assert (await client.get(url, headers=gabes)).status_code == 404
    assert (await grant(client, gabes, **body)).status_code == 201
    assert (await client.get(url, headers=gabes)).status_code == 200


async def test_reveal_audited(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, session: AsyncSession
) -> None:
    """Acceptance 16: the reporter's identity shows under a grant, and every such reading is audited with the grant."""
    report = await citizen_report(client, make_token)
    gabes = holder(staff, str(uuid.uuid4()))
    grant_id = (await grant(client, gabes, target_kind="report", target_id=report["id"])).json()["id"]
    url = f"/api/v1/staff/reports/{report['id']}"
    for _ in range(2):
        body = (await client.get(url, headers=gabes)).json()
        assert body["reporter"]["masked"] is False
    readings = await session.scalar(
        text(
            "SELECT count(*) FROM audit.log WHERE action = 'report.view_sensitive' AND target = :t "
            "AND details->>'grant_id' = :g"
        ),
        {"t": f"report:{report['id']}", "g": grant_id},
    )
    assert readings == 2
    # Another regional user without a grant: not even the report.
    assert (await client.get(url, headers=staff(gouvernorat=GABES))).status_code == 404
