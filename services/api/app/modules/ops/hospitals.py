"""The nearest hospitals of an incident on the road, and the one the room adds to it (phase L1b, design-layers.md §4).

Candidates are the places of the published hospital and clinic layers (L1a visibility applies: the reader must see the
layer) closest to the incident as the crow flies; they are then timed by car with the routing engine (phase 7), or
estimated when the engine is not there, said as ``engine: "fallback"``. Adding one writes a timeline entry with its
distance and time, so the field teams and the record keep the choice.
"""

import uuid

from fastapi import HTTPException, status
from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.modules.decision import routing
from app.modules.geo.models import Layer, LayerFeature
from app.modules.layers import access
from app.modules.ops import schemas
from app.modules.ops.crew import HOSPITAL_ICONS
from app.modules.ops.models import Incident, TimelineEvent

CANDIDATES = 9
SHOWN = 3


async def _centre(session: AsyncSession, incident: Incident) -> routing.Point | None:
    if incident.centroid is None:
        return None
    geometry = cast(Incident.centroid, Geometry)
    row = (
        await session.execute(select(func.ST_Y(geometry), func.ST_X(geometry)).where(Incident.id == incident.id))
    ).first()
    return routing.Point(float(row[0]), float(row[1])) if row else None


async def nearest(session: AsyncSession, principal: Principal, incident: Incident) -> list[schemas.NearHospital]:
    centre = await _centre(session, incident)
    if centre is None:
        return []
    here = func.ST_SetSRID(func.ST_MakePoint(centre.lon, centre.lat), 4326)
    geography = cast(here, LayerFeature.location.type)
    distance = func.ST_Distance(LayerFeature.location, geography)
    geometry = cast(LayerFeature.location, Geometry)
    rows = (
        await session.execute(
            select(LayerFeature, Layer, func.ST_Y(geometry), func.ST_X(geometry), distance)
            .join(Layer, Layer.id == LayerFeature.layer_id)
            .where(
                Layer.icon.in_(HOSPITAL_ICONS),
                Layer.deleted_at.is_(None),
                LayerFeature.hidden.is_(False),
                LayerFeature.deleted_at.is_(None),
            )
            .order_by(distance, LayerFeature.id)
            .limit(CANDIDATES * 3)
        )
    ).all()
    seen = [r for r in rows if access.sees(principal, r[1])][:CANDIDATES]
    if not seen:
        return []
    legs, engine = await routing.travel([routing.Point(float(r[2]), float(r[3])) for r in seen], centre, "car")
    out = [
        schemas.NearHospital(
            id=feature.id,
            name=feature.name,
            phone=feature.phone,
            layer=layer.key,
            lat=float(lat),
            lon=float(lon),
            distance_m=round(float(d)),
            road_m=round(leg.distance_m),
            road_s=round(leg.duration_s),
            engine=engine,
            simulated=layer.simulated,
        )
        for (feature, layer, lat, lon, d), leg in zip(seen, legs, strict=True)
    ]
    return sorted(out, key=lambda h: (h.road_s, h.distance_m))[:SHOWN]


async def choose(
    session: AsyncSession, principal: Principal, incident: Incident, feature_id: uuid.UUID, actor: str, name: str | None
) -> schemas.NearHospital:
    options = {h.id: h for h in await nearest(session, principal, incident)}
    if feature_id not in options:
        # Only one of the hospitals offered (the nearest on the road that the reader may see).
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "hospital_not_offered")
    chosen = options[feature_id]
    session.add(
        TimelineEvent(
            incident_id=incident.id,
            kind="hospital_chosen",
            actor=actor,
            payload={
                "feature_id": str(chosen.id),
                "name": chosen.name,
                "phone": chosen.phone,
                "road_m": chosen.road_m,
                "road_s": chosen.road_s,
                "engine": chosen.engine,
                "by": name,
            },
        )
    )
    return chosen
