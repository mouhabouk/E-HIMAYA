"""Statistical cross-tabulations (Yamen, 2026-11-01): the interventions counted across two dimensions at once (the
nature of the event, the period, the resources used, the gouvernorat, the level), each cell set against the same
period one year earlier; and the findings worth a sentence ("ارتفاع حرائق المحاصيل الزراعية بنسبة 15% مقارنة
بالسنة الفارطة").

Counts only, from ``ops.incident`` (opened in the period, merged ones left out) and ``ops.assignment`` for the
resources; the scope rule of the other analytics (a regional caller sees their gouvernorat only).
"""

from datetime import date
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics import domain

Dimension = Literal[
    "category", "classification", "gouvernorat", "resource", "level", "month", "quarter", "weekday", "hour"
]

_LOCAL = "(i.opened_at AT TIME ZONE 'Africa/Tunis')"
_EXPR: dict[str, str] = {
    "category": "i.category",
    "classification": "coalesce(i.classification, i.category)",
    "gouvernorat": "CAST(i.gouvernorat_code AS text)",
    "resource": "coalesce(res.kind, 'none')",
    "level": "i.op_level",
    "month": f"CAST(extract(month FROM {_LOCAL}) AS int)::text",
    "quarter": f"CAST(extract(quarter FROM {_LOCAL}) AS int)::text",
    "weekday": f"CAST(extract(isodow FROM {_LOCAL}) AS int)::text",
    "hour": f"CAST(extract(hour FROM {_LOCAL}) AS int)::text",
}

# Arabic names of what a finding speaks of (the dashboard translates the keys itself).
NATURE_AR = {
    "fire": "الحرائق",
    "flood": "الفيضانات",
    "traffic_accident": "حوادث المرور",
    "drowning": "حالات الغرق",
    "landslide": "الانزلاقات الأرضية",
    "chemical_leak": "تسربات المواد الخطرة",
    "medical": "تدخلات الإسعاف",
    "sos": "نداءات النجدة",
    "other": "التدخلات الأخرى",
    "forest_fire": "حرائق الغابات",
    "crop_fire": "حرائق المحاصيل الزراعية",
    "residential_fire": "حرائق المساكن",
    "industrial_fire": "الحرائق الصناعية",
    "vehicle_fire": "حرائق العربات",
    "road_accident": "حوادث الطرقات",
    "urban_flood": "الفيضانات الحضرية",
    "flash_flood": "السيول الجارفة",
    "river_flood": "فيضانات الأودية",
    "gas_leak": "تسربات الغاز",
}
# A change is a finding when both years together have at least this many interventions and it moves this much.
MIN_COUNT = 5
MIN_CHANGE_PCT = 10.0


def _year_before(day: date) -> date:
    try:
        return day.replace(year=day.year - 1)
    except ValueError:  # 29 February
        return day.replace(year=day.year - 1, day=28)


async def _counts(
    session: AsyncSession, rows: str, cols: str | None, codes: list[int], start: date, end: date
) -> dict[tuple[str, str], int]:
    params: dict[str, Any] = {
        "t0": domain.day_start(start),
        "t1": domain.day_start(date.fromordinal(end.toordinal() + 1)),
    }
    where = "i.opened_at >= :t0 AND i.opened_at < :t1 AND i.merged_into IS NULL"
    if codes:
        where += " AND i.gouvernorat_code = ANY(CAST(:codes AS smallint[]))"
        params["codes"] = codes
    join = ""
    if "resource" in (rows, cols):
        join = (
            "LEFT JOIN ops.assignment a ON a.incident_id = i.id AND a.status <> 'cancelled' "
            "LEFT JOIN ops.resource res ON res.id = a.resource_id"
        )
    col = _EXPR[cols] if cols else "''"
    # With resources, a cell counts interventions that used that kind (an intervention with two kinds counts twice).
    query = (
        f"SELECT {_EXPR[rows]} AS r, {col} AS c, count(DISTINCT i.id) FROM ops.incident i {join} "  # noqa: S608 (constant SQL fragments, values are bound)
        f"WHERE {where} GROUP BY 1, 2"
    )
    result = await session.execute(text(query), params)
    return {(str(r), str(c)): int(n) for r, c, n in result.all()}


def change_pct(now: int, before: int) -> float | None:
    if before == 0:
        return None
    return round((now - before) * 100.0 / before, 1)


async def crosstab(
    session: AsyncSession, rows: str, cols: str, codes: list[int], start: date, end: date
) -> dict[str, Any]:
    now = await _counts(session, rows, cols, codes, start, end)
    before = await _counts(session, rows, cols, codes, _year_before(start), _year_before(end))
    row_keys = sorted({r for r, _ in now} | {r for r, _ in before})
    col_keys = sorted({c for _, c in now} | {c for _, c in before}, key=lambda k: (len(k), k))
    cells = [
        [
            {
                "count": now.get((r, c), 0),
                "previous": before.get((r, c), 0),
                "change_pct": change_pct(now.get((r, c), 0), before.get((r, c), 0)),
            }
            for c in col_keys
        ]
        for r in row_keys
    ]
    totals = []
    for r in row_keys:
        n = sum(v for (k, _), v in now.items() if k == r)
        b = sum(v for (k, _), v in before.items() if k == r)
        totals.append({"count": n, "previous": b, "change_pct": change_pct(n, b)})
    return {
        "rows": rows,
        "cols": cols,
        "from": start,
        "to": end,
        "previous_from": _year_before(start),
        "previous_to": _year_before(end),
        "row_keys": row_keys,
        "col_keys": col_keys,
        "cells": cells,
        "row_totals": totals,
    }


async def findings(
    session: AsyncSession, codes: list[int], start: date, end: date, names: dict[int, str], limit: int = 12
) -> list[dict[str, Any]]:
    """The changes from one year to the next worth a sentence: by nature (category, then classification), nationally
    or for the gouvernorat in scope, then by nature and gouvernorat; the largest first."""
    out: list[dict[str, Any]] = []
    for dim in ("category", "classification"):
        now = await _counts(session, dim, None, codes, start, end)
        before = await _counts(session, dim, None, codes, _year_before(start), _year_before(end))
        for key in {k for k, _ in now} | {k for k, _ in before}:
            n, b = now.get((key, ""), 0), before.get((key, ""), 0)
            out.append({"dimension": dim, "key": key, "gouvernorat_code": None, "count": n, "previous": b})
    if not codes or len(codes) > 1:
        now2 = await _counts(session, "classification", "gouvernorat", codes, start, end)
        before2 = await _counts(session, "classification", "gouvernorat", codes, _year_before(start), _year_before(end))
        for key, g in set(now2) | set(before2):
            n, b = now2.get((key, g), 0), before2.get((key, g), 0)
            out.append(
                {"dimension": "classification", "key": key, "gouvernorat_code": int(g), "count": n, "previous": b}
            )
    kept = []
    seen: set[tuple[str, int | None, int, int]] = set()
    for f in out:
        pct = change_pct(f["count"], f["previous"])
        if pct is None or f["count"] + f["previous"] < MIN_COUNT or abs(pct) < MIN_CHANGE_PCT:
            continue
        # A classification equal to its category (no classification given) says the same thing twice.
        mark = (NATURE_AR.get(f["key"], f["key"]), f["gouvernorat_code"], f["count"], f["previous"])
        if mark in seen:
            continue
        seen.add(mark)
        word = "ارتفاع" if pct > 0 else "انخفاض"
        place = f" في ولاية {names.get(f['gouvernorat_code'], '')}" if f["gouvernorat_code"] else ""
        f["change_pct"] = pct
        f["text_ar"] = (
            f"{word} في عدد {NATURE_AR.get(f['key'], f['key'])}{place} بنسبة {abs(pct):g}% مقارنة بالسنة الفارطة "
            f"({f['count']} مقابل {f['previous']})"
        )
        kept.append(f)
    kept.sort(key=lambda f: -abs(f["change_pct"]) * min(f["count"] + f["previous"], 50))
    return kept[:limit]
