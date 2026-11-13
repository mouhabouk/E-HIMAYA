"""Fails when the menu and the screens drift apart (Yamen 2026-11-13: «حتى لا تعود التداخلات»).

    python3 scripts/menu/check.py

* the API's copy of the menu is the dashboard's source (scripts/menu/sync.py);
* every built entry of the menu opens a screen of the dashboard (a route in apps/dashboard/src/App.tsx), and a
  planned one has none yet (once built, its «planned» flag goes);
* every screen of the dashboard is reached from the menu: its path is an entry, or lies under one (a detail page, a
  tab), or is listed below as reached from inside another screen;
* an entry shown as a tab of another (``tabOf``) names an entry of the menu;
* every entry has its label in the three languages, and a path appears once, but for an alias;
* the 20 systems are numbered 1 to 20 in 4 blocks.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from menu import API_COPY, LOCALES, ROOT, SOURCE, items, load, systems  # noqa: E402

APP = ROOT / "apps" / "dashboard" / "src" / "App.tsx"
# Screens opened from inside another one, not from the menu.
REACHED_INSIDE = {
    "/callback",  # the sign-in's return
    "/reports/new",  # the «enter a report» button of the reports
    "/notifications/new",  # the «new notification» button
    "/memory/new",  # the «new entry» button of the national memory
}


def routes() -> set[str]:
    source = APP.read_text(encoding="utf-8")
    found = {"/" + p.lstrip("/") for p in re.findall(r'path="([^"]+)"', source) if p != "*"}
    # The first screen is the index route of the shell.
    return found | ({"/"} if re.search(r"<Route\s+index\b", source) else set())


def main() -> int:
    errors: list[str] = []
    if not API_COPY.exists() or API_COPY.read_text(encoding="utf-8") != SOURCE.read_text(encoding="utf-8"):
        errors.append(f"{API_COPY.relative_to(ROOT)} differs from the source: run python3 scripts/menu/sync.py")
    menu = load()
    sys_list = systems(menu)
    if [s["number"] for s in sys_list] != list(range(1, 21)):
        errors.append("the systems are not numbered 1 to 20")
    if len(menu["blocks"]) != 4:
        errors.append("the menu has not 4 blocks")
    screens = routes()
    entries = items(menu)
    seen: dict[str, str] = {}
    labels = {lang: json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8"))["nav"] for lang in ("ar", "fr", "en")}
    for e in entries:
        where = f"{e['path']} ({e['system'] or 'home'})"
        for lang, nav in labels.items():
            if not isinstance(nav.get(e["key"]), str):
                errors.append(f"{where}: no {lang} label nav.{e['key']}")
        if not e.get("alias"):
            if e["path"] in seen:
                errors.append(f"{where}: also in {seen[e['path']]} (mark one as an alias)")
            seen[e["path"]] = e["system"] or "home"
        if e.get("tabOf") and e["tabOf"] not in {x["path"] for x in entries if not x.get("tabOf")}:
            errors.append(f"{where}: a tab of {e['tabOf']}, which is no entry of the menu")
        if e.get("planned"):
            if e["path"] in screens:
                errors.append(f"{where}: planned, but the screen exists: remove «planned»")
        elif e["path"] not in screens:
            errors.append(f"{where}: in the menu, but no screen in App.tsx")
    built = [e["path"] for e in entries if not e.get("planned")]
    for screen in sorted(screens):
        if screen in REACHED_INSIDE or ":" in screen:
            continue
        if not any(screen == p or (p != "/" and screen.startswith(p.rstrip("/") + "/")) for p in built):
            errors.append(f"{screen}: a screen of the dashboard no entry of the menu reaches")
    for e in errors:
        print(f"menu: {e}", file=sys.stderr)
    if not errors:
        print(f"menu: {len(sys_list)} systems, {len(built)} entries, {len(entries) - len(built)} planned, all consistent")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
