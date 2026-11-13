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
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "menu"))
from menu import system_of_path  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MOBILE = REPO / "apps/mobile/lib"
# The smart app is one app with several profiles, and the staff app holds three trades (Yamen, 2026-11-13).
SURFACES = ["لوحة التحكم", "البوابة",
            "التطبيق الذكي · مواطن", "التطبيق الذكي · متطوع", "التطبيق الذكي · طبيب متطوع", "التطبيق الذكي · مؤسسة",
            "تطبيق الأعوان · عون الميدان", "تطبيق الأعوان · تطبيق التفقد", "تطبيق الأعوان · عون السلامة (تفقد مؤسسة)"]
SHEET = {"لوحة التحكم": "لوحة التحكم", "البوابة": "البوابة", "تطبيق المواطن": "citizen", "تطبيق الأعوان": "staff"}
CITIZEN = {"volunteer": [3], "doctor": [4], "institution": [5], "availability": [3, 4]}
MOD = re.compile(r"app/modules/([^/]+)/")
MEMBER = re.compile(r"^(?:  |)(?!//|@|return|if|for|switch|case|final _)[^=;{}]*?\b([A-Za-z_]\w{3,})\s*(?:<[^()]*>)?\s*\(")
TOP = re.compile(r"^(?:final|const|late)\s+(?:[\w<>?, ]+\s+)?([A-Za-z_]\w{3,})\s*=")
STOP = {"build", "copyWith", "toJson", "fromJson", "dispose", "initState", "toString", "guardApi", "Future", "Text",
        "setState", "watch", "read", "listen", "List", "Map", "then", "when", "call", "main", "super", "this"}


class Mobile:
    """Finds the screens of the Flutter app that reach each API call: the method that holds the call, then the files
    that use that method (through a controller or a provider, up to three steps)."""

    def __init__(self) -> None:
        self.files = {p: p.read_text(encoding="utf-8").splitlines() for p in MOBILE.rglob("*.dart")}
        self.text = {p: "\n".join(v) for p, v in self.files.items()}
        self.memo: dict[str, set[tuple[int, str]]] = {}

    def enclosing(self, path: Path, line: int) -> str | None:
        lines = self.files.get(path, [])
        for i in range(min(line, len(lines)) - 1, -1, -1):
            ln = lines[i]
            if ln.startswith("    ") or not ln.strip():
                continue
            m = TOP.match(ln) or MEMBER.match(ln)
            if m and m.group(1) not in STOP:
                return m.group(1)
        return None

    @staticmethod
    def is_screen(path: Path) -> bool:
        rel = path.relative_to(MOBILE).parts
        if rel[0] == "features":
            return rel[1] != "admin"
        return rel[0] == "staff" and re.search(r"_(screens?|sheet|flow|box)$", path.stem) is not None

    @staticmethod
    def place(path: Path) -> list[tuple[int, str]]:
        rel = path.relative_to(MOBILE).parts
        if rel[0] == "features":
            return [(i, rel[1]) for i in CITIZEN.get(rel[1], [2])]
        if rel[0] == "staff":
            trade = 7 if rel[1] == "inspect" else 8 if rel[1] == "prevention" else 6
            return [(trade, path.stem)]
        return []

    def screens(self, path: Path, line: int, depth: int = 0, seen: set | None = None) -> set[tuple[int, str]]:
        seen = seen if seen is not None else set()
        name = self.enclosing(path, line)
        if not name or name in seen or depth > 3:
            return set()
        if name in self.memo:
            return self.memo[name]
        seen.add(name)
        pat = re.compile(r"\b" + re.escape(name) + r"\b")
        found: set[tuple[int, str]] = set()
        for f, lines in self.files.items():
            if f == path or not pat.search(self.text[f]):
                continue
            if self.is_screen(f) or depth == 3:
                found.update(self.place(f) if self.is_screen(f) else [])
                continue
            for i, ln in enumerate(lines, 1):
                if pat.search(ln):
                    found |= self.screens(f, i, depth + 1, seen)
        self.memo[name] = found
        return found


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
    mob = Mobile()
    scr_mod: dict[tuple[str, str], set[str]] = defaultdict(set)
    scr_files: dict[tuple[str, str], set[str]] = defaultdict(set)
    scr_calls: dict[tuple[str, str], int] = defaultdict(int)
    for row in list(ws.iter_rows(values_only=True))[1:]:
        _, surface, screen, call, verb, path, fn, tbls, _fields = (list(row) + [None] * 9)[:9]
        kind = SHEET.get(surface)
        if not kind or not screen:
            continue
        if kind in ("citizen", "staff") and call:
            f, ln = call.rsplit(":", 1)
            keys = {(SURFACES[i], label) for i, label in mob.screens(REPO / f, int(ln))}
            if not keys:
                keys = {(SURFACES[2 if kind == "citizen" else 6], "خدمات مشتركة")}
        else:
            keys = {(surface, screen)}
        m = MOD.search(fn or "")
        for key in keys:
            scr_calls[key] += 1
            if call:
                scr_files[key].add(call.rsplit(":", 1)[0])
            if m:
                scr_mod[key].add(m.group(1))
        if m and tbls and "على مستوى الوحدة" not in tbls:
            mod_tables[m.group(1)].update(t.strip() for t in tbls.split("،") if t.strip() in tables)

    # ---- nodes on rings, ordered so threads cross as little as possible (barycentre of the ring inside)
    screens = sorted(scr_calls, key=lambda k: (SURFACES.index(k[0]), k[1]))
    used_mods = sorted({m for s in screens for m in scr_mod[s]} | {m for m in mod_tables if mod_tables[m]})
    R = {"surface": 215, "screen": 430, "module": 700, "table": 980}
    ang: dict[str, float] = {}

    def ring(ids: list[str], weight: dict[str, float] | None = None) -> None:
        tot = sum((weight or {}).get(i, 1) for i in ids)
        acc = 0.0
        for i in ids:
            w = (weight or {}).get(i, 1)
            ang[i] = (acc + w / 2) / tot * 2 * math.pi - math.pi / 2
            acc += w

    sid = {s: f"s:{s[0]}|{s[1]}" for s in screens}
    # each surface gets a sector of at least 6 % of the circle, so the small apps stay readable beside the dashboard
    count = {sf: sum(1 for s in screens if s[0] == sf) for sf in SURFACES}
    share = {sf: max(count[sf] / len(screens), 0.06) for sf in SURFACES if count[sf]}
    ring([sid[s] for s in screens], {sid[s]: share[s[0]] / count[s[0]] for s in screens})
    # the surfaces sit evenly on the inner ring, in the order of their sectors, so none hides another
    order = sorted(share, key=lambda sf: SURFACES.index(sf))
    for i, sf in enumerate(order):
        ang[f"u:{sf}"] = (i + .5) / len(order) * 2 * math.pi - math.pi / 2

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
        if count[sf]:
            add(f"u:{sf}", "surface", sf, n=count[sf])
    def system_of(label: str) -> str | None:
        """The system of a dashboard screen (its first path), from the menu's one source."""
        first = label.split("، ")[0].strip()
        spec = system_of_path(first) if first.startswith("/") else None
        return f"{spec['number']}. {spec['names']['ar']}" if spec else None

    for s in screens:
        extra = {"sys": name} if (name := system_of(s[1])) else {}
        add(sid[s], "screen", s[1], sf=SURFACES.index(s[0]), files=sorted(scr_files[s]), calls=scr_calls[s], **extra)
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

    data = {"surfaces": SURFACES, "nodes": nodes, "links": links, "arcs": arcs, "R": R, "built": date.today().isoformat(),
            "counts": {"surfaces": len(SURFACES), "screens": len(screens), "modules": len(mids), "tables": len(tids),
                       "schemas": len(by_schema), "links": len(links)}}
    html = (HERE / "web.html").read_text(encoding="utf-8").replace("__VIEWER__", (HERE / "viewer.js").read_text(encoding="utf-8"))
    a.out.write_text(html.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")), encoding="utf-8")
    print(f"web: {data['counts']} → {a.out}")


if __name__ == "__main__":
    main()
