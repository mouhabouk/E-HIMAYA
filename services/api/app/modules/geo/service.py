"""Administrative address of a position (phase M, docs/phase-m/design-m.md §3): the délégation, imada and municipality
that contain it, from the Map Tunisia boundaries of migration 0079."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.geo.models import Delegation, Municipality, Sector
from app.modules.geo.schemas import AdminAddressOut, PlaceName


@dataclass(frozen=True)
class AdminAddress:
    delegation_id: int | None = None
    sector_code: str | None = None
    municipality_id: int | None = None


async def admin_address(session: AsyncSession, lat: float, lon: float) -> AdminAddress:
    """Empty outside the land (at sea, abroad): a position is never forced into the nearest unit."""
    point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    sector = (
        await session.execute(
            select(Sector.code, Sector.delegation_id).where(func.ST_Intersects(Sector.boundary, point)).limit(1)
        )
    ).first()
    municipality = await session.scalar(
        select(Municipality.id).where(func.ST_Intersects(Municipality.boundary, point)).limit(1)
    )
    return AdminAddress(
        delegation_id=sector.delegation_id if sector else None,
        sector_code=sector.code if sector else None,
        municipality_id=municipality,
    )


async def address_out(
    session: AsyncSession, delegation_id: int | None, sector_code: str | None, municipality_id: int | None
) -> AdminAddressOut | None:
    """The names of a stored address, for the report card; None when nothing is known."""
    if delegation_id is None and sector_code is None and municipality_id is None:
        return None
    delegation = await session.get(Delegation, delegation_id) if delegation_id is not None else None
    sector = await session.get(Sector, sector_code) if sector_code is not None else None
    municipality = await session.get(Municipality, municipality_id) if municipality_id is not None else None
    return AdminAddressOut(
        delegation=PlaceName(id=str(delegation.id), name_ar=delegation.name_ar, name_fr=delegation.name_fr)
        if delegation
        else None,
        sector=PlaceName(id=sector.code, name_ar=sector.name_ar, name_fr=sector.name_fr) if sector else None,
        municipality=PlaceName(id=str(municipality.id), name_ar=municipality.name_ar, name_fr=municipality.name_fr)
        if municipality
        else None,
    )
