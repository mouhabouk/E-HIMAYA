"""Readings relayed by the gateway beside MediaMTX (L5b, design-l5.md §3.0 and §3.1): check, store, rate, suggest.

Each reading is checked on its own (sensor known and enabled, signature, time, plausible value, not a replay), so a
bad one never sinks the batch. A sensor whose level rises to "watch" or "alarm" puts a suggestion in the alert centre
(``weather.alert_suggestion``); an agent reviews it and nothing reaches a citizen outside the two-person path.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import get_cipher
from app.core.events import emit
from app.modules.geo.models import Gouvernorat
from app.modules.sensors import domain
from app.modules.sensors.domain import Kind
from app.modules.sensors.models import SensorDevice, SensorReading
from app.modules.weather.models import AlertSuggestion
from app.modules.weather.service import ACTIVE_STATUSES, suggestion_out

log = structlog.get_logger()
SUGGESTION_HOURS = 6


@dataclass(frozen=True, slots=True)
class RawReading:
    sensor: str
    at: str
    value: str
    sig: str


@dataclass(slots=True)
class Outcome:
    accepted: int = 0
    rejected: dict[str, int] | None = None
    suggestions: int = 0

    def refuse(self, reason: str) -> None:
        self.rejected = self.rejected or {}
        self.rejected[reason] = self.rejected.get(reason, 0) + 1


def key_of(device: SensorDevice) -> str:
    return get_cipher().decrypt(device.key_enc, context=domain.KEY_CONTEXT)


def seal_key(key: str) -> bytes:
    return get_cipher().encrypt(key, context=domain.KEY_CONTEXT)


async def ingest(session: AsyncSession, readings: list[RawReading], now: datetime | None = None) -> Outcome:
    """Store the valid readings of a batch (system scope) and raise the suggestions their levels call for."""
    now = now or datetime.now(UTC)
    out = Outcome()
    codes = sorted({r.sensor for r in readings})
    devices = {d.code: d for d in await session.scalars(select(SensorDevice).where(SensorDevice.code.in_(codes)))}
    keys: dict[str, str] = {}
    latest: dict[uuid.UUID, tuple[datetime, float]] = {}
    for r in readings:
        device = devices.get(r.sensor)
        if device is None or not device.enabled:
            out.refuse("unknown_sensor")
            continue
        if device.code not in keys:
            keys[device.code] = key_of(device)
        if not domain.signature_valid(keys[device.code], r.sensor, r.at, r.value, r.sig):
            out.refuse("bad_signature")
            continue
        at = domain.parse_at(r.at, now)
        if at is None:
            out.refuse("bad_time")
            continue
        value = domain.parse_value(r.value, Kind(device.kind))
        if value is None:
            out.refuse("bad_value")
            continue
        stored = await session.scalar(
            insert(SensorReading)
            .values(sensor_id=device.id, at=at, value=value, received_at=now)
            .on_conflict_do_nothing(constraint="uq_sensor_reading")
            .returning(SensorReading.id)
        )
        if stored is None:
            out.refuse("replay")
            continue
        out.accepted += 1
        if device.id not in latest or at > latest[device.id][0]:
            latest[device.id] = (at, value)
    by_id = {d.id: d for d in devices.values()}
    for sensor_id, (at, value) in latest.items():
        device = by_id[sensor_id]
        if device.last_at is not None and at <= device.last_at:
            continue
        before = device.level
        after = domain.level_of(value, device.watch_threshold, device.alarm_threshold)
        device.last_value, device.last_at, device.updated_at = value, at, now
        if after != before:
            device.level, device.level_since = after, now
        if domain.rises(before, after) and domain.is_fresh(at, now) and await _suggest(session, device, value, now):
            out.suggestions += 1
        await emit(
            session,
            "sensor.reading",
            {
                "sensor_id": str(device.id),
                "gouvernorat_code": device.gouvernorat_code,
                "value": value,
                "at": at.isoformat(),
                "level": device.level,
            },
        )
    if out.rejected:
        # Counts by reason only: never a key, a signature or a raw body.
        log.warning("sensor.readings_rejected", rejected=out.rejected, accepted=out.accepted)
    return out


async def _suggest(session: AsyncSession, device: SensorDevice, value: float, now: datetime) -> bool:
    kind = Kind(device.kind)
    metric = domain.METRICS[kind]
    severity = domain.SEVERITY[device.level]
    pending = await session.scalars(
        select(AlertSuggestion).where(
            AlertSuggestion.metric == metric,
            AlertSuggestion.status.in_(ACTIVE_STATUSES),
            AlertSuggestion.valid_until > now,
            AlertSuggestion.evidence["sensor_id"].astext == str(device.id),
        )
    )
    if any(s.severity == "high" or s.severity == severity for s in pending):
        return False
    gouvernorat = await session.get(Gouvernorat, device.gouvernorat_code)
    threshold = device.alarm_threshold if device.level == "alarm" else device.watch_threshold
    title, body = _texts(kind, device, value, gouvernorat)
    evidence: dict[str, Any] = {
        "source": "sensor",
        "sensor_id": str(device.id),
        "sensor_code": device.code,
        "sensor_name": device.name,
        "provider": device.provider,
        "level": device.level,
        "metric": metric,
        "threshold": threshold,
        "unit": domain.UNITS[kind],
        "max_value": value,
        "peak_point": {"lat": device.lat, "lon": device.lon},
        metric: value,
    }
    suggestion = AlertSuggestion(
        id=uuid.uuid4(),
        metric=metric,
        gouvernorat_codes=[device.gouvernorat_code],
        hazard=domain.HAZARDS[kind],
        severity=severity,
        title=title,
        body=body,
        evidence=evidence,
        valid_from=now,
        valid_until=now + timedelta(hours=SUGGESTION_HOURS),
        simulated=device.simulated,
    )
    session.add(suggestion)
    await session.flush()
    await session.refresh(suggestion)
    await emit(
        session,
        "weather.suggestion",
        {"suggestion_id": str(suggestion.id), "suggestion": suggestion_out(suggestion).model_dump(mode="json")},
    )
    return True


def _texts(
    kind: Kind, device: SensorDevice, value: float, gouvernorat: Gouvernorat | None
) -> tuple[dict[str, str], dict[str, str]]:
    """Prefilled title and body; the editor reviews them before anything is sent."""
    where_ar = gouvernorat.name_ar if gouvernorat else ""
    where_fr = gouvernorat.name_fr if gouvernorat else ""
    shown = f"{value:g}"
    if kind is Kind.RAIN_1H:
        return (
            {"ar": "أمطار غزيرة مقيسة", "fr": "Fortes pluies mesurées", "en": "Heavy rain measured"},
            {
                "ar": f"سجّل مقياس المطر «{device.name}» {shown} مم في ساعة ({where_ar}). "
                "لا تعبروا الأودية ومجاري المياه، وابتعدوا عن المناطق المنخفضة.",
                "fr": f"Le pluviomètre « {device.name} » a mesuré {shown} mm en une heure ({where_fr}). "
                "Ne traversez pas les oueds ni les routes inondées, éloignez-vous des zones basses.",
                "en": f"The rain gauge “{device.name}” measured {shown} mm in one hour ({where_fr}). "
                "Do not cross wadis or flooded roads, keep away from low-lying areas.",
            },
        )
    if kind is Kind.WATER_LEVEL:
        return (
            {"ar": "ارتفاع منسوب المياه", "fr": "Montée des eaux", "en": "Rising water"},
            {
                "ar": f"بلغ منسوب المياه عند «{device.name}» {shown} م ({where_ar}). "
                "ابتعدوا عن ضفاف الأودية والسدود ولا تعبروا الطرق المغمورة.",
                "fr": f"Le niveau d'eau à « {device.name} » atteint {shown} m ({where_fr}). "
                "Éloignez-vous des berges et des barrages, ne traversez pas les routes inondées.",
                "en": f"The water level at “{device.name}” reached {shown} m ({where_fr}). "
                "Keep away from riverbanks and dams, do not cross flooded roads.",
            },
        )
    return (
        {"ar": "حرارة مرتفعة مقيسة", "fr": "Forte chaleur mesurée", "en": "High temperature measured"},
        {
            "ar": f"سجّل الحساس «{device.name}» {shown} درجة ({where_ar}). "
            "اشربوا الماء بانتظام وتجنّبوا الشمس في منتصف النهار، وانتبهوا لكبار السن والأطفال.",
            "fr": f"Le capteur « {device.name} » a mesuré {shown} °C ({where_fr}). Buvez régulièrement, évitez "
            "le soleil en milieu de journée, veillez sur les personnes âgées et les enfants.",
            "en": f"The sensor “{device.name}” measured {shown} °C ({where_fr}). Drink regularly, avoid "
            "the midday sun, look after older people and children.",
        },
    )
