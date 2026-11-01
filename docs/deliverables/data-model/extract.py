"""The relational model of the database, drawn and described (phase 5, point 7).

    python3 docs/deliverables/data-model/extract.py postgresql://ehimaya:...@localhost/ehimaya <out-dir>

Reads the live catalogue of a database migrated to head (tables, primary keys, every foreign key with its columns,
its cardinality and its ON DELETE rule) and the Arabic descriptions of ../data-dictionary/glossary.json, then writes
into <out-dir>:

- e-Himaya_Database.dbml: the whole model in DBML (open or edit it in dbdiagram.io or dbdocs, or turn it into SQL with
  the @dbml/cli tool); one TableGroup per schema, every column, note and relation with its cardinality;
- e-Himaya_Database.drawio: one editable page per schema plus an overview page (diagrams.net / draw.io desktop,
  offline); tables are containers with one row per key column, relations use crow's-foot ends;
- png/<schema>.png and png/00-overview.png: the same diagrams rendered by Graphviz, for the document;
- model.json: what build.js needs to write the Word document.

Graphviz (`dot`) lays the diagrams out; the same coordinates go into the draw.io file so both look alike.
"""

import html
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
GLOSSARY = HERE.parent / "data-dictionary" / "glossary.json"
SKIP = "('pg_catalog','information_schema','public','topology','tiger','tiger_data','pg_toast')"
SHOWN = 6  # plain columns shown under the key columns of a table in the diagrams

SQL = f"""
SELECT json_build_object(
 'migration', (SELECT version_num FROM alembic_version LIMIT 1),
 'tables', (SELECT json_agg(json_build_object(
    'schema', n.nspname, 'name', c.relname, 'rls', c.relrowsecurity,
    'columns', (SELECT json_agg(json_build_object(
        'name', a.attname, 'type', format_type(a.atttypid, a.atttypmod), 'nullable', NOT a.attnotnull,
        'default', pg_get_expr(d.adbin, d.adrelid),
        'pk', EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conrelid = c.oid AND k.contype = 'p'
                      AND a.attnum = ANY (k.conkey)),
        'unique', EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conrelid = c.oid AND k.contype = 'u'
                      AND k.conkey = ARRAY[a.attnum])) ORDER BY a.attnum)
      FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
      WHERE a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped))
    ORDER BY n.nspname, c.relname)
   FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE c.relkind IN ('r', 'p') AND n.nspname NOT IN {SKIP} AND NOT c.relispartition),
 'fks', (SELECT json_agg(json_build_object(
    'name', k.conname,
    'from', sn.nspname || '.' || sc.relname, 'to', tn.nspname || '.' || tc.relname,
    'from_cols', (SELECT json_agg(a.attname ORDER BY u.i) FROM unnest(k.conkey) WITH ORDINALITY u(n, i)
                  JOIN pg_attribute a ON a.attrelid = k.conrelid AND a.attnum = u.n),
    'to_cols', (SELECT json_agg(a.attname ORDER BY u.i) FROM unnest(k.confkey) WITH ORDINALITY u(n, i)
                JOIN pg_attribute a ON a.attrelid = k.confrelid AND a.attnum = u.n),
    'nullable', EXISTS (SELECT 1 FROM unnest(k.conkey) u(n) JOIN pg_attribute a
                        ON a.attrelid = k.conrelid AND a.attnum = u.n WHERE NOT a.attnotnull),
    'one_to_one', EXISTS (SELECT 1 FROM pg_constraint q WHERE q.conrelid = k.conrelid AND q.contype IN ('p', 'u')
                          AND q.conkey::int[] @> k.conkey::int[] AND q.conkey::int[] <@ k.conkey::int[]),
    'on_delete', k.confdeltype, 'on_update', k.confupdtype)
    ORDER BY sn.nspname, sc.relname, k.conname)
   FROM pg_constraint k
   JOIN pg_class sc ON sc.oid = k.conrelid JOIN pg_namespace sn ON sn.oid = sc.relnamespace
   JOIN pg_class tc ON tc.oid = k.confrelid JOIN pg_namespace tn ON tn.oid = tc.relnamespace
  WHERE k.contype = 'f' AND sn.nspname NOT IN {SKIP} AND NOT sc.relispartition)
)
"""

ACTIONS = {"a": "NO ACTION", "r": "RESTRICT", "c": "CASCADE", "n": "SET NULL", "d": "SET DEFAULT"}
AR_ACTIONS = {
    "NO ACTION": "يمنع الحذف ما دام سجل تابع موجودا",
    "RESTRICT": "يمنع الحذف ما دام سجل تابع موجودا",
    "CASCADE": "حذف الأصل يحذف التوابع معه",
    "SET NULL": "حذف الأصل يفرغ المرجع في التابع",
    "SET DEFAULT": "حذف الأصل يعيد المرجع إلى قيمته الافتراضية",
}
# A colour per schema in the diagrams: the design system's navy for headers, a tint for foreign tables.
NAVY, TINT, GREY, INK = "#1F3FA0", "#E8EDFA", "#F2F3F6", "#182038"


def short(t: str) -> str:
    return (
        t.replace("timestamp with time zone", "timestamptz")
        .replace("character varying", "varchar")
        .replace("double precision", "double")
        .replace("USER-DEFINED", "enum")
    )


def kind(fk: dict) -> str:
    """Cardinality seen from the referenced table: 1:1, 1:0..1, 1:N or 1:0..N (the child side is optional)."""
    many = "1" if fk["one_to_one"] else "N"
    return f"1:0..{many}" if fk["nullable"] else f"1:{many}"


def load(dsn: str) -> dict:
    raw = subprocess.run(["psql", dsn, "-tAX", "-c", SQL], check=True, capture_output=True, text=True).stdout
    data = json.loads(raw)
    glossary = json.loads(GLOSSARY.read_text(encoding="utf-8"))
    for t in data["tables"]:
        t["key"] = f"{t['schema']}.{t['name']}"
        t["description"] = glossary["tables"].get(t["key"], "")
    for fk in data["fks"]:
        fk["on_delete"] = ACTIONS[fk["on_delete"]]
        fk["on_update"] = ACTIONS[fk["on_update"]]
        fk["kind"] = kind(fk)
        fk["cross"] = fk["from"].split(".")[0] != fk["to"].split(".")[0]
    data["schemas"] = [
        {"name": s, "description": glossary["schemas"].get(s, "")}
        for s in sorted({t["schema"] for t in data["tables"]})
    ]
    return data


# ---------------------------------------------------------------- DBML


def dbml(data: dict) -> str:
    def q(name: str) -> str:
        return f'"{name}"' if not name.replace("_", "").isalnum() else name

    def note(text: str) -> str:
        return text.replace("\\", "\\\\").replace("'", "\\'")

    out = [
        "// ء-حماية / e-Himaya: the relational model (generated by docs/deliverables/data-model/extract.py).",
        f"// Migration {data['migration']}: {len(data['tables'])} tables, {len(data['fks'])} relations.",
        "// Open in https://dbdiagram.io (Import > DBML) or render offline with @dbml/cli (dbml2sql).",
        "",
        "Project e_himaya {",
        "  database_type: 'PostgreSQL'",
        "  Note: 'ء-حماية: منظومة التبليغ والوقاية وإدارة الأخطار. كل مخطط (schema) وحدة وظيفية.'",
        "}",
        "",
    ]
    fk_cols = defaultdict(set)
    for fk in data["fks"]:
        for c in fk["from_cols"]:
            fk_cols[fk["from"]].add(c)
    for t in data["tables"]:
        head = f"Table {t['schema']}.{q(t['name'])}"
        if t["rls"]:
            head += " [headercolor: #D7141A]"
        out.append(head + " {")
        pks = [c["name"] for c in t["columns"] if c["pk"]]
        for c in t["columns"]:
            settings = []
            if c["pk"] and len(pks) == 1:
                settings.append("pk")
            if not c["nullable"] and not c["pk"]:
                settings.append("not null")
            if c["unique"]:
                settings.append("unique")
            if c["default"] and len(c["default"]) < 60 and "nextval" not in c["default"]:
                settings.append(f"default: `{c['default']}`")
            typ = short(c["type"])
            typ = f'"{typ}"' if any(ch in typ for ch in " (),[]") else typ
            out.append(f"  {q(c['name'])} {typ}{' [' + ', '.join(settings) + ']' if settings else ''}")
        if len(pks) > 1:
            out += ["", "  indexes {", f"    ({', '.join(pks)}) [pk]", "  }"]
        desc = t["description"] + (" · عزل حسب الولاية (RLS)" if t["rls"] else "")
        out += ["", f"  Note: '{note(desc)}'", "}", ""]
    for fk in data["fks"]:
        src = f"{fk['from']}.({', '.join(fk['from_cols'])})" if len(fk["from_cols"]) > 1 else f"{fk['from']}.{fk['from_cols'][0]}"
        dst = f"{fk['to']}.({', '.join(fk['to_cols'])})" if len(fk["to_cols"]) > 1 else f"{fk['to']}.{fk['to_cols'][0]}"
        sign = "-" if fk["one_to_one"] else ">"
        settings = [f"delete: {fk['on_delete'].lower()}"]
        if fk["on_update"] != "NO ACTION":
            settings.append(f"update: {fk['on_update'].lower()}")
        out.append(f"Ref {fk['name']}: {src} {sign} {dst} [{', '.join(settings)}]")
    out.append("")
    for s in data["schemas"]:
        names = [t["key"] for t in data["tables"] if t["schema"] == s["name"]]
        out.append(f"TableGroup {s['name']} [note: '{note(s['description'])}'] {{")
        out += [f"  {n}" for n in names]
        out.append("}")
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------- Graphviz layout


def rows_of(t: dict, fkc: set[str]) -> tuple[list[tuple[str, str, str]], int]:
    """The rows a table shows: key columns first, then a few plain ones; and how many are left out."""
    keys = [c for c in t["columns"] if c["pk"] or c["name"] in fkc]
    plain = [c for c in t["columns"] if not (c["pk"] or c["name"] in fkc)]
    shown = keys + plain[:SHOWN]
    rows = []
    for c in shown:
        mark = "PK" if c["pk"] else ""
        if c["name"] in fkc:
            mark = (mark + " FK").strip()
        rows.append((mark, c["name"], short(c["type"])[:22]))
    return rows, len(plain) - min(len(plain), SHOWN)


def node_label(t: dict, rows: list, hidden: int, foreign: bool) -> str:
    head = NAVY if not foreign else "#8A93A8"
    body = "white" if not foreign else GREY
    cells = [
        f'<TR><TD COLSPAN="3" BGCOLOR="{head}" ALIGN="LEFT"><FONT COLOR="white"><B>'
        f"{html.escape(t['key'] if foreign else t['name'])}</B>{' (RLS)' if t['rls'] and not foreign else ''}</FONT></TD></TR>"
    ]
    if not foreign:
        for mark, name, typ in rows:
            colour = "#D7141A" if "PK" in mark else ("#1F3FA0" if mark else INK)
            cells.append(
                f'<TR><TD ALIGN="LEFT" BGCOLOR="{body}"><FONT COLOR="{colour}" POINT-SIZE="8">{mark or " "}</FONT></TD>'
                f'<TD ALIGN="LEFT" BGCOLOR="{body}" PORT="{html.escape(name)}">{html.escape(name)}</TD>'
                f'<TD ALIGN="LEFT" BGCOLOR="{body}"><FONT COLOR="#5B6478" POINT-SIZE="8">{html.escape(typ) or " "}</FONT></TD></TR>'
            )
        if hidden:
            cells.append(
                f'<TR><TD COLSPAN="3" ALIGN="LEFT" BGCOLOR="{body}"><FONT COLOR="#5B6478" POINT-SIZE="8">'
                f"+ {hidden} columns</FONT></TD></TR>"
            )
    return f'<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="3" COLOR="#C9CEDA">{"".join(cells)}</TABLE>>'


def arrows(fk: dict) -> tuple[str, str]:
    """Crow's-foot ends: (at the child, at the parent)."""
    child = ("tee" if fk["one_to_one"] else "crow") + ("odot" if fk["nullable"] else "tee")
    return child, "teetee"


def gv_id(key: str) -> str:
    return key.replace(".", "__")


def schema_graph(data: dict, schema: str, fkc: dict) -> tuple[str, dict]:
    tables = {t["key"]: t for t in data["tables"]}
    own = [t for t in data["tables"] if t["schema"] == schema]
    fks = [fk for fk in data["fks"] if fk["from"].startswith(schema + ".") or fk["to"].startswith(schema + ".")]
    foreign = sorted({k for fk in fks for k in (fk["from"], fk["to"]) if not k.startswith(schema + ".")})
    lines = [
        "digraph G {",
        '  graph [rankdir=RL, splines=true, overlap=false, nodesep=0.35, ranksep=0.9, fontname="Helvetica", bgcolor="white", pad=0.3];',
        '  node [shape=plaintext, fontname="Helvetica", fontsize=10];',
        '  edge [color="#5B6478", penwidth=1.1, dir=both, arrowsize=0.8];',
    ]
    layout = {}
    for t in own:
        rows, hidden = rows_of(t, fkc[t["key"]])
        layout[t["key"]] = {"rows": rows, "hidden": hidden, "foreign": False}
        lines.append(f"  {gv_id(t['key'])} [label={node_label(t, rows, hidden, False)}];")
    for k in foreign:
        layout[k] = {"rows": [], "hidden": 0, "foreign": True}
        lines.append(f"  {gv_id(k)} [label={node_label(tables[k], [], 0, True)}];")
    for fk in fks:
        tail, head = arrows(fk)
        label = ", ".join(fk["from_cols"])
        lines.append(
            f'  {gv_id(fk["from"])} -> {gv_id(fk["to"])} [arrowtail={tail}, arrowhead={head}, '
            f'xlabel="{label}", fontsize=7, fontcolor="#5B6478"];'
        )
    lines.append("}")
    return "\n".join(lines), layout


def overview_graph(data: dict) -> str:
    counts = defaultdict(int)
    for fk in data["fks"]:
        a, b = fk["from"].split(".")[0], fk["to"].split(".")[0]
        if a != b:
            counts[(a, b)] += 1
    size = defaultdict(int)
    for t in data["tables"]:
        size[t["schema"]] += 1
    lines = [
        "digraph G {",
        '  graph [layout=dot, rankdir=LR, splines=true, nodesep=0.25, ranksep=1.1, fontname="Helvetica", pad=0.3];',
        f'  node [shape=box, style="rounded,filled", fillcolor="{TINT}", color="{NAVY}", fontname="Helvetica", fontsize=11];',
        '  edge [color="#8A93A8", fontname="Helvetica", fontsize=8, arrowsize=0.6];',
    ]
    for s in data["schemas"]:
        lines.append(f'  {s["name"]} [label="{s["name"]}\\n{size[s["name"]]} tables"];')
    for (a, b), n in sorted(counts.items()):
        lines.append(f'  {a} -> {b} [label="{n}", penwidth={min(4, 0.6 + n / 4):.1f}];')
    lines.append("}")
    return "\n".join(lines)


def dot(source: str, fmt: str) -> bytes:
    return subprocess.run(["dot", f"-T{fmt}"], input=source.encode(), check=True, capture_output=True).stdout


# ---------------------------------------------------------------- draw.io


def drawio(data: dict, pages: list[tuple[str, dict, dict]]) -> str:
    """pages: (name, graphviz json, layout of each table)."""
    tables = {t["key"]: t for t in data["tables"]}
    diagrams = []
    for name, gv, layout in pages:
        height = float(gv["bb"].split(",")[3])
        cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
        ids = {}
        for obj in gv.get("objects", []):
            key = obj["name"].replace("__", ".", 1)
            x, y = (float(v) for v in obj["pos"].split(","))
            w, h = float(obj["width"]) * 72, float(obj["height"]) * 72
            left, top = x - w / 2, height - y - h / 2
            cid = f"t{len(ids)}"
            ids[key] = cid
            if name == "00-overview":
                label = html.escape(obj["label"].replace("\\n", "<br>"))
                cells.append(
                    f'<mxCell id="{cid}" value="{label}" style="rounded=1;whiteSpace=wrap;html=1;fillColor={TINT};'
                    f'strokeColor={NAVY};fontColor={INK};" vertex="1" parent="1">'
                    f'<mxGeometry x="{left:.0f}" y="{top:.0f}" width="{w:.0f}" height="{h:.0f}" as="geometry"/></mxCell>'
                )
                continue
            info = layout[key]
            t = tables[key]
            title = key if info["foreign"] else t["name"] + (" (RLS)" if t["rls"] else "")
            fill = "#8A93A8" if info["foreign"] else NAVY
            row_h = 18
            rows = info["rows"] + ([("", f"+ {info['hidden']} columns", "")] if info["hidden"] else [])
            box_h = 26 + row_h * len(rows)
            cells.append(
                f'<mxCell id="{cid}" value="{html.escape(title)}" style="swimlane;fontStyle=1;childLayout=stackLayout;'
                f"horizontal=1;startSize=26;horizontalStack=0;resizeParent=1;resizeParentMax=0;resizeLast=0;"
                f'collapsible=1;marginBottom=0;html=1;fillColor={fill};fontColor=#FFFFFF;strokeColor=#C9CEDA;swimlaneFillColor=#FFFFFF;" '
                f'vertex="1" parent="1"><mxGeometry x="{left:.0f}" y="{top:.0f}" width="{max(w, 170):.0f}" '
                f'height="{box_h}" as="geometry"/></mxCell>'
            )
            for i, (mark, col, typ) in enumerate(rows):
                text = f"{mark + ' ' if mark else ''}{col}{'  : ' + typ if typ else ''}"
                style = "fontStyle=4;" if "PK" in mark else ("fontColor=#1F3FA0;" if mark else "")
                cells.append(
                    f'<mxCell id="{cid}r{i}" value="{html.escape(text)}" style="text;strokeColor=none;fillColor=none;'
                    f'align=left;verticalAlign=middle;spacingLeft=4;spacingRight=4;overflow=hidden;rotatable=0;'
                    f'points=[[0,0.5],[1,0.5]];portConstraint=eastwest;html=1;{style}" vertex="1" parent="{cid}">'
                    f'<mxGeometry y="{26 + i * row_h}" width="{max(w, 170):.0f}" height="{row_h}" as="geometry"/></mxCell>'
                )
        for i, edge in enumerate(gv.get("edges", [])):
            src = gv["objects"][edge["tail"]]["name"].replace("__", ".", 1)
            dst = gv["objects"][edge["head"]]["name"].replace("__", ".", 1)
            if name == "00-overview":
                style = "endArrow=block;endFill=1;html=1;strokeColor=#8A93A8;"
                value = html.escape(edge.get("label", ""))
            else:
                start = {"crowtee": "ERoneToMany", "crowodot": "ERzeroToMany", "teetee": "ERmandOne",
                         "teeodot": "ERzeroToOne"}.get(edge.get("arrowtail", ""), "ERmany")
                style = (f"edgeStyle=entityRelationEdgeStyle;html=1;endArrow=ERmandOne;startArrow={start};"
                         "strokeColor=#5B6478;endFill=0;startFill=0;")
                value = ""
            cells.append(
                f'<mxCell id="e{i}" value="{value}" style="{style}" edge="1" parent="1" source="{ids[src]}" '
                f'target="{ids[dst]}"><mxGeometry relative="1" as="geometry"/></mxCell>'
            )
        diagrams.append(
            f'<diagram id="{name}" name="{name}"><mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" '
            f'tooltips="1" connect="1" arrows="1" fold="1" page="0" pageScale="1" math="0" shadow="0">'
            f'<root>{"".join(cells)}</root></mxGraphModel></diagram>'
        )
    return f'<mxfile host="e-Himaya" type="device">{"".join(diagrams)}</mxfile>\n'


def main() -> int:
    dsn, out = sys.argv[1], Path(sys.argv[2])
    (out / "png").mkdir(parents=True, exist_ok=True)
    data = load(dsn)
    (out / "e-Himaya_Database.dbml").write_text(dbml(data), encoding="utf-8")
    fkc: dict[str, set[str]] = defaultdict(set)
    for fk in data["fks"]:
        fkc[fk["from"]].update(fk["from_cols"])
    pages = []
    ov = overview_graph(data)
    (out / "png" / "00-overview.png").write_bytes(dot(ov, "png"))
    pages.append(("00-overview", json.loads(dot(ov, "json")), {}))
    for s in data["schemas"]:
        src, layout = schema_graph(data, s["name"], fkc)
        (out / "png" / f"{s['name']}.png").write_bytes(dot(src.replace("digraph G {", "digraph G {\n  graph [dpi=110];", 1), "png"))
        gv = json.loads(dot(src, "json"))
        pages.append((s["name"], gv, layout))
    (out / "e-Himaya_Database.drawio").write_text(drawio(data, pages), encoding="utf-8")
    model = {
        "migration": data["migration"],
        "schemas": data["schemas"],
        "tables": [{k: t[k] for k in ("schema", "name", "key", "rls", "description")} | {"columns": len(t["columns"])}
                   for t in data["tables"]],
        "fks": data["fks"],
        "actions": AR_ACTIONS,
    }
    (out / "model.json").write_text(json.dumps(model, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(data['tables'])} tables, {len(data['fks'])} relations, migration {data['migration']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
