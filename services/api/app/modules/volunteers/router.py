"""Volunteer space of the app (FR-A-020…023): application, readiness, live position, call-outs."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.ratelimit import enforce
from app.modules.audit import service as audit
from app.modules.identity.service import CurrentReporter
from app.modules.ops import interventions
from app.modules.ops.models import Callout, Incident
from app.modules.volunteers import callout_sms, schemas, service

router = APIRouter(prefix="/api/v1/me", tags=["volunteers"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/volunteer", response_model=schemas.VolunteerOut)
async def get_volunteer(reporter: CurrentReporter, session: Session) -> schemas.VolunteerOut:
    return await service.mine_out(session, await service.get_mine(session, reporter))


@router.put("/volunteer", response_model=schemas.VolunteerOut)
async def put_volunteer(reporter: CurrentReporter, session: Session, body: schemas.VolunteerIn) -> schemas.VolunteerOut:
    volunteer = await service.declare(session, reporter, body)
    await audit.record(
        session,
        actor=reporter.actor,
        action="volunteer.declare",
        target=f"volunteer:{volunteer.user_id}",
        details={"skills": list(volunteer.skills), "status": volunteer.status},
    )
    out = await service.mine_out(session, volunteer)
    await session.commit()
    return out


@router.delete("/volunteer", status_code=status.HTTP_204_NO_CONTENT)
async def withdraw(reporter: CurrentReporter, session: Session) -> Response:
    volunteer = await service.withdraw(session, reporter)
    await audit.record(
        session, actor=reporter.actor, action="volunteer.withdraw", target=f"volunteer:{volunteer.user_id}"
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/consents", status_code=status.HTTP_204_NO_CONTENT)
async def give_consent(reporter: CurrentReporter, session: Session, body: schemas.LocationConsentIn) -> Response:
    """Consent to share the position while ready (phase 10 §4.2); idempotent."""
    if await service.give_location_consent(session, reporter, body.version, body.locale, body.platform):
        await audit.record(
            session,
            actor=reporter.actor,
            action="consent.volunteer_location",
            target=f"volunteer:{reporter.user_id}",
            details={"version": body.version},
        )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/consents/volunteer_location", status_code=status.HTTP_204_NO_CONTENT)
async def withdraw_consent(reporter: CurrentReporter, session: Session) -> Response:
    """Withdraw it: the stored position is dropped and readiness ends at once."""
    if await service.withdraw_location_consent(session, reporter):
        await audit.record(
            session,
            actor=reporter.actor,
            action="consent.volunteer_location_withdraw",
            target=f"volunteer:{reporter.user_id}",
        )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/volunteer/readiness", response_model=schemas.VolunteerOut)
async def readiness(reporter: CurrentReporter, session: Session, body: schemas.ReadinessIn) -> schemas.VolunteerOut:
    volunteer = await service.set_readiness(session, reporter, body)
    out = await service.mine_out(session, volunteer)
    await session.commit()
    return out


@router.post("/volunteer/sms-key", response_model=schemas.SmsKeyOut)
async def sms_key(reporter: CurrentReporter, session: Session) -> schemas.SmsKeyOut:
    """The key of the signed SMS answers to call-outs (phase D, S2-5, ``EH3``): made once, kept on the phone."""
    volunteer = await service.get_mine(session, reporter, lock=True)
    if volunteer.status != "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, "volunteer_not_approved")
    if volunteer.sms_key is None:
        volunteer.sms_key = callout_sms.new_key()
        await audit.record(
            session, actor=reporter.actor, action="volunteer.sms_key", target=f"volunteer:{volunteer.user_id}"
        )
    out = schemas.SmsKeyOut(key=volunteer.sms_key, volunteer_id=volunteer.user_id)
    await session.commit()
    return out


@router.put("/volunteer/location", status_code=status.HTTP_204_NO_CONTENT)
async def location(reporter: CurrentReporter, session: Session, body: schemas.LocationIn) -> Response:
    await enforce(f"vol-loc:{reporter.user_id}", 1, service.LOCATION_MIN_INTERVAL_S)
    await service.update_location(session, reporter, body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/callouts", response_model=list[schemas.MyCallout])
async def my_callouts(reporter: CurrentReporter, session: Session, active: bool = True) -> list[schemas.MyCallout]:
    return await interventions.my_callouts(session, reporter, active)


async def _one(session: AsyncSession, reporter: CurrentReporter, callout_id: uuid.UUID) -> schemas.MyCallout:
    for item in await interventions.my_callouts(session, reporter, active=False):
        if item.id == callout_id:
            return item  # type: ignore[no-any-return]
    raise AssertionError("callout target vanished")


@router.post("/callouts/{callout_id}/respond", response_model=schemas.MyCallout)
async def respond(
    reporter: CurrentReporter, session: Session, callout_id: uuid.UUID, body: schemas.RespondIn
) -> schemas.MyCallout:
    await interventions.respond(session, reporter, callout_id, body.response, body.eta_minutes)
    await session.commit()
    return await _one(session, reporter, callout_id)


@router.post("/callouts/{callout_id}/arrived", response_model=schemas.MyCallout)
async def arrived(reporter: CurrentReporter, session: Session, callout_id: uuid.UUID) -> schemas.MyCallout:
    volunteer = await service.get_mine(session, reporter)
    callout = await session.get(Callout, callout_id, with_for_update=True)
    if callout is None:
        from fastapi import HTTPException

        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await interventions.mark_arrived(session, callout, volunteer.user_id, reporter.actor)
    incident = await session.get(Incident, callout.incident_id)
    await interventions.announce_callout(session, callout, incident.gouvernorat_code if incident else None)
    await session.commit()
    return await _one(session, reporter, callout_id)
