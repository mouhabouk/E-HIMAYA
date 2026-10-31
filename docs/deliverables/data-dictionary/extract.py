"""Extract the data dictionary from a database migrated to head (review point 20, phase 4).

    python3 docs/deliverables/data-dictionary/extract.py postgresql://ehimaya:...@localhost/ehimaya out.json

Reads the live catalogue (schemas, tables, columns, types, keys, Row-Level Security, indexes, check constraints) and
joins the Arabic descriptions of glossary.json next to this file. A table or column missing from the glossary is
listed on stderr and the script exits 1, so the glossary is kept complete when a migration adds one.
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKIP = "('pg_catalog','information_schema','public','topology','tiger','tiger_data','pg_toast')"

SQL = f"""
WITH t AS (
  SELECT c.oid, n.nspname AS schema, c.relname AS name, c.relrowsecurity AS rls,
         (SELECT count(*) FROM pg_index i WHERE i.indrelid = c.oid) AS indexes,
         (SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid) AS policies,
         (SELECT count(*) FROM pg_trigger g WHERE g.tgrelid = c.oid AND NOT g.tgisinternal) AS triggers,
         (SELECT coalesce(json_agg(pg_get_constraintdef(k.oid) ORDER BY k.conname), '[]')
            FROM pg_constraint k WHERE k.conrelid = c.oid AND k.contype = 'c') AS checks
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE c.relkind IN ('r', 'p') AND n.nspname NOT IN {SKIP} AND NOT c.relispartition
), cols AS (
  SELECT a.attrelid, a.attnum, a.attname AS name, format_type(a.atttypid, a.atttypmod) AS type,
         NOT a.attnotnull AS nullable, pg_get_expr(d.adbin, d.adrelid) AS "default",
         EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conrelid = a.attrelid AND k.contype = 'p'
                 AND a.attnum = ANY (k.conkey)) AS pk,
         (SELECT string_agg(DISTINCT fn.nspname || '.' || fc.relname, ', ')
            FROM pg_constraint k JOIN pg_class fc ON fc.oid = k.confrelid
            JOIN pg_namespace fn ON fn.oid = fc.relnamespace
           WHERE k.conrelid = a.attrelid AND k.contype = 'f' AND a.attnum = ANY (k.conkey)) AS fk,
         EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conrelid = a.attrelid AND k.contype = 'u'
                 AND k.conkey = ARRAY[a.attnum]) AS uniq
    FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
   WHERE a.attnum > 0 AND NOT a.attisdropped
)
SELECT json_build_object(
  'migration', (SELECT version_num FROM alembic_version LIMIT 1),
  'server', current_setting('server_version'),
  'extensions', (SELECT json_agg(extname || ' ' || extversion ORDER BY extname) FROM pg_extension
                  WHERE extname <> 'plpgsql'),
  'views', (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE c.relkind IN ('v', 'm') AND n.nspname NOT IN {SKIP}),
  'functions', (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                 WHERE n.nspname NOT IN {SKIP}),
  'tables', (SELECT json_agg(json_build_object(
      'schema', t.schema, 'name', t.name, 'rls', t.rls, 'policies', t.policies, 'indexes', t.indexes,
      'triggers', t.triggers, 'checks', t.checks,
      'columns', (SELECT json_agg(json_build_object('name', cols.name, 'type', cols.type, 'nullable', cols.nullable,
                   'default', cols."default", 'pk', cols.pk, 'fk', cols.fk, 'unique', cols.uniq) ORDER BY cols.attnum)
                    FROM cols WHERE cols.attrelid = t.oid)) ORDER BY t.schema, t.name) FROM t)
)
"""


def main() -> int:
    dsn, out = sys.argv[1], Path(sys.argv[2])
    raw = subprocess.run(
        ["psql", dsn, "-tAX", "-c", SQL], check=True, capture_output=True, text=True
    ).stdout
    data = json.loads(raw)
    glossary = json.loads((HERE / "glossary.json").read_text(encoding="utf-8"))
    missing = []
    schemas = sorted({t["schema"] for t in data["tables"]})
    for s in schemas:
        if s not in glossary["schemas"]:
            missing.append(f"schema {s}")
    for t in data["tables"]:
        key = f"{t['schema']}.{t['name']}"
        t["description"] = glossary["tables"].get(key)
        if t["description"] is None:
            missing.append(f"table {key}")
        for c in t["columns"]:
            c["description"] = glossary["columns"].get(c["name"])
            if c["description"] is None:
                missing.append(f"column {key}.{c['name']}")
    data["schemas"] = [
        {"name": s, "description": glossary["schemas"].get(s, "")} for s in schemas
    ]
    data["counts"] = {
        "schemas": len(schemas),
        "tables": len(data["tables"]),
        "columns": sum(len(t["columns"]) for t in data["tables"]),
        "rls_tables": sum(1 for t in data["tables"] if t["rls"]),
        "encrypted_columns": sum(
            1
            for t in data["tables"]
            for c in t["columns"]
            if c["name"].endswith("_enc")
        ),
    }
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(data["counts"]), file=sys.stderr)
    for m in missing:
        print(f"missing in glossary.json: {m}", file=sys.stderr)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
