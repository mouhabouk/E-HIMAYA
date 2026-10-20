"""Location assessment of a report (phase 9 §4.2): who handles it is decided only by a trusted location.

* ``trusted``: the point lies in gouvernorat G, its accuracy circle touches no other gouvernorat and the accuracy is
  within ``geo.max_trusted_accuracy_m``. A point picked on a map (portal) without accuracy counts as exact.
* ``contradictory``: inside G but the accuracy circle crosses into another gouvernorat.
* ``pending``: outside every boundary (sea, border), accuracy above the threshold, or an app report without accuracy.

Pending and contradictory reports get no gouvernorat (NULL) and wait in the central geo-verification queue; their
candidate gouvernorats see them only when they are critical.
"""

from dataclasses import dataclass
from typing import Literal

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.geo.models import Gouvernorat
from app.modules.reports.domain import NEAREST_GOUVERNORAT_MAX_M
from app.modules.settings import domain as settings_domain
from app.modules.settings import service as settings

GeoState = Literal["trusted", "pending", "contradictory", "verified"]
GeoReason = Literal["outside_boundaries", "low_accuracy", "accuracy_missing", "accuracy_crosses_border"]
OPEN_GEO_STATES = ("pending", "contradictory")
# At most this many candidate gouvernorats are offered to the verifier.
MAX_CANDIDATES = 4


@dataclass(frozen=True, slots=True)
class Assessment:
    state: GeoState
    gouvernorat_code: int | None
    candidates: list[int]
    reason: GeoReason | None

    @property
    def tracking_gouvernorat(self) -> int | None:
        """Gouvernorat of the tracking code (phase 2 format, unchanged): the point's, else the nearest, else 00."""
        return self.gouvernorat_code if self.gouvernorat_code is not None else next(iter(self.candidates), None)


async def assess(session: AsyncSession, lat: float, lon: float, accuracy_m: float | None, source: str) -> Assessment:
    point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    target = cast(point, Geography)
    inside = await session.scalar(
        select(Gouvernorat.code).where(func.ST_Intersects(Gouvernorat.boundary, point)).limit(1)
    )
    if inside is None:
        return Assessment(
            "pending", None, await _near(session, target, NEAREST_GOUVERNORAT_MAX_M), "outside_boundaries"
        )
    if accuracy_m is None:
        if source == "portal":
            return Assessment("trusted", inside, [], None)
        return Assessment("pending", None, [inside], "accuracy_missing")
    radius = min(accuracy_m, float(NEAREST_GOUVERNORAT_MAX_M))
    others = [c for c in await _near(session, target, radius) if c != inside] if accuracy_m > 0 else []
    threshold = await settings.get(session, settings_domain.GEO_MAX_ACCURACY)
    if accuracy_m > threshold:
        return Assessment("pending", None, [inside, *others][:MAX_CANDIDATES], "low_accuracy")
    if others:
        return Assessment("contradictory", None, [inside, *others][:MAX_CANDIDATES], "accuracy_crosses_border")
    return Assessment("trusted", inside, [], None)


async def _near(session: AsyncSession, target: object, radius_m: float) -> list[int]:
    """Gouvernorats within ``radius_m`` of the point, nearest first."""
    boundary = cast(Gouvernorat.boundary, Geography)
    rows = await session.scalars(
        select(Gouvernorat.code)
        .where(func.ST_DWithin(boundary, target, radius_m))
        .order_by(func.ST_Distance(boundary, target))
        .limit(MAX_CANDIDATES)
    )
    return list(rows)
