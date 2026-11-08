# covers: NFR-06
"""The change journal ("mouchard", migration 0097): every insert, update and delete, who made it, what changed."""

import os
import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit import journal
from tests.conftest import STAFF_ISS, TokenFactory, bearer
from tests.test_orgs import Staff, User, active_org, card, register
from tests.test_orgs import user as user


def admin(make_token: TokenFactory, role: str = "sysadmin", **claims: Any) -> dict[str, str]:
    claims.setdefault("scope_level", "national")
    return bearer(make_token(issuer=STAFF_ISS, roles=[role], **claims))


async def test_every_table_is_journaled_or_excluded(session: AsyncSession) -> None:
    rows = await session.execute(
        text(
            "SELECT n.nspname || '.' || c.relname AS name, "
            "EXISTS (SELECT 1 FROM pg_trigger t WHERE t.tgrelid = c.oid AND t.tgname = 'zz_journal') AS journaled "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE c.relkind IN ('r', 'p') AND NOT c.relispartition "
            "AND n.nspname NOT IN ('public', 'information_schema', 'tiger', 'topology', 'pg_catalog', 'pg_toast') "
            "AND n.nspname NOT LIKE 'pg\\_%'"
        )
    )
    missing = sorted(r.name for r in rows if not r.journaled and r.name not in journal.EXCLUDED)
    assert missing == [], f"tables without the change journal: call audit.journal_attach() for {missing}"


async def test_trigger_keeps_values_but_hides_personal_columns(session: AsyncSession) -> None:
    await session.execute(text("SELECT set_config('ehimaya.actor', 'ehimaya-staff:tester', true)"))
    await session.execute(text("SELECT set_config('ehimaya.actor_name', 'Agent Test', true)"))
    await session.execute(text("SELECT set_config('ehimaya.request_id', 'req-journal-1', true)"))
    key = f"journal_{uuid.uuid4().hex[:8]}"
    await session.execute(
        text("INSERT INTO platform.setting (key, value) VALUES (:k, CAST(:v AS jsonb))"), {"k": key, "v": '{"a": 1}'}
    )
    await session.execute(
        text("UPDATE platform.setting SET value = CAST(:v AS jsonb) WHERE key = :k"), {"k": key, "v": '{"a": 2}'}
    )
    await session.execute(text("UPDATE platform.setting SET value = value WHERE key = :k"), {"k": key})
    await session.execute(text("DELETE FROM platform.setting WHERE key = :k"), {"k": key})
    rows = (
        await session.execute(
            text(
                "SELECT op, actor, actor_name, request_id, row_key, columns, hidden, old_values, new_values "
                "FROM audit.change WHERE schema_name = 'platform' AND table_name = 'setting' "
                "AND row_key ->> 'key' = :k ORDER BY id"
            ),
            {"k": key},
        )
    ).all()
    await session.commit()
    # The no-op update leaves no entry.
    assert [r.op for r in rows] == ["I", "U", "D"]
    insert, update, delete = rows
    assert insert.actor == "ehimaya-staff:tester" and insert.actor_name == "Agent Test"
    assert insert.request_id == "req-journal-1" and insert.row_key == {"key": key}
    assert insert.old_values is None and delete.new_values is None
    assert update.columns[0] == "value" or "value" in update.columns
    assert update.old_values["value"] == {"a": 1} and update.new_values["value"] == {"a": 2}


async def test_hidden_columns_and_personal_schemas(session: AsyncSession) -> None:
    assert await session.scalar(text("SELECT audit.journal_hidden('phone')"))
    assert await session.scalar(text("SELECT audit.journal_hidden('text_original_enc')"))
    assert await session.scalar(text("SELECT audit.journal_hidden('display_name')"))
    assert not await session.scalar(text("SELECT audit.journal_hidden('status')"))
    assert not await session.scalar(text("SELECT audit.journal_hidden('gouvernorat_code')"))
    # Personal schemas: the trigger is told to keep no value at all.
    args = await session.scalar(
        text(
            "SELECT encode(t.tgargs, 'escape') FROM pg_trigger t WHERE t.tgname = 'zz_journal' "
            "AND t.tgrelid = 'identity.account'::regclass"
        )
    )
    assert args is not None and "true" in args


async def test_runtime_role_cannot_rewrite_the_journal(session: AsyncSession) -> None:
    role = os.environ.get("DB_RUNTIME_ROLE", "").strip() or "ehimaya_app"
    exists = await session.scalar(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role})
    if not exists:
        pytest.skip("single-role database")
    await session.execute(text(f'SET LOCAL ROLE "{role}"'))
    for statement in ("UPDATE audit.change SET actor = 'forged'", "DELETE FROM audit.change"):
        with pytest.raises(DBAPIError, match="permission denied"):
            async with session.begin_nested():
                await session.execute(text(statement))
    with pytest.raises(DBAPIError):
        async with session.begin_nested():
            await session.execute(
                text("INSERT INTO audit.change (actor, schema_name, table_name, op) VALUES ('x', 'a', 'b', 'I')")
            )
    await session.rollback()


async def test_admin_window_names_staff_and_masks_public_accounts(
    client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff, user: User
) -> None:
    owner = user()
    org = await register(client, owner, **{"name": "Journal Test"})
    body = card(identifier=org["identifier"], capacity=55, version=org["version"])
    r = await client.put(f"/api/v1/orgs/{org['id']}", json=body, headers=owner)
    assert r.status_code == 200, r.text
    headers = admin(make_token, name="Sys Admin")
    r = await client.get("/api/v1/admin/changes", params={"schema": "org", "table": "organization"}, headers=headers)
    assert r.status_code == 200, r.text
    mine = [c for c in r.json()["items"] if c["row_key"].get("id") == org["id"]]
    assert {c["op"] for c in mine} >= {"I", "U"}
    update = next(c for c in mine if c["op"] == "U" and "capacity" in c["columns"])
    assert update["actor_kind"] == "public" and update["actor"].startswith("public-")
    assert update["actor_name"] is None
    assert update["old_values"]["capacity"] == 40 and update["new_values"]["capacity"] == 55
    # The name and address of the institution and its manager were never stored.
    insert = next(c for c in mine if c["op"] == "I")
    assert {"name", "address", "manager", "contact_phone", "location"} <= set(insert["hidden"])
    assert not {"name", "address", "manager", "contact_phone"} & set(insert["new_values"])
    assert insert["new_values"]["kind"] == "commercial"
    # The same request id ties the change to the logs; filters by it and by the pseudonym work.
    by_request = await client.get("/api/v1/admin/changes", params={"request_id": update["request_id"]}, headers=headers)
    assert any(c["id"] == update["id"] for c in by_request.json()["items"])
    by_actor = await client.get("/api/v1/admin/changes", params={"actor": update["actor"]}, headers=headers)
    assert by_actor.json()["items"] and all(c["actor"] == update["actor"] for c in by_actor.json()["items"])
    by_row = await client.get("/api/v1/admin/changes", params={"row": org["id"]}, headers=headers)
    assert {c["id"] for c in mine} <= {c["id"] for c in by_row.json()["items"]}
    summary = await client.get("/api/v1/admin/changes/summary", headers=headers)
    assert summary.status_code == 200 and summary.json()["total"] >= 2
    assert "org.organization" in summary.json()["tables"]
    # Reading is audited.
    audit = await client.get("/api/v1/admin/audit", params={"limit": 3}, headers=admin(make_token, "security_admin"))
    assert any(e["action"] == "journal.read" for e in audit.json())


async def test_admin_window_is_national_and_technical(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    assert (await client.get("/api/v1/admin/changes", headers=admin(make_token, "security_admin"))).status_code == 200
    regional = bearer(make_token(issuer=STAFF_ISS, roles=["sysadmin"], gouvernorat_code="61"))
    assert (await client.get("/api/v1/admin/changes", headers=regional)).status_code == 403
    operator = bearer(make_token(issuer=STAFF_ISS, roles=["ops_manager"], scope_level="national"))
    assert (await client.get("/api/v1/admin/changes", headers=operator)).status_code == 403


async def test_org_admin_follows_the_changes_of_their_institution(
    client: httpx.AsyncClient, staff: Staff, user: User
) -> None:
    owner = user()
    org_id = await active_org(client, staff, owner)
    current = (await client.get(f"/api/v1/orgs/{org_id}", headers=owner)).json()
    body = card(identifier=current["identifier"], capacity=70, version=current["version"])
    r = await client.put(f"/api/v1/orgs/{org_id}", json=body, headers=owner)
    assert r.status_code == 200, r.text
    r = await client.get(f"/api/v1/orgs/{org_id}/changes", headers=owner)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items and {i["table_name"] for i in items} >= {"organization", "member"}
    by = {i["by"] for i in items}
    # The owner's own changes carry their name; the auditor's approval is the civil protection's, unnamed.
    assert "member" in by and "civil_protection" in by
    mine = next(
        i
        for i in items
        if i["by"] == "member" and i["op"] == "U" and i["table_name"] == "organization" and "capacity" in i["columns"]
    )
    assert mine["by_name"] and mine["by_name"].startswith("User ")
    assert all(i["by_name"] is None for i in items if i["by"] == "civil_protection")
    # Another institution's admin sees nothing of it.
    other = user()
    assert (await client.get(f"/api/v1/orgs/{org_id}/changes", headers=other)).status_code == 404
