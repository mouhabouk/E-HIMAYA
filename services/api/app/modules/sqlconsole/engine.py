"""Read-only execution of the SQL window's queries (Yamen, 2026-11-09; docs/sql/console.md).

Each query opens its own connection to the chosen target (never the API's pool, so no session setting can leak),
inside a READ ONLY transaction with a statement timeout, and is always rolled back. Only one statement is accepted:
asyncpg prepares the text, and PostgreSQL refuses to prepare more than one. The first word must be one of the
reading commands, so the window never runs DDL, COPY, SET, CALL, DO or a transaction command, even when the target's
role could. The connection's password stays on the server: the client only sees the host, port, database and user.
"""

import base64
import datetime as dt
import decimal
import ipaddress
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import unquote, urlsplit

import asyncpg

from app.core.config import Settings

#: Commands the window runs. Anything else is refused before it reaches the database.
READING_COMMANDS = frozenset({"select", "with", "explain", "show", "values", "table"})
_COMMENTS = re.compile(r"(--[^\n]*)|(/\*.*?\*/)", re.S)
_FIRST_WORD = re.compile(r"[A-Za-z]+")
_EXPLAIN_WRITE = re.compile(r"^\s*explain\b[^;]*\banalyze\b", re.I | re.S)
# Functions that act on the server even inside a READ ONLY transaction (end sessions, read files, change settings).
# A role that may only SELECT is the real guard (docs/sql/console.md §3); this list refuses the obvious cases early.
_SIDE_EFFECT_FUNCTIONS = re.compile(
    r"\b(pg_terminate_backend|pg_cancel_backend|pg_reload_conf|pg_rotate_logfile|pg_promote|pg_read_file|"
    r"pg_read_binary_file|pg_ls_\w+|pg_stat_file|lo_import|lo_export|lo_\w+|dblink\w*|set_config|"
    r"pg_advisory\w*|pg_switch_wal|pg_create_\w+|pg_drop_\w+|pg_replication_\w+|pg_logical_\w+)\s*\(",
    re.I,
)
_UNICODE_ESCAPE = re.compile(r"\bU&[\"']", re.I)
_BYTES_SHOWN = 64


class ConsoleError(Exception):
    """A refusal or an error of the database, shown to the administrator as it is."""

    def __init__(self, code: str, message: str, *, position: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.position = position


@dataclass(frozen=True)
class Target:
    name: str
    dsn: str
    host: str
    port: int
    database: str
    user: str
    sslmode: str | None


@dataclass
class Result:
    columns: list[dict[str, str]]
    rows: list[list[Any]]
    truncated: bool
    duration_ms: int
    command: str
    notices: list[str] = field(default_factory=list)


def targets(settings: Settings) -> dict[str, Target]:
    """The databases the window may read, by name; "main" (the API's own database) when none are configured."""
    entries = settings.sql_console_targets or [f"main={settings.database_url}"]
    found: dict[str, Target] = {}
    for entry in entries:
        name, _, url = entry.partition("=")
        found[name.strip()] = _target(name.strip(), url.strip())
    return found


def _target(name: str, url: str) -> Target:
    dsn = re.sub(r"^postgresql\+\w+://", "postgresql://", url)
    parts = urlsplit(dsn)
    query = dict(p.split("=", 1) for p in parts.query.split("&") if "=" in p)
    return Target(
        name=name,
        dsn=dsn,
        host=parts.hostname or "localhost",
        port=parts.port or 5432,
        database=unquote(parts.path.lstrip("/")) or unquote(parts.username or ""),
        user=unquote(parts.username or ""),
        sslmode=query.get("sslmode") or query.get("ssl"),
    )


def check_reading(sql: str) -> str:
    """The command word of a reading statement, or a refusal."""
    text = _COMMENTS.sub(" ", sql).strip()
    while text.startswith("("):
        text = text[1:].lstrip()
    if not text:
        raise ConsoleError("empty", "الاستعلام فارغ.")
    match = _FIRST_WORD.match(text)
    word = match.group(0).lower() if match else ""
    if word not in READING_COMMANDS:
        raise ConsoleError(
            "not_reading",
            "النافذة للقراءة فقط: يُقبل SELECT وWITH وEXPLAIN وSHOW وVALUES وTABLE. "
            "الإدخال والتعديل يمرّان عبر ملفات docs/sql أو واجهات المنظومة.",
        )
    if _SIDE_EFFECT_FUNCTIONS.search(text) or _UNICODE_ESCAPE.search(text):
        raise ConsoleError(
            "side_effect", "هذه الدالة تؤثر في الخادم (إنهاء جلسات، قراءة ملفات، تغيير إعدادات): لا تُقبل في النافذة."
        )
    if _EXPLAIN_WRITE.match(text) and re.search(r"\b(insert|update|delete|merge)\b", text, re.I):
        raise ConsoleError("not_reading", "EXPLAIN ANALYZE ينفّذ الأمر فعلا: لا يُقبل على أمر كتابة.")
    return word.upper()


async def _connect(target: Target, settings: Settings) -> asyncpg.Connection:
    timeout_ms = str(settings.sql_console_timeout_s * 1000)
    try:
        return await asyncpg.connect(
            target.dsn,
            timeout=10,
            command_timeout=settings.sql_console_timeout_s + 5,
            statement_cache_size=0,
            server_settings={
                "application_name": "ehimaya-sql-console",
                "statement_timeout": timeout_ms,
                "lock_timeout": "2000",
                "idle_in_transaction_session_timeout": timeout_ms,
                "default_transaction_read_only": "on",
                "TimeZone": "Africa/Tunis",
            },
        )
    except (OSError, asyncpg.PostgresError, TimeoutError) as exc:
        raise ConsoleError("connection_failed", f"تعذّر الاتصال بالقاعدة {target.name}: {exc}") from exc


async def ping(target: Target, settings: Settings) -> dict[str, Any]:
    """The server's version, the role it connected as, and whether that role could write outside the window."""
    started = time.monotonic()
    conn = await _connect(target, settings)
    try:
        row = await conn.fetchrow(
            "SELECT version() AS version, current_user AS role, current_database() AS database, "
            "pg_size_pretty(pg_database_size(current_database())) AS size, "
            "(SELECT rolsuper FROM pg_roles WHERE rolname = current_user) AS superuser, "
            "EXISTS (SELECT 1 FROM information_schema.table_privileges WHERE grantee = current_user "
            "        AND privilege_type IN ('INSERT', 'UPDATE', 'DELETE')) AS can_write, "
            "now() AS server_time"
        )
    finally:
        await conn.close()
    assert row is not None
    return {
        **dict(row),
        "latency_ms": round((time.monotonic() - started) * 1000),
        "server_time": row["server_time"].isoformat(),
    }


async def _scope(conn: asyncpg.Connection, actor: str) -> None:
    # Row-level security (core/db.py): the window reads with the national scope of its national administrator, and
    # anything it could ever change would be journaled in their name. Transaction-local, like the API's own scope.
    await conn.execute(
        "SELECT set_config('ehimaya.scope', 'national', true), set_config('ehimaya.actor', $1, true), "
        "set_config('ehimaya.request_id', 'sql-console', true)",
        actor,
    )


async def run(target: Target, sql: str, settings: Settings, *, max_rows: int, actor: str = "") -> Result:
    """One reading statement, at most ``max_rows`` rows (one more is read to know whether the result was cut)."""
    command = check_reading(sql)
    notices: list[str] = []
    conn = await _connect(target, settings)
    conn.add_log_listener(lambda _c, msg: notices.append(str(msg.message)[:500]))
    started = time.monotonic()
    try:
        tx = conn.transaction(readonly=True, isolation="repeatable_read")
        await tx.start()
        try:
            await _scope(conn, actor)
            stmt = await conn.prepare(sql)
            columns = [{"name": a.name, "type": a.type.name} for a in stmt.get_attributes()]
            records = await stmt.fetch() if not columns else await _fetch_some(stmt, max_rows + 1)
        finally:
            await tx.rollback()
    except asyncpg.PostgresError as exc:
        position = getattr(exc, "position", None)
        message = str(exc)
        detail = getattr(exc, "detail", None)
        hint = getattr(exc, "hint", None)
        if detail:
            message += f"\nDETAIL: {detail}"
        if hint:
            message += f"\nHINT: {hint}"
        raise ConsoleError(
            getattr(exc, "sqlstate", None) or "db_error", message, position=int(position) if position else None
        ) from exc
    finally:
        await conn.close()
    truncated = len(records) > max_rows
    # real (float4) holds about 7 significant digits: 1.67, not the 1.6699999570846558 of its double reading.
    single = {i for i, c in enumerate(columns) if c["type"] == "float4"}
    rows = [
        [float(f"{v:.7g}") if i in single and isinstance(v, float) else cell(v) for i, v in enumerate(r.values())]
        for r in records[:max_rows]
    ]
    return Result(
        columns=columns,
        rows=rows,
        truncated=truncated,
        duration_ms=round((time.monotonic() - started) * 1000),
        command=command,
        notices=notices,
    )


async def _fetch_some(stmt: asyncpg.prepared_stmt.PreparedStatement, n: int) -> list[asyncpg.Record]:
    cursor = await stmt.cursor()
    records: list[asyncpg.Record] = await cursor.fetch(n)
    return records


async def schema(target: Target, settings: Settings) -> list[dict[str, Any]]:
    """Schemas, their tables and views, and the columns of each, for the tree beside the editor."""
    conn = await _connect(target, settings)
    try:
        rows = await conn.fetch(
            """
            SELECT n.nspname AS schema, c.relname AS name,
                   CASE c.relkind WHEN 'v' THEN 'view' WHEN 'm' THEN 'view' ELSE 'table' END AS kind,
                   c.reltuples::bigint AS approx_rows,
                   obj_description(c.oid, 'pg_class') AS comment,
                   coalesce(json_agg(json_build_array(a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull)
                                     ORDER BY a.attnum) FILTER (WHERE a.attnum > 0), '[]') AS columns
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
            WHERE c.relkind IN ('r', 'p', 'v', 'm')
              AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'tiger', 'topology')
              AND n.nspname NOT LIKE 'pg\\_%'
              AND has_table_privilege(c.oid, 'SELECT')
            GROUP BY n.nspname, c.relname, c.relkind, c.reltuples, c.oid
            ORDER BY n.nspname, c.relname
            """
        )
    finally:
        await conn.close()
    schemas: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        schemas.setdefault(r["schema"], []).append(
            {
                "name": r["name"],
                "kind": r["kind"],
                "approx_rows": max(int(r["approx_rows"]), 0),
                "comment": r["comment"],
                "columns": [{"name": c[0], "type": c[1], "not_null": c[2]} for c in json.loads(r["columns"])],
            }
        )
    return [{"name": k, "tables": v} for k, v in schemas.items()]


def cell(value: Any) -> Any:
    """A value the browser can show and export as it is."""
    if value is None or isinstance(value, bool | int | float | str):
        if isinstance(value, int) and abs(value) > 2**53:
            return str(value)
        return value
    if isinstance(value, dt.datetime | dt.date | dt.time):
        return value.isoformat()
    if isinstance(value, dt.timedelta):
        return str(value)
    if isinstance(value, decimal.Decimal | uuid.UUID | ipaddress.IPv4Address | ipaddress.IPv6Address):
        return str(value)
    if isinstance(value, ipaddress.IPv4Network | ipaddress.IPv6Network | ipaddress.IPv4Interface):
        return str(value)
    if isinstance(value, bytes | bytearray | memoryview):
        raw = bytes(value)
        shown = raw[:_BYTES_SHOWN].hex()
        return f"\\x{shown}{'…' if len(raw) > _BYTES_SHOWN else ''} ({len(raw)} B)"
    if isinstance(value, list | tuple):
        return [cell(v) for v in value]
    if isinstance(value, dict):
        return {str(k): cell(v) for k, v in value.items()}
    if isinstance(value, asyncpg.Record):
        return [cell(v) for v in value.values()]
    try:
        return json.loads(json.dumps(value))
    except TypeError:
        return base64.b64encode(value).decode() if isinstance(value, bytes) else str(value)
