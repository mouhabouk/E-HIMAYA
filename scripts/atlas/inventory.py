"""Inventory of the dashboard's screens for the flowchart atlas (Yamen, 2026-11-13).

For every route of apps/dashboard/src/App.tsx: the page file, its place in the main menu (group and item, in
Arabic), the API endpoints the page and its own components call, and the database tables behind them. Everything
is read from the source, so running it again keeps the atlas true after each merge.

    cd services/api && .venv/bin/python ../../scripts/ui_reference/backend_dump.py > /tmp/backend.json
    python3 scripts/atlas/inventory.py --backend /tmp/backend.json --out /tmp/atlas/inventory.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DASH = REPO / "apps/dashboard/src"

_spec = importlib.util.spec_from_file_location("ui_ref", REPO / "scripts/ui_reference/build.py")
assert _spec and _spec.loader
ui = importlib.util.module_from_spec(_spec)
sys.modules["ui_ref"] = ui
_spec.loader.exec_module(ui)


def flatten(node: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in node.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten(v, key))
        elif isinstance(v, str):
            out[key] = v
    return out


def menu(ar: dict[str, str]) -> dict[str, dict]:
    """{path: {group, group_key, item}} from the e(...) calls of Navigation.tsx, grouped by the `key:` they follow."""
    text = (DASH / "components/Navigation.tsx").read_text(encoding="utf-8")
    body = text[text.find("const groups: NavGroup[]") :]
    out: dict[str, dict] = {}
    group = None
    for m in re.finditer(r'key: "(\w+)"|e\(\s*[^"]*?"(/[^"]*)",\s*"\w+",\s*"\w+",\s*"(\w+)"', body, re.S):
        if m.group(1):
            group = m.group(1)
            continue
        path, key = m.group(2), m.group(3)
        out.setdefault(
            path,
            {"group_key": group, "group": ar.get(f"nav.group.{group}", group), "item": ar.get(f"nav.{key}", key)},
        )
    return out


def components_of(page: Path, depth: int = 2) -> set[Path]:
    """The page and the components it imports from src/components, src/pages (sub-panels) up to `depth` levels."""
    seen = {page.resolve()}
    frontier = [page.resolve()]
    for _ in range(depth):
        nxt = []
        for f in frontier:
            for m in ui.IMPORT.finditer(f.read_text(encoding="utf-8")):
                t = ui.resolve_import(f, m.group(1) or m.group(2))
                if t and t.suffix == ".tsx" and "/components/" in str(t) or (t and "/pages/" in str(t)):
                    t = t.resolve()
                    if t not in seen and t.name not in ("Layout.tsx", "Navigation.tsx"):
                        seen.add(t)
                        nxt.append(t)
        frontier = nxt
    return seen


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    ar = flatten(json.loads((DASH / "i18n/ar.json").read_text(encoding="utf-8")))
    backend = ui.Backend.load(Path(args.backend))
    methods = ui.web_api_methods(DASH / "lib")
    page_routes = ui.web_routes(DASH / "App.tsx")
    nav = menu(ar)
    screens = []
    for page, paths in page_routes.items():
        files = components_of(page)
        calls: dict[tuple[str, str], set[str]] = {}
        for f in files:
            for verb, url, _line in ui.web_calls(f, methods):
                r = backend.match(verb, url)
                calls.setdefault((verb, url), set()).update(r["tables"] if r else [])
        for path in sorted(set(paths)):
            if path in ("/callback",):
                continue
            screens.append(
                {
                    "route": path,
                    "page": ui.rel(page),
                    "components": sorted(ui.rel(f) for f in files if f != page.resolve()),
                    "menu": nav.get(path),
                    "api": [{"verb": v, "path": u, "tables": sorted(t)} for (v, u), t in sorted(calls.items())],
                }
            )
    screens.sort(key=lambda s: s["route"])
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"screens": screens}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(screens)} screens")


if __name__ == "__main__":
    main()
