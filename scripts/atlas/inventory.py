"""Inventory of the dashboard's screens for the flowchart atlas (Yamen, 2026-11-13).

For every route of apps/dashboard/src/App.tsx: the page file, its place in the main menu (system, block and item, in
Arabic, from apps/dashboard/src/menu/menu.json), the API endpoints the page and its own components call, and the database tables behind them. Everything
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

sys.path.insert(0, str(REPO / "scripts" / "menu"))
from menu import items as menu_items  # noqa: E402
from menu import load as load_menu  # noqa: E402
from menu import systems as menu_systems  # noqa: E402

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
    """{path: {group, group_key, block, item}} from the menu's one source (apps/dashboard/src/menu/menu.json): the
    group is the system ("7. مركز تحليل الصور والفيديو"), the block its place among the 4 blocks."""
    out: dict[str, dict] = {}
    for e in menu_items(load_menu()):
        if e.get("alias") or e.get("planned"):
            continue
        sys_spec = next((s for s in menu_systems() if s["key"] == e["system"]), None)
        group = f"{sys_spec['number']}. {sys_spec['names']['ar']}" if sys_spec else ar.get("nav.home", "الرئيسية")
        out[e["path"]] = {
            "group_key": e["system"] or "home",
            "group": group,
            "block": e["block"] or "home",
            "item": ar.get(f"nav.{e['key']}", e["key"]),
        }
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
