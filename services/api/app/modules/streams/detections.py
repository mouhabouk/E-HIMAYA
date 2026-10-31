"""Vision detections: storage, 3-of-5 confirmation, and what a confirmed fire or smoke changes.

A frame result arrives from the vision service (POST /internal/vision/detections). Detections under
VISION_MIN_CONFIDENCE are dropped. The stream keeps its last 5 analysed frames; a fire or smoke at or above
VISION_ALERT_CONFIDENCE in 3 of them is *confirmed*:

* the detection rows of the confirming frame are flagged ``confirmed`` (the ``vision_fire`` input of the priority
  score, ``ai.scoring``), and the linked report is re-scored;
* the frame (when sent) is stored as ``reports.media(kind=image, analysis.source="vision")``;
* a ``vision_alert`` entry is added to the incident timeline when the report belongs to one;
* ``stream.alert`` is pushed on the live feed.

Nothing is ever sent to the public: the decision stays with a human (FR-C-11). An uploaded report image is judged on
its own (no frame series): a fire or smoke at the alert threshold in it is confirmed at once.
"""

import base64
import binascii
import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.events import emit
from app.core.storage import get_store
from app.modules.ai import pipeline
from app.modules.ops.models import TimelineEvent
from app.modules.reports.models import Media, Report
from app.modules.streams import schemas
from app.modules.streams.domain import ALERT_LABELS, CONFIRM_FRAMES, CONFIRM_HITS, VISION_LABELS, Source, StreamStatus
from app.modules.streams.models import LiveStream, StreamDetection

log = structlog.get_logger()

FRAME_MAX_BYTES = 2 * 1024 * 1024
FRAME_PREFIX = "vision/"


def _clean_boxes(boxes: list[list[float]]) -> list[list[float]]:
    """Boxes normalised to 0..1 (x1, y1, x2, y2[, conf]); anything else is dropped."""
    cleaned: list[list[float]] = []
    for box in boxes:
        if all(0.0 <= v <= 1.0 for v in box) and box[0] <= box[2] and box[1] <= box[3]:
            cleaned.append([round(float(v), 4) for v in box])
    return cleaned


def kept(detections: list[schemas.DetectionIn]) -> list[schemas.DetectionIn]:
    threshold = get_settings().vision_min_confidence
    return [d for d in detections if d.label in VISION_LABELS and d.confidence >= threshold]


def _frame_entry(at: datetime, detections: list[schemas.DetectionIn]) -> dict[str, Any]:
    entry: dict[str, Any] = {"at": at.isoformat()}
    for label in ALERT_LABELS:
        entry[label] = max((d.confidence for d in detections if d.label == label), default=0.0)
    return entry


def confirmed_labels(frames: list[dict[str, Any]], alert: float) -> dict[str, float]:
    """Labels confirmed by the newest frame: at the alert threshold in it and in CONFIRM_HITS of the window."""
    window = frames[-CONFIRM_FRAMES:]
    if not window:
        return {}
    newest = window[-1]
    out: dict[str, float] = {}
    for label in ALERT_LABELS:
        hits = sum(1 for f in window if float(f.get(label) or 0.0) >= alert)
        if float(newest.get(label) or 0.0) >= alert and hits >= CONFIRM_HITS:
            out[label] = float(newest[label])
    return out


def _cooled_down(stream: LiveStream, label: str, at: datetime, cooldown_s: int) -> bool:
    last = (stream.vision_alerts or {}).get(label)
    if not last:
        return True
    try:
        return at - datetime.fromisoformat(last) >= timedelta(seconds=cooldown_s)
    except ValueError:
        return True


def _decode_frame(frame_b64: str | None) -> bytes | None:
    if not frame_b64:
        return None
    try:
        data = base64.b64decode(frame_b64, validate=True)
    except (binascii.Error, ValueError):
        return None
    if len(data) > FRAME_MAX_BYTES or not data.startswith(b"\xff\xd8\xff"):
        return None
    return data


async def _store_frame(
    session: AsyncSession, stream: LiveStream, frame: bytes, label: str, confidence: float, model: str
) -> Media:
    key = f"{FRAME_PREFIX}{stream.id}/{uuid.uuid4().hex}.jpg"
    await get_store().put(key, frame, "image/jpeg")
    now = datetime.now(UTC)
    media = Media(
        report_id=stream.report_id,
        stream_id=stream.id,
        kind="image",
        object_key=key,
        sha256=hashlib.sha256(frame).hexdigest(),
        bytes=len(frame),
        content_type="image/jpeg",
        verified_type="image/jpeg",
        status="stored",
        stored_at=now,
        analysis={"source": "vision", "label": label, "confidence": confidence, "model": model},
    )
    session.add(media)
    await session.flush()
    return media


async def record_frame(session: AsyncSession, stream: LiveStream, body: schemas.DetectionsIn) -> list[str]:
    """Store one analysed frame of a locked, live stream. Returns the labels it alerted (confirmed, cooled down)."""
    settings = get_settings()
    detections = kept(body.detections)
    at = body.at.astimezone(UTC)
    for d in detections:
        session.add(
            StreamDetection(
                stream_id=stream.id,
                at=at,
                label=d.label,
                confidence=d.confidence,
                boxes=_clean_boxes(d.boxes),
                model=body.model or None,
            )
        )
        if d.label == "fire":
            stream.max_fire_confidence = max(stream.max_fire_confidence or 0.0, d.confidence)
        elif d.label == "smoke":
            stream.max_smoke_confidence = max(stream.max_smoke_confidence or 0.0, d.confidence)
    stream.vision_frames = [*(stream.vision_frames or []), _frame_entry(at, detections)][-CONFIRM_FRAMES:]
    await session.flush()

    confirmed = confirmed_labels(stream.vision_frames, settings.vision_alert_confidence)
    if not confirmed:
        return []
    for label in confirmed:
        # Confirmation is recorded on every confirming frame; the cool-down only throttles the alerts.
        await session.execute(
            update(StreamDetection)
            .where(
                StreamDetection.stream_id == stream.id,
                StreamDetection.at == at,
                StreamDetection.label == label,
                StreamDetection.confidence >= settings.vision_alert_confidence,
            )
            .values(confirmed=True)
        )
    alerting = {
        label: conf
        for label, conf in confirmed.items()
        if _cooled_down(stream, label, at, settings.vision_alert_cooldown_s)
    }
    frame = _decode_frame(body.frame_jpeg_b64) if alerting else None
    for label, confidence in alerting.items():
        media = await _store_frame(session, stream, frame, label, confidence, body.model) if frame else None
        stream.vision_alerts = {**(stream.vision_alerts or {}), label: at.isoformat()}
        await _timeline(session, stream, label, confidence, media)
        if stream.org_id is not None and stream.report_id is None:
            # An institution's camera: the owner is told first and the room after the delay (review point 25).
            from app.modules.orgs import prealert

            await prealert.raise_for_stream(session, stream, label, confidence, media.id if media else None)
        await emit(
            session,
            "stream.alert",
            {
                "stream_id": str(stream.id),
                "label": label,
                "confidence": round(confidence, 3),
                "report_id": str(stream.report_id) if stream.report_id else None,
                "gouvernorat_code": stream.gouvernorat_code,
                "media_id": str(media.id) if media else None,
                "simulated": stream.source == Source.SIM,
                "at": at.isoformat(),
            },
        )
        log.info("vision.confirmed", stream_id=str(stream.id), label=label, confidence=round(confidence, 3))
    if stream.report_id is not None:
        # The confirmed detection is an input of the priority score (vision_fire).
        await pipeline.rescore(session, [stream.report_id], wait=False)
    return list(alerting)


async def _timeline(
    session: AsyncSession, stream: LiveStream, label: str, confidence: float, media: Media | None
) -> None:
    if stream.report_id is None:
        return
    incident_id = await session.scalar(select(Report.incident_id).where(Report.id == stream.report_id))
    if incident_id is None:
        return
    session.add(
        TimelineEvent(
            incident_id=incident_id,
            kind="vision_alert",
            actor="system",
            payload={
                "stream_id": str(stream.id),
                "report_id": str(stream.report_id),
                "label": label,
                "confidence": round(confidence, 3),
                "media_id": str(media.id) if media else None,
            },
        )
    )


async def record_image(session: AsyncSession, media: Media, result: dict[str, Any]) -> bool:
    """Store the detections of an uploaded report image. True when a fire or smoke was confirmed in it."""
    settings = get_settings()
    now = datetime.now(UTC)
    raw = result.get("detections") or []
    detections = kept([schemas.DetectionIn.model_validate(d) for d in raw if isinstance(d, dict)])
    confirmed = False
    for d in detections:
        hit = d.label in ALERT_LABELS and d.confidence >= settings.vision_alert_confidence
        confirmed = confirmed or hit
        session.add(
            StreamDetection(
                media_id=media.id,
                at=now,
                label=d.label,
                confidence=d.confidence,
                boxes=_clean_boxes(d.boxes),
                model=str(result.get("model") or "") or None,
                confirmed=hit,
            )
        )
    media.analysis = {
        **(media.analysis or {}),
        "vision": {
            "state": "done",
            "model": result.get("model"),
            "at": now.isoformat(),
            "detections": [{"label": d.label, "confidence": d.confidence, "boxes": d.boxes} for d in detections],
        },
    }
    await session.flush()
    return confirmed


async def live_stream_for_callback(session: AsyncSession, stream_id: uuid.UUID) -> LiveStream | None:
    """The stream a vision callback is about, locked; None when unknown or no longer live."""
    stream = await session.get(LiveStream, stream_id, with_for_update=True)
    if stream is None or stream.status != StreamStatus.LIVE:
        return None
    return stream


async def detections_count(session: AsyncSession, stream_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(StreamDetection).where(StreamDetection.stream_id == stream_id)
        )
        or 0
    )
