"""Disaster and crisis axis endpoints (phase L3, docs/phase-l/design-l3.md).

The operations rooms work an axis (attach interventions, shelters, evacuations, needs, situation reports, the status
of the decisions addressed to them); the commander (national operations manager) opens, escalates and closes axes
and decides declaration requests; the governor and the minister read the declared axes and issue signed
recommendations and decisions. Governors and ministers never see an intervention that is not attached to an axis, nor
a reporter, a phone number or a victim's identity.
"""

import json
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.crisis import domain, schemas, service
from app.modules.crisis.models import (
    Axis,
    AxisEvent,
    DeclarationRequest,
    Directive,
    Evacuation,
    Need,
    Shelter,
    Sitrep,
)
from app.modules.geo.models import Gouvernorat
from app.modules.layers.service import point as wkt_point
from app.modules.register import plans as register_plans
from app.modules.register import service as register
from app.modules.register.models import Document as RegisterDocument
from app.modules.settings import service as settings

router = APIRouter(prefix="/api/v1/staff/crisis", tags=["staff", "crisis"])
Session = Annotated[AsyncSession, Depends(get_session)]
_Reader = Annotated[
    Principal,
    Depends(
        require_roles(
            Role.OPERATOR,
            Role.OPS_MANAGER,
            Role.GOVERNOR,
            Role.MINISTER,
            Role.LOCAL_COMMITTEE,
            Role.CENTRAL_COMMITTEE,
        )
    ),
]
# The disasters one view may show at once (phase N).
# The disasters chosen at once: the setting ``crisis.disaster_map_max`` (phase N §9), never above its bound.
DISASTER_MAP_CEILING = 100
TIMELINE_LIMIT = 200
CACHE_HEADER = "private, max-age=3600"


async def reader(principal: _Reader) -> Principal:
    if not domain.reads(principal):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient_role")
    return principal


Reader = Annotated[Principal, Depends(reader)]


def _require(allowed: bool, detail: str = "insufficient_role") -> None:
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail)


def _open(axis: Axis) -> None:
    if axis.status != "open":
        raise service.conflict("axis_closed")


def _version(axis: Axis, version: int) -> None:
    if axis.version != version:
        raise service.conflict("version_conflict")


def _doc_ref(doc: RegisterDocument) -> schemas.DocRef:
    return schemas.DocRef(
        id=str(doc.id), number=doc.number, reference=doc.reference, title=doc.title, kind=doc.kind, status=doc.status
    )


async def _plan_document(session: AsyncSession, principal: Principal, axis: Axis) -> schemas.DocRef | None:
    if axis.plan_document_id is None:
        return None
    doc = await session.get(RegisterDocument, axis.plan_document_id)
    return _doc_ref(doc) if doc is not None and register.readable(principal, doc) else None


async def _axis_out(
    session: AsyncSession, principal: Principal, axis: Axis, names: dict[int, str], *, children: bool = True
) -> schemas.AxisOut:
    members = await service.family(session, axis) if children and axis.scope == "national" else [axis]
    areas = await service.geojson(session, Axis, [axis.id])
    kids = [await _axis_out(session, principal, child, names, children=False) for child in members[1:]]
    codes = sorted({c for c in [axis.gouvernorat_code, *(k.gouvernorat_code for k in kids)] if c is not None})
    return schemas.AxisOut(
        id=str(axis.id),
        number=axis.number,
        name=axis.name,
        kind=axis.kind,
        scope=axis.scope,
        parent_id=str(axis.parent_id) if axis.parent_id else None,
        gouvernorat_code=axis.gouvernorat_code,
        gouvernorat_name=names.get(axis.gouvernorat_code) if axis.gouvernorat_code else None,
        gouvernorats=codes,
        area=areas.get(axis.id),
        level=axis.level,
        plan=axis.plan,
        plan_document=await _plan_document(session, principal, axis),
        hazard_plans=[_doc_ref(d) for d in await register_plans.for_axis(session, principal, axis.kind, codes)]
        if children
        else [],
        status=axis.status,
        opened_by_name=axis.opened_by_name if domain.is_room(principal) else None,
        opened_at=axis.opened_at,
        closed_by_name=axis.closed_by_name if domain.is_room(principal) else None,
        closed_at=axis.closed_at,
        closing=axis.closing,
        next_sitrep_at=axis.next_sitrep_at,
        memory_id=str(axis.memory_id) if axis.memory_id else None,
        version=axis.version,
        figures=await service.figures(session, [m.id for m in members]),
        children=kids,
        can_manage=axis.status == "open" and domain.can_manage_axis(principal, axis.gouvernorat_code),
        can_command=axis.status == "open" and domain.is_commander(principal),
        can_issue=axis.status == "open" and domain.can_issue(principal, axis.gouvernorat_code),
    )


async def _top_axes(session: AsyncSession, state: str) -> list[Axis]:
    """Roots and regional axes; a sub-axis is listed alone when its root is hidden (never: the root is visible to
    every gouvernorat of its sub-axes) or listed under it."""
    axes = list(
        await session.scalars(
            select(Axis).where(Axis.status == state).order_by(Axis.level.desc(), Axis.opened_at.desc())
        )
    )
    visible = {a.id for a in axes}
    return [a for a in axes if a.parent_id is None or a.parent_id not in visible]


def _need_out(n: Need) -> schemas.NeedOut:
    return schemas.NeedOut(
        id=str(n.id),
        axis_id=str(n.axis_id),
        label=n.label,
        quantity=n.quantity,
        status=n.status,
        created_by_name=n.created_by_name,
        created_at=n.created_at,
        met_at=n.met_at,
    )


async def _shelters_out(session: AsyncSession, axis_ids: list[uuid.UUID]) -> list[schemas.ShelterOut]:
    lat = func.ST_Y(cast(Shelter.location, Geometry))
    lon = func.ST_X(cast(Shelter.location, Geometry))
    rows = await session.execute(select(Shelter, lat, lon).where(Shelter.axis_id.in_(axis_ids)).order_by(Shelter.name))
    return [
        schemas.ShelterOut(
            id=str(s.id),
            axis_id=str(s.axis_id),
            name=s.name,
            lat=y,
            lon=x,
            capacity=s.capacity,
            occupants=s.occupants,
            updated_at=s.updated_at,
        )
        for s, y, x in rows.all()
    ]


async def _evacuations_out(session: AsyncSession, axis_ids: list[uuid.UUID]) -> list[schemas.EvacuationOut]:
    items = list(
        await session.scalars(select(Evacuation).where(Evacuation.axis_id.in_(axis_ids)).order_by(Evacuation.name))
    )
    areas = await service.geojson(session, Evacuation, [e.id for e in items])
    return [
        schemas.EvacuationOut(
            id=str(e.id),
            axis_id=str(e.axis_id),
            name=e.name,
            area=areas.get(e.id),
            evacuated=e.evacuated,
            updated_at=e.updated_at,
        )
        for e in items
    ]


async def _directives(session: AsyncSession, principal: Principal, axes: list[Axis]) -> list[schemas.DirectiveOut]:
    by_id = {a.id: a for a in axes}
    items = list(
        await session.scalars(
            select(Directive).where(Directive.axis_id.in_(list(by_id))).order_by(Directive.issued_at.desc())
        )
    )
    return await service.directives_out(session, items, principal, by_id)


async def _sitreps(session: AsyncSession, principal: Principal, axis_ids: list[uuid.UUID]) -> list[schemas.SitrepOut]:
    query = select(Sitrep).where(Sitrep.axis_id.in_(axis_ids)).order_by(Sitrep.created_at.desc())
    if not domain.is_room(principal):
        # Governors and the minister read the reports the room sent, not its drafts.
        query = query.where(Sitrep.status == "sent")
    return [service.sitrep_out(s) for s in await session.scalars(query)]


# --- Axes -----------------------------------------------------------------------------------------------------------


@router.get("/axes", response_model=schemas.AxisList)
async def list_axes(
    principal: Reader, session: Session, state: Annotated[Literal["open", "closed"], Query(alias="status")] = "open"
) -> schemas.AxisList:
    names = await service.gouvernorat_names(session)
    return schemas.AxisList(
        items=[await _axis_out(session, principal, a, names) for a in await _top_axes(session, state)]
    )


@router.post("/axes", response_model=schemas.AxisOut, status_code=status.HTTP_201_CREATED)
async def open_axis(principal: Reader, session: Session, body: schemas.AxisIn) -> schemas.AxisOut:
    _require(domain.is_commander(principal))
    axis = await service.open_axis(session, principal, body)
    out = await _axis_out(session, principal, axis, await service.gouvernorat_names(session))
    await session.commit()
    return out


@router.get("/axes/{axis_id}", response_model=schemas.AxisDetail)
async def get_axis(principal: Reader, session: Session, axis_id: uuid.UUID) -> schemas.AxisDetail:
    axis = await service.get_axis(session, axis_id)
    members = await service.family(session, axis)
    ids = [m.id for m in members]
    names = await service.gouvernorat_names(session)
    needs = list(
        await session.scalars(select(Need).where(Need.axis_id.in_(ids)).order_by(Need.status, Need.created_at.desc()))
    )
    events = list(
        await session.scalars(
            select(AxisEvent)
            .where(AxisEvent.axis_id.in_(ids))
            .order_by(AxisEvent.at.desc(), AxisEvent.id.desc())
            .limit(TIMELINE_LIMIT)
        )
    )
    room = domain.is_room(principal)
    return schemas.AxisDetail(
        axis=await _axis_out(session, principal, axis, names),
        incidents=await service.incidents_out(session, ids, principal),
        shelters=await _shelters_out(session, ids),
        evacuations=await _evacuations_out(session, ids),
        needs=[_need_out(n) for n in needs],
        directives=await _directives(session, principal, members),
        sitreps=await _sitreps(session, principal, ids),
        timeline=[
            schemas.EventOut(at=e.at, actor_name=e.actor_name if room else None, kind=e.kind, payload=e.payload)
            for e in events
        ],
        documents=[_doc_ref(d) for d in await register.axis_documents(session, principal, ids)],
    )


@router.patch("/axes/{axis_id}", response_model=schemas.AxisOut)
async def update_axis(
    principal: Reader, session: Session, axis_id: uuid.UUID, body: schemas.AxisPatch
) -> schemas.AxisOut:
    axis = await service.get_axis(session, axis_id, lock=True)
    _open(axis)
    _require(domain.can_manage_axis(principal, axis.gouvernorat_code))
    _version(axis, body.version)
    changes: dict[str, object] = {}
    if body.level is not None and body.level != axis.level:
        _require(domain.is_commander(principal))
        changes["level"] = [axis.level, body.level]
        axis.level = body.level
        axis.next_sitrep_at = min(
            filter(
                None,
                [
                    axis.next_sitrep_at,
                    service.now() + domain.sitrep_period(await service.sitrep_hours(session), body.level),
                ],
            )
        )
    if body.name is not None and body.name != axis.name:
        _require(domain.is_commander(principal))
        changes["name"] = body.name
        axis.name = body.name
    if body.plan is not None and body.plan != axis.plan:
        changes["plan"] = True
        axis.plan = body.plan
    if body.clear_plan_document and axis.plan_document_id is not None:
        changes["plan_document"] = None
        axis.plan_document_id = None
    elif body.plan_document_id is not None and body.plan_document_id != axis.plan_document_id:
        plan_doc = await register.visible(session, principal, body.plan_document_id)
        if plan_doc.kind != "plan" or plan_doc.status != "in_force":
            raise service.conflict("not_a_plan_in_force")
        changes["plan_document"] = plan_doc.number
        axis.plan_document_id = plan_doc.id
    if body.area is not None:
        await service.check_area(session, body.area)
        axis.area = service.area_value(body.area)
        changes["area"] = True
    if changes:
        axis.version += 1
        axis.updated_at = service.now()
        await service.add_event(session, axis.id, principal, "updated", {**changes, "reason": body.reason or None})
        codes = await service.codes_of(session, axis)
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action="crisis.axis_updated",
            target=str(axis.id),
            reason=body.reason or None,
            details={"number": axis.number, **changes},
            gouvernorats=codes,
        )
        await service.notify(session, "updated", axis, codes)
    await session.flush()
    await session.refresh(axis)
    out = await _axis_out(session, principal, axis, await service.gouvernorat_names(session))
    await session.commit()
    return out


@router.post("/axes/{axis_id}/escalate", response_model=schemas.AxisOut)
async def escalate(
    principal: Reader, session: Session, axis_id: uuid.UUID, body: schemas.EscalateIn
) -> schemas.AxisOut:
    _require(domain.is_commander(principal))
    axis = await service.get_axis(session, axis_id, lock=True)
    root = await service.escalate(session, principal, axis, body.gouvernorats, body.reason)
    out = await _axis_out(session, principal, root, await service.gouvernorat_names(session))
    await session.commit()
    return out


@router.post("/axes/{axis_id}/close", response_model=schemas.AxisOut)
async def close(principal: Reader, session: Session, axis_id: uuid.UUID, body: schemas.CloseIn) -> schemas.AxisOut:
    _require(domain.is_commander(principal))
    axis = await service.get_axis(session, axis_id, lock=True)
    await service.close_axis(session, principal, axis, body.summary)
    out = await _axis_out(session, principal, axis, await service.gouvernorat_names(session))
    await session.commit()
    return out


# --- Interventions --------------------------------------------------------------------------------------------------


@router.get("/axes/{axis_id}/suggestions", response_model=schemas.IncidentList)
async def suggestions(principal: Reader, session: Session, axis_id: uuid.UUID) -> schemas.IncidentList:
    _require(domain.is_room(principal))
    axis = await service.get_axis(session, axis_id)
    return schemas.IncidentList(items=await service.suggestions(session, axis, principal))


@router.post("/axes/{axis_id}/incidents", status_code=status.HTTP_204_NO_CONTENT)
async def attach(principal: Reader, session: Session, axis_id: uuid.UUID, body: schemas.AttachIn) -> Response:
    """The room manager attaches; an operator proposes (the proposal goes to the timeline for the manager)."""
    _require(domain.is_room(principal))
    axis = await service.get_axis(session, axis_id, lock=True)
    _open(axis)
    if domain.can_manage_axis(principal, axis.gouvernorat_code):
        if await service.attach(session, principal, axis, body.incident_id):
            codes = await service.codes_of(session, axis)
            await audit.record(
                session,
                actor=audit.actor_of(principal),
                action="crisis.incident_attached",
                target=str(axis.id),
                details={"number": axis.number, "incident_id": str(body.incident_id)},
                gouvernorats=codes,
            )
            await service.notify(session, "updated", axis, codes)
    else:
        _require(principal.is_national or principal.gouvernorat_code == axis.gouvernorat_code, "out_of_scope")
        await service.add_event(
            session, axis.id, principal, "incident_proposed", {"incident_id": str(body.incident_id)}
        )
        await service.notify(
            session, "proposal", axis, await service.codes_of(session, axis), incident_id=str(body.incident_id)
        )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/axes/{axis_id}/incidents/{incident_id}/detach", status_code=status.HTTP_204_NO_CONTENT)
async def detach(
    principal: Reader, session: Session, axis_id: uuid.UUID, incident_id: uuid.UUID, body: schemas.DetachIn
) -> Response:
    axis = await service.get_axis(session, axis_id, lock=True)
    _open(axis)
    _require(domain.can_manage_axis(principal, axis.gouvernorat_code))
    await service.detach(session, principal, axis, incident_id, body.reason)
    codes = await service.codes_of(session, axis)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="crisis.incident_detached",
        target=str(axis.id),
        reason=body.reason,
        details={"number": axis.number, "incident_id": str(incident_id)},
        gouvernorats=codes,
    )
    await service.notify(session, "updated", axis, codes)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/axes/{axis_id}/suggestions/{incident_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss(principal: Reader, session: Session, axis_id: uuid.UUID, incident_id: uuid.UUID) -> Response:
    axis = await service.get_axis(session, axis_id)
    _require(domain.can_manage_axis(principal, axis.gouvernorat_code))
    await service.dismiss(session, principal, axis, incident_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Components -----------------------------------------------------------------------------------------------------


async def _managed(session: AsyncSession, principal: Principal, axis_id: uuid.UUID) -> Axis:
    axis = await service.get_axis(session, axis_id)
    _open(axis)
    _require(domain.can_manage_axis(principal, axis.gouvernorat_code))
    return axis


async def _component_changed(
    session: AsyncSession, principal: Principal, axis: Axis, kind: str, payload: dict[str, object]
) -> None:
    await service.add_event(session, axis.id, principal, kind, payload)
    await service.notify(session, "updated", axis, await service.codes_of(session, axis))


@router.post("/axes/{axis_id}/shelters", response_model=schemas.ShelterOut, status_code=status.HTTP_201_CREATED)
async def add_shelter(
    principal: Reader, session: Session, axis_id: uuid.UUID, body: schemas.ShelterIn
) -> schemas.ShelterOut:
    axis = await _managed(session, principal, axis_id)
    if body.occupants > body.capacity:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "occupants_over_capacity")
    shelter = Shelter(
        axis_id=axis.id,
        name=body.name,
        capacity=body.capacity,
        occupants=body.occupants,
        location=wkt_point(body.location.lat, body.location.lon) if body.location else None,
        updated_by=audit.actor_of(principal),
        updated_at=service.now(),
    )
    session.add(shelter)
    await session.flush()
    await _component_changed(session, principal, axis, "shelter_opened", {"name": body.name, "capacity": body.capacity})
    out = await _shelters_out(session, [axis.id])
    await session.commit()
    return next(s for s in out if s.id == str(shelter.id))


@router.patch("/axes/{axis_id}/shelters/{shelter_id}", response_model=schemas.ShelterOut)
async def update_shelter(
    principal: Reader, session: Session, axis_id: uuid.UUID, shelter_id: uuid.UUID, body: schemas.ShelterPatch
) -> schemas.ShelterOut:
    axis = await _managed(session, principal, axis_id)
    shelter = await session.scalar(
        select(Shelter).where(Shelter.id == shelter_id, Shelter.axis_id == axis.id).with_for_update()
    )
    if shelter is None:
        raise service.not_found("shelter_not_found")
    capacity = body.capacity if body.capacity is not None else shelter.capacity
    occupants = body.occupants if body.occupants is not None else shelter.occupants
    if occupants > capacity:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "occupants_over_capacity")
    shelter.capacity, shelter.occupants = capacity, occupants
    shelter.updated_by, shelter.updated_at = audit.actor_of(principal), service.now()
    await _component_changed(
        session, principal, axis, "shelter_updated", {"name": shelter.name, "occupants": occupants}
    )
    out = await _shelters_out(session, [axis.id])
    await session.commit()
    return next(s for s in out if s.id == str(shelter.id))


@router.post("/axes/{axis_id}/evacuations", response_model=schemas.EvacuationOut, status_code=status.HTTP_201_CREATED)
async def add_evacuation(
    principal: Reader, session: Session, axis_id: uuid.UUID, body: schemas.EvacuationIn
) -> schemas.EvacuationOut:
    axis = await _managed(session, principal, axis_id)
    await service.check_area(session, body.area)
    evacuation = Evacuation(
        axis_id=axis.id,
        name=body.name,
        area=service.area_value(body.area),
        evacuated=body.evacuated,
        updated_by=audit.actor_of(principal),
        updated_at=service.now(),
    )
    session.add(evacuation)
    await session.flush()
    await _component_changed(
        session, principal, axis, "evacuation_ordered", {"name": body.name, "evacuated": body.evacuated}
    )
    out = await _evacuations_out(session, [axis.id])
    await session.commit()
    return next(e for e in out if e.id == str(evacuation.id))


@router.patch("/axes/{axis_id}/evacuations/{evacuation_id}", response_model=schemas.EvacuationOut)
async def update_evacuation(
    principal: Reader, session: Session, axis_id: uuid.UUID, evacuation_id: uuid.UUID, body: schemas.EvacuationPatch
) -> schemas.EvacuationOut:
    axis = await _managed(session, principal, axis_id)
    evacuation = await session.scalar(
        select(Evacuation).where(Evacuation.id == evacuation_id, Evacuation.axis_id == axis.id).with_for_update()
    )
    if evacuation is None:
        raise service.not_found("evacuation_not_found")
    evacuation.evacuated = body.evacuated
    evacuation.updated_by, evacuation.updated_at = audit.actor_of(principal), service.now()
    await _component_changed(
        session, principal, axis, "evacuation_updated", {"name": evacuation.name, "evacuated": body.evacuated}
    )
    out = await _evacuations_out(session, [axis.id])
    await session.commit()
    return next(e for e in out if e.id == str(evacuation.id))


@router.post("/axes/{axis_id}/needs", response_model=schemas.NeedOut, status_code=status.HTTP_201_CREATED)
async def raise_need(principal: Reader, session: Session, axis_id: uuid.UUID, body: schemas.NeedIn) -> schemas.NeedOut:
    axis = await _managed(session, principal, axis_id)
    need = Need(
        axis_id=axis.id,
        label=body.label,
        quantity=body.quantity,
        status="raised",
        created_by=audit.actor_of(principal),
        created_by_name=audit.name_of(principal),
        created_at=service.now(),
    )
    session.add(need)
    await session.flush()
    await _component_changed(session, principal, axis, "need_raised", {"label": body.label, "quantity": body.quantity})
    out = _need_out(need)
    await session.commit()
    return out


@router.post("/axes/{axis_id}/needs/{need_id}/met", response_model=schemas.NeedOut)
async def need_met(principal: Reader, session: Session, axis_id: uuid.UUID, need_id: uuid.UUID) -> schemas.NeedOut:
    axis = await _managed(session, principal, axis_id)
    need = await session.scalar(select(Need).where(Need.id == need_id, Need.axis_id == axis.id).with_for_update())
    if need is None:
        raise service.not_found("need_not_found")
    if need.status != "met":
        need.status, need.met_at = "met", service.now()
        await _component_changed(session, principal, axis, "need_met", {"label": need.label})
    out = _need_out(need)
    await session.commit()
    return out


# --- Recommendations and decisions ----------------------------------------------------------------------------------


@router.post("/axes/{axis_id}/directives", response_model=schemas.DirectiveOut, status_code=status.HTTP_201_CREATED)
async def issue(
    principal: Reader, session: Session, axis_id: uuid.UUID, body: schemas.DirectiveIn
) -> schemas.DirectiveOut:
    axis = await service.get_axis(session, axis_id, lock=True)
    _require(domain.can_issue(principal, axis.gouvernorat_code))
    directive = await service.issue(session, principal, axis, body)
    out = (await service.directives_out(session, [directive], principal, {axis.id: axis}))[0]
    await session.commit()
    return out


@router.post("/directives/{directive_id}/status", response_model=schemas.DirectiveOut)
async def directive_status(
    principal: Reader, session: Session, directive_id: uuid.UUID, body: schemas.DirectiveStatusIn
) -> schemas.DirectiveOut:
    directive = await session.scalar(select(Directive).where(Directive.id == directive_id).with_for_update())
    if directive is None:
        raise service.not_found("directive_not_found")
    axis = await service.get_axis(session, directive.axis_id)
    _open(axis)
    _require(domain.can_update_directive(principal, directive.executor, axis.gouvernorat_code))
    await service.set_directive_status(session, principal, axis, directive, body.status, body.reason)
    out = (await service.directives_out(session, [directive], principal, {axis.id: axis}))[0]
    await session.commit()
    return out


# --- Situation reports ----------------------------------------------------------------------------------------------


@router.post("/axes/{axis_id}/sitreps", response_model=schemas.SitrepOut, status_code=status.HTTP_201_CREATED)
async def draft_sitrep(principal: Reader, session: Session, axis_id: uuid.UUID) -> schemas.SitrepOut:
    axis = await service.get_axis(session, axis_id)
    _open(axis)
    _require(domain.can_manage_axis(principal, axis.gouvernorat_code))
    pending = await session.scalar(select(Sitrep).where(Sitrep.axis_id == axis.id, Sitrep.status == "draft"))
    sitrep = pending or await service.draft_sitrep(session, principal, axis)
    out = service.sitrep_out(sitrep)
    await session.commit()
    return out


@router.post("/sitreps/{sitrep_id}/send", response_model=schemas.SitrepOut)
async def send_sitrep(
    principal: Reader, session: Session, sitrep_id: uuid.UUID, body: schemas.SitrepSend
) -> schemas.SitrepOut:
    sitrep = await session.scalar(select(Sitrep).where(Sitrep.id == sitrep_id).with_for_update())
    if sitrep is None:
        raise service.not_found("sitrep_not_found")
    axis = await service.get_axis(session, sitrep.axis_id, lock=True)
    _require(domain.can_manage_axis(principal, axis.gouvernorat_code))
    await service.send_sitrep(session, principal, axis, sitrep, body.assessment)
    out = service.sitrep_out(sitrep)
    await session.commit()
    return out


# --- Declaration requests -------------------------------------------------------------------------------------------


async def _requests_out(session: AsyncSession, items: list[DeclarationRequest]) -> list[schemas.RequestOut]:
    names = await service.gouvernorat_names(session)
    areas = await service.geojson(session, DeclarationRequest, [r.id for r in items])
    return [
        schemas.RequestOut(
            id=str(r.id),
            gouvernorat_code=r.gouvernorat_code,
            gouvernorat_name=names.get(r.gouvernorat_code),
            name=r.name,
            kind=r.kind,
            level=r.level,
            facts=r.facts,
            incident_ids=[str(i) for i in r.incident_ids],
            area=areas.get(r.id),
            status=r.status,
            created_by_name=r.created_by_name,
            created_at=r.created_at,
            decided_by_name=r.decided_by_name,
            decided_at=r.decided_at,
            decision_reason=r.decision_reason,
            axis_id=str(r.axis_id) if r.axis_id else None,
        )
        for r in items
    ]


@router.get("/requests", response_model=schemas.RequestList)
async def list_requests(
    principal: Reader,
    session: Session,
    state: Annotated[Literal["pending", "decided"], Query(alias="status")] = "pending",
) -> schemas.RequestList:
    _require(domain.is_room(principal))
    query = select(DeclarationRequest).order_by(DeclarationRequest.created_at.desc()).limit(100)
    query = (
        query.where(DeclarationRequest.status == "pending")
        if state == "pending"
        else query.where(DeclarationRequest.status != "pending")
    )
    return schemas.RequestList(items=await _requests_out(session, list(await session.scalars(query))))


@router.post("/requests", response_model=schemas.RequestOut, status_code=status.HTTP_201_CREATED)
async def create_request(principal: Reader, session: Session, body: schemas.RequestIn) -> schemas.RequestOut:
    _require(domain.is_room_manager(principal) and not principal.is_national and principal.gouvernorat_code is not None)
    request = await service.create_request(session, principal, body)
    out = (await _requests_out(session, [request]))[0]
    await session.commit()
    return out


@router.post("/requests/{request_id}/decide", response_model=schemas.RequestOut)
async def decide_request(
    principal: Reader, session: Session, request_id: uuid.UUID, body: schemas.DecideIn
) -> schemas.RequestOut:
    _require(domain.is_commander(principal))
    request = await session.scalar(
        select(DeclarationRequest).where(DeclarationRequest.id == request_id).with_for_update()
    )
    if request is None:
        raise service.not_found("request_not_found")
    if not body.accept and len(body.reason) < 5:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reason_required")
    await service.decide_request(session, principal, request, body.accept, body.reason)
    out = (await _requests_out(session, [request]))[0]
    await session.commit()
    return out


# --- Disasters (phase N) ---------------------------------------------------------------------------------------------


@router.get("/disasters/map", response_model=schemas.DisasterMap)
async def disaster_map(
    principal: Reader, session: Session, axis: Annotated[str, Query(max_length=DISASTER_MAP_CEILING * 37)] = ""
) -> schemas.DisasterMap:
    """The disaster view (docs/phase-n/design-n.md §3): the places of the chosen disasters only (their areas,
    interventions, shelters and evacuation zones) and their summed figures, for the rooms, the commander and the
    committees. Row-level security keeps a regional reader to the disasters of their gouvernorat."""
    try:
        axis_ids = [uuid.UUID(part) for part in axis.split(",") if part.strip()]
    except ValueError:
        axis_ids = []
    if not 0 < len(axis_ids) <= await settings.threshold(session, "crisis.disaster_map_max"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_selection")
    members: dict[uuid.UUID, Axis] = {}
    for chosen in await session.scalars(select(Axis).where(Axis.id.in_(axis_ids))):
        for member in await service.family(session, chosen):
            members.setdefault(member.id, member)
    ids = list(members)
    areas = await service.geojson(session, Axis, ids)
    return schemas.DisasterMap(
        figures=await service.figures(session, ids),
        areas=[schemas.DisasterArea(id=str(a.id), level=a.level, area=areas.get(a.id)) for a in members.values()],
        incidents=await service.incidents_out(session, ids, principal) if ids else [],
        shelters=await _shelters_out(session, ids),
        evacuations=await _evacuations_out(session, ids),
    )


# --- Command (governor, minister) -----------------------------------------------------------------------------------


@router.get("/command", response_model=schemas.CommandOverview)
async def command(principal: Reader, session: Session) -> schemas.CommandOverview:
    """The governor's and the minister's screen (design §6): the declared axes they see, the state of each
    gouvernorat, the open needs, their own decisions and the last situation reports. The rooms get the same view
    (the commander's national picture)."""
    role: Literal["governor", "minister"] = (
        "minister" if domain.is_minister(principal) or principal.is_national else "governor"
    )
    names = await service.gouvernorat_names(session)
    open_axes = list(await session.scalars(select(Axis).where(Axis.status == "open")))
    tops = await _top_axes(session, "open")
    axes_out = [await _axis_out(session, principal, a, names) for a in tops]
    closed = [
        await _axis_out(session, principal, a, names, children=False) for a in (await _top_axes(session, "closed"))[:10]
    ]
    states: list[schemas.GouvernoratState] = []
    for code in sorted({a.gouvernorat_code for a in open_axes if a.gouvernorat_code is not None}):
        mine = [a for a in open_axes if a.gouvernorat_code == code]
        f = await service.figures(session, [a.id for a in mine])
        states.append(
            schemas.GouvernoratState(
                code=code,
                name=names.get(code, str(code)),
                level=max(a.level for a in mine),
                axes=len(mine),
                incidents_open=f.incidents_open,
                resources=f.resources,
                weight=round(f.incidents_open / f.resources, 2)
                if f.resources
                else (float(f.incidents_open) if f.incidents_open else None),
                deceased=f.deceased,
                evacuated=f.evacuated,
                needs_open=f.needs_open,
            )
        )
    states.sort(key=lambda s: (-(s.level or 0), -(s.weight or 0)))
    ids = [a.id for a in open_axes]
    needs = list(
        await session.scalars(
            select(Need).where(Need.axis_id.in_(ids), Need.status == "raised").order_by(Need.created_at.desc())
        )
    )
    mine_query = select(Directive).where(Directive.axis_id.in_(ids)).order_by(Directive.issued_at.desc()).limit(50)
    if domain.issuer_role(principal):
        mine_query = mine_query.where(Directive.issued_by == audit.actor_of(principal))
    directives = await service.directives_out(
        session, list(await session.scalars(mine_query)), principal, {a.id: a for a in open_axes}
    )
    sitreps = (await _sitreps(session, principal, ids))[:10]
    return schemas.CommandOverview(
        role=role,
        gouvernorat_code=principal.gouvernorat_code,
        totals=await service.figures(session, [a.id for a in tops] + [a.id for a in open_axes if a.parent_id]),
        axes=axes_out,
        gouvernorats=states,
        needs=[_need_out(n) for n in needs],
        directives=directives,
        sitreps=sitreps,
        closed=closed,
    )


@router.get("/boundaries")
async def boundaries(principal: Reader, session: Session, response: Response) -> dict[str, object]:
    """Gouvernorat outlines for the command maps (simplified; reference data)."""
    rows = await session.execute(
        select(
            Gouvernorat.code,
            Gouvernorat.name_ar,
            Gouvernorat.name_fr,
            Gouvernorat.name_en,
            func.ST_AsGeoJSON(func.ST_SimplifyPreserveTopology(Gouvernorat.boundary, 0.005), 5),
        ).where(Gouvernorat.boundary.isnot(None))
    )
    response.headers["Cache-Control"] = CACHE_HEADER
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": code,
                "properties": {"code": code, "name_ar": ar, "name_fr": fr, "name_en": en},
                "geometry": json.loads(g),
            }
            for code, ar, fr, en, g in rows.all()
        ],
    }
