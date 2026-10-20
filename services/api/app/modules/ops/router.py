"""Incident endpoints: grouping (FR-C-02, BR-10, BR-11), interventions (FR-C-09: card, assignments,
volunteer call-outs, closing evaluation) and, from phase 9, incidents across gouvernorats (lead, participants,
command level, nearby incidents, resource requests).

Role lists are coarse first gates; the policy function (``core.access.authorize``, through ``ops.scope``) decides on
the loaded object before any change: 404 out of scope, 403 for an action the caller's role or room may not take.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import ACTION_NOT_ALLOWED, Action, active_grants, grant_covering
from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.audit.service import actor_of
from app.modules.ops import interventions, requests, schemas, scope, service
from app.modules.ops.models import Incident
from app.modules.reports import service as reports
from app.modules.reports.models import Report
from app.modules.reports.schemas import StaffReportDetail
from app.modules.reports.staff_router import READ_ROLES, WRITE_ROLES, detail_of

router = APIRouter(prefix="/api/v1/staff", tags=["incidents"])

StaffReader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
StaffWriter = Annotated[Principal, Depends(require_roles(*WRITE_ROLES))]
# Card and notes: operations and field command of the rooms involved, and central command.
CardWriter = Annotated[Principal, Depends(require_roles(*WRITE_ROLES, Role.CENTRAL_COMMITTEE))]
Closer = Annotated[Principal, Depends(require_roles(Role.OPS_MANAGER, Role.FIELD_COMMANDER))]
# Participants, lead, command level, merge, decisions on resource requests (command family and ops managers).
Commander = Annotated[Principal, Depends(require_roles(Role.OPS_MANAGER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE))]
Session = Annotated[AsyncSession, Depends(get_session)]
STATUSES = ("open", "closed", "merged", "dissolved")
REQUEST_STATUSES = ("pending", "approved", "refused", "cancelled")


async def _report(session: AsyncSession, principal: Principal, report_id: uuid.UUID, action: Action) -> Report:
    report = await session.get(Report, report_id, with_for_update=True)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await scope.check(session, principal, action, await scope.report_ctx(session, report))
    return report


async def _incident_audit(
    session: AsyncSession,
    principal: Principal,
    action: str,
    incident_id: uuid.UUID,
    reason: str | None = None,
    details: dict[str, object] | None = None,
) -> None:
    await audit.record(
        session,
        actor=actor_of(principal),
        action=action,
        target=f"incident:{incident_id}",
        reason=reason,
        details=details,
        gouvernorats=await service.all_gouvernorats(session, incident_id),
    )


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


async def incident_detail(session: AsyncSession, principal: Principal, incident: Incident) -> schemas.IncidentDetail:
    filters = reports.StaffFilters([], [], None, None, None, None, None, incident_id=incident.id)
    members, _ = await reports.staff_list(session, principal, filters, 500, None)
    return schemas.IncidentDetail(
        **(await service.summary(session, incident)).model_dump(),
        reports=members,
        timeline=await service.timeline(session, incident.id),
        assignments=await interventions.assignments_of(session, incident.id),
        callouts=await interventions.callouts_of(session, incident.id),
        evaluation=interventions.evaluation_of(incident),
        resource_requests=await requests.requests_of(session, incident.id),
    )


@router.get("/incidents/{incident_id}", response_model=schemas.IncidentDetail)
async def get_incident(principal: StaffReader, session: Session, incident_id: uuid.UUID) -> schemas.IncidentDetail:
    incident = await service.get_in_scope(session, principal, incident_id)
    detail = await incident_detail(session, principal, incident)
    code = principal.gouvernorat_code
    if code is not None and code != detail.gouvernorat_code and code not in detail.participating_gouvernorats:
        # Readable only under a break-glass grant: every such read is audited with the grant (§6.1).
        grant = grant_covering(await active_grants(session, principal), await scope.incident_ctx(session, incident))
        if grant is not None:
            await _incident_audit(session, principal, "incident.view", incident_id, details={"grant_id": str(grant.id)})
            await session.commit()
    return detail


@router.post("/reports/{report_id}/incident", response_model=StaffReportDetail)
async def link_report(
    principal: StaffWriter, session: Session, report_id: uuid.UUID, body: schemas.IncidentLinkIn
) -> StaffReportDetail:
    report = await _report(session, principal, report_id, Action.REPORT_LINK)
    actor = actor_of(principal)
    await service.link(session, principal, report, body, actor)
    details: dict[str, object] = {"action": body.action, "incident_id": str(report.incident_id)}
    if body.override_reason:
        details["duplicate_override"] = True
    await audit.record(
        session,
        actor=actor,
        action="incident.link",
        target=f"report:{report_id}",
        reason=body.override_reason,
        details=details,
        gouvernorats=await service.all_gouvernorats(session, report.incident_id) if report.incident_id else None,
    )
    await session.commit()
    return await detail_of(session, principal, report_id)


@router.delete("/reports/{report_id}/incident", response_model=StaffReportDetail)
async def detach_report(principal: StaffWriter, session: Session, report_id: uuid.UUID) -> StaffReportDetail:
    report = await _report(session, principal, report_id, Action.REPORT_LINK)
    actor = actor_of(principal)
    previous = report.incident_id
    codes = await service.all_gouvernorats(session, previous) if previous else None
    await service.detach(session, report, actor)
    await audit.record(
        session,
        actor=actor,
        action="incident.unlink",
        target=f"report:{report_id}",
        details={"incident_id": str(previous)},
        gouvernorats=codes,
    )
    await session.commit()
    return await detail_of(session, principal, report_id)


@router.post("/reports/{report_id}/suggestion/dismiss", response_model=StaffReportDetail)
async def dismiss_suggestion(principal: StaffWriter, session: Session, report_id: uuid.UUID) -> StaffReportDetail:
    report = await _report(session, principal, report_id, Action.REPORT_LINK)
    await service.dismiss(session, report)
    await audit.record(
        session,
        actor=actor_of(principal),
        action="incident.dismiss",
        target=f"report:{report_id}",
        gouvernorats=[report.gouvernorat_code] if report.gouvernorat_code is not None else None,
    )
    await session.commit()
    return await detail_of(session, principal, report_id)


@router.get("/reports/{report_id}/nearby-incidents", response_model=list[schemas.NearbyIncident])
async def nearby_incidents(
    principal: StaffReader, session: Session, report_id: uuid.UUID
) -> list[schemas.NearbyIncident]:
    """Open incidents of a compatible type within the grouping radius and window of the report, in any gouvernorat
    (summaries only): the duplicate warning and the cross-border link targets (§5.2)."""
    report = await session.get(Report, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await scope.check(session, principal, Action.REPORT_READ, await scope.report_ctx(session, report))
    return await service.nearby(session, report)


@router.post("/incidents/{incident_id}/merge", response_model=schemas.IncidentDetail)
async def merge_incidents(
    principal: Commander, session: Session, incident_id: uuid.UUID, body: schemas.MergeIn
) -> schemas.IncidentDetail:
    # Lock both in a fixed order so two opposite merges cannot deadlock.
    first, second = sorted((incident_id, body.incident_id))
    locked = {i: await service.get_in_scope(session, principal, i, lock=True) for i in (first, second)}
    target, source = locked[incident_id], locked[body.incident_id]
    if target.gouvernorat_code != source.gouvernorat_code and not principal.is_national:
        # Across leads only central command merges (§5.2).
        raise scope.forbidden(ACTION_NOT_ALLOWED)
    for incident in (target, source):
        await scope.check_incident(session, principal, incident, Action.INCIDENT_MERGE)
    codes = sorted(
        set(await service.all_gouvernorats(session, target.id))
        | set(await service.all_gouvernorats(session, source.id))
    )
    actor = actor_of(principal)
    await service.merge(session, target, source, actor)
    await audit.record(
        session,
        actor=actor,
        action="incident.merge",
        target=f"incident:{incident_id}",
        details={"merged": str(body.incident_id)},
        gouvernorats=codes,
    )
    await session.commit()
    return await incident_detail(session, principal, target)


# ---------------------------------------------------------------- lead, participants, command level (phase 9 §5.2-5.3)


@router.post("/incidents/{incident_id}/participants", response_model=schemas.IncidentDetail)
async def add_participant(
    principal: Commander, session: Session, incident_id: uuid.UUID, body: schemas.ParticipantIn
) -> schemas.IncidentDetail:
    incident = await service.get_in_scope(
        session, principal, incident_id, lock=True, action=Action.INCIDENT_PARTICIPANTS
    )
    await service.valid_gouvernorat(session, body.gouvernorat_code)
    actor = actor_of(principal)
    if await service.add_participant(
        session, incident, body.gouvernorat_code, actor, body.reason, audit.name_of(principal)
    ):
        await service.update_command_level(session, incident, actor)
        await _incident_audit(
            session,
            principal,
            "incident.participant_add",
            incident_id,
            body.reason,
            {"gouvernorat_code": body.gouvernorat_code},
        )
        await interventions.announce_incident(session, incident)
        await session.commit()
    return await incident_detail(session, principal, incident)


@router.delete("/incidents/{incident_id}/participants/{gouvernorat_code}", response_model=schemas.IncidentDetail)
async def remove_participant(
    principal: Commander, session: Session, incident_id: uuid.UUID, gouvernorat_code: int, body: schemas.ReasonIn
) -> schemas.IncidentDetail:
    incident = await service.get_in_scope(
        session, principal, incident_id, lock=True, action=Action.INCIDENT_PARTICIPANTS
    )
    codes = await service.all_gouvernorats(session, incident_id)
    actor = actor_of(principal)
    await service.remove_participant(session, incident, gouvernorat_code, actor, audit.name_of(principal), body.reason)
    await service.update_command_level(session, incident, actor)
    await audit.record(
        session,
        actor=actor,
        action="incident.participant_remove",
        target=f"incident:{incident_id}",
        reason=body.reason,
        details={"gouvernorat_code": gouvernorat_code},
        gouvernorats=codes,
    )
    await interventions.announce_incident(session, incident)
    await session.commit()
    return await incident_detail(session, principal, incident)


@router.post("/incidents/{incident_id}/lead", response_model=schemas.IncidentDetail)
async def transfer_lead(
    principal: Commander, session: Session, incident_id: uuid.UUID, body: schemas.LeadIn
) -> schemas.IncidentDetail:
    incident = await service.get_in_scope(
        session, principal, incident_id, lock=True, action=Action.INCIDENT_LEAD_TRANSFER
    )
    previous = incident.gouvernorat_code
    actor = actor_of(principal)
    await service.transfer_lead(session, incident, body.gouvernorat_code, actor, audit.name_of(principal), body.reason)
    await _incident_audit(
        session,
        principal,
        "incident.lead_transfer",
        incident_id,
        body.reason,
        {"from": previous, "to": body.gouvernorat_code},
    )
    await interventions.announce_incident(session, incident)
    await session.commit()
    return await incident_detail(session, principal, incident)


@router.post("/incidents/{incident_id}/command-level", response_model=schemas.IncidentDetail)
async def set_command_level(
    principal: Commander, session: Session, incident_id: uuid.UUID, body: schemas.CommandLevelIn
) -> schemas.IncidentDetail:
    incident = await service.get_in_scope(
        session, principal, incident_id, lock=True, action=Action.INCIDENT_COMMAND_LEVEL
    )
    previous = incident.command_level
    await service.set_command_level(
        session, incident, body.level, actor_of(principal), audit.name_of(principal), body.reason
    )
    await _incident_audit(
        session,
        principal,
        "incident.command_level",
        incident_id,
        body.reason,
        {"from": previous, "to": incident.command_level, "manual": body.level is not None},
    )
    await interventions.announce_incident(session, incident)
    await session.commit()
    return await incident_detail(session, principal, incident)


# ---------------------------------------------------------------- interventions (FR-C-09, phase 5)


@router.patch("/incidents/{incident_id}", response_model=schemas.IncidentDetail)
async def update_card(
    principal: CardWriter, session: Session, incident_id: uuid.UUID, body: schemas.IncidentCardIn
) -> schemas.IncidentDetail:
    incident = await service.get_in_scope(session, principal, incident_id, lock=True, action=Action.INCIDENT_CARD)
    await interventions.update_card(session, principal, incident, body)
    await _incident_audit(session, principal, "incident.card", incident_id, details=body.model_dump(exclude_unset=True))
    await session.commit()
    return await incident_detail(session, principal, incident)


@router.post(
    "/incidents/{incident_id}/notes", response_model=schemas.TimelineEntry, status_code=status.HTTP_201_CREATED
)
async def add_note(
    principal: CardWriter, session: Session, incident_id: uuid.UUID, body: schemas.NoteIn
) -> schemas.TimelineEntry:
    incident = await service.get_in_scope(session, principal, incident_id, action=Action.INCIDENT_NOTE)
    entry = await interventions.add_note(session, principal, incident, body.text)
    await _incident_audit(session, principal, "incident.note", incident_id)
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
    await _incident_audit(
        session,
        principal,
        "assignment.create",
        incident_id,
        details={"assignment_id": str(assignment.id), "resource_id": str(body.resource_id)},
    )
    await session.commit()
    return await interventions.assignment_out(session, assignment.id)


@router.post("/assignments/{assignment_id}/status", response_model=schemas.AssignmentOut)
async def update_assignment(
    principal: StaffWriter, session: Session, assignment_id: uuid.UUID, body: schemas.AssignmentStatusIn
) -> schemas.AssignmentOut:
    assignment = await interventions.update_assignment(session, principal, assignment_id, body)
    await _incident_audit(
        session,
        principal,
        "assignment.status",
        assignment.incident_id,
        body.note,
        {"assignment_id": str(assignment_id), "status": body.status},
    )
    await session.commit()
    return await interventions.assignment_out(session, assignment_id)


@router.post("/incidents/{incident_id}/close", response_model=schemas.IncidentDetail)
async def close_incident(
    principal: Closer, session: Session, incident_id: uuid.UUID, body: schemas.CloseIn
) -> schemas.IncidentDetail:
    incident = await service.get_in_scope(session, principal, incident_id, lock=True)
    await interventions.close(session, principal, incident, body)
    await _incident_audit(
        session,
        principal,
        "incident.close",
        incident_id,
        body.summary,
        {"outcome": body.outcome, "casualties": body.casualties.model_dump()},
    )
    await session.commit()
    return await incident_detail(session, principal, incident)


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
    await _incident_audit(
        session,
        principal,
        "callout.create",
        incident_id,
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
    await _incident_audit(
        session, principal, "callout.cancel", callout.incident_id, details={"callout_id": str(callout_id)}
    )
    await session.commit()
    return await interventions.callout_out(session, callout)


@router.post("/callouts/{callout_id}/targets/{volunteer_id}/arrived", response_model=schemas.CalloutOut)
async def target_arrived(
    principal: StaffWriter, session: Session, callout_id: uuid.UUID, volunteer_id: uuid.UUID
) -> schemas.CalloutOut:
    callout, _ = await interventions.callout_action(session, principal, callout_id)
    await interventions.mark_arrived(session, callout, volunteer_id, actor_of(principal))
    await interventions.announce_callout(session, callout)
    await _incident_audit(
        session,
        principal,
        "callout.arrived",
        callout.incident_id,
        details={"callout_id": str(callout_id), "volunteer_id": str(volunteer_id)},
    )
    await session.commit()
    return await interventions.callout_out(session, callout)


# ---------------------------------------------------------------- resource requests (phase 9 §5.4)


@router.post(
    "/incidents/{incident_id}/resource-requests",
    response_model=schemas.ResourceRequestOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_resource_request(
    principal: StaffReader, session: Session, incident_id: uuid.UUID, body: schemas.ResourceRequestIn
) -> schemas.ResourceRequestOut:
    incident = await service.get_in_scope(session, principal, incident_id, lock=True)
    row = await requests.create(session, principal, incident, body)
    out = await requests.request_out(session, row)
    await session.commit()
    return out


@router.get("/resource-requests", response_model=schemas.ResourceRequestPage)
async def list_resource_requests(
    principal: StaffReader,
    session: Session,
    status_: Annotated[str | None, Query(alias="status")] = None,
    direction: Annotated[str | None, Query(pattern="^(incoming|outgoing)$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> schemas.ResourceRequestPage:
    statuses = [s.strip() for s in (status_ or "").split(",") if s.strip()]
    if any(s not in REQUEST_STATUSES for s in statuses):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_status")
    items, next_cursor = await requests.list_requests(session, principal, statuses, direction, limit, cursor)
    return schemas.ResourceRequestPage(items=items, next_cursor=next_cursor)


@router.get("/resource-requests/{request_id}", response_model=schemas.ResourceRequestOut)
async def get_resource_request(
    principal: StaffReader, session: Session, request_id: uuid.UUID
) -> schemas.ResourceRequestOut:
    return await requests.request_out(session, await requests.get_visible(session, principal, request_id))


@router.post("/resource-requests/{request_id}/approve", response_model=schemas.ResourceRequestOut)
async def approve_resource_request(
    principal: Commander, session: Session, request_id: uuid.UUID, body: schemas.ApproveIn
) -> schemas.ResourceRequestOut:
    row = await requests.approve(session, principal, request_id, body)
    out = await requests.request_out(session, row)
    await session.commit()
    return out


@router.post("/resource-requests/{request_id}/refuse", response_model=schemas.ResourceRequestOut)
async def refuse_resource_request(
    principal: Commander, session: Session, request_id: uuid.UUID, body: schemas.ReasonIn
) -> schemas.ResourceRequestOut:
    row = await requests.refuse(session, principal, request_id, body.reason)
    out = await requests.request_out(session, row)
    await session.commit()
    return out


@router.post("/resource-requests/{request_id}/cancel", response_model=schemas.ResourceRequestOut)
async def cancel_resource_request(
    principal: StaffReader, session: Session, request_id: uuid.UUID
) -> schemas.ResourceRequestOut:
    row = await requests.cancel(session, principal, request_id)
    out = await requests.request_out(session, row)
    await session.commit()
    return out
