"""Which reports describe the same event (BR-10): same type, close in space and time, or close in meaning.

Suggestions only: linking reports into an incident is confirmed by an operator (BR-11).
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.settings import GroupingSettings
from app.modules.reports.domain import Category

_CANDIDATES = text(
    """
    WITH x AS (SELECT id, location, received_at, embedding FROM reports.report WHERE id = :id)
    SELECT r.id, r.tracking_code, r.incident_id, r.user_id, r.category,
           ST_Distance(r.location, x.location) AS distance_m,
           abs(extract(epoch FROM r.received_at - x.received_at)) / 60 AS minutes,
           CASE WHEN r.embedding IS NOT NULL AND x.embedding IS NOT NULL
                THEN 1 - (r.embedding <=> x.embedding) END AS similarity
    FROM reports.report r
    CROSS JOIN x
    LEFT JOIN ops.incident i ON i.id = r.incident_id
    WHERE r.id <> x.id
      AND r.status NOT IN ('closed', 'rejected')
      AND (r.incident_id IS NULL OR i.status = 'open')
      AND r.received_at BETWEEN x.received_at - make_interval(mins => :window)
                            AND x.received_at + make_interval(mins => :window)
      AND ST_DWithin(r.location, x.location, :radius)
    ORDER BY distance_m
    LIMIT 100
    """
)


@dataclass(frozen=True, slots=True)
class Match:
    report_id: uuid.UUID
    tracking_code: str
    incident_id: uuid.UUID | None
    user_id: uuid.UUID
    distance_m: float
    minutes: float
    similarity: float | None
    score: float
    reasons: tuple[str, ...]


def _compatible(a: Category, b: Category) -> bool:
    # A one-touch SOS carries no type: it can belong to any event nearby.
    return a == b or Category.SOS in (a, b)


async def find_matches(
    session: AsyncSession, report_id: uuid.UUID, category: Category, settings: GroupingSettings
) -> list[Match]:
    window = max(settings.window_min, settings.semantic_window_min)
    radius = max(max(settings.radius_m.values()), settings.semantic_radius_m)
    rows = (await session.execute(_CANDIDATES, {"id": report_id, "window": window, "radius": radius})).all()
    matches: list[Match] = []
    for row in rows:
        other = Category(row.category)
        distance, minutes = float(row.distance_m), float(row.minutes)
        similarity = None if row.similarity is None else float(row.similarity)
        reasons: list[str] = []
        geo_radius = max(settings.radius_m[category], settings.radius_m[other])
        if _compatible(category, other) and distance <= geo_radius and minutes <= settings.window_min:
            reasons += ["same_category" if category == other else "sos_nearby", "within_radius", "within_window"]
            geo, time = 1 - distance / geo_radius, 1 - minutes / settings.window_min
        elif (
            similarity is not None
            and similarity >= settings.semantic_min_similarity
            and distance <= settings.semantic_radius_m
            and minutes <= settings.semantic_window_min
        ):
            geo, time = 1 - distance / settings.semantic_radius_m, 1 - minutes / settings.semantic_window_min
        else:
            continue
        if similarity is not None and similarity >= settings.semantic_min_similarity:
            reasons.append("similar_content")
        score = 0.45 * geo + 0.25 * time + 0.30 * similarity if similarity is not None else 0.6 * geo + 0.4 * time
        matches.append(
            Match(
                report_id=row.id,
                tracking_code=row.tracking_code,
                incident_id=row.incident_id,
                user_id=row.user_id,
                distance_m=round(distance, 1),
                minutes=round(minutes, 1),
                similarity=None if similarity is None else round(similarity, 3),
                score=round(max(score, 0.0), 3),
                reasons=tuple(reasons),
            )
        )
    return matches


def suggestion(matches: list[Match], own_incident: uuid.UUID | None, dismissed: list[str]) -> dict[str, Any] | None:
    """Best target for a report not yet grouped: an open incident, or another report to group with."""
    if own_incident is not None:
        return None
    best: dict[str, Any] | None = None
    sizes: dict[str, int] = {}
    for match in matches:
        target = f"incident:{match.incident_id}" if match.incident_id else f"report:{match.report_id}"
        sizes[target] = sizes.get(target, 0) + 1
        if target in dismissed or (best is not None and best["score"] >= match.score):
            continue
        best = {
            "target": target,
            "kind": "incident" if match.incident_id else "report",
            "incident_id": str(match.incident_id) if match.incident_id else None,
            "report_id": str(match.report_id),
            "tracking_code": match.tracking_code,
            "score": match.score,
            "distance_m": match.distance_m,
            "minutes": match.minutes,
            "similarity": match.similarity,
            "reasons": list(match.reasons),
        }
    if best is not None:
        best["matching_reports"] = sizes[best["target"]]
    return best
