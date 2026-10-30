"""Map data layers (phase B1, docs/phase-b/design.md §2): preview, apply and undo an import; places for the maps.

* **Preview** parses the file (``domain.parse``), places each row in its gouvernorat (outside every boundary, beyond a
  coastal margin → rejected) and compares it with the layer: new, updated, unchanged and, in *replace* mode, removed.
  Nothing changes on the map; the checked rows wait in ``geo.layer_import.rows``.
* **Apply** writes the changes, keeps what they replaced in ``undo`` and bumps the layer's ``data_version``. It is
  refused when the layer changed after the preview (another import or a correction by hand): preview again.
* **Undo** restores what the last applied import replaced, only while nothing changed after it.

Phase L1a (docs/phase-l/design-layers.md §3): places may be lines or areas (``shape``; ``location`` becomes a point on
their surface), carry a suggested name until the administrator accepts it (the citizen's app reads only official
or accepted names), and are deleted softly (``deleted_at``) so they can be restored.
"""

import re
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from geoalchemy2 import Geography as Geography_
from geoalchemy2 import Geometry
from sqlalchemy import ColumnElement, cast, delete, func, insert, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.geo.models import Delegation, Layer, LayerFeature, LayerImport
from app.modules.layers import access, domain, geoformats

# Points just outside a simplified boundary (harbours, coastal hospitals) still belong to the nearest gouvernorat.
COAST_MARGIN_M = 5_000
# A preview not applied within a day is stale: the file is uploaded again.
PREVIEW_TTL_S = 24 * 3600
CHANGES = ("new", "updated", "unchanged", "removed")
# Names the citizen's app may show (a suggested or rejected name stays with the staff).
PUBLIC_NAMES = ("official", "accepted")
SHAPE_WKT = func.ST_AsText(LayerFeature.shape)


def point(lat: float, lon: float) -> str:
    return f"SRID=4326;POINT({lon} {lat})"


LAT = func.ST_Y(cast(LayerFeature.location, Geometry))
LON = func.ST_X(cast(LayerFeature.location, Geometry))


# ---------------------------------------------------------------- positions


async def locate(session: AsyncSession, rows: Sequence[domain.Row]) -> list[int | None]:
    """Gouvernorat of each row: the one containing it, else the nearest within ``COAST_MARGIN_M``, else None."""
    if not rows:
        return []
    params = {"lons": [r.lon for r in rows], "lats": [r.lat for r in rows]}
    found = await session.execute(
        text(
            """
            SELECT t.i, (SELECT g.code FROM geo.gouvernorat g
                         WHERE ST_Intersects(g.boundary, ST_SetSRID(ST_MakePoint(t.lon, t.lat), 4326)) LIMIT 1)
            FROM unnest(CAST(:lons AS float8[]), CAST(:lats AS float8[])) WITH ORDINALITY AS t(lon, lat, i)
            """
        ),
        params,
    )
    codes: list[int | None] = [None] * len(rows)
    for i, code in found.all():
        codes[i - 1] = code
    missing = [i for i, c in enumerate(codes) if c is None]
    if missing:
        near = await session.execute(
            text(
                """
                SELECT t.i, (SELECT g.code FROM geo.gouvernorat g
                             WHERE ST_DWithin(CAST(g.boundary AS geography),
                                              CAST(ST_SetSRID(ST_MakePoint(t.lon, t.lat), 4326) AS geography), :m)
                             ORDER BY ST_Distance(CAST(g.boundary AS geography),
                                                  CAST(ST_SetSRID(ST_MakePoint(t.lon, t.lat), 4326) AS geography))
                             LIMIT 1)
                FROM unnest(CAST(:lons AS float8[]), CAST(:lats AS float8[])) WITH ORDINALITY AS t(lon, lat, i)
                """
            ),
            {
                "lons": [rows[i].lon for i in missing],
                "lats": [rows[i].lat for i in missing],
                "m": COAST_MARGIN_M,
            },
        )
        for i, code in near.all():
            codes[missing[i - 1]] = code
    return codes


async def delegation_index(session: AsyncSession) -> dict[tuple[int, str], int]:
    """(gouvernorat, normalised Arabic or French name) → délégation id, to match the file's "délégation" column."""
    index: dict[tuple[int, str], int] = {}
    for d in await session.scalars(select(Delegation)):
        index[(d.gouvernorat_code, domain.normalize_heading(d.name_ar))] = d.id
        index[(d.gouvernorat_code, domain.normalize_heading(d.name_fr))] = d.id
    return index


# ---------------------------------------------------------------- comparing with the layer


def _comparable(
    name: str,
    kind: str | None,
    phone: str | None,
    lat: float,
    lon: float,
    props: dict[str, Any],
    shape: str | None = None,
    quality: tuple[Any, ...] = (),
) -> tuple[Any, ...]:
    return (name, kind, phone, round(lat, 6), round(lon, 6), sorted(props.items()), shape, quality)


def _shape_text(shape: dict[str, Any] | None) -> str | None:
    """The shape as PostGIS writes it back (``ST_AsText``), to compare a file with the layer."""
    return geoformats.to_wkt(shape).split(";", 1)[1].replace(", ", ",") if shape else None


def _quality(source_url: str | None, snapshot: str | None) -> tuple[Any, ...]:
    return (source_url, snapshot)


@dataclass(slots=True)
class Current:
    id: uuid.UUID
    ref: str
    name: str
    kind: str | None
    phone: str | None
    lat: float
    lon: float
    props: dict[str, Any]
    hidden: bool
    shape: str | None
    name_status: str
    source_url: str | None
    snapshot: str | None
    deleted: bool

    def comparable(self) -> tuple[Any, ...]:
        return _comparable(
            self.name,
            self.kind,
            self.phone,
            self.lat,
            self.lon,
            self.props,
            self.shape,
            _quality(self.source_url, self.snapshot),
        )


async def current_features(session: AsyncSession, layer_id: uuid.UUID) -> dict[str, Current]:
    rows = await session.execute(
        select(
            LayerFeature.id,
            LayerFeature.ref,
            LayerFeature.name,
            LayerFeature.kind,
            LayerFeature.phone,
            LAT,
            LON,
            LayerFeature.props,
            LayerFeature.hidden,
            func.replace(SHAPE_WKT, ", ", ","),
            LayerFeature.name_status,
            LayerFeature.source_url,
            LayerFeature.snapshot_at,
            LayerFeature.deleted_at,
        ).where(LayerFeature.layer_id == layer_id)
    )
    return {
        r.ref: Current(
            r.id,
            r.ref,
            r.name,
            r.kind,
            r.phone,
            float(r[5]),
            float(r[6]),
            r.props or {},
            r.hidden,
            r[9],
            r.name_status,
            r.source_url,
            r.snapshot_at.isoformat() if r.snapshot_at else None,
            r.deleted_at is not None,
        )
        for r in rows.all()
    }


@dataclass(slots=True)
class Preview:
    rows: list[dict[str, Any]]
    counts: dict[str, int]
    rejected: list[dict[str, Any]]
    warnings: list[dict[str, Any]]


async def build_preview(session: AsyncSession, layer: Layer, parsed: domain.Parsed, mode: str) -> Preview:
    codes = await locate(session, parsed.rows)
    delegations = await delegation_index(session)
    current = await current_features(session, layer.id)
    rejected = [{"line": r.line, "reason": r.reason, "name": r.name} for r in parsed.rejected]
    rows: list[dict[str, Any]] = []
    counts = dict.fromkeys(CHANGES, 0)
    seen: set[str] = set()
    for row, code in zip(parsed.rows, codes, strict=True):
        if code is None:
            rejected.append({"line": row.line, "reason": "outside_tunisia", "name": row.name})
            continue
        item = row.to_json()
        item["gouvernorat_code"] = code
        named = row.props.get("delegation")
        item["delegation_id"] = delegations.get((code, domain.normalize_heading(named))) if named else None
        existing = current.get(row.ref)
        seen.add(row.ref)
        if existing is None:
            change = "new"
        else:
            # A name the administrator accepted, edited or rejected stays theirs while the file only suggests one.
            if row.name_status == "suggested" and existing.name_status in ("accepted", "rejected"):
                item["name"], item["name_status"] = existing.name, existing.name_status
            file_shape = _shape_text(row.shape)
            if row.shape is not None and existing.shape is not None:
                file_shape = existing.shape if _same_shape(existing.shape, file_shape) else file_shape
            same = existing.comparable() == _comparable(
                item["name"],
                row.kind,
                row.phone,
                row.lat if row.shape is None else existing.lat,
                row.lon if row.shape is None else existing.lon,
                row.props,
                file_shape,
                _quality(row.source_url, row.snapshot),
            )
            same = same and (row.hidden is None or row.hidden == existing.hidden)
            change = "unchanged" if same else "updated"
            item["feature_id"] = str(existing.id)
        item["change"] = change
        counts[change] += 1
        rows.append(item)
    if mode == "replace":
        for ref, existing in current.items():
            if ref not in seen and not existing.deleted:
                counts["removed"] += 1
                rows.append(
                    {
                        "change": "removed",
                        "ref": ref,
                        "name": existing.name,
                        "lat": existing.lat,
                        "lon": existing.lon,
                        "feature_id": str(existing.id),
                    }
                )
    rejected.sort(key=lambda r: int(r["line"] or 0))
    counts["rejected"] = len(rejected)
    counts["warnings"] = len(parsed.warnings)
    counts["rows"] = len(parsed.rows) + len(parsed.rejected)
    warnings = [{"line": w.line, "column": w.column, "reason": w.reason} for w in parsed.warnings]
    return Preview(rows, counts, rejected[: domain.MAX_REPORTED], warnings[: domain.MAX_REPORTED])


# ---------------------------------------------------------------- applying and undoing


def _same_shape(stored: str, from_file: str | None) -> bool:
    """PostGIS writes numbers back in its own way; two shapes are the same when their numbers agree to 1e-7."""
    if from_file is None:
        return False
    numbers = re.compile(r"-?\d+(?:\.\d+)?(?:e-?\d+)?")
    a, b = numbers.findall(stored), numbers.findall(from_file)
    return len(a) == len(b) and all(abs(float(x) - float(y)) < 1e-7 for x, y in zip(a, b, strict=True))


def _snapshot(f: LayerFeature, lat: float, lon: float, shape: str | None = None) -> dict[str, Any]:
    return {
        "id": str(f.id),
        "ref": f.ref,
        "name": f.name,
        "kind": f.kind,
        "phone": f.phone,
        "lat": lat,
        "lon": lon,
        "gouvernorat_code": f.gouvernorat_code,
        "delegation_id": f.delegation_id,
        "props": f.props,
        "hidden": f.hidden,
        "import_id": str(f.import_id) if f.import_id else None,
        "version": f.version,
        "updated_by": f.updated_by,
        "updated_at": f.updated_at.isoformat(),
        "shape": shape,
        "name_status": f.name_status,
        "suggested_name": f.suggested_name,
        "name_confidence": f.name_confidence,
        "name_source": f.name_source,
        "source_url": f.source_url,
        "snapshot_at": f.snapshot_at.isoformat() if f.snapshot_at else None,
        "possible_duplicate": f.possible_duplicate,
        "deleted_at": f.deleted_at.isoformat() if f.deleted_at else None,
        "deleted_by": f.deleted_by,
        "delete_reason": f.delete_reason,
    }


async def _snapshots(session: AsyncSession, ids: Iterable[uuid.UUID]) -> list[dict[str, Any]]:
    wanted = list(ids)
    out: list[dict[str, Any]] = []
    for start in range(0, len(wanted), 5000):
        found = await session.execute(
            select(LayerFeature, LAT, LON, SHAPE_WKT).where(LayerFeature.id.in_(wanted[start : start + 5000]))
        )
        out += [_snapshot(f, float(lat), float(lon), shape) for f, lat, lon, shape in found.all()]
    return out


def _date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _values(item: dict[str, Any], layer_id: uuid.UUID, import_id: uuid.UUID, actor: str) -> dict[str, Any]:
    shape = item.get("shape")
    return {
        "layer_id": layer_id,
        "ref": item["ref"],
        "name": item["name"],
        "kind": item["kind"],
        "phone": item["phone"],
        "location": point(item["lat"], item["lon"]),
        "gouvernorat_code": item["gouvernorat_code"],
        "delegation_id": item["delegation_id"],
        "props": item["props"],
        "hidden": bool(item["hidden"]),
        "import_id": import_id,
        "updated_by": actor,
        "shape": geoformats.to_wkt(shape) if shape else None,
        "name_status": item.get("name_status") or "official",
        "suggested_name": item.get("suggested_name"),
        "name_confidence": item.get("name_confidence"),
        "name_source": item.get("name_source"),
        "source_url": item.get("source_url"),
        "snapshot_at": _date(item.get("snapshot")),
        "possible_duplicate": bool(item.get("duplicate")),
        "deleted_at": None,
        "deleted_by": None,
        "delete_reason": None,
    }


async def apply(session: AsyncSession, layer: Layer, job: LayerImport, actor: str) -> None:
    """Write the previewed changes. The caller checked the layer did not change since the preview."""
    rows = job.rows or []
    by_change: dict[str, list[dict[str, Any]]] = {c: [] for c in CHANGES}
    for item in rows:
        by_change[item["change"]].append(item)
    replaced_ids = [uuid.UUID(i["feature_id"]) for i in by_change["updated"] + by_change["removed"]]
    previous = await _snapshots(session, replaced_ids)

    now = datetime.now(UTC)
    for item in by_change["updated"]:
        values = _values(item, layer.id, job.id, actor)
        if item["hidden"] is None:
            values.pop("hidden")
        # A place the administrator deleted stays deleted when a new extract still has it.
        for key in ("deleted_at", "deleted_by", "delete_reason"):
            values.pop(key)
        await session.execute(
            update(LayerFeature)
            .where(LayerFeature.id == uuid.UUID(item["feature_id"]))
            .values(**values, version=LayerFeature.version + 1, updated_at=now)
        )
    if by_change["removed"]:
        removed = [uuid.UUID(i["feature_id"]) for i in by_change["removed"]]
        for start in range(0, len(removed), 5000):
            await session.execute(delete(LayerFeature).where(LayerFeature.id.in_(removed[start : start + 5000])))
    inserted: list[str] = []
    new = by_change["new"]
    for start in range(0, len(new), 2000):
        chunk = [_values(i, layer.id, job.id, actor) for i in new[start : start + 2000]]
        ids = await session.scalars(insert(LayerFeature).returning(LayerFeature.id), chunk)
        inserted += [str(i) for i in ids]

    # A line or an area stands on the map by a point on its surface (the middle of a river, inside a forest).
    await session.execute(
        update(LayerFeature)
        .where(LayerFeature.import_id == job.id, LayerFeature.shape.is_not(None))
        .values(location=cast(func.ST_PointOnSurface(cast(LayerFeature.shape, Geometry)), Geography_))
    )
    layer.data_version += 1
    job.status, job.applied_at, job.result_version = "applied", now, layer.data_version
    job.undo = {"inserted": inserted, "previous": previous}
    job.rows = None  # the applied rows now live in geo.layer_feature


async def undo(session: AsyncSession, layer: Layer, job: LayerImport) -> None:
    """Put back what ``job`` replaced. The caller checked nothing changed in the layer after it."""
    saved = job.undo or {}
    inserted = [uuid.UUID(i) for i in saved.get("inserted", [])]
    for start in range(0, len(inserted), 5000):
        await session.execute(delete(LayerFeature).where(LayerFeature.id.in_(inserted[start : start + 5000])))
    previous = saved.get("previous", [])
    ids = [uuid.UUID(p["id"]) for p in previous]
    for start in range(0, len(ids), 5000):
        await session.execute(delete(LayerFeature).where(LayerFeature.id.in_(ids[start : start + 5000])))
    rows = [
        {
            "id": uuid.UUID(p["id"]),
            "layer_id": layer.id,
            "ref": p["ref"],
            "name": p["name"],
            "kind": p["kind"],
            "phone": p["phone"],
            "location": point(p["lat"], p["lon"]),
            "gouvernorat_code": p["gouvernorat_code"],
            "delegation_id": p["delegation_id"],
            "props": p["props"],
            "hidden": p["hidden"],
            "import_id": uuid.UUID(p["import_id"]) if p.get("import_id") else None,
            "version": p["version"],
            "updated_by": p["updated_by"],
            "updated_at": datetime.fromisoformat(p["updated_at"]),
            **restored_quality(p),
        }
        for p in previous
    ]
    for start in range(0, len(rows), 2000):
        await session.execute(insert(LayerFeature), rows[start : start + 2000])
    layer.data_version += 1
    job.status, job.undone_at = "undone", datetime.now(UTC)
    job.undo = None


def restored_quality(p: dict[str, Any]) -> dict[str, Any]:
    """The phase L1a columns of a snapshot (older snapshots have none)."""
    deleted = p.get("deleted_at")
    return {
        "shape": f"SRID=4326;{p['shape']}" if p.get("shape") else None,
        "name_status": p.get("name_status") or "official",
        "suggested_name": p.get("suggested_name"),
        "name_confidence": p.get("name_confidence"),
        "name_source": p.get("name_source"),
        "source_url": p.get("source_url"),
        "snapshot_at": _date(p.get("snapshot_at")),
        "possible_duplicate": bool(p.get("possible_duplicate")),
        "deleted_at": datetime.fromisoformat(deleted) if deleted else None,
        "deleted_by": p.get("deleted_by"),
        "delete_reason": p.get("delete_reason"),
    }


# ---------------------------------------------------------------- reading places


def public_props(layer: Layer, props: dict[str, Any]) -> dict[str, Any]:
    """The place's columns the citizen's app may show: never a column the administrator kept from citizens."""
    return access.strip(props, access.visible_fields(None, layer))


def public_place() -> ColumnElement[bool]:
    """A place the citizen's app may show: on the map, not deleted, with an official or accepted name."""
    return (
        LayerFeature.hidden.is_(False) & LayerFeature.deleted_at.is_(None) & LayerFeature.name_status.in_(PUBLIC_NAMES)
    )


# (LayerFeature, lat, lon) rows; SQLAlchemy's Row typing does not follow geometry expressions.
FeatureRow = Any


async def features_in(
    session: AsyncSession,
    layer: Layer,
    *,
    bbox: tuple[float, float, float, float] | None = None,
    gouvernorat: int | None = None,
    include_hidden: bool = False,
    include_deleted: bool = False,
    public: bool = False,
    q: str | None = None,
    limit: int,
) -> Sequence[FeatureRow]:
    query = select(LayerFeature, LAT, LON).where(LayerFeature.layer_id == layer.id)
    if q:
        # "What, then where" (phase N, design §7): the places of the chosen layer whose name holds the words.
        for word in q.split()[:5]:
            pattern = "%" + word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            query = query.where(LayerFeature.name.ilike(pattern, escape="\\"))
    if public:
        query = query.where(public_place())
    elif not include_hidden:
        query = query.where(LayerFeature.hidden.is_(False))
    if not include_deleted:
        query = query.where(LayerFeature.deleted_at.is_(None))
    if bbox is not None:
        query = query.where(
            func.ST_Intersects(cast(LayerFeature.location, Geometry), func.ST_MakeEnvelope(*bbox, 4326))
        )
    if gouvernorat is not None:
        query = query.where(LayerFeature.gouvernorat_code == gouvernorat)
    return (await session.execute(query.order_by(LayerFeature.name, LayerFeature.id).limit(limit))).all()


async def nearest(
    session: AsyncSession, layer: Layer, lat: float, lon: float, limit: int, radius_m: int
) -> Sequence[Any]:
    here = func.ST_GeogFromText(point(lat, lon))
    distance = func.ST_Distance(LayerFeature.location, here)
    query = (
        select(LayerFeature, LAT, LON, distance)
        .where(
            LayerFeature.layer_id == layer.id,
            public_place(),
            func.ST_DWithin(LayerFeature.location, here, radius_m),
        )
        .order_by(distance, LayerFeature.id)
        .limit(limit)
    )
    return (await session.execute(query)).all()


async def shapes_in(
    session: AsyncSession, layer: Layer, bbox: tuple[float, float, float, float], zoom: int, limit: int
) -> Sequence[Any]:
    """(place, simplified GeoJSON) of the lines and areas crossing a map area; the tolerance follows the zoom so a
    whole gouvernorat's rivers stay light (about one screen pixel)."""
    tolerance = 360 / (256 * 2**zoom)
    envelope = func.ST_MakeEnvelope(*bbox, 4326)
    geometry = cast(LayerFeature.shape, Geometry)
    simplified = func.ST_AsGeoJSON(func.ST_SimplifyPreserveTopology(geometry, tolerance), 6)
    query = (
        select(LayerFeature, simplified)
        .where(
            LayerFeature.layer_id == layer.id,
            LayerFeature.shape.is_not(None),
            LayerFeature.deleted_at.is_(None),
            LayerFeature.hidden.is_(False),
            func.ST_Intersects(geometry, envelope),
        )
        .order_by(LayerFeature.id)
        .limit(limit)
    )
    return (await session.execute(query)).all()


def sync_columns(layer: Layer) -> None:
    """Keep the B1 columns in step: ``audience`` public when citizens see it, ``enabled`` when it is in use.

    A sensitive layer is never public, and its audiences do not matter (the minister alone sees it)."""
    if layer.sensitive:
        layer.audiences = [a for a in layer.audiences if a != "citizen"]
    layer.audience = "public" if "citizen" in layer.audiences and not layer.sensitive else "staff"
    layer.enabled = layer.status == "published" and layer.deleted_at is None
    layer.staff_only = sorted(k for k, allowed in (layer.fields or {}).items() if "citizen" not in allowed)


def live_layer() -> ColumnElement[bool]:
    """A layer in use: published (``enabled`` follows) and not deleted."""
    return Layer.enabled.is_(True) & Layer.deleted_at.is_(None) & or_(Layer.status == "published")


def preview_expired(job: LayerImport, now: datetime | None = None) -> bool:
    return ((now or datetime.now(UTC)) - job.created_at).total_seconds() > PREVIEW_TTL_S
