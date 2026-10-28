"""Seasonal programme endpoints (phase L2, docs/phase-l/design-l2.md §2).

Staff only. The national programme managers (system administrator, operations manager) create, import, approve,
cancel and change programmes; every change after approval is a new version with its reason, and an approved
programme shows on the maps through its layer between its validity dates. A regional room (operator, operations
manager) does the daily follow-up of the points of its own gouvernorat: status, lifeguards deployed, a note. The
supervisor's name and phone are returned to the operations rooms only.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.geo.models import Layer
from app.modules.layers.service import point as wkt_point
from app.modules.programmes import domain, schemas, service
from app.modules.programmes.models import Programme, ProgrammePoint, ProgrammeRevision
from app.modules.reports.staff_router import READ_ROLES

router = APIRouter(prefix="/api/v1/staff/programmes", tags=["staff", "programmes"])
Session = Annotated[AsyncSession, Depends(get_session)]
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES, Role.SYSADMIN))]
MANAGER_ROLES = frozenset({Role.SYSADMIN, Role.OPS_MANAGER})
ROOM_ROLES = frozenset({Role.OPERATOR, Role.OPS_MANAGER})
FOLLOW_UP = frozenset({"status", "lifeguards_deployed", "notes"})
OPEN_STATUSES = ("draft", *service.LIVE)


def can_manage(principal: Principal) -> bool:
    return principal.is_national and bool(MANAGER_ROLES & set(principal.roles))


def in_room(principal: Principal) -> bool:
    return bool(ROOM_ROLES & set(principal.roles)) or can_manage(principal)


def can_follow_up(principal: Principal, programme: Programme, gouvernorat: int | None) -> bool:
    if programme.status not in service.LIVE or not ROOM_ROLES & set(principal.roles):
        return False
    return principal.is_national or (gouvernorat is not None and principal.gouvernorat_code == gouvernorat)


def _require_manager(principal: Principal) -> None:
    if not can_manage(principal):
        code = "national_scope_required" if not principal.is_national else "insufficient_role"
        raise HTTPException(status.HTTP_403_FORBIDDEN, code)


def _reason(reason: str, *, required: bool = True) -> str | None:
    reason = reason.strip()
    if required and len(reason) < 5:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reason_required")
    return reason or None


async def _programme(session: AsyncSession, programme_id: uuid.UUID, *, lock: bool = False) -> Programme:
    query = select(Programme).where(Programme.id == programme_id)
    found = await session.scalar(query.with_for_update() if lock else query)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "programme_not_found")
    return found


async def _layer_keys(session: AsyncSession, programmes: list[Programme]) -> dict[uuid.UUID, str]:
    ids = [p.layer_id for p in programmes if p.layer_id]
    if not ids:
        return {}
    rows = (await session.execute(select(Layer.id, Layer.key).where(Layer.id.in_(ids)))).all()
    return dict(rows)


def _out(
    p: Programme, principal: Principal, figures: dict[str, Any] | None, layer_key: str | None
) -> schemas.ProgrammeOut:
    return schemas.ProgrammeOut(
        id=str(p.id),
        code=p.code,
        kind=p.kind,
        title=p.title,
        season=p.season,
        valid_from=p.valid_from,
        valid_to=p.valid_to,
        status=p.status,
        version=p.version,
        source_document=p.source_document,
        declared=p.declared or {},
        approved_by_name=p.approved_by_name,
        approved_at=p.approved_at,
        cancel_reason=p.cancel_reason,
        layer_key=layer_key,
        live=service.live_on(p, service.today()),
        updated_by_name=p.updated_by_name,
        updated_at=p.updated_at,
        figures=schemas.Figures(**(figures or {})),
        can_edit=can_manage(principal) and p.status in OPEN_STATUSES,
        can_follow_up=p.status in service.LIVE and bool(ROOM_ROLES & set(principal.roles)),
    )


def _point_out(
    p: ProgrammePoint, lat: float | None, lon: float | None, principal: Principal, programme: Programme
) -> schemas.PointOut:
    room = in_room(principal)
    return schemas.PointOut(
        id=str(p.id),
        ref=p.ref,
        gouvernorat_code=p.gouvernorat_code,
        place_name=p.place_name,
        sub_points=p.sub_points,
        lat=lat,
        lon=lon,
        geo_confidence=p.geo_confidence,
        geo_note=p.geo_note,
        staff_count=p.staff_count,
        staff_composition=p.staff_composition,
        supervisors=p.supervisors,
        lifeguards_planned=p.lifeguards_planned,
        lifeguards_deployed=p.lifeguards_deployed,
        equipment=p.equipment,
        hours=p.hours,
        opening_date=p.opening_date,
        closing_date=p.closing_date,
        status=p.status,
        supervisor_name=p.supervisor_name if room else None,
        supervisor_phone=p.supervisor_phone if room else None,
        notes=p.notes,
        updated_at=p.updated_at,
        can_follow_up=can_follow_up(principal, programme, p.gouvernorat_code),
    )


async def _detail(session: AsyncSession, programme: Programme, principal: Principal) -> schemas.ProgrammeDetail:
    query = select(ProgrammePoint, service.LAT, service.LON).where(ProgrammePoint.programme_id == programme.id)
    if not principal.is_national:
        query = query.where(ProgrammePoint.gouvernorat_code == principal.gouvernorat_code)
    rows = (await session.execute(query.order_by(ProgrammePoint.ref))).all()
    points = [_point_out(p, lat, lon, principal, programme) for p, lat, lon in rows]
    figures = (await service.figures(session, [programme.id])).get(programme.id)
    keys = await _layer_keys(session, [programme])
    computed = domain.totals([{c: getattr(p, c) for c in domain.TOTALS.values()} for p, _, _ in rows])
    return schemas.ProgrammeDetail(
        programme=_out(programme, principal, figures, keys.get(programme.layer_id) if programme.layer_id else None),
        points=points,
        computed=computed,
    )


async def _changed(
    session: AsyncSession, programme: Programme, principal: Principal, action: str, reason: str | None
) -> None:
    """After any change: a live programme becomes "updated", a version is kept, and its layer follows."""
    if programme.status == "approved":
        programme.status = "updated"
    await service.revise(session, programme, principal, action, reason)
    await service.sync_layer(session, programme, audit.actor_of(principal))


# ---------------------------------------------------------------- programmes


@router.get("", response_model=schemas.ProgrammesOut)
async def list_programmes(principal: Reader, session: Session) -> schemas.ProgrammesOut:
    programmes = list(
        (await session.scalars(select(Programme).order_by(Programme.valid_from.desc(), Programme.code))).all()
    )
    figures = await service.figures(session, [p.id for p in programmes])
    keys = await _layer_keys(session, programmes)
    items = [_out(p, principal, figures.get(p.id), keys.get(p.layer_id) if p.layer_id else None) for p in programmes]
    return schemas.ProgrammesOut(items=items, can_create=can_manage(principal))


@router.post("", response_model=schemas.ProgrammeDetail, status_code=status.HTTP_201_CREATED)
async def create_programme(principal: Reader, session: Session, body: schemas.ProgrammeIn) -> schemas.ProgrammeDetail:
    _require_manager(principal)
    if body.valid_to < body.valid_from:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "dates_reversed")
    if await session.scalar(select(Programme.id).where(Programme.code == body.code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "code_taken")
    actor = audit.actor_of(principal)
    programme = Programme(
        **body.model_dump(),
        status="draft",
        declared={},
        created_by=actor,
        updated_by=actor,
        updated_by_name=audit.name_of(principal),
    )
    session.add(programme)
    await session.flush()
    await service.revise(session, programme, principal, "create", None)
    await audit.record(session, actor=actor, action="programme.create", target=f"programme:{programme.code}")
    out = await _detail(session, programme, principal)
    await session.commit()
    return out


@router.get("/{programme_id}", response_model=schemas.ProgrammeDetail)
async def get_programme(principal: Reader, session: Session, programme_id: uuid.UUID) -> schemas.ProgrammeDetail:
    return await _detail(session, await _programme(session, programme_id), principal)


@router.patch("/{programme_id}", response_model=schemas.ProgrammeDetail)
async def update_programme(
    principal: Reader, session: Session, programme_id: uuid.UUID, body: schemas.ProgrammePatch
) -> schemas.ProgrammeDetail:
    _require_manager(principal)
    programme = await _programme(session, programme_id, lock=True)
    if programme.status not in OPEN_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "programme_closed")
    reason = _reason(body.reason, required=programme.status != "draft")
    changes = body.model_dump(exclude_unset=True, exclude={"reason"})
    for key, value in changes.items():
        if value is not None:
            setattr(programme, key, value)
    if programme.valid_to < programme.valid_from:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "dates_reversed")
    await _changed(session, programme, principal, "update", reason)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="programme.update",
        target=f"programme:{programme.code}",
        reason=reason,
        details={"fields": sorted(changes)},
    )
    out = await _detail(session, programme, principal)
    await session.commit()
    return out


@router.delete("/{programme_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_programme(principal: Reader, session: Session, programme_id: uuid.UUID) -> Response:
    """A draft is deleted; an approved programme is cancelled instead (its versions stay)."""
    _require_manager(principal)
    programme = await _programme(session, programme_id, lock=True)
    if programme.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "cancel_instead")
    await audit.record(
        session, actor=audit.actor_of(principal), action="programme.delete", target=f"programme:{programme.code}"
    )
    await session.delete(programme)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{programme_id}/approve", response_model=schemas.ProgrammeDetail)
async def approve(
    principal: Reader, session: Session, programme_id: uuid.UUID, body: schemas.ReasonIn
) -> schemas.ProgrammeDetail:
    _require_manager(principal)
    programme = await _programme(session, programme_id, lock=True)
    if programme.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "programme_not_draft")
    if not await session.scalar(select(ProgrammePoint.id).where(ProgrammePoint.programme_id == programme.id).limit(1)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "no_points")
    programme.status = "approved"
    programme.approved_by = audit.actor_of(principal)
    programme.approved_by_name = audit.name_of(principal)
    programme.approved_at = datetime.now(UTC)
    reason = _reason(body.reason, required=False)
    await service.revise(session, programme, principal, "approve", reason)
    await service.sync_layer(session, programme, audit.actor_of(principal))
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="programme.approve",
        target=f"programme:{programme.code}",
        reason=reason,
    )
    out = await _detail(session, programme, principal)
    await session.commit()
    return out


@router.post("/{programme_id}/cancel", response_model=schemas.ProgrammeDetail)
async def cancel(
    principal: Reader, session: Session, programme_id: uuid.UUID, body: schemas.ReasonIn
) -> schemas.ProgrammeDetail:
    _require_manager(principal)
    programme = await _programme(session, programme_id, lock=True)
    if programme.status not in service.LIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_live")
    reason = _reason(body.reason)
    programme.status = "cancelled"
    programme.cancel_reason = reason
    await service.revise(session, programme, principal, "cancel", reason)
    await service.sync_layer(session, programme, audit.actor_of(principal))
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="programme.cancel",
        target=f"programme:{programme.code}",
        reason=reason,
    )
    out = await _detail(session, programme, principal)
    await session.commit()
    return out


@router.post("/{programme_id}/copy", response_model=schemas.ProgrammeDetail, status_code=status.HTTP_201_CREATED)
async def copy_programme(
    principal: Reader, session: Session, programme_id: uuid.UUID, body: schemas.CopyIn
) -> schemas.ProgrammeDetail:
    """ "Copy last year's programme": a new draft with the same points, opened, without this year's counts."""
    _require_manager(principal)
    source = await _programme(session, programme_id)
    if body.valid_to < body.valid_from:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "dates_reversed")
    if await session.scalar(select(Programme.id).where(Programme.code == body.code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "code_taken")
    actor = audit.actor_of(principal)
    programme = Programme(
        code=body.code,
        kind=source.kind,
        title=body.title or source.title,
        season=body.season,
        valid_from=body.valid_from,
        valid_to=body.valid_to,
        source_document=f"نسخة من {source.code}",
        declared={},
        status="draft",
        created_by=actor,
        updated_by=actor,
        updated_by_name=audit.name_of(principal),
    )
    session.add(programme)
    await session.flush()
    rows = (
        await session.execute(
            select(ProgrammePoint, service.LAT, service.LON).where(ProgrammePoint.programme_id == source.id)
        )
    ).all()
    prefix = source.code + "-"
    for p, lat, lon in rows:
        ref = body.code + "-" + p.ref[len(prefix) :] if p.ref.startswith(prefix) else p.ref
        session.add(
            ProgrammePoint(
                programme_id=programme.id,
                ref=ref,
                gouvernorat_code=p.gouvernorat_code,
                place_name=p.place_name,
                sub_points=p.sub_points,
                location=wkt_point(lat, lon) if lat is not None else None,
                geo_confidence=p.geo_confidence,
                geo_note=p.geo_note,
                staff_count=p.staff_count,
                staff_composition=p.staff_composition,
                supervisors=p.supervisors,
                lifeguards_planned=p.lifeguards_planned,
                equipment=p.equipment,
                hours=p.hours,
                status="open",
                supervisor_name=p.supervisor_name,
                supervisor_phone=p.supervisor_phone,
                updated_by=actor,
            )
        )
    await service.revise(session, programme, principal, "copy", f"نسخة من {source.code}")
    await audit.record(
        session,
        actor=actor,
        action="programme.copy",
        target=f"programme:{programme.code}",
        details={"from": source.code},
    )
    out = await _detail(session, programme, principal)
    await session.commit()
    return out


# ---------------------------------------------------------------- points


def _locate(values: dict[str, Any]) -> None:
    lat, lon = values.pop("lat", None), values.pop("lon", None)
    if (lat is None) != (lon is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "bad_coordinates")
    if lat is not None:
        values["location"] = wkt_point(lat, lon)


@router.post("/{programme_id}/points", response_model=schemas.ProgrammeDetail, status_code=status.HTTP_201_CREATED)
async def add_point(
    principal: Reader, session: Session, programme_id: uuid.UUID, body: schemas.PointIn
) -> schemas.ProgrammeDetail:
    _require_manager(principal)
    programme = await _programme(session, programme_id, lock=True)
    if programme.status not in OPEN_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "programme_closed")
    reason = _reason(body.reason, required=programme.status != "draft")
    if await session.scalar(
        select(ProgrammePoint.id).where(ProgrammePoint.programme_id == programme.id, ProgrammePoint.ref == body.ref)
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "ref_taken")
    values = body.model_dump(exclude={"reason"})
    has_position = values["lat"] is not None
    _locate(values)
    values["geo_confidence"] = values["geo_confidence"] or ("confirmed" if has_position else "unknown")
    session.add(ProgrammePoint(programme_id=programme.id, updated_by=audit.actor_of(principal), **values))
    await _changed(session, programme, principal, "point_add", reason)
    out = await _detail(session, programme, principal)
    await session.commit()
    return out


@router.patch("/{programme_id}/points/{point_id}", response_model=schemas.ProgrammeDetail)
async def update_point(
    principal: Reader, session: Session, programme_id: uuid.UUID, point_id: uuid.UUID, body: schemas.PointPatch
) -> schemas.ProgrammeDetail:
    programme = await _programme(session, programme_id, lock=True)
    point = await session.scalar(
        select(ProgrammePoint).where(ProgrammePoint.id == point_id, ProgrammePoint.programme_id == programme.id)
    )
    if point is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "point_not_found")
    changes = body.model_dump(exclude_unset=True, exclude={"reason"})
    manager = can_manage(principal) and programme.status in OPEN_STATUSES
    if not manager:
        if not can_follow_up(principal, programme, point.gouvernorat_code):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient_role")
        if set(changes) - FOLLOW_UP:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "follow_up_only")
    if not changes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "nothing_to_change")
    if manager:
        reason = _reason(body.reason, required=programme.status != "draft")
    else:
        reason = _reason(body.reason, required=False) or "متابعة يومية"
    if "lat" in changes or "lon" in changes:
        if changes.get("lat") is None or changes.get("lon") is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "bad_coordinates")
        changes.setdefault("geo_confidence", "confirmed")
    _locate(changes)
    for key, value in changes.items():
        setattr(point, key, value)
    point.updated_by = audit.actor_of(principal)
    point.updated_at = datetime.now(UTC)
    await _changed(session, programme, principal, "point_update" if manager else "follow_up", reason)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="programme.point",
        target=f"programme:{programme.code}",
        reason=reason,
        details={"point": point.ref, "fields": sorted(changes)},
        gouvernorats=[point.gouvernorat_code] if point.gouvernorat_code else None,
    )
    out = await _detail(session, programme, principal)
    await session.commit()
    return out


@router.delete("/{programme_id}/points/{point_id}", response_model=schemas.ProgrammeDetail)
async def delete_point(
    principal: Reader, session: Session, programme_id: uuid.UUID, point_id: uuid.UUID
) -> schemas.ProgrammeDetail:
    """A point of a draft is deleted; a point of an approved programme is closed instead (a new version)."""
    _require_manager(principal)
    programme = await _programme(session, programme_id, lock=True)
    if programme.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "close_instead")
    point = await session.scalar(
        select(ProgrammePoint).where(ProgrammePoint.id == point_id, ProgrammePoint.programme_id == programme.id)
    )
    if point is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "point_not_found")
    await session.delete(point)
    await service.revise(session, programme, principal, "point_delete", point.ref)
    out = await _detail(session, programme, principal)
    await session.commit()
    return out


# ---------------------------------------------------------------- versions


async def _revision(session: AsyncSession, programme: Programme, number: int) -> ProgrammeRevision:
    found = await session.scalar(
        select(ProgrammeRevision).where(
            ProgrammeRevision.programme_id == programme.id, ProgrammeRevision.number == number
        )
    )
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "revision_not_found")
    return found


@router.get("/{programme_id}/revisions", response_model=schemas.RevisionsOut)
async def list_revisions(principal: Reader, session: Session, programme_id: uuid.UUID) -> schemas.RevisionsOut:
    programme = await _programme(session, programme_id)
    rows = (
        await session.scalars(
            select(ProgrammeRevision)
            .where(ProgrammeRevision.programme_id == programme.id)
            .order_by(ProgrammeRevision.number.desc())
        )
    ).all()
    return schemas.RevisionsOut(
        items=[
            schemas.RevisionOut(
                number=r.number,
                action=r.action,
                reason=r.reason,
                created_by_name=r.created_by_name,
                created_at=r.created_at,
                points=len(r.snapshot.get("points", {})),
            )
            for r in rows
        ]
    )


def _hide_supervisor(found: dict[str, Any], principal: Principal) -> dict[str, Any]:
    if in_room(principal):
        return found
    for fields in found["changed"].values():
        for key in ("supervisor_name", "supervisor_phone"):
            if key in fields:
                fields[key] = [None, None]
    return found


@router.get("/{programme_id}/revisions/{number}/diff", response_model=schemas.DiffOut)
async def revision_diff(
    principal: Reader,
    session: Session,
    programme_id: uuid.UUID,
    number: int,
    against: Annotated[int | None, Query(ge=1)] = None,
) -> schemas.DiffOut:
    """What version ``number`` changed compared with ``against`` (the version before it by default)."""
    programme = await _programme(session, programme_id)
    after = await _revision(session, programme, number)
    base = against if against is not None else number - 1
    before = (await _revision(session, programme, base)).snapshot if base >= 1 else {}
    found = _hide_supervisor(domain.diff(before, after.snapshot), principal)
    return schemas.DiffOut(number=number, against=base if base >= 1 else None, **found)


@router.post("/{programme_id}/revisions/{number}/restore", response_model=schemas.ProgrammeDetail)
async def restore_revision(
    principal: Reader, session: Session, programme_id: uuid.UUID, number: int, body: schemas.ReasonIn
) -> schemas.ProgrammeDetail:
    """Back to a version: its dates, title and points (a new version; the status does not go back)."""
    _require_manager(principal)
    programme = await _programme(session, programme_id, lock=True)
    if programme.status not in OPEN_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "programme_closed")
    reason = _reason(body.reason)
    snap = (await _revision(session, programme, number)).snapshot
    meta = snap.get("programme", {})
    for key in ("title", "season", "source_document"):
        if key in meta:
            setattr(programme, key, meta[key])
    for key in ("valid_from", "valid_to"):
        if meta.get(key):
            setattr(programme, key, date.fromisoformat(meta[key]))
    await session.execute(delete(ProgrammePoint).where(ProgrammePoint.programme_id == programme.id))
    for ref, values in snap.get("points", {}).items():
        session.add(
            ProgrammePoint(
                programme_id=programme.id,
                ref=ref,
                updated_by=audit.actor_of(principal),
                **service.restore_values(values),
            )
        )
    await _changed(session, programme, principal, "restore", f"{reason} (← {number})")
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="programme.restore",
        target=f"programme:{programme.code}",
        reason=reason,
        details={"revision": number},
    )
    out = await _detail(session, programme, principal)
    await session.commit()
    return out


# ---------------------------------------------------------------- import


async def _read_body(request: Request) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > domain.MAX_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "file_too_large")
        chunks.append(chunk)
    return b"".join(chunks)


def _virtual(meta: dict[str, Any], status_: str, points: list[dict[str, Any]], index: dict[str, int]) -> dict[str, Any]:
    """A snapshot of what the file holds, to compare with the programme in the system."""
    out_points = {}
    for p in points:
        values = {k: service._iso(p.get(k)) for k in domain.POINT_FIELDS if k not in ("gouvernorat_code", "lat", "lon")}
        values["gouvernorat_code"] = service.gouvernorat_of(index, p.get("governorate", ""))
        values["lat"] = round(p["lat"], 6) if p.get("lat") is not None else None
        values["lon"] = round(p["lon"], 6) if p.get("lon") is not None else None
        out_points[p["ref"]] = values
    return {"programme": {**{k: service._iso(v) for k, v in meta.items()}, "status": status_}, "points": out_points}


@router.post("/imports", response_model=schemas.ImportOut)
async def import_programmes(
    principal: Reader,
    session: Session,
    request: Request,
    file_name: Annotated[str, Query(min_length=1, max_length=200)],
    apply: Annotated[bool, Query()] = False,
    reason: Annotated[str, Query(max_length=500)] = "",
) -> schemas.ImportOut:
    """The file (xlsx template, CSV of points or JSON) is the request body. Without ``apply`` nothing is saved: the
    answer lists the errors, the warnings (totals that do not add up, points without a position) and, for a
    programme already in the system, what the file changes. With ``apply`` the new programmes are saved as drafts and
    an existing one gets a new version with the file's points."""
    _require_manager(principal)
    data = await _read_body(request)
    try:
        parsed = domain.parse(file_name, data)
    except domain.FileError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.code) from exc
    why = _reason(reason) if apply else None
    index = await service.gouvernorat_index(session)
    errors = [e.out() for e in parsed.errors]
    warnings = [w.out() for w in parsed.warnings]
    results: list[schemas.ImportedProgramme] = []
    actor = audit.actor_of(principal)
    for item in parsed.programmes:
        kept = []
        for p in item.points:
            if service.gouvernorat_of(index, p.get("governorate", "")) is None:
                errors.append(
                    {
                        "code": "unknown_gouvernorat",
                        "programme": item.code,
                        "ref": p["ref"],
                        "value": p.get("governorate", ""),
                    }
                )
                continue
            kept.append(p)
        item.points = kept
        existing = await session.scalar(select(Programme).where(Programme.code == item.code).with_for_update())
        if existing is None and item.meta is None:
            errors.append({"code": "programme_unknown", "programme": item.code})
            continue
        if existing is not None and existing.status not in OPEN_STATUSES:
            errors.append({"code": "programme_closed", "programme": item.code})
            continue
        meta = item.meta or {}
        found_diff = None
        if existing is not None:
            current = await service.snapshot(session, existing)
            wanted_meta = {k: current["programme"][k] for k in domain.PROGRAMME_FIELDS if k != "status"}
            wanted_meta.update({k: v for k, v in meta.items() if k in wanted_meta})
            virtual = _virtual(wanted_meta, existing.status, item.points, index)
            found_diff = schemas.DiffOut(
                number=existing.version + 1,
                against=existing.version,
                **_hide_supervisor(domain.diff(current, virtual), principal),
            )
        results.append(
            schemas.ImportedProgramme(
                code=item.code,
                title=meta.get("title") or (existing.title if existing else None),
                kind=meta.get("kind") or (existing.kind if existing else None),
                exists=existing is not None,
                status=existing.status if existing else None,
                points=len(item.points),
                unlocated=sum(1 for p in item.points if p.get("lat") is None),
                computed=domain.totals(item.points),
                declared=item.declared,
                diff=found_diff,
            )
        )
        if not apply:
            continue
        programme = existing
        if programme is None:
            programme = Programme(
                **meta,
                status="draft",
                declared=item.declared,
                created_by=actor,
                updated_by=actor,
                updated_by_name=audit.name_of(principal),
            )
            session.add(programme)
            await session.flush()
        else:
            for key in ("title", "season", "valid_from", "valid_to", "source_document", "kind"):
                if key in meta:
                    setattr(programme, key, meta[key])
            if item.declared:
                programme.declared = item.declared
            await session.execute(delete(ProgrammePoint).where(ProgrammePoint.programme_id == programme.id))
        for p in item.points:
            session.add(ProgrammePoint(programme_id=programme.id, updated_by=actor, **service.point_values(p, index)))
        if existing is None:
            await service.revise(session, programme, principal, "import", why)
        else:
            await _changed(session, programme, principal, "import", why)
        await audit.record(
            session,
            actor=actor,
            action="programme.import",
            target=f"programme:{programme.code}",
            reason=why,
            details={"file": file_name, "points": len(item.points)},
        )
    if apply:
        await session.commit()
    return schemas.ImportOut(
        format=parsed.format,
        applied=apply,
        programmes=results,
        errors=[schemas.ProblemOut(**e) for e in errors],
        warnings=[schemas.ProblemOut(**w) for w in warnings],
    )
