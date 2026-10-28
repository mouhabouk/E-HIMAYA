"""Watch towers (L5b, docs/phase-l/design-l5.md §3.0 and §3.2) [SIM until the field trial].

* Staff ``/api/v1/staff/towers``: the rooms see their gouvernorat's towers (the central room all of them, row level
  security), with the field of view to draw on the map and the last fire or smoke. The operations manager registers a
  tower (a fixed "camera" stream and its tower), moves or turns it, and rotates the key of its edge computer. The
  camera's publish token and the edge key are shown once and never logged.
* Internal ``POST /internal/towers/events``: the gateway beside MediaMTX relays a signed event of an edge computer.
  Never routed by Caddy; guarded like the sensor readings (app.modules.sensors.gateway).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session, get_system_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.reports.staff_router import READ_ROLES
from app.modules.sensors.gateway import Gateway
from app.modules.streams import service as streams
from app.modules.streams.domain import Source
from app.modules.streams.models import LiveStream
from app.modules.towers import domain, schemas, service
from app.modules.towers.models import CameraTower, TowerEvent

router = APIRouter(prefix="/api/v1/staff/towers", tags=["towers"])
internal_router = APIRouter(include_in_schema=False)

Session = Annotated[AsyncSession, Depends(get_session)]
SystemSession = Annotated[AsyncSession, Depends(get_system_session)]
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
Manager = Annotated[Principal, Depends(require_roles(Role.OPS_MANAGER))]
MAX_TOWERS = 500
MAX_HOURS = 168


def _now() -> datetime:
    return datetime.now(UTC)


def _out(tower: CameraTower, stream: LiveStream, last: TowerEvent | None) -> schemas.TowerOut:
    return schemas.TowerOut(
        id=tower.stream_id,
        code=tower.code,
        label=stream.label or tower.code,
        gouvernorat_code=tower.gouvernorat_code,
        lat=tower.lat,
        lon=tower.lon,
        bearing_deg=tower.bearing_deg,
        fov_deg=tower.fov_deg,
        range_m=tower.range_m,
        simulated=tower.simulated,
        stream_status=stream.status,
        last_event=(schemas.LastEvent(at=last.at, label=last.label, confidence=last.confidence) if last else None),
        field_of_view=domain.wedge(tower.lat, tower.lon, tower.bearing_deg, tower.fov_deg, tower.range_m),
        created_by_name=tower.created_by_name,
        updated_at=tower.updated_at,
    )


async def _last_event(session: AsyncSession, tower_id: uuid.UUID) -> TowerEvent | None:
    return await session.scalar(
        select(TowerEvent).where(TowerEvent.stream_id == tower_id).order_by(TowerEvent.at.desc()).limit(1)
    )


def _can_manage(principal: Principal, code: int | None = None) -> bool:
    if Role.OPS_MANAGER not in principal.roles:
        return False
    return principal.is_national or code is None or code == principal.gouvernorat_code


def _gouvernorat(principal: Principal, wanted: int | None) -> int:
    if not principal.is_national:
        if wanted is not None and wanted != principal.gouvernorat_code:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
        assert principal.gouvernorat_code is not None
        return principal.gouvernorat_code
    if wanted is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "gouvernorat_required")
    return wanted


async def _load(session: AsyncSession, tower_id: uuid.UUID) -> tuple[CameraTower, LiveStream]:
    tower = await session.get(CameraTower, tower_id)  # row level security: out of scope reads as missing
    stream = await session.get(LiveStream, tower_id) if tower else None
    if tower is None or stream is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return tower, stream


@router.get("", response_model=schemas.TowerPage)
async def list_towers(principal: Reader, session: Session) -> schemas.TowerPage:
    rows = (
        await session.execute(
            select(CameraTower, LiveStream)
            .join(LiveStream, LiveStream.id == CameraTower.stream_id)
            .order_by(CameraTower.gouvernorat_code, CameraTower.code)
            .limit(MAX_TOWERS)
        )
    ).all()
    last = {
        e.stream_id: e
        for e in await session.scalars(
            select(TowerEvent)
            .ext(distinct_on(TowerEvent.stream_id))
            .where(TowerEvent.stream_id.in_([t.stream_id for t, _ in rows]))
            .order_by(TowerEvent.stream_id, TowerEvent.at.desc())
        )
    }
    return schemas.TowerPage(
        items=[_out(t, s, last.get(t.stream_id)) for t, s in rows], can_manage=_can_manage(principal)
    )


@router.post("", response_model=schemas.TowerCreated, status_code=status.HTTP_201_CREATED)
async def create_tower(principal: Manager, session: Session, body: schemas.TowerIn) -> schemas.TowerCreated:
    code = _gouvernorat(principal, body.gouvernorat_code)
    taken = await session.scalar(
        select(func.count()).select_from(CameraTower).where(func.lower(CameraTower.code) == body.code.lower())
    )
    if taken:
        raise HTTPException(status.HTTP_409_CONFLICT, "tower_code_taken")
    actor = audit.actor_of(principal)
    stream, token = await streams.register_fixed(
        session, streams.FixedSource(Source.CAMERA, body.label, code, body.lat, body.lon), actor
    )
    key = domain.new_key()
    tower = CameraTower(
        stream_id=stream.id,
        code=body.code,
        gouvernorat_code=code,
        lat=body.lat,
        lon=body.lon,
        bearing_deg=body.bearing_deg,
        fov_deg=body.fov_deg,
        range_m=body.range_m,
        simulated=body.simulated,
        key_enc=service.seal_key(key),
        created_by=actor,
        created_by_name=audit.name_of(principal),
    )
    session.add(tower)
    try:
        await session.flush()
    except IntegrityError as exc:  # another room took the code meanwhile (not visible through row level security)
        raise HTTPException(status.HTTP_409_CONFLICT, "tower_code_taken") from exc
    await session.refresh(tower)
    await audit.record(
        session,
        actor=actor,
        action="tower.create",
        target=f"stream:{stream.id}",
        details={"code": tower.code, "simulated": tower.simulated},
        gouvernorats=[code],
    )
    out = schemas.TowerCreated(
        tower=_out(tower, stream, None),
        edge_key=key,
        publish_token=token,
        publish_url_rtsp=streams.rtsp_publish_url(stream),
        publish_url_rtmp=streams.rtmp_publish_url(stream),
    )
    await session.commit()
    return out


@router.put("/{tower_id}", response_model=schemas.TowerOut)
async def update_tower(
    principal: Manager, session: Session, tower_id: uuid.UUID, body: schemas.TowerUpdate
) -> schemas.TowerOut:
    tower, stream = await _load(session, tower_id)
    if not _can_manage(principal, tower.gouvernorat_code):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
    before = {"bearing_deg": tower.bearing_deg, "fov_deg": tower.fov_deg, "range_m": tower.range_m}
    stream.label = body.label
    for field in ("lat", "lon", "bearing_deg", "fov_deg", "range_m"):
        setattr(tower, field, getattr(body, field))
    tower.updated_at = _now()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="tower.update",
        target=f"stream:{tower.stream_id}",
        details={
            "before": before,
            "after": {"bearing_deg": tower.bearing_deg, "fov_deg": tower.fov_deg, "range_m": tower.range_m},
        },
        gouvernorats=[tower.gouvernorat_code],
    )
    out = _out(tower, stream, await _last_event(session, tower.stream_id))
    await session.commit()
    return out


@router.post("/{tower_id}/key", response_model=schemas.TowerKeyOut)
async def rotate_key(principal: Manager, session: Session, tower_id: uuid.UUID) -> schemas.TowerKeyOut:
    """A new key for the edge computer, shown once; events signed with the old one are refused from now on."""
    tower, stream = await _load(session, tower_id)
    if not _can_manage(principal, tower.gouvernorat_code):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
    key = domain.new_key()
    tower.key_enc, tower.key_version, tower.updated_at = service.seal_key(key), tower.key_version + 1, _now()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="tower.key_rotate",
        target=f"stream:{tower.stream_id}",
        details={"code": tower.code, "key_version": tower.key_version},
        gouvernorats=[tower.gouvernorat_code],
    )
    out = schemas.TowerKeyOut(tower=_out(tower, stream, await _last_event(session, tower.stream_id)), edge_key=key)
    await session.commit()
    return out


@router.get("/{tower_id}/events", response_model=schemas.TowerEventsOut)
async def events(
    principal: Reader,
    session: Session,
    tower_id: uuid.UUID,
    hours: Annotated[int, Query(ge=1, le=MAX_HOURS)] = 24,
) -> schemas.TowerEventsOut:
    tower, _ = await _load(session, tower_id)
    rows = (
        await session.scalars(
            select(TowerEvent)
            .where(TowerEvent.stream_id == tower.stream_id, TowerEvent.at >= _now() - timedelta(hours=hours))
            .order_by(TowerEvent.at.desc())
            .limit(500)
        )
    ).all()
    return schemas.TowerEventsOut(
        tower_id=tower.stream_id,
        items=[
            schemas.TowerEventOut(
                at=e.at,
                label=e.label,
                confidence=e.confidence,
                hits=e.hits,
                frames=e.frames,
                model=e.model,
                media_id=e.media_id,
                suggestion_id=e.suggestion_id,
            )
            for e in rows
        ],
    )


# ---------------------------------------------------------------- the gateway beside MediaMTX


@internal_router.post("/internal/towers/events", response_model=schemas.TowerEventResult)
async def ingest(_: Gateway, session: SystemSession, body: schemas.TowerEventIn) -> schemas.TowerEventResult:
    result = await service.ingest(session, service.RawEvent(**body.model_dump()))
    await session.commit()
    return schemas.TowerEventResult(accepted=result.accepted, reason=result.reason, suggestion=result.suggestion)
