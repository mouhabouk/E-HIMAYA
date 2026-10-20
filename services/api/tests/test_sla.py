"""Claim deadlines, late list and central response (phase 9, docs/api/phase-9-contract.md §4.2–§4.4).

The SLA worker is driven with a frozen clock (``escalate_due(session, now=…)``)."""

import uuid
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_sessionmaker
from app.main import WORKER_LOOPS
from app.modules.reports import jurisdiction
from app.modules.settings import service as settings_service
from tests.conftest import SFAX, outbox_events
from tests.test_jurisdiction import claim, detail, new_report

Staff = Callable[..., dict[str, str]]


async def _row(session: AsyncSession, report_id: str) -> Any:
    return (
        await session.execute(
            text(
                "SELECT received_at, sla_band, sla_due_at, escalation_state, escalated_at, claimed_room "
                "FROM reports.report WHERE id = :id"
            ),
            {"id": report_id},
        )
    ).one()


async def _tick(at: datetime) -> int:
    async with get_sessionmaker()() as s, s.begin():
        return await jurisdiction.escalate_due(s, now=at)


async def _late_report(client: httpx.AsyncClient, session: AsyncSession, **overrides: Any) -> dict[str, Any]:
    """A Sfax report already past its claim deadline."""
    report = await new_report(client, SFAX, **overrides)
    row = await _row(session, report["id"])
    await _tick(row.sla_due_at + timedelta(seconds=1))
    session.expire_all()
    assert (await _row(session, report["id"])).escalation_state == "late"
    return report


async def _late_ids(client: httpx.AsyncClient, headers: dict[str, str], **params: Any) -> set[str]:
    """Every id on the late list, following the cursor (the shared test database keeps late reports of earlier tests)."""
    ids: set[str] = set()
    cursor: str | None = None
    while True:
        query = {**params, "limit": 500, **({"cursor": cursor} if cursor else {})}
        r = await client.get("/api/v1/staff/reports/late", params=query, headers=headers)
        assert r.status_code == 200, r.text
        ids |= {i["id"] for i in r.json()["items"]}
        cursor = r.json()["next_cursor"]
        if cursor is None:
            return ids


@pytest.fixture
async def restore_sla() -> AsyncIterator[None]:
    async with get_sessionmaker()() as s:
        saved = (await s.execute(text("SELECT key, value::text, version FROM platform.setting"))).all()
    yield
    async with get_sessionmaker()() as s, s.begin():
        for key, value, version in saved:
            await s.execute(
                text("UPDATE platform.setting SET value = CAST(:v AS jsonb), version = :n WHERE key = :k"),
                {"k": key, "v": value, "n": version},
            )
    settings_service.invalidate()


def test_worker_loop_registered() -> None:
    names = [name for name, _ in WORKER_LOOPS]
    assert "sla-escalation" in names and "breakglass" in names


async def test_late_after_band_delay(client: httpx.AsyncClient, session: AsyncSession) -> None:
    sos = await new_report(client, SFAX, category="sos", text=None)
    row = await _row(session, sos["id"])
    assert row.sla_band == "critical" and row.sla_due_at == row.received_at + timedelta(seconds=60)
    await _tick(row.received_at + timedelta(seconds=59))
    session.expire_all()
    assert (await _row(session, sos["id"])).escalation_state == "none"
    await _tick(row.received_at + timedelta(seconds=61))
    session.expire_all()
    late = await _row(session, sos["id"])
    assert late.escalation_state == "late" and late.escalated_at == row.received_at + timedelta(seconds=61)
    steps = (
        await session.execute(
            text("SELECT kind, actor, from_room, to_room FROM reports.escalation WHERE report_id = :id"),
            {"id": sos["id"]},
        )
    ).all()
    assert [tuple(s) for s in steps] == [("late", "system:sla", "g:61", "central")]
    events = [e for e in await outbox_events(session, "report.late") if e["report"]["id"] == sos["id"]]
    assert len(events) == 1 and events[0]["report"]["late"] is True and events[0]["gouvernorat_codes"] == [61]
    # Marked once.
    await _tick(row.received_at + timedelta(seconds=120))
    count = await session.scalar(
        text("SELECT count(*) FROM reports.escalation WHERE report_id = :id"), {"id": sos["id"]}
    )
    assert count == 1


async def test_low_band_follows_rescoring(client: httpx.AsyncClient, session: AsyncSession) -> None:
    report = await new_report(client, SFAX, category="other", text="x")
    row = await _row(session, report["id"])
    # The AI rescoring lowers the priority before anyone claims it: the band and deadline follow.
    await session.execute(text("UPDATE reports.report SET priority_score = 10 WHERE id = :id"), {"id": report["id"]})
    await session.commit()
    await _tick(row.received_at + timedelta(seconds=100))
    session.expire_all()
    low = await _row(session, report["id"])
    assert (low.sla_band, low.escalation_state) == ("low", "none")
    assert low.sla_due_at == row.received_at + timedelta(seconds=180)
    await _tick(row.received_at + timedelta(seconds=179))
    session.expire_all()
    assert (await _row(session, report["id"])).escalation_state == "none"
    await _tick(row.received_at + timedelta(seconds=181))
    session.expire_all()
    assert (await _row(session, report["id"])).escalation_state == "late"


async def test_rescore_never_due_before_now(client: httpx.AsyncClient, session: AsyncSession) -> None:
    report = await new_report(client, SFAX, category="other", text="x")
    row = await _row(session, report["id"])
    await session.execute(text("UPDATE reports.report SET priority_score = 95 WHERE id = :id"), {"id": report["id"]})
    await session.commit()
    now = row.received_at + timedelta(seconds=100)
    await _tick(now)
    session.expire_all()
    critical = await _row(session, report["id"])
    # Critical delay (60 s) is already over: due in 5 s from now, not in the past.
    assert critical.sla_band == "critical" and critical.sla_due_at == now + timedelta(seconds=5)
    assert critical.escalation_state == "none"


async def test_not_for_claimed_or_older_reports(client: httpx.AsyncClient, session: AsyncSession, staff: Staff) -> None:
    claimed = await new_report(client, SFAX, category="sos", text=None)
    assert (await claim(client, staff(gouvernorat=61), claimed["id"])).status_code == 200
    older = await new_report(client, SFAX, category="sos", text=None)
    since = await settings_service.enforced_since(session)
    assert since is not None
    before = since - timedelta(days=1)
    await session.execute(
        text("UPDATE reports.report SET received_at = :at, sla_due_at = :due WHERE id = :id"),
        {"id": older["id"], "at": before, "due": before + timedelta(seconds=60)},
    )
    await session.commit()
    row = await _row(session, claimed["id"])
    await _tick(row.received_at + timedelta(minutes=10))
    session.expire_all()
    assert (await _row(session, claimed["id"])).escalation_state == "none"
    assert (await _row(session, older["id"])).escalation_state == "none"


async def test_settings_delay_applies(
    client: httpx.AsyncClient, session: AsyncSession, staff: Staff, restore_sla: None
) -> None:
    central = staff(["central_committee"], gouvernorat=None)
    current = {i["key"]: i for i in (await client.get("/api/v1/staff/settings", headers=central)).json()["items"]}
    delays = {**current["sla.claim_delay_s"]["value"], "critical": 75}
    r = await client.put(
        "/api/v1/staff/settings/sla.claim_delay_s",
        json={"value": delays, "version": current["sla.claim_delay_s"]["version"], "reason": "délai critique 75 s"},
        headers=central,
    )
    assert r.status_code == 200, r.text
    sos = await new_report(client, SFAX, category="sos", text=None)
    row = await _row(session, sos["id"])
    assert row.sla_due_at == row.received_at + timedelta(seconds=75)
    await _tick(row.received_at + timedelta(seconds=61))
    session.expire_all()
    assert (await _row(session, sos["id"])).escalation_state == "none"
    await _tick(row.received_at + timedelta(seconds=76))
    session.expire_all()
    assert (await _row(session, sos["id"])).escalation_state == "late"


async def test_central_claim_only_when_late(client: httpx.AsyncClient, session: AsyncSession, staff: Staff) -> None:
    national = staff(gouvernorat=None, name="Nour Central")
    late = await _late_report(client, session)
    # Made after the worker ran: still within its deadline.
    fresh = await new_report(client, SFAX)
    r = await claim(client, national, fresh["id"])
    assert (r.status_code, r.json()["detail"]) == (403, "not_claimable")

    # The region sees it flagged in its normal list; the central room on the late list.
    sfax = staff(gouvernorat=61)
    item = (await detail(client, sfax, late["id"])).json()
    assert item["late"] is True and item["escalation_state"] == "late"
    listed_late = await _late_ids(client, national)
    assert late["id"] in listed_late and fresh["id"] not in listed_late
    r = await client.get("/api/v1/staff/reports/late", headers=sfax)
    assert (r.status_code, r.json()["detail"]) == (403, "national_scope_required")
    assert late["id"] not in await _late_ids(client, national, gouvernorat=11)
    assert late["id"] in await _late_ids(client, national, gouvernorat=61)

    r = await claim(client, national, late["id"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["claimed_room"], body["escalation_state"]) == ("central", "central_responding")
    assert [(e["kind"], e["to_room"], e["actor_name"]) for e in body["escalations"]] == [
        ("late", "central", None),
        ("central_claim", "central", "Nour Central"),
    ]
    # The central room answers the citizen (status change notifies the reporter as in phase 2).
    r = await client.post(
        f"/api/v1/staff/reports/{late['id']}/status",
        json={"status": "in_progress", "note": "pris en charge"},
        headers=national,
    )
    assert r.status_code == 200, r.text
    # The region can no longer act on it.
    r = await client.post(f"/api/v1/staff/reports/{late['id']}/status", json={"status": "rejected"}, headers=sfax)
    assert r.status_code == 409 and r.json()["claimed_room"] == "central"


async def test_central_assignment_refused(client: httpx.AsyncClient, session: AsyncSession, staff: Staff) -> None:
    late = await _late_report(client, session)
    national = staff(gouvernorat=None)
    assert (await claim(client, national, late["id"])).status_code == 200
    linked = await client.post(
        f"/api/v1/staff/reports/{late['id']}/incident",
        json={"action": "new", "override_reason": "test central"},
        headers=national,
    )
    assert linked.status_code == 200, linked.text
    incident_id = linked.json()["incident_id"]
    r = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/assignments", json={"resource_id": str(uuid.uuid4())}, headers=national
    )
    assert (r.status_code, r.json()["detail"]) == (403, "field_action_regional_only")


async def test_refer_accept(client: httpx.AsyncClient, session: AsyncSession, staff: Staff) -> None:
    late = await _late_report(client, session)
    national = staff(["ops_manager"], gouvernorat=None, name="Nour Central")
    url = f"/api/v1/staff/reports/{late['id']}/refer"
    body = {
        "to_gouvernorat_code": 61,
        "reason": "aucune prise en charge",
        "directive": {"title": "Prendre en charge", "body": "Bilan sous 10 min", "urgency": "urgent"},
    }
    assert (await client.post(url, json=body, headers=staff(gouvernorat=61))).status_code == 403
    assert (await client.post(url, json={**body, "to_gouvernorat_code": 99}, headers=national)).status_code == 422
    r = await client.post(url, json=body, headers=national)
    assert r.status_code == 200, r.text
    assert (r.json()["escalation_state"], r.json()["claimed_room"]) == ("referred", None)
    directive_id = (
        await session.execute(
            text("SELECT payload->>'directive_id' FROM reports.escalation WHERE report_id = :id AND kind = 'referral'"),
            {"id": late["id"]},
        )
    ).scalar_one()
    directive = (
        await session.execute(
            text("SELECT gouvernorat_codes, issuer_scope, from_level FROM ops.directive WHERE id = :id"),
            {"id": directive_id},
        )
    ).one()
    assert (directive.gouvernorat_codes, directive.issuer_scope, directive.from_level) == ([61], None, "central")
    again = await client.post(url, json={**body, "directive": None}, headers=national)
    assert (again.status_code, again.json()["detail"]) == (409, "referral_pending")
    # Only the target room answers.
    accept = f"/api/v1/staff/reports/{late['id']}/referral/accept"
    assert (await client.post(accept, json={}, headers=staff(gouvernorat=11))).status_code == 404
    assert (await client.post(accept, json={}, headers=national)).status_code == 403
    r = await client.post(accept, json={"note": "équipe engagée"}, headers=staff(["local_committee"], gouvernorat=61))
    assert r.status_code == 200, r.text
    assert (r.json()["claimed_room"], r.json()["escalation_state"]) == ("g:61", "referral_accepted")
    r = await client.post(accept, json={}, headers=staff(gouvernorat=61))
    assert (r.status_code, r.json()["detail"]) == (409, "referral_not_pending")


async def test_refer_refuse(client: httpx.AsyncClient, session: AsyncSession, staff: Staff) -> None:
    late = await _late_report(client, session)
    national = staff(gouvernorat=None)
    # Referred to another region than the report's (e.g. a neighbour with means available).
    r = await client.post(
        f"/api/v1/staff/reports/{late['id']}/refer",
        json={"to_gouvernorat_code": 81, "reason": "moyens disponibles à Gabès", "directive": None},
        headers=national,
    )
    assert r.status_code == 200, r.text
    gabes = staff(gouvernorat=81)
    assert (await detail(client, gabes, late["id"])).status_code == 200
    refuse = f"/api/v1/staff/reports/{late['id']}/referral/refuse"
    assert (await client.post(refuse, json={"reason": "x"}, headers=gabes)).status_code == 422
    r = await client.post(refuse, json={"reason": "aucun moyen disponible"}, headers=gabes)
    assert r.status_code == 200, r.text
    assert r.json()["escalation_state"] == "referral_refused"
    # Gabès no longer sees it; it stays on the central late list.
    assert (await detail(client, gabes, late["id"])).status_code == 404
    assert late["id"] in await _late_ids(client, national)
    # The central room must act: it may claim it.
    assert (await claim(client, national, late["id"])).json()["escalation_state"] == "central_responding"


async def test_escalations_listed(client: httpx.AsyncClient, session: AsyncSession, staff: Staff) -> None:
    late = await _late_report(client, session)
    national = staff(gouvernorat=None, name="Nour Central")
    await client.post(
        f"/api/v1/staff/reports/{late['id']}/refer",
        json={"to_gouvernorat_code": 61, "reason": "relance de la région"},
        headers=national,
    )
    await client.post(
        f"/api/v1/staff/reports/{late['id']}/referral/refuse",
        json={"reason": "pas de moyens"},
        headers=staff(gouvernorat=61, name="Rim Sfax"),
    )
    await claim(client, national, late["id"])
    await client.request(
        "DELETE",
        f"/api/v1/staff/reports/{late['id']}/claim",
        json={"reason": "rendu à la région"},
        headers=national,
    )
    steps = (await detail(client, national, late["id"])).json()["escalations"]
    assert [(s["kind"], s["actor_name"], s["reason"]) for s in steps] == [
        ("late", None, None),
        ("referral", "Nour Central", "relance de la région"),
        ("referral_refused", "Rim Sfax", "pas de moyens"),
        ("central_claim", "Nour Central", None),
        ("claim_released", "Nour Central", "rendu à la région"),
    ]
    assert all(s["at"] for s in steps)
    assert [s["at"] for s in steps] == sorted(s["at"] for s in steps)
    # Released by the central room: late again, unclaimed.
    body = (await detail(client, national, late["id"])).json()
    assert (body["escalation_state"], body["claimed_room"]) == ("late", None)
    audited = await session.scalar(
        text(
            "SELECT count(*) FROM audit.log WHERE target = :t AND action IN "
            "('report.refer', 'report.referral_refused', 'report.claim', 'report.release')"
        ),
        {"t": f"report:{late['id']}"},
    )
    assert audited == 4
