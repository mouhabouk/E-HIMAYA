#!/usr/bin/env python3
"""The atlas as a book: a print page for every card, then a PDF (Yamen, 2026-11-14).

  python3 scripts/atlas/pdf.py <atlas-dir> [--shots <dir> ...] [--out <file.pdf>]

Reads the data of <atlas-dir>/index.html (built by build.py), so the book follows the atlas on every run. Writes
<atlas-dir>/print.html, then prints it with scripts/atlas/pdf.mjs (Playwright's Chromium) to <atlas-dir>/atlas.pdf.

The book: a cover, how to read it, a contents list with page numbers, then for each chapter in Yamen's order a title
page and one landscape A4 page per card. On a card's page the screenshot carries numbered marks, and the same numbers
sit on the boxes of the flowchart beside it: the printed form of the atlas's spotlight. A tall phone screenshot is cut
into side by side strips so it keeps a readable size. Every page has a fixed size, so the page numbers of the contents
are known before printing.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

SCOPE = {"central": "مركزي", "regional": "جهوي", "room_commander": "جهوي: القاعة والقائد", "commander": "القائد الميداني",
         "agents": "بقية الأعوان والمصالح", "admin": "مدير النظام وحده"}
REGION = {"title": "العنوان", "lead": "التعريف", "tabs": "تبويبات", "map": "خريطة", "section": "قسم", "table": "جدول",
          "form": "استمارة", "action": "زر", "window": "نافذة"}
AXC = ["#1F3FA0", "#E8590C", "#B3121A", "#7B3FD1", "#C25E00", "#0E8FA8", "#1F9D55", "#5E2A80", "#B5651D", "#12A38A",
       "#55607A", "#9C36B5"]
WRITE = ("POST", "PUT", "PATCH", "DELETE")

# Page geometry in CSS px (96 per inch): A4 landscape.
PW, PH = 1123, 794
SHOT_W, SHOT_H = 452, 560  # the screenshot box beside the flow and the cards
WIDE_W = 770  # on a page of its own, when the cards go to a second page
TOC_ROWS = 31  # lines per contents column, two columns a page

e = lambda s: html.escape(str(s if s is not None else ""), quote=True)


def image_size(path: Path) -> tuple[int, int]:
    """Width and height of a PNG or JPEG, read from its header."""
    b = path.read_bytes()
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", b[16:24])
    i = 2
    while i < len(b):
        if b[i] != 0xFF:
            i += 1
            continue
        m = b[i + 1]
        if m in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", b[i + 5:i + 9])
            return w, h
        i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    raise ValueError(f"not a PNG or JPEG: {path}")


def strips(w: int, h: int, box_w: int, box_h: int) -> tuple[int, float]:
    """How many side by side strips, and the scale, that show the whole image largest in the box."""
    best = (1, 0.0)
    for n in range(1, 5):
        sw = (box_w - (n - 1) * 10) / n
        s = min(sw / w, n * box_h / h, 1.6)
        if s > best[1] * 1.04:
            best = (n, s)
    return best


def flow_svg(flow: list[dict], marks: dict[int, int], width: int = 300) -> str:
    """The flowchart as a static SVG: the same shapes as the atlas, with the numbers of the screenshot's marks."""
    gap, w, h = 58, 252, 42
    out = [f'<svg class="flow" viewBox="0 0 {width} {len(flow) * gap + 6}" xmlns="http://www.w3.org/2000/svg">',
           ('<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
            '<path d="M0,0L10,5L0,10z" fill="#8A93A8"/></marker></defs>')]
    x = width / 2
    for k in range(1, len(flow)):
        out.append(f'<line class="e" x1="{x}" y1="{(k - 1) * gap + 24 + h / 2}" x2="{x}" y2="{k * gap + 24 - h / 2 - 1}" '
                   'marker-end="url(#ah)"/>')
    for k, n in enumerate(flow):
        y = k * gap + 24
        t = n.get("t", "proc")
        ww, hh = (w - 30, h + 8) if t == "dec" else (w, h)
        if t == "term":
            shape = f'<rect x="{x - ww / 2}" y="{y - hh / 2}" width="{ww}" height="{hh}" rx="{hh / 2}"/>'
        elif t == "proc":
            shape = f'<rect x="{x - ww / 2}" y="{y - hh / 2}" width="{ww}" height="{hh}" rx="7"/>'
        elif t == "io":
            shape = (f'<polygon points="{x - ww / 2 + 14},{y - hh / 2} {x + ww / 2 + 5},{y - hh / 2} '
                     f'{x + ww / 2 - 14},{y + hh / 2} {x - ww / 2 - 5},{y + hh / 2}"/>')
        else:
            shape = f'<polygon points="{x},{y - hh / 2} {x + ww / 2},{y} {x},{y + hh / 2} {x - ww / 2},{y}"/>'
        label = n.get("l", "")
        cap = 26 if t == "dec" else 36
        label = label if len(label) <= cap else label[:cap - 1] + "…"
        sub = n.get("s", "") or ""
        sub = sub if len(sub) <= 44 else sub[:43] + "…"
        g = [f'<g class="n {e(t)}">', shape, f'<text x="{x}" y="{y - 7 if sub else y}">{e(label)}</text>']
        if sub:
            g.append(f'<text class="s" x="{x}" y="{y + 10}">{e(sub)}</text>')
        if k in marks:
            cx = x + w / 2 + 2
            g.append(f'<circle class="mk" cx="{cx}" cy="{y}" r="11"/><text class="mkt" x="{cx}" y="{y}">{marks[k]}</text>')
        g.append("</g>")
        out.append("".join(g))
    out.append("</svg>")
    return "".join(out)


def shot_html(s: dict, src: str, size: tuple[int, int], marks: dict[int, int], box_w: int = SHOT_W,
              box_h: int = SHOT_H) -> str:
    w, h = size
    n, sc = strips(w, h, box_w, box_h)
    dw, dh = w * sc, h * sc
    part = dh / n
    boxes = []
    seen = set()
    for k, num in marks.items():
        r = s["regions"][s["flow"][k]["r"]]
        key = (r["x"], r["y"], r["w"], r["h"])
        boxes.append(f'<div class="rg" style="left:{r["x"] * sc:.1f}px;top:{r["y"] * sc:.1f}px;width:{r["w"] * sc:.1f}px;'
                     f'height:{r["h"] * sc:.1f}px"><b class="{"dup" if key in seen else ""}">{num}</b></div>')
        seen.add(key)
    inner = f'<img src="{e(src)}" style="width:{dw:.1f}px;height:{dh:.1f}px" alt="">' + "".join(boxes)
    cols = "".join(f'<div class="strip" style="width:{dw:.1f}px;height:{part:.1f}px">'
                   f'<div class="inner" style="top:{-i * part:.1f}px;width:{dw:.1f}px;height:{dh:.1f}px">{inner}</div></div>'
                   for i in range(n))
    note = f'<p class="cap">اللقطة مقسومة إلى {n} أعمدة تُقرأ من اليمين.</p>' if n > 1 else ""
    return f'<div class="shot{" phone" if s.get("phone") else ""}">{cols}</div>{note}'


def api_rows(api: list[dict], cap: int) -> str:
    rows = []
    for a in api[:cap]:
        wr = a["verb"] in WRITE
        tb = f'<br><span class="tb">{e(" · ".join(a["tables"][:4]))}</span>' if a.get("tables") else ""
        rows.append(f'<tr><td class="verb">{e(a["verb"])}<br><span class="tag{" w" if wr else ""}">{"تكتب" if wr else "تقرأ"}'
                    f'</span></td><td><span class="mono">{e(a["path"])}</span>{tb}</td></tr>')
    if len(api) > cap:
        rows.append(f'<tr><td></td><td class="more">و{len(api) - cap} نداء آخر في الأطلس التفاعلي.</td></tr>')
    return "".join(rows)


def links(a: list[dict], names: dict[str, str]) -> str:
    out = []
    for x in a:
        lab = x.get("label") or names.get(x.get("id") or "", "")
        how = f'<span class="how">{e(x.get("how", ""))}</span>' if x.get("how") else ""
        out.append(f"<li><b>{e(lab)}</b>{how}</li>" if lab else f"<li>{how}</li>")
    return "".join(out) or "<li>—</li>"


def card_page(s: dict, num: str, chap: str, page: int, D: dict, src: str | None, size, names, split: bool = False) -> str:
    """One page, or two when the cards do not fit beside the screenshot (split): the screenshot and the flow, then the cards."""
    link = s["surface"] == "link"
    app = s["surface"] != "dashboard" and not link
    marks, j = {}, 0
    for k, n in enumerate(s["flow"]):
        if n.get("r") is not None and not link and n["r"] < len(s.get("regions", [])):
            j += 1
            marks[k] = j
    badges = "".join(f'<span class="badge" style="--c:var(--c-{k});--b:var(--b-{k})">{SCOPE.get(k, k)}</span>'
                     for k in s.get("scope", []))
    route = s.get("path") or s.get("route") or ""
    surf = D["meta"]["surfaces"].get(s["surface"], "")
    head = (f'<header class="ph"><div class="pnum">{e(num)}</div><div class="ptitle"><div class="crumb">{e(s["group"])} › '
            f'{e(s["item"])}</div><h2>{e(s["title"])}</h2>'
            f'{f"<span class=route>{e(route)}</span>" if route else ""}</div><div class="badges">'
            f'<span class="surfb">{e(surf or "الترابط")}</span>{badges}</div></header>')
    flow = f'<section class="flowcol"><h3>المخطط الانسيابي</h3>{flow_svg(s["flow"], marks)}</section>'
    if link:
        body = (f'<div class="body linkb">{flow}<section class="cardscol two">'
                f'<article class="card"><h3>الجانب الوظيفي: ماذا يمر بين التطبيق واللوحة</h3><ol>'
                + "".join(f"<li>{e(t)}</li>" for t in s["functional"]) + "</ol></article>"
                '<article class="card"><h3>الجانب التقني: محسوب من الالتقاط في كل تحيين</h3><ul>'
                + "".join(f"<li>{e(t)}</li>" for t in s["technical"]) + "</ul></article>"
                f'<article class="card"><h3>شاشات التطبيق في هذا الترابط ({len(s["appScreens"])})</h3><ul class="cols">'
                + "".join(f"<li>{e(x['label'])}</li>" for x in s["appScreens"]) + "</ul></article>"
                f'<article class="card"><h3>صفحات اللوحة في هذا الترابط ({len(s["boardScreens"])})</h3><ul class="cols">'
                + "".join(f"<li>{e(x['label'])}</li>" for x in s["boardScreens"]) + "</ul></article></section></div>")
    else:
        shot = (f'<section class="shotcol">{shot_html(s, src, size, marks, *((WIDE_W, 600) if split else (SHOT_W, SHOT_H)))}</section>' if src
                else '<section class="shotcol"><p class="cap">لا لقطة لهذه الشاشة.</p></section>')
        if app:
            tline = f'<p class="hint">الجداول: {e("، ".join(s["tables"]))}</p>' if s["tables"] else ""
            cards = (f'<article class="card"><h3>الغرض والقيمة المضافة</h3><p>{e(s["purpose"])}</p>'
                     f'<p class="val">القيمة المضافة: {e(s["value"])}</p></article>'
                     f'<article class="card"><h3>خطوة بخطوة</h3><ol>' + "".join(f"<li>{e(t)}</li>" for t in s["steps"])
                     + "</ol></article>"
                     f'<article class="card"><h3>الطريق إليها ومنها</h3><h4>يصل إليها من</h4><ul class="lk">'
                     f'{links(s["from"], names)}</ul><h4>ينتقل منها إلى</h4><ul class="lk">{links(s["next"], names)}</ul></article>'
                     f'<article class="card"><h3>من يفتح هذه الشاشة</h3><ul>' + "".join(f"<li>{e(w)}</li>" for w in s["who"])
                     + "</ul></article>"
                     f'<article class="card"><h3>المعطيات: ما تقرأ وما تكتب</h3><table class="api">'
                     f'{api_rows(s["api"], 8) or "<tr><td>لا نداء للخادم عند فتح هذه الشاشة: تُعرض من الهاتف.</td></tr>"}'
                     f'</table>{tline}'
                     f'<p class="file mono">{e(s["page"])}</p></article>')
        else:
            regs = [r for r in s["regions"] if r.get("kind") != "menu"]
            who = "".join(f'<span>{e(v)}</span><span class="{"y" if (k == "admin" or s["access"].get(k)) else "no"}">'
                          f'{"✓ تفتحها" if (k == "admin" or s["access"].get(k)) else "—"}</span>'
                          for k, v in D["meta"]["personas"].items())
            tables = s.get("tables", [])
            cards = (f'<article class="card"><h3>الغرض والقيمة المضافة</h3><p>{e(s["purpose"])}</p>'
                     f'<p class="val">القيمة المضافة: {e(s["value"])}</p></article>'
                     f'<article class="card"><h3>الجانب الوظيفي: ما في الصفحة</h3><ul>'
                     + ("".join(f'<li><b>{REGION.get(r["kind"], r["kind"])}:</b> {e(r["label"])}</li>' for r in regs[:12])
                        or "<li>صفحة عرض.</li>")
                     + (f'<li class="more">و{len(regs) - 12} عنصرا آخر.</li>' if len(regs) > 12 else "") + "</ul></article>"
                     f'<article class="card"><h3>من يفتح هذه الصفحة</h3><div class="who">{who}</div></article>'
                     f'<article class="card"><h3>الجانب التقني</h3><p class="file mono">{e(s["page"])}</p><table class="api">'
                     f'{api_rows(s["api"], 8) or "<tr><td>لا نداء مباشر للخادم من هذه الصفحة.</td></tr>"}</table>'
                     + (f'<p class="hint">الجداول ({len(tables)}): {e("، ".join(tables[:10]))}{"…" if len(tables) > 10 else ""}</p>'
                        if tables else "") + "</article>")
        if split:
            return (page_wrap(head + f'<div class="body wide">{shot}{flow}</div>', chap, page, s["id"])
                    + page_wrap(head.replace("</h2>", " <small>(تابع)</small></h2>", 1)
                                + f'<div class="body cont"><section class="cardscol cols3">{cards}</section></div>',
                                chap, page + 1, s["id"]))
        body = f'<div class="body">{shot}{flow}<section class="cardscol">{cards}</section></div>'
    return page_wrap(head + body, chap, page, s["id"])


def page_wrap(inner: str, chap: str, page: int, pid: str = "", cls: str = "") -> str:
    foot = (f'<footer class="pf"><span>أطلس ء-حماية</span><span>{e(chap)}</span><span>معطيات [SIM]</span>'
            f'<span class="pn">{page}</span></footer>')
    return f'<section class="page {cls}" data-id="{e(pid)}">{inner}{foot}</section>'


def build(atlas: Path, shot_dirs: list[Path], split: set[str]) -> tuple[str, int]:
    text = (atlas / "index.html").read_text(encoding="utf-8")
    D = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', text, re.DOTALL).group(1))
    for s in D["screens"]:
        s.setdefault("surface", "dashboard")
        s.setdefault("chap", s["surface"])
    chapters = D["meta"].get("chapters") or D["meta"]["surfaces"]
    names = {s["id"]: s["title"] for s in D["screens"]}
    order = [k for k in chapters if any(s["chap"] == k for s in D["screens"])]

    # Numbers as in the atlas's picker: group . item . sub-item, within a chapter.
    nums, groups = {}, {}
    for ck in order:
        gl: list[tuple[str, str, list[dict]]] = []
        for s in D["screens"]:
            if s["chap"] != ck:
                continue
            g = next((x for x in gl if x[0] == s["gkey"]), None)
            if not g:
                g = (s["gkey"], s["group"], [])
                gl.append(g)
            g[2].append(s)
        groups[ck] = gl
        for gi, (_, _, items) in enumerate(gl):
            m = sub = 0
            for s in items:
                if s.get("detail"):
                    sub += 1
                else:
                    m, sub = m + 1, 0
                nums[s["id"]] = f"{order.index(ck) + 1}.{gi + 1}.{m}" + (f".{sub}" if s.get("detail") else "")

    # Contents lines, then their pages; the cover and the guide come first.
    lines: list[tuple[str, str, str, str]] = []  # kind, number, label, id or chapter key
    for ck in order:
        lines.append(("ch", "", chapters[ck], ck))
        for _, gname, items in groups[ck]:
            lines.append(("gr", "", gname.split(" · ")[-1] if " · " in gname else gname, ""))
            for s in items:
                lines.append(("it" if not s.get("detail") else "sub", nums[s["id"]], s["item"], s["id"]))
    per = TOC_ROWS * 2
    toc_pages = (len(lines) + per - 1) // per
    page_of: dict[str, int] = {}
    p = 2 + toc_pages
    for ck in order:
        p += 1
        page_of[ck] = p
        for _, _, items in groups[ck]:
            for s in items:
                p += 1
                page_of[s["id"]] = p
                p += s["id"] in split
    total = p

    def find(rel: str) -> tuple[str | None, tuple[int, int] | None]:
        for d in [atlas, *shot_dirs]:
            f = d / rel
            if f.exists():
                return (rel if d == atlas else f.resolve().as_uri()), image_size(f)
        return None, None

    pages = []
    counts = {ck: sum(len(it) for _, _, it in groups[ck]) for ck in order}
    by_surface: dict[str, int] = {}
    for s in D["screens"]:
        by_surface[s["surface"]] = by_surface.get(s["surface"], 0) + 1
    surf_names = D["meta"]["surfaces"]
    pages.append(
        '<section class="page cover"><div class="cv"><div class="seal">ء</div><h1>أطلس ء-حماية</h1>'
        '<p class="lead">كل شاشة وكل نافذة في المنظومة: من أين يصل المستخدم، ماذا يفعل خطوة بخطوة، إلى أين ينتقل، '
        'وما تقرأ الشاشة وما تكتب في قاعدة المعطيات.</p>'
        '<div class="stats">' + "".join(f'<div><b>{n}</b><span>{e(surf_names.get(k, "الترابط") if k != "link" else "بطاقات الترابط")}</span></div>'
                                        for k, n in by_surface.items()) +
        '</div><ol class="chaps">' + "".join(f"<li><span>{e(chapters[ck])}</span><b>{counts[ck]} بطاقة · ص {page_of[ck]}</b></li>" for ck in order)
        + f'</ol><p class="built">بُني آليا من المستودع والمنظومة يوم {e(D["meta"]["built"])} · {len(D["screens"])} بطاقة · '
        f'{total} صفحة · اللقطات بمعطيات [SIM]</p></div></section>')
    guide = (
        '<header class="ph"><div class="ptitle"><h2>كيف يُقرأ هذا الأطلس</h2></div></header><div class="guide">'
        '<article class="card"><h3>صفحة البطاقة</h3><ol>'
        '<li>في الأعلى: رقم البطاقة، المجموعة والعنصر، العنوان، المسار في المنظومة، والواجهة والأدوار.</li>'
        '<li>اللقطة: حقيقية من المنظومة بمعطيات [SIM]. المربعات البرتقالية المرقمة هي مواضع خطوات المخطط.</li>'
        '<li>المخطط الانسيابي: من أين يصل المستخدم، ثم ما يفعله، ثم إلى أين يذهب. الرقم على المربع هو رقم موضعه في اللقطة.</li>'
        '<li>البطاقات: الغرض والقيمة، الخطوات أو ما في الصفحة، من يفتحها، والمعطيات التي تقرؤها وتكتبها.</li>'
        '<li>اللقطة الطويلة لشاشة هاتف تُقسم أعمدة متجاورة، تُقرأ من اليمين إلى اليسار.</li></ol></article>'
        '<article class="card"><h3>أشكال المخطط</h3>' + flow_svg([
            {"t": "term", "l": "بداية أو نهاية", "s": "يصل إليها من · ينتقل إلى"},
            {"t": "io", "l": "معطيات", "s": "ما تقرأ الشاشة أو تكتب"},
            {"t": "proc", "l": "خطوة", "s": "يضغط، يُدخل، يختار، يرى"},
            {"t": "dec", "l": "اختيار", "s": "طريقان حسب الحالة"}], {2: 1}) + '</article>'
        '<article class="card"><h3>الفصول بترتيبها</h3><ul class="plain">' + "".join(f"<li>{e(chapters[ck])}</li>" for ck in order) +
        '</ul><p>كل فصل ينتهي ببطاقة «الترابط»: ما يمر بين التطبيق ولوحة القيادة، وظيفيا، ثم تقنيا من الالتقاط نفسه.</p></article>'
        '<article class="card"><h3>الأدوار في لوحة القيادة</h3><div class="badges">'
        + "".join(f'<span class="badge" style="--c:var(--c-{k});--b:var(--b-{k})">{v}</span>' for k, v in SCOPE.items())
        + '</div><p>نسخة تفاعلية من الأطلس تبرز كل موضع عند الضغط على مربعه. هذا الكتاب يُعاد بناؤه آليا مع كل تحيين '
        '(scripts/refresh-all.sh)، فلا يُعدّل يدويا.</p></article></div>')
    pages.append(page_wrap(guide, "دليل القراءة", 2))
    for t in range(toc_pages):
        chunk = lines[t * per:(t + 1) * per]
        colsh = []
        for c in range(2):
            rows = []
            for kind, num, label, ref in chunk[c * TOC_ROWS:(c + 1) * TOC_ROWS]:
                pg = page_of.get(ref, "")
                rows.append(f'<li class="{kind}"><span class="tn">{e(num)}</span><span class="tl">{e(label)}</span>'
                            f'<span class="tp">{pg}</span></li>')
            colsh.append(f'<ul>{"".join(rows)}</ul>')
        pages.append(page_wrap(f'<header class="ph"><div class="ptitle"><h2>المحتويات{" (تابع)" if t else ""}</h2></div></header>'
                               f'<div class="toc">{"".join(colsh)}</div>', "المحتويات", 3 + t))
    missing = 0
    for ci, ck in enumerate(order):
        gl = groups[ck]
        pages.append(page_wrap(
            f'<div class="chap" style="--g:{AXC[ci % len(AXC)]}"><div class="cn">{ci + 1}</div><h1>{e(chapters[ck].split(". ", 1)[-1])}</h1>'
            f'<p>{counts[ck]} بطاقة في {len(gl)} مجموعة</p><ol>'
            + "".join(f'<li><span>{e(g)}</span><b>{len(it)} · ص {page_of[it[0]["id"]]}</b></li>' for _, g, it in gl)
            + "</ol></div>", chapters[ck], page_of[ck], cls="divider"))
        for _, _, items in gl:
            for s in items:
                src, size = find(s["shot"]) if s.get("shot") else (None, None)
                if s.get("shot") and not src:
                    missing += 1
                pages.append(card_page(s, nums[s["id"]], chapters[ck], page_of[s["id"]], D, src, size, names,
                                           s["id"] in split))
    if missing:
        print(f"pdf: {missing} screenshot(s) not found", file=sys.stderr)
    tpl = (HERE / "print.html").read_text(encoding="utf-8")
    return tpl.replace("__PAGES__", "\n".join(pages)), total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("atlas", type=Path)
    ap.add_argument("--shots", type=Path, action="append", default=[], help="another folder that holds shots/")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--html-only", action="store_true")
    a = ap.parse_args()
    page = a.atlas / "print.html"
    # First pass: every card on one page; the printer names the cards whose text does not fit beside the screenshot.
    doc, total = build(a.atlas, a.shots, set())
    page.write_text(doc, encoding="utf-8")
    measured = subprocess.run(["node", str(HERE / "pdf.mjs"), str(page), "--measure"], capture_output=True, text=True, check=False)
    if measured.returncode:
        print(measured.stderr, file=sys.stderr)
        return measured.returncode
    split = set(json.loads(measured.stdout.strip().splitlines()[-1]))
    # Second pass: those cards get a second page for their text.
    doc, total = build(a.atlas, a.shots, split)
    page.write_text(doc, encoding="utf-8")
    print(f"pdf: print.html, {total} pages, {len(split)} card(s) on two pages")
    if a.html_only:
        return 0
    out = a.out or a.atlas / "atlas.pdf"
    return subprocess.call(["node", str(HERE / "pdf.mjs"), str(page), str(out)])


if __name__ == "__main__":
    sys.exit(main())
