"""The ready queries of docs/sql/01-queries.sql, offered in the SQL window's «جاهزة» list.

``examples.sql`` is a copy of that file shipped with the API (the image holds only ``app``); a test checks that both
are the same. Each query starts with ``-- Qnn · title``, then ``-- الوصف:`` and its continuation lines, then the SQL.
"""

import re
from functools import cache
from pathlib import Path
from typing import TypedDict

SOURCE = Path(__file__).with_name("examples.sql")
_HEAD = re.compile(r"^-- (Q\d{2}) · (.+)$")
_SECTION = re.compile(r"^-- ([أ-ي]{1,2})\. (.+)$")


class Example(TypedDict):
    id: str
    section: str
    title: str
    description: str
    sql: str


def _finish(current: dict[str, object], body: list[str], found: list[Example]) -> None:
    sql = "\n".join(body).strip()
    if sql.endswith(";"):
        sql = sql[:-1].rstrip()
    found.append(
        Example(
            id=str(current["id"]),
            section=str(current["section"]),
            title=str(current["title"]),
            description=" ".join(current["description"]).strip(),  # type: ignore[arg-type]
            sql=sql,
        )
    )


@cache
def examples() -> tuple[Example, ...]:
    found: list[Example] = []
    section = ""
    current: dict[str, object] | None = None
    body: list[str] = []
    describing = False
    for line in SOURCE.read_text(encoding="utf-8").splitlines():
        if line.startswith("-- ====="):
            if current:
                _finish(current, body, found)
                current = None
            continue
        if (m := _SECTION.match(line)) and current is None:
            section = m.group(2).strip()
            continue
        if m := _HEAD.match(line):
            if current:
                _finish(current, body, found)
            current = {"id": m.group(1), "section": section, "title": m.group(2).strip(), "description": []}
            body, describing = [], False
            continue
        if current is None:
            continue
        if not body and line.startswith("-- الوصف:"):
            describing = True
            current["description"].append(line.removeprefix("-- الوصف:").strip())  # type: ignore[attr-defined]
            continue
        if not body and describing and line.startswith("--"):
            current["description"].append(line.removeprefix("--").strip())  # type: ignore[attr-defined]
            continue
        describing = False
        if body or line.strip():
            body.append(line)
    if current:
        _finish(current, body, found)
    return tuple(found)
