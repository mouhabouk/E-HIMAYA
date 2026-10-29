"""The indicators out of their habit (AI4, docs/phase-l/design-l5.md §4.4), for the alert centre."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.ai import settings as ai_settings
from app.modules.anomaly import schemas, service
from app.modules.reports.staff_router import READ_ROLES

router = APIRouter(prefix="/api/v1/staff/anomalies", tags=["ai"])
Session = Annotated[AsyncSession, Depends(get_session)]
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES, Role.GOVERNOR, Role.MINISTER))]


async def for_scope(session: AsyncSession, codes: list[int], lang: str) -> schemas.AnomaliesOut:
    if not (await ai_settings.load(session)).assist.anomalies:
        return schemas.AnomaliesOut(enabled=False, items=[])
    rows = await service.detect(session, codes=codes)
    items = [schemas.AnomalyOut.model_validate(x) for x in await service.explain(session, rows, lang)]
    await session.commit()
    return schemas.AnomaliesOut(enabled=True, items=items)


@router.get("", response_model=schemas.AnomaliesOut)
async def list_anomalies(
    principal: Reader, session: Session, lang: Annotated[Literal["ar", "fr", "en"], Query()] = "ar"
) -> schemas.AnomaliesOut:
    """Today's indicators out of their habit in the reader's scope (a room its gouvernorat, the centre all)."""
    codes = [] if principal.is_national else [principal.gouvernorat_code or 0]
    return await for_scope(session, codes, lang)
