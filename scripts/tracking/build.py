"""Builds the request tracker page (Yamen, 2026-11-13) from the curated rows in requests.py and from the repository.

Automatic parts, so the page follows the project without hand edits:
- the figures: migrations, API operations, last merged pull request, and (when DATABASE_URL points at a migrated
  database) tables, schemas and foreign keys;
- one row for every item of docs/versions.md added after requests.VERSIONS_SEEN.

    python3 scripts/tracking/build.py <out.html>
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import requests as cur  # noqa: E402


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout


def db_counts() -> dict[str, int]:
    url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        return {}
    url = url.replace("+asyncpg", "")
    q = ("select (select count(*) from information_schema.tables where table_type='BASE TABLE' and table_schema not in "
         "('pg_catalog','information_schema','tiger','topology','tiger_data','public')),"
         "(select count(distinct table_schema) from information_schema.tables where table_type='BASE TABLE' and table_schema "
         "not in ('pg_catalog','information_schema','tiger','topology','tiger_data','public')),"
         "(select count(*) from pg_constraint c join pg_namespace n on n.oid=c.connamespace where contype='f' "
         "and nspname not in ('tiger','topology','public'))")
    out = subprocess.run(["psql", url, "-Atc", q], capture_output=True, text=True).stdout.strip()
    if not out:
        return {}
    t, s, f = (int(x) for x in out.split("|"))
    return {"tables": t, "schemas": s, "fks": f}


def collect() -> tuple[list[dict], int]:
    """Curated rows plus one row per item of docs/versions.md added after VERSIONS_SEEN; also the item count."""
    rows = list(cur.R)
    versions = (ROOT / "docs/versions.md").read_text(encoding="utf-8")
    items = re.findall(r"^(\d+)\. (.+)$", versions, re.M)
    for n, text in items:
        if int(n) > cur.VERSIONS_SEEN:
            title = re.split(r"[(:]", text, maxsplit=1)[0].strip()
            pr = re.search(r"#(\d+)", text)
            rows.append(dict(g="os", code=f"V{n}", title=title, kind="مرحلة", desc=text[:220], status="done", size="M",
                             imp=3, date="", ref=f"versions.md بند {n}" + (f" #{pr.group(1)}" if pr else "")))
    return rows, len(items)


def main() -> None:
    out = Path(sys.argv[1])
    rows, nitems = collect()
    migrations = len(list((ROOT / "services/api/migrations/versions").glob("0*.py")))
    ops = (ROOT / "docs/api/openapi.json").read_text(encoding="utf-8").count('"operationId"')
    last = re.search(r"Merge pull request #(\d+)", git("log", "--merges", "-1", "--format=%s", "origin/main") or git("log", "--merges", "-1", "--format=%s"))
    stats = {"tables": 249, "schemas": 40, "fks": 396, **db_counts(), "migrations": migrations, "ops": ops,
             "prs": int(last.group(1)) if last else 0}
    data = {"groups": cur.G, "rows": rows, "docs": cur.DOCS, "stats": stats}
    html = (HERE / "template.html").read_text(encoding="utf-8")
    html = (html.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__DATE__", date.today().isoformat()).replace("__PR__", str(stats["prs"]))
            .replace("__VERS__", str(nitems)).replace("__MIG__", f"{migrations:04d}"))
    out.write_text(html, encoding="utf-8")
    print(f"{len(rows)} rows, stats {stats}")


if __name__ == "__main__":
    main()
