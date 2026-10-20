"""Vehicle routing on OpenStreetMap Tunisia through a self-hosted Valhalla engine (docs/decision-support.md).

Valhalla (MIT) serves car (``auto``) and truck costing from one graph, prepared once from a pinned Geofabrik extract by
the ``routing-prepare`` job (infra/routing). The engine is optional: when ``ROUTING_URL`` is unset, the engine is down
or it finds no path, the API answers a straight-line estimate marked ``"engine": "fallback"`` so a dispatcher always
gets an order of magnitude, never a silent error. Road data © OpenStreetMap contributors, ODbL 1.0.
"""

import math
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import httpx
import structlog

from app.core.config import get_settings
from app.modules.reports.domain import LAT_MAX, LAT_MIN, LON_MAX, LON_MIN

log = structlog.get_logger()

Profile = Literal["car", "truck"]
ATTRIBUTION = "© OpenStreetMap contributors (ODbL 1.0)"
_COSTING: dict[str, str] = {"car": "auto", "truck": "truck"}

# Straight-line fallback: road distance ≈ 1.3 × great-circle distance (detour factor of a mixed urban/rural network);
# average speeds of an emergency vehicle including towns and tracks.
DETOUR_FACTOR = 1.3
FALLBACK_SPEED_KMH: dict[str, float] = {"car": 55.0, "truck": 45.0}
# Requests are limited to Tunisia (the graph covers the Geofabrik extract only); same bounds as report locations.
COVERAGE = (LAT_MIN, LON_MIN, LAT_MAX, LON_MAX)
MAX_MATRIX = 50


@dataclass(frozen=True, slots=True)
class Point:
    lat: float
    lon: float

    def covered(self) -> bool:
        return COVERAGE[0] <= self.lat <= COVERAGE[2] and COVERAGE[1] <= self.lon <= COVERAGE[3]


@dataclass(frozen=True, slots=True)
class Leg:
    distance_m: float
    duration_s: float


@dataclass(slots=True)
class Route:
    distance_m: float
    duration_s: float
    # [[lon, lat], ...] (GeoJSON order)
    coordinates: list[list[float]]
    engine: str
    fallback_reason: str | None = None
    assumptions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "distance_m": round(self.distance_m),
            "duration_s": round(self.duration_s),
            "geometry": {"type": "LineString", "coordinates": self.coordinates},
            "engine": self.engine,
            # A real engine or a labelled estimate: nothing here is simulated data.
            "simulated": False,
            "attribution": ATTRIBUTION if self.engine != "fallback" else None,
        }
        if self.fallback_reason is not None:
            out["fallback_reason"] = self.fallback_reason
            out["assumptions"] = self.assumptions
        return out


class RoutingUnavailable(Exception):
    """The engine is not reachable or answered an unexpected status."""


class NoRoute(Exception):
    """The engine is up but finds no road path (point off the network, island without a link)."""


class RoutingEngine(Protocol):
    name: str

    async def route(self, origin: Point, destination: Point, profile: Profile) -> Route: ...

    async def matrix(self, sources: list[Point], target: Point, profile: Profile) -> list[Leg | None]: ...


def haversine_m(a: Point, b: Point) -> float:
    r = 6_371_008.8
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp, dl = p2 - p1, math.radians(b.lon - a.lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


def estimate(origin: Point, destination: Point, profile: Profile) -> Leg:
    distance = haversine_m(origin, destination) * DETOUR_FACTOR
    return Leg(distance_m=distance, duration_s=distance / (FALLBACK_SPEED_KMH[profile] / 3.6))


def fallback_route(origin: Point, destination: Point, profile: Profile, reason: str) -> Route:
    leg = estimate(origin, destination, profile)
    return Route(
        distance_m=leg.distance_m,
        duration_s=leg.duration_s,
        coordinates=[[origin.lon, origin.lat], [destination.lon, destination.lat]],
        engine="fallback",
        fallback_reason=reason,
        assumptions=[
            f"straight line × {DETOUR_FACTOR} (road detour)",
            f"average speed {FALLBACK_SPEED_KMH[profile]:g} km/h ({profile})",
        ],
    )


def decode_polyline(encoded: str, precision: int = 6) -> list[list[float]]:
    """Google polyline algorithm (Valhalla uses precision 6) → [[lon, lat], ...]."""
    coordinates: list[list[float]] = []
    index = lat = lon = 0
    factor = 10**precision
    while index < len(encoded):
        deltas: list[int] = []
        for _ in range(2):
            shift = result = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lon += deltas[1]
        coordinates.append([round(lon / factor, 6), round(lat / factor, 6)])
    return coordinates


class ValhallaEngine:
    name = "valhalla"

    def __init__(self, base_url: str, timeout_s: float) -> None:
        self._http = httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(timeout_s))

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._http.post(path, json=body)
        except httpx.HTTPError as exc:
            raise RoutingUnavailable(type(exc).__name__) from exc
        if response.status_code == 400:
            # Valhalla answers 400 with an error_code for unroutable input (e.g. 171/442 no path, 170/171 no edge).
            raise NoRoute(str(response.json().get("error_code", "400")) if response.content else "400")
        if response.status_code != 200:
            raise RoutingUnavailable(f"HTTP {response.status_code}")
        data: dict[str, Any] = response.json()
        return data

    async def route(self, origin: Point, destination: Point, profile: Profile) -> Route:
        data = await self._post(
            "/route",
            {
                "locations": [{"lat": origin.lat, "lon": origin.lon}, {"lat": destination.lat, "lon": destination.lon}],
                "costing": _COSTING[profile],
                "units": "kilometers",
                "directions_type": "none",
            },
        )
        trip = data.get("trip") or {}
        summary = trip.get("summary") or {}
        coordinates: list[list[float]] = []
        for leg in trip.get("legs") or []:
            shape = decode_polyline(str(leg.get("shape", "")))
            coordinates.extend(shape if not coordinates else shape[1:])
        if "length" not in summary or len(coordinates) < 2:
            raise RoutingUnavailable("invalid_answer")
        return Route(
            distance_m=float(summary["length"]) * 1000,
            duration_s=float(summary.get("time", 0)),
            coordinates=coordinates,
            engine=self.name,
        )

    async def matrix(self, sources: list[Point], target: Point, profile: Profile) -> list[Leg | None]:
        data = await self._post(
            "/sources_to_targets",
            {
                "sources": [{"lat": p.lat, "lon": p.lon} for p in sources],
                "targets": [{"lat": target.lat, "lon": target.lon}],
                "costing": _COSTING[profile],
                "units": "kilometers",
            },
        )
        rows = data.get("sources_to_targets") or []
        legs: list[Leg | None] = []
        for row in rows:
            cell = row[0] if row else {}
            if cell.get("distance") is None or cell.get("time") is None:
                legs.append(None)
            else:
                legs.append(Leg(distance_m=float(cell["distance"]) * 1000, duration_s=float(cell["time"])))
        if len(legs) != len(sources):
            raise RoutingUnavailable("invalid_answer")
        return legs

    async def close(self) -> None:
        await self._http.aclose()


_engine: RoutingEngine | None = None
_default: ValhallaEngine | None = None


def get_engine() -> RoutingEngine | None:
    """None when no routing engine is configured: every answer is the straight-line estimate."""
    global _default
    if _engine is not None:
        return _engine
    settings = get_settings()
    if not settings.routing_url:
        return None
    if _default is None:
        _default = ValhallaEngine(settings.routing_url, settings.routing_timeout_s)
    return _default


def set_engine(engine: RoutingEngine | None) -> None:
    """Used by tests to inject a fake engine."""
    global _engine
    _engine = engine


async def route(origin: Point, destination: Point, profile: Profile) -> Route:
    engine = get_engine()
    if engine is None:
        return fallback_route(origin, destination, profile, "not_configured")
    try:
        return await engine.route(origin, destination, profile)
    except NoRoute:
        return fallback_route(origin, destination, profile, "no_route")
    except RoutingUnavailable as exc:
        log.warning("routing.unavailable", error=str(exc))
        return fallback_route(origin, destination, profile, "engine_unavailable")


async def travel(sources: list[Point], target: Point, profile: Profile) -> tuple[list[Leg], str]:
    """Travel distance and time from each source to the target, and the engine that computed them ("fallback" for the
    estimate). A source the engine cannot reach gets the estimate too."""
    estimates = [estimate(s, target, profile) for s in sources]
    engine = get_engine()
    if engine is None or not sources:
        return estimates, "fallback"
    legs: list[Leg | None] = []
    try:
        for start in range(0, len(sources), MAX_MATRIX):
            legs.extend(await engine.matrix(sources[start : start + MAX_MATRIX], target, profile))
    except (RoutingUnavailable, NoRoute) as exc:
        log.warning("routing.matrix_unavailable", error=str(exc))
        return estimates, "fallback"
    return [leg or est for leg, est in zip(legs, estimates, strict=True)], engine.name
