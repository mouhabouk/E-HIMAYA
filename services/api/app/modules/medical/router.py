"""Locked medical files in the app (phase C1-b): who the reporter's phone locks the file for, and the doctor's inbox.
Phase C1-c: referrals to specialists, their locked opinions, keys for a new committee member, the reporter's view.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.audit import service as audit
from app.modules.doctors import service as doctors
from app.modules.identity.service import CurrentReporter
from app.modules.medical import schemas, service
from app.modules.reports import geo

router = APIRouter(prefix="/api/v1/medical", tags=["medical"])
me_router = APIRouter(prefix="/api/v1/me/medical", tags=["medical"])
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


def _places(gouvernorat: int | None) -> list[int] | None:
    return [gouvernorat] if gouvernorat is not None else None


@router.get("/files/{report_id}/referrals", response_model=list[schemas.ReferralOut])
async def referrals(reporter: CurrentReporter, session: Session, report_id: uuid.UUID) -> list[schemas.ReferralOut]:
    return await service.referrals(session, await doctors.get_mine(session, reporter), report_id)


@router.post("/files/{report_id}/referrals", status_code=status.HTTP_204_NO_CONTENT)
async def refer(
    reporter: CurrentReporter, session: Session, report_id: uuid.UUID, body: schemas.ReferralIn
) -> Response:
    """The referring doctor's phone opened the file and locked its key for each specialist (design §13.1)."""
    doctor = await doctors.get_mine(session, reporter)
    ids, gouvernorat = await service.refer(session, doctor, report_id, body)
    await audit.record(
        session,
        actor=reporter.actor,
        action="medical.refer",
        target=f"report:{report_id}",
        reason=body.reason,
        details={"doctors": [str(i) for i in ids]},
        gouvernorats=_places(gouvernorat),
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/files/{report_id}/opinion-recipients", response_model=list[schemas.OpinionRecipient])
async def opinion_recipients(
    reporter: CurrentReporter, session: Session, report_id: uuid.UUID
) -> list[schemas.OpinionRecipient]:
    return await service.opinion_recipients(session, await doctors.get_mine(session, reporter), report_id)


@router.get("/files/{report_id}/opinions", response_model=list[schemas.OpinionOut])
async def opinions(reporter: CurrentReporter, session: Session, report_id: uuid.UUID) -> list[schemas.OpinionOut]:
    return await service.opinions(session, await doctors.get_mine(session, reporter), report_id)


@router.post("/files/{report_id}/opinions", status_code=status.HTTP_201_CREATED)
async def add_opinion(
    reporter: CurrentReporter, session: Session, report_id: uuid.UUID, body: schemas.OpinionIn
) -> dict[str, str]:
    """A referred specialist's opinion, locked on their phone (design §13.2)."""
    doctor = await doctors.get_mine(session, reporter)
    opinion_id, gouvernorat = await service.add_opinion(session, doctor, report_id, body)
    await audit.record(
        session,
        actor=reporter.actor,
        action="medical.opinion",
        target=f"report:{report_id}",
        details={"opinion_id": str(opinion_id)},
        gouvernorats=_places(gouvernorat),
    )
    await session.commit()
    return {"id": str(opinion_id)}


@router.get("/committee/pending", response_model=list[schemas.PendingMember])
async def pending(reporter: CurrentReporter, session: Session) -> list[schemas.PendingMember]:
    """Files and opinions a newly appointed committee member does not hold yet (design §13.3)."""
    return await service.pending_members(session, await doctors.get_mine(session, reporter))


@router.post("/files/{report_id}/keys", status_code=status.HTTP_204_NO_CONTENT)
async def share_file(
    reporter: CurrentReporter, session: Session, report_id: uuid.UUID, body: schemas.ShareIn
) -> Response:
    doctor = await doctors.get_mine(session, reporter)
    ids, gouvernorat = await service.share_file(session, doctor, report_id, body)
    await audit.record(
        session,
        actor=reporter.actor,
        action="medical.share",
        target=f"report:{report_id}",
        reason=body.reason,
        details={"doctors": [str(i) for i in ids]},
        gouvernorats=_places(gouvernorat),
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/opinions/{opinion_id}/keys", status_code=status.HTTP_204_NO_CONTENT)
async def share_opinion(
    reporter: CurrentReporter, session: Session, opinion_id: uuid.UUID, body: schemas.ShareIn
) -> Response:
    doctor = await doctors.get_mine(session, reporter)
    report_id, ids = await service.share_opinion(session, doctor, opinion_id, body)
    await audit.record(
        session,
        actor=reporter.actor,
        action="medical.share",
        target=f"report:{report_id}",
        reason=body.reason,
        details={"opinion_id": str(opinion_id), "doctors": [str(i) for i in ids]},
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@me_router.get("/openings", response_model=list[schemas.Opening])
async def my_openings(
    reporter: CurrentReporter,
    session: Session,
    report_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[schemas.Opening]:
    """Who saw the reporter's locked medical file, by role only (design §13.4)."""
    return await service.my_openings(session, reporter, report_id, limit)
