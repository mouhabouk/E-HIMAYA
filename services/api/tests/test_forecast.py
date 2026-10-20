"""Phase 7 §2: spread forecasts — Rothermel (1972) against Anderson's (1982) published fire behaviour, the Anderson
(1983) ellipse, the terrain model (GLO-90 reader, slope), the flood advisory, and the incident endpoints."""

import json
import math
import struct
import sys
from array import array
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.forecast import flood, rothermel, terrain, terrain_fetch
from app.modules.forecast.terrain import RasterTerrain, set_terrain, slope_at
from tests.test_operations import new_incident, random_place
from tests.weatherhelpers import PlaneTerrain, ScriptedProvider, refresh, sim_grid, weather_env

__all__ = ["sim_grid", "weather_env"]  # fixtures
Staff = Callable[..., dict[str, str]]

# ---------------------------------------------------------------- Rothermel against the published tables

# Anderson (1982, GTR-INT-122, table "fire behavior"): 8 % dead moisture, 100 % live, 5 mi/h midflame wind, no
# slope → rate of spread (chains/h) and flame length (ft).
ANDERSON_1982 = {
    1: (78.0, 4.0),
    2: (35.0, 6.0),
    3: (104.0, 12.0),
    4: (75.0, 19.0),
    5: (18.0, 4.0),
    6: (32.0, 6.0),
    7: (20.0, 5.0),
    8: (1.6, 1.0),
    9: (7.5, 2.6),
    10: (7.9, 4.8),
    11: (6.0, 3.5),
    12: (13.0, 8.0),
    13: (13.5, 10.5),
}
# Anderson's table was computed in 1982 with the original live-fuel and size-class handling; today's
# implementations (BehavePlus) differ from it most for the live-fuel models 5 and 7, and model 8 is rounded to a
# tenth of a small number. Relative tolerance per model (docs/weather-forecast.md, "Validation").
ROS_TOLERANCE = {5: 0.25, 7: 0.35, 8: 0.15}

# Andrews (2018, RMRS-GTR-371, table 8a): characteristic surface-area-to-volume ratio (1/ft) and relative packing
# ratio β/β_op of the 13 models.
ANDREWS_8A = {
    1: (3500, 0.25),
    2: (2784, 1.13),
    3: (1500, 0.21),
    4: (1739, 0.52),
    5: (1683, 0.33),
    6: (1564, 0.42),
    7: (1552, 0.34),
    8: (1889, 5.16),
    9: (2484, 4.50),
    10: (1764, 2.35),
    11: (1182, 1.62),
    12: (1145, 2.06),
    13: (1159, 2.68),
}
STANDARD = rothermel.Moisture(dead_1h=0.08, dead_10h=0.08, dead_100h=0.08, live_herb=1.0, live_woody=1.0)
CH_H_PER_FT_MIN = 60.0 / 66.0


@pytest.mark.parametrize("number", sorted(ANDERSON_1982))
def test_rate_of_spread_matches_anderson_1982(number: int) -> None:
    ros_ch_h, flame_ft = ANDERSON_1982[number]
    result = rothermel.spread(rothermel.FUEL_MODELS[number], STANDARD, 5.0)
    tolerance = ROS_TOLERANCE.get(number, 0.12)
    assert result.ros_ft_min * CH_H_PER_FT_MIN == pytest.approx(ros_ch_h, rel=tolerance)
    assert result.flame_length_m / 0.3048 == pytest.approx(flame_ft, rel=0.2, abs=0.6)
    assert not result.wind_limited


@pytest.mark.parametrize("number", sorted(ANDREWS_8A))
def test_fuel_bed_matches_andrews_table_8a(number: int) -> None:
    sav, relative = ANDREWS_8A[number]
    result = rothermel.spread(rothermel.FUEL_MODELS[number], STANDARD, 0.0)
    assert result.sav == pytest.approx(sav, abs=2)
    assert result.relative_packing_ratio == pytest.approx(relative, abs=0.02)
    model = rothermel.FUEL_MODELS[number]
    total_tons = model.load_1h + model.load_10h + model.load_100h + model.load_herb + model.load_woody
    assert result.bulk_density == pytest.approx(total_tons * rothermel.TONS_PER_ACRE / model.depth_ft)


def test_no_wind_no_slope_is_a_circle() -> None:
    result = rothermel.spread(rothermel.FUEL_MODELS[1], STANDARD, 0.0)
    assert result.length_to_breadth == 1.0
    assert result.ros_ft_min == pytest.approx(result.ros_no_wind_ft_min)
    assert result.backing_ros_ft_min == pytest.approx(result.ros_ft_min)


def test_too_wet_fuel_does_not_spread() -> None:
    wet = rothermel.Moisture(dead_1h=0.15, dead_10h=0.15, dead_100h=0.15)
    assert rothermel.spread(rothermel.FUEL_MODELS[1], wet, 5.0).ros_ft_min == 0.0  # Mx of model 1 is 12 %


def test_wind_and_slope_combine_as_vectors() -> None:
    grass = rothermel.FUEL_MODELS[1]
    flat = rothermel.spread(grass, STANDARD, 0.0)
    uphill = rothermel.spread(grass, STANDARD, 0.0, slope_fraction=0.4, upslope_deg=0.0)
    assert uphill.ros_ft_min > flat.ros_ft_min and uphill.heading_deg == pytest.approx(0.0, abs=1e-6)
    downwind = rothermel.spread(grass, STANDARD, 5.0, wind_towards_deg=90.0)
    assert downwind.heading_deg == pytest.approx(90.0)
    both = rothermel.spread(grass, STANDARD, 5.0, wind_towards_deg=90.0, slope_fraction=0.4, upslope_deg=0.0)
    assert 0.0 < both.heading_deg < 90.0
    assert downwind.ros_ft_min < both.ros_ft_min < downwind.ros_ft_min + uphill.ros_ft_min


def test_wind_limit() -> None:
    litter = rothermel.FUEL_MODELS[8]
    limited = rothermel.spread(litter, STANDARD, 40.0)
    unlimited = rothermel.spread(litter, STANDARD, 40.0, wind_limit=False)
    assert limited.wind_limited and "wind_limit_applied" in limited.notes
    assert limited.ros_ft_min < unlimited.ros_ft_min


def test_length_to_breadth_anderson_1983() -> None:
    assert rothermel.length_to_breadth(0.0) == 1.0
    expected = 0.936 * math.exp(0.2566 * 5) + 0.461 * math.exp(-0.1548 * 5) - 0.397
    assert rothermel.length_to_breadth(5.0) == pytest.approx(expected) == pytest.approx(3.19, abs=0.01)
    assert rothermel.length_to_breadth(10.0) > rothermel.length_to_breadth(5.0)
    assert rothermel.length_to_breadth(30.0) == rothermel.MAX_LENGTH_TO_BREADTH


def test_midflame_wind() -> None:
    grass = rothermel.FUEL_MODELS[1]
    assert rothermel.midflame_wind_mph(20.0, grass) == pytest.approx(20.0 / 1.609344 / 1.15 * 0.36)
    assert rothermel.midflame_wind_mph(20.0, grass, sheltered=0.15) == pytest.approx(20.0 / 1.609344 / 1.15 * 0.15)


def test_ellipse_geometry() -> None:
    result = rothermel.spread(rothermel.FUEL_MODELS[1], STANDARD, 5.0, wind_towards_deg=45.0)
    shape = rothermel.ellipse(result, 60)
    assert shape.head_m == pytest.approx(result.ros_m_min * 60)
    assert shape.length_m == pytest.approx(shape.head_m + shape.back_m)
    assert shape.length_m / shape.width_m == pytest.approx(result.length_to_breadth)
    assert shape.area_ha == pytest.approx(math.pi * shape.length_m * shape.width_m / 4 / 10_000)
    lat, lon = 35.0, 9.0
    ring = shape.ring(lat, lon)
    assert ring[0] == ring[-1] and len(ring) == 49
    # The first vertex is the head: head_m from the ignition point along the heading (45°, north-east).
    north = (ring[0][1] - lat) * 111_320.0
    east = (ring[0][0] - lon) * 111_320.0 * math.cos(math.radians(lat))
    assert math.hypot(east, north) == pytest.approx(shape.head_m, rel=1e-3)
    assert math.degrees(math.atan2(east, north)) == pytest.approx(45.0, abs=0.1)
    # The ring encloses the ignition point and has the ellipse's area.
    assert flood.ring_area_ha(ring) == pytest.approx(shape.area_ha, rel=0.01)


# ---------------------------------------------------------------- terrain


def test_terrain_tiles_are_pinned() -> None:
    assert len(terrain_fetch.TILES) == 40
    assert all(len(h) == 64 and int(h, 16) >= 0 for h in terrain_fetch.TILES.values())
    assert "N36_00_E010_00" in terrain_fetch.TILES
    assert "Copernicus" in terrain_fetch.ATTRIBUTION and "DLR" in terrain_fetch.ATTRIBUTION


def _encode_float_predictor(values: list[float], width: int) -> bytes:
    """Inverse of the TIFF floating-point predictor for one row: big-endian byte planes, then byte differences."""
    raw = array("f", values)
    if sys.byteorder == "little":
        raw.byteswap()
    data = raw.tobytes()
    planes = b"".join(bytes(data[k::4]) for k in range(4))
    assert len(planes) == 4 * width
    return bytes([planes[0]] + [(planes[i] - planes[i - 1]) & 255 for i in range(1, len(planes))])


def test_float_predictor_round_trip() -> None:
    rows = [[12.5, -3.25, 1500.0, 0.0, 87.75, 2.0], [0.5, 1.5, -400.0, 3.0, 4.0, 9999.0]]
    block = b"".join(_encode_float_predictor(r, 6) for r in rows)
    assert list(terrain_fetch._undo_float_predictor(block, 6, 2, 6)) == rows[0] + rows[1]
    assert list(terrain_fetch._undo_float_predictor(block, 6, 2, 4)) == rows[0][:4] + rows[1][:4]


def test_raster_terrain_reads_the_installed_grid(tmp_path: Path) -> None:
    rows, cols = 4, 5
    values = [r * 10 + c for r in range(rows) for c in range(cols)]
    (tmp_path / terrain_fetch.RASTER).write_bytes(struct.pack(f"<{rows * cols}h", *values))
    header = {
        "format_version": terrain_fetch.FORMAT_VERSION,
        "rows": rows,
        "cols": cols,
        "lat_top": 37.0,
        "lon_left": 10.0,
        "cells_per_degree": 1200,
        "source": "test",
        "file": terrain_fetch.RASTER,
    }
    (tmp_path / terrain_fetch.HEADER).write_text(json.dumps(header))
    grid = RasterTerrain(tmp_path)
    assert grid.elevation(37.0, 10.0) == 0.0
    assert grid.elevation(37.0 - 2 / 1200, 10.0 + 3 / 1200) == 23.0
    assert grid.elevation(30.0, 10.0) is None  # outside the raster
    (tmp_path / terrain_fetch.RASTER).write_bytes(b"\0\0")
    with pytest.raises(ValueError, match="wrong size"):
        RasterTerrain(tmp_path)


def test_slope_and_aspect() -> None:
    rising_east = slope_at(PlaneTerrain(35.0, 9.0, east=0.1), 35.0, 9.0)
    assert rising_east is not None
    assert rising_east.slope_fraction == pytest.approx(0.1, rel=1e-3)
    assert rising_east.upslope_deg == pytest.approx(90.0, abs=0.1)
    assert rising_east.elevation_m == pytest.approx(100.0)
    rising_south = slope_at(PlaneTerrain(35.0, 9.0, north=-0.05), 35.0, 9.0)
    assert rising_south is not None and rising_south.upslope_deg == pytest.approx(180.0, abs=0.1)
    flat = slope_at(PlaneTerrain(35.0, 9.0), 35.0, 9.0)
    assert flat is not None and flat.slope_fraction == 0.0


# ---------------------------------------------------------------- flood advisory


def test_flood_levels() -> None:
    def rain(observed: float = 0.0, ahead: float = 0.0, hourly: float = 0.0) -> flood.Rain:
        return flood.Rain(observed, ahead / 4, ahead / 2, ahead, hourly)

    assert flood.level(rain()) == "minimal"
    assert flood.level(rain(observed=12, ahead=10)) == "low"
    assert flood.level(rain(hourly=10)) == "low"
    assert flood.level(rain(observed=30, ahead=25)) == "moderate"
    assert flood.level(rain(hourly=20)) == "moderate"
    assert flood.level(rain(observed=60, ahead=45)) == "high"
    assert flood.level(rain(hourly=35)) == "high"


def test_flood_terrain_analysis() -> None:
    tilted = flood.analyse(PlaneTerrain(36.0, 10.0, east=0.02), 36.0, 10.0, 1000.0)
    assert tilted is not None
    assert tilted.drainage_direction_deg == 270  # water runs west, downhill
    assert tilted.mean_slope_pct == pytest.approx(2.0, abs=0.05)
    assert all(lon < 10.0 for _, lon in tilted.low_area)
    bowl = flood.analyse(PlaneTerrain(36.0, 10.0, bowl=0.01), 36.0, 10.0, 1000.0)
    assert bowl is not None and bowl.drainage_direction_deg is None
    lat, lon, z = bowl.low_points[0]
    assert (lat, lon) == pytest.approx((36.0, 10.0), abs=1e-6) and z == pytest.approx(100.0)
    assert flood.analyse(_Nowhere(), 36.0, 10.0, 1000.0) is None


class _Nowhere:
    source = "test"
    attribution = "none"

    def elevation(self, lat: float, lon: float) -> float | None:
        return None


def test_flood_geometry() -> None:
    ring = flood.circle(36.0, 10.0, 1000.0, vertices=96)
    assert ring[0] == ring[-1]
    assert flood.ring_area_ha(ring) == pytest.approx(math.pi * 100, rel=0.01)
    square = [(0.0, 0.0), (0.0, 1.0), (1.0, 0.0), (1.0, 1.0), (0.5, 0.5)]
    hull = flood.convex_hull(square)
    assert len(hull) == 4 and (0.5, 0.5) not in hull
    assert flood.polygon([(0.0, 0.0), (1.0, 1.0)]) is None


# ---------------------------------------------------------------- endpoints


async def test_fire_forecast_of_an_incident(
    client: httpx.AsyncClient, sim_grid: dict[str, int], staff: Staff, session: AsyncSession
) -> None:
    incident_id, _ = await new_incident(client, staff, random_place())
    url = f"/api/v1/staff/incidents/{incident_id}/forecast/fire"
    r = await client.post(url, headers=staff())
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["kind"] == "fire" and out["model"] == "rothermel-elliptical-v1" and out["simulated"] is True
    assert [p["minutes"] for p in out["polygons"]] == [30, 60, 120]
    areas = [p["area_ha"] for p in out["polygons"]]
    assert areas == sorted(areas) and out["rate_of_spread_m_min"] >= out["backing_rate_m_min"] >= 0
    codes = {a["code"] for a in out["assumptions"]}
    assert {"ignition_centroid", "default_fuel", "no_terrain", "simulated_weather", "uniform_conditions"} <= codes
    assert all(a["text"]["ar"] and a["text"]["fr"] for a in out["assumptions"])
    assert out["disclaimer"]["ar"] and out["disclaimer"]["fr"]
    assert out["inputs"]["fuel"] == {"key": "mixed", "anderson": 2, "name": "timber grass and understory"}
    assert out["inputs"]["slope_pct"] == 0.0 and out["attribution"][0].startswith("[SIM]")
    ring = out["polygons"][0]["geojson"]["coordinates"][0]
    assert out["polygons"][0]["geojson"]["type"] == "Polygon" and ring[0] == ring[-1]

    audit_row = await session.scalar(
        text("SELECT details FROM audit.log WHERE action = 'forecast.fire' AND target = :t ORDER BY seq DESC LIMIT 1"),
        {"t": f"incident:{incident_id}"},
    )
    assert audit_row is not None and audit_row["forecast_id"] == out["forecast_id"]
    listed = (await client.get(f"/api/v1/staff/incidents/{incident_id}/forecasts", headers=staff())).json()
    assert [f["forecast_id"] for f in listed["items"]] == [out["forecast_id"]]

    # A chosen fuel, ignition point and horizons; the terrain model gives the slope.
    place = random_place()
    set_terrain(PlaneTerrain(place["lat"], place["lon"], north=0.3))
    body = {
        "ignition": {"lat": place["lat"], "lon": place["lon"]},
        "fuel_model": "grass",
        "horizons_min": [90, 15],
    }
    r = await client.post(url, json=body, headers=staff(["central_committee"], gouvernorat=None))
    assert r.status_code == 201, r.text
    chosen = r.json()
    codes = {a["code"] for a in chosen["assumptions"]}
    assert "no_terrain" not in codes and "ignition_centroid" not in codes and "default_fuel" not in codes
    assert chosen["inputs"]["slope_pct"] == pytest.approx(30.0, abs=0.5) and chosen["inputs"]["upslope_deg"] == 0
    assert chosen["inputs"]["fuel"]["anderson"] == 1 and [p["minutes"] for p in chosen["polygons"]] == [15, 90]
    assert any("Copernicus" in a for a in chosen["attribution"])
    listed = (await client.get(f"/api/v1/staff/incidents/{incident_id}/forecasts", headers=staff())).json()
    assert [f["forecast_id"] for f in listed["items"]] == [chosen["forecast_id"], out["forecast_id"]]


async def test_forecast_scope_and_validation(
    client: httpx.AsyncClient, sim_grid: dict[str, int], staff: Staff, citizen: dict[str, str]
) -> None:
    incident_id, _ = await new_incident(client, staff, random_place())
    url = f"/api/v1/staff/incidents/{incident_id}/forecast/fire"
    assert (await client.post(url, headers=staff(gouvernorat=11))).status_code == 404
    assert (await client.post(url, headers=citizen)).status_code in (401, 403)
    assert (await client.post(url, json={"horizons_min": [800]}, headers=staff())).status_code == 422
    assert (await client.post(url, json={"fuel_model": "jungle"}, headers=staff())).status_code == 422
    flood_url = f"/api/v1/staff/incidents/{incident_id}/forecast/flood"
    assert (await client.post(flood_url, headers=staff(gouvernorat=11))).status_code == 404


async def test_forecasts_need_weather(client: httpx.AsyncClient, weather_env: None, staff: Staff) -> None:
    incident_id, _ = await new_incident(client, staff, random_place())
    for kind in ("fire", "flood"):
        r = await client.post(f"/api/v1/staff/incidents/{incident_id}/forecast/{kind}", headers=staff())
        assert r.status_code == 503 and r.json()["detail"] == "weather_unavailable"


async def test_flood_advisory_of_an_incident(client: httpx.AsyncClient, weather_env: None, staff: Staff) -> None:
    def downpour(at: datetime) -> dict[str, Any]:
        return {"precipitation_mm": 6.0, "relative_humidity_pct": 98.0}

    await refresh(ScriptedProvider(downpour))
    place = random_place()
    incident_id, _ = await new_incident(client, staff, place)
    url = f"/api/v1/staff/incidents/{incident_id}/forecast/flood"
    r = await client.post(url, headers=staff())
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["kind"] == "flood" and out["advisory"] is True and out["model"] == "rain-terrain-advisory-v1"
    assert out["level"] == "high"  # 6 mm/h: 144 mm over 24 h
    assert out["inputs"]["rain"]["observed_24h_mm"] == pytest.approx(144.0, abs=6.5)
    codes = {a["code"] for a in out["assumptions"]}
    assert {"flood_area_circle", "flood_no_terrain", "flood_no_hydraulics", "flood_point_rain"} <= codes
    assert out["low_points"] == [] and out["drainage_direction_deg"] is None
    assert out["risk_area_ha"] == pytest.approx(math.pi * 300**2 / 100, rel=0.02)  # the 3 km circle
    assert out["disclaimer"]["fr"].startswith("Avis consultatif")

    set_terrain(PlaneTerrain(place["lat"], place["lon"], east=0.01, bowl=0.002))
    shaped = (await client.post(url, headers=staff())).json()
    assert "flood_no_terrain" not in {a["code"] for a in shaped["assumptions"]}
    assert shaped["low_points"] and shaped["risk_area_ha"] < out["risk_area_ha"]
    assert shaped["inputs"]["terrain"]["min_elevation_m"] < shaped["inputs"]["terrain"]["max_elevation_m"]


def test_terrain_absent_by_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "terrain_dir", tmp_path)
    monkeypatch.setattr(terrain, "_loaded", False)
    try:
        assert terrain.get_terrain() is None
    finally:
        set_terrain(None)
