"""Map data layers (phase L1a, docs/phase-l/design-layers.md §3.1-3.2): GIS files and their geometries.

KML or KMZ, zipped Shapefile and GeoPackage are read here into the same records as the other formats (heading →
value), the geometry under ``SHAPE``. No GDAL: the three formats are read with the standard library (XML, ZIP,
SQLite) and a small WKB reader. Only WGS84 is accepted; a file in another projection is refused as a whole
(``crs_unsupported``), as reprojection is done once outside the system before the upload.

A geometry is kept as a GeoJSON geometry (``{"type": ..., "coordinates": ...}``) of one of the six simple types.
"""

import io
import itertools
import math
import os
import re
import sqlite3
import struct
import tempfile
import zipfile
from collections.abc import Iterator
from typing import Any, Literal
from xml.etree import ElementTree

# The record key of a feature's geometry (never a heading of a file: it starts with a NUL).
SHAPE = "\0shape"

Kind = Literal["point", "line", "area"]
KINDS: dict[str, Kind] = {
    "Point": "point",
    "MultiPoint": "point",
    "LineString": "line",
    "MultiLineString": "line",
    "Polygon": "area",
    "MultiPolygon": "area",
}
MAX_VERTICES = 20_000
# A zipped Shapefile or a KMZ larger than this once unpacked is refused (a ZIP bomb would fill the memory).
MAX_UNPACKED_BYTES = 120 * 1024 * 1024


class GeoFileError(ValueError):
    """The whole file is refused (code for the dashboard)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# ---------------------------------------------------------------- geometries


def kind_of(geometry: dict[str, Any]) -> Kind | None:
    return KINDS.get(str(geometry.get("type")))


def _points(geometry: dict[str, Any]) -> Iterator[tuple[float, float]]:
    """Every (lon, lat) vertex of a geometry."""
    coordinates = geometry.get("coordinates")
    depth = {"Point": 0, "MultiPoint": 1, "LineString": 1, "MultiLineString": 2, "Polygon": 2, "MultiPolygon": 3}
    level = depth.get(str(geometry.get("type")))
    if level is None:
        return

    def walk(node: Any, d: int) -> Iterator[tuple[float, float]]:
        if d == 0:
            yield float(node[0]), float(node[1])
            return
        for child in node:
            yield from walk(child, d - 1)

    yield from walk(coordinates, level)


def vertex_count(geometry: dict[str, Any]) -> int:
    return sum(1 for _ in _points(geometry))


def valid(geometry: dict[str, Any]) -> bool:
    """Numbers everywhere, lines of two points or more, closed rings of four or more."""
    try:
        points = list(_points(geometry))
    except (TypeError, ValueError, IndexError):
        return False
    if not points or not all(math.isfinite(x) and math.isfinite(y) for x, y in points):
        return False
    kind, coordinates = geometry["type"], geometry["coordinates"]
    lines = [coordinates] if kind == "LineString" else coordinates if kind == "MultiLineString" else []
    rings = coordinates if kind == "Polygon" else [r for p in coordinates for r in p] if kind == "MultiPolygon" else []
    return all(len(line) >= 2 for line in lines) and all(len(r) >= 4 and r[0] == r[-1] for r in rings)


def bounds(geometry: dict[str, Any]) -> tuple[float, float, float, float]:
    """(min lon, min lat, max lon, max lat)."""
    xs, ys = zip(*_points(geometry), strict=True)
    return min(xs), min(ys), max(xs), max(ys)


def representative(geometry: dict[str, Any]) -> tuple[float, float]:
    """(lat, lon) of a point that stands for the feature before the database computes a point on its surface: the
    middle vertex of the longest line, the centre of the largest ring's vertices, the first point."""
    kind, coordinates = geometry["type"], geometry["coordinates"]
    if kind == "Point":
        return float(coordinates[1]), float(coordinates[0])
    if kind == "MultiPoint":
        return float(coordinates[0][1]), float(coordinates[0][0])
    if kind in ("LineString", "MultiLineString"):
        lines = [coordinates] if kind == "LineString" else coordinates
        line = max(lines, key=len)
        middle = line[len(line) // 2]
        return float(middle[1]), float(middle[0])
    polygons = [coordinates] if kind == "Polygon" else coordinates
    ring = max((p[0] for p in polygons), key=len)
    vertices = ring[:-1] or ring
    return (
        sum(float(p[1]) for p in vertices) / len(vertices),
        sum(float(p[0]) for p in vertices) / len(vertices),
    )


def _wkt_coordinates(node: Any, depth: int) -> str:
    if depth == 0:
        return f"{float(node[0])} {float(node[1])}"
    return "(" + ", ".join(_wkt_coordinates(child, depth - 1) for child in node) + ")"


def to_wkt(geometry: dict[str, Any]) -> str:
    """EWKT of a GeoJSON geometry (two dimensions), for PostGIS."""
    kind, coordinates = geometry["type"], geometry["coordinates"]
    if kind == "Point":
        return f"SRID=4326;POINT({_wkt_coordinates(coordinates, 0)})"
    depth = {"MultiPoint": 1, "LineString": 1, "MultiLineString": 2, "Polygon": 2, "MultiPolygon": 3}[kind]
    if kind == "MultiPoint":
        inner = ", ".join(f"({_wkt_coordinates(p, 0)})" for p in coordinates)
        return f"SRID=4326;MULTIPOINT({inner})"
    return f"SRID=4326;{kind.upper()}{_wkt_coordinates(coordinates, depth)}"


# ---------------------------------------------------------------- KML / KMZ


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _kml_coordinates(text: str | None) -> list[list[float]]:
    out: list[list[float]] = []
    for chunk in (text or "").split():
        parts = chunk.split(",")
        if len(parts) >= 2:
            out.append([float(parts[0]), float(parts[1])])
    return out


def _kml_geometry(element: ElementTree.Element) -> dict[str, Any] | None:
    tag = _local(element.tag)
    if tag == "Point":
        coordinates = _kml_coordinates(_child_text(element, "coordinates"))
        return {"type": "Point", "coordinates": coordinates[0]} if coordinates else None
    if tag == "LineString":
        return {"type": "LineString", "coordinates": _kml_coordinates(_child_text(element, "coordinates"))}
    if tag == "Polygon":
        rings: list[list[list[float]]] = []
        for boundary in element:
            if _local(boundary.tag) in ("outerBoundaryIs", "innerBoundaryIs"):
                for ring in boundary.iter():
                    if _local(ring.tag) == "LinearRing":
                        coordinates = _kml_coordinates(_child_text(ring, "coordinates"))
                        if _local(boundary.tag) == "outerBoundaryIs":
                            rings.insert(0, coordinates)
                        else:
                            rings.append(coordinates)
        return {"type": "Polygon", "coordinates": rings}
    if tag == "MultiGeometry":
        parts = [g for g in (_kml_geometry(child) for child in element) if g is not None]
        kinds = {p["type"] for p in parts}
        if len(kinds) != 1:
            return None  # a mix of points, lines and areas does not fit one layer
        single = kinds.pop()
        multi = {"Point": "MultiPoint", "LineString": "MultiLineString", "Polygon": "MultiPolygon"}.get(single)
        return {"type": multi, "coordinates": [p["coordinates"] for p in parts]} if multi else None
    return None


def _child_text(element: ElementTree.Element, name: str) -> str | None:
    for child in element.iter():
        if _local(child.tag) == name:
            return child.text
    return None


def _unpack(data: bytes, wanted: tuple[str, ...]) -> dict[str, bytes]:
    """The members of a ZIP with the wanted extensions, refusing paths outside the archive and ZIP bombs."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise GeoFileError("zip_unreadable") from None
    with archive:
        members = [m for m in archive.infolist() if not m.is_dir()]
        if sum(m.file_size for m in members) > MAX_UNPACKED_BYTES:
            raise GeoFileError("file_too_large")
        out: dict[str, bytes] = {}
        for member in members:
            name = member.filename.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/") or "__MACOSX" in name:
                continue
            lower = name.lower()
            if lower.endswith(wanted):
                out[lower] = archive.read(member)
        return out


def read_kml(data: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    if data[:2] == b"PK":
        members = _unpack(data, (".kml",))
        if not members:
            raise GeoFileError("kml_invalid")
        data = members.get("doc.kml") or next(iter(members.values()))
    if b"<!DOCTYPE" in data[:2048] or b"<!ENTITY" in data:
        raise GeoFileError("kml_invalid")  # no document type, no entity: nothing to expand or fetch
    try:
        # No DTD reaches here (refused above), so no entity to expand; ElementTree never fetches external files.
        root = ElementTree.fromstring(data)  # noqa: S314
    except ElementTree.ParseError:
        raise GeoFileError("kml_invalid") from None
    header: list[str] = ["name"]
    records: list[dict[str, Any]] = []
    for placemark in root.iter():
        if _local(placemark.tag) != "Placemark":
            continue
        record: dict[str, Any] = {}
        geometry = None
        for child in placemark:
            tag = _local(child.tag)
            if tag in ("name", "description") and child.text:
                record[tag] = child.text.strip()
            elif tag == "ExtendedData":
                for item in child.iter():
                    item_tag = _local(item.tag)
                    if item_tag == "Data" and item.get("name"):
                        record[str(item.get("name"))] = (_child_text(item, "value") or "").strip()
                    elif item_tag == "SimpleData" and item.get("name"):
                        record[str(item.get("name"))] = (item.text or "").strip()
            elif geometry is None:
                geometry = _kml_geometry(child)
        if placemark.get("id"):
            record.setdefault("id", placemark.get("id"))
        record[SHAPE] = geometry
        for key in record:
            if key != SHAPE and key not in header:
                header.append(key)
        records.append(record)
    if not records:
        raise GeoFileError("empty_file")
    return header, records


# ---------------------------------------------------------------- Shapefile (zipped)


_WGS84 = re.compile(r'GEOGCS\["[^"]*(WGS[ _]?(19)?84|4326)', re.IGNORECASE)


def _ring_area(ring: list[list[float]]) -> float:
    """Signed area (shoelace): negative for a clockwise ring, the outer rings of a Shapefile."""
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in itertools.pairwise(ring)) / 2


def _shp_geometry(content: bytes) -> dict[str, Any] | None:
    (shape_type,) = struct.unpack_from("<i", content, 0)
    base = shape_type % 10 if shape_type >= 10 else shape_type  # Z (11, 13, 15, 18) and M (21, 23, 25, 28)
    if shape_type == 0:
        return None
    if base == 1:
        x, y = struct.unpack_from("<2d", content, 4)
        return {"type": "Point", "coordinates": [x, y]}
    if base == 8:
        (count,) = struct.unpack_from("<i", content, 36)
        points = [list(struct.unpack_from("<2d", content, 40 + 16 * i)) for i in range(count)]
        return {"type": "MultiPoint", "coordinates": points}
    if base not in (3, 5):
        return None
    parts_count, points_count = struct.unpack_from("<2i", content, 36)
    if points_count > MAX_VERTICES or parts_count > points_count:
        return {"type": "LineString", "coordinates": [[0, 0]] * (MAX_VERTICES + 1)}  # refused as too large
    parts = list(struct.unpack_from(f"<{parts_count}i", content, 44))
    offset = 44 + 4 * parts_count
    points = [list(struct.unpack_from("<2d", content, offset + 16 * i)) for i in range(points_count)]
    pieces = [points[start:end] for start, end in zip(parts, [*parts[1:], points_count], strict=True)]
    if base == 3:
        if len(pieces) == 1:
            return {"type": "LineString", "coordinates": pieces[0]}
        return {"type": "MultiLineString", "coordinates": pieces}
    polygons: list[list[list[list[float]]]] = []
    for ring in pieces:
        if _ring_area(ring) <= 0 or not polygons:
            polygons.append([ring])  # clockwise: a new outer ring
        else:
            polygons[-1].append(ring)  # counter-clockwise: a hole of the last outer ring
    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons[0]}
    return {"type": "MultiPolygon", "coordinates": polygons}


def _dbf(data: bytes, encoding: str) -> tuple[list[str], list[dict[str, Any]]]:
    if len(data) < 32:
        raise GeoFileError("shp_invalid")
    count, header_length, record_length = struct.unpack_from("<IHH", data, 4)
    fields: list[tuple[str, str, int]] = []
    offset = 32
    while offset + 32 <= header_length and data[offset] != 0x0D:
        raw_name = data[offset : offset + 11].split(b"\0", 1)[0]
        fields.append((raw_name.decode(encoding, "replace"), chr(data[offset + 11]), data[offset + 16]))
        offset += 32
    records: list[dict[str, Any]] = []
    for i in range(count):
        start = header_length + i * record_length
        row = data[start : start + record_length]
        if len(row) < record_length or row[:1] == b"*":
            records.append({"\0deleted": True})
            continue
        record: dict[str, Any] = {}
        position = 1
        for name, kind, length in fields:
            raw = row[position : position + length]
            position += length
            text = raw.decode(encoding, "replace").strip().rstrip("\0")
            if kind in ("N", "F") and text:
                try:
                    record[name] = float(text) if "." in text or "e" in text.lower() else int(text)
                except ValueError:
                    record[name] = text
            else:
                record[name] = text
        records.append(record)
    return [f[0] for f in fields], records


def read_shapefile(data: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    members = _unpack(data, (".shp", ".dbf", ".prj", ".cpg"))
    shp = next((v for k, v in members.items() if k.endswith(".shp")), None)
    dbf = next((v for k, v in members.items() if k.endswith(".dbf")), None)
    if shp is None or dbf is None:
        raise GeoFileError("shp_incomplete")
    prj = next((v for k, v in members.items() if k.endswith(".prj")), None)
    if prj is not None and (b"PROJCS" in prj or not _WGS84.search(prj.decode("latin-1"))):
        raise GeoFileError("crs_unsupported")
    cpg = next((v for k, v in members.items() if k.endswith(".cpg")), b"").decode("latin-1").strip().lower()
    encoding = {"utf-8": "utf-8", "utf8": "utf-8", "1256": "cp1256", "cp1256": "cp1256"}.get(cpg, "utf-8")
    try:
        header, records = _dbf(dbf, encoding)
    except UnicodeDecodeError:
        header, records = _dbf(dbf, "cp1256")
    except struct.error:
        raise GeoFileError("shp_invalid") from None
    geometries: list[dict[str, Any] | None] = []
    offset = 100
    try:
        while offset + 8 <= len(shp):
            _, words = struct.unpack_from(">2i", shp, offset)
            content = shp[offset + 8 : offset + 8 + 2 * words]
            geometries.append(_shp_geometry(content))
            offset += 8 + 2 * words
    except struct.error:
        raise GeoFileError("shp_invalid") from None
    out: list[dict[str, Any]] = []
    for record, geometry in zip(records, geometries, strict=False):
        if record.get("\0deleted"):
            out.append({})
            continue
        out.append({**record, SHAPE: geometry})
    return header, out


# ---------------------------------------------------------------- GeoPackage


def _wkb(data: bytes, offset: int = 0) -> tuple[dict[str, Any], int]:
    """Read one WKB geometry (ISO or extended, any dimensions, kept in two) from ``offset``."""
    order = "<" if data[offset] == 1 else ">"
    (raw_type,) = struct.unpack_from(f"{order}I", data, offset + 1)
    offset += 5
    flags = raw_type & 0xE0000000  # EWKB: Z 0x80000000, M 0x40000000, SRID 0x20000000
    if flags & 0x20000000:
        offset += 4
    base = raw_type & 0x0FFFFFFF
    dims = 2 + (1 if flags & 0x80000000 else 0) + (1 if flags & 0x40000000 else 0)
    if base > 1000:  # ISO: 1000 Z, 2000 M, 3000 ZM
        dims = {1: 3, 2: 3, 3: 4}[base // 1000]
        base %= 1000

    def point() -> list[float]:
        nonlocal offset
        values = struct.unpack_from(f"{order}{dims}d", data, offset)
        offset += 8 * dims
        return [values[0], values[1]]

    def count() -> int:
        nonlocal offset
        (n,) = struct.unpack_from(f"{order}I", data, offset)
        offset += 4
        if n > MAX_VERTICES * 4:
            raise GeoFileError("too_many_vertices")
        return int(n)

    if base == 1:
        return {"type": "Point", "coordinates": point()}, offset
    if base == 2:
        return {"type": "LineString", "coordinates": [point() for _ in range(count())]}, offset
    if base == 3:
        return {"type": "Polygon", "coordinates": [[point() for _ in range(count())] for _ in range(count())]}, offset
    if base in (4, 5, 6):
        parts = []
        for _ in range(count()):
            part, offset = _wkb(data, offset)
            parts.append(part["coordinates"])
        name = {4: "MultiPoint", 5: "MultiLineString", 6: "MultiPolygon"}[base]
        return {"type": name, "coordinates": parts}, offset
    raise GeoFileError("geometry_unsupported")


def wkb_kind(element: Any) -> Kind | None:
    """The kind of a geometry read from PostGIS (a ``WKBElement``), from its WKB type."""
    data = getattr(element, "data", None)
    if data is None:
        return None
    raw = bytes.fromhex(data) if isinstance(data, str) else bytes(data)
    if len(raw) < 5:
        return None
    (code,) = struct.unpack_from("<I" if raw[0] == 1 else ">I", raw, 1)
    base = (code & 0x0FFFFFFF) % 1000
    kinds: dict[int, Kind] = {1: "point", 4: "point", 2: "line", 5: "line", 3: "area", 6: "area"}
    return kinds.get(base)


def gpkg_geometry(blob: bytes | None) -> dict[str, Any] | None:
    """A GeoPackage geometry: the ``GP`` header (envelope of 0, 32, 48 or 64 bytes), then WKB."""
    if not blob or blob[:2] != b"GP":
        return None
    flags = blob[3]
    if flags & 0x10:  # empty geometry
        return None
    envelope = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}.get((flags >> 1) & 0x07, 0)
    geometry, _ = _wkb(blob, 8 + envelope)
    return geometry


def read_geopackage(data: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    if data[:16] != b"SQLite format 3\0":
        raise GeoFileError("gpkg_invalid")
    handle, path = tempfile.mkstemp(suffix=".gpkg")
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        try:
            db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        except sqlite3.Error:
            raise GeoFileError("gpkg_invalid") from None
        try:
            # Views and triggers of an unknown file never run functions with side effects.
            db.execute("PRAGMA trusted_schema = OFF")
            found = db.execute(
                "SELECT c.table_name, g.column_name, g.srs_id FROM gpkg_contents c "
                "JOIN gpkg_geometry_columns g ON g.table_name = c.table_name "
                "WHERE c.data_type = 'features' ORDER BY c.table_name LIMIT 1"
            ).fetchone()
            if found is None:
                raise GeoFileError("gpkg_no_features")
            table, column, srs = found
            if srs != 4326:
                raise GeoFileError("crs_unsupported")
            cursor = db.execute(f'SELECT * FROM "{table.replace(chr(34), "")}"')  # noqa: S608 (name from the file's catalogue, quoted)
            header = [d[0] for d in cursor.description]
            records: list[dict[str, Any]] = []
            for values in cursor:
                record: dict[str, Any] = {}
                for name, value in zip(header, values, strict=True):
                    if name == column:
                        record[SHAPE] = gpkg_geometry(value)
                    elif not isinstance(value, bytes):
                        record[name] = value
                records.append(record)
            return [h for h in header if h != column], records
        except sqlite3.Error:
            raise GeoFileError("gpkg_invalid") from None
        finally:
            db.close()
    finally:
        os.unlink(path)
