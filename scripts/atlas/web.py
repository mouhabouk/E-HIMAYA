"""Builds the spider web of the system (Yamen, 2026-11-13): every surface, its screens, the server modules they call
and the database tables those modules touch, as concentric rings joined by threads.

Reads the "الشاشات والبيانات" sheet of the UI reference workbook (scripts/ui_reference/build.py) and the backend dump
(scripts/ui_reference/backend_dump.py), so a new screen, endpoint or table shows on the next run.

    python3 scripts/atlas/web.py --xlsx ehimaya-ui-reference.xlsx --backend backend.json --out web.html
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

from openpyxl import load_workbook

HERE = Path(__file__).resolve().parent
SURFACES = ["لوحة التحكم", "البوابة", "تطبيق المواطن", "تطبيق الأعوان"]
MOD = re.compile(r"app/modules/([^/]+)/")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", type=Path, required=True)
    ap.add_argument("--backend", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    backend = json.loads(a.backend.read_text(encoding="utf-8"))
    tables = sorted({f"{t['schema']}.{t['table']}" for t in backend["tables"]})
    mod_tables: dict[str, set[str]] = defaultdict(set)
    mod_files: dict[str, set[str]] = defaultdict(set)
    for r in backend["routes"]:
        m = MOD.search(r.get("file") or "")
        if not m:
            continue
        mod_files[m.group(1)].add(r["file"])
        mod_tables[m.group(1)].update(t for t in r.get("tables", []) if t in tables)

    ws = load_workbook(a.xlsx, read_only=True)["الشاشات والبيانات"]
    scr_mod: dict[tuple[str, str], set[str]] = defaultdict(set)
    scr_files: dict[tuple[str, str], set[str]] = defaultdict(set)
    scr_calls: dict[tuple[str, str], int] = defaultdict(int)
    for row in list(ws.iter_rows(values_only=True))[1:]:
        _, surface, screen, call, verb, path, fn, tbls, _fields = (list(row) + [None] * 9)[:9]
        if surface not in SURFACES or not screen:
            continue
        key = (surface, screen)
        scr_calls[key] += 1
        if call:
            scr_files[key].add(call.rsplit(":", 1)[0])
        m = MOD.search(fn or "")
        if m:
            scr_mod[key].add(m.group(1))
            if tbls and "على مستوى الوحدة" not in tbls:
                mod_tables[m.group(1)].update(t.strip() for t in tbls.split("،") if t.strip() in tables)

    # ---- nodes on rings, ordered so threads cross as little as possible (barycentre of the ring inside)
    screens = sorted(scr_calls, key=lambda k: (SURFACES.index(k[0]), k[1]))
    used_mods = sorted({m for s in screens for m in scr_mod[s]} | {m for m in mod_tables if mod_tables[m]})
    R = {"surface": 150, "screen": 430, "module": 700, "table": 980}
    ang: dict[str, float] = {}

    def ring(ids: list[str], weight: dict[str, float] | None = None) -> None:
        tot = sum((weight or {}).get(i, 1) for i in ids)
        acc = 0.0
        for i in ids:
            w = (weight or {}).get(i, 1)
            ang[i] = (acc + w / 2) / tot * 2 * math.pi - math.pi / 2
            acc += w

    sid = {s: f"s:{s[0]}|{s[1]}" for s in screens}
    # each surface gets a sector of at least 15 % of the circle, so the small apps stay readable beside the dashboard
    count = {sf: sum(1 for s in screens if s[0] == sf) for sf in SURFACES}
    share = {sf: max(count[sf] / len(screens), 0.15) for sf in SURFACES if count[sf]}
    ring([sid[s] for s in screens], {sid[s]: share[s[0]] / count[s[0]] for s in screens})
    for sf in share:
        xs = [ang[sid[s]] for s in screens if s[0] == sf]
        ang[f"u:{sf}"] = math.atan2(sum(map(math.sin, xs)), sum(map(math.cos, xs)))

    def bary(ids: list[str], links: dict[str, list[str]]) -> list[str]:
        def a_of(i: str) -> float:
            xs = [ang[j] for j in links.get(i, []) if j in ang]
            if not xs:
                return 9.0
            return (math.atan2(sum(map(math.sin, xs)), sum(map(math.cos, xs))) + 2.5 * math.pi) % (2 * math.pi)
        return sorted(ids, key=a_of)

    mod_links = defaultdict(list)
    for s in screens:
        for m in scr_mod[s]:
            mod_links[f"m:{m}"].append(sid[s])
    mids = bary([f"m:{m}" for m in used_mods], mod_links)
    ring(mids)
    tab_links = defaultdict(list)
    for m in used_mods:
        for t in mod_tables[m]:
            tab_links[f"t:{t}"].append(f"m:{m}")
    # tables stay grouped by schema; schemas are ordered by the barycentre of their tables' modules
    by_schema = defaultdict(list)
    for t in tables:
        by_schema[t.split(".")[0]].append(f"t:{t}")
    sch_links = {s: [m for t in ts for m in tab_links.get(t, [])] for s, ts in by_schema.items()}
    sch_order = bary(list(by_schema), sch_links)
    tids = [t for s in sch_order for t in bary(by_schema[s], tab_links)]
    ring(tids)

    nodes, links = [], []

    def add(i: str, kind: str, label: str, **extra) -> None:
        r, t = R[kind], ang.get(i, 0.0)
        nodes.append({"id": i, "k": kind, "l": label, "x": round(r * math.cos(t), 1), "y": round(r * math.sin(t), 1),
                      "a": round(t, 4), **extra})

    for sf in SURFACES:
        add(f"u:{sf}", "surface", sf, n=sum(1 for s in screens if s[0] == sf))
    for s in screens:
        add(sid[s], "screen", s[1], sf=SURFACES.index(s[0]), files=sorted(scr_files[s]), calls=scr_calls[s])
        links.append([f"u:{s[0]}", sid[s]])
        for m in sorted(scr_mod[s]):
            links.append([sid[s], f"m:{m}"])
    for m in mids:
        name = m[2:]
        add(m, "module", name, files=sorted(mod_files[name]))
        for t in sorted(mod_tables[name]):
            links.append([m, f"t:{t}"])
    for t in tids:
        add(t, "table", t[2:], used=bool(tab_links.get(t)))
    arcs = []
    for s in sch_order:
        xs = [ang[t] for t in by_schema[s]]
        arcs.append({"s": s, "a0": min(xs), "a1": max(xs), "n": len(xs)})

    data = {"nodes": nodes, "links": links, "arcs": arcs, "R": R, "built": date.today().isoformat(),
            "counts": {"surfaces": len(SURFACES), "screens": len(screens), "modules": len(mids), "tables": len(tids),
                       "schemas": len(by_schema), "links": len(links)}}
    html = (HERE / "web.html").read_text(encoding="utf-8")
    a.out.write_text(html.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")), encoding="utf-8")
    print(f"web: {data['counts']} → {a.out}")


if __name__ == "__main__":
    main()
