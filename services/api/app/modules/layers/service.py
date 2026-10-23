"""Map data layers (phase B1, docs/phase-b/design.md §2): preview, apply and undo an import; places for the maps.

* **Preview** parses the file (``domain.parse``), places each row in its gouvernorat (outside every boundary, beyond a
  coastal margin → rejected) and compares it with the layer: new, updated, unchanged and, in *replace* mode, removed.
  Nothing changes on the map; the checked rows wait in ``geo.layer_import.rows``.
* **Apply** writes the changes, keeps what they replaced in ``undo`` and bumps the layer's ``data_version``. It is
  refused when the layer changed after the preview (another import or a correction by hand): preview again.
* **Undo** restores what the last applied import replaced, only while nothing changed after it.
"""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import cast, delete, func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.geo.models import Delegation, Layer, LayerFeature, LayerImport
from app.modules.layers import domain

# Points just outside a simplified boundary (harbours, coastal hospitals) still belong to the nearest gouvernorat.
COAST_MARGIN_M = 5_000
# A preview not applied within a day is stale: the file is uploaded again.
PREVIEW_TTL_S = 24 * 3600
CHANGES = ("new", "updated", "unchanged", "removed")


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
    name: str, kind: str | None, phone: str | None, lat: float, lon: float, props: dict[str, Any]
) -> tuple[Any, ...]:
    return (name, kind, phone, round(lat, 6), round(lon, 6), sorted(props.items()))


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

    def comparable(self) -> tuple[Any, ...]:
        return _comparable(self.name, self.kind, self.phone, self.lat, self.lon, self.props)


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
        ).where(LayerFeature.layer_id == layer_id)
    )
    return {
        r.ref: Current(r.id, r.ref, r.name, r.kind, r.phone, float(r[5]), float(r[6]), r.props or {}, r.hidden)
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
            same = existing.comparable() == _comparable(row.name, row.kind, row.phone, row.lat, row.lon, row.props)
            same = same and (row.hidden is None or row.hidden == existing.hidden)
            change = "unchanged" if same else "updated"
            item["feature_id"] = str(existing.id)
        item["change"] = change
        counts[change] += 1
        rows.append(item)
    if mode == "replace":
        for ref, existing in current.items():
            if ref not in seen:
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


def _snapshot(f: LayerFeature, lat: float, lon: float) -> dict[str, Any]:
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
    }


async def _snapshots(session: AsyncSession, ids: Iterable[uuid.UUID]) -> list[dict[str, Any]]:
    wanted = list(ids)
    out: list[dict[str, Any]] = []
    for start in range(0, len(wanted), 5000):
        found = await session.execute(
            select(LayerFeature, LAT, LON).where(LayerFeature.id.in_(wanted[start : start + 5000]))
        )
        out += [_snapshot(f, float(lat), float(lon)) for f, lat, lon in found.all()]
    return out


def _values(item: dict[str, Any], layer_id: uuid.UUID, import_id: uuid.UUID, actor: str) -> dict[str, Any]:
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
        }
        for p in previous
    ]
    for start in range(0, len(rows), 2000):
        await session.execute(insert(LayerFeature), rows[start : start + 2000])
    layer.data_version += 1
    job.status, job.undone_at = "undone", datetime.now(UTC)
    job.undo = None


# ---------------------------------------------------------------- reading places


def public_props(layer: Layer, props: dict[str, Any]) -> dict[str, Any]:
    """The place's columns the app may show: never the staff-only ones (``manager`` by default)."""
    hidden = set(layer.staff_only)
    return {k: v for k, v in props.items() if k not in hidden}


# (LayerFeature, lat, lon) rows; SQLAlchemy's Row typing does not follow geometry expressions.
FeatureRow = Any


async def features_in(
    session: AsyncSession,
    layer: Layer,
    *,
    bbox: tuple[float, float, float, float] | None = None,
    gouvernorat: int | None = None,
    include_hidden: bool = False,
    limit: int,
) -> Sequence[FeatureRow]:
    query = select(LayerFeature, LAT, LON).where(LayerFeature.layer_id == layer.id)
    if not include_hidden:
        query = query.where(LayerFeature.hidden.is_(False))
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
            LayerFeature.hidden.is_(False),
            func.ST_DWithin(LayerFeature.location, here, radius_m),
        )
        .order_by(distance, LayerFeature.id)
        .limit(limit)
    )
    return (await session.execute(query)).all()


def preview_expired(job: LayerImport, now: datetime | None = None) -> bool:
    return ((now or datetime.now(UTC)) - job.created_at).total_seconds() > PREVIEW_TTL_S
