"""The SQL window of the system administrator (Yamen, 2026-11-09; docs/sql/console.md).

A database manager in the dashboard: the connection (server, port, database, user, SSL) of each configured target,
a query box, the result as a table, the tree of schemas and tables, and the export of the result. Read only: one
reading statement at a time, in a READ ONLY transaction, with a time limit and a row limit (engine.py). Reserved to
the national system administrator; every query, refused or run, is written to the audit log with its text.
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.sqlconsole import engine
from app.modules.sqlconsole.examples import examples as ready_examples
from app.modules.sqlconsole.export import MEDIA_TYPES, ExportFormat, render

router = APIRouter(prefix="/api/v1/admin/sql", tags=["sql-console"])

Admin = Annotated[Principal, Depends(require_roles(Role.SYSADMIN))]
Session = Annotated[AsyncSession, Depends(get_session)]
_SQL_KEPT = 4000


class ConnectionOut(BaseModel):
    name: str
    host: str
    port: int
    database: str
    user: str
    sslmode: str | None
    read_only: bool = True
    timeout_s: int
    max_rows: int
    export_max_rows: int


class PingOut(BaseModel):
    name: str
    ok: bool
    version: str | None = None
    role: str | None = None
    database: str | None = None
    size: str | None = None
    superuser: bool | None = None
    can_write: bool | None = None
    latency_ms: int | None = None
    server_time: str | None = None
    error: str | None = None


class QueryIn(BaseModel):
    connection: str = Field(min_length=1, max_length=32)
    sql: str = Field(min_length=1, max_length=20000)
    max_rows: int | None = Field(default=None, ge=1, le=10000)


class ColumnOut(BaseModel):
    name: str
    type: str


class QueryOut(BaseModel):
    command: str
    columns: list[ColumnOut]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    duration_ms: int
    notices: list[str]
    executed_at: datetime


class ExportIn(QueryIn):
    format: ExportFormat


class HistoryOut(BaseModel):
    id: UUID
    connection: str
    sql: str
    title: str | None
    pinned: bool
    status: str
    command: str | None
    rows: int | None
    truncated: bool
    duration_ms: int | None
    error: str | None
    run_count: int
    created_at: datetime
    last_run_at: datetime
    updated_at: datetime


class HistoryPatch(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    sql: str | None = Field(default=None, min_length=1, max_length=20000)
    pinned: bool | None = None


_HISTORY_COLUMNS = (
    "id, connection, sql, title, pinned, status, command, rows, truncated, duration_ms, error, run_count, "
    "created_at, last_run_at, updated_at"
)


def _guard(principal: Principal, settings: Settings) -> None:
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "national_scope_required")
    if not settings.sql_console_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "sql_console_disabled")


def _target(name: str, settings: Settings) -> engine.Target:
    found = engine.targets(settings).get(name)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_connection")
    return found


def _refusal(exc: engine.ConsoleError) -> HTTPException:
    code = status.HTTP_502_BAD_GATEWAY if exc.code == "connection_failed" else status.HTTP_422_UNPROCESSABLE_CONTENT
    return HTTPException(code, {"code": exc.code, "message": exc.message, "position": exc.position})


async def _record(
    session: AsyncSession, principal: Principal, action: str, target: str, details: dict[str, Any]
) -> None:
    await audit.record(session, actor=audit.actor_of(principal), action=action, target=f"sql:{target}", details=details)
    await session.commit()


async def _remember(
    session: AsyncSession,
    principal: Principal,
    connection: str,
    sql: str,
    *,
    result: engine.Result | None = None,
    error: engine.ConsoleError | None = None,
) -> None:
    """The run in the administrator's history: a new entry, or the same text's entry with its counter raised."""
    await session.execute(
        text(
            "INSERT INTO platform.sql_query (owner, owner_name, connection, sql, status, command, rows, truncated, "
            "duration_ms, error) VALUES (:owner, :owner_name, :connection, :sql, :status, :command, :rows, "
            ":truncated, :duration_ms, :error) "
            "ON CONFLICT (owner, connection, md5(sql)) DO UPDATE SET status = EXCLUDED.status, "
            "command = EXCLUDED.command, rows = EXCLUDED.rows, truncated = EXCLUDED.truncated, "
            "duration_ms = EXCLUDED.duration_ms, error = EXCLUDED.error, "
            "run_count = platform.sql_query.run_count + 1, last_run_at = now()"
        ),
        {
            "owner": audit.actor_of(principal),
            "owner_name": audit.name_of(principal),
            "connection": connection,
            "sql": sql,
            "status": "error" if error else "ok",
            "command": result.command if result else None,
            "rows": len(result.rows) if result else None,
            "truncated": bool(result and result.truncated),
            "duration_ms": result.duration_ms if result else None,
            "error": error.message[:2000] if error else None,
        },
    )


@router.get("/connections", response_model=list[ConnectionOut])
async def connections(principal: Admin, settings: Annotated[Settings, Depends(get_settings)]) -> list[ConnectionOut]:
    """The configured databases: where they are and who the window connects as. Never the password."""
    _guard(principal, settings)
    return [
        ConnectionOut(
            name=t.name,
            host=t.host,
            port=t.port,
            database=t.database,
            user=t.user,
            sslmode=t.sslmode,
            timeout_s=settings.sql_console_timeout_s,
            max_rows=settings.sql_console_max_rows,
            export_max_rows=settings.sql_console_export_max_rows,
        )
        for t in engine.targets(settings).values()
    ]


@router.get("/examples")
async def examples(principal: Admin, settings: Annotated[Settings, Depends(get_settings)]) -> list[dict[str, str]]:
    """The ready queries of docs/sql/01-queries.sql (Q01-Q56) with their section, title and description."""
    _guard(principal, settings)
    return [{k: str(v) for k, v in e.items()} for e in ready_examples()]


@router.post("/connections/{name}/test", response_model=PingOut)
async def test_connection(
    name: str, principal: Admin, session: Session, settings: Annotated[Settings, Depends(get_settings)]
) -> PingOut:
    """Opens a connection to the target and reads its version, role and size (the «اختبار الاتصال» button)."""
    _guard(principal, settings)
    target = _target(name, settings)
    try:
        info = await engine.ping(target, settings)
    except engine.ConsoleError as exc:
        await _record(session, principal, "sql_console.test", name, {"ok": False, "error": exc.message[:300]})
        return PingOut(name=name, ok=False, error=exc.message)
    await _record(session, principal, "sql_console.test", name, {"ok": True})
    return PingOut(name=name, ok=True, **info)


@router.get("/connections/{name}/schema")
async def connection_schema(
    name: str, principal: Admin, settings: Annotated[Settings, Depends(get_settings)]
) -> list[dict[str, Any]]:
    """Schemas, tables and views with their columns, for the tree beside the editor."""
    _guard(principal, settings)
    try:
        return await engine.schema(_target(name, settings), settings)
    except engine.ConsoleError as exc:
        raise _refusal(exc) from exc


@router.post("/query", response_model=QueryOut)
async def query(
    body: QueryIn, principal: Admin, session: Session, settings: Annotated[Settings, Depends(get_settings)]
) -> QueryOut:
    """Runs one reading statement and returns at most ``max_rows`` rows (the configured limit by default)."""
    _guard(principal, settings)
    target = _target(body.connection, settings)
    limit = min(body.max_rows or settings.sql_console_max_rows, settings.sql_console_max_rows)
    details: dict[str, Any] = {"sql": body.sql[:_SQL_KEPT]}
    try:
        result = await engine.run(target, body.sql, settings, max_rows=limit, actor=audit.actor_of(principal))
    except engine.ConsoleError as exc:
        await _remember(session, principal, body.connection, body.sql, error=exc)
        await _record(session, principal, "sql_console.query", body.connection, {**details, "error": exc.code})
        raise _refusal(exc) from exc
    await _remember(session, principal, body.connection, body.sql, result=result)
    await _record(
        session,
        principal,
        "sql_console.query",
        body.connection,
        {**details, "rows": len(result.rows), "truncated": result.truncated, "duration_ms": result.duration_ms},
    )
    return QueryOut(
        command=result.command,
        columns=[ColumnOut(**c) for c in result.columns],
        rows=result.rows,
        row_count=len(result.rows),
        truncated=result.truncated,
        duration_ms=result.duration_ms,
        notices=result.notices,
        executed_at=datetime.now().astimezone(),
    )


@router.post("/export")
async def export(
    body: ExportIn, principal: Admin, session: Session, settings: Annotated[Settings, Depends(get_settings)]
) -> Response:
    """Runs the statement again with the export limit and returns the result as a file in the chosen format."""
    _guard(principal, settings)
    target = _target(body.connection, settings)
    limit = settings.sql_console_export_max_rows
    details: dict[str, Any] = {"sql": body.sql[:_SQL_KEPT], "format": body.format}
    try:
        result = await engine.run(target, body.sql, settings, max_rows=limit, actor=audit.actor_of(principal))
    except engine.ConsoleError as exc:
        await _record(session, principal, "sql_console.export", body.connection, {**details, "error": exc.code})
        raise _refusal(exc) from exc
    await _record(
        session,
        principal,
        "sql_console.export",
        body.connection,
        {**details, "rows": len(result.rows), "truncated": result.truncated},
    )
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    title = f"ء-حماية · {target.name} · {stamp}"
    content = render(body.format, result.columns, result.rows, sql=body.sql, title=title)
    filename = f"ehimaya-{target.name}-{stamp}.{body.format}"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Rows": str(len(result.rows)),
        "X-Truncated": "true" if result.truncated else "false",
        "Cache-Control": "no-store",
    }
    return Response(content=content, media_type=MEDIA_TYPES[body.format], headers=headers)


# ---------------------------------------------------------------- the administrator's history of queries


@router.get("/history", response_model=list[HistoryOut])
async def history(
    principal: Admin,
    session: Session,
    settings: Annotated[Settings, Depends(get_settings)],
    q: Annotated[str | None, Query(max_length=200)] = None,
    only: Annotated[str | None, Query(pattern="^(pinned|errors)$")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[dict[str, Any]]:
    """The caller's own queries, pinned first, then the latest run first."""
    _guard(principal, settings)
    where = ["owner = :owner"]
    params: dict[str, Any] = {"owner": audit.actor_of(principal), "limit": limit}
    if q:
        where.append("(sql ILIKE :q OR title ILIKE :q)")
        params["q"] = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    if only == "pinned":
        where.append("pinned")
    elif only == "errors":
        where.append("status = 'error'")
    rows = await session.execute(
        text(
            f"SELECT {_HISTORY_COLUMNS} FROM platform.sql_query WHERE {' AND '.join(where)} "  # noqa: S608
            "ORDER BY pinned DESC, last_run_at DESC LIMIT :limit"
        ),
        params,
    )
    return [dict(r._mapping) for r in rows]


@router.patch("/history/{entry_id}", response_model=HistoryOut)
async def edit_history(
    entry_id: UUID,
    body: HistoryPatch,
    principal: Admin,
    session: Session,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Renames, edits the text of, pins or unpins one of the caller's entries."""
    _guard(principal, settings)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "nothing_to_change")
    if "title" in changes and changes["title"] is not None:
        changes["title"] = changes["title"].strip() or None
    sets = ", ".join(f"{k} = :{k}" for k in changes)
    try:
        row = (
            await session.execute(
                text(
                    f"UPDATE platform.sql_query SET {sets}, updated_at = now() "  # noqa: S608
                    f"WHERE id = :id AND owner = :owner RETURNING {_HISTORY_COLUMNS}"
                ),
                {**changes, "id": entry_id, "owner": audit.actor_of(principal)},
            )
        ).first()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "same_query_exists") from exc
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await session.commit()
    return dict(row._mapping)


@router.delete("/history/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history(
    entry_id: UUID, principal: Admin, session: Session, settings: Annotated[Settings, Depends(get_settings)]
) -> Response:
    """Removes one of the caller's entries (the audit log keeps its runs)."""
    _guard(principal, settings)
    row = (
        await session.execute(
            text("DELETE FROM platform.sql_query WHERE id = :id AND owner = :owner RETURNING id"),
            {"id": entry_id, "owner": audit.actor_of(principal)},
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
