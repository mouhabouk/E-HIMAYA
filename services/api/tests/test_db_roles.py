"""A4: the API's runtime database role can read and append to the audit log but never rewrite it.

Production runs two roles (infra/postgres/ehimaya-roles.sh): the owner runs the migrations, the runtime role
(DB_RUNTIME_ROLE, default ehimaya_app) serves requests. These tests switch to the runtime role with SET ROLE on an
owner connection, so they need no second password. The role is created here when absent (a superuser or CREATEROLE
test login); in CI and in compose the database image creates it at first start.
"""

import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.db_roles import apply_runtime_grants

RUNTIME_ROLE = os.environ.get("DB_RUNTIME_ROLE", "").strip() or "ehimaya_app"


@pytest.fixture(scope="module")
async def owner() -> AsyncIterator[AsyncConnection]:
    """A connection as the database owner, with the runtime role present and granted."""
    url = os.environ.get("MIGRATION_DATABASE_URL") or get_settings().database_url
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.connect() as conn:
        exists = (await conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": RUNTIME_ROLE})).scalar()
        if not exists:
            try:
                await conn.execute(text(f'CREATE ROLE "{RUNTIME_ROLE}" NOLOGIN'))
                await conn.execute(text(f'GRANT "{RUNTIME_ROLE}" TO current_user WITH INHERIT FALSE, SET TRUE'))
            except DBAPIError as exc:
                pytest.fail(
                    f"runtime role {RUNTIME_ROLE} is missing and this test login cannot create it ({exc.orig}); "
                    "run infra/postgres/ehimaya-roles.sh as the postgres superuser"
                )
        await conn.run_sync(apply_runtime_grants, RUNTIME_ROLE)
        await conn.commit()
        yield conn
    await engine.dispose()


async def _as_runtime(conn: AsyncConnection, statement: str) -> None:
    """Run ``statement`` as the runtime role inside a transaction that is always rolled back."""
    await conn.rollback()
    async with conn.begin() as tx:
        try:
            await conn.execute(text(f'SET LOCAL ROLE "{RUNTIME_ROLE}"'))
            await conn.execute(text(statement))
        finally:
            await tx.rollback()


async def test_runtime_role_is_not_privileged(owner: AsyncConnection) -> None:
    row = (
        await owner.execute(
            text(
                "SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls, "
                "pg_has_role(:r, current_user, 'MEMBER') AS member_of_owner FROM pg_roles WHERE rolname = :r"
            ),
            {"r": RUNTIME_ROLE},
        )
    ).one()
    assert not any(row), row
    owned = (
        await owner.execute(
            text(
                "SELECT count(*) FROM pg_class c JOIN pg_roles r ON r.oid = c.relowner WHERE r.rolname = :r "
                "UNION ALL SELECT count(*) FROM pg_namespace n JOIN pg_roles r ON r.oid = n.nspowner "
                "WHERE r.rolname = :r"
            ),
            {"r": RUNTIME_ROLE},
        )
    ).scalars()
    assert list(owned) == [0, 0]
    await owner.rollback()


async def test_runtime_role_reads_and_appends_audit(owner: AsyncConnection) -> None:
    await owner.rollback()
    async with owner.begin() as tx:
        await owner.execute(text(f'SET LOCAL ROLE "{RUNTIME_ROLE}"'))
        await owner.execute(text("INSERT INTO audit.log (actor, action) VALUES ('system', 'test.runtime_role')"))
        count = text("SELECT count(*) FROM audit.log WHERE action = 'test.runtime_role'")
        # Row-level security (0025): without a scope the runtime role reads nothing, with ``system`` everything.
        assert (await owner.execute(count)).scalar() == 0
        await owner.execute(text("SELECT set_config('ehimaya.scope', 'system', true)"))
        assert (await owner.execute(count)).scalar()
        # Ordinary application tables: full DML (checked without changing data).
        await owner.execute(text("UPDATE reports.report SET status = status WHERE false"))
        await owner.execute(text("DELETE FROM reports.report WHERE false"))
        await tx.rollback()


@pytest.mark.parametrize(
    ("statement", "message"),
    [
        ("UPDATE audit.log SET action = 'forged'", "permission denied for table log"),
        ("DELETE FROM audit.log", "permission denied for table log"),
        ("TRUNCATE audit.log", "permission denied for table log"),
        ("ALTER TABLE audit.log DISABLE TRIGGER trg_audit_log_no_update", "must be owner of table log"),
        ("ALTER TABLE audit.log DISABLE TRIGGER ALL", "must be owner of table log"),
        ("DROP TRIGGER trg_audit_log_chain ON audit.log", "must be owner of (table|relation) log"),
        (
            "CREATE OR REPLACE FUNCTION audit.log_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            "RETURN NULL; END $$",
            "permission denied for schema audit|must be owner of function",
        ),
        ("TRUNCATE reports.report", "permission denied for table report"),
        ("ALTER TABLE reports.report ADD COLUMN forged int", "must be owner of table report"),
        ("CREATE TABLE audit.shadow (id int)", "permission denied for schema audit"),
        ("CREATE TABLE public.shadow (id int)", "permission denied for schema public"),
        ("SET session_replication_role = replica", "permission denied to set parameter"),
    ],
)
async def test_runtime_role_cannot_tamper(owner: AsyncConnection, statement: str, message: str) -> None:
    with pytest.raises(DBAPIError, match=message):
        await _as_runtime(owner, statement)


async def test_runtime_role_covers_every_table(owner: AsyncConnection) -> None:
    """Every table of every migration (including retention/erasure targets) is writable, audit only appendable."""
    rows = (
        await owner.execute(
            text(
                "SELECT n.nspname || '.' || c.relname AS name, n.nspname = 'audit' AS audit, "
                "has_table_privilege(:r, c.oid, 'SELECT') AS s, has_table_privilege(:r, c.oid, 'INSERT') AS i, "
                "has_table_privilege(:r, c.oid, 'UPDATE') AS u, has_table_privilege(:r, c.oid, 'DELETE') AS d, "
                "has_table_privilege(:r, c.oid, 'TRUNCATE') AS trunc "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace JOIN pg_roles o ON o.oid = n.nspowner "
                "WHERE c.relkind IN ('r', 'p') AND o.rolname = current_user AND n.nspname <> 'public'"
            ),
            {"r": RUNTIME_ROLE},
        )
    ).all()
    await owner.rollback()
    assert len(rows) > 20
    for row in rows:
        expected = (True, True, False, False) if row.audit else (True, True, True, True)
        assert (row.s, row.i, row.u, row.d) == expected, row.name
        assert not row.trunc, row.name
    names = {row.name for row in rows}
    assert {"events.outbox", "identity.account", "identity.consent", "reports.media", "audit.log"} <= names
