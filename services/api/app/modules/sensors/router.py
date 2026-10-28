"""Sensors of the local network (L5b, docs/phase-l/design-l5.md §3.0 and §3.1) [SIM until a real source is named].

* Staff ``/api/v1/staff/sensors``: the rooms see their gouvernorat's sensors (the central room all of them, row level
  security); the operations manager registers them, sets their thresholds, and rotates their signing key. The key is
  shown once, when created or rotated, and is never logged.
* Internal ``POST /internal/sensors/readings``: the gateway beside MediaMTX relays signed readings. Never routed by
  Caddy; answers 404 while SENSOR_GATEWAY_TOKEN is unset, and only to an address of SENSOR_GATEWAY_NETWORKS.
"""

import hmac
import ipaddress
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session, get_system_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.reports.staff_router import READ_ROLES
from app.modules.sensors import domain, schemas, service
from app.modules.sensors.domain import Kind
from app.modules.sensors.models import SensorDevice, SensorReading

log = structlog.get_logger()
router = APIRouter(prefix="/api/v1/staff/sensors", tags=["sensors"])
internal_router = APIRouter(include_in_schema=False)

Session = Annotated[AsyncSession, Depends(get_session)]
SystemSession = Annotated[AsyncSession, Depends(get_system_session)]
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
Manager = Annotated[Principal, Depends(require_roles(Role.OPS_MANAGER))]
MAX_SENSORS = 2000
MAX_HOURS = 168


def _now() -> datetime:
    return datetime.now(UTC)


def _out(d: SensorDevice, now: datetime) -> schemas.SensorOut:
    return schemas.SensorOut(
        id=d.id,
        code=d.code,
        name=d.name,
        kind=Kind(d.kind),
        unit=domain.UNITS[Kind(d.kind)],
        gouvernorat_code=d.gouvernorat_code,
        lat=d.lat,
        lon=d.lon,
        provider=d.provider,
        watch_threshold=d.watch_threshold,
        alarm_threshold=d.alarm_threshold,
        silent_after_min=d.silent_after_min,
        enabled=d.enabled,
        simulated=d.simulated,
        last_value=d.last_value,
        last_at=d.last_at,
        state=domain.state_of(
            enabled=d.enabled, level=d.level, last_at=d.last_at, silent_after_min=d.silent_after_min, now=now
        ),
        level_since=d.level_since,
        created_by_name=d.created_by_name,
        updated_at=d.updated_at,
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


async def _load(session: AsyncSession, sensor_id: uuid.UUID) -> SensorDevice:
    device = await session.get(SensorDevice, sensor_id)  # row level security: out of scope reads as missing
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return device


def _check_range(kind: Kind, *values: float) -> None:
    low, high = domain.RANGES[kind]
    if any(not low <= v <= high for v in values):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "threshold_out_of_range")


@router.get("", response_model=schemas.SensorPage)
async def list_sensors(principal: Reader, session: Session) -> schemas.SensorPage:
    rows = (
        await session.scalars(
            select(SensorDevice).order_by(SensorDevice.gouvernorat_code, SensorDevice.name).limit(MAX_SENSORS)
        )
    ).all()
    now = _now()
    return schemas.SensorPage(items=[_out(d, now) for d in rows], can_manage=_can_manage(principal))


@router.post("", response_model=schemas.SensorKeyOut, status_code=status.HTTP_201_CREATED)
async def create_sensor(principal: Manager, session: Session, body: schemas.SensorIn) -> schemas.SensorKeyOut:
    code = _gouvernorat(principal, body.gouvernorat_code)
    _check_range(body.kind, body.watch_threshold, body.alarm_threshold)
    taken = await session.scalar(
        select(func.count()).select_from(SensorDevice).where(func.lower(SensorDevice.code) == body.code.lower())
    )
    if taken:
        raise HTTPException(status.HTTP_409_CONFLICT, "sensor_code_taken")
    key = domain.new_key()
    device = SensorDevice(
        code=body.code,
        name=body.name,
        kind=body.kind.value,
        gouvernorat_code=code,
        lat=body.lat,
        lon=body.lon,
        provider=body.provider,
        watch_threshold=body.watch_threshold,
        alarm_threshold=body.alarm_threshold,
        silent_after_min=body.silent_after_min,
        simulated=body.simulated,
        key_enc=service.seal_key(key),
        created_by=audit.actor_of(principal),
        created_by_name=audit.name_of(principal),
    )
    session.add(device)
    try:
        await session.flush()
    except IntegrityError as exc:  # another room took the code meanwhile (not visible through row level security)
        raise HTTPException(status.HTTP_409_CONFLICT, "sensor_code_taken") from exc
    await session.refresh(device)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="sensor.create",
        target=str(device.id),
        details={"code": device.code, "kind": device.kind, "simulated": device.simulated},
        gouvernorats=[code],
    )
    out = schemas.SensorKeyOut(sensor=_out(device, _now()), key=key)
    await session.commit()
    return out


@router.put("/{sensor_id}", response_model=schemas.SensorOut)
async def update_sensor(
    principal: Manager, session: Session, sensor_id: uuid.UUID, body: schemas.SensorUpdate
) -> schemas.SensorOut:
    device = await _load(session, sensor_id)
    if not _can_manage(principal, device.gouvernorat_code):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
    _check_range(Kind(device.kind), body.watch_threshold, body.alarm_threshold)
    before = {"watch": device.watch_threshold, "alarm": device.alarm_threshold, "enabled": device.enabled}
    for field, value in body.model_dump().items():
        setattr(device, field, value)
    device.updated_at = _now()
    if device.last_value is not None:
        # New thresholds take effect at once; a level they raise waits for the next reading to suggest an alert.
        level = domain.level_of(device.last_value, device.watch_threshold, device.alarm_threshold)
        if level != device.level:
            device.level, device.level_since = level, device.updated_at
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="sensor.update",
        target=str(device.id),
        details={
            "before": before,
            "after": {"watch": device.watch_threshold, "alarm": device.alarm_threshold, "enabled": device.enabled},
        },
        gouvernorats=[device.gouvernorat_code],
    )
    out = _out(device, _now())
    await session.commit()
    return out


@router.post("/{sensor_id}/key", response_model=schemas.SensorKeyOut)
async def rotate_key(principal: Manager, session: Session, sensor_id: uuid.UUID) -> schemas.SensorKeyOut:
    """A new signing key, shown once; readings signed with the old one are refused from now on."""
    device = await _load(session, sensor_id)
    if not _can_manage(principal, device.gouvernorat_code):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
    key = domain.new_key()
    device.key_enc, device.key_version, device.updated_at = service.seal_key(key), device.key_version + 1, _now()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="sensor.key_rotate",
        target=str(device.id),
        details={"code": device.code, "key_version": device.key_version},
        gouvernorats=[device.gouvernorat_code],
    )
    out = schemas.SensorKeyOut(sensor=_out(device, _now()), key=key)
    await session.commit()
    return out


@router.get("/{sensor_id}/readings", response_model=schemas.ReadingsOut)
async def readings(
    principal: Reader,
    session: Session,
    sensor_id: uuid.UUID,
    hours: Annotated[int, Query(ge=1, le=MAX_HOURS)] = 24,
) -> schemas.ReadingsOut:
    device = await _load(session, sensor_id)
    rows = (
        await session.scalars(
            select(SensorReading)
            .where(SensorReading.sensor_id == device.id, SensorReading.at >= _now() - timedelta(hours=hours))
            .order_by(SensorReading.at)
            .limit(5000)
        )
    ).all()
    return schemas.ReadingsOut(
        sensor_id=device.id,
        unit=domain.UNITS[Kind(device.kind)],
        watch_threshold=device.watch_threshold,
        alarm_threshold=device.alarm_threshold,
        items=[schemas.ReadingOut(at=r.at, value=r.value) for r in rows],
    )


# ---------------------------------------------------------------- the gateway beside MediaMTX


def _on_local_network(host: str | None) -> bool:
    if host is None:
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(address in ipaddress.ip_network(n, strict=False) for n in get_settings().sensor_gateway_networks)


@internal_router.post("/internal/sensors/readings", response_model=schemas.IngestOut)
async def ingest(
    request: Request,
    session: SystemSession,
    body: schemas.ReadingsIn,
    x_gateway_token: Annotated[str, Header()] = "",
) -> schemas.IngestOut:
    expected = get_settings().sensor_gateway_token
    if expected is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    host = request.client.host if request.client else None
    if not _on_local_network(host):
        log.warning("sensor.gateway_outside_network")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "outside_local_network")
    if not x_gateway_token or not hmac.compare_digest(x_gateway_token.encode(), expected.get_secret_value().encode()):
        log.warning("sensor.gateway_bad_token")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad_token")
    outcome = await service.ingest(
        session, [service.RawReading(sensor=r.sensor, at=r.at, value=r.value, sig=r.sig) for r in body.readings]
    )
    await session.commit()
    return schemas.IngestOut(
        accepted=outcome.accepted,
        rejected=outcome.rejected or {},
        suggestions=outcome.suggestions,
    )
