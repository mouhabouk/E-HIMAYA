"""Locked medical files in the app (phase C1-b): who the reporter's phone locks the file for, and the doctor's inbox."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.audit import service as audit
from app.modules.doctors import service as doctors
from app.modules.identity.service import CurrentReporter
from app.modules.medical import schemas, service
from app.modules.reports import geo

router = APIRouter(prefix="/api/v1/medical", tags=["medical"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/recipients", response_model=schemas.RecipientsOut)
async def recipients(
    _: CurrentReporter,
    session: Session,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    accuracy_m: Annotated[float | None, Query(ge=0, le=100_000)] = None,
) -> schemas.RecipientsOut:
    """Public keys only: the same place gives the same list when the report is sent."""
    place = await geo.assess(session, lat, lon, accuracy_m, "app")
    return await service.recipients(session, place)


@router.get("/files", response_model=list[schemas.InboxItem])
async def inbox(
    reporter: CurrentReporter, session: Session, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> list[schemas.InboxItem]:
    return await service.inbox(session, await doctors.get_mine(session, reporter), limit)


@router.post("/files/{report_id}/open", response_model=schemas.OpenedFile)
async def open_file(
    reporter: CurrentReporter, session: Session, report_id: uuid.UUID, body: schemas.OpenIn
) -> schemas.OpenedFile:
    doctor = await doctors.get_mine(session, reporter)
    out, gouvernorat = await service.open_file(session, doctor, report_id, body.reason)
    await audit.record(
        session,
        actor=reporter.actor,
        action="medical.open",
        target=f"report:{report_id}",
        reason=body.reason,
        details={"via": out.via},
        gouvernorats=[gouvernorat] if gouvernorat is not None else None,
    )
    await session.commit()
    return out
