"""Positions relayed by the reader beside MediaMTX, and the alerts they raise (L5b, design-l5.md §3.3).

Each point is checked on its own (time, not a replay). The newest moves the drone on the map. Every accepted point
is compared with the zones: outside every work area of the drone's gouvernorat, inside or within the margin of a
no-fly zone (of any gouvernorat: an airport near a border counts), or the battery crossing the low threshold. An alert
is not repeated for the same drone, kind and zone within the cool-down. Nothing is ever sent to the drone.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import emit
from app.modules.drones import domain, schemas
from app.modules.drones.models import DroneAlert, DroneTelemetry
from app.modules.settings import service as settings
from app.modules.streams.domain import LOCATION_EVENT_INTERVAL_S
from app.modules.streams.models import LiveStream
from app.modules.streams.service import _point

log = structlog.get_logger()

_ZONES = text(
    """
    SELECT z.id, z.kind, z.name, z.margin_m, z.gouvernorat_code,
           ST_Covers(z.area, p.pt) AS inside,
           ST_Distance(z.area, p.pt) AS distance_m
    FROM reports.drone_zone z,
         (SELECT CAST(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) AS geography) AS pt) p
    WHERE z.active AND ST_DWithin(z.area, p.pt, :nearby)
    """
)
_HAS_WORK = text(
    "SELECT EXISTS (SELECT 1 FROM reports.drone_zone WHERE active AND kind = 'work' AND gouvernorat_code = :g)"
)


@dataclass(slots=True)
class Outcome:
    accepted: int = 0
    rejected: dict[str, int] = field(default_factory=dict)
    alerts: list[str] = field(default_factory=list)


async def _recent(session: AsyncSession, stream_id: uuid.UUID, kind: str, zone_id: Any, at: datetime) -> bool:
    query = select(DroneAlert.id).where(
        DroneAlert.stream_id == stream_id,
        DroneAlert.kind == kind,
        DroneAlert.at > at - domain.ALERT_COOLDOWN,
        DroneAlert.at <= at + domain.ALERT_COOLDOWN,
    )
    query = query.where(DroneAlert.zone_id.is_(None) if zone_id is None else DroneAlert.zone_id == zone_id)
    return await session.scalar(query.limit(1)) is not None


async def _raise(
    session: AsyncSession,
    stream: LiveStream,
    kind: str,
    at: datetime,
    zone: Any | None,
    detail: dict[str, Any],
    out: Outcome,
) -> None:
    zone_id = zone.id if zone is not None else None
    if await _recent(session, stream.id, kind, zone_id, at):
        return
    alert = DroneAlert(
        stream_id=stream.id, gouvernorat_code=stream.gouvernorat_code, at=at, kind=kind, zone_id=zone_id, detail=detail
    )
    session.add(alert)
    await session.flush()
    out.alerts.append(kind)
    await emit(
        session,
        "drone.alert",
        {
            "id": alert.id,
            "drone_id": str(stream.id),
            "drone_label": stream.label,
            "gouvernorat_code": stream.gouvernorat_code,
            "kind": kind,
            "zone_name": zone.name if zone is not None else None,
            "at": at.isoformat(),
            "detail": detail,
        },
    )
    log.info("drone.alert", drone=str(stream.id), kind=kind)


async def _check(
    session: AsyncSession,
    stream: LiveStream,
    p: schemas.PointIn,
    at: datetime,
    battery_before: float | None,
    out: Outcome,
) -> None:
    where = {"lat": round(p.lat, 6), "lon": round(p.lon, 6)}
    zones = (
        await session.execute(
            _ZONES, {"lat": p.lat, "lon": p.lon, "nearby": await settings.threshold(session, "drones.nearby_m")}
        )
    ).all()
    for z in zones:
        if z.kind != "no_fly":
            continue
        if z.inside:
            await _raise(session, stream, "in_no_fly", at, z, where, out)
        elif z.distance_m <= z.margin_m:
            await _raise(session, stream, "near_no_fly", at, z, {**where, "distance_m": round(z.distance_m)}, out)
    if stream.gouvernorat_code is not None:
        own_work = [z for z in zones if z.kind == "work" and z.gouvernorat_code == stream.gouvernorat_code]
        if not any(z.inside for z in own_work) and await session.scalar(_HAS_WORK, {"g": stream.gouvernorat_code}):
            await _raise(session, stream, "left_work_area", at, None, where, out)
    if domain.battery_alert(battery_before, p.battery_pct):
        await _raise(session, stream, "low_battery", at, None, {**where, "battery_pct": p.battery_pct}, out)


async def ingest(
    session: AsyncSession, stream: LiveStream, points: list[schemas.PointIn], now: datetime | None = None
) -> Outcome:
    """Store the valid points of a batch (system scope), move the drone, and raise the alerts they call for."""
    now = now or datetime.now(UTC)
    out = Outcome()
    last = await session.scalar(
        select(DroneTelemetry).where(DroneTelemetry.stream_id == stream.id).order_by(DroneTelemetry.at.desc()).limit(1)
    )
    battery = last.battery_pct if last else None
    newest: tuple[datetime, schemas.PointIn] | None = (last.at, None) if last else None  # type: ignore[assignment]
    for p in sorted(points, key=lambda q: q.at):
        at = p.at.astimezone(UTC)
        if abs(at - now) > domain.CLOCK_SKEW:
            out.rejected["bad_time"] = out.rejected.get("bad_time", 0) + 1
            continue
        stored = await session.scalar(
            insert(DroneTelemetry)
            .values(stream_id=stream.id, at=at, received_at=now, **p.model_dump(exclude={"at"}))
            .on_conflict_do_nothing(constraint="uq_drone_telemetry")
            .returning(DroneTelemetry.id)
        )
        if stored is None:
            out.rejected["replay"] = out.rejected.get("replay", 0) + 1
            continue
        out.accepted += 1
        await _check(session, stream, p, at, battery, out)
        if p.battery_pct is not None:
            battery = p.battery_pct
        if newest is None or at > newest[0]:
            newest = (at, p)
    if newest is not None and newest[1] is not None:
        at, p = newest
        stream.last_location = _point(p.lat, p.lon)
        stream.last_location_at = at
        payload = {"drone_id": str(stream.id), "gouvernorat_code": stream.gouvernorat_code, **p.model_dump(mode="json")}
        await emit(session, "drone.telemetry", payload)
        if stream.location_event_at is None or now - stream.location_event_at >= timedelta(
            seconds=LOCATION_EVENT_INTERVAL_S
        ):
            # The stream wall moves the drone like any fixed source.
            stream.location_event_at = now
            await emit(
                session,
                "stream.location",
                {
                    "stream_id": str(stream.id),
                    "report_id": None,
                    "gouvernorat_code": stream.gouvernorat_code,
                    "lat": p.lat,
                    "lon": p.lon,
                    "accuracy_m": None,
                    "at": at.isoformat(),
                },
            )
    if out.rejected:
        log.warning("drone.points_rejected", rejected=out.rejected, accepted=out.accepted)
    return out
