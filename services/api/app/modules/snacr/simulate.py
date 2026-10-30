"""[SIM] years of the archive generated on the distributions of the real 2022 archive (docs/phase-s/design-s.md §4).

``data/profile_2022.json`` holds aggregates only (counts by délégation and family, by month, by weekday and hour,
subtypes, quantiles of the times): no row and no person of the Office's file. The generated rows keep the
archive's own spellings of the délégations and part of its defects (missing or impossible arrival times), so the
cleaning shown to the committee works on what the real file contains.

    python -m app.modules.snacr.simulate --years 2023 2024 2025
"""

import argparse
import asyncio
import bisect
import calendar
import json
import random
from collections.abc import Iterator
from datetime import datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

from app.modules.snacr.domain import FAMILIES, Family

PROFILE = Path(__file__).with_name("data") / "profile_2022.json"
# Rows a year: the size the Office's own sheets announce (about 151, 164 and 182 thousand), growth near 7 %.
DEFAULT_ROWS = {2023: 151_000, 2024: 164_000, 2025: 182_000}
NATURE_OF: dict[Family, str] = {
    "medical": "الإسعاف في غير حوادث المرور",
    "road": "النجدة والإسعاف على الطرقات",
    "fire": "مجابهة الحرائق",
    "rescue": "الإنقاذ",
}


@cache
def profile() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(PROFILE.read_text(encoding="utf-8"))
    return loaded


def rows_for(year: int) -> int:
    return DEFAULT_ROWS.get(year, round(143_308 * 1.07 ** (year - 2022)))


class _Pick:
    """Weighted choice by bisection on the cumulative weights."""

    def __init__(self, items: list[Any], weights: list[float]) -> None:
        self.items = items
        self.cum: list[float] = []
        total = 0.0
        for w in weights:
            total += max(0.0, w)
            self.cum.append(total)
        self.total = total

    def __call__(self, rng: random.Random) -> Any:
        return self.items[bisect.bisect_right(self.cum, rng.random() * self.total)]


def _quantile(rng: random.Random, levels: list[float], values: list[float]) -> float:
    """A draw from the distribution known by its quantiles (linear between them, tails stretched by half a step)."""
    u = rng.random()
    if u <= levels[0]:
        low = max(0.0, values[0] - (values[1] - values[0]) / 2)
        return low + (values[0] - low) * u / levels[0]
    if u >= levels[-1]:
        high = values[-1] + (values[-1] - values[-2])
        return values[-1] + (high - values[-1]) * (u - levels[-1]) / (1 - levels[-1])
    i = bisect.bisect_right(levels, u) - 1
    span = levels[i + 1] - levels[i]
    return values[i] + (values[i + 1] - values[i]) * (u - levels[i]) / span


def generate(year: int, rows: int | None = None, seed: int | None = None) -> Iterator[dict[str, Any]]:
    """Records in the shape ``domain.read`` gives for the Office's file (local times, the archive's names)."""
    p = profile()
    rng = random.Random(seed if seed is not None else year)  # noqa: S311 (a reproducible simulation)
    levels: list[float] = p["quantiles"]
    cells = _Pick(
        [(c["gouvernorat"], c["delegation"], c["family"]) for c in p["cells"]], [c["count"] for c in p["cells"]]
    )
    months = {f: _Pick(list(range(1, 13)), p["month"][f]) for f in FAMILIES}
    hours = {f: [_Pick(list(range(24)), p["weekday_hour"][f][w]) for w in range(7)] for f in FAMILIES}
    subtypes = {f: _Pick(list(p["subtypes"][f]), list(p["subtypes"][f].values())) for f in FAMILIES}
    national_arrival: dict[str, list[float]] = {}
    for f in FAMILIES:
        qs = [a[f]["q"] for a in p["arrival"].values() if f in a and a[f]["q"]]
        national_arrival[f] = [sum(q[i] for q in qs) / len(qs) for i in range(len(levels))]
    for _ in range(rows if rows is not None else rows_for(year)):
        gouvernorat, delegation, family = cells(rng)
        month = months[family](rng)
        day = rng.randint(1, calendar.monthrange(year, month)[1])
        weekday = calendar.weekday(year, month, day)
        called = datetime(year, month, day, hours[family][weekday](rng), rng.randint(0, 59))
        departed = called + timedelta(minutes=round(_quantile(rng, levels, p["departure"][family])))
        stats = p["arrival"].get(gouvernorat, {}).get(family) or {"n": 1, "recorded": 1, "valid": 1, "q": None}
        arrived: datetime | None = None
        if rng.random() < stats["recorded"] / stats["n"]:
            if rng.random() < (stats["recorded"] - stats["valid"]) / max(1, stats["recorded"]):
                # The archive's own defects: an arrival before the call, or days after it.
                arrived = (
                    called - timedelta(minutes=rng.randint(5, 600))
                    if rng.random() < 0.5
                    else (called + timedelta(minutes=rng.randint(200, 2000)))
                )
            else:
                minutes = _quantile(rng, levels, stats["q"] or national_arrival[family])
                arrived = called + timedelta(minutes=max(1, round(minutes)))
        start = arrived if arrived is not None and arrived > called else departed
        ended = start + timedelta(minutes=max(5, round(_quantile(rng, levels, p["duration"][family]))))
        subtype = subtypes[family](rng)
        yield {
            "called": called,
            "departed": departed,
            "arrived": arrived,
            "ended": ended,
            "gouvernorat": gouvernorat,
            "delegation": delegation,
            "nature": NATURE_OF[family],
            "subtype": subtype if subtype.strip() else None,
        }


async def _main(years: list[int], rows: int | None) -> None:
    from app.core.db import dispose_engine, get_system_sessionmaker
    from app.modules.audit import service as audit
    from app.modules.snacr import service

    try:
        for year in years:
            async with get_system_sessionmaker()() as session:
                dataset = await service.load(
                    session, year, generate(year, rows), "simulated", None, audit.SYSTEM_ACTOR, "e-Himaya"
                )
                await audit.record(
                    session,
                    actor=audit.SYSTEM_ACTOR,
                    action="snacr.dataset_simulated",
                    target=f"snacr_dataset:{year}",
                    details={"rows": dataset.rows},
                )
                await session.commit()
                print(f"{year}: {dataset.rows} rows [SIM]")
    finally:
        await dispose_engine()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=int, nargs="+", default=[2023, 2024, 2025])
    parser.add_argument("--rows", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(_main(args.years, args.rows))
