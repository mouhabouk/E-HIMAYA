"""Prevention visits and the institution's reports, phase P3b (docs/phase-p3/design-prevention.md §8).

``router`` serves the portal and the app (members of the institution), ``staff_router`` the dashboard (scope-bound).
"""

import uuid
from typing import Annotated, Literal, get_args

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.core.storage import get_store
from app.modules.audit import service as audit
from app.modules.audit.service import actor_of
from app.modules.orgs import certificate, prevention, schemas, service
from app.modules.orgs.domain import OrgRole
from app.modules.orgs.models import PreventionReservation, PreventionVisit
from app.modules.orgs.router import delete_objects
from app.modules.orgs.service import CurrentUser
from app.modules.orgs.staff_router import ORG_READ_ROLES, _org_in_scope

router = APIRouter(prefix="/api/v1", tags=["institutions"])
staff_router = APIRouter(prefix="/api/v1/staff", tags=["staff-institutions"])

Session = Annotated[AsyncSession, Depends(get_session)]
OrgReader = Annotated[Principal, Depends(require_roles(*ORG_READ_ROLES))]
Auditor = Annotated[Principal, Depends(require_roles(Role.ORG_AUDITOR))]
VisitState = Literal["requested", "scheduled", "inspected", "decided", "cancelled"]


async def _member_visit(session: AsyncSession, org_id: uuid.UUID, visit_id: uuid.UUID) -> PreventionVisit:
    visit = await session.scalar(
        select(PreventionVisit)
        .where(PreventionVisit.id == visit_id, PreventionVisit.org_id == org_id)
        .with_for_update()
    )
    if visit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return visit


def _report_url(visit: PreventionVisit) -> schemas.DownloadOut:
    if visit.report_object_key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return schemas.DownloadOut(url=get_store().presign_get(visit.report_object_key, content_type=prevention.PDF_TYPE))


# ---------------------------------------------------------------- portal and app


@router.get("/orgs/{org_id}/prevention/visits", response_model=list[schemas.VisitOut])
async def list_visits(org_id: uuid.UUID, user: CurrentUser, session: Session) -> list[schemas.VisitOut]:
    org, _ = await service.membership(session, user, org_id)
    out = await prevention.org_visits(session, org)
    await session.commit()
    return out


@router.post("/orgs/{org_id}/prevention/visits", response_model=schemas.VisitOut, status_code=status.HTTP_201_CREATED)
async def request_visit(
    org_id: uuid.UUID, body: schemas.VisitRequestIn, user: CurrentUser, session: Session
) -> schemas.VisitOut:
    """The institution asks for a prevention visit (F-POR-08); the Office schedules it."""
    org, _ = await service.membership(session, user, org_id, OrgRole.ADMIN, lock=True)
    visit = await prevention.request_visit(session, org, user, body.note)
    await audit.record(
        session, actor=user.actor, action="prevention.request", target=f"org:{org_id}", details={"visit": str(visit.id)}
    )
    await service.org_event(session, org_id)
    await session.commit()
    (out,) = await prevention.visit_views(session, org, [visit])
    return out


@router.post("/orgs/{org_id}/prevention/visits/{visit_id}/cancel", response_model=schemas.VisitOut)
async def withdraw_request(
    org_id: uuid.UUID, visit_id: uuid.UUID, body: schemas.VisitCancelIn, user: CurrentUser, session: Session
) -> schemas.VisitOut:
    org, _ = await service.membership(session, user, org_id, OrgRole.ADMIN)
    visit = await _member_visit(session, org_id, visit_id)
    await prevention.cancel(visit, user.actor, body.reason, by_office=False)
    await audit.record(
        session,
        actor=user.actor,
        action="prevention.withdraw",
        target=f"org:{org_id}",
        details={"visit": str(visit_id)},
    )
    await service.org_event(session, org_id)
    await session.commit()
    (out,) = await prevention.visit_views(session, org, [visit])
    return out


@router.get("/orgs/{org_id}/prevention/visits/{visit_id}/report", response_model=schemas.DownloadOut)
async def visit_report(
    org_id: uuid.UUID, visit_id: uuid.UUID, user: CurrentUser, session: Session
) -> schemas.DownloadOut:
    await service.membership(session, user, org_id)
    visit = await _member_visit(session, org_id, visit_id)
    await session.commit()
    return _report_url(visit)


@router.post("/orgs/{org_id}/prevention/reservations/{reservation_id}/response", response_model=schemas.ReservationOut)
async def respond_reservation(
    org_id: uuid.UUID,
    reservation_id: uuid.UUID,
    body: schemas.ReservationResponseIn,
    user: CurrentUser,
    session: Session,
) -> schemas.ReservationOut:
    """The institution says how it met a reservation; the auditor then lifts it."""
    await service.membership(session, user, org_id, OrgRole.EDITOR)
    item = await session.get(PreventionReservation, reservation_id, with_for_update=True)
    if item is None or item.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    prevention.respond(item, user, body.note)
    await audit.record(
        session,
        actor=user.actor,
        action="prevention.reservation_response",
        target=f"org:{org_id}",
        details={"reservation": str(reservation_id)},
    )
    await service.org_event(session, org_id)
    await session.commit()
    return prevention.reservation_out(item, service.today())


@router.get("/orgs/{org_id}/annual-report", response_model=schemas.AnnualReport)
async def annual_report(
    org_id: uuid.UUID, user: CurrentUser, session: Session, year: Annotated[int, Query(ge=2000, le=2100)]
) -> schemas.AnnualReport:
    org, _ = await service.membership(session, user, org_id)
    out = await prevention.annual_report(session, org, year)
    await session.commit()
    return out


# ---------------------------------------------------------------- dashboard


@staff_router.get("/prevention/visits", response_model=schemas.StaffVisitPage)
async def visit_queue(
    principal: OrgReader,
    session: Session,
    status_: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> schemas.StaffVisitPage:
    """Visits in scope, newest first; ``status`` is a comma-separated list."""
    statuses = [s.strip() for s in (status_ or "").split(",") if s.strip()]
    if any(s not in get_args(VisitState) for s in statuses):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_status")
    items, next_cursor = await prevention.staff_queue(session, principal, statuses, limit, cursor)
    return schemas.StaffVisitPage(items=items, next_cursor=next_cursor)


@staff_router.get("/orgs/{org_id}/prevention/visits", response_model=list[schemas.VisitOut])
async def org_visits(principal: OrgReader, session: Session, org_id: uuid.UUID) -> list[schemas.VisitOut]:
    org = await _org_in_scope(session, principal, org_id)
    return await prevention.org_visits(session, org)


@staff_router.post(
    "/orgs/{org_id}/prevention/visits", response_model=schemas.StaffVisit, status_code=status.HTTP_201_CREATED
)
async def schedule_visit(
    principal: Auditor, session: Session, org_id: uuid.UUID, body: schemas.VisitScheduleIn
) -> schemas.StaffVisit:
    """The Office schedules a visit without a request (F-POR-08: «زيارة مبرمجة»)."""
    org = await _org_in_scope(session, principal, org_id, lock=True)
    actor = actor_of(principal)
    visit = await prevention.schedule_new(session, org, body, actor)
    await audit.record(
        session,
        actor=actor,
        action="prevention.schedule",
        target=f"org:{org_id}",
        details={"visit": str(visit.id), "scheduled_on": str(visit.scheduled_on)},
    )
    await prevention.notify_admins(session, org, visit, "scheduled")
    await service.org_event(session, org_id)
    await session.commit()
    return await prevention.staff_view(session, visit, org)


@staff_router.get("/prevention/visits/{visit_id}", response_model=schemas.StaffVisit)
async def get_visit(principal: OrgReader, session: Session, visit_id: uuid.UUID) -> schemas.StaffVisit:
    visit, org = await prevention.scoped_visit(session, principal, visit_id)
    return await prevention.staff_view(session, visit, org)


@staff_router.post("/prevention/visits/{visit_id}/schedule", response_model=schemas.StaffVisit)
async def schedule_request(
    principal: Auditor, session: Session, visit_id: uuid.UUID, body: schemas.VisitScheduleIn
) -> schemas.StaffVisit:
    visit, org = await prevention.scoped_visit(session, principal, visit_id, lock=True)
    actor = actor_of(principal)
    await prevention.schedule(session, visit, body, actor)
    await audit.record(
        session,
        actor=actor,
        action="prevention.schedule",
        target=f"org:{org.id}",
        details={"visit": str(visit_id), "scheduled_on": str(visit.scheduled_on)},
    )
    await prevention.notify_admins(session, org, visit, "scheduled")
    await service.org_event(session, org.id)
    await session.commit()
    return await prevention.staff_view(session, visit, org)


@staff_router.post("/prevention/visits/{visit_id}/inspection", response_model=schemas.StaffVisit)
async def record_inspection(
    principal: Auditor, session: Session, visit_id: uuid.UUID, body: schemas.InspectionIn
) -> schemas.StaffVisit:
    """The grid filled on site; the server computes the comparison report and renders the visit report."""
    visit, org = await prevention.scoped_visit(session, principal, visit_id, lock=True)
    actor = actor_of(principal)
    stale = await prevention.inspect(session, visit, org, body, actor, audit.name_of(principal))
    comparison = visit.comparison or {}
    await audit.record(
        session,
        actor=actor,
        action="prevention.inspection",
        target=f"org:{org.id}",
        details={
            "visit": str(visit_id),
            "inspected_on": str(visit.inspected_on),
            "conform": comparison.get("conform"),
            "nonconform": comparison.get("nonconform"),
        },
    )
    await service.org_event(session, org.id)
    await session.commit()
    await delete_objects(*stale)
    return await prevention.staff_view(session, visit, org)


@staff_router.post("/prevention/visits/{visit_id}/decision", response_model=schemas.StaffVisit)
async def decide_visit(
    principal: Auditor, session: Session, visit_id: uuid.UUID, body: schemas.VisitDecisionIn
) -> schemas.StaffVisit:
    visit, org = await prevention.scoped_visit(session, principal, visit_id, lock=True)
    actor = actor_of(principal)
    issued, stale = await prevention.decide(session, visit, org, body, actor, audit.name_of(principal))
    await audit.record(
        session,
        actor=actor,
        action="prevention.decision",
        target=f"org:{org.id}",
        reason=visit.decision_reason,
        details={
            "visit": str(visit_id),
            "decision": body.decision,
            "reservations": len(body.reservations),
            "code": issued.code if issued else None,
        },
    )
    if issued is not None:
        await certificate.certificate_event(session, issued)
    await prevention.notify_admins(session, org, visit, "decided")
    await service.org_event(session, org.id)
    await session.commit()
    await delete_objects(*stale)
    return await prevention.staff_view(session, visit, org)


@staff_router.post("/prevention/visits/{visit_id}/cancel", response_model=schemas.StaffVisit)
async def cancel_visit(
    principal: Auditor, session: Session, visit_id: uuid.UUID, body: schemas.VisitCancelIn
) -> schemas.StaffVisit:
    visit, org = await prevention.scoped_visit(session, principal, visit_id, lock=True)
    actor = actor_of(principal)
    await prevention.cancel(visit, actor, body.reason, by_office=True)
    await audit.record(
        session,
        actor=actor,
        action="prevention.cancel",
        target=f"org:{org.id}",
        reason=visit.cancel_reason,
        details={"visit": str(visit_id)},
    )
    await service.org_event(session, org.id)
    await session.commit()
    return await prevention.staff_view(session, visit, org)


@staff_router.get("/prevention/visits/{visit_id}/report", response_model=schemas.DownloadOut)
async def staff_visit_report(principal: OrgReader, session: Session, visit_id: uuid.UUID) -> schemas.DownloadOut:
    visit, _ = await prevention.scoped_visit(session, principal, visit_id)
    return _report_url(visit)


@staff_router.post("/prevention/reservations/{reservation_id}/lift", response_model=schemas.ReservationOut)
async def lift_reservation(
    principal: Auditor, session: Session, reservation_id: uuid.UUID, body: schemas.ReservationLiftIn
) -> schemas.ReservationOut:
    item, org = await prevention.scoped_reservation(session, principal, reservation_id)
    actor = actor_of(principal)
    prevention.lift(item, actor, audit.name_of(principal), body.note)
    await audit.record(
        session,
        actor=actor,
        action="prevention.reservation_lift",
        target=f"org:{org.id}",
        details={"reservation": str(reservation_id), "visit": str(item.visit_id)},
    )
    await service.org_event(session, org.id)
    await session.commit()
    return prevention.reservation_out(item, service.today())
