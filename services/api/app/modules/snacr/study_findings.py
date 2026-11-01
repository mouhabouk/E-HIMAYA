"""The statistical board and the technical notes of a SNACR study (Yamen, 2026-11-01): read from the study's own
tables, never from the archive again, so an archived study keeps the reading it had.

* ``classes``: each table (SEC_GLOB, SAP, SR, LCI, SB, DIV) by year, its share of all outings, its change from the
  first year to the last and from one year to the next, and its night share when the day is split;
* ``delegations``: each délégation (its rows under several units joined) with its yearly mean, its rate per 1 000
  inhabitants, its change from the first year to the last and its mean travel time;
* ``notes``: the sentences an analyst would write in the technical note, in Arabic, each with its tone
  (``up``, ``down``, ``warn``, ``info``).

The thresholds are those of the cross-tabulations (analytics.crosstab): a change is told from 15 % on 20 outings."""

import itertools
from typing import Any

MIN_COUNT = 20
MIN_CHANGE_PCT = 15.0
WHITE_WARN_PCT = 10.0
TRAVEL_DROP_WARN_PCT = 5.0
SLOW_TRAVEL_MIN = 10.0
CLASS_AR = {
    "SEC_GLOB": "مجموع الخرجات",
    "SAP": "إسعاف الأشخاص",
    "SR": "النجدة على الطرقات",
    "LCI": "مكافحة الحرائق",
    "SB": "الخرجات البيضاء",
    "DIV": "التدخلات المختلفة",
}


def change_pct(now: float, before: float) -> float | None:
    if before == 0:
        return None
    return round((now - before) / before * 100, 1)


def ltr(text: str) -> str:
    """A signed figure or a time kept left to right inside an Arabic sentence (Unicode isolates)."""
    return f"\u2066{text}\u2069"


def mmss(value: float | None) -> str:
    if value is None:
        return "—"
    total = round(value * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def _year_totals(item: dict[str, Any], years: list[int]) -> dict[str, int | None]:
    out: dict[str, int | None] = {}
    for y in years:
        per = item["counts"].get(str(y))
        out[str(y)] = None if per is None else int(sum(per.values()))
    return out


def _period_totals(item: dict[str, Any], years: list[int], periods: list[str]) -> dict[str, int]:
    out = dict.fromkeys(periods, 0)
    for y in years:
        per = item["counts"].get(str(y))
        if per is not None:
            for p in periods:
                out[p] += int(per.get(p, 0))
    return out


def _travel(item: dict[str, Any]) -> float | None:
    values = [v for v in item["travel"].values() if v is not None]
    return round(sum(values) / len(values), 2) if values else None


def _pct(part: float, whole: float) -> float:
    return round(part / whole * 100, 1) if whole else 0.0


def _classes(tables: list[dict[str, Any]], years: list[int], periods: list[str]) -> list[dict[str, Any]]:
    glob = next((tb for tb in tables if tb["key"] == "SEC_GLOB"), None)
    all_total = glob["total"]["total"] if glob else 0
    out = []
    for tb in tables:
        per_year = _year_totals(tb["total"], years)
        steps = []
        for a, b in itertools.pairwise(years):
            na, nb = per_year[str(a)] or 0, per_year[str(b)] or 0
            steps.append({"from": a, "to": b, "change_pct": change_pct(nb, na)})
        first, last = per_year[str(years[0])] or 0, per_year[str(years[-1])] or 0
        by_period = _period_totals(tb["total"], years, periods)
        out.append(
            {
                "key": tb["key"],
                "label_ar": CLASS_AR.get(tb["key"], tb["key"]),
                "per_year": per_year,
                "total": tb["total"]["total"],
                "share_pct": _pct(tb["total"]["total"], all_total),
                "change_pct": change_pct(last, first) if len(years) > 1 else None,
                "steps": steps,
                "night_pct": _pct(by_period.get("S", 0), sum(by_period.values())) if "S" in periods else None,
                "travel": tb["total"]["travel"],
            }
        )
    return out


def _delegations(glob: dict[str, Any], years: list[int]) -> list[dict[str, Any]]:
    """The délégations of SEC_GLOB, a délégation under two units over the years counted once."""
    joined: dict[tuple[str, str], dict[str, Any]] = {}
    for block in glob["gouvernorats"]:
        for unit in block["units"]:
            for r in unit["rows"]:
                key = (block["gouvernorat"], r["delegation"])
                d = joined.setdefault(
                    key,
                    {
                        "gouvernorat": block["gouvernorat"],
                        "delegation": r["delegation"],
                        "units": [],
                        "population": r["population"],
                        "per_year": dict.fromkeys(map(str, years)),
                        "travel_sum": 0.0,
                        "travel_n": 0,
                    },
                )
                d["units"].append(unit["unit"])
                for y, n in _year_totals(r, years).items():
                    if n is not None:
                        d["per_year"][y] = (d["per_year"][y] or 0) + n
                t = _travel(r)
                if t is not None:
                    d["travel_sum"] += t
                    d["travel_n"] += 1
    out = []
    for d in joined.values():
        seen = [v for v in d["per_year"].values() if v is not None]
        mean = round(sum(seen) / len(seen), 1) if seen else 0.0
        first, last = d["per_year"][str(years[0])], d["per_year"][str(years[-1])]
        pop = d["population"]
        out.append(
            {
                "gouvernorat": d["gouvernorat"],
                "delegation": d["delegation"],
                "units": d["units"],
                "per_year": d["per_year"],
                "mean": mean,
                "population": pop,
                "rate_per_1000": round(mean / pop * 1000, 2) if pop else None,
                "change_pct": (
                    change_pct(last, first)
                    if len(years) > 1 and first is not None and last is not None and first + last >= MIN_COUNT
                    else None
                ),
                "travel": round(d["travel_sum"] / d["travel_n"], 2) if d["travel_n"] else None,
            }
        )
    out.sort(key=lambda d: -d["mean"])
    return out


def _notes(
    classes: list[dict[str, Any]],
    delegations: list[dict[str, Any]],
    years: list[int],
    periods: list[str],
    quality: dict[str, Any],
    travel_max: int,
) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []

    def say(tone: str, text: str) -> None:
        notes.append({"tone": tone, "text_ar": text})

    span = f"{years[0]}–{years[-1]}" if len(years) > 1 else str(years[0])
    glob = next((c for c in classes if c["key"] == "SEC_GLOB"), None)
    if glob is None or glob["total"] == 0:
        say("info", "لا توجد تدخلات في السنوات المختارة.")
        return notes
    say(
        "info",
        f"بلغ مجموع الخرجات {glob['total']} خلال الفترة {span}، أي بمعدل سنوي قدره "
        f"{round(glob['total'] / len(years))} خرجة.",
    )
    if len(years) > 1:
        first, last = glob["per_year"][str(years[0])] or 0, glob["per_year"][str(years[-1])] or 0
        pct = glob["change_pct"]
        if pct is not None:
            word, tone = ("ارتفع", "up") if pct > 0 else ("انخفض", "down") if pct < 0 else ("استقر", "info")
            say(tone, f"{word} عدد الخرجات من {first} سنة {years[0]} إلى {last} سنة {years[-1]} ({ltr(f'{pct:+g}%')}).")
        peak = max(years, key=lambda y: glob["per_year"][str(y)] or 0)
        say("info", f"سجلت سنة {peak} أعلى عدد من الخرجات ({glob['per_year'][str(peak)]}).")
        for s in glob["steps"]:
            if s["change_pct"] is not None and abs(s["change_pct"]) >= MIN_CHANGE_PCT:
                word = "قفزة" if s["change_pct"] > 0 else "تراجع"
                say(
                    "up" if s["change_pct"] > 0 else "down",
                    f"{word} في الخرجات بين {s['from']} و{s['to']} بنسبة {abs(s['change_pct']):g}%.",
                )
    ranked = sorted((c for c in classes if c["key"] not in ("SEC_GLOB", "SB")), key=lambda c: -c["total"])
    if ranked:
        parts = "، ثم ".join(f"{c['label_ar']} ({c['key']}) بنسبة {c['share_pct']:g}%" for c in ranked[:3])
        say("info", f"يتصدر التدخلات {parts} من مجموع الخرجات.")
    white = next((c for c in classes if c["key"] == "SB"), None)
    if white is not None and white["total"]:
        tone = "warn" if white["share_pct"] >= WHITE_WARN_PCT else "info"
        extra = "، وهي نسبة مرتفعة تستوجب مراجعة التثبت من البلاغات قبل الخروج" if tone == "warn" else ""
        say(tone, f"الخرجات البيضاء {white['total']} أي {white['share_pct']:g}% من الخرجات{extra}.")
    for c in classes:
        if c["key"] in ("SEC_GLOB",) or c["change_pct"] is None or abs(c["change_pct"]) < MIN_CHANGE_PCT:
            continue
        first, last = c["per_year"][str(years[0])] or 0, c["per_year"][str(years[-1])] or 0
        if first + last < MIN_COUNT:
            continue
        word, tone = ("ارتفاع", "up") if c["change_pct"] > 0 else ("انخفاض", "down")
        say(
            tone,
            f"{word} في {c['label_ar']} ({c['key']}) بنسبة {abs(c['change_pct']):g}% بين {years[0]} و{years[-1]} "
            f"({first} مقابل {last}).",
        )
    if "S" in periods and glob["night_pct"] is not None:
        say("info", f"تقع {glob['night_pct']:g}% من الخرجات ليلا (من 18:01 إلى 05:59).")
        nightly = [c for c in classes if c["key"] != "SEC_GLOB" and c["total"] >= MIN_COUNT and c["night_pct"]]
        if nightly:
            top = max(nightly, key=lambda c: c["night_pct"])
            if top["night_pct"] >= (glob["night_pct"] or 0) + 10:
                say(
                    "warn",
                    f"{top['label_ar']} ({top['key']}) ليلية أكثر من غيرها: {top['night_pct']:g}% منها ليلا، "
                    "ما يستدعي تدعيم المداومة الليلية لهذا الصنف.",
                )
        tj, ts = glob["travel"].get("J"), glob["travel"].get("S")
        if tj is not None and ts is not None:
            say("info", f"معدل زمن الانطلاق {ltr(mmss(tj))} نهارا و{ltr(mmss(ts))} ليلا (دقيقة:ثانية).")
            if ts - tj >= 1:
                say("warn", f"زمن الانطلاق ليلا أطول بـ{ltr(mmss(ts - tj))} من النهار.")
    else:
        t = glob["travel"].get("T")
        if t is not None:
            say("info", f"معدل زمن الانطلاق {ltr(mmss(t))} (دقيقة:ثانية).")
    rated = [d for d in delegations if d["rate_per_1000"] is not None]
    if rated:
        top = max(rated, key=lambda d: d["rate_per_1000"])
        say(
            "info",
            f"أعلى نسبة خرجات للسكان في معتمدية {top['delegation']}: {top['rate_per_1000']:g} خرجة لكل ألف ساكن سنويا.",
        )
    moving = [d for d in delegations if d["change_pct"] is not None and abs(d["change_pct"]) >= MIN_CHANGE_PCT]
    ups = sorted((d for d in moving if d["change_pct"] > 0), key=lambda d: -d["change_pct"])[:3]
    downs = sorted((d for d in moving if d["change_pct"] < 0), key=lambda d: d["change_pct"])[:3]
    if ups:
        say(
            "up",
            "أكبر ارتفاع في المعتمديات: "
            + "، ".join(f"{d['delegation']} ({ltr(f'{d["change_pct"]:+g}%')})" for d in ups),
        )
    if downs:
        say(
            "down",
            "أكبر انخفاض في المعتمديات: "
            + "، ".join(f"{d['delegation']} ({ltr(f'{d["change_pct"]:+g}%')})" for d in downs),
        )
    slow = sorted((d for d in delegations if (d["travel"] or 0) >= SLOW_TRAVEL_MIN), key=lambda d: -d["travel"])[:3]
    if slow:
        say(
            "warn",
            "أطول زمن انطلاق: " + "، ".join(f"{d['delegation']} ({ltr(mmss(d['travel']))})" for d in slow) + "، وهي "
            "معتمديات تستحق دراسة موقع الوحدة أو إحداث نقطة متقدمة.",
        )
    moved = sorted({d["delegation"] for d in delegations if len(d["units"]) > 1})
    if moved:
        say("info", "تغيرت الوحدة المغطية خلال الفترة في: " + "، ".join(moved) + " (الخانات «*» في الجداول).")
    rows = int(quality.get("rows", 0) or 0)
    dropped = int(quality.get("travel_negative", 0) or 0) + int(quality.get("travel_over", 0) or 0)
    missing = int(quality.get("travel_missing", 0) or 0)
    if rows and _pct(dropped + missing, rows) >= TRAVEL_DROP_WARN_PCT:
        say(
            "warn",
            f"{_pct(dropped + missing, rows):g}% من الخرجات بلا زمن انطلاق صالح ({missing} فارغ، {dropped} سالب أو "
            f"يفوق {travel_max} دقيقة): يستحسن تحسين تسجيل أوقات الانطلاق والوصول.",
        )
    return notes


def read(tables: dict[str, Any], quality: dict[str, Any], travel_max: int) -> dict[str, Any]:
    years: list[int] = tables.get("years") or []
    periods: list[str] = tables.get("periods") or []
    found = tables.get("tables") or []
    if not years or not found:
        return {"classes": [], "delegations": [], "notes": []}
    classes = _classes(found, years, periods)
    glob = next((tb for tb in found if tb["key"] == "SEC_GLOB"), None)
    delegations = _delegations(glob, years) if glob else []
    return {
        "classes": classes,
        "delegations": delegations,
        "notes": _notes(classes, delegations, years, periods, quality, travel_max),
    }
