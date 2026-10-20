"""Read access to the terrain model installed by ``terrain_fetch`` (Copernicus DEM GLO-90, 3 arc-seconds).

The raster is memory-mapped read-only; a lookup touches a few pages only. Without an installed model every caller
gets ``None`` and states the assumption it makes instead (slope 0, no drainage analysis).
"""

import json
import math
import mmap
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import structlog

from app.core.config import get_settings
from app.modules.forecast.terrain_fetch import ATTRIBUTION, FORMAT_VERSION, HEADER

log = structlog.get_logger()
M_PER_DEG = 111_320.0


@dataclass(frozen=True, slots=True)
class SlopeAt:
    elevation_m: float
    slope_fraction: float  # rise over run
    upslope_deg: float  # direction the ground rises towards, clockwise from north

    @property
    def slope_pct(self) -> float:
        return self.slope_fraction * 100.0


class TerrainModel(Protocol):
    source: str
    attribution: str

    def elevation(self, lat: float, lon: float) -> float | None: ...


class RasterTerrain:
    def __init__(self, directory: Path) -> None:
        header = json.loads((directory / HEADER).read_text())
        if header.get("format_version") != FORMAT_VERSION:
            raise ValueError("unsupported terrain format")
        self.rows, self.cols = int(header["rows"]), int(header["cols"])
        self.lat_top, self.lon_left = float(header["lat_top"]), float(header["lon_left"])
        self.per_degree = int(header["cells_per_degree"])
        self.source = str(header["source"])
        self.attribution = str(header.get("attribution", ATTRIBUTION))
        path = directory / str(header["file"])
        if path.stat().st_size != 2 * self.rows * self.cols:
            raise ValueError("terrain raster has the wrong size")
        with path.open("rb") as handle:
            self._map = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)

    def _cell(self, row: int, col: int) -> float | None:
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            return None
        (value,) = struct.unpack_from("<h", self._map, 2 * (row * self.cols + col))
        return float(value)

    def elevation(self, lat: float, lon: float) -> float | None:
        row = round((self.lat_top - lat) * self.per_degree)
        col = round((lon - self.lon_left) * self.per_degree)
        return self._cell(row, col)


def slope_at(terrain: TerrainModel, lat: float, lon: float, spacing_m: float = 90.0) -> SlopeAt | None:
    """Horn (1981) slope and aspect from the 3 x 3 neighbourhood sampled every ``spacing_m``."""
    d_lat = spacing_m / M_PER_DEG
    d_lon = spacing_m / (M_PER_DEG * math.cos(math.radians(lat)))
    z: dict[tuple[int, int], float] = {}
    for i in (-1, 0, 1):  # i: north (+1) / south (-1)
        for j in (-1, 0, 1):  # j: east (+1) / west (-1)
            value = terrain.elevation(lat + i * d_lat, lon + j * d_lon)
            if value is None:
                return None
            z[(i, j)] = value
    dz_dx = ((z[(1, 1)] + 2 * z[(0, 1)] + z[(-1, 1)]) - (z[(1, -1)] + 2 * z[(0, -1)] + z[(-1, -1)])) / (8 * spacing_m)
    dz_dy = ((z[(1, -1)] + 2 * z[(1, 0)] + z[(1, 1)]) - (z[(-1, -1)] + 2 * z[(-1, 0)] + z[(-1, 1)])) / (8 * spacing_m)
    slope = math.hypot(dz_dx, dz_dy)
    upslope = (math.degrees(math.atan2(dz_dx, dz_dy)) + 360.0) % 360.0 if slope > 0 else 0.0
    return SlopeAt(elevation_m=z[(0, 0)], slope_fraction=slope, upslope_deg=upslope)


_terrain: TerrainModel | None = None
_loaded = False


def get_terrain() -> TerrainModel | None:
    """The installed terrain model, or None (checked once per process; see ``set_terrain``)."""
    global _terrain, _loaded
    if not _loaded:
        _loaded = True
        directory = get_settings().terrain_dir
        try:
            _terrain = RasterTerrain(directory) if directory and (directory / HEADER).is_file() else None
        except (OSError, ValueError, KeyError) as exc:
            log.warning("terrain.unavailable", error=type(exc).__name__)
            _terrain = None
        if _terrain is None:
            log.info("terrain.absent", directory=str(directory))
    return _terrain


def set_terrain(terrain: TerrainModel | None) -> None:
    """Replace the terrain model (tests); ``None`` means "no model installed"."""
    global _terrain, _loaded
    _terrain, _loaded = terrain, True
