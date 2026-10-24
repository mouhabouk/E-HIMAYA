"""Doctors in the dashboard (phase C1-a): the regional medical coordinator checks each registration."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.doctors import schemas, service

router = APIRouter(prefix="/api/v1/staff/doctors", tags=["staff-doctors"])
Session = Annotated[AsyncSession, Depends(get_session)]
# The registration numbers are personal data: only those who decide see the list (volunteer reviewers until the
# medical coordinators are named).
REVIEW_ROLES = (Role.MEDICAL_COORDINATOR, Role.OPS_MANAGER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE)
Reviewer = Annotated[Principal, Depends(require_roles(*REVIEW_ROLES))]
STATUSES = schemas.DoctorStatus.__args__  # type: ignore[attr-defined]
KINDS = schemas.DoctorKind.__args__  # type: ignore[attr-defined]
SPECIALTIES = schemas.Specialty.__args__  # type: ignore[attr-defined]


@router.get("", response_model=schemas.StaffDoctorPage)
async def list_doctors(
    principal: Reviewer,
    session: Session,
    status_: Annotated[str | None, Query(alias="status")] = None,
    kind: str | None = None,
    specialty: str | None = None,
    gouvernorat_code: int | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> schemas.StaffDoctorPage:
    statuses = [s.strip() for s in (status_ or "").split(",") if s.strip()]
    if any(s not in STATUSES for s in statuses):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_status")
    if kind is not None and kind not in KINDS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_kind")
    if specialty is not None and specialty not in SPECIALTIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_specialty")
    items, next_cursor = await service.staff_list(
        session,
        principal,
        statuses=statuses,
        kind=kind,
        specialty=specialty,
        gouvernorat_code=gouvernorat_code,
        q=q.strip() if q and q.strip() else None,
        limit=limit,
        cursor=cursor,
    )
    return schemas.StaffDoctorPage(items=items, next_cursor=next_cursor)


@router.get("/{doctor_id}", response_model=schemas.StaffDoctorDetail)
async def get_doctor(principal: Reviewer, session: Session, doctor_id: uuid.UUID) -> schemas.StaffDoctorDetail:
    doctor = await service.get_in_scope(session, principal, doctor_id)
    detail = await service.staff_detail(session, doctor)
    # The file shows the phone and the registration numbers: every opening is audited.
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="doctor.view",
        target=f"doctor:{doctor_id}",
        gouvernorats=[doctor.gouvernorat_code],
    )
    await session.commit()
    return detail


@router.post("/{doctor_id}/review", response_model=schemas.StaffDoctorDetail)
async def review_doctor(
    principal: Reviewer, session: Session, doctor_id: uuid.UUID, body: schemas.DoctorReviewIn
) -> schemas.StaffDoctorDetail:
    doctor = await service.get_in_scope(session, principal, doctor_id, lock=True)
    previous = await service.review(session, principal, doctor, body)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="doctor.review",
        target=f"doctor:{doctor_id}",
        reason=body.reason,
        details={"decision": body.decision, "from": previous, "to": doctor.status},
        gouvernorats=[doctor.gouvernorat_code],
    )
    detail = await service.staff_detail(session, doctor)
    await session.commit()
    return detail
