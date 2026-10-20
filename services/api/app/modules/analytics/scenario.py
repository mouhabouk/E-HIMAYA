"""What-if simulation (FR-C-12): a seeded Monte Carlo queue replaying the historical demand against the resources left.

Model, stated in every result (``assumptions``):

* Arrivals: a Poisson process per hour whose rate is the historical rate of reports of that category, in those
  gouvernorats, at that hour of day, in the same season (± ``SEASON_DAYS`` days around the scenario date in each of the
  last ``HISTORY_YEARS`` years), scaled by the demand factor and by the weather relation of phase 7 when chosen.
  Days on which the platform received no report at all nationwide are treated as data gaps and left out.
* A report needs an intervention with the historical share "incidents / reports" (several reports are often grouped
  into one incident). An intervention holds one resource for a service time drawn from the historical engagement
  times (order → release) of that category, or from a stated default when history is too thin.
* Resources: the available fleet of the relevant kinds in those gouvernorats, minus the unavailable ones; first come,
  first served, no reinforcement from other gouvernorats.

The same seed, history and parameters always give the same result (``random.Random(seed)``, nothing else random).
It is a planning aid built on history, not a forecast: results say so (``disclaimer``) and carry their provenance,
``calibration: "uncalibrated"`` (the model has not been validated against real outcomes) and a ``confidence``.
"""

import heapq
import math
import random
import secrets
import statistics
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics import domain, schemas

SEASON_DAYS = 45
HISTORY_YEARS = 3
# Below these, the run is returned with confidence "low" (audit finding T26).
MIN_EVENTS = 30
MIN_DAYS = 30
MIN_SERVICE_SAMPLES = 20
MIN_INCIDENT_LINKS = 10
# Engagement times are clamped to this range (minutes): shorter is a data-entry slip, longer an order never released.
SERVICE_MIN_MIN, SERVICE_MAX_MIN = 5.0, 24 * 60.0
# A run never simulates more than this many arrivals in total (all Monte Carlo runs together).
MAX_SIMULATED_ARRIVALS = 3_000_000
OVERLOAD_UTILISATION = 0.95

# Resource kinds that answer each category (the whole operational fleet when no category is chosen).
CATEGORY_KINDS: dict[str | None, tuple[str, ...]] = {
    "fire": ("fire_engine", "water_tanker", "large_extinguisher"),
    "flood": ("rescue_vehicle", "boat", "heavy_equipment"),
    "traffic_accident": ("ambulance", "rescue_vehicle"),
    "drowning": ("boat", "rescue_vehicle", "ambulance"),
    "landslide": ("heavy_equipment", "rescue_vehicle"),
    "chemical_leak": ("fire_engine", "rescue_vehicle"),
    "medical": ("ambulance",),
}
ALL_KINDS = (
    "fire_engine",
    "water_tanker",
    "ambulance",
    "rescue_vehicle",
    "heavy_equipment",
    "large_extinguisher",
    "boat",
    "other",
)
# Default engagement times (minutes) when history has fewer than MIN_SERVICE_SAMPLES released orders.
DEFAULT_SERVICE_MIN: dict[str | None, float] = {
    "fire": 150.0,
    "flood": 180.0,
    "traffic_accident": 60.0,
    "drowning": 90.0,
    "landslide": 240.0,
    "chemical_leak": 180.0,
    "medical": 45.0,
    "sos": 60.0,
    "other": 60.0,
    None: 90.0,
}
# Default demand multipliers of the weather conditions (used when history cannot measure the relation).
FIRE_FACTORS = {"fire": 2.5}
RAIN_FACTORS = {"flood": 3.0, "landslide": 2.0, "traffic_accident": 1.3, "drowning": 1.2}
FIRE_DANGER_HIGH = ("very_high", "extreme")
RAIN_HIGH = ("watch", "warning")


def kinds_for(category: str | None) -> tuple[str, ...]:
    return CATEGORY_KINDS.get(category, ALL_KINDS)


def _years_back(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # 29 February
        return day.replace(year=day.year - years, day=28)


# ---------------------------------------------------------------- history


@dataclass
class History:
    window_from: date | None = None
    window_to: date | None = None
    days: list[date] = field(default_factory=list)
    gap_days: int = 0
    by_hour: list[int] = field(default_factory=lambda: [0] * 24)
    events: int = 0
    incidents: int = 0
    linked_reports: int = 0
    service: list[float] = field(default_factory=list)
    service_source: str = "default"
    fleet: dict[str, list[str]] = field(default_factory=dict)

    @property
    def job_ratio(self) -> float:
        if self.linked_reports < MIN_INCIDENT_LINKS or self.incidents == 0:
            return 1.0
        return min(1.0, max(0.05, self.incidents / self.linked_reports))


def _scope(alias: str, category: str | None) -> str:
    cond = f"{alias}.gouvernorat_code = ANY(CAST(:codes AS smallint[]))"
    return cond + (f" AND {alias}.category = :category" if category else "")


async def load_history(
    session: AsyncSession, codes: list[int], category: str | None, start: datetime, kinds: tuple[str, ...]
) -> History:
    """Past demand, engagement times and current fleet for a scenario starting at ``start``."""
    history = History()
    params: dict[str, Any] = {"codes": codes, "category": category} if category else {"codes": codes}
    today = domain.local_today(start)
    yesterday = today - timedelta(days=1)
    first = await session.scalar(text("SELECT min(received_at) FROM reports.report"))
    first_day = first.astimezone(domain.TUNIS_TZ).date() if first else None
    covered: set[date] = set()
    if first_day is not None:
        for years in range(HISTORY_YEARS):
            centre = _years_back(today, years)
            lo = max(centre - timedelta(days=SEASON_DAYS), first_day)
            hi = min(centre + timedelta(days=SEASON_DAYS), yesterday)
            day = lo
            while day <= hi:
                covered.add(day)
                day += timedelta(days=1)
    if covered:
        history.window_from, history.window_to = min(covered), max(covered)
        active = set(
            await session.scalars(
                text(
                    "SELECT DISTINCT CAST((received_at AT TIME ZONE 'Africa/Tunis') AS date) FROM reports.report "
                    "WHERE received_at >= :t0 AND received_at < :t1"
                ),
                {
                    "t0": domain.day_start(history.window_from),
                    "t1": domain.day_start(history.window_to + timedelta(days=1)),
                },
            )
        )
        history.days = sorted(covered & active)
        history.gap_days = len(covered - active)
    if history.days:
        rows = await session.execute(
            text(
                "SELECT CAST(extract(hour FROM (r.received_at AT TIME ZONE 'Africa/Tunis')) AS int), count(*), "  # noqa: S608 (constant SQL fragments, values are bound)
                "count(r.incident_id), count(DISTINCT r.incident_id) FROM reports.report r "
                f"WHERE {_scope('r', category)} AND r.status <> 'rejected' "
                "AND CAST((r.received_at AT TIME ZONE 'Africa/Tunis') AS date) = ANY(CAST(:days AS date[])) "
                "GROUP BY 1"
            ),
            params | {"days": history.days},
        )
        for hour, n, linked, _ in rows.all():
            history.by_hour[int(hour)] = int(n)
            history.linked_reports += int(linked)
        history.events = sum(history.by_hour)
        history.incidents = int(
            await session.scalar(
                text(
                    "SELECT count(DISTINCT r.incident_id) FROM reports.report r "  # noqa: S608 (constant SQL fragments, values are bound)
                    f"WHERE {_scope('r', category)} AND r.status <> 'rejected' "
                    "AND CAST((r.received_at AT TIME ZONE 'Africa/Tunis') AS date) = ANY(CAST(:days AS date[]))"
                ),
                params | {"days": history.days},
            )
            or 0
        )
    service_sql = (
        "SELECT extract(epoch FROM a.released_at - a.created_at) / 60.0 FROM ops.assignment a "
        "JOIN ops.incident i ON i.id = a.incident_id WHERE a.kind = 'resource' AND a.released_at IS NOT NULL "
        "AND a.created_at >= :since {scope} ORDER BY a.created_at, a.id"
    )
    since = start - timedelta(days=365 * HISTORY_YEARS)
    for source, scope in (
        ("history", " AND " + _scope("i", category)),
        ("history_national", " AND i.category = :category" if category else ""),
    ):
        samples = [
            min(SERVICE_MAX_MIN, max(SERVICE_MIN_MIN, float(v)))
            for v in await session.scalars(text(service_sql.format(scope=scope)), params | {"since": since})
            if v is not None
        ]
        if len(samples) >= MIN_SERVICE_SAMPLES:
            history.service, history.service_source = samples, source
            break
    fleet_rows = await session.execute(
        text(
            "SELECT r.kind, CAST(r.id AS text) FROM ops.resource r JOIN ops.unit u ON u.id = r.unit_id "
            "WHERE u.gouvernorat_code = ANY(CAST(:codes AS smallint[])) AND r.status <> 'out_of_service' "
            "AND r.kind = ANY(CAST(:kinds AS text[])) ORDER BY r.kind, r.id"
        ),
        {"codes": codes, "kinds": list(kinds)},
    )
    for kind, rid in fleet_rows.all():
        history.fleet.setdefault(kind, []).append(rid)
    return history


def remaining_capacity(fleet: dict[str, list[str]], unavailable: list[Any] | dict[str, int]) -> tuple[int, int]:
    """(resources left, resources removed). Unknown ids or kinds outside this fleet: 422 ``unknown_resource``."""
    total = sum(len(ids) for ids in fleet.values())
    if isinstance(unavailable, dict):
        removed = 0
        for kind, n in unavailable.items():
            if kind not in domain.RESOURCE_LABELS:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown_resource")
            removed += min(n, len(fleet.get(kind, [])))
        return total - removed, removed
    known = {rid for ids in fleet.values() for rid in ids}
    wanted = {str(rid) for rid in unavailable}
    if not wanted <= known:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown_resource")
    return total - len(wanted), len(wanted)


# ---------------------------------------------------------------- weather relation (phase 7)


@dataclass
class WeatherEffect:
    multipliers: list[float]
    factor: float
    source: str  # history | default | forecast | none
    condition: str | None


def _default_factor(table: dict[str, float], category: str | None, shares: dict[str, float]) -> float:
    if category is not None:
        return table.get(category, 1.0)
    # All categories: the condition raises only the share of the categories it affects.
    return 1.0 + sum(shares.get(c, 0.0) * (f - 1.0) for c, f in table.items())


async def _category_shares(session: AsyncSession, codes: list[int], days: list[date]) -> dict[str, float]:
    if not days:
        return {}
    rows = await session.execute(
        text(
            "SELECT category, count(*) FROM reports.report WHERE gouvernorat_code = ANY(CAST(:codes AS smallint[])) "
            "AND CAST((received_at AT TIME ZONE 'Africa/Tunis') AS date) = ANY(CAST(:days AS date[])) GROUP BY 1"
        ),
        {"codes": codes, "days": days},
    )
    counts = {c: int(n) for c, n in rows.all()}
    total = sum(counts.values())
    return {c: n / total for c, n in counts.items()} if total else {}


async def _measured_factor(
    session: AsyncSession, codes: list[int], category: str, history: History, condition_sql: str
) -> float | None:
    """Ratio of the daily report rate on days with the condition (past observations of the grid points of those
    gouvernorats) to the rate on the other days; None when history is too thin to measure it."""
    if not history.days:
        return None
    cond_days = set(
        await session.scalars(
            text(
                "SELECT DISTINCT CAST((o.at AT TIME ZONE 'Africa/Tunis') AS date) FROM weather.observation o "  # noqa: S608 (constant SQL fragments, values are bound)
                "JOIN weather.grid_point p ON p.id = o.point_id "
                "WHERE p.gouvernorat_code = ANY(CAST(:codes AS smallint[])) AND o.forecast = false "
                f"AND {condition_sql} AND o.at >= :t0 AND o.at < :t1"
            ),
            {
                "codes": codes,
                "t0": domain.day_start(history.days[0]),
                "t1": domain.day_start(history.days[-1] + timedelta(days=1)),
            },
        )
    ) & set(history.days)
    other_days = [d for d in history.days if d not in cond_days]
    if len(cond_days) < 5 or not other_days or history.events < MIN_EVENTS:
        return None
    rows = await session.execute(
        text(
            "SELECT CAST((received_at AT TIME ZONE 'Africa/Tunis') AS date) = ANY(CAST(:cond AS date[])), count(*) "
            "FROM reports.report WHERE gouvernorat_code = ANY(CAST(:codes AS smallint[])) AND category = :category "
            "AND status <> 'rejected' "
            "AND CAST((received_at AT TIME ZONE 'Africa/Tunis') AS date) = ANY(CAST(:days AS date[])) GROUP BY 1"
        ),
        {"cond": sorted(cond_days), "codes": codes, "category": category, "days": history.days},
    )
    counts = {bool(k): int(n) for k, n in rows.all()}
    rate_other = counts.get(False, 0) / len(other_days)
    if rate_other <= 0:
        return None
    return min(10.0, max(1.0, (counts.get(True, 0) / len(cond_days)) / rate_other))


async def weather_effect(
    session: AsyncSession,
    codes: list[int],
    category: str | None,
    weather: str,
    start: datetime,
    hours: int,
    history: History,
) -> WeatherEffect:
    shares = await _category_shares(session, codes, history.days) if category is None else {}
    fire = _default_factor(FIRE_FACTORS, category, shares)
    rain = _default_factor(RAIN_FACTORS, category, shares)
    source = "default"
    if category in FIRE_FACTORS:
        measured = await _measured_factor(
            session, codes, category, history, "o.fire_danger IN ('very_high', 'extreme')"
        )
        fire, source = (measured, "history") if measured is not None else (fire, source)
    if category in RAIN_FACTORS:
        measured = await _measured_factor(session, codes, category, history, "o.heavy_rain IN ('watch', 'warning')")
        rain, source = (measured, "history") if measured is not None else (rain, source)
    if weather == "fire_danger_extreme":
        return WeatherEffect([fire] * hours, fire, source if fire > 1.0 else "none", "fire_danger")
    if weather == "heavy_rain":
        return WeatherEffect([rain] * hours, rain, source if rain > 1.0 else "none", "heavy_rain")
    # As forecast: the hours whose forecast (phase 7 grid) reaches the condition in one of the gouvernorats.
    rows = await session.execute(
        text(
            "SELECT o.at, bool_or(o.fire_danger IN ('very_high', 'extreme')), "
            "bool_or(o.heavy_rain IN ('watch', 'warning')) "
            "FROM weather.observation o JOIN weather.grid_point p ON p.id = o.point_id "
            "WHERE p.gouvernorat_code = ANY(CAST(:codes AS smallint[])) AND o.at >= :t0 AND o.at < :t1 GROUP BY o.at"
        ),
        {"codes": codes, "t0": start, "t1": start + timedelta(hours=hours)},
    )
    by_hour = {at.astimezone(UTC): (bool(f), bool(r)) for at, f, r in rows.all()}
    if not by_hour:
        return WeatherEffect([1.0] * hours, 1.0, "none", None)
    multipliers = []
    for h in range(hours):
        high_fire, high_rain = by_hour.get(start + timedelta(hours=h), (False, False))
        multipliers.append(max(fire if high_fire else 1.0, rain if high_rain else 1.0))
    peak = max(multipliers)
    return WeatherEffect(multipliers, peak, "forecast" if peak > 1.0 else "none", "forecast")


# ---------------------------------------------------------------- simulation (pure, deterministic)


def percentile(values: list[float], q: float) -> float:
    """Linear interpolation between closest ranks (q in [0, 1])."""
    ordered = sorted(values)
    if not ordered:
        return 0.0
    pos = (len(ordered) - 1) * q
    low, high = math.floor(pos), math.ceil(pos)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def _band(values: list[float], digits: int) -> dict[str, float]:
    return {f"p{int(q * 100)}": round(percentile(values, q), digits) for q in (0.1, 0.5, 0.9)}


@dataclass
class SimulationOutput:
    reports: list[list[float]]  # [hour][run]
    waits: list[list[float]]  # minutes
    utilisation: list[list[float]]  # 0..1
    run_reports_per_hour: list[float]
    run_wait: list[float]
    run_utilisation: list[float]
    run_total: list[float]


def simulate(
    report_rates: list[float],
    job_ratio: float,
    service_samples: list[float],
    default_service_min: float,
    capacity: int,
    runs: int,
    seed: int,
) -> SimulationOutput:
    """Monte Carlo of a multi-server first-come-first-served queue over ``len(report_rates)`` hours.

    ``report_rates[h]`` is the expected number of reports in hour h; each report needs an intervention with
    probability ``job_ratio``; an intervention holds one of ``capacity`` resources for a service time drawn from
    ``service_samples`` (or a gamma law of mean ``default_service_min`` when empty)."""
    hours = len(report_rates)
    horizon = hours * 60.0
    # Planning simulation, not security: a seeded generator is the point (same seed, same result).
    rng = random.Random(seed)  # noqa: S311
    out = SimulationOutput(
        [[] for _ in range(hours)], [[] for _ in range(hours)], [[] for _ in range(hours)], [], [], [], []
    )
    for _ in range(runs):
        free = [0.0] * capacity
        arrivals, jobs = [0] * hours, [0] * hours
        wait_sum, busy = [0.0] * hours, [0.0] * hours
        for h, rate in enumerate(report_rates):
            if rate <= 0:
                continue
            per_minute = rate / 60.0
            t = h * 60.0 + rng.expovariate(per_minute)
            while t < (h + 1) * 60.0:
                arrivals[h] += 1
                if rng.random() < job_ratio:
                    service = (
                        rng.choice(service_samples)
                        if service_samples
                        else rng.gammavariate(2.0, default_service_min / 2.0)
                    )
                    begin = max(t, heapq.heappop(free))
                    end = begin + service
                    heapq.heappush(free, end)
                    jobs[h] += 1
                    wait_sum[h] += begin - t
                    k = int(begin // 60)
                    while k < hours and k * 60.0 < end:
                        busy[k] += max(0.0, min(end, (k + 1) * 60.0) - max(begin, k * 60.0))
                        k += 1
                t += rng.expovariate(per_minute)
        for h in range(hours):
            out.reports[h].append(float(arrivals[h]))
            out.waits[h].append(wait_sum[h] / jobs[h] if jobs[h] else 0.0)
            out.utilisation[h].append(min(1.0, busy[h] / (60.0 * capacity)))
        total_jobs = sum(jobs)
        out.run_reports_per_hour.append(sum(arrivals) / hours)
        out.run_wait.append(sum(wait_sum) / total_jobs if total_jobs else 0.0)
        out.run_utilisation.append(min(1.0, sum(busy) / (horizon * capacity)))
        out.run_total.append(float(sum(arrivals)))
    return out


# ---------------------------------------------------------------- texts (ar/fr/en)

DISCLAIMER = {
    "ar": "أداة مساعدة على التخطيط مبنية على المعطيات التاريخية للمنصة، وليست تنبؤًا: الأرقام تقديرات احتمالية "
    "(النسب المئوية 10/50/90) ولا تعوّض تقدير القيادة الميدانية.",
    "fr": "Outil d'aide à la planification fondé sur l'historique de la plateforme, pas une prévision : les chiffres "
    "sont des estimations probabilistes (percentiles 10/50/90) et ne remplacent pas l'appréciation du commandement.",
    "en": "A planning aid built on the platform's history, not a forecast: the figures are probabilistic estimates "
    "(10/50/90 percentiles) and do not replace the judgement of the command.",
}
CALIBRATION_NOTE = {
    "ar": "النموذج غير معايَر: لم تتم مقارنة نتائجه بنتائج حقيقية بعد، فلا ينبغي اعتماد أرقامه كقيم دقيقة.",
    "fr": "Modèle non calibré : ses résultats n'ont pas encore été validés par comparaison avec des issues réelles ; "
    "ses chiffres ne doivent pas être lus comme des valeurs exactes.",
    "en": "Uncalibrated model: its results have not yet been validated against real outcomes; its figures must not "
    "be read as exact values.",
}


def _places(codes: list[int], names: dict[int, dict[str, str]], lang: str) -> str:
    return (
        "، ".join(names.get(c, {}).get(lang, str(c)) for c in codes)
        if lang == "ar"
        else ", ".join(names.get(c, {}).get(lang, str(c)) for c in codes)
    )


def assumptions(
    params: schemas.ScenarioIn,
    history: History,
    effect: WeatherEffect,
    capacity: int,
    removed: int,
    mean_service: float,
    names: dict[int, dict[str, str]],
) -> list[dict[str, str]]:
    cat = domain.category_label(params.category.value if params.category else None)
    kinds = kinds_for(params.category.value if params.category else None)
    kinds_ar = "، ".join(domain.RESOURCE_LABELS[k]["ar"] for k in kinds)
    kinds_fr = ", ".join(domain.RESOURCE_LABELS[k]["fr"] for k in kinds)
    kinds_en = ", ".join(domain.RESOURCE_LABELS[k]["en"] for k in kinds)
    measured_ratio = history.linked_reports >= MIN_INCIDENT_LINKS
    window = f"{history.window_from} → {history.window_to}" if history.window_from else "—"
    items = [
        {
            "ar": f"الطلب يعيد التوزيع الساعي لـ {history.events} بلاغًا سابقًا ({cat['ar']}، "
            f"{_places(params.gouvernorats, names, 'ar')}) في نفس الموسم (±{SEASON_DAYS} يومًا، آخر {HISTORY_YEARS} "
            f"سنوات، {len(history.days)} يومًا مغطى: {window})، مضروبًا في ×{params.demand_factor:g}.",
            "fr": f"La demande rejoue la répartition horaire de {history.events} signalements passés ({cat['fr']}, "
            f"{_places(params.gouvernorats, names, 'fr')}) de la même saison (±{SEASON_DAYS} jours, {HISTORY_YEARS} "
            f"dernières années, {len(history.days)} jours couverts : {window}), "
            f"multipliée par ×{params.demand_factor:g}.",
            "en": f"Demand replays the hourly distribution of {history.events} past reports ({cat['en']}, "
            f"{_places(params.gouvernorats, names, 'en')}) from the same season (±{SEASON_DAYS} days, last "
            f"{HISTORY_YEARS} years, {len(history.days)} days covered: {window}), "
            f"multiplied by ×{params.demand_factor:g}.",
        },
        {
            "ar": f"{history.gap_days} يومًا بدون أي بلاغ على المستوى الوطني اعتُبرت انقطاعًا في المعطيات واستُبعدت.",
            "fr": f"{history.gap_days} jours sans aucun signalement au niveau national sont traités comme des lacunes "
            "de données et exclus.",
            "en": f"{history.gap_days} days without any report nationwide are treated as data gaps and excluded.",
        },
        {
            "ar": f"كل بلاغ يتطلب تدخلًا بنسبة {history.job_ratio:.0%} (نسبة الحوادث إلى البلاغات"
            f"{' التاريخية' if measured_ratio else '، قيمة افتراضية'}).",
            "fr": f"Chaque signalement demande une intervention avec une probabilité de {history.job_ratio:.0%} "
            f"(rapport incidents / signalements {'historique' if measured_ratio else 'par défaut'}).",
            "en": f"Each report requires an intervention with a probability of {history.job_ratio:.0%} "
            f"({'historical' if measured_ratio else 'default'} incidents / reports ratio).",
        },
        {
            "ar": f"كل تدخل يشغل وسيلة واحدة لمدة متوسطها {round(mean_service / 5) * 5:.0f} دقيقة "
            + (
                f"(مأخوذة من {len(history.service)} تكليفًا سابقًا)."
                if history.service
                else "(قيمة افتراضية: لا يوجد تاريخ كافٍ لمدد التدخل)."
            ),
            "fr": f"Chaque intervention mobilise un moyen pendant {round(mean_service / 5) * 5:.0f} min en moyenne "
            + (
                f"(tirées de {len(history.service)} engagements passés)."
                if history.service
                else "(valeur par défaut : historique des durées insuffisant)."
            ),
            "en": f"Each intervention keeps one resource busy for {round(mean_service / 5) * 5:.0f} min on average "
            + (
                f"(taken from {len(history.service)} past commitments)."
                if history.service
                else "(default value: not enough history of durations)."
            ),
        },
        {
            "ar": f"الوسائل المتاحة: {capacity} ({kinds_ar}) بعد سحب {removed}؛ الأولوية حسب ترتيب الوصول، "
            "دون تعزيزات من ولايات أخرى.",
            "fr": f"Moyens disponibles : {capacity} ({kinds_fr}) après retrait de {removed} ; premier arrivé, premier "
            "servi, sans renfort d'autres gouvernorats.",
            "en": f"Available resources: {capacity} ({kinds_en}) after withdrawing {removed}; first come, first "
            "served, without reinforcement from other governorates.",
        },
    ]
    weather_text = {
        "none": (
            "لا يوجد عامل طقس مطبق (لا توقعات أو لا تأثير على هذا الصنف).",
            "Aucun facteur météo appliqué (pas de prévision ou pas d'effet sur cette catégorie).",
            "No weather factor applied (no forecast, or no effect on this category).",
        ),
        "forecast": (
            f"عامل الطقس حسب التوقعات (المرحلة 7): حتى ×{effect.factor:.1f} في الساعات المعنية.",
            f"Facteur météo selon les prévisions (phase 7) : jusqu'à ×{effect.factor:.1f} aux heures concernées.",
            f"Weather factor from the forecasts (phase 7): up to ×{effect.factor:.1f} in the hours concerned.",
        ),
        "history": (
            f"عامل الطقس ×{effect.factor:.1f} مقاس من التاريخ (الأيام المماثلة مقابل الأيام الأخرى).",
            f"Facteur météo ×{effect.factor:.1f} mesuré sur l'historique (jours comparables contre autres jours).",
            f"Weather factor ×{effect.factor:.1f} measured on the history (comparable days against other days).",
        ),
        "default": (
            f"عامل الطقس ×{effect.factor:.1f} قيمة افتراضية (التاريخ غير كافٍ لقياسه).",
            f"Facteur météo ×{effect.factor:.1f} par défaut (historique insuffisant pour le mesurer).",
            f"Weather factor ×{effect.factor:.1f} by default (not enough history to measure it).",
        ),
    }[effect.source]
    items.append({"ar": weather_text[0], "fr": weather_text[1], "en": weather_text[2]})
    return items


def confidence(history: History) -> tuple[str, list[dict[str, str]]]:
    reasons = []
    if history.events < MIN_EVENTS:
        reasons.append(
            {
                "ar": f"عدد الأحداث السابقة لهذا الصنف والمكان ({history.events}) أقل من {MIN_EVENTS}.",
                "fr": "Trop peu d'événements passés pour cette catégorie et ce lieu "
                f"({history.events} < {MIN_EVENTS}).",
                "en": f"Too few past events for this category and place ({history.events} < {MIN_EVENTS}).",
            }
        )
    if len(history.days) < MIN_DAYS:
        reasons.append(
            {
                "ar": f"الأيام المغطاة بالمعطيات ({len(history.days)}) أقل من {MIN_DAYS}.",
                "fr": f"Trop peu de jours couverts par les données ({len(history.days)} < {MIN_DAYS}).",
                "en": f"Too few days covered by the data ({len(history.days)} < {MIN_DAYS}).",
            }
        )
    if not history.service:
        reasons.append(
            {
                "ar": "مدد التدخل افتراضية لغياب تاريخ كافٍ.",
                "fr": "Durées d'intervention par défaut, faute d'historique suffisant.",
                "en": "Default intervention durations, for lack of sufficient history.",
            }
        )
    return ("low" if reasons else "normal"), reasons


# ---------------------------------------------------------------- run


async def run(
    session: AsyncSession, params: schemas.ScenarioIn, runs: int, names: dict[int, dict[str, str]]
) -> tuple[int, dict[str, Any]]:
    """Gather the history, simulate, and return (seed, result)."""
    from anyio import to_thread

    seed = params.seed if params.seed is not None else secrets.randbelow(2**53)
    now = datetime.now(UTC)
    start = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    category = params.category.value if params.category else None
    kinds = kinds_for(category)
    history = await load_history(session, params.gouvernorats, category, start, kinds)
    capacity, removed = remaining_capacity(history.fleet, params.unavailable_resources)
    if capacity <= 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "no_capacity")
    hours = params.horizon_hours
    effect = await weather_effect(session, params.gouvernorats, category, params.weather, start, hours, history)
    days = max(1, len(history.days))
    rates = []
    for h in range(hours):
        hod = (start + timedelta(hours=h)).astimezone(domain.TUNIS_TZ).hour
        rates.append(history.by_hour[hod] / days * params.demand_factor * effect.multipliers[h])
    if sum(rates) * runs > MAX_SIMULATED_ARRIVALS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "demand_too_large")
    default_service = DEFAULT_SERVICE_MIN.get(category, DEFAULT_SERVICE_MIN[None])
    mean_service = statistics.fmean(history.service) if history.service else default_service
    sim = await to_thread.run_sync(
        simulate, rates, history.job_ratio, history.service, default_service, capacity, runs, seed
    )
    hours_out, overload = [], []
    for h in range(hours):
        offered = rates[h] * history.job_ratio * mean_service / 60.0
        utilisation = _band(sim.utilisation[h], 2)
        overloaded = offered > capacity or utilisation["p50"] >= OVERLOAD_UTILISATION
        if overloaded:
            overload.append(h)
        hours_out.append(
            {
                "hour": h,
                "at": (start + timedelta(hours=h)).isoformat(),
                "demand": _band(sim.reports[h], 1),
                "wait_minutes": {k: round(v) for k, v in _band(sim.waits[h], 0).items()},
                "utilisation": utilisation,
                "overloaded": overloaded,
            }
        )
    level, reasons = confidence(history)
    result = {
        "start_at": start.isoformat(),
        "hours": hours_out,
        "overload_hours": overload,
        "summary": {
            "reports_per_hour": _band(sim.run_reports_per_hour, 1),
            "total_reports": {k: round(v) for k, v in _band(sim.run_total, 0).items()},
            "wait_minutes": {k: round(v) for k, v in _band(sim.run_wait, 0).items()},
            "utilisation": _band(sim.run_utilisation, 2),
            "capacity": capacity,
        },
        "assumptions": assumptions(params, history, effect, capacity, removed, mean_service, names),
        "disclaimer": DISCLAIMER,
        "calibration": "uncalibrated",
        "calibration_note": CALIBRATION_NOTE,
        "confidence": level,
        "confidence_reasons": reasons,
        "provenance": {
            "history_from": history.window_from.isoformat() if history.window_from else None,
            "history_to": history.window_to.isoformat() if history.window_to else None,
            "season_days": SEASON_DAYS,
            "history_years": HISTORY_YEARS,
            "events": history.events,
            "incidents": history.incidents,
            "days_covered": len(history.days),
            "gap_days": history.gap_days,
            "job_ratio": round(history.job_ratio, 2),
            "service_time_source": history.service_source,
            "service_time_samples": len(history.service),
            "mean_service_minutes": round(mean_service / 5) * 5,
            "weather": params.weather,
            "weather_factor": round(effect.factor, 1),
            "weather_factor_source": effect.source,
            "resources_total": capacity + removed,
            "resources_removed": removed,
        },
    }
    return seed, result
