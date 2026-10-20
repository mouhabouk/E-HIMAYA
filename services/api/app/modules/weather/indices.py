"""Derived indices of an hourly series (pure functions): 24 h rain, heavy-rain level, daily fire weather indices.

The FWI System is a daily system: each day's codes come from the noon local standard time values (Tunisia keeps
UTC+1 all year, so 11:00 UTC) and the rain of the 24 h before (Van Wagner 1987). Every hour of a local day carries
that day's indices; hours of a day whose noon is not in the series carry the previous day's. The moisture codes are
carried from day to day in ``weather.grid_point.codes``; only days whose noon is past are folded into it.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from app.modules.weather import fwi
from app.modules.weather.provider import Hour

TUNIS_OFFSET = timedelta(hours=1)
NOON_UTC_HOUR = 11

# Heavy-rain levels (mm in 1 h, mm in 24 h). "warning" matches the default alert rules of the contract
# (rain_1h ≥ 20, rain_24h ≥ 50); "watch" is half of it, to give notice.
RAIN_WARNING = (20.0, 50.0)
RAIN_WATCH = (10.0, 30.0)
RAIN_LEVELS = ("none", "watch", "warning")


def local_date(at: datetime) -> date:
    return (at.astimezone(UTC) + TUNIS_OFFSET).date()


def heavy_rain_level(rain_1h: float | None, rain_24h: float | None) -> str:
    one, day = rain_1h or 0.0, rain_24h or 0.0
    if one >= RAIN_WARNING[0] or day >= RAIN_WARNING[1]:
        return "warning"
    if one >= RAIN_WATCH[0] or day >= RAIN_WATCH[1]:
        return "watch"
    return "none"


@dataclass(frozen=True, slots=True)
class Row:
    hour: Hour
    precipitation_24h_mm: float | None
    heavy_rain: str
    indices: fwi.Indices | None


@dataclass(frozen=True, slots=True)
class Result:
    rows: list[Row]
    # Indices of the last past noon, and its local date (None: nothing new to fold in).
    last_past: fwi.Indices | None
    last_past_date: date | None
    daily: dict[date, fwi.Indices]


def rain_24h(hours: list[Hour]) -> list[float | None]:
    """Sum of the 24 hourly amounts ending at each hour (None until 24 h of history are present)."""
    by_time = {h.at: h.precipitation_mm for h in hours}
    out: list[float | None] = []
    for h in hours:
        window = [by_time.get(h.at - timedelta(hours=k)) for k in range(24)]
        out.append(None if any(v is None for v in window) else round(sum(v or 0.0 for v in window), 1))
    return out


def compute(
    hours: list[Hour], lat: float, previous: fwi.Indices | None, previous_date: date | None, now: datetime
) -> Result:
    """``previous``: the indices of ``previous_date`` (the last day already folded in), None at the first fetch."""
    hours = sorted(hours, key=lambda h: h.at)
    totals = rain_24h(hours)
    by_time = {h.at: (h, total) for h, total in zip(hours, totals, strict=True)}
    noons = sorted(h.at for h in hours if h.at.astimezone(UTC).hour == NOON_UTC_HOUR)

    state = previous.codes if previous is not None else fwi.Codes()
    daily: dict[date, fwi.Indices] = {}
    if previous is not None and previous_date is not None:
        daily[previous_date] = previous
    new_last: fwi.Indices | None = None
    new_date: date | None = None
    for noon in noons:
        day = local_date(noon)
        hour, _ = by_time[noon]
        if previous_date is not None and day <= previous_date:
            continue
        if hour.temperature_c is None or hour.relative_humidity_pct is None or hour.wind_speed_kmh is None:
            continue
        # Rain of the 24 h ending at noon; at the start of the series, what is known of it.
        window = [by_time.get(noon - timedelta(hours=k)) for k in range(24)]
        rain = sum((w[0].precipitation_mm or 0.0) for w in window if w is not None)
        today = fwi.daily(
            state, hour.temperature_c, hour.relative_humidity_pct, hour.wind_speed_kmh, rain, day.month, lat
        )
        daily[day] = today
        state = today.codes
        if noon <= now:
            new_last, new_date = today, day

    rows: list[Row] = []
    last: fwi.Indices | None = None
    for h, total in zip(hours, totals, strict=True):
        day_indices = daily.get(local_date(h.at))
        if day_indices is not None:
            last = day_indices
        rows.append(Row(h, total, heavy_rain_level(h.precipitation_mm, total), day_indices or last))
    return Result(rows=rows, last_past=new_last, last_past_date=new_date, daily=daily)
