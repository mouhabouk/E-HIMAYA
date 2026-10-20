"""Rainfall-driven flood advisory (pure functions). An advisory, not a hydraulic model: it combines the rain observed
and forecast over an area with where water collects on the terrain model (low points, drainage direction), and says
so in every result."""

import math
from dataclasses import dataclass

from app.modules.forecast.terrain import M_PER_DEG, TerrainModel

GRID = 21  # samples per side of the analysed square
LOW_QUANTILE = 0.2  # the lowest fifth of the area is where runoff gathers first

# Levels from the accumulated rain (observed 24 h + next 24 h, mm) and the strongest hourly rate (mm/h).
LEVELS = (("high", 100.0, 30.0), ("moderate", 50.0, 20.0), ("low", 20.0, 10.0))


@dataclass(frozen=True, slots=True)
class Rain:
    observed_24h_mm: float
    next_6h_mm: float
    next_12h_mm: float
    next_24h_mm: float
    max_1h_mm: float

    @property
    def total_mm(self) -> float:
        return self.observed_24h_mm + self.next_24h_mm


@dataclass(frozen=True, slots=True)
class TerrainAnalysis:
    center_elevation_m: float
    min_elevation_m: float
    max_elevation_m: float
    drainage_direction_deg: float | None  # downslope direction of the area, clockwise from north
    mean_slope_pct: float
    low_points: list[tuple[float, float, float]]  # (lat, lon, elevation) local minima, lowest first
    low_area: list[tuple[float, float]]  # (lat, lon) of the lowest cells


def level(rain: Rain) -> str:
    for name, total, hourly in LEVELS:
        if rain.total_mm >= total or rain.max_1h_mm >= hourly:
            return name
    return "minimal"


def analyse(terrain: TerrainModel, lat: float, lon: float, radius_m: float) -> TerrainAnalysis | None:
    """Sample a GRID x GRID square of side 2 x radius around (lat, lon)."""
    step_m = 2 * radius_m / (GRID - 1)
    d_lat = step_m / M_PER_DEG
    d_lon = step_m / (M_PER_DEG * math.cos(math.radians(lat)))
    half = GRID // 2
    cells: dict[tuple[int, int], tuple[float, float, float]] = {}
    for i in range(GRID):  # i: rows from south to north
        for j in range(GRID):
            p_lat, p_lon = lat + (i - half) * d_lat, lon + (j - half) * d_lon
            z = terrain.elevation(p_lat, p_lon)
            if z is None:
                return None
            cells[(i, j)] = (p_lat, p_lon, z)
    elevations = sorted(c[2] for c in cells.values())
    # Least-squares plane z = a·east + b·north + c over the square: its downhill direction drains the area.
    sx = sy = sxx = syy = sxz = syz = 0.0
    mean_z = sum(elevations) / len(elevations)
    for (i, j), (_, _, z) in cells.items():
        x, y = (j - half) * step_m, (i - half) * step_m
        sx += x
        sy += y
        sxx += x * x
        syy += y * y
        sxz += x * (z - mean_z)
        syz += y * (z - mean_z)
    a, b = sxz / sxx, syz / syy
    gradient = math.hypot(a, b)
    drainage = (math.degrees(math.atan2(-a, -b)) + 360.0) % 360.0 if gradient > 1e-4 else None
    minima = []
    for (i, j), (p_lat, p_lon, z) in cells.items():
        around = [cells.get((i + di, j + dj)) for di in (-1, 0, 1) for dj in (-1, 0, 1) if di or dj]
        if all(n is None or z <= n[2] for n in around) and any(n is not None and z < n[2] for n in around):
            minima.append((round(p_lat, 5), round(p_lon, 5), z))
    minima.sort(key=lambda m: m[2])
    cutoff = elevations[max(int(len(elevations) * LOW_QUANTILE) - 1, 0)]
    low_area = [(c[0], c[1]) for c in cells.values() if c[2] <= cutoff]
    return TerrainAnalysis(
        center_elevation_m=cells[(half, half)][2],
        min_elevation_m=elevations[0],
        max_elevation_m=elevations[-1],
        drainage_direction_deg=None if drainage is None else round(drainage),
        mean_slope_pct=round(gradient * 100, 1),
        low_points=minima[:5],
        low_area=low_area,
    )


def convex_hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Andrew's monotone chain on (lat, lon) pairs; returns the hull counter-clockwise in (lon, lat)."""
    pts = sorted({(lon, lat) for lat, lon in points})
    if len(pts) < 3:
        return pts

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[tuple[float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def circle(lat: float, lon: float, radius_m: float, vertices: int = 48) -> list[list[float]]:
    ring = []
    for k in range(vertices):
        t = 2 * math.pi * k / vertices
        ring.append(
            [
                round(lon + radius_m * math.sin(t) / (M_PER_DEG * math.cos(math.radians(lat))), 6),
                round(lat + radius_m * math.cos(t) / M_PER_DEG, 6),
            ]
        )
    ring.append(ring[0])
    return ring


def polygon(points: list[tuple[float, float]]) -> list[list[float]] | None:
    hull = convex_hull(points)
    if len(hull) < 3:
        return None
    ring = [[round(x, 6), round(y, 6)] for x, y in hull]
    ring.append(ring[0])
    return ring


def ring_area_ha(ring: list[list[float]]) -> float:
    """Planar area of a lon/lat ring on the local tangent plane, hectares."""
    if len(ring) < 4:
        return 0.0
    lat0 = sum(p[1] for p in ring) / len(ring)
    kx, ky = M_PER_DEG * math.cos(math.radians(lat0)), M_PER_DEG
    twice = sum(
        (ring[k][0] * kx) * (ring[k + 1][1] * ky) - (ring[k + 1][0] * kx) * (ring[k][1] * ky)
        for k in range(len(ring) - 1)
    )
    return abs(twice) / 2 / 10_000.0
