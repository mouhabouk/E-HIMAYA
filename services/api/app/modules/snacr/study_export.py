"""A SNACR study as the Office's file: a PDF (A4 landscape, Arabic) and an Excel workbook with one sheet per table
(SEC_GLOB, SAP, SR, LCI, SB, DIV), the layout of the file "ariana" (unit, délégation, the count per year and period,
the yearly mean, the mean travel time)."""

import html
import io
from typing import Any

from app.core import print_footer
from app.modules.snacr.models import Study

PERIOD_AR = {"J": "نهار", "S": "ليل", "T": "اليوم كاملا"}
PERIOD_FR = {"J": "J", "S": "S", "T": "24h"}
SOURCE_AR = {"office": "ملف الديوان", "simulated": "محاكاة [SIM]", "live": "سجلات القاعات"}


def minutes(value: float | None) -> str:
    """6.91 → "6:55" (minutes and seconds)."""
    if value is None:
        return "—"
    total = round(value * 60)
    return f"{total // 60}:{total % 60:02d}"


def _count(value: Any) -> str:
    return "*" if value is None else str(value)


def _mean(value: float | None) -> str:
    if value is None:
        return "*"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def title(study: Study, gouvernorat_name: str | None) -> str:
    scope = f"ولاية {gouvernorat_name}" if study.gouvernorat_code else "المستوى الوطني"
    return f"دراسة SNACR رقم {study.number}، {scope}"


def settings_lines(study: Study) -> list[tuple[str, str]]:
    years = "، ".join(str(y) for y in study.years)
    split = "فترتان: نهار من 06:00 إلى 18:00، ليل من 18:01 إلى 05:59" if study.split else "اليوم كاملا (حصة واحدة)"
    return [
        ("السنوات المعتمدة", f"{years} ({len(study.years)} سنوات)" if len(study.years) > 2 else years),
        ("تقسيم اليوم", split),
        ("زمن التنقل", f"الوصول − الخروج، يُحتسب من 0 إلى {study.travel_max} دقيقة"),
        ("الحالة", "الدراسة الحالية" if study.status == "current" else "مؤرشفة"),
        ("أطلقها", f"{study.created_by_name or study.created_by}، {study.created_at:%Y-%m-%d %H:%M}"),
    ]


_CSS = """
@page { size: A4 landscape; margin: 12mm 10mm 14mm 10mm; }
body { font-family: "Noto Naskh Arabic", "Noto Sans Arabic", "DejaVu Sans", sans-serif; font-size: 8.5pt;
  color: #1b1b1b; direction: rtl; text-align: right; }
.brand { font-size: 10pt; color: #555; border-bottom: 3px solid #b71c1c; padding-bottom: 5px; }
h1 { font-size: 17pt; color: #b71c1c; margin: 8mm 0 3mm; }
h2 { font-size: 12pt; margin: 0 0 4px; color: #b71c1c; page-break-before: always; }
h3 { font-size: 10pt; margin: 8px 0 3px; }
.sim { margin: 4mm 0; padding: 5px 9px; border: 2px solid #b45309; background: #fff7e6; color: #92400e;
  font-weight: bold; }
table { width: 100%; border-collapse: collapse; margin-top: 3px; }
tr { page-break-inside: avoid; }
th, td { border: 1px solid #bbb; padding: 2px 4px; }
th { background: #f1f1f1; font-weight: bold; text-align: center; }
td.num { text-align: center; direction: ltr; unicode-bidi: isolate; }
tr.sub td { background: #f6f6f6; font-weight: bold; }
tr.tot td { background: #ececec; font-weight: bold; }
.small { font-size: 7.5pt; color: #555; }
"""


def _head(years: list[int], periods: list[str], glob: bool) -> str:
    n = len(periods)
    fixed = ["وحدة التدخل", "المعتمدية"] + (["المساحة (كم²)", "السكان 2024", "الكثافة (س/كم²)"] if glob else [])
    top = "".join(f'<th rowspan="2">{h}</th>' for h in fixed)
    top += "".join(f'<th colspan="{n}">{y}</th>' for y in years)
    top += f'<th colspan="{n}">المعدل السنوي</th><th colspan="{n}">متوسط زمن التنقل</th><th rowspan="2">المجموع</th>'
    sub = "".join(f"<th>{PERIOD_AR[p]}</th>" for _ in range(len(years) + 2) for p in periods)
    return f"<tr>{top}</tr><tr>{sub}</tr>"


def _cells(item: dict[str, Any], years: list[int], periods: list[str]) -> str:
    out = []
    for y in years:
        per = item["counts"].get(str(y))
        out += [f'<td class="num">{_count(None if per is None else per[p])}</td>' for p in periods]
    out += [f'<td class="num">{_mean(item["mean"][p])}</td>' for p in periods]
    out += [f'<td class="num">{minutes(item["travel"][p])}</td>' for p in periods]
    out.append(f'<td class="num">{item["total"]}</td>')
    return "".join(out)


def _table_html(table: dict[str, Any], years: list[int], periods: list[str]) -> str:
    e = html.escape
    glob = table["key"] == "SEC_GLOB"
    blank = '<td class="num"></td>' * (3 if glob else 0)
    parts = []
    for block in table["gouvernorats"]:
        rows = [f"<h3>ولاية {e(block['gouvernorat'])}</h3><table>", _head(years, periods, glob)]
        for unit in block["units"]:
            for i, r in enumerate(unit["rows"]):
                first = f'<td rowspan="{len(unit["rows"])}">{e(unit["unit"])}</td>' if i == 0 else ""
                extra = (
                    f'<td class="num">{r["area_km2"] or "—"}</td><td class="num">{r["population"] or "—"}</td>'
                    f'<td class="num">{r["density"] or "—"}</td>'
                    if glob
                    else ""
                )
                rows.append(f"<tr>{first}<td>{e(r['delegation'])}</td>{extra}{_cells(r, years, periods)}</tr>")
            s = unit["subtotal"]
            sub_extra = f'<td class="num">{s.get("area_km2") or "—"}</td><td></td><td></td>' if glob else ""
            rows.append(
                f'<tr class="sub"><td>المجموع الفرعي</td><td class="num">{s["delegations"]}</td>{sub_extra}'
                f"{_cells(s, years, periods)}</tr>"
            )
        rows.append(
            f'<tr class="tot"><td colspan="2">مجموع الولاية</td>{blank}{_cells(block["total"], years, periods)}</tr>'
        )
        rows.append("</table>")
        parts.append("".join(rows))
    if len(table["gouvernorats"]) > 1:
        parts.append(
            f'<table>{_head(years, periods, glob)}<tr class="tot"><td colspan="2">المجموع الوطني</td>{blank}'
            f"{_cells(table['total'], years, periods)}</tr></table>"
        )
    return "".join(parts)


def render_html(study: Study, gouvernorat_name: str | None) -> str:
    e = html.escape
    t = study.tables
    years, periods = t["years"], t["periods"]
    q = study.quality
    settings = "".join(f"<tr><th>{e(k)}</th><td>{e(v)}</td></tr>" for k, v in settings_lines(study))
    data = "".join(
        f"<tr><td class='num'>{d['year']}</td><td>{e(SOURCE_AR.get(d['source'], d['source']))}</td>"
        f"<td>{e(d.get('file_name') or '—')}</td><td class='num'>{d['rows']}</td></tr>"
        for d in q.get("datasets", [])
    )
    qual = [
        ("التدخلات في الدراسة", q.get("rows", 0)),
        ("منها خرجات بيضاء (SB)", q.get("white", 0)),
        ("أزمنة تنقل محتسبة", q.get("travel_kept", 0)),
        ("أزمنة تنقل فارغة", q.get("travel_missing", 0)),
        ("أزمنة تنقل سالبة (مستبعدة)", q.get("travel_negative", 0)),
        (f"أزمنة تنقل تفوق {study.travel_max} دقيقة (مستبعدة)", q.get("travel_over", 0)),
        ("دون وحدة تدخل (الوحدة = المعتمدية)", q.get("unit_missing", 0)),
        ("معتمدية غير معروفة", q.get("delegation_unmatched", 0)),
    ]
    qual_rows = "".join(f"<tr><th>{e(k)}</th><td class='num'>{v}</td></tr>" for k, v in qual)
    sim = '<div class="sim">[SIM] تحتوي هذه الدراسة على سنوات محاكاة</div>' if study.simulated else ""
    tables = "".join(
        f"<h2>{e(tb['key'])}: {e(tb['label_ar'])}</h2>{_table_html(tb, years, periods)}" for tb in t["tables"]
    )
    head = title(study, gouvernorat_name)
    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>{e(head)}</title>
<style>{_CSS}</style></head><body>
<div class="brand">منصة ء-حماية · الديوان الوطني للحماية المدنية · تحليل المخاطر وتغطيتها (SNACR)</div>
<h1>{e(head)}</h1>{sim}
<table>{settings}</table>
<h3>الملفات السنوية</h3>
<table><tr><th>السنة</th><th>المصدر</th><th>الملف</th><th>الأسطر</th></tr>{data}</table>
<h3>تقرير الجودة</h3><table>{qual_rows}</table>
<p class="small">الجداول: SEC_GLOB كل الخرجات ومنها البيضاء؛ SAP إسعاف الأشخاص؛ SR النجدة على الطرقات؛
LCI مكافحة الحرائق؛ SB الخرجات البيضاء (INTERV_OUI_NON = لا)؛ DIV تدخلات مختلفة. المعتمدية مكان الحادث،
والوحدة هي التي غطت المعتمدية تلك السنة (أكثر الوحدات خروجا إليها). «*»: سنة لم تكن فيها المعتمدية تحت
هذه الوحدة. المعدل السنوي على السنوات الظاهرة.</p>
{tables}
</body></html>"""


def render_pdf(study: Study, gouvernorat_name: str | None) -> bytes:
    from weasyprint import HTML

    page = print_footer.apply(
        render_html(study, gouvernorat_name),
        ["منصة ء-حماية · الديوان الوطني للحماية المدنية", title(study, gouvernorat_name)],
        f"e-Himaya SNACR study {study.number} {study.id}",
    )
    pdf: bytes = HTML(string=page).write_pdf()
    return pdf


def render_xlsx(study: Study, gouvernorat_name: str | None) -> bytes:
    """One sheet per table, with the headings of the file "ariana": Unité d'intervention, Délégation, (Superficie,
    Nb_pop, Dens_Pop), Nombre d'interventions per year and period, Moyenne Annuelle, Temps mis en route moyen."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    t = study.tables
    years, periods = t["years"], t["periods"]
    n = len(periods)
    bold = Font(bold=True)
    grey = PatternFill("solid", fgColor="EEEEEE")
    center = Alignment(horizontal="center", vertical="center")
    wb = Workbook()
    info = wb.active
    info.title = "ETUDE"
    info.sheet_view.rightToLeft = True
    info.append([title(study, gouvernorat_name)])
    info["A1"].font = Font(bold=True, size=13)
    for k, v in settings_lines(study):
        info.append([k, v])
    info.append([])
    for k, v in sorted(study.quality.items()):
        if k != "datasets":
            info.append([k, v])
    for tb in t["tables"]:
        glob = tb["key"] == "SEC_GLOB"
        ws = wb.create_sheet(tb["key"])
        fixed = ["Unité d’intervention", "Délégation"] + (
            ["Superficie en Km2", "Nb_pop", "Dens_Pop (H/km²)"] if glob else []
        )
        start = len(fixed) + 1
        row1 = fixed + ["Nombre d'interventions"] + [None] * (len(years) * n - 1)
        row1 += ["Moyenne Annuelle"] + [None] * (n - 1) + ["Temps mis en route moyen"] + [None] * (n - 1) + ["Total"]
        row2 = [None] * len(fixed) + [y for y in years for _ in periods] + [None] * (2 * n + 1)
        row3 = [None] * len(fixed) + [PERIOD_FR[p] for _ in range(len(years) + 2) for p in periods] + [None]
        for r in (row1, row2, row3):
            ws.append(r)
        for c in range(1, len(row1) + 1):
            for rr in (1, 2, 3):
                cell = ws.cell(rr, c)
                cell.font, cell.fill, cell.alignment = bold, grey, center

        def values(item: dict[str, Any]) -> list[Any]:
            out: list[Any] = []
            for y in years:
                per = item["counts"].get(str(y))
                out += ["*" if per is None else per[p] for p in periods]
            out += [item["mean"][p] if item["mean"][p] is not None else "*" for p in periods]
            out += [round(item["travel"][p] / 1440, 6) if item["travel"][p] is not None else None for p in periods]
            out.append(item["total"])
            return out

        time_cols = range(start + len(years) * n + n, start + len(years) * n + 2 * n)
        for block in tb["gouvernorats"]:
            for unit in block["units"]:
                for i, r in enumerate(unit["rows"]):
                    extra = [r["area_km2"], r["population"], r["density"]] if glob else []
                    ws.append([unit["unit"] if i == 0 else None, r["delegation"], *extra, *values(r)])
                s = unit["subtotal"]
                ws.append(
                    ["Sous Total", s["delegations"], *([s.get("area_km2"), None, None] if glob else []), *values(s)]
                )
                for c in range(1, ws.max_column + 1):
                    ws.cell(ws.max_row, c).font = bold
            ws.append([f"TOTAL {block['gouvernorat']}", None, *([None] * 3 if glob else []), *values(block["total"])])
            for c in range(1, ws.max_column + 1):
                ws.cell(ws.max_row, c).font, ws.cell(ws.max_row, c).fill = bold, grey
        if len(tb["gouvernorats"]) > 1:
            ws.append(["TOTAL", None, *([None] * 3 if glob else []), *values(tb["total"])])
        for row in ws.iter_rows(min_row=4):
            for c in time_cols:
                row[c - 1].number_format = "[mm]:ss"
        ws.column_dimensions["A"].width = 22
        ws.column_dimensions["B"].width = 22
        ws.freeze_panes = ws.cell(4, start)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
