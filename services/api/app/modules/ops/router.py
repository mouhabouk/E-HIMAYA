"""Incident endpoints: grouping (FR-C-02, BR-10, BR-11) and interventions (FR-C-09: card, assignments,
volunteer call-outs, closing evaluation)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.audit.service import actor_of
from app.modules.ops import interventions, schemas, service
from app.modules.reports import service as reports
from app.modules.reports.models import Report
from app.modules.reports.schemas import StaffReportDetail
from app.modules.reports.staff_router import READ_ROLES, WRITE_ROLES, detail_of

router = APIRouter(prefix="/api/v1/staff", tags=["incidents"])

StaffReader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
StaffWriter = Annotated[Principal, Depends(require_roles(*WRITE_ROLES))]
Closer = Annotated[Principal, Depends(require_roles(Role.OPS_MANAGER, Role.FIELD_COMMANDER))]
Session = Annotated[AsyncSession, Depends(get_session)]
STATUSES = ("open", "closed", "merged", "dissolved")


async def _report_in_scope(session: AsyncSession, principal: Principal, report_id: uuid.UUID) -> Report:
    report = await session.get(Report, report_id, with_for_update=True)
    if report is None or not reports.in_scope(principal, report.gouvernorat_code):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return report


@router.get("/incidents", response_model=schemas.IncidentPage)
async def list_incidents(
    principal: StaffReader,
    session: Session,
    status_: Annotated[str, Query(alias="status")] = "open",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> schemas.IncidentPage:
    statuses = [s.strip() for s in status_.split(",") if s.strip() and s.strip() != "all"]
    if any(s not in STATUSES for s in statuses):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_status")
    items, next_cursor = await service.list_incidents(session, principal, statuses, limit, cursor)
    return schemas.IncidentPage(items=items, next_cursor=next_cursor)


@router.get("/incidents/{incident_id}", response_model=schemas.IncidentDetail)
async def get_incident(principal: StaffReader, session: Session, incident_id: uuid.UUID) -> schemas.IncidentDetail:
    incident = await service.get_in_scope(session, principal, incident_id)
    filters = reports.StaffFilters([], [], None, None, None, None, None, incident_id=incident_id)
    members, _ = await reports.staff_list(session, principal, filters, 500, None)
    return schemas.IncidentDetail(
        **(await service.summary(session, incident)).model_dump(),
        reports=members,
        timeline=await service.timeline(session, incident_id),
        assignments=await interventions.assignments_of(session, incident_id),
        callouts=await interventions.callouts_of(session, incident_id),
        evaluation=interventions.evaluation_of(incident),
    )


@router.post("/reports/{report_id}/incident", response_model=StaffReportDetail)
async def link_report(
    principal: StaffWriter, session: Session, report_id: uuid.UUID, body: schemas.IncidentLinkIn
) -> StaffReportDetail:
    report = await _report_in_scope(session, principal, report_id)
    actor = actor_of(principal)
    await service.link(session, principal, report, body, actor)
    await audit.record(
        session,
        actor=actor,
        action="incident.link",
        target=f"report:{report_id}",
        details={"action": body.action, "incident_id": str(report.incident_id)},
    )
    await session.commit()
    return await detail_of(session, principal, report_id)


@router.delete("/reports/{report_id}/incident", response_model=StaffReportDetail)
async def detach_report(principal: StaffWriter, session: Session, report_id: uuid.UUID) -> StaffReportDetail:
    report = await _report_in_scope(session, principal, report_id)
    actor = actor_of(principal)
    previous = report.incident_id
    await service.detach(session, report, actor)
    await audit.record(
        session,
        actor=actor,
        action="incident.unlink",
        target=f"report:{report_id}",
        details={"incident_id": str(previous)},
    )
    await session.commit()
    return await detail_of(session, principal, report_id)


@router.post("/reports/{report_id}/suggestion/dismiss", response_model=StaffReportDetail)
async def dismiss_suggestion(principal: StaffWriter, session: Session, report_id: uuid.UUID) -> StaffReportDetail:
    report = await _report_in_scope(session, principal, report_id)
    await service.dismiss(session, report)
    await audit.record(session, actor=actor_of(principal), action="incident.dismiss", target=f"report:{report_id}")
    await session.commit()
    return await detail_of(session, principal, report_id)


@router.post("/incidents/{incident_id}/merge", response_model=schemas.IncidentDetail)
async def merge_incidents(
    principal: StaffWriter, session: Session, incident_id: uuid.UUID, body: schemas.MergeIn
) -> schemas.IncidentDetail:
    # Lock both in a fixed order so two opposite merges cannot deadlock.
    first, second = sorted((incident_id, body.incident_id))
    locked = {i: await service.get_in_scope(session, principal, i, lock=True) for i in (first, second)}
    actor = actor_of(principal)
    await service.merge(session, locked[incident_id], locked[body.incident_id], actor)
    await audit.record(
        session,
        actor=actor,
        action="incident.merge",
        target=f"incident:{incident_id}",
        details={"merged": str(body.incident_id)},
    )
    await session.commit()
    return await get_incident(principal, session, incident_id)


# ---------------------------------------------------------------- interventions (FR-C-09, phase 5)


@router.patch("/incidents/{incident_id}", response_model=schemas.IncidentDetail)
async def update_card(
    principal: StaffWriter, session: Session, incident_id: uuid.UUID, body: schemas.IncidentCardIn
) -> schemas.IncidentDetail:
    incident = await service.get_in_scope(session, principal, incident_id, lock=True)
    await interventions.update_card(session, principal, incident, body)
    await audit.record(
        session,
        actor=actor_of(principal),
        action="incident.card",
        target=f"incident:{incident_id}",
        details=body.model_dump(exclude_unset=True),
    )
    await session.commit()
    return await get_incident(principal, session, incident_id)


@router.post(
    "/incidents/{incident_id}/notes", response_model=schemas.TimelineEntry, status_code=status.HTTP_201_CREATED
)
async def add_note(
    principal: StaffWriter, session: Session, incident_id: uuid.UUID, body: schemas.NoteIn
) -> schemas.TimelineEntry:
    incident = await service.get_in_scope(session, principal, incident_id)
    entry = await interventions.add_note(session, principal, incident, body.text)
    await session.commit()
    return entry


@router.post(
    "/incidents/{incident_id}/assignments", response_model=schemas.AssignmentOut, status_code=status.HTTP_201_CREATED
)
async def create_assignment(
    principal: StaffWriter, session: Session, incident_id: uuid.UUID, body: schemas.AssignmentIn
) -> schemas.AssignmentOut:
    incident = await service.get_in_scope(session, principal, incident_id, lock=True)
    assignment = await interventions.create_assignment(session, principal, incident, body)
    await audit.record(
        session,
        actor=actor_of(principal),
        action="assignment.create",
        target=f"incident:{incident_id}",
        details={"assignment_id": str(assignment.id), "resource_id": str(body.resource_id)},
    )
    await session.commit()
    return await interventions.assignment_out(session, assignment.id)


@router.post("/assignments/{assignment_id}/status", response_model=schemas.AssignmentOut)
async def update_assignment(
    principal: StaffWriter, session: Session, assignment_id: uuid.UUID, body: schemas.AssignmentStatusIn
) -> schemas.AssignmentOut:
    assignment = await interventions.update_assignment(session, principal, assignment_id, body)
    await audit.record(
        session,
        actor=actor_of(principal),
        action="assignment.status",
        target=f"incident:{assignment.incident_id}",
        reason=body.note,
        details={"assignment_id": str(assignment_id), "status": body.status},
    )
    await session.commit()
    return await interventions.assignment_out(session, assignment_id)


@router.post("/incidents/{incident_id}/close", response_model=schemas.IncidentDetail)
async def close_incident(
    principal: Closer, session: Session, incident_id: uuid.UUID, body: schemas.CloseIn
) -> schemas.IncidentDetail:
    incident = await service.get_in_scope(session, principal, incident_id, lock=True)
    await interventions.close(session, principal, incident, body)
    await audit.record(
        session,
        actor=actor_of(principal),
        action="incident.close",
        target=f"incident:{incident_id}",
        reason=body.summary,
        details={"outcome": body.outcome, "casualties": body.casualties.model_dump()},
    )
    await session.commit()
    return await get_incident(principal, session, incident_id)


@router.get("/incidents/{incident_id}/volunteer-suggestions", response_model=list[schemas.VolunteerSuggestion])
async def volunteer_suggestions(
    principal: StaffReader,
    session: Session,
    incident_id: uuid.UUID,
    skill: str | None = None,
    radius_km: Annotated[int, Query(ge=1, le=100)] = 30,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[schemas.VolunteerSuggestion]:
    incident = await service.get_in_scope(session, principal, incident_id)
    return await interventions.suggestions(session, principal, incident, skill, radius_km, limit)


@router.post(
    "/incidents/{incident_id}/callouts", response_model=schemas.CalloutOut, status_code=status.HTTP_201_CREATED
)
async def create_callout(
    principal: StaffWriter, session: Session, incident_id: uuid.UUID, body: schemas.CalloutIn
) -> schemas.CalloutOut:
    incident = await service.get_in_scope(session, principal, incident_id, lock=True)
    callout = await interventions.create_callout(session, principal, incident, body)
    await audit.record(
        session,
        actor=actor_of(principal),
        action="callout.create",
        target=f"incident:{incident_id}",
        details={"callout_id": str(callout.id), "skill": body.skill, "requested": body.requested},
    )
    await session.commit()
    return await interventions.callout_out(session, callout)


@router.get("/callouts/{callout_id}", response_model=schemas.CalloutOut)
async def get_callout(principal: StaffReader, session: Session, callout_id: uuid.UUID) -> schemas.CalloutOut:
    callout, _ = await interventions.get_callout(session, principal, callout_id)
    return await interventions.callout_out(session, callout)


@router.post("/callouts/{callout_id}/cancel", response_model=schemas.CalloutOut)
async def cancel_callout(principal: StaffWriter, session: Session, callout_id: uuid.UUID) -> schemas.CalloutOut:
    callout = await interventions.cancel_callout(session, principal, callout_id)
    await audit.record(
        session, actor=actor_of(principal), action="callout.cancel", target=f"incident:{callout.incident_id}"
    )
    await session.commit()
    return await interventions.callout_out(session, callout)


@router.post("/callouts/{callout_id}/targets/{volunteer_id}/arrived", response_model=schemas.CalloutOut)
async def target_arrived(
    principal: StaffWriter, session: Session, callout_id: uuid.UUID, volunteer_id: uuid.UUID
) -> schemas.CalloutOut:
    callout, incident = await interventions.get_callout(session, principal, callout_id, lock=True)
    await interventions.mark_arrived(session, callout, volunteer_id, actor_of(principal))
    await interventions.announce_callout(session, callout, incident.gouvernorat_code)
    await session.commit()
    return await interventions.callout_out(session, callout)
