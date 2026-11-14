"""Builds the mind maps of the project, one per phase plus an overview (Yamen, 2026-11-13).

Reads the same rows as the request tracker (requests.py, plus the items of docs/versions.md added since), so a new
phase or a changed status shows on the next run without hand edits.

    python3 scripts/tracking/mindmap.py <out.html>

The same run writes <out>-deck.html beside it (Yamen, 2026-11-14): the mind maps as a presentation, a chapter slide
and an interactive map slide per phase, with the folding branches and «next» walking through the branches.
"""

from __future__ import annotations

import base64
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import requests as cur  # noqa: E402
from build import collect  # noqa: E402

sys.path.insert(0, str(HERE.parent / "menu"))
from menu import items as load_items, label, load  # noqa: E402

sys.path.insert(0, str(HERE.parent / "atlas"))
from content import SCREENS  # noqa: E402


def menu_maps() -> tuple[dict[str, str], list[dict]]:
    """One map per block of the dashboard menu (apps/dashboard/src/menu/menu.json): a branch per system, its entries as
    leaves; a system still holding planned screens shows as approved, not done."""
    groups: dict[str, str] = {}
    rows: list[dict] = []
    for block in load()["blocks"]:
        g = f"menu_{block['key']}"
        groups[g] = f"القائمة: {block['names']['ar']}"
        for s in block["systems"]:
            built = [label(i["key"]) for i in s["items"] if not i.get("planned") and not i.get("alias")]
            planned = [f"{label(i['key'])} (قيد الإنجاز)" for i in s["items"] if i.get("planned")]
            rows.append(
                dict(g=g, code=str(s["number"]), title=s["names"]["ar"], kind="نظام", desc="، ".join(built + planned),
                     status="approved" if planned else "done", size="L" if len(s["items"]) > 5 else "M",
                     imp=4 if block["key"] == "operational" else 3, date="", ref="menu.json",
                     screens=[dict(p=i["path"], l=label(i["key"])) for i in s["items"]
                              if not i.get("planned") and not i.get("alias")])
            )
    return groups, rows


def link_screens(rows: list[dict]) -> None:
    """The dashboard screens an item speaks of (Yamen 2026-11-14: its screenshot opens from its card): a menu entry
    whose label appears in the item's title or description. Menu systems already list their own entries."""
    entries = [i for i in load_items() if not i.get("planned") and not i.get("alias")]
    labels = [(i["path"], label(i["key"])) for i in entries]
    for r in rows:
        if "screens" in r:
            continue
        text = f"{r['title']} {r['desc']}"
        hits = [dict(p=p, l=lb) for p, lb in labels if len(lb) >= 5 and lb in text]
        r["screens"] = hits[:4]
    for r in rows:   # what each screen is for and what it adds, from the atlas texts
        for sc in r["screens"]:
            sc["u"], sc["v"] = SCREENS.get(sc["p"], ("", ""))


def main() -> None:
    out = Path(sys.argv[1])
    rows, nitems = collect()
    menu_groups, menu_rows = menu_maps()
    groups = {**cur.G, **menu_groups}
    rows = rows + menu_rows
    link_screens(rows)
    data = {"groups": groups, "rows": rows, "built": date.today().isoformat(), "versions": nitems}
    viewer = (HERE.parent / "atlas" / "viewer.js").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    logo = "data:image/png;base64," + base64.b64encode((HERE / "assets" / "civil-protection-logo.png").read_bytes()).decode()
    deck = out.with_name(out.stem + "-deck.html")
    for page, target in (("mindmap.html", out), ("mindmap-deck.html", deck)):
        html = (HERE / page).read_text(encoding="utf-8").replace("__VIEWER__", viewer).replace("__LOGO__", logo)
        target.write_text(html.replace("__DATA__", payload), encoding="utf-8")
    print(f"{len(groups)} mind maps, {len(rows)} items → {out} and {deck}")


if __name__ == "__main__":
    main()
