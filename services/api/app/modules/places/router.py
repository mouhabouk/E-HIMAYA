"""Saved places (phase M, docs/phase-m/design-m.md §7): ``/api/v1/staff/places``.

Every room marks points on its map with a name, a kind (important, critical, other) and a note, and finds them again
in a list. The point must lie in Tunisia; its gouvernorat and délégation come from the Map Tunisia boundaries. A
regional room keeps its own gouvernorat's places (row level security), the central room sees them all. Every change
is in the audit log.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, require_roles
from app.modules.audit import service as audit
from app.modules.places import schemas
from app.modules.places.models import SavedPlace
from app.modules.reports.staff_router import READ_ROLES

router = APIRouter(prefix="/api/v1/staff/places", tags=["places"])

Session = Annotated[AsyncSession, Depends(get_session)]
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
MAX_PLACES = 1000
# Critical first, then important, then the others; the latest change first within a kind.
_ORDER = {"critical": 0, "important": 1, "other": 2}


def _out(place: SavedPlace) -> schemas.PlaceOut:
    return schemas.PlaceOut.model_validate(place, from_attributes=True)


def _clean(note: str | None) -> str | None:
    return note.strip() if note and note.strip() else None


async def _where(session: AsyncSession, lat: float, lon: float) -> tuple[int, int | None]:
    row = (
        await session.execute(
            text(
                "SELECT g.code, (SELECT d.id FROM geo.delegation d WHERE d.gouvernorat_code = g.code "
                "AND ST_Intersects(d.boundary, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) LIMIT 1) "
                "FROM geo.gouvernorat g WHERE ST_Intersects(g.boundary, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) "
                "LIMIT 1"
            ),
            {"lat": lat, "lon": lon},
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "outside_tunisia")
    return int(row[0]), (int(row[1]) if row[1] is not None else None)


async def _load(session: AsyncSession, place_id: uuid.UUID) -> SavedPlace:
    place = await session.get(SavedPlace, place_id)
    if place is None:  # absent, or another gouvernorat's (row level security)
        raise HTTPException(status.HTTP_404_NOT_FOUND, "place_not_found")
    return place


@router.get("", response_model=list[schemas.PlaceOut])
async def list_places(
    principal: Reader, session: Session, kind: Annotated[schemas.Kind | None, Query()] = None
) -> list[schemas.PlaceOut]:
    query = select(SavedPlace).order_by(SavedPlace.updated_at.desc()).limit(MAX_PLACES)
    if kind is not None:
        query = query.where(SavedPlace.kind == kind)
    places = list(await session.scalars(query))
    places.sort(key=lambda p: _ORDER.get(p.kind, 9))
    return [_out(p) for p in places]


@router.post("", response_model=schemas.PlaceOut, status_code=status.HTTP_201_CREATED)
async def create_place(principal: Reader, session: Session, body: schemas.PlaceIn) -> schemas.PlaceOut:
    code, delegation = await _where(session, body.lat, body.lon)
    if not principal.can_access_gouvernorat(code):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
    actor = audit.actor_of(principal)
    name = audit.name_of(principal)
    place = SavedPlace(
        name=body.name.strip(),
        kind=body.kind,
        note=_clean(body.note),
        lat=body.lat,
        lon=body.lon,
        gouvernorat_code=code,
        delegation_id=delegation,
        created_by=actor,
        created_by_name=name,
        updated_by_name=name,
    )
    session.add(place)
    await session.flush()
    await session.refresh(place)
    await audit.record(
        session,
        actor=actor,
        action="place.create",
        target=f"place:{place.id}",
        details={"kind": place.kind},
        gouvernorats=[code],
    )
    out = _out(place)
    await session.commit()
    return out


@router.put("/{place_id}", response_model=schemas.PlaceOut)
async def update_place(
    principal: Reader, session: Session, place_id: uuid.UUID, body: schemas.PlaceUpdate
) -> schemas.PlaceOut:
    place = await _load(session, place_id)
    before = place.kind
    place.name, place.kind, place.note = body.name.strip(), body.kind, _clean(body.note)
    place.updated_by_name = audit.name_of(principal)
    place.updated_at = datetime.now(UTC)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="place.update",
        target=f"place:{place.id}",
        details={"kind": {"before": before, "after": place.kind}},
        gouvernorats=[place.gouvernorat_code],
    )
    out = _out(place)
    await session.commit()
    return out


@router.delete("/{place_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_place(principal: Reader, session: Session, place_id: uuid.UUID) -> None:
    place = await _load(session, place_id)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="place.delete",
        target=f"place:{place.id}",
        details={"name": place.name, "kind": place.kind},
        gouvernorats=[place.gouvernorat_code],
    )
    await session.delete(place)
    await session.commit()
