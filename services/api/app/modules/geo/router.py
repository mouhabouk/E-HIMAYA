"""Administrative reference (gouvernorats and délégations) used by every registration and report form."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.geo.models import Delegation, Gouvernorat
from app.modules.geo.schemas import DelegationOut, GouvernoratOut

router = APIRouter(prefix="/api/v1/geo", tags=["geo"])

Lang = Literal["ar", "fr", "en"]
# Reference data changes only through migrations: let clients and the mobile app cache it.
CACHE_HEADER = "public, max-age=86400"


def _localized(name_ar: str, name_fr: str, lang: Lang) -> str:
    # English uses the official French transliteration.
    return name_ar if lang == "ar" else name_fr


@router.get("/gouvernorats", response_model=list[GouvernoratOut])
async def list_gouvernorats(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    lang: Annotated[Lang, Query()] = "ar",
) -> list[GouvernoratOut]:
    counts = (
        select(Delegation.gouvernorat_code, func.count().label("n")).group_by(Delegation.gouvernorat_code).subquery()
    )
    rows = await session.execute(
        select(Gouvernorat, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.gouvernorat_code == Gouvernorat.code)
        .order_by(Gouvernorat.code)
    )
    response.headers["Cache-Control"] = CACHE_HEADER
    return [
        GouvernoratOut(
            code=g.code,
            iso_code=g.iso_code,
            name=_localized(g.name_ar, g.name_fr, lang),
            name_ar=g.name_ar,
            name_fr=g.name_fr,
            delegation_count=n,
        )
        for g, n in rows.all()
    ]


@router.get("/gouvernorats/{code}/delegations", response_model=list[DelegationOut])
async def list_delegations(
    code: int,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    lang: Annotated[Lang, Query()] = "ar",
) -> list[DelegationOut]:
    if await session.get(Gouvernorat, code) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_gouvernorat")
    rows = await session.scalars(select(Delegation).where(Delegation.gouvernorat_code == code).order_by(Delegation.id))
    response.headers["Cache-Control"] = CACHE_HEADER
    return [
        DelegationOut(
            id=d.id,
            code=d.code,
            gouvernorat_code=d.gouvernorat_code,
            name=_localized(d.name_ar, d.name_fr, lang),
            name_ar=d.name_ar,
            name_fr=d.name_fr,
        )
        for d in rows
    ]
