# covers: NFR-13
"""The SQL window of the system administrator (docs/sql/console.md): read only, audited, with a history per owner."""

import csv
import io
import json
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from openpyxl import load_workbook
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sqlconsole import engine, examples
from app.modules.sqlconsole.export import render
from tests.conftest import STAFF_ISS, TokenFactory, bearer

URL = "/api/v1/admin/sql"


def sysadmin(make_token: TokenFactory, **claims: Any) -> dict[str, str]:
    claims.setdefault("scope_level", "national")
    return bearer(make_token(issuer=STAFF_ISS, roles=["sysadmin"], **claims))


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "  -- a comment\n select now()",
        "/* x */ WITH t AS (SELECT 1) SELECT * FROM t",
        "(SELECT 1) UNION (SELECT 2)",
        "EXPLAIN SELECT 1",
        "show timezone",
        "VALUES (1), (2)",
        "TABLE platform.sql_query",
    ],
)
def test_reading_statements_are_accepted(sql: str) -> None:
    engine.check_reading(sql)


@pytest.mark.parametrize(
    ("sql", "code"),
    [
        ("", "empty"),
        ("-- only a comment", "empty"),
        ("DELETE FROM audit.log", "not_reading"),
        ("drop table platform.sql_query", "not_reading"),
        ("COPY audit.log TO '/tmp/x'", "not_reading"),
        ("SET ROLE postgres", "not_reading"),
        ("DO $$ BEGIN END $$", "not_reading"),
        ("BEGIN", "not_reading"),
        ("SELECT pg_terminate_backend(42)", "side_effect"),
        ("select set_config('ehimaya.scope', 'system', false)", "side_effect"),
        ("SELECT pg_read_file('/etc/passwd')", "side_effect"),
        ('SELECT * FROM U&"audit".log', "side_effect"),
        ("EXPLAIN ANALYZE DELETE FROM audit.log", "not_reading"),
    ],
)
def test_other_statements_are_refused(sql: str, code: str) -> None:
    with pytest.raises(engine.ConsoleError) as caught:
        engine.check_reading(sql)
    assert caught.value.code == code


def test_targets_hide_the_password() -> None:
    target = engine._target("reports", "postgresql+asyncpg://reader:s3cret@db.local:6432/ehimaya?sslmode=require")
    assert (target.host, target.port, target.database, target.user, target.sslmode) == (
        "db.local",
        6432,
        "ehimaya",
        "reader",
        "require",
    )
    assert target.dsn.startswith("postgresql://")


async def test_only_the_national_sysadmin_opens_the_window(
    client: httpx.AsyncClient, make_token: TokenFactory, staff: Any
) -> None:
    assert (await client.get(f"{URL}/connections", headers=staff(["operator"], gouvernorat=None))).status_code == 403
    regional = sysadmin(make_token, scope_level=None, gouvernorat_code="11")
    assert (await client.get(f"{URL}/connections", headers=regional)).status_code == 403
    listed = await client.get(f"{URL}/connections", headers=sysadmin(make_token))
    assert listed.status_code == 200
    main = listed.json()[0]
    assert main["name"] == "main" and main["read_only"] is True
    assert "password" not in json.dumps(listed.json()).lower()


async def test_connection_test_and_schema_tree(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    headers = sysadmin(make_token)
    ping = (await client.post(f"{URL}/connections/main/test", headers=headers)).json()
    assert ping["ok"] is True and "PostgreSQL" in ping["version"]
    assert (await client.post(f"{URL}/connections/elsewhere/test", headers=headers)).status_code == 404
    tree = (await client.get(f"{URL}/connections/main/schema", headers=headers)).json()
    platform = next(s for s in tree if s["name"] == "platform")
    table = next(t for t in platform["tables"] if t["name"] == "sql_query")
    assert {"name": "sql", "type": "text", "not_null": True} in table["columns"]


async def test_query_returns_columns_rows_and_is_audited(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    marker = uuid.uuid4().hex[:8]
    sql = f"SELECT g AS n, 'ص-{marker}' AS label, now() AS at FROM generate_series(1, 5) g"  # noqa: S608
    out = await client.post(f"{URL}/query", headers=sysadmin(make_token), json={"connection": "main", "sql": sql})
    assert out.status_code == 200, out.text
    body = out.json()
    assert [c["name"] for c in body["columns"]] == ["n", "label", "at"]
    assert body["rows"][0][:2] == [1, f"ص-{marker}"] and body["row_count"] == 5 and body["command"] == "SELECT"
    cut = await client.post(
        f"{URL}/query", headers=sysadmin(make_token), json={"connection": "main", "sql": sql, "max_rows": 2}
    )
    assert cut.json()["truncated"] is True and cut.json()["row_count"] == 2
    audited = (
        (
            await session.execute(
                text("SELECT details FROM audit.log WHERE action = 'sql_console.query' AND details->>'sql' = :s"),
                {"s": sql},
            )
        )
        .scalars()
        .all()
    )
    assert len(audited) == 2 and audited[0]["rows"] in (5, 2)


async def test_values_come_back_as_the_database_shows_them(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    sql = (
        "SELECT 1.67::real AS r, 2.5::numeric AS n, NULL::text AS nothing, '{\"a\": 1}'::jsonb AS j, "
        "ARRAY[1, 2] AS arr, '\\x0102'::bytea AS b, 9007199254740993::bigint AS big, '2026-11-09'::date AS d"
    )
    out = await client.post(f"{URL}/query", headers=sysadmin(make_token), json={"connection": "main", "sql": sql})
    assert out.status_code == 200, out.text
    assert out.json()["rows"][0] == [
        1.67,
        "2.5",
        None,
        '{"a": 1}',
        [1, 2],
        "\\x0102 (2 B)",
        "9007199254740993",
        "2026-11-09",
    ]


async def test_writes_never_happen(client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession) -> None:
    headers = sysadmin(make_token)
    before = await session.scalar(text("SELECT count(*) FROM platform.sql_query"))
    for sql in (
        "DELETE FROM platform.sql_query",
        "SELECT 1; DELETE FROM platform.sql_query",
        "WITH gone AS (DELETE FROM platform.sql_query RETURNING 1) SELECT count(*) FROM gone",
        "SELECT nextval('audit.log_id_seq')",
    ):
        out = await client.post(f"{URL}/query", headers=headers, json={"connection": "main", "sql": sql})
        assert out.status_code == 422, (sql, out.text)
        assert out.json()["detail"]["message"]
    # The four refused runs are in the history (the API's session, not the window's).
    after = await session.scalar(text("SELECT count(*) FROM platform.sql_query"))
    assert after == before + 4


async def test_a_database_error_comes_back_with_its_position(
    client: httpx.AsyncClient, make_token: TokenFactory
) -> None:
    out = await client.post(
        f"{URL}/query", headers=sysadmin(make_token), json={"connection": "main", "sql": "SELECT nope FROM audit.log"}
    )
    assert out.status_code == 422
    detail = out.json()["detail"]
    assert detail["code"] == "42703" and detail["position"] == 8


async def test_history_is_kept_per_owner_and_can_be_edited_and_deleted(
    client: httpx.AsyncClient, make_token: TokenFactory
) -> None:
    mine = sysadmin(make_token, sub=str(uuid.uuid4()))
    other = sysadmin(make_token, sub=str(uuid.uuid4()))
    sql = "SELECT count(*) FROM platform.sql_query"
    for _ in range(3):
        await client.post(f"{URL}/query", headers=mine, json={"connection": "main", "sql": sql})
    await client.post(f"{URL}/query", headers=mine, json={"connection": "main", "sql": "SELECT broken("})
    entries = (await client.get(f"{URL}/history", headers=mine)).json()
    assert len(entries) == 2
    entry = next(e for e in entries if e["sql"] == sql)
    assert entry["run_count"] == 3 and entry["status"] == "ok" and entry["rows"] == 1
    errors = (await client.get(f"{URL}/history", headers=mine, params={"only": "errors"})).json()
    assert [e["sql"] for e in errors] == ["SELECT broken("]
    assert (await client.get(f"{URL}/history", headers=other)).json() == []

    # Another administrator neither edits nor deletes it.
    assert (await client.patch(f"{URL}/history/{entry['id']}", headers=other, json={"pinned": True})).status_code == 404
    assert (await client.delete(f"{URL}/history/{entry['id']}", headers=other)).status_code == 404

    edited = await client.patch(
        f"{URL}/history/{entry['id']}",
        headers=mine,
        json={"title": "  عدد الاستعلامات ", "pinned": True, "sql": sql + " WHERE pinned"},
    )
    assert edited.status_code == 200
    assert edited.json()["title"] == "عدد الاستعلامات" and edited.json()["pinned"] is True
    found = (await client.get(f"{URL}/history", headers=mine, params={"q": "عدد"})).json()
    assert [e["id"] for e in found] == [entry["id"]]
    assert (await client.get(f"{URL}/history", headers=mine, params={"only": "pinned"})).json()[0]["id"] == entry["id"]
    clash = await client.patch(f"{URL}/history/{errors[0]['id']}", headers=mine, json={"sql": sql + " WHERE pinned"})
    assert clash.status_code == 409

    assert (await client.delete(f"{URL}/history/{entry['id']}", headers=mine)).status_code == 204
    assert len((await client.get(f"{URL}/history", headers=mine)).json()) == 1


async def test_export_formats(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    headers = sysadmin(make_token)
    sql = "SELECT 1 AS id, '=cmd()' AS formula, 'تونس' AS city, NULL AS empty"
    for fmt in ("csv", "xlsx", "json", "sql", "html", "md"):
        out = await client.post(
            f"{URL}/export", headers=headers, json={"connection": "main", "sql": sql, "format": fmt}
        )
        assert out.status_code == 200, (fmt, out.text)
        assert f".{fmt}" in out.headers["content-disposition"] and out.headers["x-rows"] == "1"
    refused = await client.post(
        f"{URL}/export", headers=headers, json={"connection": "main", "sql": "DELETE FROM audit.log", "format": "csv"}
    )
    assert refused.status_code == 422


def test_render_escapes_formulas_and_keeps_arabic() -> None:
    columns = [{"name": "id", "type": "int4"}, {"name": "f", "type": "text"}, {"name": "city", "type": "text"}]
    rows: list[list[Any]] = [[1, "=HYPERLINK(1)", "أريانة"], [2, "-5", None]]
    text_csv = render("csv", columns, rows, sql="SELECT", title="t").decode("utf-8")
    assert text_csv.startswith("﻿")
    parsed = list(csv.reader(io.StringIO(text_csv.lstrip("﻿"))))
    assert parsed[1] == ["1", "'=HYPERLINK(1)", "أريانة"] and parsed[2] == ["2", "-5", ""]
    book = load_workbook(io.BytesIO(render("xlsx", columns, rows, sql="SELECT", title="t")))
    sheet = book.worksheets[0]
    assert sheet["B2"].value == "'=HYPERLINK(1)" and sheet["A2"].value == 1 and sheet["C2"].value == "أريانة"
    assert book.worksheets[1]["A2"].value == "SELECT"
    insert = render("sql", columns, [[1, "it's", None]], sql="SELECT", title="t").decode()
    assert "VALUES (1, 'it''s', NULL);" in insert
    md = render("md", columns, [[1, "a|b", "x"]], sql="SELECT", title="t").decode()
    assert "a\\|b" in md
    assert "&lt;b&gt;" in render("html", columns, [[1, "<b>", "x"]], sql="SELECT", title="t").decode()
    assert json.loads(render("json", columns, rows, sql="SELECT", title="t"))["rows"][0]["city"] == "أريانة"


def test_the_ready_queries_are_those_of_the_docs() -> None:
    docs = Path(__file__).resolve().parents[3] / "docs" / "sql" / "01-queries.sql"
    if docs.exists():
        assert examples.SOURCE.read_text(encoding="utf-8") == docs.read_text(encoding="utf-8")
    found = examples.examples()
    assert [e["id"] for e in found] == [f"Q{i:02d}" for i in range(1, 57)]
    assert all(e["title"] and e["description"] and e["section"] for e in found)


async def test_every_ready_query_runs_in_the_window(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    headers = sysadmin(make_token)
    listed = (await client.get(f"{URL}/examples", headers=headers)).json()
    assert len(listed) == 56
    for example in listed:
        engine.check_reading(example["sql"])
        out = await client.post(
            f"{URL}/query", headers=headers, json={"connection": "main", "sql": example["sql"], "max_rows": 5}
        )
        assert out.status_code == 200, (example["id"], out.text)
