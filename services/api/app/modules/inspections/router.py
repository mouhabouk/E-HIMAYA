"""Periodic inspections endpoints, phase I1 (docs/phase-i/design-i.md).

* ``/api/v1/staff/inspections``: the general inspectorate (``inspector_general``): the calculation model, the notes of
  the mission orders, the disclosure policy, the inspectors' accounts, the mission orders and their PDF, the reports,
  what each room reads of them, the dashboard and the state of every place.
* ``/api/v1/staff/inspection-results``: the operations rooms (``operator``, ``ops_manager``) read what is disclosed of
  the inspections of the rooms only (Yamen 2026-11-11): a regional room its own room's, the central room every room's.
  The inspections in progress and the programme are the central room's only.
* ``/api/v1/staff/inspection-admin``: the system administrator deletes reports (reason, confirm word) and restores them.
* ``/api/v1/inspect``: the inspector's app: registration and activation are open (rate limited); the rest needs the
  app's own token (roles ``inspector`` and ``inspector_external``).
* ``/api/v1/verify/om/{ref}``: the QR code of a mission order, open to anyone.
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import ratelimit
from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit.service import name_of
from app.modules.inspections import schemas, service
from app.modules.inspections.models import Mission
from app.modules.orgs import certificate

router = APIRouter(prefix="/api/v1/staff/inspections", tags=["staff", "inspections"])
rooms_router = APIRouter(prefix="/api/v1/staff/inspection-results", tags=["staff", "inspections"])
admin_router = APIRouter(prefix="/api/v1/staff/inspection-admin", tags=["staff", "inspections"])
app_router = APIRouter(prefix="/api/v1/inspect", tags=["inspections"])
public_router = APIRouter(prefix="/api/v1/verify", tags=["inspections"])

Session = Annotated[AsyncSession, Depends(get_session)]
General = Annotated[Principal, Depends(require_roles(Role.INSPECTOR_GENERAL))]
Room = Annotated[Principal, Depends(require_roles(Role.OPERATOR, Role.OPS_MANAGER))]
Admin = Annotated[Principal, Depends(require_roles(Role.SYSADMIN))]
InspectorApp = Annotated[Principal, Depends(require_roles(Role.INSPECTOR, Role.INSPECTOR_EXTERNAL))]

#: Registrations, activations and refreshes tried from one address in an hour.
REGISTRATIONS_PER_HOUR = 10
ACTIVATIONS_PER_HOUR = 20
REFRESHES_PER_HOUR = 120
VERIFICATIONS_PER_HOUR = 120


# ---------------------------------------------------------------- settings


@router.get("/profile", response_model=schemas.ProfileOut)
async def get_profile(_: General, session: Session) -> schemas.ProfileOut:
    return service.profile_out(await service.active_profile(session))


@router.put("/profile", response_model=schemas.ProfileOut)
async def put_profile(principal: General, session: Session, body: schemas.ProfileIn) -> schemas.ProfileOut:
    out = await service.save_profile(session, principal, body)
    await session.commit()
    return out


@router.get("/order-notes", response_model=schemas.OrderNotesOut)
async def get_order_notes(_: General, session: Session) -> schemas.OrderNotesOut:
    return schemas.OrderNotesOut(notes=await service.order_notes(session))


@router.put("/order-notes", response_model=schemas.OrderNotesOut)
async def put_order_notes(principal: General, session: Session, body: schemas.OrderNotesIn) -> schemas.OrderNotesOut:
    notes = await service.save_order_notes(session, principal, body.notes)
    await session.commit()
    return schemas.OrderNotesOut(notes=notes)


@router.get("/policy", response_model=schemas.PolicyOut)
async def get_policy(_: General, session: Session) -> schemas.PolicyOut:
    return service.policy_out(await service.policy(session))


@router.put("/policy", response_model=schemas.PolicyOut)
async def put_policy(principal: General, session: Session, body: schemas.PolicyIn) -> schemas.PolicyOut:
    out = await service.save_policy(session, principal, body)
    await session.commit()
    return out


@router.post("/policy/apply", response_model=schemas.DeleteOut)
async def apply_policy(principal: General, session: Session) -> schemas.DeleteOut:
    """Apply the policy to the rooms' reports already sent (the count of reports changed)."""
    count = await service.apply_policy(session, principal)
    await session.commit()
    return schemas.DeleteOut(deleted=count)


# ---------------------------------------------------------------- the inspectors' accounts


@router.get("/inspectors", response_model=list[schemas.InspectorOut])
async def list_inspectors(
    _: General, session: Session, state: Annotated[schemas.InspectorStatus | None, Query()] = None
) -> list[schemas.InspectorOut]:
    return await service.inspectors(session, state)


@router.post("/inspectors/{inspector_id}/activate", response_model=schemas.InspectorOut)
async def activate_account(
    principal: General, session: Session, inspector_id: uuid.UUID, body: schemas.ActivateIn
) -> schemas.InspectorOut:
    out = await service.activate_account(session, principal, inspector_id, body)
    await session.commit()
    return out


@router.post("/inspectors/{inspector_id}/reject", response_model=schemas.InspectorOut)
async def reject_account(
    principal: General, session: Session, inspector_id: uuid.UUID, body: schemas.RejectIn
) -> schemas.InspectorOut:
    out = await service.reject_account(session, principal, inspector_id, body.reason)
    await session.commit()
    return out


@router.post("/inspectors/{inspector_id}/code", response_model=schemas.InspectorOut)
async def renew_code(principal: General, session: Session, inspector_id: uuid.UUID) -> schemas.InspectorOut:
    out = await service.renew_code(session, principal, inspector_id)
    await session.commit()
    return out


@router.post("/inspectors/{inspector_id}/lost", response_model=schemas.InspectorOut)
async def report_lost(principal: General, session: Session, inspector_id: uuid.UUID) -> schemas.InspectorOut:
    out = await service.report_lost(session, principal, inspector_id)
    await session.commit()
    return out


@router.post("/inspectors/{inspector_id}/close", response_model=schemas.InspectorOut)
async def close_account(principal: General, session: Session, inspector_id: uuid.UUID) -> schemas.InspectorOut:
    out = await service.close_account(session, principal, inspector_id)
    await session.commit()
    return out


# ---------------------------------------------------------------- mission orders


@router.get("/missions", response_model=list[schemas.MissionOut])
async def list_missions(
    _: General,
    session: Session,
    from_date: date | None = None,
    to_date: date | None = None,
    inspector_id: uuid.UUID | None = None,
) -> list[schemas.MissionOut]:
    return await service.list_missions(session, from_date, to_date, inspector_id)


@router.post("/missions", response_model=schemas.MissionOut, status_code=status.HTTP_201_CREATED)
async def create_mission(principal: General, session: Session, body: schemas.MissionIn) -> schemas.MissionOut:
    out = await service.create_mission(session, principal, body)
    await session.commit()
    return out


@router.post("/missions/{mission_id}/cancel", response_model=schemas.MissionOut)
async def cancel_mission(
    principal: General, session: Session, mission_id: uuid.UUID, body: schemas.CancelIn
) -> schemas.MissionOut:
    out = await service.cancel_mission(session, principal, mission_id, body.reason)
    await session.commit()
    return out


@router.get("/missions/{mission_id}/order.pdf", response_class=Response)
async def order_pdf(principal: General, session: Session, mission_id: uuid.UUID) -> Response:
    mission = await session.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    data = await certificate.render_document_pdf(await service.order_html(session, mission, name_of(principal)))
    return Response(
        data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{mission.ref}.pdf"', "Cache-Control": "no-store"},
    )


# ---------------------------------------------------------------- reports


@router.get("/records", response_model=list[schemas.RecordRow])
async def list_records(
    _: General,
    session: Session,
    gouvernorat_code: Annotated[int | None, Query(ge=1, le=99)] = None,
    target: schemas.Target | None = None,
    kind: schemas.Kind | None = None,
    inspector_id: uuid.UUID | None = None,
    unit_kind: schemas.UnitKind | None = None,
    search: Annotated[str | None, Query(max_length=80)] = None,
    from_date: date | None = None,
    to_date: date | None = None,
    verdict: Annotated[str | None, Query(max_length=40)] = None,
) -> list[schemas.RecordRow]:
    return await service.records(
        session,
        gouvernorat_code=gouvernorat_code,
        target=target,
        kind=kind,
        inspector_id=inspector_id,
        unit_kind=unit_kind,
        search=search,
        from_date=from_date,
        to_date=to_date,
        verdict=verdict,
    )


@router.get("/records/{inspection_id}", response_model=schemas.RecordOut)
async def get_record(_: General, session: Session, inspection_id: uuid.UUID) -> schemas.RecordOut:
    return await service.record(session, inspection_id)


@router.put("/records/{inspection_id}/disclosure", response_model=schemas.RecordOut)
async def set_disclosure(
    principal: General, session: Session, inspection_id: uuid.UUID, body: schemas.DisclosureIn
) -> schemas.RecordOut:
    out = await service.set_disclosure(session, principal, inspection_id, body)
    await session.commit()
    return out


@router.put("/records/{inspection_id}/audience", response_model=schemas.RecordOut)
async def set_audience(
    principal: General, session: Session, inspection_id: uuid.UUID, body: schemas.AudienceIn
) -> schemas.RecordOut:
    out = await service.set_audience(session, principal, inspection_id, body)
    await session.commit()
    return out


@router.get("/dashboard", response_model=schemas.DashboardOut)
async def dashboard(_: General, session: Session) -> schemas.DashboardOut:
    return await service.dashboard(session)


@router.get("/places", response_model=list[schemas.UnitStatusOut])
async def places(
    _: General, session: Session, gouvernorat_code: Annotated[int | None, Query(ge=1, le=99)] = None
) -> list[schemas.UnitStatusOut]:
    return await service.unit_status(session, gouvernorat_code)


# ---------------------------------------------------------------- the operations rooms


@rooms_router.get("", response_model=list[schemas.RoomResultOut])
async def room_results(principal: Room, session: Session) -> list[schemas.RoomResultOut]:
    return await service.room_results(session, principal)


@rooms_router.get("/live", response_model=list[schemas.RoomLiveOut])
async def room_live(principal: Room, session: Session) -> list[schemas.RoomLiveOut]:
    return await service.room_live(session, principal)


@rooms_router.get("/upcoming", response_model=list[schemas.RoomUpcomingOut])
async def room_upcoming(principal: Room, session: Session) -> list[schemas.RoomUpcomingOut]:
    return await service.room_upcoming(session, principal)


# ---------------------------------------------------------------- the system administrator


@admin_router.post("/delete", response_model=schemas.DeleteOut)
async def delete_records(principal: Admin, session: Session, body: schemas.DeleteIn) -> schemas.DeleteOut:
    count = await service.delete_records(session, principal, body)
    await session.commit()
    return schemas.DeleteOut(deleted=count)


@admin_router.get("/bin", response_model=list[schemas.BinRow])
async def bin_rows(_: Admin, session: Session) -> list[schemas.BinRow]:
    return await service.bin_rows(session)


@admin_router.post("/bin/{inspection_id}/restore", status_code=status.HTTP_204_NO_CONTENT)
async def restore(principal: Admin, session: Session, inspection_id: uuid.UUID) -> Response:
    await service.restore(session, principal, inspection_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- the inspector's app


@app_router.post("/register", response_model=schemas.RegisterOut, status_code=status.HTTP_201_CREATED)
async def register(request: Request, session: Session, body: schemas.RegisterIn) -> schemas.RegisterOut:
    await ratelimit.enforce(f"insp-register:{ratelimit.client_key(request)}", REGISTRATIONS_PER_HOUR, 3600)
    out = await service.register(session, body)
    await session.commit()
    return out


@app_router.post("/activate", response_model=schemas.AppTokens)
async def app_activate(request: Request, session: Session, body: schemas.AppActivateIn) -> schemas.AppTokens:
    await ratelimit.enforce(f"insp-activate:{ratelimit.client_key(request)}", ACTIVATIONS_PER_HOUR, 3600)
    out = await service.app_activate(session, body)
    await session.commit()
    return out


@app_router.post("/token", response_model=schemas.AppTokens)
async def app_refresh(request: Request, session: Session, body: schemas.AppRefreshIn) -> schemas.AppTokens:
    await ratelimit.enforce(f"insp-token:{ratelimit.client_key(request)}", REFRESHES_PER_HOUR, 3600)
    out = await service.app_refresh(session, body)
    await session.commit()
    return out


@app_router.get("/missions", response_model=list[schemas.AppMissionOut])
async def my_missions(principal: InspectorApp, session: Session) -> list[schemas.AppMissionOut]:
    inspector = await service.me(session, principal)
    return await service.my_missions(session, inspector)


@app_router.get("/inspections", response_model=list[schemas.AppHistoryRow])
async def my_inspections(principal: InspectorApp, session: Session) -> list[schemas.AppHistoryRow]:
    inspector = await service.me(session, principal)
    return await service.my_inspections(session, inspector)


@app_router.post("/inspections", response_model=schemas.AppInspectionOut)
async def start(principal: InspectorApp, session: Session, body: schemas.StartIn) -> schemas.AppInspectionOut:
    inspector = await service.me(session, principal)
    out = await service.start(session, inspector, body)
    await session.commit()
    return out


@app_router.post("/sites/{site_id}/presence", response_model=schemas.PresenceOut)
async def presence(
    principal: InspectorApp, session: Session, site_id: uuid.UUID, body: schemas.PresenceIn
) -> schemas.PresenceOut:
    inspector = await service.me(session, principal)
    out = await service.presence(session, inspector, site_id, body)
    await session.commit()
    return out


@app_router.put("/inspections/{inspection_id}", response_model=schemas.AppInspectionOut)
async def progress(
    principal: InspectorApp, session: Session, inspection_id: uuid.UUID, body: schemas.ProgressIn
) -> schemas.AppInspectionOut:
    inspector = await service.me(session, principal)
    out = await service.progress(session, inspector, inspection_id, body)
    await session.commit()
    return out


@app_router.post("/inspections/{inspection_id}/submit", response_model=schemas.ReceiptOut)
async def submit(
    principal: InspectorApp, session: Session, inspection_id: uuid.UUID, body: schemas.SubmitIn
) -> schemas.ReceiptOut:
    inspector = await service.me(session, principal)
    out = await service.submit(session, inspector, inspection_id, body)
    await session.commit()
    return out


# ---------------------------------------------------------------- the QR code of a mission order


@public_router.get("/om/{ref}", response_model=schemas.OrderVerifyOut)
async def verify_order(
    request: Request, session: Session, ref: Annotated[str, Path(pattern=r"^OM-[0-9]{4}-[0-9]{4,}$")]
) -> schemas.OrderVerifyOut:
    await ratelimit.enforce(f"insp-verify:{ratelimit.client_key(request)}", VERIFICATIONS_PER_HOUR, 3600)
    return await service.verify_order(session, ref)
