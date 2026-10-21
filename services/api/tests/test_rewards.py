"""Phase 8 rewards (docs/api/phase-8-contract.md §3): points from outbox events (idempotent), no points for anonymous,
rejected or false reports, once per incident, daily cap, pause at level disaster, badges and their confirmation,
revocation, nominations and certificates with a minimal public verification, citizen erasure, staff scope."""

import base64
import os
import secrets
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import timedelta
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_system_sessionmaker
from app.modules.privacy import retention
from app.modules.rewards import consumer, service
from tests.conftest import (
    FakeStore,
    TokenFactory,
    accept_charter,
    bearer,
    device_headers,
    report_body,
)

Staff = Callable[..., dict[str, str]]
SFAX_CODE = 61


def sfax_place() -> dict[str, float]:
    return {"lat": 34.60 + secrets.randbelow(1000) / 10_000, "lon": 10.50 + secrets.randbelow(1000) / 10_000}


@pytest.fixture(autouse=True)
async def _normal_levels() -> AsyncIterator[None]:
    yield
    async with get_system_sessionmaker()() as s, s.begin():
        await s.execute(text("UPDATE ops.level_state SET level = 'normal', reason = NULL"))


@pytest.fixture
def signing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "certificate_signing_key", SecretStr(base64.b64encode(os.urandom(32)).decode()))


async def drain() -> None:
    await consumer.run_until_idle(get_system_sessionmaker(), gap_grace=timedelta(0))


async def new_citizen(
    client: httpx.AsyncClient, make_token: TokenFactory, gouvernorat: int = SFAX_CODE
) -> dict[str, str]:
    headers = bearer(make_token(roles=["citizen"], email=f"r{uuid.uuid4().hex[:8]}@example.tn", email_verified=True))
    r = await client.put(
        "/api/v1/me/profile",
        json={
            "first_name": "Amine",
            "last_name": "Ben Salah",
            "cin": f"{secrets.randbelow(100_000_000):08d}",
            "phone": f"+2169{secrets.randbelow(10_000_000):07d}",
            "gouvernorat_code": gouvernorat,
            "delegation_id": gouvernorat * 100 + 1,
            "locale": "fr",
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    await accept_charter(client, headers)
    return headers


async def citizen_id(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    subject = (await client.get("/api/v1/me", headers=headers)).json()["subject"]
    async with get_system_sessionmaker()() as s:
        user_id = await s.scalar(text("SELECT user_id FROM identity.account WHERE keycloak_sub = :s"), {"s": subject})
    return str(user_id)


async def report(
    client: httpx.AsyncClient, headers: dict[str, str], place: dict[str, float], category: str = "fire"
) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/reports", json=report_body({**place, "accuracy_m": 10.0}, category=category), headers=headers
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def incident_of(client: httpx.AsyncClient, staff: Staff, report_id: str, incident_id: str | None = None) -> str:
    body = (
        {"action": "new", "override_reason": "independent test incident"}
        if incident_id is None
        else {"action": "link", "incident_id": incident_id}
    )
    r = await client.post(f"/api/v1/staff/reports/{report_id}/incident", json=body, headers=staff(["operator"]))
    assert r.status_code == 200, r.text
    return r.json()["incident_id"]  # type: ignore[no-any-return]


async def close(client: httpx.AsyncClient, staff: Staff, incident_id: str, outcome: str = "resolved") -> None:
    body = {"outcome": outcome, "summary": "أُغلق التدخل بعد المعاينة", "casualties": {"rescued": 1}}
    r = await client.post(f"/api/v1/staff/incidents/{incident_id}/close", json=body, headers=staff(["field_commander"]))
    assert r.status_code == 200, r.text


async def verified_incident(
    client: httpx.AsyncClient, staff: Staff, headers: dict[str, str], category: str = "fire"
) -> tuple[str, dict[str, Any]]:
    rep = await report(client, headers, sfax_place(), category)
    incident_id = await incident_of(client, staff, rep["id"])
    await close(client, staff, incident_id)
    return incident_id, rep


async def mine(client: httpx.AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    r = await client.get("/api/v1/me/rewards", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


# ---------------------------------------------------------------- automatic points


async def test_verified_points_are_idempotent(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, session: AsyncSession
) -> None:
    headers = await new_citizen(client, make_token)
    rep = await report(client, headers, sfax_place())
    incident_id = await incident_of(client, staff, rep["id"])
    await drain()
    # Received, then in progress: nothing yet (points only for verified usefulness).
    assert (await mine(client, headers))["balance"] == 0
    await close(client, staff, incident_id)
    await drain()
    me = await mine(client, headers)
    # +50 verified and ×1.5 for the accurate category (booked as +25).
    assert me["balance"] == 75 and not me["anonymous"] and not me["paused"]
    assert {(h["reason"], h["delta"], h["tracking_code"]) for h in me["history"]} == {
        ("report_verified", 50, rep["tracking_code"]),
        ("accurate_category", 25, rep["tracking_code"]),
    }
    assert next(h for h in me["history"] if h["reason"] == "accurate_category")["multiplier"] == 1.5
    assert me["next_badge"] == {"level": "bronze", "threshold": 100, "missing_points": 25}
    assert me["badges"] == [] and me["daily_cap"] == 200
    assert "198" in me["safety_notice"]["fr"] and me["prizes_notice"]["ar"]

    # Replaying every event (cursor back to 0) and calling the engine again pays nothing more.
    await session.execute(text("UPDATE rewards.consumer_cursor SET last_id = 0"))
    await session.commit()
    await drain()
    async with get_system_sessionmaker()() as s, s.begin():
        assert await service.award_report(s, uuid.UUID(rep["id"])) == ["duplicate", "duplicate"]
    assert (await mine(client, headers))["balance"] == 75


async def test_anonymous_rejected_and_false_reports_earn_nothing(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, session: AsyncSession
) -> None:
    anon = device_headers()
    await accept_charter(client, anon)
    rep = await report(client, anon, sfax_place())
    await close(client, staff, await incident_of(client, staff, rep["id"]))

    citizen = await new_citizen(client, make_token)
    rejected = await report(client, citizen, sfax_place())
    r = await client.post(
        f"/api/v1/staff/reports/{rejected['id']}/status",
        json={"status": "rejected", "note": "بلاغ غير صحيح"},
        headers=staff(["operator"]),
    )
    assert r.status_code == 200, r.text
    false_alarm = await report(client, citizen, sfax_place())
    await close(client, staff, await incident_of(client, staff, false_alarm["id"]), outcome="false_alarm")
    await drain()

    me = await mine(client, anon)
    assert me["anonymous"] is True and me["balance"] == 0 and me["history"] == []
    assert (await mine(client, citizen))["balance"] == 0
    rows = await session.scalar(
        text("SELECT count(*) FROM rewards.points_ledger WHERE report_id = ANY(:ids)"),
        {"ids": [uuid.UUID(rep["id"]), uuid.UUID(rejected["id"]), uuid.UUID(false_alarm["id"])]},
    )
    assert rows == 0


async def test_once_per_incident_and_daily_cap(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = await new_citizen(client, make_token)
    first = await report(client, headers, sfax_place())
    incident_id = await incident_of(client, staff, first["id"])
    # More reports of the same incident by the same person earn nothing more (no reward for repeated reporting).
    for _ in range(2):
        again = await report(client, headers, sfax_place())
        await incident_of(client, staff, again["id"], incident_id)
    other = await new_citizen(client, make_token)
    medical = await report(client, other, sfax_place(), category="medical")
    await incident_of(client, staff, medical["id"], incident_id)
    await close(client, staff, incident_id)
    await drain()
    assert (await mine(client, headers))["balance"] == 75
    # Another verified reporter of the same incident; a different category than the incident's: no bonus.
    assert (await mine(client, other))["balance"] == 50

    monkeypatch.setattr(get_settings(), "rewards_daily_cap", 100)
    capped = await new_citizen(client, make_token)
    for _ in range(2):
        await verified_incident(client, staff, capped)
    await drain()
    me = await mine(client, capped)
    assert me["balance"] == 100
    assert any(h["capped"] for h in me["history"])
    # Rescues designated by staff are outside the cap.
    incident_id, rep = await verified_incident(client, staff, capped)
    await drain()
    r = await client.post(
        f"/api/v1/staff/rewards/interventions/{incident_id}/rescue",
        json={"report_ids": [rep["id"]], "note": "دلّ البلاغ على مكان العالقين"},
        headers=staff(["operator"]),
    )
    assert r.json()["awarded"] == [{"report_id": rep["id"], "status": "applied", "reason": None}]
    assert (await mine(client, capped))["balance"] == 600


async def test_rescue_flag_rules(client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory) -> None:
    headers = await new_citizen(client, make_token)
    rep = await report(client, headers, sfax_place())
    incident_id = await incident_of(client, staff, rep["id"])
    path = f"/api/v1/staff/rewards/interventions/{incident_id}/rescue"
    body = {"report_ids": [rep["id"]]}
    assert (await client.post(path, json=body, headers=staff(["operator"]))).json()[
        "detail"
    ] == "incident_not_evaluated"
    assert (await client.post(path, json=body, headers=staff(["local_committee"]))).status_code == 403
    assert (await client.post(path, json=body, headers=staff(["operator"], gouvernorat=11))).status_code == 404
    await close(client, staff, incident_id)
    first = (await client.post(path, json=body, headers=staff(["operator"]))).json()["awarded"][0]
    second = (await client.post(path, json=body, headers=staff(["operator"]))).json()["awarded"][0]
    assert (first["status"], second["status"]) == ("applied", "duplicate")

    anon = device_headers()
    await accept_charter(client, anon)
    anon_rep = await report(client, anon, sfax_place())
    anon_incident = await incident_of(client, staff, anon_rep["id"])
    await close(client, staff, anon_incident)
    r = await client.post(
        f"/api/v1/staff/rewards/interventions/{anon_incident}/rescue",
        json={"report_ids": [anon_rep["id"]]},
        headers=staff(["operator"]),
    )
    assert r.json()["awarded"][0] == {"report_id": anon_rep["id"], "status": "skipped", "reason": "not_eligible"}

    false_rep = await report(client, headers, sfax_place())
    false_incident = await incident_of(client, staff, false_rep["id"])
    await close(client, staff, false_incident, outcome="false_alarm")
    r = await client.post(
        f"/api/v1/staff/rewards/interventions/{false_incident}/rescue",
        json={"report_ids": [false_rep["id"]]},
        headers=staff(["operator"]),
    )
    assert r.json()["detail"] == "false_alarm"


async def test_paused_at_disaster_level_then_applied(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory
) -> None:
    headers = await new_citizen(client, make_token)
    rep = await report(client, headers, sfax_place())
    incident_id = await incident_of(client, staff, rep["id"])
    r = await client.post(
        "/api/v1/staff/levels",
        json={"gouvernorat_codes": [SFAX_CODE], "level": "disaster", "reason": "فيضانات واسعة"},
        headers=staff(["central_committee"], gouvernorat=None),
    )
    assert r.status_code == 200, r.text
    await close(client, staff, incident_id)
    await drain()
    me = await mine(client, headers)
    assert me["balance"] == 0 and me["pending_points"] == 75 and me["paused"] is True
    settings_out = (await client.get("/api/v1/staff/rewards/settings", headers=staff())).json()
    assert SFAX_CODE in settings_out["paused_gouvernorats"]

    r = await client.post(
        "/api/v1/staff/levels",
        json={"gouvernorat_codes": [SFAX_CODE], "level": "normal", "reason": "انتهاء الأزمة"},
        headers=staff(["central_committee"], gouvernorat=None),
    )
    assert r.status_code == 200, r.text
    await drain()
    me = await mine(client, headers)
    assert me["balance"] == 75 and me["pending_points"] == 0 and me["paused"] is False


# ---------------------------------------------------------------- badges, revocation, certificates


async def test_badges_confirmation_and_certificate(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, signing_key: None, fake_store: FakeStore
) -> None:
    headers = await new_citizen(client, make_token)
    cid = await citizen_id(client, headers)
    manager = staff(["ops_manager"])
    r = await client.post(
        f"/api/v1/staff/rewards/citizens/{cid}/adjust", json={"delta": 600, "reason": "تعويض نقاط"}, headers=manager
    )
    assert r.status_code == 200, r.text
    assert r.json()["balance"] == 600 and r.json()["badges"] == ["bronze"]
    me = await mine(client, headers)
    # Bronze is immediate; silver waits for a staff confirmation before it shows.
    assert [b["level"] for b in me["badges"]] == ["bronze"] and me["current_badge"] == "bronze"
    assert me["next_badge"]["level"] == "gold"
    pending = (await client.get("/api/v1/staff/rewards/badges?status=pending&limit=200", headers=manager)).json()
    silver = next(b for b in pending["items"] if b["citizen_id"] == cid)
    assert silver["level"] == "silver" and silver["balance"] == 600 and silver["pseudonym"].startswith("C-")
    assert (
        await client.post(f"/api/v1/staff/rewards/badges/{silver['id']}/confirm", headers=staff())
    ).status_code == 403
    r = await client.post(f"/api/v1/staff/rewards/badges/{silver['id']}/confirm", headers=manager)
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    again = await client.post(f"/api/v1/staff/rewards/badges/{silver['id']}/confirm", headers=manager)
    assert again.json()["detail"] == "invalid_transition"
    assert [b["level"] for b in (await mine(client, headers))["badges"]] == ["bronze", "silver"]

    await client.post(
        f"/api/v1/staff/rewards/citizens/{cid}/adjust",
        json={"delta": 1500, "reason": "مساهمة استثنائية"},
        headers=manager,
    )
    pending = (await client.get("/api/v1/staff/rewards/badges?status=pending&level=gold", headers=manager)).json()
    gold = next(b for b in pending["items"] if b["citizen_id"] == cid)
    # A certificate needs a confirmed gold/ambassador badge.
    r = await client.post("/api/v1/staff/rewards/certificates", json={"badge_award_id": gold["id"]}, headers=manager)
    assert r.json()["detail"] == "not_eligible"
    await client.post(f"/api/v1/staff/rewards/badges/{gold['id']}/confirm", headers=manager)
    r = await client.post("/api/v1/staff/rewards/certificates", json={"badge_award_id": gold["id"]}, headers=manager)
    assert r.status_code == 201, r.text
    cert = r.json()
    assert cert["initials"] == "A. B." and cert["distinction"] == "gold"
    assert cert["verify_url"].endswith(f"/api/v1/rewards/certificates/{cert['code']}")
    duplicate = await client.post(
        "/api/v1/staff/rewards/certificates", json={"badge_award_id": gold["id"]}, headers=manager
    )
    assert duplicate.json()["detail"] == "certificate_exists"
    pdf_key = f"rewards/certificates/{cert['id']}.pdf"
    assert fake_store.objects[pdf_key].startswith(b"%PDF")

    # Public verification: initials, distinction and date only (no name, no id, no gouvernorat).
    public = await client.get(f"/api/v1/rewards/certificates/{cert['code']}")
    assert public.status_code == 200
    body = public.json()
    assert set(body) == {"code", "valid", "initials", "distinction", "distinction_label", "date"}
    assert body["valid"] is True and body["initials"] == "A. B." and "Amine" not in public.text
    assert (await client.get("/api/v1/rewards/certificates/EHR-26-999999-ABCD")).status_code == 404
    assert (await client.get("/api/v1/rewards/certificates/not-a-code")).status_code == 422

    me = await mine(client, headers)
    assert [c["code"] for c in me["certificates"]] == [cert["code"]]
    download = await client.get(f"/api/v1/me/rewards/certificates/{cert['id']}", headers=headers)
    assert download.status_code == 302 and pdf_key in download.headers["location"]
    as_json = await client.get(
        f"/api/v1/staff/rewards/certificates/{cert['id']}/pdf", headers={**manager, "Accept": "application/json"}
    )
    assert as_json.status_code == 200 and pdf_key in as_json.json()["url"]
    other = await new_citizen(client, make_token)
    assert (await client.get(f"/api/v1/me/rewards/certificates/{cert['id']}", headers=other)).status_code == 404

    # Revoking the badge revokes its certificate: the verification then answers "not valid".
    r = await client.post(
        f"/api/v1/staff/rewards/badges/{gold['id']}/revoke", json={"reason": "خطأ في الإسناد"}, headers=manager
    )
    assert r.json()["status"] == "revoked"
    assert (await client.get(f"/api/v1/rewards/certificates/{cert['code']}")).json()["valid"] is False
    assert (await mine(client, headers))["certificates"] == []


async def test_ledger_revocation_and_append_only(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, session: AsyncSession
) -> None:
    headers = await new_citizen(client, make_token)
    await verified_incident(client, staff, headers)
    await drain()
    cid = await citizen_id(client, headers)
    manager = staff(["local_committee"])
    detail = (await client.get(f"/api/v1/staff/rewards/citizens/{cid}", headers=manager)).json()
    verified = next(h for h in detail["history"] if h["reason"] == "report_verified")
    path = f"/api/v1/staff/rewards/ledger/{verified['id']}/revoke"
    assert (await client.post(path, json={"reason": "x"}, headers=manager)).status_code == 422
    r = await client.post(path, json={"reason": "بلاغ تبيّن أنه مكرر"}, headers=manager)
    assert r.status_code == 200, r.text
    assert r.json()["balance"] == 25
    revoked = next(h for h in r.json()["history"] if h["id"] == verified["id"])
    assert revoked["revoked"] is True
    assert any(h["reason"] == "revocation" and h["delta"] == -50 for h in r.json()["history"])
    assert (await client.post(path, json={"reason": "مرة ثانية"}, headers=manager)).json()[
        "detail"
    ] == "already_revoked"
    assert (await mine(client, headers))["balance"] == 25

    # The ledger is append-only in the database itself.
    with pytest.raises(DBAPIError):
        await session.execute(
            text("UPDATE rewards.points_ledger SET delta = 5000 WHERE id = :id"), {"id": verified["id"]}
        )
    await session.rollback()
    audit_actions = set(
        await session.scalars(text("SELECT action FROM audit.log WHERE target = :t"), {"t": f"citizen:{cid}"})
    )
    assert "rewards.ledger.revoke" in audit_actions


async def test_volunteer_mission(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, session: AsyncSession
) -> None:
    from tests.test_operations import approved_volunteer

    place = sfax_place()
    reporter = await new_citizen(client, make_token)
    rep = await report(client, reporter, place)
    incident_id = await incident_of(client, staff, rep["id"])
    volunteer = bearer(
        make_token(roles=["citizen"], email=f"v{uuid.uuid4().hex[:8]}@example.tn", email_verified=True, name="V")
    )
    volunteer_id = await approved_volunteer(client, staff, volunteer, {**place, "accuracy_m": 10.0})
    operator = staff(["operator"])
    r = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/callouts",
        json={"skill": "first_aid", "requested": 1, "radius_km": 10, "volunteer_ids": [volunteer_id]},
        headers=operator,
    )
    assert r.status_code == 201, r.text
    callout = r.json()
    respond = f"/api/v1/me/callouts/{callout['id']}/respond"
    assert (
        await client.post(respond, json={"response": "accept", "eta_minutes": 5}, headers=volunteer)
    ).status_code == 200
    assert (await client.post(f"/api/v1/me/callouts/{callout['id']}/arrived", headers=volunteer)).status_code == 200
    await drain()
    # Being on scene earns nothing (safety rule T25); the completed mission does.
    assert (await mine(client, volunteer))["balance"] == 0
    incident = (await client.get(f"/api/v1/staff/incidents/{incident_id}", headers=operator)).json()
    assignment = next(a for a in incident["assignments"] if a["kind"] == "volunteer")
    r = await client.post(
        f"/api/v1/staff/assignments/{assignment['id']}/status", json={"status": "released"}, headers=operator
    )
    assert r.status_code == 200, r.text
    await drain()
    me = await mine(client, volunteer)
    assert me["balance"] == 100 and me["history"][0]["reason"] == "volunteer_mission"
    assert me["history"][0]["intervention_id"] == incident_id


# ---------------------------------------------------------------- rules, nominations, scope


async def test_rules_crud(client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory) -> None:
    national = staff(["central_committee"], gouvernorat=None)
    rules = (await client.get("/api/v1/staff/rewards/rules", headers=staff())).json()
    defaults = {r["reason"]: r for r in rules if r["is_default"]}
    assert defaults["report_verified"]["points"] == 50 and defaults["accurate_category"]["multiplier"] == 1.5
    assert defaults["report_helped_rescue"]["points"] == 500 and defaults["volunteer_mission"]["points"] == 100
    verified = defaults["report_verified"]
    path = f"/api/v1/staff/rewards/rules/{verified['id']}"
    regional = staff(["central_committee"], gouvernorat=SFAX_CODE)
    assert (await client.patch(path, json={"points": 80}, headers=regional)).json()[
        "detail"
    ] == "national_scope_required"
    assert (await client.patch(path, json={"points": 80}, headers=staff(["ops_manager"]))).status_code == 403
    # Phase 9 §2: reward rules are a central committee decision only (sysadmin removed).
    sysadmin = staff(["sysadmin"], gouvernorat=None)
    assert (await client.patch(path, json={"points": 80}, headers=sysadmin)).status_code == 403
    assert (await client.get("/api/v1/staff/rewards/rules", headers=sysadmin)).status_code == 403
    assert (await client.delete(path, headers=national)).json()["detail"] == "default_rule"
    assert (await client.patch(path, json={"multiplier": 2}, headers=national)).json()["detail"] == "invalid_rule"

    created = await client.post(
        "/api/v1/staff/rewards/rules",
        json={"reason": "report_verified", "category": "drowning", "points": 70},
        headers=national,
    )
    assert created.status_code == 201, created.text
    rule = created.json()
    try:
        headers = await new_citizen(client, make_token)
        await verified_incident(client, staff, headers, category="drowning")
        await drain()
        # 70 for drowning reports, ×1.5 accurate category → +35.
        assert (await mine(client, headers))["balance"] == 105
        r = await client.patch(f"/api/v1/staff/rewards/rules/{rule['id']}", json={"enabled": False}, headers=national)
        assert r.json()["enabled"] is False
        conflict = await client.post(
            "/api/v1/staff/rewards/rules",
            json={"reason": "report_verified", "category": "drowning", "points": 10},
            headers=national,
        )
        assert conflict.json()["detail"] == "rule_exists"
    finally:
        assert (await client.delete(f"/api/v1/staff/rewards/rules/{rule['id']}", headers=national)).status_code == 204


async def test_nominations_and_scope(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, signing_key: None, session: AsyncSession
) -> None:
    headers = await new_citizen(client, make_token)
    _, rep = await verified_incident(client, staff, headers)
    await drain()
    cid = await citizen_id(client, headers)
    proposer, decider = staff(["ops_manager"]), staff(["local_committee"])
    body = {
        "kind": "vigilant_citizen",
        "subject_kind": "citizen",
        "subject_id": cid,
        "year": 2026,
        "reason": "بلاغات دقيقة ساهمت في التدخل السريع",
        "evidence": {"report_ids": [rep["id"]], "intervention_ids": []},
    }
    wrong = {**body, "subject_kind": "org"}
    assert (await client.post("/api/v1/staff/rewards/nominations", json=wrong, headers=proposer)).status_code == 422
    outsider = staff(["ops_manager"], gouvernorat=11)
    assert (await client.post("/api/v1/staff/rewards/nominations", json=body, headers=outsider)).json()[
        "detail"
    ] == "subject_not_found"
    r = await client.post("/api/v1/staff/rewards/nominations", json=body, headers=proposer)
    assert r.status_code == 201, r.text
    nomination = r.json()
    assert nomination["status"] == "proposed" and nomination["subject_label"].startswith("C-")
    assert (await client.post("/api/v1/staff/rewards/nominations", json=body, headers=proposer)).json()[
        "detail"
    ] == "duplicate_nomination"
    approve = f"/api/v1/staff/rewards/nominations/{nomination['id']}/approve"
    assert (await client.post(approve, headers=proposer)).json()["detail"] == "same_reviewer"
    r = await client.post(approve, headers=decider)
    assert r.status_code == 200 and r.json()["status"] == "approved"
    cert = (
        await client.post(
            "/api/v1/staff/rewards/certificates", json={"nomination_id": nomination["id"]}, headers=decider
        )
    ).json()
    assert cert["distinction"] == "vigilant_citizen" and cert["year"] == 2026

    # Scope: another gouvernorat's staff sees neither the citizen, the nomination nor the certificate.
    reader = staff(["operator"], gouvernorat=11)
    assert (await client.get(f"/api/v1/staff/rewards/citizens/{cid}", headers=reader)).status_code == 404
    assert (
        await client.get(f"/api/v1/staff/rewards/nominations/{nomination['id']}", headers=reader)
    ).status_code == 404
    listed = (await client.get("/api/v1/staff/rewards/certificates?limit=200", headers=reader)).json()["items"]
    assert cert["id"] not in [c["id"] for c in listed]
    # Phase 9 §10: the national ranking needs national scope (403 out_of_scope).
    assert (await client.get("/api/v1/staff/rewards/leaderboard?scope=national", headers=reader)).json()[
        "detail"
    ] == "out_of_scope"
    assert (
        await client.get(f"/api/v1/staff/rewards/leaderboard?gouvernorat={SFAX_CODE}", headers=reader)
    ).status_code == 403
    assert (await client.get("/api/v1/staff/rewards/citizens", headers=device_headers())).status_code == 401
    citizen_token = await new_citizen(client, make_token)
    assert (await client.get("/api/v1/staff/rewards/citizens", headers=citizen_token)).status_code == 403

    # Pseudonyms by default; contact only on request, audited.
    sfax = staff(["operator"])
    page = (await client.get("/api/v1/staff/rewards/citizens?limit=200", headers=sfax)).json()
    item = next(i for i in page["items"] if i["citizen_id"] == cid)
    assert item["contact"] is None and item["balance"] == 75
    detail = (await client.get(f"/api/v1/staff/rewards/citizens/{cid}?with_contact=true", headers=sfax)).json()
    assert detail["contact"]["first_name"] == "Amine" and detail["contact"]["phone"].startswith("+216")
    logged = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'rewards.citizens.contact' AND details::text LIKE :c"),
        {"c": f"%{cid}%"},
    )
    assert logged == 1
    board = await client.get("/api/v1/staff/rewards/leaderboard?scope=gouvernorat", headers=sfax)
    assert board.status_code == 200
    assert "Amine" not in board.text and cid not in board.text
    assert any(i["pseudonym"] == item["pseudonym"] for i in board.json()["items"]) or len(board.json()["items"]) == 50
    national_board = await client.get(
        "/api/v1/staff/rewards/leaderboard?scope=national", headers=staff(["operator"], gouvernorat=None)
    )
    assert national_board.status_code == 200 and national_board.json()["gouvernorat_code"] is None


async def test_account_deletion_cascade(
    client: httpx.AsyncClient,
    staff: Staff,
    make_token: TokenFactory,
    signing_key: None,
    fake_store: FakeStore,
    session: AsyncSession,
) -> None:
    headers = await new_citizen(client, make_token)
    _, rep = await verified_incident(client, staff, headers)
    await drain()
    cid = await citizen_id(client, headers)
    manager, decider = staff(["ops_manager"]), staff(["central_committee"])
    await client.post(
        f"/api/v1/staff/rewards/citizens/{cid}/adjust",
        json={"delta": 2000, "reason": "مساهمة استثنائية"},
        headers=manager,
    )
    nomination = (
        await client.post(
            "/api/v1/staff/rewards/nominations",
            json={
                "kind": "vigilant_citizen",
                "subject_kind": "citizen",
                "subject_id": cid,
                "year": 2026,
                "reason": "سلوك مدني مثالي أثناء التدخل",
                "evidence": {"report_ids": [rep["id"]]},
            },
            headers=manager,
        )
    ).json()
    await client.post(f"/api/v1/staff/rewards/nominations/{nomination['id']}/approve", headers=decider)
    cert = (
        await client.post(
            "/api/v1/staff/rewards/certificates", json={"nomination_id": nomination["id"]}, headers=decider
        )
    ).json()

    exported = (await client.get("/api/v1/me/export", headers=headers)).json()["rewards"]
    assert exported["balance"] == 2075 and exported["nominations"][0]["kind"] == "vigilant_citizen"
    assert {b["level"] for b in exported["badges"]} == {"bronze", "silver", "gold"}

    r = await client.post("/api/v1/me/delete", json={"confirm": "DELETE"}, headers=headers)
    assert r.status_code == 202, r.text
    uid = uuid.UUID(cid)
    counts = (
        await session.execute(
            text(
                "SELECT (SELECT count(*) FROM rewards.points_ledger WHERE citizen_id = :u), "
                "(SELECT count(*) FROM rewards.badge_award WHERE citizen_id = :u), "
                "(SELECT count(*) FROM rewards.certificate WHERE subject_id = :u)"
            ),
            {"u": uid},
        )
    ).one()
    assert tuple(counts) == (0, 0, 0)
    row = (
        await session.execute(
            text("SELECT subject_id, reason, evidence, anonymised_at FROM rewards.nomination WHERE id = :id"),
            {"id": uuid.UUID(nomination["id"])},
        )
    ).one()
    assert row.subject_id is None and row.reason is None and row.evidence["report_ids"] == []
    assert row.anonymised_at is not None
    assert f"rewards/certificates/{cert['id']}.pdf" in fake_store.deleted
    # The public verification still answers with the same minimal data.
    public = (await client.get(f"/api/v1/rewards/certificates/{cert['code']}")).json()
    assert public["initials"] == "A. B." and public["valid"] is True
    audit_details = await session.scalar(
        text("SELECT details FROM audit.log WHERE action = 'user.delete' AND target = :t"), {"t": f"account:{cid}"}
    )
    assert audit_details["rewards_ledger_deleted"] == 2 + 1 and audit_details["rewards_nominations_anonymised"] == 1


async def test_retention_detaches_anonymised_reports(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, session: AsyncSession
) -> None:
    headers = await new_citizen(client, make_token)
    _, rep = await verified_incident(client, staff, headers)
    await drain()
    await session.execute(
        text("UPDATE reports.report SET updated_at = now() - interval '6 years' WHERE id = :id"), {"id": rep["id"]}
    )
    await session.commit()
    await retention.run_job(get_system_sessionmaker(), "reports", retention.anonymise_reports)
    await retention.run_job(get_system_sessionmaker(), "rewards_ledger", dict(retention.JOBS)["rewards_ledger"])
    linked = await session.scalar(
        text("SELECT count(*) FROM rewards.points_ledger WHERE report_id = :id"), {"id": uuid.UUID(rep["id"])}
    )
    assert linked == 0
    # The points stay with the citizen.
    assert (await mine(client, headers))["balance"] == 75
