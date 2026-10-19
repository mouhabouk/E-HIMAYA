"""Privileges of the API's runtime database role (A4).

Two roles share the database (infra/postgres/ehimaya-roles.sh creates them):
  - the owner (MIGRATION_DATABASE_URL) owns the database and every schema, runs the migrations and applies the grants
    below after each of them;
  - the runtime role (DATABASE_URL, name in DB_RUNTIME_ROLE) gets SELECT/INSERT/UPDATE/DELETE on the application
    tables and only SELECT/INSERT on the audit schema. It owns nothing, so it can never ALTER a table, TRUNCATE,
    DISABLE TRIGGER or rewrite the hash chain of audit.log.
ALTER DEFAULT PRIVILEGES gives the same rights on tables later migrations create in existing schemas; a migration
that creates a new schema is covered because the grants are re-applied after every `alembic upgrade`.
"""

import re

from sqlalchemy import Connection, text

# Append-only schemas: the runtime role may read and append, never change or remove.
APPEND_ONLY_SCHEMAS = frozenset({"audit"})
_ROLE_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def _owned_schemas(connection: Connection) -> list[str]:
    rows = connection.execute(
        text(
            "SELECT n.nspname FROM pg_namespace n JOIN pg_roles r ON r.oid = n.nspowner "
            "WHERE r.rolname = current_user AND n.nspname <> 'public' "
            "AND n.nspname NOT LIKE 'pg\\_%' AND n.nspname <> 'information_schema' ORDER BY 1"
        )
    )
    return [row[0] for row in rows]


def runtime_grant_statements(schemas: list[str], role: str) -> list[str]:
    """The GRANT/REVOKE statements for ``role`` on ``schemas`` (identifiers already validated)."""
    if not _ROLE_NAME.match(role):
        raise ValueError(f"invalid runtime role name: {role!r}")
    statements: list[str] = []
    for schema in schemas:
        s, r = f'"{schema}"', f'"{role}"'
        table_privs = "SELECT, INSERT" if schema in APPEND_ONLY_SCHEMAS else "SELECT, INSERT, UPDATE, DELETE"
        statements += [
            f"GRANT USAGE ON SCHEMA {s} TO {r}",
            f"REVOKE ALL ON ALL TABLES IN SCHEMA {s} FROM {r}",
            f"GRANT {table_privs} ON ALL TABLES IN SCHEMA {s} TO {r}",
            f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {s} TO {r}",
            f"GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA {s} TO {r}",
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {s} REVOKE ALL ON TABLES FROM {r}",
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {s} GRANT {table_privs} ON TABLES TO {r}",
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {s} GRANT USAGE, SELECT ON SEQUENCES TO {r}",
        ]
    return statements


def apply_runtime_grants(connection: Connection, role: str) -> list[str]:
    """Grant ``role`` its runtime privileges on every schema the current (owner) role owns; return the schemas.

    Does nothing when the role does not exist (single-role development setups)."""
    exists = connection.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role}).scalar()
    if not exists:
        return []
    schemas = [s for s in _owned_schemas(connection) if _ROLE_NAME.match(s)]
    for statement in runtime_grant_statements(schemas, role):
        connection.execute(text(statement))
    return schemas
