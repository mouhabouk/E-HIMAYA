"""Doctor space of the app (phase C1-a): registration, availability, and the referral list of approved doctors."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.audit import service as audit
from app.modules.doctors import schemas, service
from app.modules.identity.service import CurrentReporter
from app.modules.medical import schemas as medical_schemas
from app.modules.medical import service as medical

router = APIRouter(prefix="/api/v1", tags=["doctors"])
Session = Annotated[AsyncSession, Depends(get_session)]
SPECIALTIES = schemas.Specialty.__args__  # type: ignore[attr-defined]


@router.get("/me/doctor", response_model=schemas.DoctorOut)
async def get_doctor(reporter: CurrentReporter, session: Session) -> schemas.DoctorOut:
    return service.doctor_out(await service.get_mine(session, reporter))


@router.put("/me/doctor", response_model=schemas.DoctorOut)
async def put_doctor(reporter: CurrentReporter, session: Session, body: schemas.DoctorIn) -> schemas.DoctorOut:
    doctor = await service.declare(session, reporter, body)
    await audit.record(
        session,
        actor=reporter.actor,
        action="doctor.declare",
        target=f"doctor:{doctor.user_id}",
        details={"kind": doctor.kind, "specialties": list(doctor.specialties), "status": doctor.status},
        gouvernorats=[doctor.gouvernorat_code],
    )
    out = service.doctor_out(doctor)
    await session.commit()
    return out


@router.delete("/me/doctor", status_code=status.HTTP_204_NO_CONTENT)
async def withdraw(reporter: CurrentReporter, session: Session) -> Response:
    doctor = await service.withdraw(session, reporter)
    await audit.record(
        session,
        actor=reporter.actor,
        action="doctor.withdraw",
        target=f"doctor:{doctor.user_id}",
        gouvernorats=[doctor.gouvernorat_code],
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/doctor/availability", response_model=schemas.DoctorOut)
async def availability(reporter: CurrentReporter, session: Session, body: schemas.AvailabilityIn) -> schemas.DoctorOut:
    doctor = await service.set_availability(session, reporter, body)
    out = service.doctor_out(doctor)
    await session.commit()
    return out


@router.get("/doctors/directory", response_model=list[schemas.DirectoryDoctor])
async def directory(
    reporter: CurrentReporter,
    session: Session,
    specialty: str | None = None,
    gouvernorat_code: int | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[schemas.DirectoryDoctor]:
    """The referral list (design §4.3): open to approved doctors only."""
    me = await service.get_mine(session, reporter)
    if me.status != "approved":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "doctor_not_approved")
    if specialty is not None and specialty not in SPECIALTIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_specialty")
    return await service.directory(
        session, specialty=specialty, gouvernorat_code=gouvernorat_code, near=me.gouvernorat_code, limit=limit
    )


@router.get("/me/doctor/key", response_model=medical_schemas.DoctorKeyOut)
async def get_key(reporter: CurrentReporter, session: Session) -> medical_schemas.DoctorKeyOut:
    """The doctor's locked private key, to open it on a new phone with their code (phase C1-b)."""
    return medical.key_out(await service.get_mine(session, reporter))


@router.put("/me/doctor/key", response_model=schemas.DoctorOut)
async def put_key(reporter: CurrentReporter, session: Session, body: medical_schemas.DoctorKeyIn) -> schemas.DoctorOut:
    doctor = await service.get_mine(session, reporter, lock=True)
    replaced = await medical.set_key(session, doctor, body)
    await audit.record(
        session,
        actor=reporter.actor,
        action="doctor.key_replace" if replaced else "doctor.key_set",
        target=f"doctor:{doctor.user_id}",
        gouvernorats=[doctor.gouvernorat_code],
    )
    out = service.doctor_out(doctor)
    await session.commit()
    return out
