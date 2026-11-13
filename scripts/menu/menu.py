"""The dashboard menu's one source (Yamen 2026-11-13): apps/dashboard/src/menu/menu.json, read by every script.

    from menu import load, systems, items, label
"""

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "apps" / "dashboard" / "src" / "menu" / "menu.json"
API_COPY = ROOT / "services" / "api" / "app" / "modules" / "features" / "menu.json"
LOCALES = ROOT / "apps" / "dashboard" / "src" / "i18n"


def load(path: Path = SOURCE) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def systems(menu: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Every system with its block key, in menu order."""
    menu = menu or load()
    return [{**s, "block": b["key"]} for b in menu["blocks"] for s in b["systems"]]


def items(menu: dict[str, Any] | None = None, planned: bool = True) -> list[dict[str, Any]]:
    """Every menu entry with its system and block (the home page first, system None); aliases kept, flagged."""
    menu = menu or load()
    out = [{**menu["home"], "system": None, "block": None}]
    for s in systems(menu):
        for i in s["items"]:
            if planned or not i.get("planned"):
                out.append({**i, "system": s["key"], "block": s["block"]})
    return out


def label(key: str, lang: str = "ar") -> str:
    """An entry's label, from the dashboard's translations (nav.<key>)."""
    nav = json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8"))["nav"]
    value = nav.get(key, key)
    return value if isinstance(value, str) else key


def system_of_path(path: str, menu: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """The system a dashboard path belongs to: its own entry (not an alias), else the longest entry path above it."""
    best: tuple[int, dict[str, Any]] | None = None
    for s in systems(menu):
        for i in s["items"]:
            if i.get("alias"):
                continue
            p = i["path"]
            if path == p or path.startswith(p.rstrip("/") + "/"):
                if best is None or len(p) > best[0]:
                    best = (len(p), s)
    return best[1] if best else None
