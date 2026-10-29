# ruff: noqa: E501
"""Suggested activities for a programme (AI3, docs/phase-l/design-l5.md §4.3).

A plain statistical engine, no language model: every suggestion says the figures it rests on, and the room accepts
it (it becomes an activity of the programme, approved like any other) or sets it aside with a reason. Nothing is
added by itself (AI-01). Four sources, read for the gouvernorat of the programme and the days still ahead in it:

1. the weather forecast of its grid points: high fire danger on a day calls a forest watch patrol, heavy rain a
   readiness check of the flood equipment;
2. its beaches in red on a day call a reinforced beach watch;
3. the season: the incidents of the same days in the past three years, by category, against their yearly average;
4. a rise: the incidents of the last 14 days against the 8 weeks before.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.coastal.models import BeachDay
from app.modules.geo.models import LayerFeature
from app.modules.ops.models import Incident
from app.modules.schedule import domain
from app.modules.weather.models import GridPoint, Observation

Lang = str
# Fire danger classes that call a patrol, and their order.
DANGER = ("low", "moderate", "high", "very_high", "extreme")
PATROL_FROM = "high"
RAIN = ("none", "watch", "warning")
# The categories the season and the rise look at, and the activity each suggests.
SEASON_ACTIVITY = {
    "fire": "prevention_visit",
    "flood": "readiness_check",
    "drowning": "awareness",
    "traffic_accident": "awareness",
}
YEARS = 3
# The season: at least this many incidents on the same days of the past years, at this multiple of the yearly rate.
SEASON_MIN = 3
SEASON_RATIO = 1.5
# The rise: at least this many incidents in the last 14 days, at this multiple of the 8 weeks before.
RECENT_DAYS = 14
BEFORE_DAYS = 56
RISE_MIN = 3
RISE_RATIO = 2.0
# A month would otherwise list a patrol a day.
MAX_PER_SOURCE = 7
MAX_SUGGESTIONS = 12

_T: dict[str, dict[str, str]] = {
    "ar": {
        "fire_patrol": "دورية مراقبة الغابات: خطر حرائق {level}",
        "fire_patrol.why": "توقع خطر الحرائق {level} يوم {day} في {points} من {total} نقاط الطقس بالولاية.",
        "flood_readiness": "تفقد جاهزية معدات الفيضانات قبل أمطار غزيرة",
        "flood_readiness.why": "توقع أمطار غزيرة ({level}) يوم {day} في {points} من {total} نقاط الطقس بالولاية.",
        "beach_watch": "تعزيز المراقبة بالشواطئ: {beaches} شاطئ في الأحمر",
        "beach_watch.why": "خطر الغرق أحمر يوم {day} في {beaches} شاطئ بالولاية.",
        "season.prevention_visit": "زيارات وقائية: موسم {category}",
        "season.readiness_check": "تفقد الجاهزية: موسم {category}",
        "season.awareness": "حملة توعية: موسم {category}",
        "season.why": "{count} تدخلا ({category}) في نفس الأيام خلال السنوات الثلاث الماضية، أي {ratio} مرة المعدل السنوي.",
        "rise": "تفقد الجاهزية: ارتفاع تدخلات {category}",
        "rise.why": "{recent} تدخلا ({category}) في آخر 14 يوما مقابل {before} في الأسابيع الثمانية السابقة.",
        "level.high": "مرتفع",
        "level.very_high": "مرتفع جدا",
        "level.extreme": "شديد",
        "level.watch": "يقظة",
        "level.warning": "إنذار",
        "cat.fire": "الحرائق",
        "cat.flood": "الفيضانات",
        "cat.drowning": "الغرق",
        "cat.traffic_accident": "حوادث المرور",
        "sim": "معطيات محاكاة",
    },
    "fr": {
        "fire_patrol": "Patrouille de surveillance des forêts : danger d'incendie {level}",
        "fire_patrol.why": "Danger d'incendie {level} prévu le {day} sur {points} des {total} points météo du gouvernorat.",
        "flood_readiness": "Vérifier le matériel d'inondation avant de fortes pluies",
        "flood_readiness.why": "Fortes pluies prévues ({level}) le {day} sur {points} des {total} points météo du gouvernorat.",
        "beach_watch": "Renforcer la surveillance des plages : {beaches} plage(s) en rouge",
        "beach_watch.why": "Risque de noyade rouge le {day} sur {beaches} plage(s) du gouvernorat.",
        "season.prevention_visit": "Visites de prévention : saison {category}",
        "season.readiness_check": "Contrôle de disponibilité : saison {category}",
        "season.awareness": "Campagne de sensibilisation : saison {category}",
        "season.why": "{count} interventions ({category}) aux mêmes dates ces trois dernières années, soit {ratio} fois la moyenne annuelle.",
        "rise": "Contrôle de disponibilité : hausse {category}",
        "rise.why": "{recent} interventions ({category}) ces 14 derniers jours contre {before} les 8 semaines précédentes.",
        "level.high": "élevé",
        "level.very_high": "très élevé",
        "level.extreme": "extrême",
        "level.watch": "vigilance",
        "level.warning": "alerte",
        "cat.fire": "des incendies",
        "cat.flood": "des inondations",
        "cat.drowning": "des noyades",
        "cat.traffic_accident": "des accidents de la route",
        "sim": "données simulées",
    },
    "en": {
        "fire_patrol": "Forest watch patrol: {level} fire danger",
        "fire_patrol.why": "{level} fire danger forecast on {day} at {points} of the {total} weather points of the gouvernorat.",
        "flood_readiness": "Check the flood equipment before heavy rain",
        "flood_readiness.why": "Heavy rain forecast ({level}) on {day} at {points} of the {total} weather points of the gouvernorat.",
        "beach_watch": "Reinforce the beach watch: {beaches} beach(es) in red",
        "beach_watch.why": "Red drowning risk on {day} at {beaches} beach(es) of the gouvernorat.",
        "season.prevention_visit": "Prevention visits: {category} season",
        "season.readiness_check": "Readiness check: {category} season",
        "season.awareness": "Awareness campaign: {category} season",
        "season.why": "{count} interventions ({category}) on the same days of the past three years, {ratio} times the yearly average.",
        "rise": "Readiness check: rise in {category}",
        "rise.why": "{recent} interventions ({category}) in the last 14 days against {before} in the 8 weeks before.",
        "level.high": "high",
        "level.very_high": "very high",
        "level.extreme": "extreme",
        "level.watch": "watch",
        "level.warning": "warning",
        "cat.fire": "fires",
        "cat.flood": "floods",
        "cat.drowning": "drownings",
        "cat.traffic_accident": "road accidents",
        "sim": "simulated data",
    },
}


@dataclass(frozen=True, slots=True)
class Suggestion:
    key: str
    source: str  # weather, beaches, season, rise
    activity: str
    on_date: date
    title: str
    reasons: list[str] = field(default_factory=list)
    simulated: bool = False
    # The figures it rests on, kept in the audit log when it is accepted or set aside.
    evidence: dict[str, object] = field(default_factory=dict)


def _t(lang: Lang) -> dict[str, str]:
    return _T.get(lang, _T["ar"])


def window(period_start: date, period_end: date, today: date) -> list[date]:
    """The days of the programme still ahead (today included)."""
    first = max(period_start, today)
    return [first + timedelta(days=n) for n in range((period_end - first).days + 1)] if first <= period_end else []


def _local_day(at: datetime) -> date:
    return at.astimezone(domain.TUNIS).date()


def _bounds(days: list[date]) -> tuple[datetime, datetime]:
    return (
        datetime.combine(days[0], time(0), domain.TUNIS),
        datetime.combine(days[-1] + timedelta(days=1), time(0), domain.TUNIS),
    )


async def _weather(session: AsyncSession, g: int, days: list[date], lang: Lang) -> list[Suggestion]:
    t = _t(lang)
    points = {
        p.id: p.simulated for p in await session.scalars(select(GridPoint).where(GridPoint.gouvernorat_code == g))
    }
    if not points:
        return []
    start, end = _bounds(days)
    rows = await session.execute(
        select(Observation.point_id, Observation.at, Observation.fire_danger, Observation.heavy_rain).where(
            Observation.point_id.in_(points), Observation.at >= start, Observation.at < end
        )
    )
    danger: dict[date, dict[int, int]] = defaultdict(dict)
    rain: dict[date, dict[int, int]] = defaultdict(dict)
    for point, at, fire, heavy in rows:
        day = _local_day(at)
        if fire in DANGER:
            danger[day][point] = max(danger[day].get(point, 0), DANGER.index(fire))
        if heavy in RAIN:
            rain[day][point] = max(rain[day].get(point, 0), RAIN.index(heavy))
    total = len(points)
    simulated = any(points.values())
    out: list[Suggestion] = []
    patrol_from = DANGER.index(PATROL_FROM)
    for day in days:
        high = [r for r in danger.get(day, {}).values() if r >= patrol_from]
        if high:
            level = DANGER[max(high)]
            text = t[f"level.{level}"]
            out.append(
                Suggestion(
                    key=f"fire_patrol:{day.isoformat()}",
                    source="weather",
                    activity="patrol",
                    on_date=day,
                    title=t["fire_patrol"].format(level=text),
                    reasons=[
                        t["fire_patrol.why"].format(level=text, day=day.isoformat(), points=len(high), total=total)
                    ],
                    simulated=simulated,
                    evidence={"fire_danger": level, "points": len(high), "of": total},
                )
            )
    for day in days:
        wet = [r for r in rain.get(day, {}).values() if r > 0]
        if wet:
            level = RAIN[max(wet)]
            # The check comes the day before the rain, when that day is still ahead.
            on = day - timedelta(days=1) if day - timedelta(days=1) in days else day
            out.append(
                Suggestion(
                    key=f"flood_readiness:{day.isoformat()}",
                    source="weather",
                    activity="readiness_check",
                    on_date=on,
                    title=t["flood_readiness"],
                    reasons=[
                        t["flood_readiness.why"].format(
                            level=t[f"level.{level}"], day=day.isoformat(), points=len(wet), total=total
                        )
                    ],
                    simulated=simulated,
                    evidence={"heavy_rain": level, "day": day.isoformat(), "points": len(wet), "of": total},
                )
            )
    return out


async def _beaches(session: AsyncSession, g: int, days: list[date], lang: Lang) -> list[Suggestion]:
    t = _t(lang)
    rows = await session.execute(
        select(BeachDay.day, func.count(), func.bool_or(BeachDay.simulated))
        .join(LayerFeature, LayerFeature.id == BeachDay.feature_id)
        .where(
            LayerFeature.gouvernorat_code == g,
            BeachDay.day >= days[0],
            BeachDay.day <= days[-1],
            BeachDay.level == "red",
        )
        .group_by(BeachDay.day)
        .order_by(BeachDay.day)
    )
    return [
        Suggestion(
            key=f"beach_watch:{day.isoformat()}",
            source="beaches",
            activity="patrol",
            on_date=day,
            title=t["beach_watch"].format(beaches=n),
            reasons=[t["beach_watch.why"].format(day=day.isoformat(), beaches=n)],
            simulated=bool(sim),
            evidence={"red_beaches": n},
        )
        for day, n, sim in rows
    ]


async def _incidents(session: AsyncSession, g: int, since: datetime, until: datetime) -> list[tuple[str, datetime]]:
    rows = await session.execute(
        select(Incident.category, Incident.opened_at).where(
            Incident.gouvernorat_code == g,
            Incident.merged_into.is_(None),
            Incident.category.in_(SEASON_ACTIVITY),
            Incident.opened_at >= since,
            Incident.opened_at < until,
        )
    )
    return [(c, at) for c, at in rows]


async def _history(session: AsyncSession, g: int, days: list[date], now: datetime, lang: Lang) -> list[Suggestion]:
    t = _t(lang)
    today = _local_day(now)
    since = datetime.combine(today - timedelta(days=365 * YEARS), time(0), domain.TUNIS)
    incidents = await _incidents(session, g, since, now)
    if not incidents:
        return []
    out: list[Suggestion] = []
    # The season: the same days (same weekdays, 52 weeks apart) of each past year.
    same: set[date] = {d - timedelta(weeks=52 * y) for d in days for y in range(1, YEARS + 1)}
    yearly: Counter[str] = Counter(c for c, _ in incidents)
    season: Counter[str] = Counter(c for c, at in incidents if _local_day(at) in same)
    for category in SEASON_ACTIVITY:
        count = season[category]
        expected = yearly[category] * len(same) / (365 * YEARS)
        if count >= SEASON_MIN and count >= SEASON_RATIO * max(expected, 0.5):
            activity = SEASON_ACTIVITY[category]
            name = t[f"cat.{category}"]
            ratio = round(count / expected, 1) if expected else count
            out.append(
                Suggestion(
                    key=f"season:{category}",
                    source="season",
                    activity=activity,
                    on_date=days[0],
                    title=t[f"season.{activity}"].format(category=name),
                    reasons=[t["season.why"].format(count=count, category=name, ratio=ratio)],
                    evidence={"category": category, "count": count, "expected": round(expected, 2)},
                )
            )
    # The rise: the last 14 days against the 8 weeks before.
    recent_from = now - timedelta(days=RECENT_DAYS)
    before_from = recent_from - timedelta(days=BEFORE_DAYS)
    recent: Counter[str] = Counter(c for c, at in incidents if at >= recent_from)
    before: Counter[str] = Counter(c for c, at in incidents if before_from <= at < recent_from)
    for category in SEASON_ACTIVITY:
        r, b = recent[category], before[category]
        expected = b * RECENT_DAYS / BEFORE_DAYS
        if r >= RISE_MIN and r >= RISE_RATIO * max(expected, 0.5):
            name = t[f"cat.{category}"]
            out.append(
                Suggestion(
                    key=f"rise:{category}",
                    source="rise",
                    activity="readiness_check",
                    on_date=days[0],
                    title=t["rise"].format(category=name),
                    reasons=[t["rise.why"].format(recent=r, before=b, category=name)],
                    evidence={"category": category, "recent": r, "before": b},
                )
            )
    return out


async def suggestions(
    session: AsyncSession,
    gouvernorat: int,
    period_start: date,
    period_end: date,
    now: datetime,
    lang: Lang,
    taken: set[str],
    planned: set[tuple[str, date]],
) -> list[Suggestion]:
    """What the engine suggests for the days still ahead in a programme, without the suggestions already accepted
    or set aside (``taken``) and the activities already planned that day (``planned``: activity and day)."""
    days = window(period_start, period_end, _local_day(now.astimezone(UTC)))
    if not days:
        return []
    found: list[Suggestion] = []
    for source in (
        await _weather(session, gouvernorat, days, lang),
        await _beaches(session, gouvernorat, days, lang),
        await _history(session, gouvernorat, days, now, lang),
    ):
        fresh = [s for s in source if s.key not in taken and (s.activity, s.on_date) not in planned]
        found.extend(fresh[:MAX_PER_SOURCE])
    found.sort(key=lambda s: (s.on_date, s.key))
    return found[:MAX_SUGGESTIONS]


def note(s: Suggestion, lang: Lang) -> str:
    """The notes of the activity an accepted suggestion becomes."""
    sim = f" [{_t(lang)['sim']}]" if s.simulated else ""
    return " ".join(s.reasons) + sim
