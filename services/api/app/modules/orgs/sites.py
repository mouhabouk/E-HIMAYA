"""Sensitive sites near a report (BR-20, component ``sensitive_sites``): the registered institutions.

Depends only on the institution models and rules, so the AI pipeline can import it without a cycle.
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orgs import domain
from app.modules.orgs.models import Hazmat, Organization

# Institutions considered for one report: the most sensitive of the nearest ones wins.
_CANDIDATES = 20


async def nearest(session: AsyncSession, location: Any) -> tuple[float, dict[str, Any]] | None:
    """Value (0..1) and explanation of the component for a point (a geography value), None when no site."""
    distance = func.ST_Distance(Organization.location, location)
    hazmat = (
        select(func.count(Hazmat.id)).where(Hazmat.org_id == Organization.id).correlate(Organization).scalar_subquery()
    )
    rows = (
        await session.execute(
            select(Organization, distance, hazmat)
            .where(
                Organization.status == domain.OrgStatus.ACTIVE,
                func.ST_DWithin(Organization.location, location, domain.SENSITIVE_RADIUS_M),
            )
            .order_by(distance)
            .limit(_CANDIDATES)
        )
    ).all()
    best: tuple[float, dict[str, Any]] | None = None
    for org, meters, hazmat_count in rows:
        classification = domain.classify(
            kind=org.kind,
            capacity=org.capacity,
            height_m=org.height_m,
            receives_public=org.receives_public,
            hazmat_count=int(hazmat_count),
        )
        value, reason = domain.sensitivity(classification, org.kind, int(hazmat_count))
        if best is None or value > best[0]:  # rows are nearest first: ties keep the nearest
            best = (
                value,
                {"org_id": str(org.id), "name": org.name, "distance_m": round(float(meters), 1), "reason": reason},
            )
    return best
