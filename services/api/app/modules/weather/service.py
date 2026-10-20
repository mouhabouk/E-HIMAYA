"""Weather grid refresh, threshold rules → suggested alerts, and the read side used by the endpoints and the scores.

Refresh cycle (worker role, ``weather_forever``): points whose data is due are claimed with SKIP LOCKED (several
workers share the grid), fetched in batches outside any transaction, and written point by point (hourly rows for the
past 30 h and next 48 h, the fire weather codes of the last past noon). Then old rows are pruned and the rules are
evaluated over the next 24 h, under an advisory lock so one process creates the suggestions.
"""

import math
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import Float, and_, any_, cast, delete, func, literal, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.events import emit
from app.core.security import Principal
from app.modules.geo.models import Gouvernorat
from app.modules.weather import fwi, indices, schemas, texts
from app.modules.weather.models import AlertSuggestion, GridPoint, Observation, Rule
from app.modules.weather.provider import (
    SIM_ATTRIBUTION,
    Series,
    WeatherProvider,
    WeatherRateLimited,
    WeatherUnavailable,
    get_provider,
)

log = structlog.get_logger()

KEEP_PAST = timedelta(hours=30)
KEEP_AHEAD = timedelta(hours=48)
PRUNE_AFTER = timedelta(hours=36)
RULE_WINDOW = timedelta(hours=24)
FORECAST_DAYS = 3
CLAIM_LEASE = timedelta(minutes=15)
_EVALUATE_LOCK = 0x5745_4154  # "WEAT": advisory lock of the rule evaluation and the grid seeding
METRICS = ("fire_danger", "wind_gust", "rain_24h", "rain_1h")
ACTIVE_STATUSES = ("pending", "accepted", "dismissed")


def _hour(at: datetime) -> datetime:
    return at.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def _backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(300 * 2 ** max(attempts - 1, 0), 6 * 3600))


# ---------------------------------------------------------------- grid


async def ensure_grid(session: AsyncSession) -> int:
    """Lay the grid over Tunisia (land within 10 km of a gouvernorat) on first start. Returns the number of points."""
    count = int(await session.scalar(select(func.count()).select_from(GridPoint)) or 0)
    if count:
        return count
    await session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _EVALUATE_LOCK})
    step = get_settings().weather_grid_step_deg
    await session.execute(
        text(
            """
            INSERT INTO weather.grid_point (lat, lon, location, gouvernorat_code, next_fetch_at)
            SELECT g.lat, g.lon, ST_SetSRID(ST_MakePoint(g.lon, g.lat), 4326)::geography,
                   (SELECT b.code FROM geo.gouvernorat b WHERE b.boundary IS NOT NULL
                    ORDER BY ST_Distance(b.boundary, ST_SetSRID(ST_MakePoint(g.lon, g.lat), 4326)) LIMIT 1),
                   timestamptz '2000-01-01T00:00:00Z'
            FROM (SELECT round(la::numeric, 4)::float8 AS lat, round(lo::numeric, 4)::float8 AS lon
                  FROM generate_series(30.0, 37.6, CAST(:step AS numeric)) la,
                       generate_series(7.5, 11.6, CAST(:step AS numeric)) lo) g
            WHERE EXISTS (SELECT 1 FROM geo.gouvernorat b WHERE b.boundary IS NOT NULL
                          AND ST_DWithin(b.boundary, ST_SetSRID(ST_MakePoint(g.lon, g.lat), 4326), 0.1))
            ON CONFLICT (lat, lon) DO NOTHING
            """
        ),
        {"step": step},
    )
    # A gouvernorat smaller than a grid cell (Tunis) gets its own point, so that its rules can be met.
    await session.execute(
        text(
            """
            INSERT INTO weather.grid_point (lat, lon, location, gouvernorat_code, next_fetch_at)
            SELECT p.lat, p.lon, ST_SetSRID(ST_MakePoint(p.lon, p.lat), 4326)::geography, p.code,
                   timestamptz '2000-01-01T00:00:00Z'
            FROM (SELECT b.code, round(ST_Y(ST_PointOnSurface(b.boundary))::numeric, 2)::float8 AS lat,
                         round(ST_X(ST_PointOnSurface(b.boundary))::numeric, 2)::float8 AS lon
                  FROM geo.gouvernorat b
                  WHERE b.boundary IS NOT NULL
                    AND NOT EXISTS (SELECT 1 FROM weather.grid_point w WHERE w.gouvernorat_code = b.code)) p
            ON CONFLICT (lat, lon) DO NOTHING
            """
        )
    )
    count = int(await session.scalar(select(func.count()).select_from(GridPoint)) or 0)
    log.info("weather.grid_created", points=count, step_deg=step)
    return count


# ---------------------------------------------------------------- refresh


@dataclass(frozen=True, slots=True)
class Claimed:
    id: int
    lat: float
    lon: float
    previous: fwi.Indices | None
    previous_date: date | None
    attempts: int


def _indices_of(codes: dict[str, float] | None) -> fwi.Indices | None:
    if not codes or any(k not in codes for k in ("ffmc", "dmc", "dc", "isi", "bui", "fwi")):
        return None
    return fwi.Indices(**{k: float(codes[k]) for k in ("ffmc", "dmc", "dc", "isi", "bui", "fwi")})


async def _claim(sessionmaker: async_sessionmaker[AsyncSession], now: datetime, limit: int) -> list[Claimed]:
    async with sessionmaker() as session, session.begin():
        await ensure_grid(session)
        rows = (
            await session.execute(
                select(GridPoint)
                .where(GridPoint.next_fetch_at <= now)
                .order_by(GridPoint.next_fetch_at, GridPoint.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).scalars()
        claimed: list[Claimed] = []
        for point in rows:
            point.next_fetch_at = now + CLAIM_LEASE
            claimed.append(
                Claimed(point.id, point.lat, point.lon, _indices_of(point.codes), point.codes_date, point.attempts)
            )
    return claimed


async def store_series(
    session: AsyncSession, point_id: int, series: Series, provider: WeatherProvider, now: datetime
) -> None:
    """Write one point's fetched series and derived indices (caller's transaction)."""
    point = await session.get(GridPoint, point_id, with_for_update=True)
    if point is None:
        return
    result = indices.compute(series.hours, point.lat, _indices_of(point.codes), point.codes_date, now)
    current = _hour(now)
    rows: list[dict[str, Any]] = []
    for row in result.rows:
        h = row.hour
        if not current - KEEP_PAST <= h.at <= current + KEEP_AHEAD:
            continue
        ix = row.indices
        rows.append(
            {
                "point_id": point_id,
                "at": h.at,
                "temperature_c": h.temperature_c,
                "relative_humidity_pct": h.relative_humidity_pct,
                "wind_speed_kmh": h.wind_speed_kmh,
                "wind_gust_kmh": h.wind_gust_kmh,
                "wind_direction_deg": h.wind_direction_deg,
                "precipitation_mm": h.precipitation_mm,
                "precipitation_24h_mm": row.precipitation_24h_mm,
                "weather_code": h.weather_code,
                "ffmc": ix.ffmc if ix else None,
                "dmc": ix.dmc if ix else None,
                "dc": ix.dc if ix else None,
                "isi": ix.isi if ix else None,
                "bui": ix.bui if ix else None,
                "fwi": ix.fwi if ix else None,
                "fire_danger": ix.danger.value if ix else None,
                "heavy_rain": row.heavy_rain,
                "forecast": h.at > now,
            }
        )
    if rows:
        # One statement executed for many parameter sets: compiled once and cached (a multi-VALUES insert would be
        # compiled again for every point).
        await session.execute(_UPSERT, rows)
    if result.last_past is not None:
        point.codes = {k: round(v, 4) for k, v in vars_of(result.last_past).items()}
        point.codes_date = result.last_past_date
    settings = get_settings()
    point.fetched_at = now
    point.next_fetch_at = now + timedelta(seconds=settings.weather_fetch_min_age_s)
    point.attempts = 0
    point.source = provider.name
    point.simulated = provider.simulated


def _upsert() -> Any:
    statement = insert(Observation)
    columns = {
        c.name: statement.excluded[c.name] for c in Observation.__table__.columns if c.name not in ("point_id", "at")
    }
    return statement.on_conflict_do_update(index_elements=["point_id", "at"], set_=columns)


_UPSERT = _upsert()


def vars_of(ix: fwi.Indices) -> dict[str, float]:
    return {k: getattr(ix, k) for k in ("ffmc", "dmc", "dc", "isi", "bui", "fwi")}


async def _failed(sessionmaker: async_sessionmaker[AsyncSession], points: list[Claimed], now: datetime) -> None:
    async with sessionmaker() as session, session.begin():
        for p in points:
            await session.execute(
                update(GridPoint)
                .where(GridPoint.id == p.id)
                .values(attempts=GridPoint.attempts + 1, next_fetch_at=now + _backoff(p.attempts + 1))
            )


async def refresh(
    sessionmaker: async_sessionmaker[AsyncSession], provider: WeatherProvider | None = None, now: datetime | None = None
) -> dict[str, int]:
    """One refresh cycle. Returns counters (fetched, failed, suggestions)."""
    provider = provider or get_provider()
    now = now or datetime.now(UTC)
    settings = get_settings()
    claimed = await _claim(sessionmaker, now, settings.weather_max_points_per_cycle)
    fetched = failed = 0
    # New points are spun up with past days (their fire weather codes start from the standard start-up values).
    groups: dict[int, list[Claimed]] = defaultdict(list)
    for p in claimed:
        groups[1 if p.previous is not None else settings.weather_spinup_days].append(p)
    stop = False
    for past_days, points in groups.items():
        for start in range(0, len(points), settings.weather_batch_size):
            batch = points[start : start + settings.weather_batch_size]
            if stop:
                await _failed(sessionmaker, batch, now)
                failed += len(batch)
                continue
            try:
                series = await provider.fetch([(p.lat, p.lon) for p in batch], past_days, FORECAST_DAYS)
            except WeatherRateLimited:
                log.warning("weather.rate_limited", provider=provider.name)
                stop = True
                await _failed(sessionmaker, batch, now)
                failed += len(batch)
                continue
            except WeatherUnavailable as exc:
                log.warning("weather.fetch_failed", provider=provider.name, error=str(exc), points=len(batch))
                await _failed(sessionmaker, batch, now)
                failed += len(batch)
                continue
            async with sessionmaker() as session, session.begin():
                for p, s in zip(batch, series, strict=True):
                    await store_series(session, p.id, s, provider, now)
            fetched += len(batch)
    created = 0
    async with sessionmaker() as session, session.begin():
        await session.execute(delete(Observation).where(Observation.at < now - PRUNE_AFTER))
        if fetched:
            created = await evaluate_rules(session, now, source=provider.name, simulated=provider.simulated)
        await expire_suggestions(session, now)
    if claimed:
        log.info(
            "[SIM] weather.refreshed" if provider.simulated else "weather.refreshed",
            fetched=fetched,
            failed=failed,
            suggestions=created,
        )
    return {"fetched": fetched, "failed": failed, "suggestions": created}


# ---------------------------------------------------------------- rules → suggested alerts


async def effective_rules(session: AsyncSession) -> dict[int, dict[str, Rule]]:
    """Per gouvernorat, the rule of each metric: its own when defined, else the national one."""
    rules = list(await session.scalars(select(Rule)))
    national = {r.metric: r for r in rules if r.gouvernorat_code is None}
    codes = list(await session.scalars(select(Gouvernorat.code)))
    out: dict[int, dict[str, Rule]] = {}
    for code in codes:
        own = {r.metric: r for r in rules if r.gouvernorat_code == code}
        out[code] = {m: own.get(m) or national[m] for m in METRICS if (own.get(m) or national.get(m)) is not None}
    return out


def _value(metric: str, row: Any) -> float | None:
    if metric == "fire_danger":
        return None if row.fire_danger is None else float(fwi.DANGER_RANK[fwi.FireDanger(row.fire_danger)])
    if metric == "wind_gust":
        value = row.wind_gust_kmh
    elif metric == "rain_24h":
        value = row.precipitation_24h_mm
    else:
        value = row.precipitation_mm
    return None if value is None else float(value)


async def evaluate_rules(session: AsyncSession, now: datetime, *, source: str, simulated: bool) -> int:
    """Create suggested alerts for the gouvernorats where a rule is met in the next 24 h. Returns how many."""
    locked = await session.scalar(text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": _EVALUATE_LOCK})
    if not locked:
        return 0
    start = _hour(now)
    rows = (
        await session.execute(
            select(
                GridPoint.gouvernorat_code,
                GridPoint.lat,
                GridPoint.lon,
                Observation.at,
                Observation.fire_danger,
                Observation.fwi,
                Observation.wind_gust_kmh,
                Observation.precipitation_24h_mm,
                Observation.precipitation_mm,
            )
            .join(GridPoint, GridPoint.id == Observation.point_id)
            .where(
                Observation.at >= start,
                Observation.at <= start + RULE_WINDOW,
                GridPoint.gouvernorat_code.is_not(None),
            )
        )
    ).all()
    rules = await effective_rules(session)
    # (metric, severity) → gouvernorat → exceedances [(value, at, lat, lon, fwi)]
    hits: dict[tuple[str, str], dict[int, list[tuple[float, datetime, float, float, float | None]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    rule_of: dict[tuple[str, str], dict[int, Rule]] = defaultdict(dict)
    for row in rows:
        for metric, rule in rules.get(row.gouvernorat_code, {}).items():
            if not rule.enabled:
                continue
            value = _value(metric, row)
            if value is not None and value >= rule.threshold:
                hits[(metric, rule.severity)][row.gouvernorat_code].append((value, row.at, row.lat, row.lon, row.fwi))
                rule_of[(metric, rule.severity)][row.gouvernorat_code] = rule
    if not hits:
        return 0
    active = (
        await session.execute(
            select(AlertSuggestion.metric, AlertSuggestion.gouvernorat_codes).where(
                AlertSuggestion.status.in_(ACTIVE_STATUSES), AlertSuggestion.valid_until > now
            )
        )
    ).all()
    covered = {(m, code) for m, codes in active for code in codes}
    names = {g.code: g for g in await session.scalars(select(Gouvernorat))}
    created = 0
    for (metric, severity), by_code in sorted(hits.items()):
        codes = sorted(code for code in by_code if (metric, code) not in covered)
        if not codes:
            continue
        exceed = [hit for code in codes for hit in by_code[code]]
        peak = max(exceed, key=lambda h: h[0])
        valid_from = min(h[1] for h in exceed)
        valid_until = max(max(h[1] for h in exceed) + timedelta(hours=1), valid_from + timedelta(hours=3))
        title, body = texts.suggestion_texts(
            metric,
            peak[0],
            [names[c].name_ar for c in codes],
            [names[c].name_fr for c in codes],
            valid_from,
            valid_until,
        )
        evidence: dict[str, Any] = {
            "metric": metric,
            "thresholds": {str(c): rule_of[(metric, severity)][c].threshold for c in codes},
            "rule_ids": sorted({rule_of[(metric, severity)][c].id for c in codes}),
            "max_value": round(peak[0], 1),
            "peak_at": peak[1].isoformat(),
            "peak_point": {"lat": peak[2], "lon": peak[3]},
            "points_over_threshold": len({(h[2], h[3]) for h in exceed}),
            "hours_over_threshold": len({h[1] for h in exceed}),
            "window": {"from": start.isoformat(), "to": (start + RULE_WINDOW).isoformat()},
            "per_gouvernorat": {str(c): {"max_value": round(max(h[0] for h in by_code[c]), 1)} for c in codes},
            "source": source,
            metric: round(peak[0], 1),  # flat metric → value, as the dashboard also reads it
        }
        if metric == "fire_danger":
            evidence["max_value_label"] = texts.DANGER_LABELS[list(fwi.FireDanger)[int(peak[0])]]["en"]
            evidence["max_fwi"] = round(max(h[4] or 0.0 for h in exceed), 1)
        suggestion = AlertSuggestion(
            id=uuid.uuid4(),
            metric=metric,
            gouvernorat_codes=codes,
            hazard=texts.HAZARDS[metric],
            severity=severity,
            title=title,
            body=body,
            evidence=evidence,
            valid_from=valid_from,
            valid_until=valid_until,
            simulated=simulated,
        )
        session.add(suggestion)
        await session.flush()
        await session.refresh(suggestion)
        payload = {
            "suggestion_id": str(suggestion.id),
            "suggestion": suggestion_out(suggestion).model_dump(mode="json"),
        }
        await emit(session, "weather.suggestion", payload)
        created += 1
    return created


async def expire_suggestions(session: AsyncSession, now: datetime) -> None:
    await session.execute(
        update(AlertSuggestion)
        .where(AlertSuggestion.status == "pending", AlertSuggestion.valid_until <= now)
        .values(status="expired", updated_at=now)
    )


def suggestion_out(s: AlertSuggestion) -> schemas.SuggestionOut:
    return schemas.SuggestionOut(
        id=s.id,
        metric=s.metric,
        gouvernorat_codes=list(s.gouvernorat_codes),
        category="weather",
        hazard=s.hazard,
        severity=s.severity,
        title=s.title,
        body=s.body,
        evidence=s.evidence,
        valid_from=s.valid_from,
        valid_until=s.valid_until,
        status=s.status,
        created_at=s.created_at,
        decided_by=s.decided_by,
        decided_at=s.decided_at,
        dismiss_reason=s.dismiss_reason,
        simulated=s.simulated,
    )


def suggestion_visible(principal: Principal) -> Any:
    if principal.is_national:
        return True
    return literal(principal.gouvernorat_code) == any_(AlertSuggestion.gouvernorat_codes)


# ---------------------------------------------------------------- read side


async def nearest_point(session: AsyncSession, lat: float, lon: float) -> GridPoint | None:
    """The closest grid point with data, within WEATHER_MAX_DISTANCE_KM."""
    target = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    geography = cast(target, GridPoint.location.type)
    limit_m = get_settings().weather_max_distance_km * 1000
    point: GridPoint | None = await session.scalar(
        select(GridPoint)
        .where(GridPoint.fetched_at.is_not(None), func.ST_DWithin(GridPoint.location, geography, limit_m))
        .order_by(GridPoint.location.op("<->")(geography))
        .limit(1)
    )
    return point


async def series_of(session: AsyncSession, point_id: int, start: datetime, end: datetime) -> list[Observation]:
    rows = await session.scalars(
        select(Observation)
        .where(Observation.point_id == point_id, Observation.at >= start, Observation.at <= end)
        .order_by(Observation.at)
    )
    return list(rows)


def hour_out(o: Observation) -> schemas.HourOut:
    danger = None
    if o.fire_danger is not None and o.fwi is not None:
        danger = schemas.FireDangerOut.model_validate(
            {
                "class": o.fire_danger,
                "fwi": round(o.fwi, 1),
                "ffmc": _r(o.ffmc),
                "dmc": _r(o.dmc),
                "dc": _r(o.dc),
                "isi": _r(o.isi),
                "bui": _r(o.bui),
            }
        )
    return schemas.HourOut(
        time=o.at,
        temperature_c=_r(o.temperature_c),
        wind_speed_kmh=_r(o.wind_speed_kmh),
        wind_gust_kmh=_r(o.wind_gust_kmh),
        wind_direction_deg=None if o.wind_direction_deg is None else round(o.wind_direction_deg),
        relative_humidity_pct=None if o.relative_humidity_pct is None else round(o.relative_humidity_pct),
        precipitation_mm_h=_r(o.precipitation_mm),
        precipitation_24h_mm=_r(o.precipitation_24h_mm),
        fire_danger=danger,
        heavy_rain=schemas.HeavyRainOut(level=o.heavy_rain),
        weather_code=o.weather_code,
    )


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (haversine), km, one decimal."""
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return round(6371.0 * 2 * math.asin(math.sqrt(a)), 1)


def _r(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def current_of(rows: list[Observation], now: datetime) -> Observation | None:
    """The row of the current hour (or the latest one before it)."""
    hour = _hour(now)
    past = [o for o in rows if o.at <= hour]
    return past[-1] if past else (rows[0] if rows else None)


def attribution(simulated: bool) -> dict[str, str] | str:
    """Attribution of the shown data: the simulator's notice for simulated values, else the provider's."""
    return SIM_ATTRIBUTION if simulated else get_provider().attribution()


async def grid_features(
    session: AsyncSession, bbox: tuple[float, float, float, float] | None, at: datetime
) -> list[dict[str, Any]]:
    query = (
        select(GridPoint, Observation)
        .join(Observation, and_(Observation.point_id == GridPoint.id, Observation.at == at))
        .order_by(GridPoint.id)
    )
    if bbox is not None:
        min_lon, min_lat, max_lon, max_lat = bbox
        query = query.where(
            GridPoint.lon >= min_lon, GridPoint.lon <= max_lon, GridPoint.lat >= min_lat, GridPoint.lat <= max_lat
        )
    features = []
    for point, obs in (await session.execute(query)).all():
        props = hour_out(obs).model_dump(mode="json", by_alias=True)
        # Flat values for map styling: the class string, the FWI and the rain level (as the dashboard reads them).
        props |= {
            "fire_danger": obs.fire_danger,
            "fwi": _r(obs.fwi),
            "fire_indices": props["fire_danger"],
            "heavy_rain": obs.heavy_rain,
            "rain_level": obs.heavy_rain,
            "point_id": point.id,
            "gouvernorat_code": point.gouvernorat_code,
            "simulated": point.simulated,
        }
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [point.lon, point.lat]},
                "properties": props,
            }
        )
    return features


async def rules_list(session: AsyncSession, principal: Principal) -> list[Rule]:
    query = select(Rule).order_by(func.coalesce(Rule.gouvernorat_code, 0), Rule.metric)
    if not principal.is_national:
        query = query.where(or_(Rule.gouvernorat_code.is_(None), Rule.gouvernorat_code == principal.gouvernorat_code))
    return list(await session.scalars(query))


async def max_ahead(session: AsyncSession, point_id: int, now: datetime, hours: int) -> dict[str, float | None]:
    """Largest values of the next ``hours`` hours at a point (flood advisory, decision support)."""
    start = _hour(now)
    row = (
        await session.execute(
            select(
                func.max(Observation.precipitation_mm),
                func.sum(Observation.precipitation_mm),
                func.max(Observation.wind_gust_kmh),
                func.max(cast(Observation.fwi, Float)),
            ).where(
                Observation.point_id == point_id,
                Observation.at > start,
                Observation.at <= start + timedelta(hours=hours),
            )
        )
    ).one()
    return {"max_rain_1h": row[0], "rain_total": row[1], "max_gust": row[2], "max_fwi": row[3]}
