"""The SQL window's result as a file: CSV, Excel, JSON, SQL INSERT statements, HTML or Markdown."""

import csv
import html
import io
import json
from datetime import datetime
from typing import Any, Literal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ExportFormat = Literal["csv", "xlsx", "json", "sql", "html", "md"]

MEDIA_TYPES: dict[str, str] = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "json": "application/json",
    "sql": "application/sql; charset=utf-8",
    "html": "text/html; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list | dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _formula_safe(text: str) -> str:
    # A cell that starts like a formula is read by spreadsheets as one (CSV injection): keep it text.
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") and not _is_number(text) else text


def _is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int | float):
        return repr(value)
    if isinstance(value, list | dict):
        return "'" + json.dumps(value, ensure_ascii=False).replace("'", "''") + "'::jsonb"
    return "'" + str(value).replace("'", "''") + "'"


def _ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def render(fmt: ExportFormat, columns: list[dict[str, str]], rows: list[list[Any]], *, sql: str, title: str) -> bytes:
    names = [c["name"] for c in columns]
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(names)
        for row in rows:
            writer.writerow([_formula_safe(_text(v)) for v in row])
        # UTF-8 with BOM: Excel then reads the Arabic text correctly.
        return ("\ufeff" + buf.getvalue()).encode("utf-8")
    if fmt == "json":
        payload = {
            "query": sql,
            "exported_at": datetime.now().astimezone().isoformat(),
            "columns": columns,
            "rows": [dict(zip(names, row, strict=False)) for row in rows],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    if fmt == "sql":
        lines = [f"-- {title}", "-- " + sql.replace("\n", "\n-- "), ""]
        cols = ", ".join(_ident(n) for n in names)
        for row in rows:
            values = ", ".join(_sql_literal(v) for v in row)
            lines.append(f"INSERT INTO query_result ({cols}) VALUES ({values});")  # noqa: S608 - a file, not a query
        return ("\n".join(lines) + "\n").encode("utf-8")
    if fmt == "md":

        def md(v: Any) -> str:
            return _text(v).replace("|", "\\|").replace("\n", " ")

        out = ["| " + " | ".join(md(n) for n in names) + " |", "|" + "---|" * len(names)]
        out += ["| " + " | ".join(md(v) for v in row) + " |" for row in rows]
        return ("\n".join(out) + "\n").encode("utf-8")
    if fmt == "html":
        head = "".join(f"<th>{html.escape(n)}</th>" for n in names)
        body = "".join(
            "<tr>" + "".join(f'<td dir="auto">{html.escape(_text(v))}</td>' for v in row) + "</tr>" for row in rows
        )
        doc = (
            '<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">'
            f"<title>{html.escape(title)}</title><style>"
            "body{font-family:'IBM Plex Sans Arabic',sans-serif;color:#182038;margin:24px}"
            "pre{background:#EEF0F4;padding:12px;border-radius:12px;direction:ltr;text-align:left;white-space:pre-wrap}"
            "table{border-collapse:collapse;width:100%;font-size:13px}"
            "th{background:#1F3FA0;color:#fff;text-align:start;padding:6px 8px}"
            "td{border-bottom:1px solid #E3E7EF;padding:6px 8px;vertical-align:top}"
            "tr:nth-child(even) td{background:#F7F8FB}</style></head><body>"
            f"<h1>{html.escape(title)}</h1><pre>{html.escape(sql)}</pre>"
            f"<p>{len(rows)} سطرا</p><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
            "</body></html>"
        )
        return doc.encode("utf-8")
    # xlsx
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "النتيجة"
    ws.sheet_view.rightToLeft = True
    ws.append(names)
    for col in range(1, len(names) + 1):
        c = ws.cell(row=1, column=col)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F3FA0")
        c.alignment = Alignment(horizontal="center")
    for row in rows:
        ws.append([v if isinstance(v, int | float | bool) or v is None else _formula_safe(_text(v)) for v in row])
    for i, n in enumerate(names, start=1):
        width = max([len(n)] + [len(_text(r[i - 1])) for r in rows[:200]]) + 2
        ws.column_dimensions[get_column_letter(i)].width = min(max(width, 8), 60)
    ws.freeze_panes = "A2"
    q = wb.create_sheet("الاستعلام")
    q.sheet_view.rightToLeft = True
    q["A1"] = title
    q["A1"].font = Font(bold=True)
    q["A2"] = sql
    q["A2"].alignment = Alignment(wrap_text=True, vertical="top")
    q.column_dimensions["A"].width = 120
    data = io.BytesIO()
    wb.save(data)
    return data.getvalue()
