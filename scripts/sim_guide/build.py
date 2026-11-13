"""Builds the guide to the [SIM] data of e-Himaya (Yamen, 2026-11-13): where each simulated item lives and how it is
replaced by real data, automatically, by hand from the dashboard, by a script, or by a code change.

The items are curated in items.py. Automatic parts, so the guide follows the project without hand edits:
- the Markdown guide docs/sql/sim-guide.md is rewritten from items.py at every run;
- ``--check`` scans the migrations for every ``simulated``/``sim`` column and ``'sim'``/``'simulated'`` source, and
  docs/sql/03-sim-to-real.sql for every R request, and fails when one is not covered by an item (a new [SIM] source
  added by a phase must be added to items.py, so the guide never falls behind);
- ``--html`` writes an HTML page of the same guide; with DATABASE_URL (or MIGRATION_DATABASE_URL) pointing at a
  database it adds, per item, how many rows are still [SIM] there.

    python3 scripts/sim_guide/build.py                       # rewrite docs/sql/sim-guide.md
    python3 scripts/sim_guide/build.py --check               # fail if a [SIM] source is not in the guide
    python3 scripts/sim_guide/build.py --html out/sim-guide.html

Standard library only (psql for the counts).
"""

from __future__ import annotations

import argparse
import html
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from items import ITEMS, MODES  # noqa: E402

MD_OUT = ROOT / "docs/sql/sim-guide.md"
MIGRATIONS = ROOT / "services/api/migrations/versions"
SIM_TO_REAL = ROOT / "docs/sql/03-sim-to-real.sql"
INVENTORY = ROOT / "docs/sql/sim-inventory.md"


# ------------------------------------------------------------------------------------------------ drift check
def migration_sources() -> dict[str, list[str]]:
    """schema.table -> migrations that give it a [SIM] mark (simulated/sim boolean, or a 'sim'/'simulated' source)."""
    found: dict[str, list[str]] = {}
    table_re = re.compile(r"(?:CREATE TABLE(?: IF NOT EXISTS)?|ALTER TABLE(?: IF EXISTS)?(?: ONLY)?)\s+([a-z_]+\.[a-z_]+)", re.I)
    for f in sorted(MIGRATIONS.glob("0*.py")):
        text = f.read_text(encoding="utf-8")
        for m in re.finditer(r"\b(?:simulated|sim)\s+boolean\b|source[^,;\n]{0,80}'(?:sim|simulated)'", text, re.I):
            tables = table_re.findall(text[: m.start()])
            if tables:
                found.setdefault(tables[-1].lower(), []).append(f.name[:4])
    return found


def check() -> list[str]:
    problems: list[str] = []
    covered = {t for it in ITEMS for t in it["tables"]}
    for table, migs in sorted(migration_sources().items()):
        if table not in covered:
            problems.append(f"{table} carries a [SIM] mark (migration {migs[0]}) but no item of scripts/sim_guide/items.py lists it")
    steps = " ".join(text for it in ITEMS for _, text in it["steps"])
    for r in sorted(set(re.findall(r"^-- (R\d\d) ·", SIM_TO_REAL.read_text(encoding="utf-8"), re.M))):
        if not re.search(rf"\b{r}\b", steps):
            problems.append(f"{r} of docs/sql/03-sim-to-real.sql is not named by any item")
    ids = {it["id"] for it in ITEMS}
    for s in sorted(set(re.findall(r"^\| (S\d\d) \|", INVENTORY.read_text(encoding="utf-8"), re.M))):
        if s not in ids:
            problems.append(f"{s} of docs/sql/sim-inventory.md has no item")
    for it in ITEMS:
        if it["mode"] not in MODES or any(m not in MODES for m, _ in it["steps"]):
            problems.append(f"{it['id']}: unknown mode")
    return problems


# ------------------------------------------------------------------------------------------------ live counts
def db_url() -> str | None:
    url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    return url.replace("+asyncpg", "") if url else None


def counts(url: str) -> dict[str, int | None]:
    """Item id -> rows still [SIM] in that database (None when the query failed, e.g. an older schema)."""
    out: dict[str, int | None] = {}
    for it in ITEMS:
        if not it["count"]:
            continue
        r = subprocess.run(["psql", url, "-XAtc", it["count"]], capture_output=True, text=True)
        out[it["id"]] = int(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip().isdigit() else None
    return out


# ------------------------------------------------------------------------------------------------ Markdown
def md_cell(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def build_md() -> str:
    by_mode: dict[str, int] = {m: 0 for m in MODES}
    for it in ITEMS:
        by_mode[it["mode"]] += 1
    L: list[str] = []
    L += ["# دليل المعطيات التجريبية [SIM]: أين توجد وكيف تُستبدل بالمعطيات الحقيقية", "",
          "> **ملف مولَّد آليا** بـ `python3 scripts/sim_guide/build.py`، ويُعاد توليده في كل تشغيل لـ `scripts/refresh-all.sh`. لا يُعدَّل",
          "> يدويا: البنود في `scripts/sim_guide/items.py`. الفحص `--check` يوقف التحيين إن أضافت مرحلة مصدرا [SIM] جديدا (عمود",
          "> `simulated` أو مصدر `sim` في ترحيل، أو طلب R جديد) دون أن يُذكر هنا، فلا يتأخر الدليل عن التطوير.", "",
          "المراجع التفصيلية في المجلد نفسه: [`sim-inventory.md`](sim-inventory.md) (الجرد: أين يظهر الوسم ولماذا)،",
          "[`01-queries.sql`](01-queries.sql) (المراقبة Q53 إلى Q56)، [`02-inserts.sql`](02-inserts.sql) (إدخال المعطى الحقيقي I1 إلى I13)،",
          "[`03-sim-to-real.sql`](03-sim-to-real.sql) (التحويل R01 إلى R17).", "",
          "## الجواب باختصار", "",
          "لا توجد آلية واحدة: كل معطى تجريبي يُستبدل بالطريقة التي تناسب مصدره. أغلب الحالات **آلية بعد إعداد واحد** (مزوّد",
          "حقيقي مكان المحاكي) أو **يدوية من لوحة القيادة** (مصادقة أو توريد ملف رسمي)، وتكمّلها **سكريبتات SQL جاهزة** تنظّف",
          "ما بقي من المعطيات القديمة. قلة من الحالات نصوص ثابتة في الشيفرة يغيّرها مطوّر، وبعضها يبقى [SIM] عمدا (التمارين",
          "وأدوات الاختبار).", "",
          "| الطريقة | المعنى | عدد البنود |", "|---|---|---|"]
    for m, (label, desc) in MODES.items():
        L.append(f"| **{label}** | {desc} | {by_mode[m]} |")
    L += ["", "قاعدة ثابتة: لا يُنزع وسم [SIM] عن معطى ما زال مخترعا. كل طلب R في `03-sim-to-real.sql` مشروط بوصول المعطى",
          "الحقيقي، ويُشغَّل أولا تجربة جافة (ينتهي بـ ROLLBACK) ثم بـ `-v commit=1`، وكل تغيير يُسجَّل باسم الفاعل في سجل التغييرات.", "",
          "## الجدول السريع", "",
          "| # | المعطى التجريبي | الطريقة الأساسية | المعطى الحقيقي ومن يقدّمه | الجدول في القاعدة |", "|---|---|---|---|---|"]
    for it in ITEMS:
        tables = "، ".join(f"`{t}`" for t in it["tables"]) or "—"
        L.append(f"| [{it['id']}](#{it['id'].lower()}) | {md_cell(it['title'])} | {MODES[it['mode']][0]} | {md_cell(it['real'])} | {tables} |")
    L += ["", "## ترتيب التحويل المقترح", "",
          "1. **قياس ما بقي**: `psql \"$MIGRATION_DATABASE_URL\" -f docs/sql/01-queries.sql` (القسم ز، Q53)، أو صفحة الدليل",
          "   المولَّدة `sim-guide.html` في مجلد التحيين، وفيها عمود «ما بقي [SIM]» لكل بند.",
          "2. **الإعدادات أولا** (البنود الآلية): `WEATHER_PROVIDER=open-meteo`، مزوّد الرسائل وFirebase، خط الهاتف، كاميرات",
          "   حقيقية، ثم `APP_ENV=production`. الخدمات نفسها تكتب بعدها كل معطى جديد حقيقيا.",
          "3. **تنظيف القديم بسكريبت**: `psql \"$MIGRATION_DATABASE_URL\" -f docs/sql/03-sim-to-real.sql` (تجربة جافة) ثم مع",
          "   `-v commit=1`. يشمل حذف بيانات العرض (R16) قبل إدخال الوحدات والوسائل الحقيقية (I1 إلى I3).",
          "4. **المعطيات الرسمية حين تصل**: من لوحة القيادة (القوائم، القوالب، أرشيف SNACR، الدليل الطبي، بطاقات الاستقبال)،",
          "   أو بطلبات `02-inserts.sql` لكميات كبيرة.",
          "5. **تعديلات الشيفرة** (الشهادات، المعاينة، حقول المؤسسة، الدرون) بطلب دمج حين يصل النص الرسمي.",
          "6. **التحقق**: إعادة Q53 حتى تصير الأرقام 0 (ما عدا التمارين).", "",
          "## التفصيل لكل بند", ""]
    for it in ITEMS:
        L += [f"### {it['id']}", "", f"**{it['title']}** · الطريقة الأساسية: **{MODES[it['mode']][0]}**", "",
              f"- **أين يظهر:** {it['where']}",
              f"- **المعطى الحقيقي ومن يقدّمه:** {it['real']}"]
        if it["tables"]:
            L.append(f"- **العلامة في القاعدة:** {'، '.join(f'`{t}`' for t in it['tables'])}")
        if it["count"]:
            L.append(f"- **عدّ ما بقي:** `{it['count']}`")
        L += ["- **كيف يُستبدل:**"]
        for i, (m, text) in enumerate(it["steps"], 1):
            L.append(f"  {i}. *{MODES[m][0]}*: {text}")
        L.append("")
    L += ["## التحيين الآلي لهذا الدليل", "",
          "- `python3 scripts/sim_guide/build.py`: يعيد كتابة هذا الملف من `items.py`.",
          "- `python3 scripts/sim_guide/build.py --check`: يفشل إن ظهر في الترحيلات جدول بعلامة [SIM] غير مذكور، أو طلب R",
          "  جديد في `03-sim-to-real.sql`، أو بند S جديد في الجرد، دون بند هنا.",
          "- `scripts/refresh-all.sh <مجلد>`: يشغّل الفحص في الخطوة 0، ثم يكتب `sim-guide.html` مع عدّ ما بقي [SIM] في القاعدة.",
          ""]
    return "\n".join(L)


# ------------------------------------------------------------------------------------------------ HTML
CSS = """
:root{--page:#F6F8FC;--card:#FFFFFF;--line:#E3E7EF;--ink:#182038;--muted:#5B6478;--brand:#1F3FA0;--brand-tint:#E8EDFA;
--gold:#C9A24A;--sim-bg:#FFF3D6;--sim:#7A4B00;--ok:#166B2E;--ok-bg:#E6F4EA;--orange:#F08C00;
--m-auto:#00695A;--m-auto-bg:#E0F3EF;--m-ui:#1F3FA0;--m-ui-bg:#E8EDFA;--m-script:#5E2A80;--m-script-bg:#F2EAF8;
--m-code:#B3121A;--m-code-bg:#FDE8E8;--m-keep:#3E4657;--m-keep-bg:#EEF0F4;
--f-body:"IBM Plex Sans Arabic","Noto Sans Arabic","Segoe UI",Tahoma,sans-serif;--f-mono:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--page:#0E1426;--card:#161E35;--line:#26304D;--ink:#E8ECF5;
--muted:#A6AFC4;--brand:#8FA8FF;--brand-tint:#1D2850;--sim-bg:#3A2E0E;--sim:#FFC933;--ok:#4CC772;--ok-bg:#163223;
--m-auto:#4DD0B8;--m-auto-bg:#123630;--m-ui:#8FA8FF;--m-ui-bg:#1D2850;--m-script:#C49BE6;--m-script-bg:#2D2040;
--m-code:#FF6B6B;--m-code-bg:#3D1A1F;--m-keep:#A6AFC4;--m-keep-bg:#232B45;color-scheme:dark}}
:root[data-theme="dark"]{--page:#0E1426;--card:#161E35;--line:#26304D;--ink:#E8ECF5;--muted:#A6AFC4;--brand:#8FA8FF;
--brand-tint:#1D2850;--sim-bg:#3A2E0E;--sim:#FFC933;--ok:#4CC772;--ok-bg:#163223;--m-auto:#4DD0B8;--m-auto-bg:#123630;
--m-ui:#8FA8FF;--m-ui-bg:#1D2850;--m-script:#C49BE6;--m-script-bg:#2D2040;--m-code:#FF6B6B;--m-code-bg:#3D1A1F;
--m-keep:#A6AFC4;--m-keep-bg:#232B45;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font-family:var(--f-body);font-size:15px;line-height:1.65}
.wrap{max-width:1100px;margin:0 auto;padding-inline:16px}
header{background:#0B1A3F;color:#F2F5FC;padding-block:26px 20px;border-bottom:3px solid var(--gold)}
header h1{margin:0;font-size:clamp(21px,3.2vw,30px);text-wrap:balance}
header p{margin:6px 0 0;color:#C3CBE0;max-width:75ch}
.sim{display:inline-block;background:#F5B400;color:#182038;font-weight:700;border-radius:6px;padding:0 6px;font-size:.85em}
.modes{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin:18px 0}
.mode{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px}
.mode b{display:block;font-size:16px}.mode small{color:var(--muted)}
.mode .n{font-family:var(--f-mono);font-size:24px;font-weight:600}
.pill{display:inline-block;border-radius:999px;padding:1px 10px;font-size:13px;font-weight:600;white-space:nowrap}
.auto{color:var(--m-auto);background:var(--m-auto-bg)}.ui{color:var(--m-ui);background:var(--m-ui-bg)}
.script{color:var(--m-script);background:var(--m-script-bg)}.code{color:var(--m-code);background:var(--m-code-bg)}
.keep{color:var(--m-keep);background:var(--m-keep-bg)}
.note{background:var(--sim-bg);color:var(--ink);border-inline-start:4px solid #F5B400;border-radius:10px;padding:10px 14px;margin:14px 0}
.filters{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0}
.filters button{font:inherit;cursor:pointer;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;padding:4px 12px}
.filters button[aria-pressed="true"]{background:var(--brand);border-color:var(--brand);color:var(--card);font-weight:600}
:focus-visible{outline:2px solid var(--orange);outline-offset:2px}
.item{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin:10px 0}
.item h3{margin:0 0 4px;font-size:16.5px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.item .id{font-family:var(--f-mono);color:var(--muted);font-weight:600}
.item dl{display:grid;grid-template-columns:max-content 1fr;gap:2px 12px;margin:8px 0;font-size:14px}
.item dt{color:var(--muted)}.item dd{margin:0}
.item ol{margin:6px 0 0;padding-inline-start:22px}.item li{margin:4px 0}
.left{font-family:var(--f-mono);font-weight:600;border-radius:8px;padding:1px 8px}
.left.zero{color:var(--ok);background:var(--ok-bg)}.left.some{color:var(--sim);background:var(--sim-bg)}
code{font-family:var(--f-mono);font-size:.88em;background:var(--page);border:1px solid var(--line);border-radius:5px;padding:0 4px;overflow-wrap:anywhere;direction:ltr;unicode-bidi:isolate}
header code{background:#12224D;border-color:#2A3A6B;color:#F2F5FC}
h2{margin:26px 0 8px;font-size:20px}
footer{color:var(--muted);font-size:13px;padding-block:24px}
@media (max-width:560px){.item dl{grid-template-columns:1fr}.item dt{margin-top:4px}}
"""

JS = """
document.querySelectorAll('.filters button').forEach(b=>b.addEventListener('click',()=>{
  document.querySelectorAll('.filters button').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
  const m=b.dataset.m;document.querySelectorAll('.item').forEach(i=>{i.hidden=m!=='all'&&!i.dataset.modes.split(' ').includes(m)});
}));
"""


def inline_md(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    return s.replace("[SIM]", '<span class="sim">[SIM]</span>')


def build_html(left: dict[str, int | None], db_note: str) -> str:
    by_mode = {m: sum(1 for it in ITEMS if it["mode"] == m) for m in MODES}
    tracked = [v for v in left.values() if v is not None]
    out = ['<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width,initial-scale=1">',
           "<title>دليل المعطيات التجريبية</title>",
           '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap">',
           f"<style>{CSS}</style></head><body>",
           '<header><div class="wrap"><h1>دليل المعطيات التجريبية <span class="sim">[SIM]</span> وكيف تُستبدل</h1>',
           f"<p>ء-حماية · {len(ITEMS)} بندا · مولَّد آليا في {date.today().isoformat()} من <code>scripts/sim_guide/items.py</code>. {html.escape(db_note)}</p>",
           "</div></header><main class=\"wrap\">",
           '<p>لا توجد آلية واحدة: كل معطى تجريبي يُستبدل بالطريقة التي تناسب مصدره. أغلب الحالات <b>آلية بعد إعداد واحد</b> أو '
           '<b>يدوية من لوحة القيادة</b>، وتكمّلها <b>سكريبتات SQL جاهزة</b> تنظّف ما بقي من المعطيات القديمة.</p>',
           '<div class="modes">']
    for m, (label, desc) in MODES.items():
        out.append(f'<div class="mode"><span class="pill {m}">{html.escape(label)}</span> <span class="n">{by_mode[m]}</span>'
                   f"<small style=\"display:block\">{inline_md(desc)}</small></div>")
    out.append("</div>")
    if tracked:
        out.append(f'<div class="note">ما بقي [SIM] في هذه القاعدة: <b>{sum(tracked)}</b> سطرا في '
                   f"<b>{sum(1 for v in tracked if v)}</b> بندا من {len(tracked)} بندا قابلا للعدّ.</div>")
    out.append('<div class="note">قاعدة ثابتة: لا يُنزع وسم <span class="sim">[SIM]</span> عن معطى ما زال مخترعا. كل سكريبت '
               "يُشغَّل أولا تجربة جافة (ROLLBACK) ثم بـ <code>-v commit=1</code>.</div>")
    out.append('<h2>البنود</h2><div class="filters" role="group" aria-label="تصفية حسب الطريقة">'
               '<button data-m="all" aria-pressed="true">الكل</button>')
    for m, (label, _) in MODES.items():
        out.append(f'<button data-m="{m}" aria-pressed="false">{html.escape(label)}</button>')
    out.append("</div>")
    for it in ITEMS:
        modes = " ".join(sorted({it["mode"], *(m for m, _ in it["steps"])}))
        badge = ""
        if it["id"] in left:
            v = left[it["id"]]
            badge = ('<span class="left">؟</span>' if v is None else
                     f'<span class="left {"zero" if v == 0 else "some"}" title="ما بقي [SIM]">{v}</span>')
        out.append(f'<article class="item" id="{it["id"].lower()}" data-modes="{modes}"><h3><span class="id">{it["id"]}</span>'
                   f'{inline_md(it["title"])} <span class="pill {it["mode"]}">{html.escape(MODES[it["mode"]][0])}</span>{badge}</h3><dl>'
                   f"<dt>أين يظهر</dt><dd>{inline_md(it['where'])}</dd>"
                   f"<dt>المعطى الحقيقي</dt><dd>{inline_md(it['real'])}</dd>")
        if it["tables"]:
            out.append(f"<dt>العلامة في القاعدة</dt><dd>{'، '.join(f'<code>{t}</code>' for t in it['tables'])}</dd>")
        out.append("</dl><ol>")
        for m, text in it["steps"]:
            out.append(f'<li><span class="pill {m}">{html.escape(MODES[m][0])}</span> {inline_md(text)}</li>')
        out.append("</ol></article>")
    out += ["<footer>المراجع: docs/sql/sim-inventory.md · docs/sql/01-queries.sql (Q53) · docs/sql/02-inserts.sql · "
            "docs/sql/03-sim-to-real.sql · docs/sql/sim-guide.md</footer></main>", f"<script>{JS}</script></body></html>"]
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="fail if a [SIM] source of the repository is not in the guide")
    ap.add_argument("--html", type=Path, help="also write the HTML page (with live counts when a database is set)")
    args = ap.parse_args()
    if args.check:
        problems = check()
        for p in problems:
            print(f"sim-guide: {p}", file=sys.stderr)
        if problems:
            sys.exit(1)
        print(f"sim-guide: {len(ITEMS)} items cover every [SIM] source of the migrations and every R request")
        return
    MD_OUT.write_text(build_md(), encoding="utf-8")
    print(f"sim-guide: {MD_OUT.relative_to(ROOT)} ({len(ITEMS)} items)")
    if args.html:
        url = db_url()
        left = counts(url) if url else {}
        note = "عدد ما بقي [SIM] محسوب على القاعدة المحلية." if left else "بلا قاعدة معطيات: عمود «ما بقي» غائب."
        args.html.parent.mkdir(parents=True, exist_ok=True)
        args.html.write_text(build_html(left, note), encoding="utf-8")
        print(f"sim-guide: {args.html}")


if __name__ == "__main__":
    main()
