"""Coastal safety (phase L1b): the beaches, their marine weather, the daily drowning risk and the coastal alerts.

The worker (app/modules/coastal/worker.py) runs ``refresh`` every COASTAL_REFRESH_INTERVAL_S:

1. ``sync_beaches``: every place of the beaches layer (COASTAL_LAYER_KEY) gets a ``coastal.beach`` row, with the
   direction of the open sea computed once from the gouvernorat boundaries (16 bearings at 2 km, the ones outside
   the land averaged).
2. ``fetch_marine``: the beaches that are due get four days of hourly marine weather (a failure keeps the last values
   and retries later with a back-off).
3. ``compute``: the risk of every beach for today and the next three days (Tunis time), from the marine weather, the
   nearest point of the weather grid (phase 7), the beach card and the drownings reported within 500 m.
4. A beach that turns yellow or red today opens a coastal alert for the rooms of its gouvernorat (live event
   ``coastal.alert``), once per beach, day and level.
"""

import dataclasses
import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import structlog
from sqlalchemy import and_, delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import events
from app.core.config import get_settings
from app.modules.coastal import marine, risk, shadow
from app.modules.coastal.models import Beach, BeachDay, CoastalAlert, CoastalSettings, MarineHour, Presence
from app.modules.geo.models import Layer, LayerFeature
from app.modules.layers.service import LAT, LON
from app.modules.programmes import service as programmes
from app.modules.reports.domain import Category, Status
from app.modules.reports.models import Report
from app.modules.weather import service as weather
from app.modules.weather.models import Observation

log = structlog.get_logger()

FORECAST_DAYS = 4
TUNIS = timedelta(hours=1)  # Africa/Tunis, UTC+1 all year
SEAWARD_SQL = text(
    """
    UPDATE coastal.beach c SET seaward_deg = s.deg
    FROM (
        SELECT b.feature_id,
               CASE WHEN count(d.deg) BETWEEN 1 AND 15
                    THEN mod(CAST(degrees(atan2(sum(sin(radians(d.deg))), sum(cos(radians(d.deg))))) AS numeric)
                             + 360, 360)
               END AS deg
        FROM coastal.beach b
        JOIN geo.layer_feature f ON f.id = b.feature_id
        LEFT JOIN LATERAL (
            SELECT a * 22.5 AS deg
            FROM generate_series(0, 15) a
            WHERE NOT EXISTS (
                SELECT 1 FROM geo.gouvernorat g
                WHERE g.boundary IS NOT NULL
                  AND ST_Intersects(g.boundary, CAST(ST_Project(f.location, 2000, radians(a * 22.5)) AS geometry)))
        ) d ON true
        WHERE b.feature_id = ANY(:ids)
        GROUP BY b.feature_id
    ) s
    WHERE c.feature_id = s.feature_id
    """
)


def today_in_tunis(now: datetime) -> date:
    return (now + TUNIS).date()


async def beach_layer(session: AsyncSession) -> Layer | None:
    layer: Layer | None = await session.scalar(
        select(Layer).where(Layer.key == get_settings().coastal_layer_key, Layer.deleted_at.is_(None))
    )
    return layer


async def rules(session: AsyncSession) -> dict[str, Any]:
    row = await session.get(CoastalSettings, 1)
    return risk.rules_of(row.rules if row else None)


# ---------------------------------------------------------------- refresh


async def sync_beaches(session: AsyncSession) -> int:
    """A ``coastal.beach`` row for every place of the beaches layer; returns how many were added."""
    layer = await beach_layer(session)
    if layer is None:
        return 0
    missing = (
        await session.scalars(
            select(LayerFeature.id).where(
                LayerFeature.layer_id == layer.id,
                LayerFeature.deleted_at.is_(None),
                ~select(Beach.feature_id).where(Beach.feature_id == LayerFeature.id).exists(),
            )
        )
    ).all()
    if not missing:
        return 0
    await session.execute(
        insert(Beach)
        .values([{"feature_id": i, "next_fetch_at": datetime(2000, 1, 1, tzinfo=UTC)} for i in missing])
        .on_conflict_do_nothing()
    )
    await session.execute(SEAWARD_SQL, {"ids": list(missing)})
    return len(missing)


@dataclass(frozen=True, slots=True)
class _Due:
    feature_id: uuid.UUID
    lat: float
    lon: float
    attempts: int


async def fetch_marine(session: AsyncSession, now: datetime) -> int:
    """Fetch the marine weather of the beaches that are due. Returns the number of beaches updated."""
    settings = get_settings()
    provider = marine.get_provider()
    layer = await beach_layer(session)
    if layer is None:
        return 0
    rows = (
        await session.execute(
            select(Beach.feature_id, LAT, LON, Beach.attempts)
            .join(LayerFeature, LayerFeature.id == Beach.feature_id)
            .where(Beach.next_fetch_at <= now, LayerFeature.deleted_at.is_(None), LayerFeature.layer_id == layer.id)
            .order_by(Beach.next_fetch_at, Beach.feature_id)
            .limit(settings.coastal_max_beaches_per_cycle)
        )
    ).all()
    due = [_Due(r[0], float(r[1]), float(r[2]), int(r[3])) for r in rows]
    updated = 0
    start = datetime.combine(now.date(), time(0), UTC)
    for i in range(0, len(due), marine.BATCH):
        batch = due[i : i + marine.BATCH]
        try:
            series = await provider.fetch([(b.lat, b.lon) for b in batch], FORECAST_DAYS)
        except marine.MarineRateLimited:
            await _failed(session, batch, now)
            break
        except marine.MarineUnavailable as exc:
            log.warning("coastal.marine_unavailable", reason=str(exc), beaches=len(batch))
            await _failed(session, batch, now)
            continue
        for beach, hours in zip(batch, series, strict=True):
            values = [
                {
                    "feature_id": beach.feature_id,
                    "at": h.at,
                    "wave_height_m": h.wave_height_m,
                    "wave_period_s": h.wave_period_s,
                    "wave_direction_deg": h.wave_direction_deg,
                    "sea_temp_c": h.sea_temp_c,
                    "current_kmh": h.current_kmh,
                    "current_direction_deg": h.current_direction_deg,
                }
                for h in hours
                if h.at >= start
            ]
            if values:
                stmt = insert(MarineHour).values(values)
                await session.execute(
                    stmt.on_conflict_do_update(
                        index_elements=[MarineHour.feature_id, MarineHour.at],
                        set_={c: stmt.excluded[c] for c in values[0] if c not in ("feature_id", "at")},
                    )
                )
            await session.execute(
                update(Beach)
                .where(Beach.feature_id == beach.feature_id)
                .values(
                    fetched_at=now,
                    next_fetch_at=now + timedelta(seconds=settings.coastal_refresh_interval_s),
                    attempts=0,
                    source=provider.name,
                    simulated=provider.simulated,
                )
            )
            updated += 1
    # Hours older than yesterday are no longer read.
    await session.execute(delete(MarineHour).where(MarineHour.at < start - timedelta(days=1)))
    return updated


async def _failed(session: AsyncSession, batch: list[_Due], now: datetime) -> None:
    for beach in batch:
        pause = timedelta(minutes=min(15 * 2**beach.attempts, 360))
        await session.execute(
            update(Beach)
            .where(Beach.feature_id == beach.feature_id)
            .values(next_fetch_at=now + pause, attempts=min(beach.attempts + 1, 10))
        )


def _bathing(day: date, rules: dict[str, Any]) -> tuple[datetime, datetime]:
    """The bathing hours of a day (Tunis time) in UTC, end exclusive."""
    first = datetime.combine(day, time(int(rules["first_hour"])), UTC) - TUNIS
    last = datetime.combine(day, time(int(rules["last_hour"])), UTC) - TUNIS
    return first, last + timedelta(hours=1)


def _max(values: list[float | None]) -> float | None:
    found = [v for v in values if v is not None]
    return max(found) if found else None


_YES = {"true", "yes", "1", "oui", "نعم", "محروس"}
_NO = {"false", "no", "0", "non", "لا", "غير محروس"}


def flag(value: Any) -> bool | None:
    """A yes/no column of a beach card as imported (files carry text: "True", "oui", "نعم"...); None when unknown."""
    if isinstance(value, bool):
        return value
    text_value = str(value).strip().lower() if value is not None else ""
    if text_value in _YES:
        return True
    if text_value in _NO:
        return False
    return None


def day_inputs(
    day: date,
    rules: dict[str, Any],
    marine_hours: list[MarineHour],
    weather_hours: list[Observation],
    seaward_deg: float | None,
    props: dict[str, Any],
    incidents: int,
) -> risk.DayInputs:
    first, end = _bathing(day, rules)
    sea = [h for h in marine_hours if first <= h.at < end]
    air = [h for h in weather_hours if first <= h.at < end]
    onshore = [
        h for h in air if h.wind_speed_kmh is not None and risk.is_onshore(h.wind_direction_deg, seaward_deg, rules)
    ]
    strongest = max(onshore, key=lambda h: h.wind_speed_kmh or 0.0) if onshore else None
    guarded = props.get("guarded")
    crowd = props.get("crowd")
    return risk.DayInputs(
        day=day,
        wave_height_m=_max([h.wave_height_m for h in sea]),
        current_kmh=_max([h.current_kmh for h in sea]),
        sea_temp_c=_max([h.sea_temp_c for h in sea]),
        max_temperature_c=_max([h.temperature_c for h in air]),
        onshore_wind_kmh=strongest.wind_speed_kmh if strongest else (0.0 if air and seaward_deg is not None else None),
        onshore_wind_from_deg=strongest.wind_direction_deg if strongest else None,
        max_wind_kmh=_max([h.wind_speed_kmh for h in air]),
        crowd=crowd if crowd in ("high", "medium", "low") else None,
        guarded=flag(guarded),
        incidents=incidents,
    )


async def _incidents(
    session: AsyncSession, feature_ids: list[uuid.UUID], rules: dict[str, Any], now: datetime
) -> dict[uuid.UUID, int]:
    since = now - timedelta(days=365 * int(rules["incident_years"]))
    rows = (
        await session.execute(
            select(LayerFeature.id, func.count(Report.id))
            .join(
                Report,
                and_(
                    Report.category == Category.DROWNING.value,
                    Report.status != Status.REJECTED.value,
                    Report.created_at >= since,
                    func.ST_DWithin(Report.location, LayerFeature.location, float(rules["incident_radius_m"])),
                ),
            )
            .where(LayerFeature.id.in_(feature_ids))
            .group_by(LayerFeature.id)
        )
    ).all()
    return {r[0]: int(r[1]) for r in rows}


async def compute(session: AsyncSession, now: datetime) -> int:
    """The risk of every beach for today and the next three days; opens today's alerts. Returns the rows written."""
    layer = await beach_layer(session)
    if layer is None:
        return 0
    rule_set = await rules(session)
    beaches = (
        await session.execute(
            select(Beach, LayerFeature, LAT, LON)
            .join(LayerFeature, LayerFeature.id == Beach.feature_id)
            .where(LayerFeature.layer_id == layer.id, LayerFeature.deleted_at.is_(None))
        )
    ).all()
    if not beaches:
        return 0
    today = today_in_tunis(now)
    days = [today + timedelta(days=d) for d in range(FORECAST_DAYS)]
    window_start, _ = _bathing(days[0], rule_set)
    _, window_end = _bathing(days[-1], rule_set)
    incidents = await _incidents(session, [b[0].feature_id for b in beaches], rule_set, now)
    model = await shadow.latest(session)
    previous = {
        r.feature_id: r.level for r in (await session.scalars(select(BeachDay).where(BeachDay.day == today))).all()
    }
    marine_rows = (
        await session.scalars(select(MarineHour).where(MarineHour.at >= window_start, MarineHour.at < window_end))
    ).all()
    by_beach: dict[uuid.UUID, list[MarineHour]] = {}
    for h in marine_rows:
        by_beach.setdefault(h.feature_id, []).append(h)
    grid_cache: dict[int | None, list[Observation]] = {}
    written = 0
    for beach, feature, lat, lon in beaches:
        point = await weather.nearest_point(session, float(lat), float(lon))
        key = point.id if point else None
        if key not in grid_cache:
            grid_cache[key] = await weather.series_of(session, key, window_start, window_end) if key else []
        weather_hours = grid_cache[key]
        simulated = beach.simulated or bool(point is not None and point.simulated)
        sources = sorted({s for s in (beach.source, point.source if point else None) if s})
        for day in days:
            inputs = day_inputs(
                day,
                rule_set,
                by_beach.get(beach.feature_id, []),
                weather_hours,
                beach.seaward_deg,
                feature.props or {},
                incidents.get(beach.feature_id, 0),
            )
            guarded_by = await programmes.guarded_near(session, float(lat), float(lon), day)
            if guarded_by is not None:
                inputs = dataclasses.replace(inputs, guarded=True)
            assessed = risk.assess(inputs, rule_set)
            shadowed = shadow.assess(model, inputs, rule_set)
            stmt = insert(BeachDay).values(
                feature_id=beach.feature_id,
                day=day,
                score=assessed.score,
                level=assessed.level,
                factors=assessed.factors,
                inputs={**inputs.as_dict(), "guarded_by": guarded_by},
                source=",".join(sources) or None,
                simulated=simulated,
                computed_at=now,
                **shadowed,
            )
            await session.execute(
                stmt.on_conflict_do_update(
                    index_elements=[BeachDay.feature_id, BeachDay.day],
                    set_={
                        "score": stmt.excluded.score,
                        "level": stmt.excluded.level,
                        "factors": stmt.excluded.factors,
                        "inputs": stmt.excluded.inputs,
                        "source": stmt.excluded.source,
                        "simulated": stmt.excluded.simulated,
                        "computed_at": stmt.excluded.computed_at,
                        "shadow_p": stmt.excluded.shadow_p,
                        "shadow_level": stmt.excluded.shadow_level,
                        "shadow_version": stmt.excluded.shadow_version,
                    },
                )
            )
            written += 1
            if day == today and assessed.level in ("yellow", "red"):
                await _open_alert(session, feature, today, assessed, previous.get(beach.feature_id), simulated)
    return written


async def _open_alert(
    session: AsyncSession,
    feature: LayerFeature,
    day: date,
    assessed: risk.Risk,
    previous: str | None,
    simulated: bool,
) -> None:
    alert_id = uuid.uuid4()
    result = await session.execute(
        insert(CoastalAlert)
        .values(
            id=alert_id,
            feature_id=feature.id,
            day=day,
            level=assessed.level,
            previous_level=previous,
            score=assessed.score,
            gouvernorat_code=feature.gouvernorat_code,
            simulated=simulated,
        )
        .on_conflict_do_nothing(constraint="uq_coastal_alert")
        .returning(CoastalAlert.id)
    )
    if result.scalar_one_or_none() is None:
        return
    await events.emit(
        session,
        "coastal.alert",
        {
            "id": str(alert_id),
            "feature_id": str(feature.id),
            "name": feature.name,
            "level": assessed.level,
            "score": assessed.score,
            "day": day.isoformat(),
            "gouvernorat_code": feature.gouvernorat_code,
            "gouvernorat_codes": [feature.gouvernorat_code] if feature.gouvernorat_code else [],
            "simulated": simulated,
        },
    )


async def refresh(sessionmaker: async_sessionmaker[AsyncSession], now: datetime | None = None) -> dict[str, int]:
    """One cycle of the coastal worker (system scope)."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        added = await sync_beaches(session)
        await session.commit()
    async with sessionmaker() as session:
        fetched = await fetch_marine(session, now)
        await session.commit()
    async with sessionmaker() as session:
        written = await compute(session, now)
        await session.commit()
    return {"added": added, "fetched": fetched, "days": written}


# ---------------------------------------------------------------- presence (anonymous counts)

PRESENCE_WINDOW = timedelta(minutes=30)


def token_hash(token: str, day: date) -> bytes:
    """A keyed hash of the phone's random token, with a key that changes every day: rows of two days cannot be linked,
    and the token itself is never stored."""
    key = hashlib.sha256(get_settings().field_encryption_key.get_secret_value().encode() + day.isoformat().encode())
    return hmac.new(key.digest(), token.encode(), hashlib.sha256).digest()


async def record_presence(session: AsyncSession, feature_id: uuid.UUID, token: str, now: datetime) -> None:
    stmt = insert(Presence).values(feature_id=feature_id, token_hash=token_hash(token, today_in_tunis(now)), at=now)
    await session.execute(
        stmt.on_conflict_do_update(index_elements=[Presence.feature_id, Presence.token_hash], set_={"at": now})
    )


async def presence_counts(session: AsyncSession, now: datetime) -> dict[uuid.UUID, int]:
    rows = (
        await session.execute(
            select(Presence.feature_id, func.count())
            .where(Presence.at >= now - PRESENCE_WINDOW)
            .group_by(Presence.feature_id)
        )
    ).all()
    return {r[0]: int(r[1]) for r in rows}
