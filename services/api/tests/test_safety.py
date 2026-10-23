"""Personal safety between citizens (phase B2, docs/phase-b/design-b2.md): invitations and links, alerts to linked
contacts on the critical channel, live location links, safety checks fired by the server, row-level security and
retention."""

import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.db import DbScope, get_system_sessionmaker
from app.core.db_roles import apply_runtime_grants
from app.modules.safety import service
from app.modules.safety.models import SafetyCheck
from tests.conftest import TokenFactory, bearer, device_headers

RUNTIME_ROLE = os.environ.get("DB_RUNTIME_ROLE", "").strip() or "ehimaya_app"
POINT = {"lat": 36.8065, "lon": 10.1815, "accuracy_m": 12.0}


def _cin() -> str:
    return f"{secrets.randbelow(100_000_000):08d}"


def _phone() -> str:
    return f"+2162{secrets.randbelow(10_000_000):07d}"


async def _person(
    client: httpx.AsyncClient, make_token: TokenFactory, first_name: str, phone: str | None = None
) -> dict[str, str]:
    headers = bearer(make_token(roles=["citizen"]))
    phone = phone or _phone()
    profile = {
        "first_name": first_name,
        "last_name": "Test",
        "cin": _cin(),
        "phone": phone,
        "gouvernorat_code": 11,
        "delegation_id": 1101,
        "locale": "fr",
    }
    r = await client.put("/api/v1/me/profile", json=profile, headers=headers)
    assert r.status_code == 200, r.text
    return headers


async def _link(client: httpx.AsyncClient, inviter: dict[str, str], invitee: dict[str, str]) -> dict[str, Any]:
    code = (await client.post("/api/v1/safety/invitations", headers=inviter)).json()["code"]
    r = await client.post(f"/api/v1/safety/invitations/{code}/accept", headers=invitee)
    assert r.status_code == 201, r.text
    return r.json()


async def _pushes(session: AsyncSession, kind: str, ref: str) -> list[dict[str, Any]]:
    rows = await session.execute(
        text("SELECT user_id, payload FROM notify.outbox WHERE payload->>'type' = :k AND payload->'data'->>'id' = :r"),
        {"k": kind, "r": ref},
    )
    return [{"user_id": r.user_id, **r.payload} for r in rows]


async def _fire() -> int:
    async with get_system_sessionmaker()() as s, s.begin():
        return await service.fire_due_checks(s)


async def _check_row(check_id: str) -> tuple[str, uuid.UUID | None]:
    async with get_system_sessionmaker()() as s:
        row = await s.get(SafetyCheck, uuid.UUID(check_id))
        assert row is not None
        return row.status, row.alert_id


def _alert(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "client_uuid": str(uuid.uuid4()),
        "message": "J'ai besoin d'aide, appelez-moi",
        "location": POINT,
        "battery": 23,
    }
    body.update(overrides)
    return body


async def test_invitation_links_two_accounts_both_ways(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    amel_phone, karim_phone = _phone(), _phone()
    amel = await _person(client, make_token, "Amel", amel_phone)
    karim = await _person(client, make_token, "Karim", karim_phone)
    r = await client.post("/api/v1/safety/invitations", headers=amel)
    assert r.status_code == 201
    code = r.json()["code"]
    assert len(code) == 9 and code[4] == "-"
    # Only a keyed hash of the code is stored.
    stored = await session.scalar(
        text("SELECT count(*) FROM safety.invitation WHERE code_hash = :h"), {"h": code.encode()}
    )
    assert stored == 0

    preview = await client.get(f"/api/v1/safety/invitations/{code.lower().replace('-', ' ')}", headers=karim)
    assert preview.status_code == 200, preview.text
    assert preview.json()["first_name"] == "Amel" and preview.json()["phone_hint"] == f"•• •• •• {amel_phone[-2:]}"
    assert (await client.get(f"/api/v1/safety/invitations/{code}", headers=amel)).json()["detail"] == "own_invitation"

    link = await _link_with_code(client, code, karim)
    assert link["first_name"] == "Amel" and link["phone"] == amel_phone
    # The inviter is told; the other side sees the invitee.
    assert len(await _pushes(session, "safety_link", link["id"])) == 1
    mine = (await client.get("/api/v1/safety/links", headers=amel)).json()["items"]
    assert [(i["id"], i["first_name"], i["phone"]) for i in mine] == [(link["id"], "Karim", karim_phone)]

    # Single use.
    again = await client.post(f"/api/v1/safety/invitations/{code}/accept", headers=karim)
    assert again.status_code == 410 and again.json()["detail"] == "invitation_used"
    # A second invitation between the same people.
    r = await client.post(
        f"/api/v1/safety/invitations/{(await client.post('/api/v1/safety/invitations', headers=karim)).json()['code']}"
        "/accept",
        headers=amel,
    )
    assert r.status_code == 409 and r.json()["detail"] == "already_linked"

    # Either side removes it for both.
    assert (await client.delete(f"/api/v1/safety/links/{link['id']}", headers=karim)).status_code == 204
    assert (await client.get("/api/v1/safety/links", headers=amel)).json()["items"] == []


async def _link_with_code(client: httpx.AsyncClient, code: str, invitee: dict[str, str]) -> dict[str, Any]:
    r = await client.post(f"/api/v1/safety/invitations/{code}/accept", headers=invitee)
    assert r.status_code == 201, r.text
    return r.json()


async def test_invitation_rules(client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession) -> None:
    amel = await _person(client, make_token, "Amel")
    karim = await _person(client, make_token, "Karim")
    assert (await client.get("/api/v1/safety/invitations/0000-0000", headers=karim)).status_code == 404
    assert (await client.get("/api/v1/safety/invitations/not-a-code", headers=karim)).status_code == 404
    code = (await client.post("/api/v1/safety/invitations", headers=amel)).json()["code"]
    await session.execute(
        text("UPDATE safety.invitation SET expires_at = now() - interval '1 minute' WHERE code_hash = :h"),
        {"h": service.code_hash(code)},
    )
    await session.commit()
    r = await client.post(f"/api/v1/safety/invitations/{code}/accept", headers=karim)
    assert r.status_code == 410 and r.json()["detail"] == "invitation_expired"
    # A guest cannot link.
    guest = device_headers()
    assert (await client.post("/api/v1/safety/invitations", headers=guest)).json()["detail"] == "registration_required"
    # At most 5 open invitations.
    for _ in range(5):
        assert (await client.post("/api/v1/safety/invitations", headers=karim)).status_code == 201
    assert (await client.post("/api/v1/safety/invitations", headers=karim)).json()["detail"] == "too_many_invitations"


def test_code_normalisation() -> None:
    assert service.normalize_code("abcd efgh") == "ABCD-EFGH"
    assert service.normalize_code("O1IL-2345") == "0111-2345"
    assert service.normalize_code("ABCD-EFG") is None
    assert service.normalize_code("ABCD-EFGU") is None  # U is not in Crockford's alphabet
    for _ in range(20):
        code = service.new_code()
        assert service.normalize_code(code) == code


async def test_alert_rings_linked_contacts_and_reports_receipts(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    amel_phone = _phone()
    amel = await _person(client, make_token, "Amel", amel_phone)
    karim = await _person(client, make_token, "Karim")
    nour = await _person(client, make_token, "Nour")
    stranger = await _person(client, make_token, "Sami")
    to_karim = await _link(client, karim, amel)
    await _link(client, amel, nour)

    body = _alert()
    r = await client.post("/api/v1/safety/alerts", json=body, headers=amel)
    assert r.status_code == 201, r.text
    sent = r.json()
    assert sent["recipients"] == 2
    # The phone retries after a lost answer: same alert, no second ring.
    again = await client.post("/api/v1/safety/alerts", json=body, headers=amel)
    assert again.json()["id"] == sent["id"] and again.json()["recipients"] == 2
    pushes = await _pushes(session, "safety_alert", sent["id"])
    assert len(pushes) == 2
    for p in pushes:
        assert p["critical"] is True and p["data"]["redacted"] == "1"
        # No name, message or place in what Google or Apple carry.
        assert "Amel" not in str(p) and "aide" not in str(p) and "36.8" not in str(p)

    # Message and position are encrypted at rest.
    raw = (
        await session.execute(
            text("SELECT message_enc, position_enc FROM safety.alert WHERE id = :i"), {"i": sent["id"]}
        )
    ).one()
    assert b"aide" not in bytes(raw.message_enc) and b"36.8" not in bytes(raw.position_enc)

    seen_by_karim = (await client.get(f"/api/v1/safety/alerts/{sent['id']}", headers=karim)).json()
    assert seen_by_karim["sender_first_name"] == "Amel" and seen_by_karim["sender_phone"] == amel_phone
    assert seen_by_karim["message"] == body["message"] and seen_by_karim["battery"] == 23
    assert seen_by_karim["position"]["lat"] == POINT["lat"] and not seen_by_karim["seen"]
    assert seen_by_karim["recipients"] is None  # only the sender sees the receipts
    assert (await client.post(f"/api/v1/safety/alerts/{sent['id']}/seen", headers=karim)).status_code == 204
    own = (await client.get(f"/api/v1/safety/alerts/{sent['id']}", headers=amel)).json()
    assert own["mine"] and own["recipients"] == 2 and own["seen_by"] == 1
    assert [a["id"] for a in (await client.get("/api/v1/safety/alerts", headers=karim)).json()["items"]] == [sent["id"]]
    # Someone who is not a recipient sees nothing.
    assert (await client.get(f"/api/v1/safety/alerts/{sent['id']}", headers=stranger)).status_code == 404
    assert (await client.post(f"/api/v1/safety/alerts/{sent['id']}/seen", headers=stranger)).status_code == 404

    # Chosen recipients only (a group on the phone).
    only = await client.post("/api/v1/safety/alerts", json=_alert(link_ids=[to_karim["id"]]), headers=amel)
    assert only.json()["recipients"] == 1
    assert len(await _pushes(session, "safety_alert", only.json()["id"])) == 1
    assert (await client.get(f"/api/v1/safety/alerts/{only.json()['id']}", headers=karim)).status_code == 200
    assert (await client.get(f"/api/v1/safety/alerts/{only.json()['id']}", headers=nour)).status_code == 404
    r = await client.post("/api/v1/safety/alerts", json=_alert(link_ids=[str(uuid.uuid4())]), headers=amel)
    assert r.status_code == 422 and r.json()["detail"] == "unknown_link"
    r = await client.post("/api/v1/safety/alerts", json=_alert(), headers=stranger)
    assert r.status_code == 409 and r.json()["detail"] == "no_linked_contact"


async def test_alert_expires_for_the_receiver(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    amel = await _person(client, make_token, "Amel")
    karim = await _person(client, make_token, "Karim")
    await _link(client, karim, amel)
    sent = (await client.post("/api/v1/safety/alerts", json=_alert(location=None), headers=amel)).json()
    # The app's clock decides expiry: the past is taken from it, not from the database's now().
    expired = await session.scalar(
        text("UPDATE safety.alert SET expires_at = :t WHERE id = :i RETURNING id"),
        {"t": datetime.now(UTC) - timedelta(minutes=1), "i": uuid.UUID(sent["id"])},
    )
    await session.commit()
    assert expired is not None, sent
    r = await client.get(f"/api/v1/safety/alerts/{sent['id']}", headers=karim)
    assert r.status_code == 410 and r.json()["detail"] == "alert_expired"
    assert (await client.get("/api/v1/safety/alerts", headers=karim)).json()["items"] == []


async def test_live_location_link(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    amel = await _person(client, make_token, "Amel")
    karim = await _person(client, make_token, "Karim")
    stranger = await _person(client, make_token, "Sami")
    await _link(client, karim, amel)
    r = await client.post("/api/v1/safety/live", json={"minutes": 60}, headers=amel)
    assert r.status_code == 201, r.text
    share = r.json()
    expires = datetime.fromisoformat(share["expires_at"])
    assert timedelta(minutes=59) < expires - datetime.now(UTC) <= timedelta(minutes=60)
    assert (await client.post("/api/v1/safety/live", json={"minutes": 481}, headers=amel)).json()["detail"] == (
        "duration_too_long"
    )

    for i in range(3):
        moved = {**POINT, "lat": POINT["lat"] + i * 0.001}
        r = await client.put(
            f"/api/v1/safety/live/{share['id']}", json={"location": moved, "battery": 50 - i}, headers=amel
        )
        assert r.status_code == 200, r.text
    view = await client.post("/api/v1/live/view", json={"token": share["token"]})
    assert view.status_code == 200
    live = view.json()
    assert live["active"] and len(live["points"]) == 3 and live["battery"] == 48
    assert "Amel" not in view.text and "+216" not in view.text
    assert (await client.post("/api/v1/live/view", json={"token": "x" * 43})).status_code == 404

    # A linked contact follows it only through an alert pointing to it.
    assert (await client.get(f"/api/v1/safety/live/{share['id']}", headers=karim)).status_code == 404
    await client.post("/api/v1/safety/alerts", json=_alert(live_share_id=share["id"]), headers=amel)
    followed = await client.get(f"/api/v1/safety/live/{share['id']}", headers=karim)
    assert followed.status_code == 200 and len(followed.json()["points"]) == 3
    assert (await client.get(f"/api/v1/safety/live/{share['id']}", headers=stranger)).status_code == 404
    # Nobody else updates or stops it.
    assert (await client.post(f"/api/v1/safety/live/{share['id']}/stop", headers=karim)).status_code == 404

    stopped = (await client.post(f"/api/v1/safety/live/{share['id']}/stop", headers=amel)).json()
    assert not stopped["active"] and stopped["stopped_at"]
    assert not (await client.post("/api/v1/live/view", json={"token": share["token"]})).json()["active"]
    r = await client.put(f"/api/v1/safety/live/{share['id']}", json={"location": POINT}, headers=amel)
    assert r.status_code == 410 and r.json()["detail"] == "live_ended"


async def test_guest_can_share_live_location(client: httpx.AsyncClient) -> None:
    guest = device_headers()
    r = await client.post("/api/v1/safety/live", json={"minutes": 15}, headers=guest)
    assert r.status_code == 201, r.text


async def test_safety_check_fires_once_when_not_answered(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    amel = await _person(client, make_token, "Amel")
    karim = await _person(client, make_token, "Karim")
    await _link(client, karim, amel)
    body = {"minutes": 30, "message": "Randonnée au Boukornine, retour prévu à 18 h", "location": POINT, "battery": 80}
    r = await client.post("/api/v1/safety/checks", json=body, headers=amel)
    assert r.status_code == 201, r.text
    check = r.json()
    assert check["status"] == "active" and check["contacts"] == 1
    assert (await client.post("/api/v1/safety/checks", json=body, headers=amel)).json()["detail"] == "check_active"
    moved = {**POINT, "lat": 36.7}
    r = await client.put(
        f"/api/v1/safety/checks/{check['id']}/position", json={"location": moved, "battery": 41}, headers=amel
    )
    assert r.status_code == 200

    # Not due yet: nothing happens.
    await _fire()
    assert await _check_row(check["id"]) == ("active", None)

    await session.execute(
        text("UPDATE safety.safety_check SET due_at = now() - interval '1 second' WHERE id = :i"), {"i": check["id"]}
    )
    await session.commit()
    assert await _fire() >= 1
    status, alert_id = await _check_row(check["id"])
    assert status == "fired" and alert_id is not None
    # Fired once only.
    await _fire()
    assert await _check_row(check["id"]) == ("fired", alert_id)
    row = SafetyCheck(alert_id=alert_id)
    alert = (await client.get(f"/api/v1/safety/alerts/{row.alert_id}", headers=karim)).json()
    assert alert["kind"] == "check" and alert["message"] == body["message"]
    assert alert["position"]["lat"] == 36.7 and alert["battery"] == 41
    assert len(await _pushes(session, "safety_alert", str(row.alert_id))) == 1
    assert len(await _pushes(session, "safety_check_fired", check["id"])) == 1
    current = (await client.get("/api/v1/safety/checks/current", headers=amel)).json()
    assert current["status"] == "fired" and current["alert_id"] == str(row.alert_id)


async def test_safety_check_answered_or_extended(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    amel = await _person(client, make_token, "Amel")
    body = {"minutes": 60, "message": "Travail de nuit"}
    assert (await client.post("/api/v1/safety/checks", json={**body, "minutes": 25 * 60}, headers=amel)).json()[
        "detail"
    ] == "duration_too_long"
    check = (await client.post("/api/v1/safety/checks", json=body, headers=amel)).json()
    assert check["contacts"] == 0
    longer = (
        await client.post(f"/api/v1/safety/checks/{check['id']}/extend", json={"minutes": 30}, headers=amel)
    ).json()
    assert datetime.fromisoformat(longer["due_at"]) - datetime.fromisoformat(check["due_at"]) == timedelta(minutes=30)
    r = await client.post(f"/api/v1/safety/checks/{check['id']}/extend", json={"minutes": 24 * 60}, headers=amel)
    assert r.json()["detail"] == "duration_too_long"
    ok = (await client.post(f"/api/v1/safety/checks/{check['id']}/ok", headers=amel)).json()
    assert ok["status"] == "ok"
    assert (await client.post(f"/api/v1/safety/checks/{check['id']}/ok", headers=amel)).json()["detail"] == "check_ok"
    other = await _person(client, make_token, "Sami")
    assert (await client.post(f"/api/v1/safety/checks/{check['id']}/ok", headers=other)).status_code == 404


async def test_row_level_security_of_safety(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    """Raw SQL as the runtime role: staff scopes read nothing; sender and recipient read their own alert only."""
    amel = await _person(client, make_token, "Amel")
    karim = await _person(client, make_token, "Karim")
    await _link(client, karim, amel)
    sent = (await client.post("/api/v1/safety/alerts", json=_alert(), headers=amel)).json()
    sender, recipient = (
        await session.execute(
            text(
                "SELECT a.sender_id, r.recipient_id FROM safety.alert a "
                "JOIN safety.alert_recipient r ON r.alert_id = a.id WHERE a.id = :i"
            ),
            {"i": sent["id"]},
        )
    ).one()
    url = os.environ.get("MIGRATION_DATABASE_URL") or get_settings().database_url
    engine = create_async_engine(url, poolclass=NullPool)
    tables = ("invitation", "link", "alert", "alert_recipient", "live_share", "safety_check")
    try:
        async with engine.connect() as c:
            if not (await c.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": RUNTIME_ROLE})).scalar():
                pytest.skip(f"runtime role {RUNTIME_ROLE} missing")
            await c.run_sync(apply_runtime_grants, RUNTIME_ROLE)
            await c.commit()

            async def count(scope: DbScope, sql: str) -> int:
                await c.execute(text("RESET ROLE"))
                values = scope.settings()
                await c.execute(
                    text(
                        "SELECT set_config('ehimaya.scope', :scope, true), "
                        "set_config('ehimaya.gouvernorat', :gouvernorat, true), "
                        "set_config('ehimaya.subject', :subject, true)"
                    ),
                    values,
                )
                await c.execute(text(f'SET LOCAL ROLE "{RUNTIME_ROLE}"'))
                return int((await c.execute(text(sql), {"i": sent["id"]})).scalar_one())

            async with c.begin():
                for staff in (
                    DbScope("national", subject="ops-1"),
                    DbScope("gouvernorat", gouvernorat=11, subject="ops-2"),
                ):
                    for table in tables:
                        assert await count(staff, f"SELECT count(*) FROM safety.{table}") == 0  # noqa: S608
                one = "SELECT count(*) FROM safety.alert WHERE id = :i"
                assert await count(DbScope.public(sender), one) == 1
                assert await count(DbScope.public(recipient), one) == 1
                assert await count(DbScope.public(uuid.uuid4()), one) == 0
                # The sender does not read the recipient rows directly (the API reads receipts with the system scope).
                receipts = "SELECT count(*) FROM safety.alert_recipient WHERE alert_id = :i"
                assert await count(DbScope.public(recipient), receipts) == 1
                assert await count(DbScope.public(sender), receipts) == 0
                await c.rollback()
    finally:
        await engine.dispose()


async def test_retention_of_safety_rows(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    amel = await _person(client, make_token, "Amel")
    karim = await _person(client, make_token, "Karim")
    await _link(client, karim, amel)
    sent = (await client.post("/api/v1/safety/alerts", json=_alert(), headers=amel)).json()
    share = (await client.post("/api/v1/safety/live", json={"minutes": 15}, headers=amel)).json()
    later = datetime.now(UTC) + timedelta(days=8)
    settings = get_settings()
    async with get_system_sessionmaker()() as s, s.begin():
        await service.purge_alerts(s, settings, datetime.now(UTC))
        assert await s.scalar(text("SELECT count(*) FROM safety.alert WHERE id = :i"), {"i": sent["id"]}) == 1
        while await service.purge_alerts(s, settings, later):
            pass
        while await service.purge_live_shares(s, settings, later):
            pass
        assert await s.scalar(text("SELECT count(*) FROM safety.alert WHERE id = :i"), {"i": sent["id"]}) == 0
        assert await s.scalar(text("SELECT count(*) FROM safety.live_share WHERE id = :i"), {"i": share["id"]}) == 0
