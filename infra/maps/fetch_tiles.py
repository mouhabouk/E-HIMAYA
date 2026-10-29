"""ء-حماية / e-Himaya — copies the raster tiles of Tunisia from a tile server into one MBTiles file (docs/offline-maps.md).

Run once on a machine with internet (compose service "maps-satellite", profile "maps-prepare"); the file is then
served by the Office's own map server with no outside request. Standard library only (python:3.12-slim).

Only the tiles that touch a gouvernorat (with a margin of one tile) are fetched: the sea and the neighbouring
countries far from the border are skipped. The copy is resumable: a tile already in the file is not fetched again,
so an interrupted run continues where it stopped. Requests are few at a time and paced, and every tile is checked to
be an image before it is kept. Respect the licence and the usage policy of the source (docs/offline-maps.md §4).

Environment:
  SAT_URL          tile address with {z} {x} {y} (default: Sentinel-2 cloudless 2020 by EOX)
  SAT_MIN_ZOOM     first zoom level (default 0)
  SAT_MAX_ZOOM     last zoom level (default 14)
  SAT_OUT          output file (default /data/satellite.mbtiles)
  SAT_ATTRIBUTION  attribution stored in the file
  SAT_WORKERS      parallel requests (default 4, at most 8)
  SAT_DELAY_S      pause of each worker between two requests (default 0.05)
  SAT_COUNT_ONLY   "1": print the number of tiles and the estimated size per zoom, fetch nothing
"""

import math
import os
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

DEFAULT_URL = "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg"
DEFAULT_ATTRIBUTION = (
    "Sentinel-2 cloudless – s2maps.eu by EOX IT Services GmbH "
    "(contains modified Copernicus Sentinel data 2020), CC BY-NC-SA 4.0"
)
USER_AGENT = "e-Himaya offline map preparation (Office national de la protection civile, Tunisia)"
# Bounding boxes of the 24 gouvernorats (apps/dashboard/src/lib/mapStyle.ts, from geoBoundaries).
GOUVERNORATS = [
    (10.0, 36.69, 10.35, 36.94), (9.96, 36.82, 10.29, 37.12), (10.04, 36.45, 10.42, 36.81),
    (9.57, 36.55, 10.12, 36.97), (10.33, 36.35, 11.14, 37.14), (9.59, 36.0, 10.39, 36.66),
    (8.9, 36.72, 10.28, 37.54), (8.88, 36.34, 9.86, 37.16), (8.15, 36.35, 9.08, 37.01),
    (8.25, 35.62, 9.17, 36.45), (8.92, 35.48, 9.77, 36.47), (9.27, 35.02, 10.31, 36.14),
    (8.25, 34.63, 9.34, 35.79), (8.92, 34.26, 10.06, 35.5), (10.16, 35.4, 10.69, 36.39),
    (10.49, 35.42, 11.05, 35.81), (10.16, 35.09, 11.17, 35.59), (9.71, 34.17, 11.34, 35.28),
    (8.04, 34.05, 9.56, 34.81), (7.52, 33.42, 8.65, 34.53), (7.73, 32.5, 10.01, 34.19),
    (9.25, 33.27, 10.48, 34.28), (9.71, 32.25, 11.6, 33.92), (8.36, 30.23, 11.34, 33.23),
]
BOUNDS = (7.4, 30.2, 11.7, 37.6)
# Average size of a satellite JPEG tile, for the estimate only.
AVERAGE_TILE_BYTES = 22_000


def tile_x(lon: float, z: int) -> int:
    return min(2**z - 1, max(0, int((lon + 180.0) / 360.0 * 2**z)))


def tile_y(lat: float, z: int) -> int:
    r = math.radians(lat)
    return min(2**z - 1, max(0, int((1.0 - math.asinh(math.tan(r)) / math.pi) / 2.0 * 2**z)))


def tiles_of(z: int) -> list[tuple[int, int]]:
    """Tiles of zoom z that touch a gouvernorat, with one tile of margin, without duplicates."""
    seen: set[tuple[int, int]] = set()
    top = 2**z - 1
    for west, south, east, north in GOUVERNORATS:
        for x in range(max(0, tile_x(west, z) - 1), min(top, tile_x(east, z) + 1) + 1):
            for y in range(max(0, tile_y(north, z) - 1), min(top, tile_y(south, z) + 1) + 1):
                seen.add((x, y))
    return sorted(seen)


def open_mbtiles(path: str, min_zoom: int, max_zoom: int, attribution: str, fmt: str) -> sqlite3.Connection:
    db = sqlite3.connect(path, check_same_thread=False)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE IF NOT EXISTS metadata (name TEXT PRIMARY KEY, value TEXT)")
    db.execute(
        "CREATE TABLE IF NOT EXISTS tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB, "
        "PRIMARY KEY (zoom_level, tile_column, tile_row))"
    )
    meta = {
        "name": "satellite",
        "type": "baselayer",
        "version": "1",
        "description": "Satellite imagery of Tunisia for e-Himaya",
        "format": fmt,
        "bounds": ",".join(str(v) for v in BOUNDS),
        "center": "9.5,34.5,6",
        "minzoom": str(min_zoom),
        "maxzoom": str(max_zoom),
        "attribution": attribution,
    }
    db.executemany("INSERT OR REPLACE INTO metadata (name, value) VALUES (?, ?)", meta.items())
    db.commit()
    return db


def image_format(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def fetch(url: str, attempts: int = 4) -> bytes | None:
    """The tile, or None when the source has none (404/204); retries other failures with a growing pause."""
    for attempt in range(attempts):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 (operator-set https address)
                if response.status == 204:
                    return None
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code in (401, 403):
                raise SystemExit(f"the source refuses the request ({exc.code}): check SAT_URL and its licence key")
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(2 ** (attempt + 1))
    raise ConnectionError(f"no answer for {url}")


def main() -> int:
    url = os.environ.get("SAT_URL", "").strip() or DEFAULT_URL
    if not url.startswith(("https://", "http://")) or any(p not in url for p in ("{z}", "{x}", "{y}")):
        print("SAT_URL must be an http(s) address with {z}, {x} and {y}", file=sys.stderr)
        return 2
    min_zoom = int(os.environ.get("SAT_MIN_ZOOM", "0"))
    max_zoom = int(os.environ.get("SAT_MAX_ZOOM", "14"))
    if not 0 <= min_zoom <= max_zoom <= 19:
        print("zoom levels must satisfy 0 <= SAT_MIN_ZOOM <= SAT_MAX_ZOOM <= 19", file=sys.stderr)
        return 2
    workers = max(1, min(8, int(os.environ.get("SAT_WORKERS", "4"))))
    delay = max(0.0, float(os.environ.get("SAT_DELAY_S", "0.05")))
    out = os.environ.get("SAT_OUT", "/data/satellite.mbtiles")
    attribution = os.environ.get("SAT_ATTRIBUTION", "").strip() or (DEFAULT_ATTRIBUTION if url == DEFAULT_URL else "")

    plan = {z: tiles_of(z) for z in range(min_zoom, max_zoom + 1)}
    total = sum(len(t) for t in plan.values())
    for z, tiles in plan.items():
        print(f"zoom {z:2d}: {len(tiles):9d} tiles  ~{len(tiles) * AVERAGE_TILE_BYTES / 1e9:7.2f} GB")
    print(f"total  : {total:9d} tiles  ~{total * AVERAGE_TILE_BYTES / 1e9:7.2f} GB (estimate)")
    if os.environ.get("SAT_COUNT_ONLY") == "1":
        return 0

    fmt = url.rsplit(".", 1)[-1].split("?")[0].lower()
    db = open_mbtiles(out, min_zoom, max_zoom, attribution, "jpg" if fmt in ("jpg", "jpeg") else fmt or "png")
    lock = threading.Lock()
    done = {"new": 0, "kept": 0, "empty": 0}

    def one(z: int, x: int, y: int) -> None:
        row = 2**z - 1 - y  # MBTiles rows count from the south (TMS)
        with lock:
            if db.execute(
                "SELECT 1 FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?", (z, x, row)
            ).fetchone():
                done["kept"] += 1
                return
        data = fetch(url.replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y)))
        time.sleep(delay)
        if data is None or image_format(data) is None:
            with lock:
                done["empty"] += 1
            return
        with lock:
            db.execute("INSERT OR REPLACE INTO tiles VALUES (?, ?, ?, ?)", (z, x, row, data))
            done["new"] += 1
            if done["new"] % 500 == 0:
                db.commit()

    started = time.monotonic()
    for z, tiles in plan.items():
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for future in [pool.submit(one, z, x, y) for x, y in tiles]:
                future.result()
        with lock:
            db.commit()
        print(f"zoom {z:2d} done: {done} ({time.monotonic() - started:.0f} s)", flush=True)
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS tile_index ON tiles (zoom_level, tile_column, tile_row)")
    db.commit()
    db.execute("PRAGMA journal_mode=DELETE")
    db.close()
    print(f"satellite ready: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
