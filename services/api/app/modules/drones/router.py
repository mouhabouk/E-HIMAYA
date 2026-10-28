"""Drones as read-only sources (L5b, docs/phase-l/design-l5.md §3.3) [SIM until the type is known].

* Staff ``/api/v1/staff/drones``: the rooms see their gouvernorat's drones (the central room all of them, row level
  security) with the last position and the camera's cone, the track of the last minutes, the work areas and no-fly
  zones, and the alerts, which an agent acknowledges. The operations manager registers a drone (a fixed "drone" stream
  whose publish token is shown once) and draws the zones.
* Internal ``GET /internal/drones/live`` and ``POST /internal/drones/telemetry``: the reader beside MediaMTX learns
  which drone streams are on air and relays their positions. Never routed by Caddy; guarded like the sensor readings.

There is no route that sends anything to a drone, and there never will be: the pilot alone flies it
(tests/test_drones.py fails if one appears).
"""

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session, get_system_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.drones import domain, schemas, service
from app.modules.drones.models import DroneAlert, DroneTelemetry, DroneZone
from app.modules.notify.service import _check_polygon, _polygon_wkt
from app.modules.reports.staff_router import READ_ROLES, WRITE_ROLES
from app.modules.sensors.gateway import Gateway
from app.modules.streams import service as streams
from app.modules.streams.domain import Source, StreamStatus
from app.modules.streams.models import LiveStream

router = APIRouter(prefix="/api/v1/staff/drones", tags=["drones"])
internal_router = APIRouter(include_in_schema=False)

Session = Annotated[AsyncSession, Depends(get_session)]
SystemSession = Annotated[AsyncSession, Depends(get_system_session)]
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
Writer = Annotated[Principal, Depends(require_roles(*WRITE_ROLES))]
Manager = Annotated[Principal, Depends(require_roles(Role.OPS_MANAGER))]
MAX_DRONES = 200
MAX_ZONES = 500
MAX_ALERTS = 200


def _now() -> datetime:
    return datetime.now(UTC)


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


def _telemetry(t: DroneTelemetry) -> schemas.Telemetry:
    return schemas.Telemetry(
        at=t.at,
        lat=t.lat,
        lon=t.lon,
        alt_m=t.alt_m,
        heading_deg=t.heading_deg,
        sensor_az_deg=t.sensor_az_deg,
        sensor_hfov_deg=t.sensor_hfov_deg,
        battery_pct=t.battery_pct,
        mode=t.mode,
    )


def _view(t: DroneTelemetry | None) -> list[list[float]] | None:
    if t is None or t.sensor_hfov_deg is None:
        return None
    # The camera's direction: the sensor's own azimuth when given (relative to the heading), else the heading.
    if t.sensor_az_deg is not None:
        bearing = ((t.heading_deg or 0.0) + t.sensor_az_deg) % 360
    elif t.heading_deg is not None:
        bearing = t.heading_deg
    else:
        return None
    return domain.wedge(t.lat, t.lon, bearing, t.sensor_hfov_deg, domain.camera_reach_m(t.alt_m))


def _out(stream: LiveStream, last: DroneTelemetry | None, open_alerts: int) -> schemas.DroneOut:
    return schemas.DroneOut(
        id=stream.id,
        label=stream.label or str(stream.id)[:8],
        gouvernorat_code=stream.gouvernorat_code,
        stream_status=stream.status,
        last=_telemetry(last) if last else None,
        camera_view=_view(last),
        open_alerts=open_alerts,
    )


async def _drone(session: AsyncSession, drone_id: uuid.UUID) -> LiveStream:
    stream = await session.get(LiveStream, drone_id)  # row level security: out of scope reads as missing
    if stream is None or stream.source != Source.DRONE.value:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return stream


async def _last(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, DroneTelemetry]:
    if not ids:
        return {}
    return {
        t.stream_id: t
        for t in await session.scalars(
            select(DroneTelemetry)
            .ext(distinct_on(DroneTelemetry.stream_id))
            .where(DroneTelemetry.stream_id.in_(ids))
            .order_by(DroneTelemetry.stream_id, DroneTelemetry.at.desc())
        )
    }


async def _open_alerts(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not ids:
        return {}
    rows = await session.execute(
        select(DroneAlert.stream_id, func.count())
        .where(DroneAlert.stream_id.in_(ids), DroneAlert.acknowledged_at.is_(None))
        .group_by(DroneAlert.stream_id)
    )
    return {stream_id: count for stream_id, count in rows}


@router.get("", response_model=schemas.DronePage)
async def list_drones(principal: Reader, session: Session) -> schemas.DronePage:
    rows = (
        await session.scalars(
            select(LiveStream)
            .where(LiveStream.source == Source.DRONE.value)
            .order_by(LiveStream.gouvernorat_code, LiveStream.label)
            .limit(MAX_DRONES)
        )
    ).all()
    ids = [s.id for s in rows]
    last, alerts = await _last(session, ids), await _open_alerts(session, ids)
    return schemas.DronePage(
        items=[_out(s, last.get(s.id), alerts.get(s.id, 0)) for s in rows], can_register=_can_manage(principal)
    )


@router.post("", response_model=schemas.DroneCreated, status_code=status.HTTP_201_CREATED)
async def register_drone(principal: Manager, session: Session, body: schemas.DroneIn) -> schemas.DroneCreated:
    """A drone of the room: its video is published to MediaMTX with the token shown once; nothing goes back to it."""
    code = _gouvernorat(principal, body.gouvernorat_code)
    actor = audit.actor_of(principal)
    stream, token = await streams.register_fixed(
        session, streams.FixedSource(Source.DRONE, body.label, code, None, None), actor
    )
    await audit.record(
        session,
        actor=actor,
        action="drone.create",
        target=f"stream:{stream.id}",
        details={"label": body.label},
        gouvernorats=[code],
    )
    out = schemas.DroneCreated(
        drone=_out(stream, None, 0),
        publish_token=token,
        publish_url_rtsp=streams.rtsp_publish_url(stream),
        publish_url_rtmp=streams.rtmp_publish_url(stream),
    )
    await session.commit()
    return out


@router.get("/alerts", response_model=list[schemas.AlertOut])
async def list_alerts(
    principal: Reader,
    session: Session,
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
    open_only: bool = False,
) -> list[schemas.AlertOut]:
    query = (
        select(DroneAlert, LiveStream.label, DroneZone.name)
        .join(LiveStream, LiveStream.id == DroneAlert.stream_id)
        .outerjoin(DroneZone, DroneZone.id == DroneAlert.zone_id)
        .where(DroneAlert.at >= _now() - timedelta(hours=hours))
        .order_by(DroneAlert.at.desc())
        .limit(MAX_ALERTS)
    )
    if open_only:
        query = query.where(DroneAlert.acknowledged_at.is_(None))
    return [
        schemas.AlertOut(
            id=a.id,
            drone_id=a.stream_id,
            drone_label=label or str(a.stream_id)[:8],
            at=a.at,
            kind=a.kind,
            zone_name=zone,
            detail=a.detail,
            acknowledged_by_name=a.acknowledged_by_name,
            acknowledged_at=a.acknowledged_at,
        )
        for a, label, zone in (await session.execute(query))
    ]


@router.post("/alerts/{alert_id}/ack", status_code=status.HTTP_204_NO_CONTENT)
async def acknowledge(principal: Writer, session: Session, alert_id: int) -> None:
    alert = await session.get(DroneAlert, alert_id)  # row level security: another room's drone reads as missing
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if alert.acknowledged_at is None:
        alert.acknowledged_by = audit.actor_of(principal)
        alert.acknowledged_by_name = audit.name_of(principal)
        alert.acknowledged_at = _now()
        await session.commit()


@router.get("/zones", response_model=list[schemas.ZoneOut])
async def list_zones(principal: Reader, session: Session) -> list[schemas.ZoneOut]:
    rows = await session.execute(
        select(DroneZone, func.ST_AsGeoJSON(DroneZone.area))
        .order_by(DroneZone.gouvernorat_code, DroneZone.kind, DroneZone.name)
        .limit(MAX_ZONES)
    )
    return [_zone(z, geo) for z, geo in rows]


def _zone(z: DroneZone, geojson: str) -> schemas.ZoneOut:
    ring: list[list[float]] = json.loads(geojson)["coordinates"][0]
    return schemas.ZoneOut(
        id=z.id,
        kind=z.kind,
        name=z.name,
        gouvernorat_code=z.gouvernorat_code,
        ring=ring,
        margin_m=z.margin_m,
        active=z.active,
        created_by_name=z.created_by_name,
        updated_at=z.updated_at,
    )


async def _area(session: AsyncSession, ring: list[list[float]]) -> str:
    polygon: dict[str, Any] = {"type": "Polygon", "coordinates": [ring]}
    wkt = _polygon_wkt(polygon)
    await _check_polygon(session, wkt)
    return wkt


async def _zone_of(session: AsyncSession, zone_id: uuid.UUID) -> schemas.ZoneOut:
    z, geo = (
        await session.execute(select(DroneZone, func.ST_AsGeoJSON(DroneZone.area)).where(DroneZone.id == zone_id))
    ).one()
    return _zone(z, geo)


@router.post("/zones", response_model=schemas.ZoneOut, status_code=status.HTTP_201_CREATED)
async def create_zone(principal: Manager, session: Session, body: schemas.ZoneIn) -> schemas.ZoneOut:
    code = _gouvernorat(principal, body.gouvernorat_code)
    actor = audit.actor_of(principal)
    zone = DroneZone(
        gouvernorat_code=code,
        kind=body.kind,
        name=body.name,
        area=await _area(session, body.ring),
        margin_m=body.margin_m,
        created_by=actor,
        created_by_name=audit.name_of(principal),
    )
    session.add(zone)
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action="drone.zone_create",
        target=f"drone_zone:{zone.id}",
        details={"kind": zone.kind, "name": zone.name},
        gouvernorats=[code],
    )
    out = await _zone_of(session, zone.id)
    await session.commit()
    return out


@router.put("/zones/{zone_id}", response_model=schemas.ZoneOut)
async def update_zone(
    principal: Manager, session: Session, zone_id: uuid.UUID, body: schemas.ZoneUpdate
) -> schemas.ZoneOut:
    zone = await session.get(DroneZone, zone_id)
    if zone is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if not _can_manage(principal, zone.gouvernorat_code):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
    zone.name, zone.margin_m, zone.active = body.name, body.margin_m, body.active
    zone.area = await _area(session, body.ring)
    zone.updated_at = _now()
    await session.flush()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="drone.zone_update",
        target=f"drone_zone:{zone.id}",
        details={"kind": zone.kind, "name": zone.name, "active": zone.active},
        gouvernorats=[zone.gouvernorat_code],
    )
    out = await _zone_of(session, zone.id)
    await session.commit()
    return out


@router.get("/{drone_id}/track", response_model=schemas.TrackOut)
async def track(
    principal: Reader,
    session: Session,
    drone_id: uuid.UUID,
    minutes: Annotated[int, Query(ge=1, le=domain.TRACK_MINUTES_MAX)] = 30,
) -> schemas.TrackOut:
    stream = await _drone(session, drone_id)
    rows = (
        await session.scalars(
            select(DroneTelemetry)
            .where(DroneTelemetry.stream_id == stream.id, DroneTelemetry.at >= _now() - timedelta(minutes=minutes))
            .order_by(DroneTelemetry.at.desc())
            .limit(2000)
        )
    ).all()
    return schemas.TrackOut(drone_id=stream.id, items=[_telemetry(t) for t in reversed(rows)])


# ---------------------------------------------------------------- the reader beside MediaMTX (read only)


@internal_router.get("/internal/drones/live", response_model=schemas.LiveDrones)
async def live(_: Gateway, session: SystemSession) -> schemas.LiveDrones:
    ids = await session.scalars(
        select(LiveStream.id).where(
            LiveStream.source == Source.DRONE.value, LiveStream.status == StreamStatus.LIVE.value
        )
    )
    return schemas.LiveDrones(items=list(ids))


@internal_router.post("/internal/drones/telemetry", response_model=schemas.TelemetryResult)
async def telemetry(_: Gateway, session: SystemSession, body: schemas.TelemetryIn) -> schemas.TelemetryResult:
    stream = await session.get(LiveStream, body.stream_id)
    if stream is None or stream.source != Source.DRONE.value:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_drone")
    out = await service.ingest(session, stream, body.points)
    await session.commit()
    return schemas.TelemetryResult(
        accepted=out.accepted,
        rejected=out.rejected,
        alerts=out.alerts,
    )
