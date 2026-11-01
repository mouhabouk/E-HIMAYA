"""SNACR studies in the Office's format (Yamen, 2026-11-01; methodology note e-Himaya_Methodologie_SNACR).

Three stages: the cleaning happens on import (domain.clean), the processing derives the class (SAP, SR, LCI, DIV, SB),
the period (day J 06:00–18:00, night S 18:01–05:59, or the whole day) and the travel time (arrival − departure), and
the analysis builds the six tables of the Office's file: SEC_GLOB (every outing) then one table per class, a row per
délégation under the unit that covered it that year, the count per year and period, the yearly mean, the mean travel
time. A study is frozen with its settings; launching the next one of the same scope archives it, and any study can be
exported again (PDF, Excel).
"""

from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.geo.models import Delegation, Gouvernorat
from app.modules.snacr import domain
from app.modules.snacr.models import Dataset, Study

_COUNTS = text(
    """
SELECT i.gouvernorat_code AS g, i.delegation_id AS d,
    CASE WHEN i.delegation_id IS NULL THEN i.delegation_raw END AS raw,
    i.year AS y, i.unit_raw AS u,
    CASE WHEN i.intervened IS FALSE THEN 'SB' WHEN i.family = 'medical' THEN 'SAP' WHEN i.family = 'road' THEN 'SR'
         WHEN i.family = 'fire' THEN 'LCI' ELSE 'DIV' END AS c,
    CASE WHEN EXTRACT(HOUR FROM x.l) * 60 + EXTRACT(MINUTE FROM x.l) BETWEEN :day_start AND :day_end THEN 'J'
         ELSE 'S' END AS p,
    count(*) AS n,
    count(*) FILTER (WHERE x.t BETWEEN 0 AND :travel_max) AS tn,
    coalesce(sum(x.t) FILTER (WHERE x.t BETWEEN 0 AND :travel_max), 0) AS ts,
    count(*) FILTER (WHERE x.t IS NULL) AS t_missing,
    count(*) FILTER (WHERE x.t < 0) AS t_negative,
    count(*) FILTER (WHERE x.t > :travel_max) AS t_over
FROM snacr.intervention i
CROSS JOIN LATERAL (
    SELECT i.called_at AT TIME ZONE 'Africa/Tunis' AS l,
           EXTRACT(EPOCH FROM (i.arrived_at - i.departed_at)) / 60 AS t
) x
WHERE i.year = ANY(CAST(:years AS smallint[]))
  AND (CAST(:g AS smallint) IS NULL OR i.gouvernorat_code = CAST(:g AS smallint))
GROUP BY 1, 2, 3, 4, 5, 6, 7
"""
)


def _zero(years: list[int], periods: list[str]) -> dict[str, Any]:
    return {
        "n": {str(y): {p: 0 for p in periods} for y in years},
        "ts": dict.fromkeys(periods, 0.0),
        "tn": dict.fromkeys(periods, 0),
    }


def _finish(acc: dict[str, Any], years: list[int], periods: list[str], active: set[int] | None) -> dict[str, Any]:
    """Counts per year (None for a year the row did not exist under this unit), the yearly mean over the years shown,
    and the mean travel time in minutes."""
    shown = [y for y in years if active is None or y in active]
    counts = {str(y): (acc["n"][str(y)] if (active is None or y in active) else None) for y in years}
    mean = {p: (round(sum(acc["n"][str(y)][p] for y in shown) / len(shown), 2) if shown else None) for p in periods}
    travel = {p: (round(acc["ts"][p] / acc["tn"][p], 2) if acc["tn"][p] else None) for p in periods}
    total = sum(acc["n"][str(y)][p] for y in shown for p in periods)
    return {"counts": counts, "mean": mean, "travel": travel, "total": total}


def _add(into: dict[str, Any], src: dict[str, Any], periods: list[str]) -> None:
    for y, per in src["n"].items():
        for p in periods:
            into["n"][y][p] += per[p]
    for p in periods:
        into["ts"][p] += src["ts"][p]
        into["tn"][p] += src["tn"][p]


async def compute(
    session: AsyncSession, gouvernorat: int | None, years: list[int], split: bool, travel_max: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The six tables and the quality report of a study (not stored)."""
    periods = ["J", "S"] if split else ["T"]
    result = await session.execute(
        _COUNTS,
        {
            "years": years,
            "g": gouvernorat,
            "travel_max": travel_max,
            "day_start": domain.DAY_START_MIN,
            "day_end": domain.DAY_END_MIN,
        },
    )
    lines = result.all()
    g_names = dict((await session.execute(select(Gouvernorat.code, Gouvernorat.name_ar))).all())
    d_rows = (
        await session.execute(
            select(Delegation.id, Delegation.name_ar, Delegation.area_km2, Delegation.population_2024)
        )
    ).all()
    d_info = {i: (n, a, pop) for i, n, a, pop in d_rows}

    # The unit of each délégation and year: the one that made most of its outings (the coverage of that year).
    unit_votes: dict[tuple[int, Any, int], Counter[str]] = defaultdict(Counter)
    spellings: dict[str, Counter[str]] = defaultdict(Counter)
    quality = Counter[str]()
    for line in lines:
        dkey = line.d if line.d is not None else f"raw:{line.raw}"
        ukey = domain.unit_key(line.u)
        unit_votes[(line.g, dkey, line.y)][ukey] += line.n
        if line.u:
            spellings[ukey][line.u] += line.n
        quality["rows"] += line.n
        quality["white"] += line.n if line.c == "SB" else 0
        quality["unit_missing"] += line.n if not line.u else 0
        quality["delegation_unmatched"] += line.n if line.d is None else 0
        quality["travel_kept"] += line.tn
        quality["travel_missing"] += line.t_missing
        quality["travel_negative"] += line.t_negative
        quality["travel_over"] += line.t_over
    unit_of = {k: v.most_common(1)[0][0] for k, v in unit_votes.items()}
    # A year without any outing to a délégation keeps the unit of the nearest year: it shows 0, not "*".
    places_seen = {(g, dkey) for g, dkey, _ in unit_votes}
    for g, dkey in places_seen:
        had = sorted(y for gg, dd, y in unit_votes if (gg, dd) == (g, dkey))
        for y in years:
            if (g, dkey, y) not in unit_of:
                nearest = min(had, key=lambda h: (abs(h - y), h))
                unit_of[(g, dkey, y)] = unit_of[(g, dkey, nearest)]

    def d_name(dkey: Any) -> str:
        return d_info.get(dkey, ("",))[0] if isinstance(dkey, int) else str(dkey)[4:]

    def u_name(ukey: str, dkey: Any) -> str:
        return spellings[ukey].most_common(1)[0][0] if ukey and spellings.get(ukey) else d_name(dkey)

    # acc[table][(g, unit, dkey)] and the years each row is active
    acc: dict[str, dict[tuple[int, str, Any], dict[str, Any]]] = {t: {} for t in domain.TABLES}
    active: dict[tuple[int, str, Any], set[int]] = defaultdict(set)
    for line in lines:
        dkey = line.d if line.d is not None else f"raw:{line.raw}"
        ukey = unit_of[(line.g, dkey, line.y)]
        key = (line.g, ukey, dkey)
        active[key].add(line.y)
        p = line.p if split else "T"
        for table in ("SEC_GLOB", line.c):
            row = acc[table].setdefault(key, _zero(years, periods))
            row["n"][str(line.y)][p] += line.n
            row["ts"][p] += float(line.ts)
            row["tn"][p] += line.tn

    for (g, dkey, y), ukey in unit_of.items():
        active[(g, ukey, dkey)].add(y)
    keys = sorted(active, key=lambda k: (k[0], u_name(k[1], k[2]), d_name(k[2])))
    tables: list[dict[str, Any]] = []
    for table in domain.TABLES:
        grand = _zero(years, periods)
        blocks: list[dict[str, Any]] = []
        for g in sorted({k[0] for k in keys}):
            g_acc = _zero(years, periods)
            units: list[dict[str, Any]] = []
            for ukey in dict.fromkeys(k[1] for k in keys if k[0] == g):
                u_acc = _zero(years, periods)
                u_rows: list[dict[str, Any]] = []
                area = 0.0
                unit_keys = [k for k in keys if k[0] == g and k[1] == ukey]
                for key in unit_keys:
                    row = acc[table].get(key, _zero(years, periods))
                    name, a, pop = d_info.get(key[2], (d_name(key[2]), None, None))
                    area += a or 0
                    u_rows.append(
                        {
                            "delegation_id": key[2] if isinstance(key[2], int) else None,
                            "delegation": name,
                            "area_km2": round(a, 2) if a else None,
                            "population": pop,
                            "density": round(pop / a, 1) if pop and a else None,
                            **_finish(row, years, periods, active[key]),
                        }
                    )
                    _add(u_acc, row, periods)
                units.append(
                    {
                        "unit": u_name(ukey, unit_keys[0][2]),
                        "rows": u_rows,
                        "subtotal": {
                            **_finish(u_acc, years, periods, None),
                            "delegations": len(u_rows),
                            "area_km2": round(area, 2) or None,
                        },
                    }
                )
                _add(g_acc, u_acc, periods)
            blocks.append(
                {
                    "gouvernorat_code": g,
                    "gouvernorat": g_names.get(g, ""),
                    "units": units,
                    "total": _finish(g_acc, years, periods, None),
                }
            )
            _add(grand, g_acc, periods)
        tables.append(
            {
                "key": table,
                "label_ar": "كل التدخلات" if table == "SEC_GLOB" else domain.CLASS_AR[table],
                "gouvernorats": blocks,
                "total": _finish(grand, years, periods, None),
            }
        )
    return {"years": years, "periods": periods, "tables": tables}, dict(quality)


async def launch(
    session: AsyncSession,
    gouvernorat: int | None,
    years: list[int],
    split: bool,
    travel_max: int,
    actor: str,
    actor_name: str | None,
) -> Study:
    """Compute and freeze a new study; the current study of the same scope is archived, never rewritten."""
    tables, quality = await compute(session, gouvernorat, years, split, travel_max)
    datasets = (await session.scalars(select(Dataset).where(Dataset.year.in_(years)))).all()
    quality["datasets"] = [
        {"year": d.year, "source": d.source, "simulated": d.simulated, "file_name": d.file_name, "rows": d.rows}
        for d in sorted(datasets, key=lambda d: d.year)
    ]
    scope = func.coalesce(Study.gouvernorat_code, 0) == (gouvernorat or 0)
    number = int(await session.scalar(select(func.coalesce(func.max(Study.number), 0)).where(scope)) or 0) + 1
    await session.execute(
        update(Study).where(scope, Study.status == "current").values(status="archived", archived_at=datetime.now(UTC))
    )
    study = Study(
        number=number,
        gouvernorat_code=gouvernorat,
        years=years,
        split=split,
        travel_max=travel_max,
        status="current",
        simulated=any(d.simulated for d in datasets),
        tables=tables,
        quality=quality,
        created_by=actor,
        created_by_name=actor_name,
    )
    session.add(study)
    await session.flush()
    return study
