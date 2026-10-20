"""One-shot installation of the terrain model of Tunisia (Copernicus DEM GLO-90), standard library only.

Run once per installation (compose service ``terrain``, docs/weather-forecast.md). The API never downloads anything
at run time: it reads the converted raster from TERRAIN_DIR (a volume) and works without it, with slope 0 and an
explicit assumption in every forecast.

    python -m app.modules.forecast.terrain_fetch --out /terrain
    python -m app.modules.forecast.terrain_fetch --out /terrain --tiles /path/to/downloaded/tiles   # offline copy

Source: the 40 one-degree GLO-90 tiles covering 30–38° N, 7–12° E (Tunisia and its borders), Cloud Optimized
GeoTIFFs of the AWS Open Data copy (s3://copernicus-dem-90m). Every tile is pinned by SHA-256 (``TILES``); a mismatch
stops the installation. Licence: "Licence for COP-DEM-GLO-90-F Global 90m Full, Free & Open" (ESA / Copernicus,
free of charge, worldwide, reproduction, distribution and adaptation allowed, with the notice in ``ATTRIBUTION``).

Output, in ``--out``:
* ``tunisia-glo90.i16`` — elevation in metres, int16 little-endian, row-major, 9600 rows x 6000 columns, cell
  3 arc-seconds; cell (r, c) is centred on lat 38 - r/1200, lon 7 + c/1200 (the tiles' own pixel centres). The sea
  (no tile) and voids are 0.
* ``tunisia-glo90.json`` — the header the API reads (grid, SHA-256 of the raster and of every source tile, licence).
"""

import argparse
import hashlib
import itertools
import json
import operator
import struct
import sys
import tempfile
import urllib.request
import zlib
from array import array
from pathlib import Path
from typing import Any

BASE_URL = "https://copernicus-dem-90m.s3.amazonaws.com"
RASTER = "tunisia-glo90.i16"
HEADER = "tunisia-glo90.json"
LAT_TOP, LON_LEFT = 38, 7  # north-west corner (pixel centre of cell 0, 0)
LATS, LONS = range(30, 38), range(7, 12)  # tile south-west corners
CELLS_PER_DEGREE = 1200
ROWS, COLS = len(LATS) * CELLS_PER_DEGREE, len(LONS) * CELLS_PER_DEGREE
ATTRIBUTION = (
    "produced using Copernicus WorldDEM-90 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 "
    "provided under COPERNICUS by the European Union and ESA; all rights reserved"
)
LICENSE = "Licence for COP-DEM-GLO-90-F Global 90m Full, Free & Open (ESA, Copernicus)"
FORMAT_VERSION = 1

# SHA-256 of each tile as published on 2022-05-09 (s3://copernicus-dem-90m, checked 2026-10-20).
TILES: dict[str, str] = {
    "N30_00_E007_00": "a099021385d720a73c050f4c580328483986698eb5df82113c9e279916c77cbd",
    "N30_00_E008_00": "721fcacabf69105d8fa128b254087066fccff236bc42c0060ded457b1e045934",
    "N30_00_E009_00": "21c664df8ee6325992a22e0b5a876ad0b7e8ce111bf5095730838cbbbbd738c2",
    "N30_00_E010_00": "68aadf7327e50d6d07b8ecae3695cbbf4c332593f866ee80be98bbe02374a2e9",
    "N30_00_E011_00": "fb2a16b996503bba9119cfffcf4f0687b8e93e4dcf6fae25b858efc97924c1f9",
    "N31_00_E007_00": "8a85393290d5268db3a2a72b6fcdd69cf09cc8912da4c6a75e6580837bf34825",
    "N31_00_E008_00": "36224b2b42334c0117d2ac1822b7b494101d5f1a3750ca14b0fe2074e5c2c73a",
    "N31_00_E009_00": "fc867cc4e10d8c0b5eadcf85342d025c0a34377d95bc94c2ed6354b415bf8e27",
    "N31_00_E010_00": "8f695186d8192bf5a5a8141419153060ab5f3078e67c40f3133f450b15a3dcaf",
    "N31_00_E011_00": "ddbb7a6d6e93e47f28bd59a8d026b760d4c64c48c230b91dac48f12d2925e9ee",
    "N32_00_E007_00": "209c97f0be42a0a04d16368ed942e7107a472fe2def0adb79323da5eafb971a9",
    "N32_00_E008_00": "963a0138472c71e008e0cc9c3072efdc1e22decca8d4581a1b78726b5ae9f1ba",
    "N32_00_E009_00": "3f6153128a52e997cb992b6c268bc7715b3401d9288315b1a38d950eb8e627d0",
    "N32_00_E010_00": "63ae55da374b752be826b94f499e176aaeabdffbc36d1454a2f6aa5081921216",
    "N32_00_E011_00": "21d5d20623032cc4dbc74101d7b4a448ffafebcdf77030b86c8ad528c46d25c0",
    "N33_00_E007_00": "f6a200a4e71c4f993bd45903f02975913ba0c89c17d580082b55affd93f3c9c6",
    "N33_00_E008_00": "94a53826fd6c966a5cf0402b03bf1fc5794d42bf863eba5ac7d0bd188c182339",
    "N33_00_E009_00": "99a8add8dc183e39bc63de68d11495f767f28f79550e3d6d9c8debb021d6e0f8",
    "N33_00_E010_00": "824edf9d466b985a77cfa4404dd501814dba96e91cbc4bbede96dc23edb964d0",
    "N33_00_E011_00": "292568c39a0d9df2f2ded19afefff67b6f330117892348a9715b0916c49febfb",
    "N34_00_E007_00": "51cd0b49f0b6c944357159b2fb0b2216cc4d7be5d23018f4dbcc679ba6ca6166",
    "N34_00_E008_00": "b74c1e9d5c32afd331ea4a548c5b20cc088349baad54794efac1fa8e0524b86d",
    "N34_00_E009_00": "83b249f1374c8c202300a2dd9474cbd54bfb88a96fb2e773b806ad17ab7a052a",
    "N34_00_E010_00": "764b2dfa3be6e588d13cd473b090a6ec044e2f0fc398aa8f8f263cf5edb7bd01",
    "N34_00_E011_00": "822280a9561ba874cdb10d72a789274e281ffad1970eb470a8f98a5d825fcf89",
    "N35_00_E007_00": "b4c94dc966b4085d817535e0b4f81915dd427cc542a0c87e92016da51b2e7e65",
    "N35_00_E008_00": "22b6be1031a2c93089f604f2e9194832197d4debb5b700e03ad4d840ea1b9c0f",
    "N35_00_E009_00": "de3062e06d0dfc1a31df389975adc77197e89661a29f3f4bc62985c663d9346b",
    "N35_00_E010_00": "f34bdea306f844665cb277e06257e8098b3ca7415f010522546be296b1b9201b",
    "N35_00_E011_00": "6064a92593eddb620afbb14bbe3d03caca8867ecff142e3112e90852cb29965c",
    "N36_00_E007_00": "dd17e4b1fae599b5c79496970b5f01debfedf14aeca1823f65b0c40fcc8dbc55",
    "N36_00_E008_00": "0d367e50d86347dd4e0ce3253c931c86f27ff647992d4a1e89633ab77684ffca",
    "N36_00_E009_00": "9f8a1dd7a2cf7401cc571b673ca08d9c5706612435550280310ed59495a1fa0c",
    "N36_00_E010_00": "388db3c033b3ec6619ac16df943e59e893da7ee40334a9d216b5f946a87a74b9",
    "N36_00_E011_00": "bc771f85df59caa9e36ac1ac25ccca7a4fb3aee42f5000f1996dc08d55b91ced",
    "N37_00_E007_00": "331348da6e4b8364e6b6a14e9ceedc0b61e25201ee29c56e51b95f3904d25c23",
    "N37_00_E008_00": "1d2155c3ab37937a388374a0502d7d5cae8f85b7a813d2a3ac3bcfceb497f00c",
    "N37_00_E009_00": "15db0f981e1514ef78b4497a0cc2280848ef83c996b83b5175df56988eec6fb6",
    "N37_00_E010_00": "f09750bf4909515a5211e9011da71954baa63e287cc2b0666254a763fb1b0061",
    "N37_00_E011_00": "72192c0a98f7ffac08078c6fff20abf28d199adf91d829f5916ad08557019e29",
}


def tile_name(key: str) -> str:
    return f"Copernicus_DSM_COG_30_{key}_DEM"


def tile_key(lat: int, lon: int) -> str:
    return f"N{lat:02d}_00_E{lon:03d}_00"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------- GeoTIFF reading (the subset GLO-90 COGs use)

_TYPES = {1: ("B", 1), 2: ("s", 1), 3: ("H", 2), 4: ("I", 4), 11: ("f", 4), 12: ("d", 8), 16: ("Q", 8)}


def _ifd(data: bytes) -> dict[int, tuple[Any, ...]]:
    """Tags of the first image file directory (the full-resolution image of a COG); classic little-endian TIFF."""
    if data[:4] != b"II*\x00":
        raise ValueError("not a little-endian classic TIFF")
    (offset,) = struct.unpack_from("<I", data, 4)
    (count,) = struct.unpack_from("<H", data, offset)
    tags: dict[int, tuple[Any, ...]] = {}
    for i in range(count):
        tag, kind, n, value = struct.unpack_from("<HHI4s", data, offset + 2 + 12 * i)
        if kind not in _TYPES:
            continue
        code, size = _TYPES[kind]
        raw = value if n * size <= 4 else data[struct.unpack("<I", value)[0] :][: n * size]
        tags[tag] = struct.unpack(f"<{n}{code}", raw[: n * size])
    return tags


def _undo_float_predictor(block: bytes, width: int, rows: int, keep_cols: int) -> array:  # type: ignore[type-arg]
    """Adobe floating-point predictor (TIFF Technote 3, predictor 3): each row holds the bytes of its samples split
    in planes, most significant first, then differenced byte by byte. Returns the first ``keep_cols`` float32 values
    of each of the first ``rows`` rows."""
    row_len = width * 4
    out = array("f")
    for r in range(rows):
        row = block[r * row_len : (r + 1) * row_len]
        planes = []
        for k in range(4):
            start = k * width
            prefix = sum(row[:start])
            cumulative = itertools.accumulate(row[start : start + keep_cols], operator.add, initial=prefix)
            next(cumulative)
            planes.append(bytes(map(operator.and_, cumulative, itertools.repeat(255))))
        big_endian = bytearray(4 * keep_cols)
        for k in range(4):
            big_endian[k::4] = planes[k]
        values = array("f")
        values.frombytes(bytes(big_endian))
        if sys.byteorder == "little":
            values.byteswap()
        out.extend(values)
    return out


def decode_tile(data: bytes) -> tuple[array, tuple[float, float]]:  # type: ignore[type-arg]
    """Elevations (float32, row-major, CELLS_PER_DEGREE²) and the (lat, lon) centre of the north-west pixel."""
    tags = _ifd(data)
    width, height = tags[256][0], tags[257][0]
    if (width, height) != (CELLS_PER_DEGREE, CELLS_PER_DEGREE):
        raise ValueError(f"unexpected tile size {width}x{height}")
    if tags.get(258, (0,))[0] != 32 or tags.get(339, (1,))[0] != 3 or tags.get(259, (1,))[0] not in (8, 32946):
        raise ValueError("expected deflate-compressed float32 samples")
    predictor = tags.get(317, (1,))[0]
    scale, tie = tags[33550], tags[33922]
    if abs(scale[0] - 1 / CELLS_PER_DEGREE) > 1e-9 or abs(scale[1] - 1 / CELLS_PER_DEGREE) > 1e-9:
        raise ValueError("unexpected pixel size")
    # The tie point is the centre of the north-west pixel when GTRasterTypeGeoKey (1025) is PixelIsPoint (2, what
    # GLO-90 COGs declare), else its north-west corner, half a cell away from the centre.
    keys = tags.get(34735, ())
    raster_type = next((keys[i + 3] for i in range(4, len(keys) - 3, 4) if keys[i] == 1025), 1)
    half = 0.0 if raster_type == 2 else 0.5
    north_west = (tie[4] - half * scale[1], tie[3] + half * scale[0])
    tile_w, tile_h = tags[322][0], tags[323][0]
    offsets, counts = tags[324], tags[325]
    across = -(-width // tile_w)
    grid = array("f", bytes(4 * width * height))
    for index, (offset, count) in enumerate(zip(offsets, counts, strict=True)):
        ty, tx = divmod(index, across)
        rows = min(tile_h, height - ty * tile_h)
        cols = min(tile_w, width - tx * tile_w)
        if rows <= 0 or cols <= 0:
            continue
        block = zlib.decompress(data[offset : offset + count])
        if predictor == 3:
            values = _undo_float_predictor(block, tile_w, rows, cols)
        elif predictor == 1:
            full = array("f", block)
            values = array("f")
            for r in range(rows):
                values.extend(full[r * tile_w : r * tile_w + cols])
        else:
            raise ValueError(f"unsupported predictor {predictor}")
        for r in range(rows):
            start = (ty * tile_h + r) * width + tx * tile_w
            grid[start : start + cols] = values[r * cols : (r + 1) * cols]
    return grid, north_west


# ---------------------------------------------------------------- installation


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 (fixed https URL)
        data: bytes = response.read()
    return data


def _tile_bytes(key: str, local: Path | None) -> bytes:
    name = tile_name(key)
    if local is not None:
        path = local / f"{name}.tif"
        if path.is_file():
            return path.read_bytes()
    return _download(f"{BASE_URL}/{name}/{name}.tif")


def install(out: Path, local: Path | None = None, *, force: bool = False) -> dict[str, Any]:
    header_path, raster_path = out / HEADER, out / RASTER
    if not force and header_path.is_file() and raster_path.is_file():
        header: dict[str, Any] = json.loads(header_path.read_text())
        if header.get("format_version") == FORMAT_VERSION and header.get("tiles") == TILES:
            print(f"terrain: already installed in {out}")
            return header
    out.mkdir(parents=True, exist_ok=True)
    raster = array("h", bytes(2 * ROWS * COLS))
    for lat, lon in itertools.product(LATS, LONS):
        key = tile_key(lat, lon)
        expected = TILES.get(key)
        if expected is None:
            raise SystemExit(f"terrain: tile {key} is not pinned")
        data = _tile_bytes(key, local)
        if sha256(data) != expected:
            raise SystemExit(f"terrain: SHA-256 mismatch for {key}, refusing to install")
        grid, (north, west) = decode_tile(data)
        if abs(north - (lat + 1)) > 1e-6 or abs(west - lon) > 1e-6:
            raise SystemExit(f"terrain: tile {key} is not where its name says ({north}, {west})")
        row0, col0 = (LAT_TOP - (lat + 1)) * CELLS_PER_DEGREE, (lon - LON_LEFT) * CELLS_PER_DEGREE
        for r in range(CELLS_PER_DEGREE):
            line = grid[r * CELLS_PER_DEGREE : (r + 1) * CELLS_PER_DEGREE]
            # NaN (voids) and the sea are 0; GLO-90 heights fit in int16 (Tunisia: -25 m to 1544 m).
            ints = array("h", (round(v) if v == v and -1000 < v < 9000 else 0 for v in line))
            start = (row0 + r) * COLS + col0
            raster[start : start + CELLS_PER_DEGREE] = ints
        print(f"terrain: {key} ok")
    if sys.byteorder != "little":
        raster.byteswap()
    payload = raster.tobytes()
    with tempfile.NamedTemporaryFile(dir=out, delete=False) as tmp:
        tmp.write(payload)
    Path(tmp.name).chmod(0o644)
    Path(tmp.name).replace(raster_path)
    header = {
        "format_version": FORMAT_VERSION,
        "source": "Copernicus DEM GLO-90 (COP-DEM_GLO-90-DGED), AWS Open Data copy s3://copernicus-dem-90m",
        "license": LICENSE,
        "attribution": ATTRIBUTION,
        "file": RASTER,
        "dtype": "int16-le",
        "rows": ROWS,
        "cols": COLS,
        "lat_top": LAT_TOP,
        "lon_left": LON_LEFT,
        "cells_per_degree": CELLS_PER_DEGREE,
        "sha256": sha256(payload),
        "tiles": TILES,
    }
    header_path.write_text(json.dumps(header, indent=2))
    print(f"terrain: installed {ROWS}x{COLS} cells in {out}")
    return header


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tiles", type=Path, help="directory holding already downloaded tiles (<name>.tif)")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    install(args.out, args.tiles, force=args.force)


if __name__ == "__main__":
    main()
