"""Aggregates over reports and interventions: overview, trends with a seasonal baseline, hexagon hotspots.

Every query is restricted to the caller's gouvernorat scope before it runs (national roles see all). Aggregates only:
counts, durations and areas; never a name, a phone number or a single report position (hotspots are hexagons).
Days, hours and weekdays are those of Africa/Tunis.
"""

import base64
import json
import math
import statistics
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Literal

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import Principal
from app.modules.analytics import domain, schemas

Interval = Literal["day", "week", "month"]
Metric = Literal["reports", "response_time", "interventions"]
# Years looked back for the seasonal baseline; at least two of them must have data for a band to show.
BASELINE_YEARS = 5
BASELINE_MIN_YEARS = 2
MAX_POINTS = {"day": 400, "week": 260, "month": 120}
DEFAULT_SPAN = {"day": timedelta(days=30), "week": timedelta(weeks=26), "month": timedelta(days=365)}
HEX_MIN_KM, HEX_MAX_KM = 1.0, 50.0


# ---------------------------------------------------------------- scope and parameters


def resolve_scope(principal: Principal, requested: list[int] | None) -> list[int]:
    """Gouvernorats a query covers: ``[]`` means national (national roles only). A regional caller gets their own
    gouvernorat by default and a 403 ``out_of_scope`` for any other."""
    codes = sorted(set(requested or []))
    if principal.is_national:
        return codes
    own = principal.gouvernorat_code
    assert own is not None
    if not codes:
        return [own]
    if any(c != own for c in codes):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
    return codes


def in_scope(principal: Principal, gouvernorats: list[int]) -> bool:
    """A stored object covering ``gouvernorats`` ([] = national) is visible to the caller."""
    if principal.is_national:
        return True
    return bool(gouvernorats) and all(principal.can_access_gouvernorat(c) for c in gouvernorats)


def period(raw_from: date | None, raw_to: date | None, default_span: timedelta) -> tuple[date, date]:
    to = raw_to or domain.local_today()
    start = raw_from or (to - default_span + timedelta(days=1))
    if start > to:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_period")
    if (to - start).days + 1 > get_settings().analytics_max_period_days:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "period_too_long")
    return start, to


def encode_cursor(at: datetime, item_id: uuid.UUID | int) -> str:
    return base64.urlsafe_b64encode(f"{at.isoformat()}|{item_id}".encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        at, item_id = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode().split("|", 1)
        return datetime.fromisoformat(at), item_id
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc


def _report_filter(codes: list[int], category: str | None, alias: str = "r") -> tuple[str, dict[str, Any]]:
    """SQL condition on ``reports.report`` (alias ``r``) for a scope and an optional category."""
    clauses: list[str] = ["TRUE"]
    params: dict[str, Any] = {}
    if codes:
        clauses.append(f"{alias}.gouvernorat_code = ANY(CAST(:codes AS smallint[]))")
        params["codes"] = codes
    if category:
        clauses.append(f"{alias}.category = :category")
        params["category"] = category
    return " AND ".join(clauses), params


def _incident_filter(codes: list[int], category: str | None) -> tuple[str, dict[str, Any]]:
    """SQL condition on ``ops.incident`` (alias ``i``): led by, or with the participation of, the gouvernorats."""
    clauses: list[str] = ["TRUE"]
    params: dict[str, Any] = {}
    if codes:
        clauses.append(
            "(i.gouvernorat_code = ANY(CAST(:codes AS smallint[])) OR EXISTS (SELECT 1 "
            "FROM ops.incident_gouvernorat ig WHERE ig.incident_id = i.id "
            "AND ig.gouvernorat_code = ANY(CAST(:codes AS smallint[]))))"
        )
        params["codes"] = codes
    if category:
        clauses.append("i.category = :category")
        params["category"] = category
    return " AND ".join(clauses), params


def _bounds(start: date, end: date) -> dict[str, datetime]:
    return {"t0": domain.day_start(start), "t1": domain.day_start(end + timedelta(days=1))}


# ---------------------------------------------------------------- overview

_LOCAL = "(r.received_at AT TIME ZONE 'Africa/Tunis')"

# Stage times of each report: first resource or volunteer ordered on its incident, first arrival on scene, closure.
# Orders given before the report arrived (a report joining a running incident) do not count as its response.
_STAGES_SQL = """
    WITH t AS (
        SELECT r.received_at,
            (SELECT min(a.created_at) FROM ops.assignment a
              WHERE a.incident_id = r.incident_id AND a.created_at >= r.received_at) AS assigned,
            (SELECT min(a.on_scene_at) FROM ops.assignment a
              WHERE a.incident_id = r.incident_id AND a.on_scene_at >= r.received_at) AS on_scene,
            (SELECT min(h.at) FROM reports.status_history h
              WHERE h.report_id = r.id AND h.status = 'closed' AND h.at >= r.received_at) AS closed
        FROM reports.report r
        WHERE r.received_at >= :t0 AND r.received_at < :t1 AND {where}
    )
    SELECT
        avg(extract(epoch FROM assigned - received_at)),
        percentile_cont(0.9) WITHIN GROUP (ORDER BY extract(epoch FROM assigned - received_at)),
        count(assigned),
        avg(extract(epoch FROM on_scene - received_at)),
        percentile_cont(0.9) WITHIN GROUP (ORDER BY extract(epoch FROM on_scene - received_at)),
        count(on_scene),
        avg(extract(epoch FROM closed - received_at)),
        percentile_cont(0.9) WITHIN GROUP (ORDER BY extract(epoch FROM closed - received_at)),
        count(closed)
    FROM t
"""

_GROUPS = {
    "category": "r.category",
    "gouvernorat": "r.gouvernorat_code",
    "status": "r.status",
    "source": "r.source",
    "hour": f"CAST(extract(hour FROM {_LOCAL}) AS int)",
    "weekday": f"CAST(extract(isodow FROM {_LOCAL}) AS int)",
}


def _stage(mean: Any, p90: Any, n: Any) -> schemas.Stage:
    return schemas.Stage(
        mean_s=round(float(mean), 1) if mean is not None else None,
        p90_s=round(float(p90), 1) if p90 is not None else None,
        n=int(n or 0),
    )


async def overview(
    session: AsyncSession, codes: list[int], category: str | None, start: date, end: date
) -> schemas.Overview:
    where, params = _report_filter(codes, category)
    params |= _bounds(start, end)
    groups: dict[str, list[schemas.KeyCount]] = {}
    for name, expression in _GROUPS.items():
        rows = await session.execute(
            text(
                f"SELECT {expression} AS k, count(*) FROM reports.report r "  # noqa: S608 (constant SQL fragments, values are bound)
                f"WHERE r.received_at >= :t0 AND r.received_at < :t1 AND {where} GROUP BY k ORDER BY count(*) DESC, k"
            ),
            params,
        )
        # Reports not located yet have no gouvernorat (phase 9 §4): "unverified", which only national queries see.
        missing = "unverified" if name == "gouvernorat" else "unknown"
        groups[name] = [schemas.KeyCount(key=k if k is not None else missing, count=int(n)) for k, n in rows.all()]
    by_status = {str(g.key): g.count for g in groups["status"]}
    stages = (await session.execute(text(_STAGES_SQL.format(where=where)), params)).one()
    incident_where, incident_params = _incident_filter(codes, category)
    lead = "i.gouvernorat_code = ANY(CAST(:codes AS smallint[]))" if codes else "TRUE"
    incident_rows = await session.execute(
        text(
            f"SELECT NOT ({lead}) AS participating, count(*) FROM ops.incident i "  # noqa: S608 (constant SQL fragments, values are bound)
            f"WHERE i.opened_at >= :t0 AND i.opened_at < :t1 AND {incident_where} GROUP BY 1 ORDER BY 1"
        ),
        incident_params | _bounds(start, end),
    )
    return schemas.Overview(
        from_=start,
        to=end,
        gouvernorats=codes,
        category=category,
        totals=schemas.Totals(
            received=sum(by_status.values()),
            verified=sum(by_status.get(s.value, 0) for s in domain.VERIFIED_STATUSES),
            in_progress=sum(by_status.get(s.value, 0) for s in domain.IN_PROGRESS_STATUSES),
            closed=by_status.get("closed", 0),
            rejected=by_status.get("rejected", 0),
        ),
        response_time=schemas.ResponseTimes(
            to_assignment=_stage(*stages[0:3]),
            to_on_scene=_stage(*stages[3:6]),
            to_closed=_stage(*stages[6:9]),
        ),
        by_category=groups["category"],
        by_gouvernorat=groups["gouvernorat"],
        by_status=groups["status"],
        by_source=groups["source"],
        by_hour=sorted(groups["hour"], key=lambda g: int(g.key)),
        by_weekday=sorted(groups["weekday"], key=lambda g: int(g.key)),
        incidents=[schemas.IncidentCount(participating=bool(p), count=int(n)) for p, n in incident_rows.all()],
        min_cell=get_settings().analytics_min_cell,
    )


# ---------------------------------------------------------------- trends


def bucket_of(day: date, interval: Interval) -> date:
    if interval == "day":
        return day
    if interval == "week":
        return day - timedelta(days=day.isoweekday() - 1)
    return day.replace(day=1)


def shift_back(bucket: date, interval: Interval, years: int) -> date:
    """The same period ``years`` years earlier: same weekday 52 weeks back for days and weeks, same month."""
    if interval == "month":
        month = bucket.month - 1 - 12 * years
        return date(bucket.year + month // 12, month % 12 + 1, 1)
    return bucket - timedelta(weeks=52 * years)


def _next_bucket(bucket: date, interval: Interval) -> date:
    if interval == "day":
        return bucket + timedelta(days=1)
    if interval == "week":
        return bucket + timedelta(weeks=1)
    return date(bucket.year + bucket.month // 12, bucket.month % 12 + 1, 1)


def buckets_between(start: date, end: date, interval: Interval) -> list[date]:
    out, current = [], bucket_of(start, interval)
    while current <= end:
        out.append(current)
        current = _next_bucket(current, interval)
    return out


def _series_sql(metric: Metric, interval: Interval, where: str) -> str:
    if metric == "interventions":
        # Resources ordered on incidents (cancelled orders excluded), scoped by the incident's lead gouvernorat or the
        # gouvernorats taking part in it (phase 9).
        local = "(a.created_at AT TIME ZONE 'Africa/Tunis')"
        return (
            f"SELECT CAST(date_trunc('{interval}', {local}) AS date) AS b, CAST(count(*) AS float8) "  # noqa: S608 (constant SQL fragments, values are bound)
            "FROM ops.assignment a JOIN ops.incident i ON i.id = a.incident_id "
            f"WHERE a.kind = 'resource' AND a.status <> 'cancelled' AND a.created_at >= :t0 AND a.created_at < :t1 "
            f"AND {where} GROUP BY b"
        )
    if metric == "response_time":
        return (
            f"SELECT CAST(date_trunc('{interval}', {_LOCAL}) AS date) AS b, "  # noqa: S608 (constant SQL fragments, values are bound)
            "avg(extract(epoch FROM (SELECT min(a.created_at) FROM ops.assignment a "
            "WHERE a.incident_id = r.incident_id AND a.created_at >= r.received_at) - r.received_at)) "
            f"FROM reports.report r WHERE r.received_at >= :t0 AND r.received_at < :t1 AND {where} GROUP BY b"
        )
    return (
        f"SELECT CAST(date_trunc('{interval}', {_LOCAL}) AS date) AS b, CAST(count(*) AS float8) "  # noqa: S608 (constant SQL fragments, values are bound)
        f"FROM reports.report r WHERE r.received_at >= :t0 AND r.received_at < :t1 AND {where} GROUP BY b"
    )


def _first_data_sql(metric: Metric, where: str) -> str:
    if metric == "interventions":
        return (
            "SELECT min(a.created_at) FROM ops.assignment a JOIN ops.incident i ON i.id = a.incident_id "  # noqa: S608 (constant SQL fragments, values are bound)
            f"WHERE a.kind = 'resource' AND {where}"
        )
    return f"SELECT min(r.received_at) FROM reports.report r WHERE {where}"  # noqa: S608 (constant SQL fragments, values are bound)


def seasonal_point(
    values: dict[date, float],
    bucket: date,
    interval: Interval,
    first_bucket: date | None,
    zero_when_missing: bool,
) -> tuple[float | None, float | None, float | None, float | None]:
    """(last_year, expected, low, high) of one period from the same periods of previous years.

    A previous year counts only when the platform already had data then (``first_bucket``); a count missing in such a
    year is a zero, a mean (response time) is skipped. The band is mean ± 1.96 standard deviations (≥ 0), shown only
    from two qualifying years on."""
    history: list[float] = []
    last_year: float | None = None
    for years in range(1, BASELINE_YEARS + 1):
        past = shift_back(bucket, interval, years)
        if first_bucket is None or past < first_bucket:
            continue
        value = values.get(past, 0.0 if zero_when_missing else None)
        if years == 1:
            last_year = value
        if value is not None:
            history.append(value)
    if len(history) < BASELINE_MIN_YEARS:
        return last_year, None, None, None
    mean = statistics.fmean(history)
    spread = 1.96 * statistics.stdev(history)
    return last_year, round(mean, 2), round(max(0.0, mean - spread), 2), round(mean + spread, 2)


async def trends(
    session: AsyncSession,
    codes: list[int],
    category: str | None,
    metric: Metric,
    interval: Interval,
    start: date,
    end: date,
) -> schemas.Trend:
    periods = buckets_between(start, end, interval)
    if len(periods) > MAX_POINTS[interval]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "period_too_long")
    # Interventions are scoped by their incident (alias i), reports and response times by the report (alias r).
    where, params = _incident_filter(codes, category) if metric == "interventions" else _report_filter(codes, category)
    history_start = shift_back(periods[0], interval, BASELINE_YEARS)
    params |= _bounds(history_start, end)
    rows = await session.execute(text(_series_sql(metric, interval, where)), params)
    values = {b: float(v) for b, v in rows.all() if v is not None}
    first_at = await session.scalar(text(_first_data_sql(metric, where)), params)
    first_bucket = bucket_of(first_at.astimezone(domain.TUNIS_TZ).date(), interval) if first_at else None
    counts = metric != "response_time"
    points: list[schemas.TrendPoint] = []
    for bucket in periods:
        last_year, expected, low, high = seasonal_point(values, bucket, interval, first_bucket, counts)
        value = values.get(bucket, 0.0 if counts and first_bucket and bucket >= first_bucket else None)
        points.append(
            schemas.TrendPoint(
                period_start=bucket,
                value=round(value, 1) if value is not None else None,
                last_year=round(last_year, 1) if last_year is not None else None,
                expected=expected,
                low=low,
                high=high,
            )
        )
    years = 0
    if first_bucket is not None:
        years = sum(1 for y in range(1, BASELINE_YEARS + 1) if shift_back(periods[-1], interval, y) >= first_bucket)
    return schemas.Trend(
        metric=metric,
        interval=interval,
        unit="seconds" if metric == "response_time" else "count",
        from_=start,
        to=end,
        gouvernorats=codes,
        category=category,
        points=points,
        baseline_available=any(p.expected is not None for p in points),
        history_years=years,
    )


# ---------------------------------------------------------------- hotspots

# Hexagons of a fixed grid in Web Mercator (ST_HexagonGrid tiles from the origin, so a cell keeps its i:j across
# requests); a report on a shared edge is counted once (the hexagon of smallest i, j).
_HOTSPOTS_SQL = """
    WITH pts AS (
        SELECT r.id, ST_Transform(CAST(r.location AS geometry), 3857) AS g FROM reports.report r
        WHERE r.received_at >= :t0 AND r.received_at < :t1 AND {where}
    ), ext AS (
        SELECT ST_SetSRID(CAST(ST_Extent(g) AS geometry), 3857) AS box FROM pts
    ), cells AS (
        SELECT DISTINCT ON (p.id) p.id, h.i, h.j, h.geom
        FROM ext, ST_HexagonGrid(:size, ext.box) AS h
        JOIN pts p ON ST_Intersects(h.geom, p.g)
        WHERE ext.box IS NOT NULL
        ORDER BY p.id, h.i, h.j
    )
    SELECT i, j, count(*) AS n, ST_AsGeoJSON(ST_Transform(geom, 4326), 6) AS shape
    FROM cells GROUP BY i, j, geom ORDER BY n DESC, i, j
"""


def hex_size_m(size_km: float, lat: float = 34.0) -> float:
    """Web Mercator stretches distances by 1/cos(latitude): the grid size that gives ``size_km`` on the ground
    around Tunisia (edge to edge of a hexagon is about the requested size)."""
    return size_km * 1000.0 / math.cos(math.radians(lat))


async def hotspots(
    session: AsyncSession, codes: list[int], category: str | None, start: date, end: date, size_km: float
) -> dict[str, Any]:
    where, params = _report_filter(codes, category)
    params |= _bounds(start, end) | {"size": hex_size_m(size_km)}

    rows = (await session.execute(text(_HOTSPOTS_SQL.format(where=where)), params)).all()
    features = [
        {
            "type": "Feature",
            "geometry": json.loads(shape),
            "properties": {"id": f"{i}:{j}", "count": int(n)},
        }
        for i, j, n, shape in rows
    ]
    return {
        "type": "FeatureCollection",
        "features": features,
        "cell_size_m": round(size_km * 1000.0),
        "from": start.isoformat(),
        "to": end.isoformat(),
        "gouvernorats": codes,
        "category": category,
    }


# ---------------------------------------------------------------- gouvernorat names


async def gouvernorat_names(session: AsyncSession) -> dict[int, dict[str, str]]:
    rows = await session.execute(text("SELECT code, name_ar, name_fr, name_en FROM geo.gouvernorat"))
    return {int(code): {"ar": ar, "fr": fr, "en": en} for code, ar, fr, en in rows.all()}
