"""Builds the flowchart atlas from the capture (scripts/atlas/capture.mjs) and the inventory (inventory.py).

Writes <out>/index.html (every screen, chosen from a drop-down list), <out>/screens/<id>.html (one file per screen)
and keeps the screenshots in <out>/shots/. Each screen gets a card (purpose, added value, functional and technical
detail), a flowchart whose boxes point at the screenshot, who can open it, and a spoken commentary.

    python3 scripts/atlas/build.py <capture.json> <out-dir> [--portal <dir>] [--mobile <dir>] [--backend <backend.json>]

The portal and the two mobile apps (Yamen, 2026-11-13) are added from their own captures (apps.py): pass "-" as the
capture to build their screens alone.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from apps import screens as app_screens  # noqa: E402
from apps_content import SURFACES  # noqa: E402
from chapters import CHAPTERS, chapter_of, link_cards  # noqa: E402
from content import GROUP_VALUE, SCREENS  # noqa: E402

KIND_AR = {"menu": "القائمة", "title": "الصفحة", "lead": "الغرض", "tabs": "التبويبات", "map": "الخريطة",
           "section": "قسم", "table": "جدول", "form": "استمارة", "action": "إجراء", "window": "نافذة"}
sys.path.insert(0, str(HERE.parent / "menu"))
from menu import systems as menu_systems  # noqa: E402

# The order of the menu's one source: the home page, then the 20 systems.
GROUP_ORDER = ["home", *(s["key"] for s in menu_systems())]


def scope(access: dict[str, bool]) -> list[str]:
    tags = []
    if access.get("central") or access.get("central_committee"):
        tags.append("central")
    if access.get("regional") or access.get("local_committee"):
        tags.append("regional")
    if access.get("regional") and access.get("commander"):
        tags.append("room_commander")
    elif access.get("commander"):
        tags.append("commander")
    if access.get("agents"):
        tags.append("agents")
    return tags or ["admin"]


def parent_menu(route: str, by_route: dict[str, dict]) -> dict | None:
    probe = route
    while "/" in probe.strip("/"):
        probe = probe.rsplit("/", 1)[0]
        m = by_route.get(probe, {}).get("menu")
        if m:
            return m
    return None


def flow(s: dict) -> list[dict]:
    regs = s.get("regions", [])
    menu = s["menu"] or {}
    nodes = [{"t": "term", "l": "الدخول من القائمة", "s": f"{menu.get('group', '')} › {menu.get('item', '')}",
              "r": next((i for i, r in enumerate(regs) if r["kind"] == "menu"), None)}]
    title = next((i for i, r in enumerate(regs) if r["kind"] == "title"), None)
    nodes.append({"t": "io", "l": s.get("title") or menu.get("item", ""), "s": "تُحمَّل المعطيات من الخادم", "r": title})
    middle = []
    for i, r in enumerate(regs):
        if r["kind"] in ("menu", "title", "lead"):
            continue
        if r["kind"] == "tabs":
            middle.append({"t": "dec", "l": "أي تبويب؟", "s": r["label"][:46], "r": i})
        elif r["kind"] == "form":
            middle.append({"t": "io", "l": "إدخال: " + r["label"][:30], "r": i})
        elif r["kind"] == "action":
            middle.append({"t": "proc", "l": "تنفيذ: " + r["label"][:30], "r": i, "act": True})
        else:
            middle.append({"t": "proc", "l": r["label"][:38] or KIND_AR[r["kind"]], "s": KIND_AR[r["kind"]], "r": i})
    acts = [m for m in middle if m.get("act")][:2]
    rest = [m for m in middle if not m.get("act")][:8]
    nodes += rest + acts
    writes = any(a["verb"] in ("POST", "PUT", "PATCH", "DELETE") for a in s.get("api", []))
    nodes.append({"t": "term", "l": "يُحفظ ويُسجَّل في السجل" if writes else "عرض وقراءة فقط",
                  "s": "كل تغيير يدخل سجل التدقيق" if writes else "لا يغيّر شيئا في القاعدة", "r": None})
    return nodes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("capture")
    ap.add_argument("out")
    ap.add_argument("--portal", type=Path)
    ap.add_argument("--mobile", type=Path)
    ap.add_argument("--backend", type=Path)
    args = ap.parse_args()
    cap = json.loads(Path(args.capture).read_text(encoding="utf-8")) if args.capture != "-" else {"screens": [], "personas": {}}
    out = Path(args.out)
    by_route = {s["route"]: s for s in cap["screens"]}
    screens = []
    for s in cap["screens"]:
        if not s.get("shot"):
            continue
        locked = "لا تملك صلاحية" in (s.get("title") or "")
        if locked:  # the national administrator is refused here (a regional-only or dormant page)
            s["title"] = ""
            s["lead"] = ""
        menu = s.get("menu") or parent_menu(s["route"], by_route) or {"group": "صفحات أخرى", "group_key": "other", "item": s.get("title", "")}
        detail = s.get("menu") is None
        s["menu"] = {**menu, "item": (s.get("title") or menu["item"]) if detail else menu["item"]}
        key = s["route"] if s["route"] in SCREENS else None
        if key is None and detail:
            base = s["route"].rsplit("/", 1)[0]
            parent = SCREENS.get(base)
            purpose = ("تفاصيل عنصر واحد من «" + menu["item"] + "»: " + (s.get("lead") or s.get("title") or "")).strip(": ")
            value = parent[1] if parent else GROUP_VALUE.get(menu.get("group_key", ""), "")
        else:
            purpose, value = SCREENS.get(s["route"], (s.get("lead") or s.get("title", ""), GROUP_VALUE.get(menu.get("group_key", ""), "")))
        if locked:
            purpose = "لا تُفتح هذه الصفحة لمدير النظام على المستوى الوطني، لذلك تُظهر لقطتها رسالة المنع. " + purpose
        tables = sorted({t for a in s.get("api", []) for t in a["tables"]})
        screens.append({
            "id": s["id"], "route": s["route"], "path": s.get("path"), "shot": s["shot"], "height": s.get("height", 900),
            "group": s["menu"]["group"], "gkey": s["menu"].get("group_key", "other"), "item": s["menu"]["item"],
            "title": s.get("title") or s["menu"]["item"], "detail": detail, "locked": locked, "purpose": purpose, "value": value,
            "lead": s.get("lead", ""), "page": s["page"], "components": s.get("components", [])[:12],
            "api": s.get("api", []), "tables": tables, "regions": s.get("regions", []),
            "access": s.get("access", {}), "scope": scope(s.get("access", {})), "flow": flow(s),
        })
        for w in s.get("windows", []):  # its tabs and dialogs, each a card of its own after the screen
            kind = "تبويب" if w["kind"] == "tab" else "نافذة"
            win = {**s, "title": f"{s.get('title') or menu['item']} › {kind}: {w['label']}", "regions": w.get("regions", [])}
            wflow = flow(win)
            wflow[0] = {"t": "term", "l": "يُفتح من الصفحة", "s": f"{s.get('title') or menu['item']} ← «{w['label']}»", "r": None}
            screens.append({**screens[-1],
                            "id": w["id"].replace("~", "--"), "shot": w["shot"], "height": w.get("height", 900),
                            "item": f"{kind}: {w['label']}", "title": win["title"], "detail": True,
                            "purpose": f"{kind} «{w['label']}» في صفحة «{s.get('title') or menu['item']}». " + purpose,
                            "regions": w.get("regions", []), "flow": wflow, "window": w["kind"]})
    order = {k: i for i, k in enumerate(GROUP_ORDER)}
    screens.sort(key=lambda x: (order.get(x["gkey"], 99), x["detail"] and not x.get("window"), x["route"], x.get("window") or ""))
    screens += app_screens(args.portal, args.mobile, args.backend, out)
    # Chapters (Yamen's order): each card joins its chapter, in the order of the chapter's members, then the link card.
    for c in screens:
        c.setdefault("surface", "dashboard")
        c["chap"] = chapter_of(c["surface"], c["gkey"])
    def rank(c: dict) -> tuple:
        ch = next(i for i, x in enumerate(CHAPTERS) if x["key"] == c["chap"])
        group = c["gkey"].split(":", 1)[1] if ":" in c["gkey"] else c["gkey"]
        mem = CHAPTERS[ch]["members"]
        pos = next((i for i, (sf, g) in enumerate(mem) if sf == c["surface"] and g in (group, "*")), len(mem))
        return (ch, pos)
    screens = sorted(screens, key=rank)  # stable: the order inside a member stays
    links = link_cards(screens)
    final = []
    for ch in CHAPTERS:
        final += [c for c in screens if c["chap"] == ch["key"]] + [x for x in links if x["chap"] == ch["key"]]
    screens = final
    meta = {"built": date.today().isoformat(), "personas": cap["personas"], "count": len(screens),
            "surface": "لوحة القيادة (مدير النظام)", "surfaces": {**SURFACES, "link": "الترابط"},
            "chapters": {c["key"]: c["title"] for c in CHAPTERS}}
    tpl = (HERE / "template.html").read_text(encoding="utf-8")
    out.mkdir(parents=True, exist_ok=True)
    (out / "screens").mkdir(exist_ok=True)
    blob = lambda data: json.dumps(data, ensure_ascii=False).replace("</", "<\\/")  # noqa: E731
    (out / "index.html").write_text(tpl.replace("__DATA__", blob({"meta": meta, "screens": screens})).replace("__BASE__", ""), encoding="utf-8")
    for sc in screens:
        one = {"meta": {**meta, "single": True}, "screens": [sc]}
        (out / "screens" / f"{sc['id']}.html").write_text(tpl.replace("__DATA__", blob(one)).replace("__BASE__", "../"), encoding="utf-8")
    print(f"{len(screens)} screens → {out}")


if __name__ == "__main__":
    main()
