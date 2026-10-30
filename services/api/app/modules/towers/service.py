"""Events relayed by the gateway beside MediaMTX from the edge computers of the watch towers (L5b, design-l5.md §3.2).

An event is checked on its own (tower known, frame a JPEG, signature, time, label, confidence, 3 of 5 frames, not a
replay). An accepted one is kept with its frame beside the camera's stream (``reports.media`` and
``reports.stream_detection``, like the server's own detector), and becomes a suggestion in the alert centre and a
``stream.alert`` on the live feed. Never an automatic report: the room decides, with the live picture in front of it.
"""

import base64
import binascii
import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import get_cipher
from app.core.events import emit
from app.core.storage import get_store
from app.modules.geo.models import Gouvernorat
from app.modules.reports.models import Media
from app.modules.settings import service as settings
from app.modules.streams.models import LiveStream, StreamDetection
from app.modules.towers import domain
from app.modules.towers.models import CameraTower, TowerEvent
from app.modules.weather.models import AlertSuggestion
from app.modules.weather.service import ACTIVE_STATUSES, suggestion_out

log = structlog.get_logger()
FRAME_MAX_BYTES = 2 * 1024 * 1024
SEVERITY = {"fire": "high", "smoke": "medium"}


@dataclass(frozen=True, slots=True)
class RawEvent:
    tower: str
    at: str
    label: str
    confidence: str
    hits: str
    frames: str
    model: str
    frame_jpeg_b64: str
    sig: str


@dataclass(frozen=True, slots=True)
class Result:
    accepted: bool
    reason: str | None = None
    suggestion: bool = False


def key_of(tower: CameraTower) -> str:
    return get_cipher().decrypt(tower.key_enc, context=domain.KEY_CONTEXT)


def seal_key(key: str) -> bytes:
    return get_cipher().encrypt(key, context=domain.KEY_CONTEXT)


def _frame(raw: str) -> bytes | None:
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        return None
    if not data or len(data) > FRAME_MAX_BYTES or not data.startswith(b"\xff\xd8\xff"):
        return None
    return data


def _refuse(reason: str) -> Result:
    # The reason only: never a key, a signature or the frame.
    log.warning("tower.event_rejected", reason=reason)
    return Result(accepted=False, reason=reason)


async def ingest(session: AsyncSession, raw: RawEvent, now: datetime | None = None) -> Result:
    """Check and keep one event (system scope); suggest an alert unless one for this tower is still open."""
    now = now or datetime.now(UTC)
    tower = await session.scalar(select(CameraTower).where(CameraTower.code == raw.tower))
    if tower is None:
        return _refuse("unknown_tower")
    frame = _frame(raw.frame_jpeg_b64) if raw.frame_jpeg_b64 else None
    if raw.frame_jpeg_b64 and frame is None:
        return _refuse("bad_frame")
    sha = hashlib.sha256(frame).hexdigest() if frame else ""
    fields = (raw.tower, raw.at, raw.label, raw.confidence, raw.hits, raw.frames, sha)
    if not domain.signature_valid(key_of(tower), raw.sig, *fields):
        return _refuse("bad_signature")
    # A detection is live or nothing: one that comes late is refused, unlike a sensor's reading.
    at = domain.parse_at(raw.at, now, max_age=domain.CLOCK_SKEW)
    if at is None:
        return _refuse("bad_time")
    confidence = domain.parse_confidence(raw.confidence)
    if raw.label not in domain.LABELS or confidence is None:
        return _refuse("bad_value")
    counts = domain.parse_confirmation(raw.hits, raw.frames)
    if counts is None:
        return _refuse("not_confirmed")
    if confidence < get_settings().vision_min_confidence:
        return _refuse("low_confidence")
    model = raw.model or None
    event_id = await session.scalar(
        insert(TowerEvent)
        .values(
            stream_id=tower.stream_id,
            at=at,
            label=raw.label,
            confidence=confidence,
            hits=counts[0],
            frames=counts[1],
            model=model,
            received_at=now,
        )
        .on_conflict_do_nothing(constraint="uq_tower_event")
        .returning(TowerEvent.id)
    )
    if event_id is None:
        return _refuse("replay")
    event = await session.get(TowerEvent, event_id)
    assert event is not None
    stream = await session.get(LiveStream, tower.stream_id)
    assert stream is not None
    media = await _store_frame(session, tower, frame, raw.label, confidence, model) if frame else None
    session.add(
        StreamDetection(
            stream_id=stream.id,
            at=at,
            label=raw.label,
            confidence=confidence,
            model=f"edge:{model}" if model else "edge",
            confirmed=True,
        )
    )
    if raw.label == "fire":
        stream.max_fire_confidence = max(stream.max_fire_confidence or 0.0, confidence)
    else:
        stream.max_smoke_confidence = max(stream.max_smoke_confidence or 0.0, confidence)
    if tower.last_event_at is None or at > tower.last_event_at:
        tower.last_event_at = at
    event.media_id = media.id if media else None
    suggestion = await _suggest(session, tower, raw.label, confidence, counts, media, now)
    event.suggestion_id = suggestion.id if suggestion else None
    await session.flush()
    if suggestion is not None:
        await emit(
            session,
            "stream.alert",
            {
                "stream_id": str(stream.id),
                "label": raw.label,
                "confidence": round(confidence, 3),
                "report_id": None,
                "gouvernorat_code": tower.gouvernorat_code,
                "media_id": str(media.id) if media else None,
                "simulated": tower.simulated,
                "at": at.isoformat(),
            },
        )
    log.info("tower.event", tower=tower.code, label=raw.label, suggestion=suggestion is not None)
    return Result(accepted=True, suggestion=suggestion is not None)


async def _store_frame(
    session: AsyncSession, tower: CameraTower, frame: bytes, label: str, confidence: float, model: str | None
) -> Media:
    key = f"vision/{tower.stream_id}/{uuid.uuid4().hex}.jpg"
    await get_store().put(key, frame, "image/jpeg")
    media = Media(
        report_id=None,
        stream_id=tower.stream_id,
        kind="image",
        object_key=key,
        sha256=hashlib.sha256(frame).hexdigest(),
        bytes=len(frame),
        content_type="image/jpeg",
        verified_type="image/jpeg",
        status="stored",
        stored_at=datetime.now(UTC),
        analysis={"source": "edge", "tower": tower.code, "label": label, "confidence": confidence, "model": model},
    )
    session.add(media)
    await session.flush()
    return media


async def _suggest(
    session: AsyncSession,
    tower: CameraTower,
    label: str,
    confidence: float,
    counts: tuple[int, int],
    media: Media | None,
    now: datetime,
) -> AlertSuggestion | None:
    metric = domain.METRICS[label]
    severity = SEVERITY[label]
    open_ = await session.scalars(
        select(AlertSuggestion).where(
            AlertSuggestion.metric.in_(tuple(domain.METRICS.values())),
            AlertSuggestion.status.in_(ACTIVE_STATUSES),
            AlertSuggestion.valid_until > now,
            AlertSuggestion.evidence["tower_id"].astext == str(tower.stream_id),
        )
    )
    # One open suggestion per tower: smoke then fire raises it, a second fire does not repeat it.
    if any(s.severity == "high" or s.severity == severity for s in open_):
        return None
    gouvernorat = await session.get(Gouvernorat, tower.gouvernorat_code)
    stream = await session.get(LiveStream, tower.stream_id)
    name = stream.label if stream and stream.label else tower.code
    title, body = _texts(label, name, gouvernorat)
    evidence: dict[str, Any] = {
        "source": "tower",
        "tower_id": str(tower.stream_id),
        "tower_code": tower.code,
        "tower_name": name,
        "label": label,
        "metric": metric,
        "confidence": round(confidence, 3),
        "hits": counts[0],
        "frames": counts[1],
        "media_id": str(media.id) if media else None,
        "bearing_deg": tower.bearing_deg,
        "fov_deg": tower.fov_deg,
        "range_m": tower.range_m,
        "peak_point": {"lat": tower.lat, "lon": tower.lon},
        "max_value": round(confidence, 3),
        metric: round(confidence, 3),
    }
    suggestion = AlertSuggestion(
        id=uuid.uuid4(),
        metric=metric,
        gouvernorat_codes=[tower.gouvernorat_code],
        hazard="forest_fire",
        severity=severity,
        title=title,
        body=body,
        evidence=evidence,
        valid_from=now,
        valid_until=now + timedelta(hours=await settings.threshold(session, "towers.suggestion_hours")),
        simulated=tower.simulated,
    )
    session.add(suggestion)
    await session.flush()
    await session.refresh(suggestion)
    await emit(
        session,
        "weather.suggestion",
        {"suggestion_id": str(suggestion.id), "suggestion": suggestion_out(suggestion).model_dump(mode="json")},
    )
    return suggestion


def _texts(label: str, name: str, gouvernorat: Gouvernorat | None) -> tuple[dict[str, str], dict[str, str]]:
    """Prefilled title and body; the room checks the live picture and the editor reviews them before any send."""
    where_ar = gouvernorat.name_ar if gouvernorat else ""
    where_fr = gouvernorat.name_fr if gouvernorat else ""
    if label == "fire":
        return (
            {
                "ar": "حريق رصده برج مراقبة",
                "fr": "Feu repéré par une tour de guet",
                "en": "Fire spotted by a watch tower",
            },
            {
                "ar": f"رصد برج المراقبة «{name}» نارا ({where_ar}). ابتعدوا عن الغابة، ولا تقتربوا من الدخان، "
                "واتبعوا تعليمات الحماية المدنية.",
                "fr": f"La tour de guet « {name} » a repéré un feu ({where_fr}). Éloignez-vous de la forêt, "
                "n’approchez pas de la fumée et suivez les consignes de la Protection civile.",
                "en": f"The watch tower “{name}” spotted a fire ({where_fr}). Keep away from the forest, do not "
                "approach the smoke and follow the Civil Protection’s instructions.",
            },
        )
    return (
        {
            "ar": "دخان رصده برج مراقبة",
            "fr": "Fumée repérée par une tour de guet",
            "en": "Smoke spotted by a watch tower",
        },
        {
            "ar": f"رصد برج المراقبة «{name}» دخانا ({where_ar}). ابتعدوا عن مصدر الدخان واتبعوا تعليمات "
            "الحماية المدنية.",
            "fr": f"La tour de guet « {name} » a repéré de la fumée ({where_fr}). Éloignez-vous de la fumée et "
            "suivez les consignes de la Protection civile.",
            "en": f"The watch tower “{name}” spotted smoke ({where_fr}). Keep away from the smoke and follow the "
            "Civil Protection’s instructions.",
        },
    )
