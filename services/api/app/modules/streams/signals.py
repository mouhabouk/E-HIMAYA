"""Vision input of the priority score (``vision_fire``, ai.scoring): kept free of the pipeline imports."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports.models import Media
from app.modules.streams.domain import ALERT_LABELS
from app.modules.streams.models import LiveStream, StreamDetection


async def vision_signal(session: AsyncSession, report_id: uuid.UUID) -> tuple[float, dict[str, Any]] | None:
    """Strongest confirmed fire or smoke of a report (its live streams and uploaded images), or None."""
    stream_ids = select(LiveStream.id).where(LiveStream.report_id == report_id)
    media_ids = select(Media.id).where(Media.report_id == report_id)
    row = (
        await session.execute(
            select(StreamDetection.label, StreamDetection.confidence, StreamDetection.stream_id)
            .where(
                StreamDetection.confirmed.is_(True),
                StreamDetection.label.in_(ALERT_LABELS),
                StreamDetection.stream_id.in_(stream_ids) | StreamDetection.media_id.in_(media_ids),
            )
            .order_by(StreamDetection.confidence.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    label, confidence, stream_id = row
    return float(confidence), {"label": label, "source": "stream" if stream_id else "image"}
