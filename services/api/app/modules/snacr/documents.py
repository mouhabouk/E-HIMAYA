"""The plan as a document, in Arabic (docs/phase-s/design-s.md §7). Its sections follow the cycle the references share:
framework, method, territory, everyday risks, coverage and gaps, specific risks, objectives, review; the completeness
of the archive in annex."""

import html
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.geo.models import Delegation, Gouvernorat
from app.modules.snacr.models import Plan

FAMILY = {"medical": "الإسعاف", "road": "حوادث الطرقات", "fire": "الحرائق", "rescue": "الإنقاذ"}
ZONE = {"urban": "حضرية", "periurban": "شبه حضرية", "rural": "ريفية"}
PRIORITY = {"high": "مرتفعة", "medium": "متوسطة", "low": "منخفضة", None: "—"}
STATUS = {"draft": "مسودة", "approved": "معتمد", "superseded": "معوَّض بنسخة أحدث"}
HAZARD = {
    "flood": "الفيضانات",
    "forest_fire": "حرائق الغابات",
    "industrial": "المخاطر الصناعية",
    "hazmat_transport": "نقل المواد الخطرة",
    "coastal": "المخاطر الساحلية والغرق",
    "earthquake": "الزلازل",
    "storm": "العواصف الرملية والرياح",
    "drought": "الجفاف والحرارة",
    "epidemic": "الأوبئة",
}
USE = {
    "legal_basis": "الأساس القانوني",
    "committees_and_review": "اللجان والاعتماد والمراجعة السنوية",
    "special_risks": "المخاطر الخاصة وأهداف الحد منها",
    "structure_everyday_special_coverage": "بنية المخطط: المخاطر الجارية والخاصة وأهداف التغطية",
    "plan_cycle": "دورة المخطط: الإطار، المخاطر، التحليل، القرار، التقييم",
    "percentile_indicators": "قياس الآجال بالمئين التسعين",
    "matrix": "مستوى الخطر = الاحتمال × الأثر",
}
SKIP = {
    "called_missing": "دون ساعة البلاغ",
    "nature_unknown": "طبيعة غير معروفة",
    "gouvernorat_unknown": "إدارة جهوية غير معروفة",
    "other_year": "من سنة أخرى",
}
FLAG = {
    "arrival_missing": "دون ساعة الوصول",
    "arrival_negative": "وصول قبل البلاغ",
    "arrival_outlier": "وصول بعد أكثر من 3 ساعات",
    "delegation_unmatched": "معتمدية غير معروفة",
    "delegation_reassigned": "معتمدية مسندة إلى ولاية أخرى وصُحّحت",
}


async def names(session: AsyncSession) -> dict[str, dict[int, str]]:
    return {
        "gouvernorats": dict((await session.execute(select(Gouvernorat.code, Gouvernorat.name_ar))).all()),
        "delegations": dict((await session.execute(select(Delegation.id, Delegation.name_ar))).all()),
    }


def _n(value: Any, suffix: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        text = f"{value:,.1f}".replace(",", " ")
    elif isinstance(value, int):
        text = f"{value:,}".replace(",", " ")
    else:
        text = str(value)
    return text + suffix


def _table(head: list[str], rows: list[list[Any]], numeric_from: int = 1) -> str:
    e = html.escape
    out = ["<table><tr>", *(f"<th>{e(h)}</th>" for h in head), "</tr>"]
    for row in rows:
        out.append("<tr>")
        for i, cell in enumerate(row):
            cls = ' class="num"' if i >= numeric_from else ""
            out.append(f"<td{cls}>{e(str(cell))}</td>")
        out.append("</tr>")
    if not rows:
        out.append(f'<tr><td colspan="{len(head)}">—</td></tr>')
    out.append("</table>")
    return "".join(out)


def _objective(o: dict[str, Any], g: dict[int, str]) -> str:
    where = g.get(o["gouvernorat_code"], str(o["gouvernorat_code"]))
    if o["kind"] == "coverage":
        return (
            f"معتمدية {o['delegation']} ({where}): رفع نسبة تدخلات {FAMILY[o['family']]} التي تصل في أجل "
            f"{o['target_min']} دقيقة من {_n(o['from_pct'], '%')} إلى {_n(o['to_pct'], '%')}."
        )
    if o["kind"] == "data":
        return (
            f"ولاية {where}: تسجيل ساعة الوصول في كل تدخل، من {_n(o['from_pct'], '%')} من التدخلات اليوم إلى "
            f"{_n(o['to_pct'], '%')} على الأقل."
        )
    if o["kind"] == "names":
        return f"ولاية {where}: ربط {_n(o['rows'])} تدخلا بمعتمديتها في جدول المرادفات."
    return f"ولاية {where}: إعداد أو تحيين مخطط تدخل خاص بخطر {HAZARD.get(o.get('hazard') or '', '')}."


_CSS = """
@page { size: A4; margin: 16mm 14mm 18mm 14mm;
  @bottom-center { content: counter(page) " / " counter(pages); font-size: 8pt; color: #666; } }
body { font-family: "Noto Naskh Arabic", "Noto Sans Arabic", "DejaVu Sans", sans-serif; font-size: 9.5pt;
  color: #1b1b1b; direction: rtl; text-align: right; }
.cover { page-break-after: always; }
.cover h1 { font-size: 19pt; color: #b71c1c; margin: 26mm 0 3mm; }
.cover .brand { font-size: 11pt; color: #555; border-bottom: 3px solid #b71c1c; padding-bottom: 6px; }
.sim { margin: 6mm 0; padding: 6px 10px; border: 2px solid #b45309; background: #fff7e6; color: #92400e;
  font-weight: bold; }
h2 { font-size: 12pt; margin: 16px 0 6px; border-bottom: 1px solid #b71c1c; color: #b71c1c; padding-bottom: 2px; }
h3 { font-size: 10pt; margin: 10px 0 4px; }
table { width: 100%; border-collapse: collapse; margin-top: 4px; }
tr { page-break-inside: avoid; }
th, td { border: 1px solid #ccc; padding: 3px 5px; vertical-align: top; }
th { background: #f4f4f4; }
td.num { text-align: center; direction: ltr; unicode-bidi: isolate; }
.small { font-size: 8pt; color: #555; }
ol li { margin-bottom: 3px; }
"""


def render_html(plan: Plan, summary: dict[str, Any], names: dict[str, dict[int, str]]) -> str:
    e = html.escape
    g = names["gouvernorats"]
    c = plan.content
    a = c["analysis"]
    m = a["method"]
    regional = plan.gouvernorat_code is not None
    title = (
        f"المخطط الجهوي لتحليل المخاطر وتغطيتها، ولاية {g.get(plan.gouvernorat_code or 0, '')}"
        if regional
        else "المخطط الوطني لتحليل المخاطر وتغطيتها (SNACR)"
    )
    committee = (
        f"اللجنة الجهوية برئاسة السيد والي {g.get(plan.gouvernorat_code or 0, '')}"
        if regional
        else "اللجنة الوطنية برئاسة السيد وزير الداخلية"
    )
    years = "، ".join(str(y) for y in plan.years)
    cover_rows = [
        ["النسخة", f"{plan.version} · {STATUS[plan.status]}"],
        ["السنوات المحلَّلة", years],
        ["الجهة المعتمِدة", committee],
        [
            "أُعدّ بتاريخ",
            plan.created_at.strftime("%Y-%m-%d") + (f" · {plan.created_by_name}" if plan.created_by_name else ""),
        ],
    ]
    if plan.approved_at:
        cover_rows.append(["اعتُمد بتاريخ", plan.approved_at.strftime("%Y-%m-%d") + f" · {plan.approved_by_name or ''}"])
        cover_rows.append(["المراجعة القادمة", summary["review_due"].strftime("%Y-%m-%d")])
        cover_rows.append(["صالح إلى", summary["valid_until"].strftime("%Y-%m-%d")])
    sim = (
        '<div class="sim">[SIM] جزء من المعطيات تجريبي: سنوات مولَّدة على توزيعات أرشيف 2022 الحقيقي، أو مخاطر خاصة '
        "أولية لم تراجعها اللجنة بعد. تُستبدل بالمعطيات الحقيقية بنفس العملية.</div>"
        if plan.simulated
        else ""
    )
    sections: list[str] = []

    refs = [[r["code"], r["title"], USE.get(r["use"], r["use"])] for r in c["references"]]
    sections.append("<h2>1. الإطار والمرجعية</h2>" + _table(["المرجع", "العنوان", "ما يُعتمد منه"], refs, 99))

    targets = [[FAMILY[f], *(f"{m['targets'][f][z]} د" for z in ("urban", "periurban", "rural"))] for f in FAMILY]
    sections.append(
        "<h2>2. المنهجية</h2>"
        "<p>تُحلَّل <b>المخاطر الجارية</b> (كثيرة الوقوع، محدودة الأثر) من أرشيف التدخلات لثلاث سنوات متتالية: التواتر "
        "لكل ألف ساكن (تعداد 2024)، وأجل الوصول من البلاغ في الوسيط وفي المئين التسعين، ونسبة التدخلات التي تصل في "
        "الأجل المستهدف لصنف المعتمدية. وتُحلَّل <b>المخاطر الخاصة</b> (نادرة، شديدة الأثر) بسجل يقدّر فيه الاحتمال "
        "والأثر من 1 إلى 5.</p>"
        f"<p>الهدف: أن تصل {m['goal']}% من التدخلات في الأجل المستهدف. صنف المعتمدية: حضرية من {m['urban']} ساكن "
        f"في الكلم²، وشبه حضرية من {m['periurban']}، وريفية دون ذلك.</p>"
        + _table(["الصنف", "حضرية", "شبه حضرية", "ريفية"], targets)
        + "<p class='small'>مستوى التواتر من 1 إلى 5 حسب خُمس المعتمدية بين معتمديات البلاد. مستوى التغطية 1 إذا "
        "بلغت الهدف، ثم 2 و3 و4 و5 كلما ابتعدت عنه (10 و25 و40 نقطة). الأولوية = التواتر × التغطية: مرتفعة من 15، "
        "ومتوسطة من 8.</p>"
    )

    t = a["totals"]
    sections.append(
        "<h2>3. الإقليم والنشاط</h2>"
        + _table(
            ["المؤشر", "القيمة"],
            [
                ["السكان (تعداد 2024)", _n(t["population"])],
                ["متوسط التدخلات السنوي", _n(t["annual"])],
                ["التدخلات لكل ألف ساكن في السنة", _n(t["rate_per_1000"])],
                ["نسبة التدخلات في الأجل المستهدف", _n(t["compliance_pct"], "%")],
                ["اكتمال ساعة الوصول", _n(t["completeness_pct"], "%")],
            ],
        )
        + "<h3>حسب السنة والصنف</h3>"
        + _table(
            ["السنة", *FAMILY.values()],
            [[y["year"], *(_n(y["families"].get(f, 0)) for f in FAMILY)] for y in a["by_year"]],
        )
    )

    if regional:
        rows = [
            [
                d["name_ar"],
                ZONE[d["zone"]],
                _n(d["annual"]),
                _n(d["rate_per_1000"]),
                _n(d["families"].get("medical", {}).get("arrival_p90")),
                _n(d["compliance_pct"], "%"),
                _n(d["completeness_pct"], "%"),
            ]
            for d in a["delegations"]
        ]
        head = ["المعتمدية", "الصنف", "تدخلات/سنة", "لكل ألف", "م90 الإسعاف (د)", "في الأجل", "الاكتمال"]
    else:
        rows = [
            [
                g.get(x["code"], x["code"]),
                _n(x["annual"]),
                _n(x["rate_per_1000"]),
                _n(x["families"].get("medical", {}).get("arrival_median")),
                _n(x["families"].get("medical", {}).get("arrival_p90")),
                _n(x["compliance_pct"], "%"),
                _n(x["completeness_pct"], "%"),
            ]
            for x in a["gouvernorats"]
        ]
        head = ["الولاية", "تدخلات/سنة", "لكل ألف", "وسيط الإسعاف (د)", "م90 الإسعاف (د)", "في الأجل", "الاكتمال"]
    month_names = [
        "جانفي",
        "فيفري",
        "مارس",
        "أفريل",
        "ماي",
        "جوان",
        "جويلية",
        "أوت",
        "سبتمبر",
        "أكتوبر",
        "نوفمبر",
        "ديسمبر",
    ]
    months = [[FAMILY[f], *(_n(v) for v in a["month"][f])] for f in FAMILY]
    subtypes = [
        [FAMILY[f], "، ".join(f"{s['subtype']} ({_n(s['rows'])})" for s in a["subtypes"][f][:5])] for f in FAMILY
    ]
    sections.append(
        "<h2>4. المخاطر الجارية</h2>"
        + _table(head, rows)
        + "<h3>الموسمية (عدد التدخلات حسب الشهر)</h3>"
        + f"<div class='small'>{_table(['الصنف', *month_names], months)}</div>"
        + "<h3>أكثر الأنواع تكرارا</h3>"
        + _table(["الصنف", "الأنواع"], subtypes, 99)
    )

    matrix_rows = [[f"تواتر {5 - i}", *a["matrix"][4 - i]] for i in range(5)]
    gaps = sorted(
        (d for d in a["delegations"] if d["priority"] in ("high", "medium")),
        key=lambda d: (d["priority"] != "high", -(d["frequency_level"] or 0) * (d["coverage_level"] or 0)),
    )[:40]
    gap_rows = [
        [
            d["name_ar"],
            g.get(d["gouvernorat_code"], ""),
            PRIORITY[d["priority"]],
            d["frequency_level"],
            d["coverage_level"],
            _n(d["compliance_pct"], "%"),
        ]
        for d in gaps
    ]
    sections.append(
        "<h2>5. التغطية والفجوات</h2><p>عدد المعتمديات حسب مستوى التواتر (الأسطر) ومستوى التغطية (الأعمدة، 1 = الهدف "
        "محقق).</p>"
        + _table(["", "تغطية 1", "2", "3", "4", "5"], matrix_rows)
        + "<h3>المعتمديات ذات الأولوية</h3>"
        + _table(["المعتمدية", "الولاية", "الأولوية", "التواتر", "التغطية", "في الأجل"], gap_rows, 2)
    )

    specials = [
        [
            g.get(r["gouvernorat_code"], ""),
            HAZARD.get(r["hazard"], r["hazard"]) + (" [SIM]" if r["simulated"] else ""),
            r["probability"],
            r["gravity"],
            PRIORITY[r["level"]],
        ]
        for r in sorted(c["special_risks"], key=lambda r: -r["probability"] * r["gravity"])
    ]
    sections.append(
        "<h2>6. المخاطر الخاصة</h2>" + _table(["الولاية", "الخطر", "الاحتمال", "الأثر", "المستوى"], specials, 2)
    )

    objectives = "".join(f"<li>{e(_objective(o, g))}</li>" for o in c["objectives"][:80])
    sections.append(f"<h2>7. الأهداف</h2><ol>{objectives or '<li>—</li>'}</ol>")
    sections.append(
        "<h2>8. المراجعة والمتابعة</h2>"
        f"<p>تراجع {e(committee)} هذا المخطط كل {m['review_months']} شهرا على الأقل، في اجتماعها السنوي الذي "
        f"يفرضه الأمر عدد 942 لسنة 1993، ويُعاد إعداده كل {m['validity_years']} سنوات أو عند تغيّر المعطيات تغيرا "
        "جوهريا. تتابع المنظومة المؤشرات نفسها كل سنة على آخر ثلاث سنوات محمّلة.</p>"
    )

    quality_rows = []
    for q in c["quality"]:
        info = q["quality"]
        skipped = "، ".join(f"{SKIP.get(k, k)}: {_n(v)}" for k, v in (info.get("skipped") or {}).items()) or "—"
        flags = "، ".join(f"{FLAG.get(k, k)}: {_n(v)}" for k, v in (info.get("flags") or {}).items()) or "—"
        quality_rows.append([f"{q['year']}{' [SIM]' if q['simulated'] else ''}", _n(q["rows"]), skipped, flags])
    sections.append(
        "<h2>ملحق: اكتمال الأرشيف</h2>"
        + _table(["السنة", "الأسطر المعتمدة", "أسطر مستبعدة", "ملاحظات على الأسطر"], quality_rows, 1)
        + "<p class='small'>لا يقرأ الاستيراد العنوان ولا الوصف ولا الملاحظات ولا الأعوان ولا الآليات: لا اسم ولا هاتف "
        "ولا رقم هوية في قاعدة المخطط.</p>"
    )

    cover = _table(["", ""], cover_rows, 99).replace("<tr><th></th><th></th></tr>", "")
    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>{e(title)}</title>
<style>{_CSS}</style></head><body>
<div class="cover"><div class="brand">منصة ء-حماية · الديوان الوطني للحماية المدنية</div><h1>{e(title)}</h1>
{sim}{cover}</div>
{"".join(sections)}
</body></html>"""


def render_pdf(page: str) -> bytes:
    from weasyprint import HTML

    pdf: bytes = HTML(string=page).write_pdf()
    return pdf
