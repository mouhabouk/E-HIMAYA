"""Map data layers (phase B1, docs/phase-b/design.md §2.3, §2.7).

Staff (``/api/v1/staff/layers``): every staff member reads the layers and their places; the system administrator
(national scope) creates and changes layers; imports and corrections by hand are also open to content editors on the
layers the administrator opened to them. Every change carries a reason and is audited.

Public (``/api/v1/layers``, no sign-in: the app reads it on the first launch and offline packages are cached): the
enabled public layers, their places near a point or in a map area, and the offline copy of one gouvernorat with an
``ETag``. The columns marked staff-only (``manager`` by default) never leave the API here.
"""

import csv
import hashlib
import io
import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import as_system, get_session
from app.core.security import CurrentPrincipal, Principal, Role
from app.modules.audit import service as audit
from app.modules.decision import routing
from app.modules.geo.models import Layer, LayerFeature, LayerImport, LayerRevision
from app.modules.layers import access, domain, geoformats, schemas, service
from app.modules.ops.models import Unit

router = APIRouter(prefix="/api/v1/staff/layers", tags=["staff", "layers"])
public_router = APIRouter(prefix="/api/v1/layers", tags=["layers"])
Session = Annotated[AsyncSession, Depends(get_session)]
Lang = Literal["ar", "fr", "en"]

UNITS_KEY = "civil_protection"
UNITS_NAME = {"ar": "مراكز الحماية المدنية", "fr": "Centres de la Protection civile", "en": "Civil Protection centres"}
UNITS_SOURCE = {"ar": "الديوان الوطني للحماية المدنية", "fr": "ONPC", "en": "ONPC"}
MAX_STAFF_FEATURES = 5000
MAX_PUBLIC_BBOX = 2000
MAX_PACKAGE = 20_000
MAX_PREVIEW_POINTS = 2000
PUBLIC_CACHE = "public, max-age=300"


async def _staff(principal: CurrentPrincipal) -> Principal:
    if not principal.is_staff or not principal.roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient_role")
    return principal


Staff = Annotated[Principal, Depends(_staff)]


def can_manage(principal: Principal) -> bool:
    return access.manages(principal)


def can_import(principal: Principal, layer: Layer) -> bool:
    if not principal.is_national or layer.deleted_at is not None:
        return False
    if access.manages(principal):
        return True
    return Role.CONTENT_EDITOR in principal.roles and layer.editors_allowed and not layer.sensitive


def _require(allowed: bool, principal: Principal) -> None:
    if not allowed:
        code = "national_scope_required" if not principal.is_national else "insufficient_role"
        raise HTTPException(status.HTTP_403_FORBIDDEN, code)


async def _layer(session: AsyncSession, key: str, *, lock: bool = False) -> Layer:
    query = select(Layer).where(Layer.key == key)
    layer = await session.scalar(query.with_for_update() if lock else query)
    if layer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return layer


async def _seen_layer(session: AsyncSession, key: str, principal: Principal, *, lock: bool = False) -> Layer:
    """A layer the principal sees or works on; any other answers 404, as if it did not exist."""
    layer = await _layer(session, key, lock=lock)
    if not (access.sees(principal, layer) or can_import(principal, layer)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return layer


def _check_reason(reason: str) -> str:
    reason = reason.strip()
    if len(reason) < 5:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reason_required")
    return reason


# ---------------------------------------------------------------- layers

# The settings a revision keeps (phase L1a, design §3.5); going back to one restores them.
REVISED = (
    "name",
    "icon",
    "colour",
    "source",
    "licence",
    "to_verify",
    "simulated",
    "editors_allowed",
    "status",
    "audiences",
    "scope",
    "default_on",
    "sensitive",
    "fields",
    "actions",
)


def _settings(layer: Layer) -> dict[str, Any]:
    return {k: getattr(layer, k) for k in REVISED}


async def _revise(session: AsyncSession, layer: Layer, principal: Principal, action: str, reason: str | None) -> None:
    number = (
        await session.scalar(select(func.max(LayerRevision.number)).where(LayerRevision.layer_id == layer.id))
    ) or 0
    session.add(
        LayerRevision(
            layer_id=layer.id,
            number=number + 1,
            action=action,
            snapshot=_settings(layer),
            reason=reason,
            created_by=audit.actor_of(principal),
            created_by_name=audit.name_of(principal),
        )
    )


_sync = service.sync_columns


async def _layer_out(session: AsyncSession, layer: Layer, principal: Principal) -> schemas.LayerOut:
    live = LayerFeature.deleted_at.is_(None)
    total, hidden, suggested, duplicates, deleted, lines, areas = (
        await session.execute(
            select(
                func.count().filter(live),
                func.count().filter(live & LayerFeature.hidden),
                func.count().filter(live & (LayerFeature.name_status == "suggested")),
                func.count().filter(live & LayerFeature.possible_duplicate),
                func.count().filter(LayerFeature.deleted_at.is_not(None)),
                func.count().filter(live & func.GeometryType(cast(LayerFeature.shape, Geometry)).ilike("%LINE%")),
                func.count().filter(live & func.GeometryType(cast(LayerFeature.shape, Geometry)).ilike("%POLYGON%")),
            ).where(LayerFeature.layer_id == layer.id)
        )
    ).one()
    points = total - lines - areas
    kinds = [k for k, n in (("point", points), ("line", lines), ("area", areas)) if n]
    last = await session.scalar(
        select(LayerImport)
        .where(LayerImport.layer_id == layer.id, LayerImport.status.in_(("applied", "undone")))
        .order_by(LayerImport.applied_at.desc())
        .limit(1)
    )
    return schemas.LayerOut(
        id=layer.id,
        key=layer.key,
        name=schemas.Names.model_validate(layer.name),
        icon=layer.icon,
        colour=layer.colour,
        audience=layer.audience,
        source=layer.source,
        licence=layer.licence,
        to_verify=layer.to_verify,
        simulated=layer.simulated,
        staff_only=list(layer.staff_only),
        editors_allowed=layer.editors_allowed,
        enabled=layer.enabled,
        version=layer.version,
        data_version=layer.data_version,
        feature_count=total,
        hidden_count=hidden,
        updated_by_name=layer.updated_by_name,
        updated_at=layer.updated_at,
        last_import=(
            schemas.LastImport(
                id=last.id, status=last.status, at=last.undone_at or last.applied_at, by=last.created_by_name
            )
            if last and (last.undone_at or last.applied_at)
            else None
        ),
        can_manage=can_manage(principal),
        can_import=can_import(principal, layer),
        status=layer.status,
        audiences=list(layer.audiences),
        scope=list(layer.scope),
        default_on=layer.default_on,
        sensitive=layer.sensitive,
        fields=dict(layer.fields or {}),
        actions=schemas.Actions.model_validate(layer.actions or {}),
        geometry=kinds[0] if len(kinds) == 1 else "mixed" if kinds else "point",
        quality={"suggested": suggested, "duplicates": duplicates, "deleted": deleted},
        deleted_at=layer.deleted_at,
        delete_reason=layer.delete_reason,
        purge_at=(
            layer.deleted_at + timedelta(days=get_settings().retention_layer_deleted_days) if layer.deleted_at else None
        ),
    )


@router.get("", response_model=schemas.LayersOut)
async def list_layers(principal: Staff, session: Session) -> schemas.LayersOut:
    layers = (await session.scalars(select(Layer).order_by(Layer.created_at, Layer.key))).all()
    mine = [layer for layer in layers if access.sees(principal, layer) or can_import(principal, layer)]
    return schemas.LayersOut(
        items=[await _layer_out(session, layer, principal) for layer in mine if layer.deleted_at is None],
        deleted=[await _layer_out(session, layer, principal) for layer in mine if layer.deleted_at is not None],
        can_manage=can_manage(principal),
        icons=list(domain.ICONS),
        palette=list(domain.PALETTE),
        limits={"file_bytes": domain.MAX_FILE_BYTES, "rows": domain.MAX_ROWS},
    )


@router.get("/template")
async def template(
    principal: Staff,
    format: Annotated[Literal["csv", "xlsx"], Query()] = "csv",
    lang: Annotated[Lang, Query()] = "fr",
) -> Response:
    """Empty file with the standard columns in the chosen language (the extra columns are free)."""
    columns = [c for c in domain.STANDARD if c != "hidden"]
    headings = [domain.HEADINGS[lang][c] for c in columns]
    return _table_response([headings], format, f"layer-template-{lang}")


@router.post("", response_model=schemas.LayerOut, status_code=status.HTTP_201_CREATED)
async def create_layer(principal: Staff, session: Session, body: schemas.LayerIn) -> schemas.LayerOut:
    _require(can_manage(principal), principal)
    if body.key == UNITS_KEY or await session.scalar(select(Layer.id).where(Layer.key == body.key)):
        raise HTTPException(status.HTTP_409_CONFLICT, "key_taken")
    actor = audit.actor_of(principal)
    audiences = body.audiences
    if audiences is None:
        audiences = list(access.AUDIENCES if body.audience == "public" else access.STAFF_AUDIENCES)
    fields = body.fields
    if fields is None:
        fields = {column: list(access.STAFF_AUDIENCES) for column in body.staff_only}
    layer = Layer(
        key=body.key,
        name=body.name.model_dump(),
        icon=body.icon,
        colour=body.colour,
        audience=body.audience,
        source=body.source.strip(),
        licence=body.licence.strip(),
        to_verify=body.to_verify,
        simulated=body.simulated,
        staff_only=body.staff_only,
        editors_allowed=body.editors_allowed,
        created_by=actor,
        updated_by=actor,
        updated_by_name=audit.name_of(principal),
        status=body.status,
        audiences=sorted(set(audiences)),
        scope=body.scope,
        default_on=body.default_on,
        sensitive=body.sensitive,
        fields=fields,
        actions=body.actions.model_dump(),
    )
    _sync(layer)
    session.add(layer)
    await session.flush()
    reason = _check_reason(body.reason)
    await audit.record(session, actor=actor, action="layer.create", target=f"layer:{layer.key}", reason=reason)
    await _revise(session, layer, principal, "create", reason)
    await session.refresh(layer)
    out = await _layer_out(session, layer, principal)
    await session.commit()
    return out


# What the app or the maps show changes with these: the offline packages are built again.
PACKAGED = {"audience", "staff_only", "enabled", "simulated", "status", "audiences", "scope", "sensitive", "fields"}


@router.patch("/{key}", response_model=schemas.LayerOut)
async def update_layer(principal: Staff, session: Session, key: str, body: schemas.LayerPatch) -> schemas.LayerOut:
    _require(can_manage(principal), principal)
    layer = await _layer(session, key, lock=True)
    if layer.deleted_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "layer_deleted")
    if body.version != layer.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
    changes = body.model_dump(exclude_unset=True, exclude={"version", "reason"})
    if "name" in changes and body.name is not None:
        changes["name"] = body.name.model_dump()
    if "actions" in changes and body.actions is not None:
        changes["actions"] = body.actions.model_dump()
    # The B1 switches still work: "enabled" publishes or pauses, "audience" and "staff_only" set the new columns.
    if "enabled" in changes and "status" not in changes:
        changes["status"] = "published" if changes["enabled"] else "paused"
    if "audience" in changes and "audiences" not in changes:
        others = [a for a in layer.audiences if a != "citizen"] or list(access.STAFF_AUDIENCES)
        changes["audiences"] = ["citizen", *others] if changes["audience"] == "public" else others
    if "staff_only" in changes and "fields" not in changes:
        changes["fields"] = {
            **{k: v for k, v in (layer.fields or {}).items() if "citizen" in v},
            **{column: list(access.STAFF_AUDIENCES) for column in changes["staff_only"] or []},
        }
    changes.pop("enabled", None)
    changes.pop("audience", None)
    changes.pop("staff_only", None)
    if "audiences" in changes:
        changes["audiences"] = sorted(set(changes["audiences"] or []))
    for field, value in changes.items():
        setattr(layer, field, value.strip() if isinstance(value, str) and field in ("source", "licence") else value)
    _sync(layer)
    layer.version += 1
    if changes.keys() & PACKAGED or body.model_fields_set & PACKAGED:
        layer.data_version += 1
    layer.updated_by, layer.updated_by_name = audit.actor_of(principal), audit.name_of(principal)
    layer.updated_at = datetime.now(UTC)
    reason = _check_reason(body.reason)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="layer.update",
        target=f"layer:{layer.key}",
        reason=reason,
        details={"fields": sorted(body.model_fields_set - {"version", "reason"})},
    )
    await _revise(session, layer, principal, "update", reason)
    await session.flush()
    await session.refresh(layer)
    out = await _layer_out(session, layer, principal)
    await session.commit()
    return out


@router.delete("/{key}", response_model=schemas.LayerOut)
async def delete_layer(principal: Staff, session: Session, key: str, body: schemas.ReasonIn) -> schemas.LayerOut:
    """Off every map and offline package at once; kept 30 days in "deleted", where it can be restored as it was."""
    _require(can_manage(principal), principal)
    layer = await _layer(session, key, lock=True)
    if layer.deleted_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "layer_deleted")
    reason = _check_reason(body.reason)
    layer.deleted_at, layer.deleted_by, layer.delete_reason = datetime.now(UTC), audit.actor_of(principal), reason
    _sync(layer)
    layer.version += 1
    layer.data_version += 1
    await audit.record(
        session, actor=audit.actor_of(principal), action="layer.delete", target=f"layer:{layer.key}", reason=reason
    )
    await _revise(session, layer, principal, "delete", reason)
    await session.flush()
    await session.refresh(layer)
    out = await _layer_out(session, layer, principal)
    await session.commit()
    return out


@router.post("/{key}/restore", response_model=schemas.LayerOut)
async def restore_layer(principal: Staff, session: Session, key: str, body: schemas.ReasonIn) -> schemas.LayerOut:
    """A deleted layer comes back as it was, paused: the administrator publishes it again by choice."""
    _require(can_manage(principal), principal)
    layer = await _layer(session, key, lock=True)
    if layer.deleted_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_deleted")
    reason = _check_reason(body.reason)
    layer.deleted_at = layer.deleted_by = layer.delete_reason = None
    if layer.status == "published":
        layer.status = "paused"
    _sync(layer)
    layer.version += 1
    layer.data_version += 1
    await audit.record(
        session, actor=audit.actor_of(principal), action="layer.restore", target=f"layer:{layer.key}", reason=reason
    )
    await _revise(session, layer, principal, "restore", reason)
    await session.flush()
    await session.refresh(layer)
    out = await _layer_out(session, layer, principal)
    await session.commit()
    return out


@router.delete("/{key}/purge", status_code=status.HTTP_204_NO_CONTENT)
async def purge_layer(principal: Staff, session: Session, key: str, body: schemas.ReasonIn) -> Response:
    """Erase a deleted layer now, with its places, imports and revisions (otherwise done after 30 days)."""
    _require(can_manage(principal), principal)
    layer = await _layer(session, key, lock=True)
    if layer.deleted_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_deleted")
    reason = _check_reason(body.reason)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="layer.purge",
        target=f"layer:{layer.key}",
        reason=reason,
        details={"name": layer.name.get("fr", layer.key)},
    )
    await session.delete(layer)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{key}/revisions", response_model=schemas.RevisionsOut)
async def list_revisions(principal: Staff, session: Session, key: str) -> schemas.RevisionsOut:
    _require(can_manage(principal), principal)
    layer = await _layer(session, key)
    revisions = (
        await session.scalars(
            select(LayerRevision).where(LayerRevision.layer_id == layer.id).order_by(LayerRevision.number.desc())
        )
    ).all()
    items: list[schemas.Revision] = []
    for i, revision in enumerate(revisions):
        before = revisions[i + 1].snapshot if i + 1 < len(revisions) else {}
        changed = sorted(k for k in REVISED if revision.snapshot.get(k) != before.get(k)) if before else []
        items.append(
            schemas.Revision(
                number=revision.number,
                action=revision.action,
                reason=revision.reason,
                created_by_name=revision.created_by_name,
                created_at=revision.created_at,
                changes=changed,
            )
        )
    return schemas.RevisionsOut(items=items[:100])


@router.post("/{key}/revisions/{number}/restore", response_model=schemas.LayerOut)
async def restore_revision(
    principal: Staff, session: Session, key: str, number: int, body: schemas.ReasonIn
) -> schemas.LayerOut:
    """Back to the settings of a revision (the places themselves come back by undoing imports)."""
    _require(can_manage(principal), principal)
    layer = await _layer(session, key, lock=True)
    if layer.deleted_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "layer_deleted")
    revision = await session.scalar(
        select(LayerRevision).where(LayerRevision.layer_id == layer.id, LayerRevision.number == number)
    )
    if revision is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    for field in REVISED:
        if field in revision.snapshot:
            setattr(layer, field, revision.snapshot[field])
    _sync(layer)
    layer.version += 1
    layer.data_version += 1
    layer.updated_by, layer.updated_by_name = audit.actor_of(principal), audit.name_of(principal)
    layer.updated_at = datetime.now(UTC)
    reason = _check_reason(body.reason)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="layer.revision_restore",
        target=f"layer:{layer.key}",
        reason=reason,
        details={"revision": number},
    )
    await _revise(session, layer, principal, f"restore:{number}", reason)
    await session.flush()
    await session.refresh(layer)
    out = await _layer_out(session, layer, principal)
    await session.commit()
    return out


# ---------------------------------------------------------------- imports


def _import_out(
    job: LayerImport, layer: Layer, principal: Principal, latest_applied: uuid.UUID | None
) -> dict[str, Any]:
    expired = job.status == "preview" and service.preview_expired(job)
    allowed = can_import(principal, layer)
    return dict(
        id=job.id,
        file_name=job.file_name,
        format=job.format,
        mode=job.mode,
        status=job.status,
        counts=job.counts,
        rejected=job.rejected,
        warnings=job.warnings,
        reason=job.reason,
        created_by_name=job.created_by_name,
        created_at=job.created_at,
        applied_at=job.applied_at,
        undone_at=job.undone_at,
        expired=expired,
        can_apply=allowed and job.status == "preview" and not expired and job.base_version == layer.data_version,
        can_undo=allowed
        and job.status == "applied"
        and job.id == latest_applied
        and job.result_version == layer.data_version,
    )


async def _latest_applied(session: AsyncSession, layer: Layer) -> uuid.UUID | None:
    return await session.scalar(
        select(LayerImport.id)
        .where(LayerImport.layer_id == layer.id, LayerImport.status == "applied")
        .order_by(LayerImport.applied_at.desc())
        .limit(1)
    )


def _points(rows: Sequence[dict[str, Any]]) -> list[schemas.PreviewPoint]:
    order = {"removed": 0, "new": 1, "updated": 2, "unchanged": 3}
    ranked = sorted(rows, key=lambda r: order[r["change"]])[:MAX_PREVIEW_POINTS]
    return [
        schemas.PreviewPoint(ref=r["ref"], name=r["name"], lat=r["lat"], lon=r["lon"], change=r["change"])
        for r in ranked
    ]


async def _read_body(request: Request) -> bytes:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > domain.MAX_FILE_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "file_too_large")
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > domain.MAX_FILE_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "file_too_large")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/{key}/imports", response_model=schemas.ImportDetail, status_code=status.HTTP_201_CREATED)
async def preview_import(
    principal: Staff,
    session: Session,
    request: Request,
    key: str,
    file_name: Annotated[str, Query(min_length=1, max_length=200)],
    mode: Annotated[schemas.Mode, Query()] = "merge",
) -> schemas.ImportDetail:
    """The file is the request body (any content type). Nothing changes on the map until it is applied."""
    layer = await _layer(session, key)
    _require(can_import(principal, layer), principal)
    data = await _read_body(request)
    try:
        parsed = domain.parse(file_name, data)
    except domain.FileError as e:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE if e.code == "file_too_large" else status.HTTP_422_UNPROCESSABLE_CONTENT,
            e.code,
        ) from None
    preview = await service.build_preview(session, layer, parsed, mode)
    job = LayerImport(
        layer_id=layer.id,
        file_name=file_name.replace("/", "_").replace("\\", "_")[-200:],
        sha256=hashlib.sha256(data).hexdigest(),
        format=parsed.format,
        mode=mode,
        status="preview",
        counts=preview.counts,
        rejected=preview.rejected,
        warnings=preview.warnings,
        rows=preview.rows,
        base_version=layer.data_version,
        created_by=audit.actor_of(principal),
        created_by_name=audit.name_of(principal),
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)
    out = schemas.ImportDetail(**_import_out(job, layer, principal, None), points=_points(preview.rows))
    await session.commit()
    return out


@router.get("/{key}/imports", response_model=schemas.ImportsOut)
async def list_imports(principal: Staff, session: Session, key: str) -> schemas.ImportsOut:
    layer = await _layer(session, key)
    _require(can_import(principal, layer) or can_manage(principal), principal)
    latest = await _latest_applied(session, layer)
    jobs = await session.scalars(
        select(LayerImport).where(LayerImport.layer_id == layer.id).order_by(LayerImport.created_at.desc()).limit(50)
    )
    return schemas.ImportsOut(items=[schemas.ImportOut(**_import_out(j, layer, principal, latest)) for j in jobs])


async def _job(session: AsyncSession, layer: Layer, import_id: uuid.UUID, *, lock: bool = False) -> LayerImport:
    query = select(LayerImport).where(LayerImport.id == import_id, LayerImport.layer_id == layer.id)
    job = await session.scalar(query.with_for_update() if lock else query)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return job


@router.get("/{key}/imports/{import_id}", response_model=schemas.ImportDetail)
async def get_import(principal: Staff, session: Session, key: str, import_id: uuid.UUID) -> schemas.ImportDetail:
    layer = await _layer(session, key)
    _require(can_import(principal, layer) or can_manage(principal), principal)
    job = await _job(session, layer, import_id)
    latest = await _latest_applied(session, layer)
    return schemas.ImportDetail(**_import_out(job, layer, principal, latest), points=_points(job.rows or []))


@router.post("/{key}/imports/{import_id}/apply", response_model=schemas.ImportOut)
async def apply_import(
    principal: Staff, session: Session, key: str, import_id: uuid.UUID, body: schemas.ReasonIn
) -> schemas.ImportOut:
    layer = await _layer(session, key, lock=True)
    _require(can_import(principal, layer), principal)
    job = await _job(session, layer, import_id, lock=True)
    if job.status != "preview":
        raise HTTPException(status.HTTP_409_CONFLICT, "not_a_preview")
    if service.preview_expired(job):
        raise HTTPException(status.HTTP_409_CONFLICT, "preview_expired")
    if job.base_version != layer.data_version:
        raise HTTPException(status.HTTP_409_CONFLICT, "layer_changed")
    actor = audit.actor_of(principal)
    await service.apply(session, layer, job, actor)
    job.reason = _check_reason(body.reason)
    await audit.record(
        session,
        actor=actor,
        action="layer.import_apply",
        target=f"layer:{layer.key}",
        reason=job.reason,
        details={"import": str(job.id), "file": job.file_name, "sha256": job.sha256, "mode": job.mode, **job.counts},
    )
    await session.flush()
    await session.refresh(job)
    out = schemas.ImportOut(**_import_out(job, layer, principal, job.id))
    await session.commit()
    return out


@router.post("/{key}/imports/{import_id}/discard", response_model=schemas.ImportOut)
async def discard_import(principal: Staff, session: Session, key: str, import_id: uuid.UUID) -> schemas.ImportOut:
    layer = await _layer(session, key)
    _require(can_import(principal, layer), principal)
    job = await _job(session, layer, import_id, lock=True)
    if job.status != "preview":
        raise HTTPException(status.HTTP_409_CONFLICT, "not_a_preview")
    job.status, job.rows = "discarded", None
    await session.flush()
    await session.refresh(job)
    out = schemas.ImportOut(**_import_out(job, layer, principal, None))
    await session.commit()
    return out


@router.post("/{key}/imports/{import_id}/undo", response_model=schemas.ImportOut)
async def undo_import(
    principal: Staff, session: Session, key: str, import_id: uuid.UUID, body: schemas.ReasonIn
) -> schemas.ImportOut:
    layer = await _layer(session, key, lock=True)
    _require(can_import(principal, layer), principal)
    job = await _job(session, layer, import_id, lock=True)
    if job.status != "applied" or job.id != await _latest_applied(session, layer):
        raise HTTPException(status.HTTP_409_CONFLICT, "not_last_import")
    if job.result_version != layer.data_version:
        raise HTTPException(status.HTTP_409_CONFLICT, "layer_changed")
    await service.undo(session, layer, job)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="layer.import_undo",
        target=f"layer:{layer.key}",
        reason=_check_reason(body.reason),
        details={"import": str(job.id), "file": job.file_name},
    )
    await session.flush()
    await session.refresh(job)
    out = schemas.ImportOut(**_import_out(job, layer, principal, None))
    await session.commit()
    return out


# ---------------------------------------------------------------- export


def _export_rows(layer: Layer, found: Sequence[service.FeatureRow], lang: Lang) -> tuple[list[str], list[list[Any]]]:
    extras: list[str] = []
    for f, _, _ in found:
        for k in f.props:
            if k not in domain.PROPS_KEYS and k not in extras:
                extras.append(k)
    columns = [*domain.STANDARD, "gouvernorat"]
    headings = [domain.HEADINGS[lang][c] for c in columns] + extras
    rows: list[list[Any]] = []
    for f, lat, lon in found:
        standard = {
            "id": f.ref,
            "name": f.name,
            "type": f.kind or "",
            "lat": float(lat),
            "lon": float(lon),
            "phone": f.phone or "",
            "hidden": "1" if f.hidden else "",
            "gouvernorat": f.gouvernorat_code or "",
            **{k: f.props.get(k, "") for k in domain.PROPS_KEYS},
        }
        rows.append([standard[c] for c in columns] + [f.props.get(k, "") for k in extras])
    return headings, rows


def _cell(value: Any, *, numeric_text: bool) -> Any:
    if isinstance(value, str) and not numeric_text:
        return domain.neutralize(value)
    return value


def _table_response(table: list[list[Any]], fmt: str, stem: str, phone_columns: Sequence[int] = ()) -> Response:
    """CSV (UTF-8 with BOM, read correctly by Excel) or XLSX; text cells neutralised against formula injection."""
    safe = set(phone_columns)
    cleaned = [[_cell(v, numeric_text=i in safe) for i, v in enumerate(row)] for row in table]
    if fmt == "xlsx":
        from openpyxl import Workbook

        book = Workbook(write_only=True)
        sheet = book.create_sheet()
        for row in cleaned:
            sheet.append(row)
        buffer = io.BytesIO()
        book.save(buffer)
        content, media = buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        text_buffer = io.StringIO()
        csv.writer(text_buffer).writerows(cleaned)
        content, media = ("﻿" + text_buffer.getvalue()).encode(), "text/csv; charset=utf-8"
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{stem}.{fmt}"'})


@router.get("/{key}/export")
async def export_layer(
    principal: Staff,
    session: Session,
    key: str,
    format: Annotated[Literal["csv", "xlsx", "geojson"], Query()] = "csv",
    lang: Annotated[Lang, Query()] = "fr",
) -> Response:
    """The whole layer with every column (staff-only ones included): edit it and import it again."""
    layer = await _layer(session, key)
    _require(can_import(principal, layer) or can_manage(principal), principal)
    found = await service.features_in(session, layer, include_hidden=True, limit=domain.MAX_ROWS)
    shapes: dict[uuid.UUID, str] = dict(
        (
            await session.execute(
                select(LayerFeature.id, func.ST_AsGeoJSON(cast(LayerFeature.shape, Geometry), 7)).where(
                    LayerFeature.layer_id == layer.id, LayerFeature.shape.is_not(None)
                )
            )
        ).all()
    )
    stem = f"{layer.key}-v{layer.data_version}"
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="layer.export",
        target=f"layer:{layer.key}",
        details={"format": format, "count": len(found)},
    )
    await session.commit()
    if format == "geojson":
        doc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": f.ref,
                    "geometry": (
                        json.loads(shapes[f.id])
                        if f.id in shapes
                        else {"type": "Point", "coordinates": [float(lon), float(lat)]}
                    ),
                    "properties": {
                        "id": f.ref,
                        "name": f.name,
                        **({"name_suggested": f.suggested_name} if f.name_status == "suggested" else {}),
                        **({"osm_url": f.source_url} if f.source_url else {}),
                        **({"type": f.kind} if f.kind else {}),
                        **({"phone": f.phone} if f.phone else {}),
                        **({"hidden": True} if f.hidden else {}),
                        **f.props,
                    },
                }
                for f, lat, lon in found
            ],
        }
        return Response(
            json.dumps(doc, ensure_ascii=False).encode(),
            media_type="application/geo+json",
            headers={"Content-Disposition": f'attachment; filename="{stem}.geojson"'},
        )
    headings, rows = _export_rows(layer, found, lang)
    phone_columns = [domain.STANDARD.index("phone"), domain.STANDARD.index("phone2")]
    return _table_response([headings, *rows], format, stem, phone_columns)


# ---------------------------------------------------------------- places (staff)


def _feature_out(f: LayerFeature, lat: float, lon: float, hidden_fields: set[str] | None = None) -> schemas.FeatureOut:
    shape_kind = geoformats.wkb_kind(f.shape) or "point" if f.shape is not None else "point"
    return schemas.FeatureOut(
        id=f.id,
        ref=f.ref,
        name=f.name,
        kind=f.kind,
        phone=None if hidden_fields and "phone" in hidden_fields else f.phone,
        lat=float(lat),
        lon=float(lon),
        gouvernorat_code=f.gouvernorat_code,
        delegation_id=f.delegation_id,
        props=access.strip(f.props, hidden_fields),
        hidden=f.hidden,
        version=f.version,
        updated_at=f.updated_at,
        geometry=shape_kind,
        name_status=f.name_status,
        suggested_name=f.suggested_name,
        name_confidence=f.name_confidence,
        name_source=f.name_source,
        source_url=f.source_url,
        snapshot_at=f.snapshot_at.isoformat() if f.snapshot_at else None,
        possible_duplicate=f.possible_duplicate,
        deleted_at=f.deleted_at,
        delete_reason=f.delete_reason,
    )


async def _sensitive_read(session: AsyncSession, principal: Principal, layer: Layer, what: str, count: int) -> None:
    """Every read of a sensitive layer's places is in the audit log (design §3.3)."""
    if layer.sensitive:
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action="layer.sensitive_read",
            target=f"layer:{layer.key}",
            details={"what": what, "count": count},
        )


def _bbox(raw: str | None) -> tuple[float, float, float, float] | None:
    if raw is None:
        return None
    try:
        parts = tuple(float(p) for p in raw.split(","))
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_bbox") from None
    if len(parts) != 4 or not (parts[0] < parts[2] and parts[1] < parts[3]):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_bbox")
    return parts


@router.get("/{key}/features", response_model=schemas.FeaturesOut)
async def staff_features(
    principal: Staff,
    session: Session,
    key: str,
    bbox: Annotated[str | None, Query(description="minLon,minLat,maxLon,maxLat")] = None,
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
    deleted: Annotated[bool, Query(description="the deleted places (managers)")] = False,
) -> schemas.FeaturesOut:
    layer = await _seen_layer(session, key, principal)
    if deleted:
        _require(can_import(principal, layer) or can_manage(principal), principal)
    found = await service.features_in(
        session,
        layer,
        bbox=_bbox(bbox),
        gouvernorat=gouvernorat,
        include_hidden=True,
        include_deleted=deleted,
        limit=MAX_STAFF_FEATURES + 1,
    )
    if deleted:
        found = [row for row in found if row[0].deleted_at is not None]
    hidden_fields = access.visible_fields(principal, layer)
    await _sensitive_read(session, principal, layer, "features", len(found))
    await session.commit()
    return schemas.FeaturesOut(
        items=[_feature_out(f, lat, lon, hidden_fields) for f, lat, lon in found[:MAX_STAFF_FEATURES]],
        truncated=len(found) > MAX_STAFF_FEATURES,
    )


@router.get("/{key}/shapes", response_model=schemas.Shapes)
async def staff_shapes(
    principal: Staff,
    session: Session,
    key: str,
    bbox: Annotated[str, Query(description="minLon,minLat,maxLon,maxLat")],
    zoom: Annotated[int, Query(ge=0, le=22)] = 10,
    lang: Annotated[Lang, Query()] = "ar",
) -> schemas.Shapes:
    """The lines and areas of a layer in a map area, simplified for the zoom (rivers, forests, beaches)."""
    layer = await _seen_layer(session, key, principal)
    area = _bbox(bbox)
    assert area is not None
    found = await service.shapes_in(session, layer, area, zoom, MAX_STAFF_FEATURES + 1)
    await _sensitive_read(session, principal, layer, "shapes", len(found))
    await session.commit()
    return schemas.Shapes(
        features=[
            {
                "type": "Feature",
                "id": str(f.id),
                "geometry": json.loads(geometry),
                "properties": {
                    "id": str(f.id),
                    "name": f.props.get(f"name_{lang}") or f.name,
                    "name_status": f.name_status,
                    "kind": f.kind,
                },
            }
            for f, geometry in found[:MAX_STAFF_FEATURES]
            if geometry
        ],
        truncated=len(found) > MAX_STAFF_FEATURES,
    )


async def _relocate(session: AsyncSession, lat: float, lon: float) -> int:
    probe = domain.Row(0, "", "", lat, lon)
    code = (await service.locate(session, [probe]))[0]
    if code is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "outside_tunisia")
    return code


@router.post("/{key}/features", response_model=schemas.FeatureOut, status_code=status.HTTP_201_CREATED)
async def create_feature(principal: Staff, session: Session, key: str, body: schemas.FeatureIn) -> schemas.FeatureOut:
    layer = await _layer(session, key, lock=True)
    _require(can_import(principal, layer), principal)
    ref = body.ref or domain.auto_ref(body.name, body.lat, body.lon)
    if await session.scalar(select(LayerFeature.id).where(LayerFeature.layer_id == layer.id, LayerFeature.ref == ref)):
        raise HTTPException(status.HTTP_409_CONFLICT, "duplicate_id")
    actor = audit.actor_of(principal)
    feature = LayerFeature(
        layer_id=layer.id,
        ref=ref,
        name=body.name.strip(),
        kind=body.kind or None,
        phone=body.phone,
        location=service.point(body.lat, body.lon),
        gouvernorat_code=await _relocate(session, body.lat, body.lon),
        props=body.props,
        updated_by=actor,
    )
    session.add(feature)
    layer.data_version += 1
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action="layer.feature_create",
        target=f"layer:{layer.key}",
        reason=_check_reason(body.reason),
        details={"feature": str(feature.id), "ref": ref},
    )
    found = (
        await session.execute(select(LayerFeature, service.LAT, service.LON).where(LayerFeature.id == feature.id))
    ).one()
    out = _feature_out(*found)
    await session.commit()
    return out


@router.patch("/{key}/features/{feature_id}", response_model=schemas.FeatureOut)
async def update_feature(
    principal: Staff, session: Session, key: str, feature_id: uuid.UUID, body: schemas.FeaturePatch
) -> schemas.FeatureOut:
    layer = await _layer(session, key, lock=True)
    _require(can_import(principal, layer), principal)
    found = (
        await session.execute(
            select(LayerFeature, service.LAT, service.LON)
            .where(LayerFeature.id == feature_id, LayerFeature.layer_id == layer.id)
            .with_for_update(of=LayerFeature)
        )
    ).one_or_none()
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    feature, lat, lon = found
    if body.version != feature.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
    changes = body.model_dump(exclude_unset=True, exclude={"version", "reason"})
    if "lat" in changes or "lon" in changes:
        lat, lon = changes.pop("lat", lat) or lat, changes.pop("lon", lon) or lon
        feature.location = service.point(lat, lon)
        feature.gouvernorat_code = await _relocate(session, lat, lon)
    for field, value in changes.items():
        if field == "name" and value is not None:
            value = value.strip()
            # A name typed by the administrator is theirs: no longer a suggestion.
            if feature.name_status in ("suggested", "rejected"):
                feature.name_status = "accepted"
        if field == "hidden" and value is None:
            continue
        setattr(feature, field, value)
    feature.version += 1
    feature.updated_by, feature.updated_at = audit.actor_of(principal), datetime.now(UTC)
    layer.data_version += 1
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="layer.feature_update",
        target=f"layer:{layer.key}",
        reason=_check_reason(body.reason),
        details={"feature": str(feature.id), "fields": sorted(body.model_fields_set - {"version", "reason"})},
    )
    await session.flush()
    found = (
        await session.execute(select(LayerFeature, service.LAT, service.LON).where(LayerFeature.id == feature.id))
    ).one()
    out = _feature_out(*found)
    await session.commit()
    return out


async def _feature(session: AsyncSession, layer: Layer, feature_id: uuid.UUID) -> LayerFeature:
    feature = await session.scalar(
        select(LayerFeature).where(LayerFeature.id == feature_id, LayerFeature.layer_id == layer.id).with_for_update()
    )
    if feature is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return feature


@router.delete("/{key}/features/{feature_id}", response_model=schemas.FeatureOut)
async def delete_feature(
    principal: Staff, session: Session, key: str, feature_id: uuid.UUID, body: schemas.ReasonIn
) -> schemas.FeatureOut:
    """Off the maps at once; the place stays in the layer's "deleted" list, where it can be restored."""
    layer = await _layer(session, key, lock=True)
    _require(can_import(principal, layer), principal)
    feature = await _feature(session, layer, feature_id)
    if feature.deleted_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_deleted")
    reason = _check_reason(body.reason)
    actor = audit.actor_of(principal)
    feature.deleted_at, feature.deleted_by, feature.delete_reason = datetime.now(UTC), actor, reason
    feature.version += 1
    layer.data_version += 1
    await audit.record(
        session,
        actor=actor,
        action="layer.feature_delete",
        target=f"layer:{layer.key}",
        reason=reason,
        details={"feature": str(feature.id), "ref": feature.ref, "name": feature.name},
    )
    await session.flush()
    row = (
        await session.execute(select(LayerFeature, service.LAT, service.LON).where(LayerFeature.id == feature.id))
    ).one()
    out = _feature_out(*row)
    await session.commit()
    return out


@router.post("/{key}/features/{feature_id}/restore", response_model=schemas.FeatureOut)
async def restore_feature(
    principal: Staff, session: Session, key: str, feature_id: uuid.UUID, body: schemas.ReasonIn
) -> schemas.FeatureOut:
    layer = await _layer(session, key, lock=True)
    _require(can_import(principal, layer), principal)
    feature = await _feature(session, layer, feature_id)
    if feature.deleted_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_deleted")
    reason = _check_reason(body.reason)
    feature.deleted_at = feature.deleted_by = feature.delete_reason = None
    feature.version += 1
    layer.data_version += 1
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="layer.feature_restore",
        target=f"layer:{layer.key}",
        reason=reason,
        details={"feature": str(feature.id), "ref": feature.ref},
    )
    await session.flush()
    row = (
        await session.execute(select(LayerFeature, service.LAT, service.LON).where(LayerFeature.id == feature.id))
    ).one()
    out = _feature_out(*row)
    await session.commit()
    return out


# ---------------------------------------------------------------- reviewing suggested names (design §3.6)


@router.get("/{key}/review", response_model=schemas.ReviewQueue)
async def review_queue(
    principal: Staff,
    session: Session,
    key: str,
    confidence: Annotated[Literal["confirmed", "high", "medium", "low", "review"] | None, Query()] = None,
    duplicates: Annotated[bool, Query(description="the possible duplicates instead of the names")] = False,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> schemas.ReviewQueue:
    """The places waiting for the administrator: suggested names (by confidence), or possible duplicates."""
    layer = await _layer(session, key)
    _require(can_import(principal, layer), principal)
    live = (LayerFeature.layer_id == layer.id) & LayerFeature.deleted_at.is_(None)
    waiting = LayerFeature.possible_duplicate.is_(True) if duplicates else LayerFeature.name_status == "suggested"
    counts = dict(
        (
            await session.execute(
                select(LayerFeature.name_confidence, func.count())
                .where(live, LayerFeature.name_status == "suggested")
                .group_by(LayerFeature.name_confidence)
            )
        ).all()
    )
    counts = {str(k or "unknown"): int(v) for k, v in counts.items()}
    counts["duplicates"] = int(
        await session.scalar(select(func.count()).where(live, LayerFeature.possible_duplicate.is_(True))) or 0
    )
    query = select(LayerFeature, service.LAT, service.LON).where(live, waiting)
    if confidence is not None and not duplicates:
        query = query.where(LayerFeature.name_confidence == confidence)
    total = int(await session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    order = (LayerFeature.name, LayerFeature.id) if duplicates else (LayerFeature.gouvernorat_code, LayerFeature.id)
    rows = (await session.execute(query.order_by(*order).offset(offset).limit(limit))).all()
    return schemas.ReviewQueue(items=[_feature_out(f, la, lo) for f, la, lo in rows], counts=counts, total=total)


@router.post("/{key}/review", response_model=schemas.ReviewOut)
async def review(principal: Staff, session: Session, key: str, body: schemas.ReviewIn) -> schemas.ReviewOut:
    """Accept, edit or reject suggested names (one by one, or every name of a confidence at once); keep or merge
    possible duplicates. The citizen's app shows a place only once its name is official or accepted."""
    layer = await _layer(session, key, lock=True)
    _require(can_import(principal, layer), principal)
    reason = _check_reason(body.reason)
    actor = audit.actor_of(principal)
    now = datetime.now(UTC)
    done = dict.fromkeys(("accepted", "edited", "rejected", "kept", "merged"), 0)
    if body.accept_confidence:
        result = await session.execute(
            update(LayerFeature)
            .where(
                LayerFeature.layer_id == layer.id,
                LayerFeature.deleted_at.is_(None),
                LayerFeature.name_status == "suggested",
                LayerFeature.name_confidence.in_(body.accept_confidence),
            )
            .values(name_status="accepted", version=LayerFeature.version + 1, updated_by=actor, updated_at=now)
        )
        done["accepted"] += result.rowcount or 0  # type: ignore[attr-defined]
    ids = [item.id for item in body.items] + [item.into for item in body.items if item.into]
    found = {
        f.id: f
        for f in await session.scalars(
            select(LayerFeature).where(LayerFeature.layer_id == layer.id, LayerFeature.id.in_(ids)).with_for_update()
        )
    }
    for item in body.items:
        feature = found.get(item.id)
        if feature is None or feature.deleted_at is not None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        if item.action == "accept":
            feature.name_status = "accepted"
            done["accepted"] += 1
        elif item.action == "edit":
            if not item.name or not item.name.strip():
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "name_required")
            feature.name, feature.name_status = item.name.strip(), "accepted"
            done["edited"] += 1
        elif item.action == "reject":
            feature.name_status = "rejected"
            done["rejected"] += 1
        elif item.action == "keep":
            feature.possible_duplicate = False
            done["kept"] += 1
        else:  # merge: this place duplicates ``into``, which stays
            other = found.get(item.into) if item.into else None
            if other is None or other.id == feature.id or other.deleted_at is not None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "merge_target_invalid")
            feature.deleted_at, feature.deleted_by, feature.delete_reason = now, actor, f"merge:{other.id}"
            other.possible_duplicate = False
            # The kept place takes what only the duplicate had (a phone, a column).
            other.phone = other.phone or feature.phone
            other.props = {**feature.props, **other.props}
            other.version += 1
            done["merged"] += 1
        feature.version += 1
        feature.updated_by, feature.updated_at = actor, now
    if any(done.values()):
        layer.data_version += 1
    await audit.record(
        session, actor=actor, action="layer.review", target=f"layer:{layer.key}", reason=reason, details=done
    )
    await session.commit()
    return schemas.ReviewOut(**done)


# ---------------------------------------------------------------- public (the app)


def _localized(names: dict[str, str], lang: Lang) -> str:
    return names.get(lang) or names.get("fr") or next(iter(names.values()), "")


async def _units_summary(session: AsyncSession) -> tuple[int, int]:
    """Count and version of the Civil Protection centres (read across scopes: fixed public sites only)."""
    async with as_system(session):
        count, latest = (await session.execute(select(func.count(Unit.id), func.max(Unit.updated_at)))).one()
    return int(count), int(latest.timestamp()) if latest else 0


def _etag(*parts: object) -> str:
    return '"' + hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:32] + '"'


@public_router.get("", response_model=schemas.PublicLayers)
async def public_layers(
    session: Session,
    response: Response,
    lang: Annotated[Lang, Query()] = "ar",
    if_none_match: Annotated[str | None, Header()] = None,
) -> schemas.PublicLayers | Response:
    layers = (await session.scalars(select(Layer).where(_PUBLIC_LAYER).order_by(Layer.created_at, Layer.key))).all()
    counts = dict(
        (
            await session.execute(
                select(LayerFeature.layer_id, func.count())
                .where(service.public_place())
                .group_by(LayerFeature.layer_id)
            )
        ).all()
    )
    unit_count, unit_version = await _units_summary(session)
    etag = _etag(lang, unit_count, unit_version, *[(layer.key, layer.version, layer.data_version) for layer in layers])
    if if_none_match == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    items = [
        schemas.PublicLayer(
            key=UNITS_KEY,
            name=UNITS_NAME[lang],
            names=schemas.Names.model_validate(UNITS_NAME),
            icon="civil_protection",
            colour="#C62828",
            source=UNITS_SOURCE[lang],
            licence="",
            to_verify=False,
            simulated=False,
            count=unit_count,
            data_version=unit_version,
            origin="units",
        )
    ]
    items += [
        schemas.PublicLayer(
            key=layer.key,
            name=_localized(layer.name, lang),
            names=schemas.Names.model_validate(layer.name),
            icon=layer.icon,
            colour=layer.colour,
            source=layer.source,
            licence=layer.licence,
            to_verify=layer.to_verify,
            simulated=layer.simulated,
            count=counts.get(layer.id, 0),
            data_version=layer.data_version,
            origin="file",
            default_on=layer.default_on,
            actions=schemas.Actions.model_validate(layer.actions or {}),
        )
        for layer in layers
    ]
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return schemas.PublicLayers(items=items)


# "Nearest on the road": this many times ``limit`` candidates as the crow flies are timed on the road.
ROAD_CANDIDATES = 3


# A layer the citizen's app reads: open to citizens, published, not sensitive, not deleted (RLS says the same).
_PUBLIC_LAYER = (Layer.audience == "public") & Layer.enabled & Layer.sensitive.is_(False) & Layer.deleted_at.is_(None)


async def _public_layer(session: AsyncSession, key: str) -> Layer:
    layer = await session.scalar(select(Layer).where(Layer.key == key, _PUBLIC_LAYER))
    if layer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return layer


def _public_feature(
    layer: Layer, f: LayerFeature, lat: float, lon: float, lang: Lang, distance: float | None = None
) -> schemas.PublicFeature:
    # A file may name a place in each language (columns name_ar, name_fr, name_en): the app gets its own.
    localized = f.props.get(f"name_{lang}")
    hidden = access.visible_fields(None, layer)
    return schemas.PublicFeature(
        id=f.id,
        name=localized.strip() if isinstance(localized, str) and localized.strip() else f.name,
        kind=f.kind,
        phone=None if hidden and "phone" in hidden else f.phone,
        lat=float(lat),
        lon=float(lon),
        gouvernorat_code=f.gouvernorat_code,
        props=service.public_props(layer, f.props),
        distance_m=round(distance, 1) if distance is not None else None,
    )


async def _units(
    session: AsyncSession,
    lang: Lang,
    *,
    near: tuple[float, float] | None = None,
    radius_m: int = 0,
    bbox: tuple[float, float, float, float] | None = None,
    gouvernorat: int | None = None,
    limit: int,
) -> list[schemas.PublicFeature]:
    lat_col, lon_col = func.ST_Y(cast(Unit.location, Geometry)), func.ST_X(cast(Unit.location, Geometry))
    columns: list[Any] = [Unit, lat_col, lon_col]
    query = select(*columns)
    if near is not None:
        here = func.ST_GeogFromText(service.point(*near))
        distance = func.ST_Distance(Unit.location, here)
        query = select(Unit, lat_col, lon_col, distance).where(func.ST_DWithin(Unit.location, here, radius_m))
        query = query.order_by(distance, Unit.id)
    else:
        query = query.order_by(Unit.name_fr, Unit.id)
    if bbox is not None:
        query = query.where(func.ST_Intersects(cast(Unit.location, Geometry), func.ST_MakeEnvelope(*bbox, 4326)))
    if gouvernorat is not None:
        query = query.where(Unit.gouvernorat_code == gouvernorat)
    async with as_system(session):
        rows = (await session.execute(query.limit(limit))).all()
    return [
        schemas.PublicFeature(
            id=row[0].id,
            name=row[0].name_ar if lang == "ar" else row[0].name_fr,
            kind=row[0].kind,
            phone=row[0].phone,
            lat=float(row[1]),
            lon=float(row[2]),
            gouvernorat_code=row[0].gouvernorat_code,
            props={},
            distance_m=round(float(row[3]), 1) if near is not None else None,
        )
        for row in rows
    ]


@public_router.get("/{key}/features", response_model=schemas.PublicFeatures)
async def public_features(
    session: Session,
    response: Response,
    key: str,
    near: Annotated[str | None, Query(description="lat,lon")] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 3,
    radius_km: Annotated[int, Query(ge=1, le=300)] = 100,
    bbox: Annotated[str | None, Query(description="minLon,minLat,maxLon,maxLat")] = None,
    lang: Annotated[Lang, Query()] = "ar",
    road: Annotated[bool, Query(description="order the nearest places by the road (car)")] = False,
) -> schemas.PublicFeatures:
    """Either the nearest places to ``near`` (with their distance) or the places in a map area (``bbox``). With
    ``road``, the closest candidates as the crow flies are ordered by the distance and time on the road (routing
    engine, or its estimate when the engine is not there, said in ``road_engine``)."""
    if (near is None) == (bbox is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "near_or_bbox_required")
    position: tuple[float, float] | None = None
    if near is not None:
        try:
            lat, lon = (float(p) for p in near.split(","))
        except ValueError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_near") from None
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_near")
        position = (lat, lon)
    area = _bbox(bbox)
    response.headers["Cache-Control"] = "public, max-age=60"
    if key == UNITS_KEY:
        _, version = await _units_summary(session)
        cap = limit if position else MAX_PUBLIC_BBOX + 1
        items = await _units(session, lang, near=position, radius_m=radius_km * 1000, bbox=area, limit=cap)
        return schemas.PublicFeatures(
            layer=key, data_version=version, items=items[:MAX_PUBLIC_BBOX], truncated=len(items) > MAX_PUBLIC_BBOX
        )
    layer = await _public_layer(session, key)
    if position is not None:
        candidates = min(limit * ROAD_CANDIDATES, 50) if road else limit
        found = await service.nearest(session, layer, position[0], position[1], candidates, radius_km * 1000)
        items = [_public_feature(layer, f, la, lo, lang, float(d)) for f, la, lo, d in found]
        if road and items:
            here = routing.Point(position[0], position[1])
            legs, engine = await routing.travel([routing.Point(i.lat, i.lon) for i in items], here, "car")
            for item, leg in zip(items, legs, strict=True):
                item.road_m, item.road_s, item.road_engine = round(leg.distance_m), round(leg.duration_s), engine
            items = sorted(items, key=lambda i: (i.road_s or 0.0, i.distance_m or 0.0))[:limit]
        return schemas.PublicFeatures(layer=key, data_version=layer.data_version, items=items)
    rows = await service.features_in(session, layer, bbox=area, public=True, limit=MAX_PUBLIC_BBOX + 1)
    return schemas.PublicFeatures(
        layer=key,
        data_version=layer.data_version,
        items=[_public_feature(layer, f, la, lo, lang) for f, la, lo in rows[:MAX_PUBLIC_BBOX]],
        truncated=len(rows) > MAX_PUBLIC_BBOX,
    )


@public_router.get("/{key}/package", response_model=schemas.PublicFeatures)
async def public_package(
    session: Session,
    response: Response,
    key: str,
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
    lang: Annotated[Lang, Query()] = "ar",
    if_none_match: Annotated[str | None, Header()] = None,
) -> schemas.PublicFeatures | Response:
    """Offline copy of a layer (one gouvernorat, or the whole country): the app keeps it and asks again with
    ``If-None-Match``; an unchanged layer answers 304 without a body."""
    if key == UNITS_KEY:
        count, version = await _units_summary(session)
        etag = _etag(key, version, count, gouvernorat, lang)
        if if_none_match == etag:
            return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
        items = await _units(session, lang, gouvernorat=gouvernorat, limit=MAX_PACKAGE)
        response.headers["ETag"], response.headers["Cache-Control"] = etag, PUBLIC_CACHE
        return schemas.PublicFeatures(layer=key, data_version=version, items=items)
    layer = await _public_layer(session, key)
    etag = _etag(key, layer.data_version, layer.version, gouvernorat, lang)
    if if_none_match == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    rows = await service.features_in(session, layer, gouvernorat=gouvernorat, public=True, limit=MAX_PACKAGE + 1)
    response.headers["ETag"], response.headers["Cache-Control"] = etag, PUBLIC_CACHE
    return schemas.PublicFeatures(
        layer=key,
        data_version=layer.data_version,
        items=[_public_feature(layer, f, la, lo, lang) for f, la, lo in rows[:MAX_PACKAGE]],
        truncated=len(rows) > MAX_PACKAGE,
    )
