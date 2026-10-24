"""The medical committee in the dashboard (docs/phase-c/design-medical-axis.md §11): the system administrator appoints
approved Civil Protection doctors for a fixed term, renews or revokes them. Every change is audited and e-mailed."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.doctors import schemas, service

router = APIRouter(prefix="/api/v1/staff/medical-committee", tags=["staff-medical-committee"])
Session = Annotated[AsyncSession, Depends(get_session)]


async def _national_admin(principal: Annotated[Principal, Depends(require_roles(Role.SYSADMIN))]) -> Principal:
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "national_scope_required")
    return principal


Admin = Annotated[Principal, Depends(_national_admin)]


async def _out(session: AsyncSession) -> schemas.CommitteeOut:
    return schemas.CommitteeOut(members=await service.committee(session), max_members=service.COMMITTEE_MAX)


@router.get("", response_model=schemas.CommitteeOut)
async def get_committee(_: Admin, session: Session) -> schemas.CommitteeOut:
    return await _out(session)


@router.get("/candidates", response_model=list[schemas.StaffDoctor])
async def candidates(
    _: Admin,
    session: Session,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[schemas.StaffDoctor]:
    return await service.committee_candidates(session, q.strip() if q and q.strip() else None, limit)


@router.put("/{doctor_id}", response_model=schemas.CommitteeOut)
async def appoint(
    principal: Admin, session: Session, doctor_id: uuid.UUID, body: schemas.AppointmentIn
) -> schemas.CommitteeOut:
    doctor, renewal = await service.appoint(session, principal, doctor_id, body)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="medical_committee.renew" if renewal else "medical_committee.appoint",
        target=f"doctor:{doctor_id}",
        reason=body.reason,
        details={"until": doctor.committee_until.isoformat() if doctor.committee_until else None},
        gouvernorats=[doctor.gouvernorat_code],
    )
    out = await _out(session)
    await session.commit()
    return out


@router.post("/{doctor_id}/revoke", response_model=schemas.CommitteeOut)
async def revoke(
    principal: Admin, session: Session, doctor_id: uuid.UUID, body: schemas.RevocationIn
) -> schemas.CommitteeOut:
    doctor = await service.revoke(session, doctor_id, body.reason)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="medical_committee.revoke",
        target=f"doctor:{doctor_id}",
        reason=body.reason,
        gouvernorats=[doctor.gouvernorat_code],
    )
    out = await _out(session)
    await session.commit()
    return out
