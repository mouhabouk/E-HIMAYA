"""The atlas cards of the public portal, the citizen app and the staff app (Yamen, 2026-11-13).

Joins the curated screens of apps_content.py with their capture: the portal's (scripts/atlas/capture_portal.mjs,
<dir>/capture.json) and the mobile apps' (apps/mobile/test/atlas, one <id>.json per screen). Each request a screen
sent is matched to the API route behind it and to its tables (scripts/ui_reference/backend_dump.py), so the card says
what the screen reads and what it writes. build.py adds these screens to the dashboard's.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from apps_catalog import CATALOG, VALUE  # noqa: E402
from apps_catalog import GROUPS as CAT_GROUPS  # noqa: E402
from apps_catalog import WHO as CAT_WHO  # noqa: E402
from apps_content import SCREENS, SURFACES, WHO  # noqa: E402

WRITE = ("POST", "PUT", "PATCH", "DELETE")
# Asked by every screen when the app starts (environment, version, hidden features): left out of each card.
COMMON = {"/api/v1/app/environment", "/api/v1/app/features", "/api/v1/app/version"}


def _backend(path: Path | None):
    if not path:
        return None
    spec = importlib.util.spec_from_file_location("ui_ref_apps", HERE.parent / "ui_reference/build.py")
    assert spec and spec.loader
    ui = importlib.util.module_from_spec(spec)
    sys.modules["ui_ref_apps"] = ui
    spec.loader.exec_module(ui)
    return ui.Backend.load(path)


def _region(regions: list[dict], words: str | None) -> int | None:
    if not words:
        return None
    w = words.strip().lower()
    for i, r in enumerate(regions):
        if r["kind"] != "menu" and w in r["label"].lower():
            return i
    for i, r in enumerate(regions):
        if w in r["label"].lower():
            return i
    return None


def _flow(sc: dict, cap: dict, names: dict[str, str]) -> list[dict]:
    regs = cap.get("regions", [])
    came = " · ".join((names.get(i, "") + (" ← " if i and names.get(i) else "") + how) for i, how in sc["from"])
    nodes = [{"t": "term", "l": "يصل إليها من", "s": came, "r": None}]
    reads = {a["path"] for a in cap.get("api", []) if a["verb"] not in WRITE and a["path"] not in COMMON}
    nodes.append({"t": "io", "l": sc["title"], "s": f"تقرأ {len(reads)} نداء من الخادم" if reads else "تُعرض من الهاتف دون نداء",
                  "r": next((i for i, r in enumerate(regs) if r["kind"] == "title"), None)})
    kinds = {"do": "proc", "in": "io", "ask": "dec", "see": "proc"}
    for kind, text, words in sc["steps"]:
        nodes.append({"t": kinds[kind], "l": text, "s": {"see": "تعرض", "do": "يفعل", "in": "يُدخل", "ask": "يختار"}[kind],
                      "r": _region(regs, words), "act": kind == "do"})
    nxt = " · ".join(names.get(i) or how for i, how in sc["next"]) or "نهاية المسار"
    nodes.append({"t": "term", "l": "ينتقل إلى", "s": nxt, "r": None})
    return nodes


PAGE = {"citizen": "apps/mobile/lib/core/routing/app_router.dart → ", "staff": "apps/mobile/lib/staff/ · ",
        "portal": "apps/portal/src/App.tsx → "}
KIND_STEP = {"form": "in", "tabs": "ask", "action": "do", "section": "see", "window": "see", "map": "see"}


def _surface(sid: str) -> str:
    return {"p": "portal", "c": "citizen", "w": "citizen", "s": "staff"}[sid.split("-")[0][0]]


def _auto(sid: str, cap: dict) -> dict:
    """A card for a capture without a hand-told entry: its catalog line, and steps read from its regions."""
    surface = _surface(sid)
    group, parent, title, purpose = CATALOG.get(sid, ("other", None, cap.get("title") or sid, cap.get("title") or ""))
    if surface == "portal" and group == "other":
        group = "orgs"
    steps, seen = [], set()
    for r in cap.get("regions", []):
        label = r["label"].split(" · ")[0].strip()
        if r["kind"] in ("title", "menu") or not label or label in seen or len(steps) >= 7:
            continue
        seen.add(label)
        kind = KIND_STEP.get(r["kind"], "see")
        text = {"in": "يُدخل: ", "do": "يضغط «", "ask": "يختار تبويبا: ", "see": "يرى: "}[kind] + label[:60] + ("»" if kind == "do" else "")
        steps.append((kind, text, label))
    window = sid.startswith(("w-", "sw-", "pw-"))
    frm = [(parent, "زر في الشاشة" if window else "من القائمة أو زر في الشاشة")] if parent else [(None, "فتح التطبيق" if surface != "portal" else "رابط البوابة")]
    nxt = [(parent, "إغلاق النافذة أو تأكيدها، والعودة")] if window and parent else []
    return {"id": sid, "surface": surface, "group": group, "route": cap.get("route") or cap.get("path") or "",
            "title": title, "page": PAGE.get(surface, "") + (cap.get("route") or cap.get("path") or ""), "who": CAT_WHO.get(f"{surface}:{group}", []),
            "purpose": purpose, "value": VALUE.get(f"{surface}:{group}", ""), "from": frm, "steps": steps, "next": nxt,
            "window": window}


def screens(portal: Path | None, mobile: Path | None, backend: Path | None, out: Path) -> list[dict]:
    be = _backend(backend)
    caps: dict[str, dict] = {}
    if portal and (portal / "capture.json").exists():
        for s in json.loads((portal / "capture.json").read_text(encoding="utf-8"))["screens"]:
            if s.get("shot"):
                caps[s["id"]] = {**s, "base": portal}
    if mobile and mobile.exists():
        for f in mobile.glob("*.json"):
            s = json.loads(f.read_text(encoding="utf-8"))
            if s.get("shot"):
                caps[s["id"]] = {**s, "base": mobile}
    curated = {s["id"] for s in SCREENS}
    order = {k: i for i, k in enumerate(CATALOG)}
    extra = sorted((i for i in caps if i not in curated), key=lambda i: (order.get(i, 10_000), i))
    all_screens = [*SCREENS, *(_auto(i, caps[i]) for i in extra)]
    for sc in all_screens:  # a curated screen is filed in its catalog group
        if sc["id"] in CATALOG and sc["id"] in curated:
            sc["group"] = CATALOG[sc["id"]][0]
    names = {s["id"]: s["title"] for s in all_screens}
    names.update({i: c[2] for i, c in CATALOG.items() if i not in names})
    known = {s["id"] for s in all_screens if s["id"] in caps}
    (out / "shots").mkdir(parents=True, exist_ok=True)
    result = []
    for sc in all_screens:
        cap = caps.get(sc["id"])
        if not cap:
            continue
        shutil.copyfile(cap["base"] / cap["shot"], out / cap["shot"])
        api, seen = [], set()
        for a in cap.get("api", []):
            key = (a["verb"], a["path"])
            if key in seen or a["path"] in COMMON:
                continue
            seen.add(key)
            m = be.match(a["verb"], a["path"]) if be else None
            api.append({"verb": a["verb"], "path": a["path"], "tables": sorted(m["tables"]) if m else []})
        tables = sorted({t for a in api for t in a["tables"]})
        link = lambda pairs: [{"id": i if i in known else None, "label": names.get(i, "") if i else "", "how": how} for i, how in pairs]  # noqa: E731
        surface = sc["surface"]
        result.append({
            "id": sc["id"], "surface": surface, "surfaceName": SURFACES[surface], "phone": surface != "portal",
            "route": sc["route"], "path": cap.get("path") or sc["route"], "shot": cap["shot"], "height": cap.get("height", 900),
            "group": f"{SURFACES[surface]} · {CAT_GROUPS[surface][sc['group']]}", "gkey": f"{surface}:{sc['group']}",
            "item": sc["title"], "title": sc["title"], "detail": bool(sc.get("window")), "locked": False,
            "purpose": sc["purpose"], "value": sc["value"], "lead": "", "page": sc["page"], "components": [],
            "api": api, "tables": tables, "regions": cap.get("regions", []), "access": {},
            "who": [WHO.get(w, w) for w in sc["who"]], "scope": [], "flow": _flow(sc, cap, names),
            "steps": [t for _, t, _ in sc["steps"]], "from": link(sc["from"]), "next": link(sc["next"]),
            "writes": [a for a in api if a["verb"] in WRITE],
        })
    return result
