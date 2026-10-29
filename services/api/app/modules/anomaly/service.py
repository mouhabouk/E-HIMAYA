# ruff: noqa: E501
"""Indicators out of their habit (AI4, docs/phase-l/design-l5.md §4.4).

Plain statistics, no language model. Each indicator of a gouvernorat or a delegation over the last seven days is
compared with its usual series: the same seven days of the past three years (the season, a week either side) when
the system holds enough of them, else the eight weeks before. It is out of its habit when it lies far from the mean
of that series in standard deviations, and far enough in plain figures not to call attention for little:

* the number of reports of a gouvernorat, more or fewer than usual;
* the arrival time on scene in a delegation, longer than usual;
* the completion rate of the approved programmes of a gouvernorat, lower than usual.

What is found is kept once per indicator, place and day (``ai.anomaly``), audited once, and shown calmly in the
situation now and the alert centre with its explanation. Nothing reaches a citizen.
"""

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import as_system
from app.modules.ai.models import Anomaly
from app.modules.analytics.domain import TUNIS_TZ
from app.modules.audit import service as audit
from app.modules.geo.models import Delegation, Gouvernorat

WEEK = 604_800  # seconds
YEARS = 3
RECENT = range(1, 9)
SEASON = sorted({52 * y + d for y in range(1, YEARS + 1) for d in (-1, 0, 1)})
SEASON_MIN_POINTS = 6
MIN_POINTS = 4
SYSTEM = "system:anomalies"


@dataclass(frozen=True, slots=True)
class Rule:
    # Standard deviations from the mean, the least plain gap, a floor on the deviation (a flat series), the least
    # sample this week, and the direction that matters (1 higher, -1 lower, 0 both).
    z: float
    gap: float
    floor: float
    min_n: int
    direction: int


RULES: dict[str, Rule] = {
    "reports": Rule(z=3.0, gap=5, floor=2.0, min_n=0, direction=0),
    "arrival": Rule(z=2.5, gap=3, floor=3.0, min_n=5, direction=1),
    "completion": Rule(z=2.5, gap=0.10, floor=0.08, min_n=5, direction=-1),
}

_T: dict[str, dict[str, str]] = {
    "ar": {
        "reports": "عدد البلاغات في ولاية {place} خلال الأيام السبعة الأخيرة {value}، والمعتاد {mean} ± {std} ({baseline}).",
        "arrival": "زمن الوصول في معتمدية {place} خلال الأيام السبعة الأخيرة {value} دقيقة، والمعتاد {mean} ± {std} ({baseline}).",
        "completion": "نسبة إنجاز البرمجة في ولاية {place} خلال الأيام السبعة الأخيرة {value}، والمعتاد {mean} ± {std} ({baseline}).",
        "season": "في الأيام نفسها من السنوات الماضية",
        "recent": "في الأسابيع الثمانية السابقة",
    },
    "fr": {
        "reports": "Signalements dans le gouvernorat de {place} ces sept derniers jours : {value}, l'habitude est de {mean} ± {std} ({baseline}).",
        "arrival": "Délai d'arrivée dans la délégation de {place} ces sept derniers jours : {value} min, l'habitude est de {mean} ± {std} ({baseline}).",
        "completion": "Taux de réalisation du programme du gouvernorat de {place} ces sept derniers jours : {value}, l'habitude est de {mean} ± {std} ({baseline}).",
        "season": "aux mêmes dates les années passées",
        "recent": "les huit semaines précédentes",
    },
    "en": {
        "reports": "Reports in the gouvernorat of {place} over the last seven days: {value}, usually {mean} ± {std} ({baseline}).",
        "arrival": "Arrival time in the delegation of {place} over the last seven days: {value} min, usually {mean} ± {std} ({baseline}).",
        "completion": "Programme completion in the gouvernorat of {place} over the last seven days: {value}, usually {mean} ± {std} ({baseline}).",
        "season": "on the same days of past years",
        "recent": "over the eight weeks before",
    },
}


@dataclass(frozen=True, slots=True)
class Found:
    indicator: str
    unit_key: str
    gouvernorat_code: int
    delegation_id: int | None
    value: float
    mean: float
    std: float
    z: float
    baseline: str
    points: int
    n: int


def judge(
    indicator: str,
    series: dict[int, tuple[float, int]],
    usable: set[int],
) -> tuple[float, float, float, str, int] | None:
    """Mean, deviation, z, baseline and points of this week's figure against its series, or None when the series is
    too short. ``series`` maps a week back (0 = the last seven days) to its value and sample; ``usable`` are the weeks
    back the system already covered (a week before the first record is no zero)."""
    if 0 not in series:
        return None
    season = [series[b][0] for b in SEASON if b in usable and b in series]
    if len(season) >= SEASON_MIN_POINTS:
        points, baseline = season, "season"
    else:
        points, baseline = [series[b][0] for b in RECENT if b in usable and b in series], "recent"
    if len(points) < MIN_POINTS:
        return None
    mean = sum(points) / len(points)
    std = math.sqrt(sum((x - mean) ** 2 for x in points) / (len(points) - 1))
    z = (series[0][0] - mean) / max(std, RULES[indicator].floor)
    return mean, std, z, baseline, len(points)


def out_of_habit(indicator: str, value: float, n: int, mean: float, z: float) -> bool:
    rule = RULES[indicator]
    gap = value - mean
    if n < rule.min_n or abs(gap) < rule.gap or abs(z) < rule.z:
        return False
    return rule.direction == 0 or (gap > 0) == (rule.direction > 0)


def _scope(codes: list[int], column: str) -> str:
    return f" AND {column} = ANY(CAST(:codes AS smallint[]))" if codes else ""


async def _first(session: AsyncSession, sql: str) -> datetime | None:
    first = (await session.execute(text(sql))).scalar()
    if first is None:
        return None
    if isinstance(first, date) and not isinstance(first, datetime):
        return datetime.combine(first, datetime.min.time(), TUNIS_TZ)
    return first  # type: ignore[no-any-return]


def _usable(now: datetime, first: datetime | None) -> set[int]:
    if first is None:
        return set()
    covered = int((now - first).total_seconds() // WEEK)
    return set(range(covered))  # week k is wholly after the first record when k + 1 <= covered


async def _reports(session: AsyncSession, now: datetime, codes: list[int]) -> list[Found]:
    usable = _usable(now, await _first(session, "SELECT min(received_at) FROM reports.report"))
    if not usable:
        return []
    rows = await session.execute(
        text(
            "SELECT r.gouvernorat_code, CAST(floor(extract(epoch FROM CAST(:now AS timestamptz) - r.received_at) / 604800) AS int) AS b, count(*) "  # noqa: S608 (constant SQL fragments, values are bound)
            "FROM reports.report r WHERE r.received_at < :now AND r.received_at >= :since AND r.gouvernorat_code IS NOT NULL"
            f"{_scope(codes, 'r.gouvernorat_code')} GROUP BY 1, 2"
        ),
        {"now": now, "since": now - timedelta(weeks=max(SEASON) + 1), "codes": codes},
    )
    series: dict[int, dict[int, tuple[float, int]]] = defaultdict(dict)
    for g, b, count in rows:
        series[g][b] = (float(count), int(count))
    found = []
    for g, s in series.items():
        # A week the system covered without a report is a zero, not a gap.
        full = {b: s.get(b, (0.0, 0)) for b in usable | {0}}
        judged = judge("reports", full, usable)
        if judged and out_of_habit("reports", full[0][0], full[0][1], judged[0], judged[2]):
            found.append(Found("reports", f"g:{g}", g, None, full[0][0], *judged, n=full[0][1]))
    return found


async def _arrival(session: AsyncSession, now: datetime, codes: list[int]) -> list[Found]:
    usable = _usable(now, await _first(session, "SELECT min(on_scene_at) FROM ops.assignment"))
    if not usable:
        return []
    rows = await session.execute(
        text(
            "WITH t AS (SELECT r.gouvernorat_code AS g, r.delegation_id AS d, r.received_at, "  # noqa: S608 (constant SQL fragments, values are bound)
            "(SELECT min(a.on_scene_at) FROM ops.assignment a WHERE a.incident_id = r.incident_id "
            "AND a.on_scene_at >= r.received_at) AS on_scene FROM reports.report r "
            "WHERE r.received_at < :now AND r.received_at >= :since AND r.incident_id IS NOT NULL "
            f"AND r.delegation_id IS NOT NULL AND r.gouvernorat_code IS NOT NULL{_scope(codes, 'r.gouvernorat_code')}) "
            "SELECT g, d, CAST(floor(extract(epoch FROM CAST(:now AS timestamptz) - received_at) / 604800) AS int), "
            "avg(extract(epoch FROM on_scene - received_at)) / 60, count(*) FROM t WHERE on_scene IS NOT NULL GROUP BY 1, 2, 3"
        ),
        {"now": now, "since": now - timedelta(weeks=max(SEASON) + 1), "codes": codes},
    )
    series: dict[tuple[int, int], dict[int, tuple[float, int]]] = defaultdict(dict)
    for g, d, b, minutes, n in rows:
        # A week with fewer than three arrivals says little of the habit.
        if b == 0 or n >= 3:
            series[(g, d)][b] = (float(minutes), int(n))
    found = []
    for (g, d), s in series.items():
        judged = judge("arrival", s, usable)
        if judged and out_of_habit("arrival", s[0][0], s[0][1], judged[0], judged[2]):
            found.append(Found("arrival", f"d:{d}", g, d, round(s[0][0], 1), *judged, n=s[0][1]))
    return found


async def _completion(session: AsyncSession, today: date, codes: list[int]) -> list[Found]:
    first = await _first(
        session,
        "SELECT min(i.on_date) FROM sched.item i JOIN sched.period p ON p.id = i.period_id WHERE p.status = 'approved'",
    )
    if first is None:
        return []
    covered = ((today - first.date()).days + 1) // 7
    usable = set(range(covered))
    rows = await session.execute(
        text(
            "SELECT i.gouvernorat_code, (CAST(:today AS date) - i.on_date) / 7 AS b, "  # noqa: S608 (constant SQL fragments, values are bound)
            "count(*) FILTER (WHERE i.status NOT IN ('refused', 'cancelled')), "
            "count(*) FILTER (WHERE i.status = 'done' OR (i.status = 'planned' AND NOT i.status_manual "
            "AND i.starts_at IS NOT NULL AND i.on_date < CAST(:today AS date))) "
            "FROM sched.item i JOIN sched.period p ON p.id = i.period_id "
            "WHERE p.status = 'approved' AND i.on_date <= CAST(:today AS date) AND i.on_date > CAST(:today AS date) - :days"
            f"{_scope(codes, 'i.gouvernorat_code')} GROUP BY 1, 2"
        ),
        {"today": today, "days": 7 * (max(SEASON) + 1), "codes": codes},
    )
    series: dict[int, dict[int, tuple[float, int]]] = defaultdict(dict)
    for g, b, due, done in rows:
        if due >= RULES["completion"].min_n:
            series[g][b] = (done / due, int(due))
    found = []
    for g, s in series.items():
        judged = judge("completion", s, usable)
        if judged and out_of_habit("completion", s[0][0], s[0][1], judged[0], judged[2]):
            found.append(Found("completion", f"g:{g}", g, None, round(s[0][0], 3), *judged, n=s[0][1]))
    return found


async def detect(session: AsyncSession, now: datetime | None = None, codes: list[int] | None = None) -> list[Anomaly]:
    """Finds the indicators out of their habit in the scope (``codes``, [] = the whole country), keeps the new ones
    once (audited) and returns those of the day. Runs with the system scope: only figures leave it, no person."""
    now = now or datetime.now(UTC)
    codes = codes or []
    today = now.astimezone(TUNIS_TZ).date()
    async with as_system(session):
        found = [
            *await _reports(session, now, codes),
            *await _arrival(session, now, codes),
            *await _completion(session, today, codes),
        ]
        for f in found:
            raised = await session.scalar(
                insert(Anomaly)
                .values(
                    indicator=f.indicator,
                    unit_key=f.unit_key,
                    gouvernorat_code=f.gouvernorat_code,
                    delegation_id=f.delegation_id,
                    day=today,
                    value=f.value,
                    mean=round(f.mean, 3),
                    std=round(f.std, 3),
                    z=round(f.z, 2),
                    baseline=f.baseline,
                    points=f.points,
                    n=f.n,
                    raised_at=now,
                )
                .on_conflict_do_nothing(constraint="uq_anomaly")
                .returning(Anomaly.id)
            )
            if raised is not None:
                await audit.record(
                    session,
                    actor=SYSTEM,
                    action="ai.anomaly_raised",
                    target=f"{f.indicator}:{f.unit_key}",
                    details={
                        "value": f.value,
                        "mean": round(f.mean, 3),
                        "std": round(f.std, 3),
                        "z": round(f.z, 2),
                        "baseline": f.baseline,
                    },
                    gouvernorats=[f.gouvernorat_code],
                )
        query = select(Anomaly).where(Anomaly.day == today)
        if codes:
            query = query.where(Anomaly.gouvernorat_code.in_(codes))
        rows = list(
            await session.scalars(query.order_by(Anomaly.gouvernorat_code, Anomaly.indicator, Anomaly.unit_key))
        )
    return rows


def _figure(indicator: str, x: float) -> str:
    return f"{round(x * 100)} %" if indicator == "completion" else str(round(x))


async def explain(session: AsyncSession, rows: list[Anomaly], lang: str) -> list[dict[str, Any]]:
    """Each anomaly with the names of its place and its sentence in the reader's language."""
    t = _T.get(lang, _T["ar"])
    g_names = {
        g.code: (g.name_ar if lang == "ar" else g.name_en if lang == "en" else g.name_fr)
        for g in await session.scalars(select(Gouvernorat))
    }
    ids = {r.delegation_id for r in rows if r.delegation_id}
    d_names = (
        {
            d.id: (d.name_ar if lang == "ar" else d.name_fr)
            for d in await session.scalars(select(Delegation).where(Delegation.id.in_(ids)))
        }
        if ids
        else {}
    )
    out = []
    for r in rows:
        place = d_names.get(r.delegation_id, "—") if r.delegation_id else g_names.get(r.gouvernorat_code, "—")
        out.append(
            {
                "id": r.id,
                "indicator": r.indicator,
                "gouvernorat_code": r.gouvernorat_code,
                "gouvernorat_name": g_names.get(r.gouvernorat_code),
                "delegation_id": r.delegation_id,
                "delegation_name": d_names.get(r.delegation_id) if r.delegation_id else None,
                "day": r.day,
                "value": r.value,
                "mean": r.mean,
                "std": r.std,
                "z": r.z,
                "baseline": r.baseline,
                "points": r.points,
                "n": r.n,
                "higher": r.value > r.mean,
                "text": t[r.indicator].format(
                    place=place,
                    value=_figure(r.indicator, r.value),
                    mean=_figure(r.indicator, r.mean),
                    std=_figure(r.indicator, r.std),
                    baseline=t[r.baseline],
                ),
                "raised_at": r.raised_at,
            }
        )
    return out
