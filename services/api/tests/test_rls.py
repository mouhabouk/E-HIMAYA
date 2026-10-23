"""Row-level security (phase 9 §9, migration 0025): raw SQL as the runtime role, whatever the API does.

Every test seeds its rows as the owner (not subject to the policies), then switches to the runtime role with
``SET LOCAL ROLE`` and a scope, inside one transaction that is always rolled back: nothing stays in the database.
Beja (31) is the caller's gouvernorat, Jendouba (32) its neighbour.
"""

import json
import os
import secrets
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.db import SYSTEM_SCOPE, DbScope, as_system, get_sessionmaker, get_system_sessionmaker
from app.core.db_roles import apply_runtime_grants

RUNTIME_ROLE = os.environ.get("DB_RUNTIME_ROLE", "").strip() or "ehimaya_app"
BEJA, JENDOUBA = 31, 32
SUBJECT = f"staff-{uuid.uuid4()}"


@dataclass
class Seed:
    user: uuid.UUID = field(default_factory=uuid.uuid4)
    other_user: uuid.UUID = field(default_factory=uuid.uuid4)
    ids: dict[str, uuid.UUID] = field(default_factory=dict)


@pytest.fixture
async def conn() -> AsyncIterator[AsyncConnection]:
    """An owner connection in an open transaction, rolled back at the end."""
    url = os.environ.get("MIGRATION_DATABASE_URL") or get_settings().database_url
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.connect() as c:
        if not (await c.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": RUNTIME_ROLE})).scalar():
            pytest.skip(f"runtime role {RUNTIME_ROLE} missing (infra/postgres/ehimaya-roles.sh)")
        await c.run_sync(apply_runtime_grants, RUNTIME_ROLE)
        await c.commit()
        tx = await c.begin()
        try:
            yield c
        finally:
            await tx.rollback()
    await engine.dispose()


def _keys(settings: dict[str, str]) -> dict[str, str]:
    return {"s": settings["scope"], "g": settings["gouvernorat"], "u": settings["subject"]}


async def scoped(c: AsyncConnection, scope: DbScope | None) -> None:
    await c.execute(text("RESET ROLE"))
    values = _keys(scope.settings()) if scope else {"s": "", "g": "", "u": ""}
    await c.execute(
        text(
            "SELECT set_config('ehimaya.scope', :s, true), set_config('ehimaya.gouvernorat', :g, true), "
            "set_config('ehimaya.subject', :u, true)"
        ),
        values,
    )
    await c.execute(text(f'SET LOCAL ROLE "{RUNTIME_ROLE}"'))


async def owner(c: AsyncConnection) -> None:
    await c.execute(text("RESET ROLE"))


async def _report(c: AsyncConnection, user: uuid.UUID, code: int | None, **extra: Any) -> uuid.UUID:
    rid = uuid.uuid4()
    columns = {
        "id": rid,
        "tracking_code": f"EH-{secrets.randbelow(90) + 10}-{secrets.randbelow(90) + 10}-{secrets.randbelow(10**7):07d}",
        "user_id": user,
        "category": "fire",
        "gouvernorat_code": code,
        "status": "received",
        **extra,
    }
    names = ", ".join(columns)
    values = ", ".join(f":{k}" for k in columns)
    await c.execute(
        text(
            f"INSERT INTO reports.report ({names}, location, created_at) "  # noqa: S608 (test seed, bound values)
            f"VALUES ({values}, CAST(ST_SetSRID(ST_MakePoint(9.18, 36.72), 4326) AS geography), now())"
        ),
        columns,
    )
    await c.execute(
        text("INSERT INTO reports.status_history (report_id, status, actor) VALUES (:r, 'received', 'test')"),
        {"r": rid},
    )
    return rid


async def _incident(c: AsyncConnection, code: int) -> uuid.UUID:
    iid = uuid.uuid4()
    await c.execute(
        text("INSERT INTO ops.incident (id, category, gouvernorat_code, status) VALUES (:i, 'fire', :g, 'open')"),
        {"i": iid, "g": code},
    )
    await c.execute(
        text("INSERT INTO ops.timeline_event (incident_id, kind, actor, payload) VALUES (:i, 'created', 'test', '{}')"),
        {"i": iid},
    )
    return iid


async def _unit(c: AsyncConnection, code: int) -> tuple[uuid.UUID, uuid.UUID]:
    unit, resource = uuid.uuid4(), uuid.uuid4()
    await c.execute(
        text(
            "INSERT INTO ops.unit (id, name_ar, name_fr, kind, gouvernorat_code, location) VALUES "
            "(:u, 'وحدة', 'Unité', 'unit', :g, CAST(ST_SetSRID(ST_MakePoint(9.18, 36.72), 4326) AS geography))"
        ),
        {"u": unit, "g": code},
    )
    await c.execute(
        text("INSERT INTO ops.resource (id, unit_id, kind, label) VALUES (:r, :u, 'fire_engine', 'RLS-1')"),
        {"r": resource, "u": unit},
    )
    return unit, resource


async def _call(c: AsyncConnection, code: int | None, status: str) -> uuid.UUID:
    cid = uuid.uuid4()
    await c.execute(
        text(
            "INSERT INTO telephony.call (id, channel_id, direction, gouvernorat_code, status) "
            "VALUES (:i, :ch, 'inbound', :g, :s)"
        ),
        {"i": cid, "ch": f"rls-{cid}", "g": code, "s": status},
    )
    return cid


async def _audit(c: AsyncConnection, gouvernorats: list[int]) -> int:
    details = json.dumps({"gouvernorats": gouvernorats, "rls": True})
    seq = await c.scalar(
        text("SELECT seq FROM audit.append('system', 'test.rls', NULL, NULL, CAST(:d AS jsonb))"), {"d": details}
    )
    return int(seq)


@pytest.fixture
async def seed(conn: AsyncConnection) -> Seed:
    data = Seed()
    for user in (data.user, data.other_user):
        await conn.execute(
            text("INSERT INTO identity.account (user_id, kind, keycloak_sub) VALUES (:u, 'citizen', :s)"),
            {"u": user, "s": f"rls-{user}"},
        )
    ids = data.ids
    ids["inc_beja"] = await _incident(conn, BEJA)
    ids["inc_shared"] = await _incident(conn, JENDOUBA)
    ids["inc_jendouba"] = await _incident(conn, JENDOUBA)
    await conn.execute(
        text(
            "INSERT INTO ops.incident_gouvernorat (incident_id, gouvernorat_code, role, added_by) "
            "VALUES (:i, :g, 'participating', 'test')"
        ),
        {"i": ids["inc_shared"], "g": BEJA},
    )
    ids["rep_beja"] = await _report(conn, data.user, BEJA, incident_id=ids["inc_beja"])
    ids["rep_shared"] = await _report(conn, data.other_user, JENDOUBA, incident_id=ids["inc_shared"])
    ids["rep_jendouba"] = await _report(conn, data.other_user, JENDOUBA)
    ids["rep_candidate"] = await _report(
        conn, data.other_user, None, geo_state="pending", geo_candidates=[BEJA, JENDOUBA]
    )
    ids["rep_granted"] = await _report(conn, data.other_user, JENDOUBA)
    await conn.execute(
        text(
            "INSERT INTO access.break_glass_grant (subject, target_kind, target_id, justification, expires_at) "
            "VALUES (:s, 'report', :t, 'Dossier transféré depuis Jendouba, lecture urgente.', "
            "now() + interval '10 minutes')"
        ),
        {"s": SUBJECT, "t": ids["rep_granted"]},
    )
    ids["unit_beja"], ids["res_beja"] = await _unit(conn, BEJA)
    ids["unit_jendouba"], ids["res_jendouba"] = await _unit(conn, JENDOUBA)
    ids["call_jendouba"] = await _call(conn, JENDOUBA, "ended")
    ids["call_ringing"] = await _call(conn, None, "ringing")
    ids["call_unlocated"] = await _call(conn, None, "ended")
    return data


BEJA_SCOPE = DbScope("gouvernorat", gouvernorat=BEJA, subject=SUBJECT)


async def _visible(c: AsyncConnection, table: str, ids: list[uuid.UUID]) -> set[uuid.UUID]:
    rows = await c.execute(
        text(f"SELECT id FROM {table} WHERE id = ANY(:ids)"),  # noqa: S608 (constant table names)
        {"ids": ids},
    )
    return {r[0] for r in rows}


async def test_regional_scope_sees_its_rows_only(conn: AsyncConnection, seed: Seed) -> None:
    ids = seed.ids
    await scoped(conn, BEJA_SCOPE)
    reports = await _visible(conn, "reports.report", [ids[k] for k in ids if k.startswith("rep_")])
    # Own, participating incident, candidate of a pending report, break-glass grant; not the neighbour's.
    assert reports == {ids["rep_beja"], ids["rep_shared"], ids["rep_candidate"], ids["rep_granted"]}
    incidents = await _visible(conn, "ops.incident", [ids["inc_beja"], ids["inc_shared"], ids["inc_jendouba"]])
    assert incidents == {ids["inc_beja"], ids["inc_shared"]}
    history = await conn.scalar(
        text("SELECT count(*) FROM reports.status_history WHERE report_id = ANY(:r)"),
        {"r": [ids["rep_beja"], ids["rep_jendouba"]]},
    )
    assert history == 1
    timeline = await conn.scalar(
        text("SELECT count(*) FROM ops.timeline_event WHERE incident_id = ANY(:i)"),
        {"i": [ids["inc_beja"], ids["inc_jendouba"]]},
    )
    assert timeline == 1
    assert await _visible(conn, "ops.unit", [ids["unit_beja"], ids["unit_jendouba"]]) == {ids["unit_beja"]}
    assert await _visible(conn, "ops.resource", [ids["res_beja"], ids["res_jendouba"]]) == {ids["res_beja"]}
    calls = await _visible(conn, "telephony.call", [ids["call_jendouba"], ids["call_ringing"], ids["call_unlocated"]])
    assert calls == {ids["call_ringing"]}  # the shared ringing queue only
    # Writes cannot reach what reads cannot.
    changed = await conn.execute(
        text("UPDATE reports.report SET status = 'rejected' WHERE id = :r"), {"r": ids["rep_jendouba"]}
    )
    assert changed.rowcount == 0  # type: ignore[attr-defined]
    deleted = await conn.execute(text("DELETE FROM ops.unit WHERE id = :u"), {"u": ids["unit_jendouba"]})
    assert deleted.rowcount == 0  # type: ignore[attr-defined]


async def test_expired_grant_and_other_subject(conn: AsyncConnection, seed: Seed) -> None:
    ids = seed.ids
    await scoped(conn, DbScope("gouvernorat", gouvernorat=BEJA, subject="somebody-else"))
    assert ids["rep_granted"] not in await _visible(conn, "reports.report", [ids["rep_granted"]])
    await owner(conn)
    await conn.execute(
        text(
            "UPDATE access.break_glass_grant SET granted_at = now() - interval '20 minutes', "
            "expires_at = now() - interval '1 minute' WHERE subject = :s"
        ),
        {"s": SUBJECT},
    )
    await scoped(conn, BEJA_SCOPE)
    assert await _visible(conn, "reports.report", [ids["rep_granted"]]) == set()
    # The holder still lists their own grant; another subject does not.
    assert await conn.scalar(text("SELECT count(*) FROM access.break_glass_grant WHERE subject = :s"), {"s": SUBJECT})
    await scoped(conn, DbScope("gouvernorat", gouvernorat=BEJA, subject="somebody-else"))
    assert not await conn.scalar(
        text("SELECT count(*) FROM access.break_glass_grant WHERE subject = :s"), {"s": SUBJECT}
    )


@pytest.mark.parametrize(
    "table",
    [
        "reports.report",
        "reports.status_history",
        "reports.media",
        "reports.escalation",
        "reports.reporter_context",
        "reports.live_stream",
        "ops.incident",
        "ops.timeline_event",
        "ops.assignment",
        "ops.callout",
        "ops.resource_request",
        "ops.unit",
        "ops.resource",
        "telephony.call",
        "audit.log",
        "access.break_glass_grant",
    ],
)
async def test_unset_scope_reads_nothing(conn: AsyncConnection, seed: Seed, table: str) -> None:
    await scoped(conn, None)
    assert await conn.scalar(text(f"SELECT count(*) FROM {table}")) == 0  # noqa: S608 (constant table names)
    await scoped(conn, SYSTEM_SCOPE)
    if table in ("reports.report", "ops.incident", "ops.unit", "telephony.call", "audit.log"):
        assert await conn.scalar(text(f"SELECT count(*) FROM {table}"))  # noqa: S608


async def test_unset_scope_cannot_insert(conn: AsyncConnection, seed: Seed) -> None:
    await scoped(conn, None)
    with pytest.raises(DBAPIError, match="row-level security"):
        await conn.execute(
            text("INSERT INTO ops.timeline_event (incident_id, kind, actor, payload) VALUES (:i, 'x', 'x', '{}')"),
            {"i": seed.ids["inc_beja"]},
        )


async def test_system_and_national_see_everything(conn: AsyncConnection, seed: Seed) -> None:
    every = [seed.ids[k] for k in seed.ids if k.startswith("rep_")]
    for scope in (SYSTEM_SCOPE, DbScope("national", subject=SUBJECT)):
        await scoped(conn, scope)
        assert await _visible(conn, "reports.report", every) == set(every)
        calls = [seed.ids[k] for k in seed.ids if k.startswith("call_")]
        assert await _visible(conn, "telephony.call", calls) == set(calls)


async def test_public_scope_own_reports(conn: AsyncConnection, seed: Seed) -> None:
    every = [seed.ids[k] for k in seed.ids if k.startswith("rep_")]
    await scoped(conn, DbScope.public(seed.user))
    assert await _visible(conn, "reports.report", every) == {seed.ids["rep_beja"]}
    assert await _visible(conn, "ops.incident", [seed.ids["inc_beja"]]) == set()
    assert await conn.scalar(text("SELECT count(*) FROM telephony.call")) == 0
    assert await conn.scalar(text("SELECT count(*) FROM reports.reporter_context")) == 0


async def test_reporter_context_other_gouvernorat(conn: AsyncConnection, seed: Seed) -> None:
    """Acceptance 20: where the reporter lives is never readable by another gouvernorat, nor by the reporter's own
    public scope; the room of the incident's location reads it (the API then decides whether to show it)."""
    ids = seed.ids
    for report_id in (ids["rep_beja"], ids["rep_jendouba"]):
        await conn.execute(
            text(
                "INSERT INTO reports.reporter_context (report_id, reporter_gouvernorat_code, source) "
                "VALUES (:r, :g, 'profile')"
            ),
            {"r": report_id, "g": JENDOUBA},
        )
    query = text("SELECT report_id FROM reports.reporter_context WHERE report_id = ANY(:r)")
    params = {"r": [ids["rep_beja"], ids["rep_jendouba"]]}
    await scoped(conn, BEJA_SCOPE)
    assert {r[0] for r in await conn.execute(query, params)} == {ids["rep_beja"]}
    await scoped(conn, DbScope("gouvernorat", gouvernorat=JENDOUBA, subject="jendouba"))
    assert {r[0] for r in await conn.execute(query, params)} == {ids["rep_jendouba"]}
    await scoped(conn, DbScope.public(seed.user))
    assert {r[0] for r in await conn.execute(query, params)} == set()


async def test_audit_scope_append_and_immutability(conn: AsyncConnection, seed: Seed) -> None:
    beja, jendouba, national = await _audit(conn, [BEJA]), await _audit(conn, [JENDOUBA]), await _audit(conn, [])
    await scoped(conn, BEJA_SCOPE)
    seen = {
        r[0]
        for r in await conn.execute(
            text("SELECT seq FROM audit.log WHERE seq = ANY(:s)"), {"s": [beja, jendouba, national]}
        )
    }
    assert seen == {beja}
    # A regional user still appends (national-only entries too) and the chain stays whole.
    appended = await conn.execute(
        text("SELECT seq, prev_hash FROM audit.append('staff:x', 'test.rls_regional', NULL, NULL, '{}')")
    )
    seq, prev_hash = appended.one()
    assert seq > national and prev_hash
    await conn.execute(text("INSERT INTO audit.log (actor, action) VALUES ('system', 'test.rls_direct')"))
    await owner(conn)
    assert await conn.scalar(text("SELECT audit.verify_chain()")) is None
    await scoped(conn, BEJA_SCOPE)
    with pytest.raises(DBAPIError, match="permission denied"):
        await conn.execute(text("UPDATE audit.log SET action = 'forged' WHERE seq = :s"), {"s": beja})


async def test_runtime_role_is_bound_by_policies(conn: AsyncConnection) -> None:
    row = (
        await conn.execute(
            text(
                "SELECT r.rolbypassrls, "
                "(SELECT bool_and(c.relrowsecurity AND NOT c.relforcerowsecurity) FROM pg_class c "
                " JOIN pg_namespace n ON n.oid = c.relnamespace "
                " WHERE (n.nspname, c.relname) IN (('reports', 'report'), ('ops', 'incident'), ('audit', 'log'), "
                "                                  ('telephony', 'call'), ('access', 'break_glass_grant'))) AS enabled "
                "FROM pg_roles r WHERE r.rolname = :r"
            ),
            {"r": RUNTIME_ROLE},
        )
    ).one()
    assert row.rolbypassrls is False and row.enabled is True


# ---------------------------------------------------------------- the application's sessions


async def test_sessions_carry_their_scope() -> None:
    query = text("SELECT current_setting('ehimaya.scope', true)")
    async with get_system_sessionmaker()() as s:
        assert await s.scalar(query) == "system"
    # Outside a request nothing is set: fail closed.
    async with get_sessionmaker()() as s:
        assert await s.scalar(query) == "none"
        async with as_system(s):
            assert await s.scalar(query) == "system"
            async with as_system(s), s.begin_nested():
                assert await s.scalar(query) == "system"
            assert await s.scalar(query) == "system"
        assert await s.scalar(query) == "none"


def test_worker_loops_and_clis_use_the_system_scope() -> None:
    from pathlib import Path

    import app.main

    root = Path(app.main.__file__).parent
    assert "start_worker_loops(get_system_sessionmaker())" in Path(app.main.__file__).read_text()
    for cli in sorted(root.glob("modules/*/cli.py")):
        source = cli.read_text()
        assert "get_sessionmaker(" not in source, cli


async def test_evidence_is_read_by_staff_and_written_by_the_system_only(conn: AsyncConnection) -> None:
    """Phase 10 §4.3: every staff scope reads the anchors; only the worker (system scope) seals them."""
    insert = text(
        "INSERT INTO evidence.anchor (seq, to_at, media_count, anchor_hash) "
        "VALUES ((SELECT coalesce(max(seq), 0) + 1 FROM evidence.anchor), now(), 0, :h)"
    )
    await scoped(conn, BEJA_SCOPE)
    await conn.scalar(text("SELECT count(*) FROM evidence.anchor"))
    with pytest.raises(DBAPIError, match="row-level security"):
        await conn.execute(insert, {"h": secrets.token_hex(32)})


async def test_map_layers_public_and_staff(conn: AsyncConnection) -> None:
    """Phase B1 (migration 0032): the app reads public, enabled layers and their visible places without a scope;
    staff layers, hidden places and imports need a staff scope; writes need the national or system scope."""
    await owner(conn)
    ids: dict[str, uuid.UUID] = {}
    for name, audience, enabled in (("pub", "public", True), ("staff", "staff", True), ("off", "public", False)):
        ids[name] = await conn.scalar(
            text(
                "INSERT INTO geo.layer (key, name, icon, colour, audience, enabled, created_by, updated_by) "
                "VALUES (:k, '{}', 'pin', '#2E7D32', :a, :e, 'x', 'x') RETURNING id"
            ),
            {"k": f"rls_{name}_{secrets.token_hex(4)}", "a": audience, "e": enabled},
        )
        for hidden in (False, True):
            await conn.execute(
                text(
                    "INSERT INTO geo.layer_feature (layer_id, ref, name, location, hidden) "
                    "VALUES (:l, :r, 'p', 'SRID=4326;POINT(9.18 36.72)', :h)"
                ),
                {"l": ids[name], "r": f"r{hidden}", "h": hidden},
            )
        await conn.execute(
            text(
                "INSERT INTO geo.layer_import (layer_id, file_name, sha256, format, mode, counts, base_version, "
                "created_by) VALUES (:l, 'f.csv', 'x', 'csv', 'merge', '{}', 0, 'x')"
            ),
            {"l": ids[name]},
        )
    mine = list(ids.values())

    async def counts() -> tuple[int, int, int]:
        layers = await conn.scalar(text("SELECT count(*) FROM geo.layer WHERE id = ANY(:i)"), {"i": mine})
        places = await conn.scalar(text("SELECT count(*) FROM geo.layer_feature WHERE layer_id = ANY(:i)"), {"i": mine})
        imports = await conn.scalar(text("SELECT count(*) FROM geo.layer_import WHERE layer_id = ANY(:i)"), {"i": mine})
        return layers or 0, places or 0, imports or 0

    await scoped(conn, None)
    assert await counts() == (1, 1, 0)
    await scoped(conn, DbScope("public", subject=str(uuid.uuid4())))
    assert await counts() == (1, 1, 0)
    await scoped(conn, BEJA_SCOPE)
    assert await counts() == (3, 6, 3)
    change = text("UPDATE geo.layer SET source = 'x' WHERE id = :i")
    assert (await conn.execute(change, {"i": ids["pub"]})).rowcount == 0
    with pytest.raises(DBAPIError, match="row-level security"):
        await conn.execute(
            text("INSERT INTO geo.layer_feature (layer_id, ref, name, location) VALUES (:l, 'n', 'n', 'POINT(9 36)')"),
            {"l": ids["pub"]},
        )


async def test_map_layers_written_by_central_staff(conn: AsyncConnection) -> None:
    await owner(conn)
    layer = await conn.scalar(
        text(
            "INSERT INTO geo.layer (key, name, icon, colour, created_by, updated_by) "
            "VALUES (:k, '{}', 'pin', '#2E7D32', 'x', 'x') RETURNING id"
        ),
        {"k": f"rls_w_{secrets.token_hex(4)}"},
    )
    await scoped(conn, DbScope("national", subject=SUBJECT))
    change = text("UPDATE geo.layer SET source = 'x' WHERE id = :i")
    assert (await conn.execute(change, {"i": layer})).rowcount == 1
