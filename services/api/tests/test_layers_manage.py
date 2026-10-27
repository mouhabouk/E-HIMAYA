"""Map layers managed by the system administrator (phase L1a, docs/phase-l/design-layers.md §3 and §6): the new file
formats with lines and areas, who sees which layer and column, the sensitive layer, deleting and restoring layers and
places, settings revisions, the review of suggested names and duplicates, and a real enriched OpenStreetMap file."""

import io
import json
import sqlite3
import struct
import uuid
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.layers import cli, domain, geoformats
from app.modules.privacy import retention

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/layers"
PUBLIC = "/api/v1/layers"
OSM = Path(__file__).resolve().parents[3] / "data" / "osm"

# A beach near Sousse (clockwise outer ring, as a Shapefile writes it) and a river near Tunis.
BEACH = [[10.64, 35.83], [10.65, 35.83], [10.65, 35.82], [10.64, 35.82], [10.64, 35.83]]
RIVER = [[10.10, 36.80], [10.12, 36.81], [10.15, 36.81]]
SFAX = (34.7406, 10.7603)


def _admin(staff: Staff) -> dict[str, str]:
    return staff(["sysadmin"], gouvernorat=None)


def _minister(staff: Staff) -> dict[str, str]:
    return staff(["central_committee"], gouvernorat=None)


def _governor(staff: Staff) -> dict[str, str]:
    return staff(["local_committee"], gouvernorat=61)


# ---------------------------------------------------------------- files built here (no database)


def _shp_zip(prj: str = 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984"]]') -> bytes:
    """A zipped Shapefile with one polygon (the beach) and one line (the river), and their names."""

    def record(number: int, content: bytes) -> bytes:
        return struct.pack(">2i", number, len(content) // 2) + content

    def poly(shape_type: int, points: list[list[float]]) -> bytes:
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        out = struct.pack("<i4d2i", shape_type, min(xs), min(ys), max(xs), max(ys), 1, len(points))
        out += struct.pack("<i", 0)
        return out + b"".join(struct.pack("<2d", *p) for p in points)

    shp = bytes(100) + record(1, poly(5, BEACH)) + record(2, poly(3, RIVER))
    names = ["شاطئ بوجعفر".encode(), b"Oued Meliane"]
    width = 40
    header_length = 32 + 32 + 1
    dbf = struct.pack("<B3BIHH20x", 3, 126, 10, 27, len(names), header_length, 1 + width)
    dbf += b"name".ljust(11, b"\0") + b"C" + bytes(4) + bytes([width, 0]) + bytes(14) + b"\r"
    dbf += b"".join(b" " + n.ljust(width, b" ") for n in names) + b"\x1a"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("layer/beaches.shp", shp)
        z.writestr("layer/beaches.dbf", dbf)
        z.writestr("layer/beaches.prj", prj)
        z.writestr("layer/beaches.cpg", "UTF-8")
        z.writestr("../evil.shp", b"never read")
    return buffer.getvalue()


def _wkb_point(lon: float, lat: float) -> bytes:
    return struct.pack("<BI2d", 1, 1, lon, lat)


def _wkb_line(points: list[list[float]]) -> bytes:
    return struct.pack("<BII", 1, 2, len(points)) + b"".join(struct.pack("<2d", *p) for p in points)


def _gpkg(tmp_path: Path, srs: int = 4326) -> bytes:
    path = tmp_path / f"places-{srs}.gpkg"
    db = sqlite3.connect(path)
    db.executescript(
        "CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT);"
        "CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, srs_id INTEGER);"
        "CREATE TABLE places (fid INTEGER PRIMARY KEY, geom BLOB, name TEXT, phone TEXT);"
    )
    db.execute("INSERT INTO gpkg_contents VALUES ('places', 'features')")
    db.execute("INSERT INTO gpkg_geometry_columns VALUES ('places', 'geom', ?)", (srs,))
    header = b"GP\x00\x01" + struct.pack("<i", srs)  # little-endian, no envelope
    db.execute(
        "INSERT INTO places (geom, name, phone) VALUES (?, ?, ?)",
        (header + _wkb_point(SFAX[1], SFAX[0]), "Pharmacie de nuit", "74 000 111"),
    )
    db.execute("INSERT INTO places (geom, name, phone) VALUES (?, ?, ?)", (header + _wkb_line(RIVER), "Oued", None))
    db.commit()
    db.close()
    return path.read_bytes()


KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
  <Placemark><name>Forêt de Dar Chichou</name>
    <ExtendedData><Data name="type"><value>forêt</value></Data></ExtendedData>
    <Polygon><outerBoundaryIs><LinearRing><coordinates>
      10.90,36.90 10.95,36.90 10.95,36.95 10.90,36.95 10.90,36.90
    </coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
  <Placemark><name>Poste</name><Point><coordinates>10.7603,34.7406,0</coordinates></Point></Placemark>
</Document></kml>"""


def test_kml_and_kmz() -> None:
    parsed = domain.parse("forets.kml", KML.encode())
    assert parsed.format == "kml" and not parsed.rejected
    forest, post = parsed.rows
    assert (forest.name, forest.kind, forest.geometry) == ("Forêt de Dar Chichou", "forêt", "area")
    assert 36.9 < forest.lat < 36.95 and 10.9 < forest.lon < 10.95
    assert (post.geometry, post.lat, post.lon, post.shape) == ("point", 34.7406, 10.7603, None)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("doc.kml", KML)
    assert [r.name for r in domain.parse("forets.kmz", buffer.getvalue()).rows] == ["Forêt de Dar Chichou", "Poste"]
    # No document type: nothing to expand ("billion laughs") or fetch.
    evil = b'<?xml version="1.0"?><!DOCTYPE kml [<!ENTITY a "aaaa">]><kml>&a;</kml>'
    with pytest.raises(domain.FileError, match="kml_invalid"):
        domain.parse("x.kml", evil)


def test_shapefile() -> None:
    parsed = domain.parse("plages.zip", _shp_zip())
    assert parsed.format == "shp" and not parsed.rejected
    beach, river = parsed.rows
    assert (beach.name, beach.geometry, river.name, river.geometry) == ("شاطئ بوجعفر", "area", "Oued Meliane", "line")
    assert beach.shape is not None and beach.shape["type"] == "Polygon"
    # Carthage or Lambert: converted outside before the upload.
    lambert = 'PROJCS["Carthage / Nord Tunisie",GEOGCS["Carthage"]]'
    with pytest.raises(domain.FileError, match="crs_unsupported"):
        domain.parse("plages.zip", _shp_zip(lambert))


def test_geopackage(tmp_path: Path) -> None:
    parsed = domain.parse("lieux.gpkg", _gpkg(tmp_path))
    assert parsed.format == "gpkg"
    pharmacy, river = parsed.rows
    assert (pharmacy.name, pharmacy.lat, pharmacy.lon, pharmacy.phone) == (
        "Pharmacie de nuit",
        34.7406,
        10.7603,
        "+21674000111",
    )
    assert river.geometry == "line"
    with pytest.raises(domain.FileError, match="crs_unsupported"):
        domain.parse("lieux.gpkg", _gpkg(tmp_path, 22391))  # Carthage / Nord Tunisie


def test_too_large_a_shape() -> None:
    line = [[10 + i * 1e-5, 36.0] for i in range(geoformats.MAX_VERTICES + 1)]
    doc = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "LineString", "coordinates": line}, "properties": {"name": "x"}}
        ],
    }
    parsed = domain.parse("big.geojson", json.dumps(doc).encode())
    assert parsed.rows == [] and [r.reason for r in parsed.rejected] == ["too_many_vertices"]


def _enriched(features: list[dict[str, Any]]) -> bytes:
    return json.dumps({"type": "FeatureCollection", "features": features}).encode()


def _place(osm_id: int, lon: float, lat: float, name: str | None, suggested: str | None, confidence: str | None) -> Any:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "name": name or "(بدون اسم)",
            "osm_type": "node",
            "osm_id": osm_id,
            "osm_url": f"https://www.openstreetmap.org/node/{osm_id}",
            "name_suggested": suggested,
            "name_confidence": confidence,
            "name_source": "أقرب تجمّع" if suggested else None,
            "osm_snapshot": "2026-10-27",
            "phone": "74 241 511",
        },
    }


def test_enriched_names_and_duplicates() -> None:
    parsed = domain.parse(
        "h.geojson",
        _enriched(
            [
                _place(1, 10.7603, 34.7406, "مستشفى الهادي شاكر", None, "مؤكد"),
                _place(2, 10.7604, 34.7406, "مستشفى الهادي شاكر", None, None),
                _place(3, 10.6360, 35.8256, None, "مؤسسة استشفائية قرب سهلول", "مرتفعة"),
                _place(4, 10.1815, 36.8065, None, None, None),
            ]
        ),
    )
    first, second, suggested = parsed.rows
    # The confidence only matters for a suggested name.
    assert (first.ref, first.name_status, first.name_confidence) == ("osm:node/1", "official", None)
    assert first.source_url == "https://www.openstreetmap.org/node/1" and first.snapshot == "2026-10-27"
    assert first.duplicate and second.duplicate  # same name within 50 m
    assert (suggested.name, suggested.name_status, suggested.name_confidence) == (
        "مؤسسة استشفائية قرب سهلول",
        "suggested",
        "high",
    )
    assert not suggested.duplicate
    assert [r.reason for r in parsed.rejected] == ["name_missing"]


@pytest.mark.skipif(not OSM.is_dir(), reason="data/osm not in this checkout")
def test_every_osm_file_reads_and_has_settings() -> None:
    found = cli.files(OSM)
    assert "barracks" not in found and "oil_gas" not in found
    assert set(found) <= set(cli.PRESETS), set(found) - set(cli.PRESETS)
    rivers = domain.parse("rivers_enriched.geojson", found["rivers"].read_bytes())
    assert rivers.rows and {r.geometry for r in rivers.rows} == {"line"}
    beaches = domain.parse("beaches_enriched.geojson", found["beaches"].read_bytes())
    assert {"area", "point"} <= {r.geometry for r in beaches.rows}
    assert all(r.ref.startswith("osm:") for r in beaches.rows)


# ---------------------------------------------------------------- API helpers


async def _create(client: httpx.AsyncClient, staff: Staff, **extra: Any) -> dict[str, Any]:
    body = {
        "key": f"t_{uuid.uuid4().hex[:10]}",
        "name": {"ar": "طبقة", "fr": "Couche", "en": "Layer"},
        "icon": "pin",
        "colour": "#2E7D32",
        "source": "OpenStreetMap",
        "licence": "ODbL",
        "reason": "test of layer management",
        **extra,
    }
    r = await client.post(URL, json=body, headers=_admin(staff))
    assert r.status_code == 201, r.text
    return r.json()


async def _import(client: httpx.AsyncClient, staff: Staff, key: str, data: bytes, name: str) -> dict[str, Any]:
    admin = _admin(staff)
    r = await client.post(
        f"{URL}/{key}/imports",
        params={"file_name": name, "mode": "merge"},
        content=data,
        headers={**admin, "Content-Type": "application/octet-stream"},
    )
    assert r.status_code == 201, r.text
    applied = await client.post(
        f"{URL}/{key}/imports/{r.json()['id']}/apply", json={"reason": "first load"}, headers=admin
    )
    assert applied.status_code == 200, applied.text
    return r.json()


async def _patch(client: httpx.AsyncClient, staff: Staff, key: str, **changes: Any) -> httpx.Response:
    admin = _admin(staff)
    layers = (await client.get(URL, headers=admin)).json()
    layer = next(i for i in [*layers["items"], *layers["deleted"]] if i["key"] == key)
    return await client.patch(
        f"{URL}/{key}", json={"version": layer["version"], "reason": "settings change", **changes}, headers=admin
    )


def _keys(r: httpx.Response) -> set[str]:
    return {i["key"] for i in r.json()["items"]}


# ---------------------------------------------------------------- API


async def test_lines_and_areas_on_the_map(client: httpx.AsyncClient, staff: Staff) -> None:
    layer = await _create(client, staff, status="published", audiences=["room", "field", "command"])
    key = layer["key"]
    await _import(client, staff, key, _shp_zip(), "plages.zip")
    features = (await client.get(f"{URL}/{key}/features", headers=staff())).json()["items"]
    assert {f["name"]: f["geometry"] for f in features} == {"شاطئ بوجعفر": "area", "Oued Meliane": "line"}
    beach = next(f for f in features if f["geometry"] == "area")
    # The point of an area is on its surface (the region and "nearest" use it).
    assert 35.82 <= beach["lat"] <= 35.83 and 10.64 <= beach["lon"] <= 10.65 and beach["gouvernorat_code"] == 51
    r = await client.get(f"{URL}/{key}/shapes", params={"bbox": "10.0,35.0,11.0,37.0", "zoom": 12}, headers=staff())
    assert r.status_code == 200, r.text
    kinds = {f["properties"]["name"]: f["geometry"]["type"] for f in r.json()["features"]}
    assert kinds == {"شاطئ بوجعفر": "Polygon", "Oued Meliane": "LineString"}
    listed = next(i for i in (await client.get(URL, headers=_admin(staff))).json()["items"] if i["key"] == key)
    assert listed["geometry"] == "mixed"
    # Exported with its shapes: the file comes back the same.
    export = await client.get(f"{URL}/{key}/export", params={"format": "geojson"}, headers=_admin(staff))
    types = {f["geometry"]["type"] for f in export.json()["features"]}
    assert types == {"Polygon", "LineString"}


async def test_draft_audiences_and_scope(client: httpx.AsyncClient, staff: Staff) -> None:
    layer = await _create(client, staff)
    key = layer["key"]
    assert layer["status"] == "draft" and layer["enabled"] is False
    await _import(client, staff, key, _gpkg_api(), "lieux.geojson")
    operator, field = staff(["operator"], gouvernorat=None), staff(["field_commander"], gouvernorat=None)
    # A draft: the administrator alone.
    assert key not in _keys(await client.get(URL, headers=operator))
    assert (await client.get(f"{URL}/{key}/features", headers=operator)).status_code == 404
    assert key not in _keys(await client.get(PUBLIC))

    r = await _patch(client, staff, key, status="published", audiences=["room"])
    assert r.status_code == 200 and r.json()["enabled"] is True and r.json()["audience"] == "staff"
    assert (await client.get(f"{URL}/{key}/features", headers=operator)).status_code == 200
    assert (await client.get(f"{URL}/{key}/features", headers=field)).status_code == 404
    assert key not in _keys(await client.get(PUBLIC))

    # Limited to Sfax: the regional room of Sfax sees it, the one of Sousse does not, the national one does.
    await _patch(client, staff, key, scope=[61])
    assert (await client.get(f"{URL}/{key}/features", headers=staff(["operator"], gouvernorat=61))).status_code == 200
    assert (await client.get(f"{URL}/{key}/features", headers=staff(["operator"], gouvernorat=51))).status_code == 404
    assert (await client.get(f"{URL}/{key}/features", headers=operator)).status_code == 200

    # Citizens too: on the public list and map.
    r = await _patch(client, staff, key, audiences=["citizen", "room"], scope=[])
    assert r.json()["audience"] == "public"
    assert key in _keys(await client.get(PUBLIC))
    near = f"{SFAX[0]},{SFAX[1]}"
    assert [i["name"] for i in (await client.get(f"{PUBLIC}/{key}/features", params={"near": near})).json()["items"]]

    # Paused: off every map, kept for the administrator.
    await _patch(client, staff, key, status="paused")
    assert (await client.get(f"{PUBLIC}/{key}/features", params={"near": near})).status_code == 404
    assert (await client.get(f"{URL}/{key}/features", headers=operator)).status_code == 404


def _gpkg_api() -> bytes:
    """GeoJSON of the same two places as the GeoPackage (one point in Sfax, one line), for the API tests."""
    return _enriched(
        [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [SFAX[1], SFAX[0]]},
                "properties": {"name": "Pharmacie de nuit", "phone": "74 000 111", "manager": "Dr X"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": RIVER},
                "properties": {"name": "Oued"},
            },
        ]
    )


async def test_fields_by_audience(client: httpx.AsyncClient, staff: Staff) -> None:
    layer = await _create(
        client,
        staff,
        status="published",
        audiences=["citizen", "room", "field"],
        fields={"phone": ["room"], "manager": ["room"]},
    )
    key = layer["key"]
    await _import(client, staff, key, _gpkg_api(), "lieux.geojson")
    room = (await client.get(f"{URL}/{key}/features", headers=staff())).json()["items"]
    field = (await client.get(f"{URL}/{key}/features", headers=staff(["team_leader"]))).json()["items"]
    pharmacy = next(f for f in room if f["name"] == "Pharmacie de nuit")
    assert pharmacy["phone"] == "+21674000111" and pharmacy["props"]["manager"] == "Dr X"
    pharmacy = next(f for f in field if f["name"] == "Pharmacie de nuit")
    assert pharmacy["phone"] is None and "manager" not in pharmacy["props"]
    # Never to the citizen, even asked directly.
    public = (await client.get(f"{PUBLIC}/{key}/features", params={"near": f"{SFAX[0]},{SFAX[1]}"})).json()["items"]
    assert public[0]["phone"] is None and "manager" not in public[0]["props"]


async def test_sensitive_layer_for_the_minister_alone(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    r = await client.post(
        URL,
        json={
            "key": f"t_{uuid.uuid4().hex[:10]}",
            "name": {"ar": "حساسة", "fr": "Sensible", "en": "Sensitive"},
            "icon": "pin",
            "colour": "#37474F",
            "reason": "sensitive test layer",
            "status": "published",
            "audiences": ["citizen", "room", "command"],
            "sensitive": True,
        },
        headers=_admin(staff),
    )
    assert r.status_code == 201, r.text
    layer = r.json()
    key = layer["key"]
    assert layer["sensitive"] is True and "citizen" not in layer["audiences"] and layer["audience"] == "staff"
    await _import(client, staff, key, _gpkg_api(), "s.geojson")

    assert (await client.get(f"{URL}/{key}/features", headers=_minister(staff))).status_code == 200
    # Never a governor, a regional or national room, nor the citizen.
    for headers in (
        _governor(staff),
        staff(["local_committee"], gouvernorat=None),
        staff(),
        staff(["operator"], gouvernorat=None),
    ):
        assert (await client.get(f"{URL}/{key}/features", headers=headers)).status_code == 404
        assert key not in _keys(await client.get(URL, headers=headers))
    assert key not in _keys(await client.get(PUBLIC))
    assert (await client.get(f"{PUBLIC}/{key}/features", params={"near": "34.7,10.7"})).status_code == 404
    # Every read of its places is in the audit log.
    reads = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'layer.sensitive_read' AND target = :t"),
        {"t": f"layer:{key}"},
    )
    assert reads == 1


async def test_delete_restore_and_purge_a_layer(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    layer = await _create(client, staff, status="published", audiences=["citizen", "room"])
    key, admin = layer["key"], _admin(staff)
    await _import(client, staff, key, _gpkg_api(), "x.geojson")
    assert (await client.request("DELETE", f"{URL}/{key}", json={"reason": "x"}, headers=admin)).status_code == 422
    r = await client.request("DELETE", f"{URL}/{key}", json={"reason": "مكررة"}, headers=staff())
    assert r.status_code == 403
    r = await client.request("DELETE", f"{URL}/{key}", json={"reason": "duplicate layer"}, headers=admin)
    assert r.status_code == 200 and r.json()["deleted_at"] and r.json()["purge_at"]
    # Off every map at once; in the administrator's "deleted" list.
    assert key not in _keys(await client.get(PUBLIC))
    assert (await client.get(f"{URL}/{key}/features", headers=staff())).status_code == 404
    listed = (await client.get(URL, headers=admin)).json()
    assert key not in {i["key"] for i in listed["items"]} and key in {i["key"] for i in listed["deleted"]}
    assert (await _patch(client, staff, key, colour="#283593")).json()["detail"] == "layer_deleted"

    # Restored as it was, but paused: published again by choice.
    r = await client.post(f"{URL}/{key}/restore", json={"reason": "deleted by mistake"}, headers=admin)
    assert r.status_code == 200 and r.json()["status"] == "paused" and r.json()["deleted_at"] is None
    assert len((await client.get(f"{URL}/{key}/features", headers=admin)).json()["items"]) == 2
    r = await client.request("DELETE", f"{URL}/{key}/purge", json={"reason": "erase now"}, headers=admin)
    assert (r.status_code, r.json()["detail"]) == (409, "not_deleted")

    await client.request("DELETE", f"{URL}/{key}", json={"reason": "replaced by another"}, headers=admin)
    r = await client.request("DELETE", f"{URL}/{key}/purge", json={"reason": "erase it now"}, headers=admin)
    assert r.status_code == 204
    assert (await client.get(f"{URL}/{key}/features", headers=admin)).status_code == 404
    actions = (
        await session.scalars(
            text("SELECT action FROM audit.log WHERE target = :t ORDER BY seq"), {"t": f"layer:{key}"}
        )
    ).all()
    assert actions[-4:] == ["layer.delete", "layer.restore", "layer.delete", "layer.purge"]
    # The units' layer is never deleted.
    r = await client.request("DELETE", f"{URL}/civil_protection", json={"reason": "not possible"}, headers=admin)
    assert r.status_code == 404


async def test_retention_erases_after_30_days(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    kept = await _create(client, staff)
    old = await _create(client, staff)
    admin = _admin(staff)
    await _import(client, staff, kept["key"], _gpkg_api(), "x.geojson")
    for key in (kept["key"], old["key"]):
        await client.request("DELETE", f"{URL}/{key}", json={"reason": "no longer used"}, headers=admin)
    async with session.begin():
        await session.execute(
            text("UPDATE geo.layer SET deleted_at = now() - interval '31 days' WHERE key = :k"), {"k": old["key"]}
        )
    async with session.begin():
        erased = await retention.purge_deleted_layers(session, get_settings(), datetime.now(UTC))
    assert erased >= 1
    keys = set((await session.scalars(text("SELECT key FROM geo.layer"))).all())
    await session.commit()
    assert old["key"] not in keys and kept["key"] in keys
    # A place deleted more than 30 days ago is erased too, the others stay.
    async with session.begin():
        await session.execute(
            text(
                "UPDATE geo.layer_feature SET deleted_at = :at FROM geo.layer l "
                "WHERE l.id = geo.layer_feature.layer_id AND l.key = :k AND geo.layer_feature.name = 'Oued'"
            ),
            {
                "k": kept["key"],
                "at": datetime.now(UTC) - timedelta(days=get_settings().retention_layer_deleted_days + 1),
            },
        )
    async with session.begin():
        assert await retention.purge_deleted_features(session, get_settings(), datetime.now(UTC)) >= 1
    names = (
        await session.scalars(
            text("SELECT f.name FROM geo.layer_feature f JOIN geo.layer l ON l.id = f.layer_id WHERE l.key = :k"),
            {"k": kept["key"]},
        )
    ).all()
    assert names == ["Pharmacie de nuit"]


async def test_delete_and_restore_a_place(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    layer = await _create(client, staff, status="published", audiences=["citizen", "room"])
    key, admin = layer["key"], _admin(staff)
    await _import(client, staff, key, _gpkg_api(), "x.geojson")
    near = {"near": f"{SFAX[0]},{SFAX[1]}"}
    place = next(
        f
        for f in (await client.get(f"{URL}/{key}/features", headers=admin)).json()["items"]
        if f["geometry"] == "point"
    )
    r = await client.request(
        "DELETE", f"{URL}/{key}/features/{place['id']}", json={"reason": "closed for good"}, headers=admin
    )
    assert r.status_code == 200 and r.json()["deleted_at"]
    assert (await client.get(f"{PUBLIC}/{key}/features", params=near)).json()["items"] == []
    assert [f["name"] for f in (await client.get(f"{URL}/{key}/features", headers=staff())).json()["items"]] == ["Oued"]
    deleted = (await client.get(f"{URL}/{key}/features", params={"deleted": True}, headers=admin)).json()["items"]
    assert [(f["id"], f["delete_reason"]) for f in deleted] == [(place["id"], "closed for good")]
    assert (await client.get(f"{URL}/{key}/features", params={"deleted": True}, headers=staff())).status_code == 403
    r = await client.post(f"{URL}/{key}/features/{place['id']}/restore", json={"reason": "open again"}, headers=admin)
    assert r.status_code == 200 and r.json()["deleted_at"] is None
    assert [i["name"] for i in (await client.get(f"{PUBLIC}/{key}/features", params=near)).json()["items"]] == [
        "Pharmacie de nuit"
    ]
    snapshot = await session.scalar(
        text("SELECT details FROM audit.log WHERE action = 'layer.feature_delete' AND target = :t"),
        {"t": f"layer:{key}"},
    )
    assert snapshot["name"] == "Pharmacie de nuit"


async def test_settings_revisions(client: httpx.AsyncClient, staff: Staff) -> None:
    layer = await _create(client, staff, colour="#2E7D32")
    key, admin = layer["key"], _admin(staff)
    await _patch(client, staff, key, colour="#283593", status="published", audiences=["room"])
    await _patch(client, staff, key, fields={"phone": ["room"]})
    revisions = (await client.get(f"{URL}/{key}/revisions", headers=admin)).json()["items"]
    assert [r["number"] for r in revisions] == [3, 2, 1]
    assert revisions[0]["changes"] == ["fields"] and {"colour", "status", "audiences"} <= set(revisions[1]["changes"])
    assert (await client.get(f"{URL}/{key}/revisions", headers=staff())).status_code == 403
    r = await client.post(f"{URL}/{key}/revisions/1/restore", json={"reason": "back to the start"}, headers=admin)
    assert r.status_code == 200, r.text
    back = r.json()
    assert (back["colour"], back["status"], back["fields"]) == ("#2E7D32", "draft", layer["fields"])
    assert next(r["number"] for r in (await client.get(f"{URL}/{key}/revisions", headers=admin)).json()["items"]) == 4


async def test_review_of_suggested_names(client: httpx.AsyncClient, staff: Staff) -> None:
    layer = await _create(client, staff, status="published", audiences=["citizen", "room"])
    key, admin = layer["key"], _admin(staff)
    await _import(
        client,
        staff,
        key,
        _enriched(
            [
                _place(1, 10.7603, 34.7406, "مستشفى الهادي شاكر", None, None),
                _place(2, 10.7604, 34.7406, "مستشفى الهادي شاكر", None, None),
                _place(3, 10.6360, 35.8256, None, "مؤسسة استشفائية قرب سهلول", "مرتفعة"),
                _place(4, 10.1815, 36.8065, None, "مؤسسة قرب باب سعدون", "منخفضة"),
                _place(5, 10.0963, 35.6781, None, "مؤسسة قرب القيروان", "للمراجعة"),
            ]
        ),
        "hospitals_enriched.geojson",
    )
    box = {"bbox": "9.0,33.0,12.0,38.0"}

    async def public_names() -> list[str]:
        items = (await client.get(f"{PUBLIC}/{key}/features", params=box)).json()["items"]
        return sorted(i["name"] for i in items)

    # The citizen sees official names only; the staff see the suggested ones, marked.
    assert await public_names() == ["مستشفى الهادي شاكر", "مستشفى الهادي شاكر"]
    staff_items = (await client.get(f"{URL}/{key}/features", headers=staff())).json()["items"]
    assert sorted(f["name_status"] for f in staff_items) == [
        "official",
        "official",
        "suggested",
        "suggested",
        "suggested",
    ]

    queue = (await client.get(f"{URL}/{key}/review", headers=admin)).json()
    assert queue["total"] == 3 and queue["counts"] == {"high": 1, "low": 1, "review": 1, "duplicates": 2}
    assert (await client.get(f"{URL}/{key}/review", headers=staff())).status_code == 403
    r = await client.post(
        f"{URL}/{key}/review", json={"accept_confidence": ["high"], "reason": "checked"}, headers=admin
    )
    assert r.json()["accepted"] == 1
    low = (await client.get(f"{URL}/{key}/review", params={"confidence": "low"}, headers=admin)).json()["items"][0]
    other = (await client.get(f"{URL}/{key}/review", params={"confidence": "review"}, headers=admin)).json()["items"][0]
    r = await client.post(
        f"{URL}/{key}/review",
        json={
            "items": [
                {"id": low["id"], "action": "edit", "name": "مستشفى شارل نيكول"},
                {"id": other["id"], "action": "reject"},
            ],
            "reason": "names checked on site",
        },
        headers=admin,
    )
    assert (r.json()["edited"], r.json()["rejected"]) == (1, 1)
    assert await public_names() == sorted(
        ["مستشفى الهادي شاكر", "مستشفى الهادي شاكر", "مؤسسة استشفائية قرب سهلول", "مستشفى شارل نيكول"]
    )

    # The two "Hédi Chaker": merged, one stays.
    duplicates = (await client.get(f"{URL}/{key}/review", params={"duplicates": True}, headers=admin)).json()["items"]
    first, second = duplicates
    r = await client.post(
        f"{URL}/{key}/review",
        json={"items": [{"id": second["id"], "action": "merge", "into": first["id"]}], "reason": "same hospital"},
        headers=admin,
    )
    assert r.json()["merged"] == 1
    assert (await public_names()).count("مستشفى الهادي شاكر") == 1
    assert (await client.get(f"{URL}/{key}/review", params={"duplicates": True}, headers=admin)).json()["total"] == 0
    # An import again keeps the administrator's decisions.
    again = await client.post(
        f"{URL}/{key}/imports",
        params={"file_name": "hospitals_enriched.geojson", "mode": "merge"},
        content=_enriched([_place(4, 10.1815, 36.8065, None, "مؤسسة قرب باب سعدون", "منخفضة")]),
        headers={**admin, "Content-Type": "application/octet-stream"},
    )
    assert again.json()["counts"]["unchanged"] == 1


@pytest.mark.skipif(not (OSM / "layers" / "hospitals_enriched.geojson").is_file(), reason="data/osm not here")
async def test_real_osm_hospitals(client: httpx.AsyncClient, staff: Staff) -> None:
    layer = await _create(client, staff, icon="hospital", colour="#C62828")
    key, admin = layer["key"], _admin(staff)
    data = (OSM / "layers" / "hospitals_enriched.geojson").read_bytes()
    preview = await _import(client, staff, key, data, "hospitals_enriched.geojson")
    assert preview["counts"]["new"] > 200 and preview["counts"]["rejected"] == 0
    queue = (await client.get(f"{URL}/{key}/review", headers=admin)).json()
    assert queue["total"] > 0 and queue["counts"]["duplicates"] > 0
    listed = next(i for i in (await client.get(URL, headers=admin)).json()["items"] if i["key"] == key)
    assert listed["quality"]["suggested"] == queue["total"]
