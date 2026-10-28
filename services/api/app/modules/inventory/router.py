"""Resources register endpoints (phase R1, docs/phase-r/design-resources.md §2).

Staff only. Each regional room keeps the register of its own gouvernorat (vehicles with their specifications,
equipment counted by quantity, staff with their specialities) and confirms each unit's figures every month; the central
room sees and keeps every gouvernorat and the national catalogue. Row level security (migration 0059) holds the same
rule in the database. The governor and the minister see the counts only; the names and phones of the staff are
returned to the operations rooms only, and exported by the room of their own gouvernorat only, every export audited.
"""

import csv
import io
import json
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from geoalchemy2 import Geometry
from sqlalchemy import and_, cast, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session, get_system_sessionmaker
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.geo.models import Gouvernorat
from app.modules.inventory import domain, schemas
from app.modules.inventory.models import Agent, AgentSkill, Category, InventoryRevision, Stock, UnitCheck
from app.modules.layers.domain import neutralize
from app.modules.ops import resources
from app.modules.ops.domain import ResourceKind
from app.modules.ops.models import Assignment, Resource, Unit
from app.modules.programmes.domain import FileError, normalize
from app.modules.reports.staff_router import READ_ROLES

router = APIRouter(prefix="/api/v1/staff/inventory", tags=["staff", "inventory"])
Session = Annotated[AsyncSession, Depends(get_session)]
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES, Role.SYSADMIN))]
Viewer = Annotated[Principal, Depends(require_roles(*READ_ROLES, Role.SYSADMIN, Role.GOVERNOR, Role.MINISTER))]
ROOM_ROLES = frozenset({Role.OPERATOR, Role.OPS_MANAGER})
NAME_ROLES = ROOM_ROLES | {Role.SYSADMIN}
LIST_ROLES = frozenset({*READ_ROLES, Role.SYSADMIN})
OLD_KINDS = frozenset(ResourceKind.__args__)  # type: ignore[attr-defined]
Entity = Literal["vehicles", "stock", "agents"]


# ---------------------------------------------------------------- who may do what


def can_manage_catalogue(principal: Principal) -> bool:
    return principal.is_national and bool({Role.SYSADMIN, Role.OPS_MANAGER} & set(principal.roles))


def can_edit(principal: Principal, gouvernorat: int | None = None) -> bool:
    """The operations manager of the gouvernorat (the central one: all), or the national system administrator."""
    if Role.SYSADMIN in principal.roles and principal.is_national:
        return True
    if Role.OPS_MANAGER not in principal.roles:
        return False
    return gouvernorat is None or principal.can_access_gouvernorat(gouvernorat)


def sees_names(principal: Principal) -> bool:
    return bool(NAME_ROLES & set(principal.roles))


def exports_names(principal: Principal, gouvernorat: int | None) -> bool:
    """Personal data leaves the system through the room that owns it only."""
    return (
        gouvernorat is not None
        and principal.gouvernorat_code == gouvernorat
        and bool(ROOM_ROLES & set(principal.roles))
    )


def _require_list(principal: Principal) -> None:
    if not LIST_ROLES & set(principal.roles):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "counts_only")


def _require_edit(principal: Principal, gouvernorat: int | None) -> None:
    if not can_edit(principal, gouvernorat):
        code = "out_of_scope" if can_edit(principal) else "insufficient_role"
        raise HTTPException(status.HTTP_403_FORBIDDEN, code)


def _reason(reason: str, *, required: bool = True) -> str | None:
    reason = reason.strip()
    if required and len(reason) < 5:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reason_required")
    return reason or None


def _now() -> datetime:
    return datetime.now(UTC)


def _scope(principal: Principal, column: Any) -> Any:
    return True if principal.is_national else column == principal.gouvernorat_code


def _gouvernorat(principal: Principal, wanted: int | None) -> int:
    """The gouvernorat of an import or a template: the caller's own, or the one the central room names."""
    if not principal.is_national:
        if wanted is not None and wanted != principal.gouvernorat_code:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
        assert principal.gouvernorat_code is not None
        return principal.gouvernorat_code
    if wanted is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "gouvernorat_required")
    return wanted


# ---------------------------------------------------------------- catalogue


def _category_out(c: Category) -> schemas.CategoryOut:
    return schemas.CategoryOut(
        key=c.key,
        kind=c.kind,
        family=c.family,
        name=c.name,
        specs=[schemas.SpecDef(**s) for s in c.specs],
        levels=c.levels,
        position=c.position,
        active=c.active,
    )


def _ref(c: Category) -> domain.CategoryRef:
    return domain.CategoryRef(
        key=c.key,
        kind=c.kind,
        specs=tuple((s["key"], s.get("type", "number")) for s in c.specs),
        levels=c.levels,
        active=c.active,
    )


async def _categories(session: AsyncSession) -> list[Category]:
    return list((await session.scalars(select(Category).order_by(Category.kind, Category.position))).all())


async def _category(session: AsyncSession, key: str, kind: str) -> Category:
    found = await session.get(Category, key)
    if found is None or found.kind != kind:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "category_unknown")
    if not found.active:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "category_inactive")
    return found


def _specs(values: dict[str, Any], category: Category) -> dict[str, Any]:
    unknown = set(values) - {s["key"] for s in category.specs}
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "spec_unknown")
    try:
        return domain.check_specs(values, _ref(category))
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "spec_invalid") from exc


def _check_family(kind: str, family: str | None) -> None:
    if (kind == "skill") != (family is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "family_mismatch")


@router.get("/catalogue", response_model=schemas.CatalogueOut)
async def catalogue(principal: Viewer, session: Session) -> schemas.CatalogueOut:
    items = [_category_out(c) for c in await _categories(session)]
    return schemas.CatalogueOut(items=items, can_manage=can_manage_catalogue(principal))


@router.post("/catalogue", response_model=schemas.CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(principal: Reader, session: Session, body: schemas.CategoryIn) -> schemas.CategoryOut:
    if not can_manage_catalogue(principal):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "national_scope_required")
    family = body.family if body.kind != "skill" else None
    _check_family(body.kind, family)
    if await session.get(Category, body.key):
        raise HTTPException(status.HTTP_409_CONFLICT, "category_taken")
    category = Category(
        key=body.key,
        kind=body.kind,
        family=family,
        name=body.name.model_dump(),
        specs=[s.model_dump() for s in body.specs] if body.kind != "skill" else [],
        levels=body.levels if body.kind == "skill" else 0,
        position=body.position,
        updated_by=audit.actor_of(principal),
    )
    session.add(category)
    await audit.record(
        session, actor=audit.actor_of(principal), action="inventory.category", target=f"category:{body.key}"
    )
    await session.commit()
    return _category_out(category)


@router.patch("/catalogue/{key}", response_model=schemas.CategoryOut)
async def update_category(
    principal: Reader, session: Session, key: str, body: schemas.CategoryPatch
) -> schemas.CategoryOut:
    """A type is never deleted (the register refers to it): it is switched off and new rows cannot use it."""
    if not can_manage_catalogue(principal):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "national_scope_required")
    category = await session.get(Category, key, with_for_update=True)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "category_not_found")
    changes = body.model_dump(exclude_unset=True)
    if "family" in changes:
        _check_family(category.kind, changes["family"])
        category.family = changes["family"]
    if body.name is not None:
        category.name = body.name.model_dump()
    if body.specs is not None and category.kind != "skill":
        category.specs = [s.model_dump() for s in body.specs]
    if body.levels is not None and category.kind == "skill":
        category.levels = body.levels
    for field in ("position", "active"):
        if changes.get(field) is not None:
            setattr(category, field, changes[field])
    category.updated_at = _now()
    category.updated_by = audit.actor_of(principal)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="inventory.category",
        target=f"category:{key}",
        details={"fields": sorted(changes)},
    )
    await session.commit()
    return _category_out(category)


# ---------------------------------------------------------------- units and overview


def _today() -> date:
    return _now().date()


def _stale(verified_at: datetime | None) -> bool:
    return verified_at is None or verified_at < _now() - timedelta(days=domain.STALE_DAYS)


async def _unit(session: AsyncSession, unit_id: uuid.UUID) -> Unit:
    found = await session.get(Unit, unit_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unit_not_found")
    return found


async def _unit_rows(session: AsyncSession, principal: Principal, gouvernorat: int | None) -> list[schemas.UnitRow]:
    query = select(Unit).where(_scope(principal, Unit.gouvernorat_code))
    if gouvernorat is not None:
        query = query.where(Unit.gouvernorat_code == gouvernorat)
    units = list((await session.scalars(query.order_by(Unit.gouvernorat_code, Unit.name_ar))).all())
    ids = [u.id for u in units]
    if not ids:
        return []
    vehicles: dict[uuid.UUID, list[int]] = defaultdict(lambda: [0, 0])
    for unit_id, state, n in (
        await session.execute(
            select(Resource.unit_id, Resource.status, func.count())
            .where(Resource.unit_id.in_(ids))
            .group_by(Resource.unit_id, Resource.status)
        )
    ).all():
        vehicles[unit_id][0] += n
        if state == "available":
            vehicles[unit_id][1] += n
    stock = {
        unit_id: (int(r or 0), int(b or 0))
        for unit_id, r, b in (
            await session.execute(
                select(Stock.unit_id, func.sum(Stock.qty_ready), func.sum(Stock.qty_broken))
                .where(Stock.unit_id.in_(ids))
                .group_by(Stock.unit_id)
            )
        ).all()
    }
    agents = {
        unit_id: (int(n), int(d or 0))
        for unit_id, n, d in (
            await session.execute(
                select(Agent.unit_id, func.count(), func.count().filter(Agent.availability == "on_duty"))
                .where(Agent.unit_id.in_(ids))
                .group_by(Agent.unit_id)
            )
        ).all()
    }
    checks = {c.unit_id: c for c in (await session.scalars(select(UnitCheck).where(UnitCheck.unit_id.in_(ids)))).all()}
    out = []
    for u in units:
        check = checks.get(u.id)
        out.append(
            schemas.UnitRow(
                id=u.id,
                name_ar=u.name_ar,
                name_fr=u.name_fr,
                kind=u.kind,
                gouvernorat_code=u.gouvernorat_code,
                vehicles=vehicles[u.id][0],
                vehicles_ready=vehicles[u.id][1],
                equipment_ready=stock.get(u.id, (0, 0))[0],
                equipment_broken=stock.get(u.id, (0, 0))[1],
                agents=agents.get(u.id, (0, 0))[0],
                agents_on_duty=agents.get(u.id, (0, 0))[1],
                verified_at=check.verified_at if check else None,
                verified_by_name=check.verified_by_name if check else None,
                stale=_stale(check.verified_at if check else None),
                can_edit=can_edit(principal, u.gouvernorat_code),
            )
        )
    return out


@router.get("/units", response_model=schemas.UnitsOut)
async def list_units(
    principal: Reader, session: Session, gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None
) -> schemas.UnitsOut:
    return schemas.UnitsOut(items=await _unit_rows(session, principal, gouvernorat))


@router.post("/units/{unit_id}/verify", response_model=schemas.UnitRow)
async def verify_unit(principal: Reader, session: Session, unit_id: uuid.UUID) -> schemas.UnitRow:
    """The regional room confirms that the unit's figures are up to date (the monthly reminder stops)."""
    unit = await _unit(session, unit_id)
    _require_edit(principal, unit.gouvernorat_code)
    check = await session.get(UnitCheck, unit.id, with_for_update=True)
    if check is None:
        check = UnitCheck(unit_id=unit.id, gouvernorat_code=unit.gouvernorat_code, verified_by="")
        session.add(check)
    check.verified_at = _now()
    check.verified_by = audit.actor_of(principal)
    check.verified_by_name = audit.name_of(principal)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="inventory.verify",
        target=f"unit:{unit.id}",
        gouvernorats=[unit.gouvernorat_code],
    )
    await session.commit()
    rows = await _unit_rows(session, principal, unit.gouvernorat_code)
    return next(r for r in rows if r.id == unit.id)


@router.get("/overview", response_model=schemas.OverviewOut)
async def overview(principal: Viewer, session: Session) -> schemas.OverviewOut:
    """The counts by gouvernorat and by type: what the governor and the minister see (no list, no name)."""
    gouvernorats = (
        await session.execute(
            select(Gouvernorat.code, Gouvernorat.name_ar, Gouvernorat.name_fr, Gouvernorat.name_en)
            .where(_scope(principal, Gouvernorat.code))
            .order_by(Gouvernorat.code)
        )
    ).all()
    rows = {
        code: schemas.GouvernoratRow(
            code=code,
            name_ar=ar,
            name_fr=fr,
            name_en=en,
            units=0,
            stale_units=0,
            vehicles=schemas.Tally(),
            equipment=schemas.Tally(),
            agents=0,
            agents_on_duty=0,
        )
        for code, ar, fr, en in gouvernorats
    }
    units = (
        await session.execute(
            select(Unit.gouvernorat_code, UnitCheck.verified_at)
            .outerjoin(UnitCheck, UnitCheck.unit_id == Unit.id)
            .where(_scope(principal, Unit.gouvernorat_code))
        )
    ).all()
    for code, verified_at in units:
        if code in rows:
            rows[code].units += 1
            rows[code].stale_units += int(_stale(verified_at))
    categories: dict[str, schemas.CategoryTotal] = {}
    vehicle_rows = (
        await session.execute(
            select(Unit.gouvernorat_code, Resource.category_key, Resource.status, Resource.out_reason, func.count())
            .join(Unit, Unit.id == Resource.unit_id)
            .where(_scope(principal, Unit.gouvernorat_code))
            .group_by(Unit.gouvernorat_code, Resource.category_key, Resource.status, Resource.out_reason)
        )
    ).all()
    for code, key, state, out_reason, n in vehicle_rows:
        field = domain.vehicle_state(state, out_reason)
        if code in rows:
            tally = rows[code].vehicles
            setattr(tally, field, getattr(tally, field) + n)
        total = categories.setdefault(key or "other", schemas.CategoryTotal(key=key or "other", kind="vehicle"))
        setattr(total, field, getattr(total, field) + n)
    stock_rows = (
        await session.execute(
            select(Stock.gouvernorat_code, Stock.category_key, func.sum(Stock.qty_ready), func.sum(Stock.qty_broken))
            .where(_scope(principal, Stock.gouvernorat_code))
            .group_by(Stock.gouvernorat_code, Stock.category_key)
        )
    ).all()
    for code, key, ready, broken in stock_rows:
        if code in rows:
            rows[code].equipment.ready += int(ready or 0)
            rows[code].equipment.broken += int(broken or 0)
        total = categories.setdefault(key, schemas.CategoryTotal(key=key, kind="equipment"))
        total.ready += int(ready or 0)
        total.broken += int(broken or 0)
    for code, n, on_duty in (
        await session.execute(
            select(Agent.gouvernorat_code, func.count(), func.count().filter(Agent.availability == "on_duty"))
            .where(_scope(principal, Agent.gouvernorat_code))
            .group_by(Agent.gouvernorat_code)
        )
    ).all():
        if code in rows:
            rows[code].agents, rows[code].agents_on_duty = int(n), int(on_duty)
    today = _today()
    valid = func.coalesce(AgentSkill.cert_expires >= today, True)
    skills = [
        schemas.SkillTotal(key=key, agents=int(n), ready=int(ready), expired=int(expired))
        for key, n, ready, expired in (
            await session.execute(
                select(
                    AgentSkill.skill_key,
                    func.count(),
                    func.count().filter(and_(Agent.availability == "on_duty", valid)),
                    func.count().filter(AgentSkill.cert_expires < today),
                )
                .join(Agent, Agent.id == AgentSkill.agent_id)
                .where(_scope(principal, Agent.gouvernorat_code))
                .group_by(AgentSkill.skill_key)
                .order_by(AgentSkill.skill_key)
            )
        ).all()
    ]
    lists = bool(LIST_ROLES & set(principal.roles))
    return schemas.OverviewOut(
        gouvernorats=list(rows.values()),
        categories=sorted(categories.values(), key=lambda c: (c.kind, c.key)),
        skills=skills,
        can_list=lists,
        can_edit=can_edit(principal),
        can_see_names=lists and sees_names(principal),
    )


# ---------------------------------------------------------------- revisions


async def _revise(
    session: AsyncSession,
    principal: Principal,
    entity: Literal["vehicle", "stock", "agent"],
    entity_id: uuid.UUID,
    gouvernorat: int,
    action: str,
    snapshot: dict[str, Any],
    reason: str | None,
) -> None:
    session.add(
        InventoryRevision(
            entity=entity,
            entity_id=entity_id,
            gouvernorat_code=gouvernorat,
            action=action,
            snapshot=snapshot,
            reason=reason,
            created_by=audit.actor_of(principal),
            created_by_name=audit.name_of(principal),
        )
    )


PERSONAL = ("matricule", "full_name", "phone")


@router.get("/revisions", response_model=schemas.RevisionsOut)
async def list_revisions(
    principal: Reader,
    session: Session,
    entity_id: Annotated[uuid.UUID | None, Query()] = None,
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> schemas.RevisionsOut:
    query = select(InventoryRevision).where(_scope(principal, InventoryRevision.gouvernorat_code))
    if entity_id is not None:
        query = query.where(InventoryRevision.entity_id == entity_id)
    if gouvernorat is not None:
        query = query.where(InventoryRevision.gouvernorat_code == gouvernorat)
    found = (await session.scalars(query.order_by(InventoryRevision.created_at.desc()).limit(limit))).all()
    names = sees_names(principal)
    items = []
    for r in found:
        snapshot = dict(r.snapshot)
        if not names:
            for key in PERSONAL:
                snapshot.pop(key, None)
        items.append(
            schemas.RevisionOut(
                id=r.id,
                entity=r.entity,
                entity_id=r.entity_id,
                action=r.action,
                snapshot=snapshot,
                reason=r.reason,
                created_by_name=r.created_by_name,
                created_at=r.created_at,
            )
        )
    return schemas.RevisionsOut(items=items)


# ---------------------------------------------------------------- vehicles


def _vehicle_out(r: Resource, unit: Unit) -> schemas.VehicleOut:
    return schemas.VehicleOut(
        id=r.id,
        unit_id=unit.id,
        unit_name=unit.name_ar,
        gouvernorat_code=unit.gouvernorat_code,
        category_key=r.category_key,
        kind=r.kind,
        label=r.label,
        code=r.code,
        specs=r.specs or {},
        state=domain.vehicle_state(r.status, r.out_reason),
        year=r.year,
        notes=r.notes,
        version=r.version,
        updated_at=r.updated_at,
    )


def _vehicle_snapshot(r: Resource, unit: Unit) -> dict[str, Any]:
    return _vehicle_out(r, unit).model_dump(mode="json", exclude={"updated_at", "unit_name"})


@router.get("/vehicles", response_model=schemas.VehiclesOut)
async def list_vehicles(
    principal: Reader,
    session: Session,
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
    unit_id: Annotated[uuid.UUID | None, Query()] = None,
    category: Annotated[str | None, Query(max_length=40)] = None,
) -> schemas.VehiclesOut:
    query = (
        select(Resource, Unit).join(Unit, Unit.id == Resource.unit_id).where(_scope(principal, Unit.gouvernorat_code))
    )
    if gouvernorat is not None:
        query = query.where(Unit.gouvernorat_code == gouvernorat)
    if unit_id is not None:
        query = query.where(Resource.unit_id == unit_id)
    if category:
        query = query.where(Resource.category_key == category)
    rows = (await session.execute(query.order_by(Unit.gouvernorat_code, Unit.name_ar, Resource.label))).all()
    return schemas.VehiclesOut(items=[_vehicle_out(r, u) for r, u in rows], can_edit=can_edit(principal))


async def _vehicle(session: AsyncSession, vehicle_id: uuid.UUID) -> tuple[Resource, Unit]:
    row = (
        await session.execute(
            select(Resource, Unit)
            .join(Unit, Unit.id == Resource.unit_id)
            .where(Resource.id == vehicle_id)
            .with_for_update(of=Resource)
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "vehicle_not_found")
    return row[0], row[1]


async def _label_free(session: AsyncSession, unit_id: uuid.UUID, label: str, own: uuid.UUID | None) -> None:
    query = select(Resource.id).where(Resource.unit_id == unit_id, Resource.label == label)
    if own is not None:
        query = query.where(Resource.id != own)
    if await session.scalar(query):
        raise HTTPException(status.HTTP_409_CONFLICT, "label_taken")


def _apply_vehicle(r: Resource, values: dict[str, Any], category: Category) -> None:
    r.category_key = category.key
    r.kind = category.key if category.key in OLD_KINDS else "other"
    r.label, r.code, r.specs, r.year, r.notes = (
        values["label"],
        values.get("code"),
        values["specs"],
        values.get("year"),
        values.get("notes"),
    )
    if r.status != "assigned":
        # An engaged vehicle changes state through its assignment only.
        r.status, r.out_reason = domain.state_columns(values["state"])


@router.post("/vehicles", response_model=schemas.VehicleOut, status_code=status.HTTP_201_CREATED)
async def create_vehicle(principal: Reader, session: Session, body: schemas.VehicleIn) -> schemas.VehicleOut:
    unit = await _unit(session, body.unit_id)
    _require_edit(principal, unit.gouvernorat_code)
    category = await _category(session, body.category_key, "vehicle")
    values = body.model_dump()
    values["specs"] = _specs(body.specs, category)
    await _label_free(session, unit.id, body.label, None)
    vehicle = Resource(unit_id=unit.id, status="available", updated_by=audit.actor_of(principal))
    _apply_vehicle(vehicle, values, category)
    session.add(vehicle)
    await session.flush()
    await session.refresh(vehicle)
    reason = _reason(body.reason, required=False)
    await _revise(
        session,
        principal,
        "vehicle",
        vehicle.id,
        unit.gouvernorat_code,
        "create",
        _vehicle_snapshot(vehicle, unit),
        reason,
    )
    await resources.announce(session, vehicle.id)
    await session.commit()
    return _vehicle_out(vehicle, unit)


@router.patch("/vehicles/{vehicle_id}", response_model=schemas.VehicleOut)
async def update_vehicle(
    principal: Reader, session: Session, vehicle_id: uuid.UUID, body: schemas.VehicleIn
) -> schemas.VehicleOut:
    vehicle, unit = await _vehicle(session, vehicle_id)
    _require_edit(principal, unit.gouvernorat_code)
    if body.version is not None and body.version != vehicle.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
    reason = _reason(body.reason)
    if body.unit_id != vehicle.unit_id:
        if vehicle.status == "assigned":
            raise HTTPException(status.HTTP_409_CONFLICT, "resource_busy")
        unit = await _unit(session, body.unit_id)
        _require_edit(principal, unit.gouvernorat_code)
        vehicle.unit_id = unit.id
    category = await _category(session, body.category_key, "vehicle")
    values = body.model_dump()
    values["specs"] = _specs(body.specs, category)
    await _label_free(session, unit.id, body.label, vehicle.id)
    _apply_vehicle(vehicle, values, category)
    vehicle.version += 1
    vehicle.updated_at = _now()
    vehicle.updated_by = audit.actor_of(principal)
    await session.flush()
    await _revise(
        session,
        principal,
        "vehicle",
        vehicle.id,
        unit.gouvernorat_code,
        "update",
        _vehicle_snapshot(vehicle, unit),
        reason,
    )
    await resources.announce(session, vehicle.id)
    await session.commit()
    return _vehicle_out(vehicle, unit)


@router.delete("/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(
    principal: Reader, session: Session, vehicle_id: uuid.UUID, body: schemas.ReasonIn
) -> Response:
    """Removed from the register (sold, scrapped); a vehicle that served in an intervention stays, out of service."""
    vehicle, unit = await _vehicle(session, vehicle_id)
    _require_edit(principal, unit.gouvernorat_code)
    reason = _reason(body.reason)
    snapshot = _vehicle_snapshot(vehicle, unit)
    if vehicle.status == "assigned":
        raise HTTPException(status.HTTP_409_CONFLICT, "resource_busy")
    if await session.scalar(select(func.count()).where(Assignment.resource_id == vehicle.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "resource_in_history")
    await session.delete(vehicle)
    await _revise(session, principal, "vehicle", vehicle.id, unit.gouvernorat_code, "delete", snapshot, reason)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- equipment by quantity


def _stock_out(s: Stock, unit: Unit) -> schemas.StockOut:
    return schemas.StockOut(
        id=s.id,
        unit_id=unit.id,
        unit_name=unit.name_ar,
        gouvernorat_code=s.gouvernorat_code,
        category_key=s.category_key,
        specs=s.specs or {},
        qty_ready=s.qty_ready,
        qty_broken=s.qty_broken,
        notes=s.notes,
        version=s.version,
        updated_at=s.updated_at,
    )


def _stock_snapshot(s: Stock, unit: Unit) -> dict[str, Any]:
    return _stock_out(s, unit).model_dump(mode="json", exclude={"updated_at", "unit_name"})


@router.get("/stock", response_model=schemas.StockListOut)
async def list_stock(
    principal: Reader,
    session: Session,
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
    unit_id: Annotated[uuid.UUID | None, Query()] = None,
    category: Annotated[str | None, Query(max_length=40)] = None,
) -> schemas.StockListOut:
    query = select(Stock, Unit).join(Unit, Unit.id == Stock.unit_id).where(_scope(principal, Stock.gouvernorat_code))
    if gouvernorat is not None:
        query = query.where(Stock.gouvernorat_code == gouvernorat)
    if unit_id is not None:
        query = query.where(Stock.unit_id == unit_id)
    if category:
        query = query.where(Stock.category_key == category)
    rows = (await session.execute(query.order_by(Stock.gouvernorat_code, Unit.name_ar, Stock.category_key))).all()
    return schemas.StockListOut(items=[_stock_out(s, u) for s, u in rows], can_edit=can_edit(principal))


async def _stock(session: AsyncSession, stock_id: uuid.UUID) -> tuple[Stock, Unit]:
    row = (
        await session.execute(
            select(Stock, Unit)
            .join(Unit, Unit.id == Stock.unit_id)
            .where(Stock.id == stock_id)
            .with_for_update(of=Stock)
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "stock_not_found")
    return row[0], row[1]


async def _stock_free(
    session: AsyncSession, unit_id: uuid.UUID, key: str, specs: dict[str, Any], own: uuid.UUID | None
) -> None:
    query = select(Stock.id).where(Stock.unit_id == unit_id, Stock.category_key == key, Stock.specs == specs)
    if own is not None:
        query = query.where(Stock.id != own)
    if await session.scalar(query):
        raise HTTPException(status.HTTP_409_CONFLICT, "stock_exists")


@router.post("/stock", response_model=schemas.StockOut, status_code=status.HTTP_201_CREATED)
async def create_stock(principal: Reader, session: Session, body: schemas.StockIn) -> schemas.StockOut:
    unit = await _unit(session, body.unit_id)
    _require_edit(principal, unit.gouvernorat_code)
    category = await _category(session, body.category_key, "equipment")
    specs = _specs(body.specs, category)
    await _stock_free(session, unit.id, category.key, specs, None)
    line = Stock(
        unit_id=unit.id,
        gouvernorat_code=unit.gouvernorat_code,
        category_key=category.key,
        specs=specs,
        qty_ready=body.qty_ready,
        qty_broken=body.qty_broken,
        notes=body.notes,
        updated_by=audit.actor_of(principal),
    )
    session.add(line)
    await session.flush()
    await session.refresh(line)
    reason = _reason(body.reason, required=False)
    await _revise(
        session, principal, "stock", line.id, unit.gouvernorat_code, "create", _stock_snapshot(line, unit), reason
    )
    await session.commit()
    return _stock_out(line, unit)


@router.patch("/stock/{stock_id}", response_model=schemas.StockOut)
async def update_stock(
    principal: Reader, session: Session, stock_id: uuid.UUID, body: schemas.StockIn
) -> schemas.StockOut:
    line, unit = await _stock(session, stock_id)
    _require_edit(principal, unit.gouvernorat_code)
    if body.version is not None and body.version != line.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
    reason = _reason(body.reason)
    if body.unit_id != line.unit_id:
        unit = await _unit(session, body.unit_id)
        _require_edit(principal, unit.gouvernorat_code)
    category = await _category(session, body.category_key, "equipment")
    specs = _specs(body.specs, category)
    await _stock_free(session, unit.id, category.key, specs, line.id)
    line.unit_id, line.gouvernorat_code = unit.id, unit.gouvernorat_code
    line.category_key, line.specs = category.key, specs
    line.qty_ready, line.qty_broken, line.notes = body.qty_ready, body.qty_broken, body.notes
    line.version += 1
    line.updated_at = _now()
    line.updated_by = audit.actor_of(principal)
    await session.flush()
    await _revise(
        session, principal, "stock", line.id, unit.gouvernorat_code, "update", _stock_snapshot(line, unit), reason
    )
    await session.commit()
    return _stock_out(line, unit)


@router.delete("/stock/{stock_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stock(principal: Reader, session: Session, stock_id: uuid.UUID, body: schemas.ReasonIn) -> Response:
    line, unit = await _stock(session, stock_id)
    _require_edit(principal, unit.gouvernorat_code)
    reason = _reason(body.reason)
    snapshot = _stock_snapshot(line, unit)
    await session.delete(line)
    await _revise(session, principal, "stock", line.id, unit.gouvernorat_code, "delete", snapshot, reason)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- staff


def _skill_out(s: AgentSkill, today: date) -> schemas.SkillOut:
    return schemas.SkillOut(
        skill_key=s.skill_key,
        level=s.level,
        cert_expires=s.cert_expires,
        expired=s.cert_expires is not None and s.cert_expires < today,
    )


def _agent_out(a: Agent, unit: Unit, skills: list[AgentSkill], names: bool, today: date) -> schemas.AgentOut:
    return schemas.AgentOut(
        id=a.id,
        unit_id=unit.id,
        unit_name=unit.name_ar,
        gouvernorat_code=a.gouvernorat_code,
        matricule=a.matricule if names else None,
        full_name=a.full_name if names else None,
        phone=a.phone if names else None,
        rank=a.rank,
        availability=a.availability,
        skills=[_skill_out(s, today) for s in sorted(skills, key=lambda s: s.skill_key)],
        notes=a.notes if names else None,
        version=a.version,
        updated_at=a.updated_at,
    )


def _agent_snapshot(a: Agent, skills: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "unit_id": str(a.unit_id),
        "gouvernorat_code": a.gouvernorat_code,
        "matricule": a.matricule,
        "full_name": a.full_name,
        "phone": a.phone,
        "rank": a.rank,
        "availability": a.availability,
        "notes": a.notes,
        "skills": [
            {**s, "cert_expires": s["cert_expires"].isoformat() if s.get("cert_expires") else None} for s in skills
        ],
    }


async def _skills_of(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, list[AgentSkill]]:
    out: dict[uuid.UUID, list[AgentSkill]] = defaultdict(list)
    if ids:
        for s in (await session.scalars(select(AgentSkill).where(AgentSkill.agent_id.in_(ids)))).all():
            out[s.agent_id].append(s)
    return out


@router.get("/agents", response_model=schemas.AgentsOut)
async def list_agents(
    principal: Reader,
    session: Session,
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
    unit_id: Annotated[uuid.UUID | None, Query()] = None,
    skill: Annotated[str | None, Query(max_length=40)] = None,
) -> schemas.AgentsOut:
    query = select(Agent, Unit).join(Unit, Unit.id == Agent.unit_id).where(_scope(principal, Agent.gouvernorat_code))
    if gouvernorat is not None:
        query = query.where(Agent.gouvernorat_code == gouvernorat)
    if unit_id is not None:
        query = query.where(Agent.unit_id == unit_id)
    if skill:
        query = query.where(
            select(AgentSkill.agent_id).where(AgentSkill.agent_id == Agent.id, AgentSkill.skill_key == skill).exists()
        )
    names = sees_names(principal)
    order = (Agent.gouvernorat_code, Unit.name_ar, Agent.full_name if names else Agent.rank, Agent.id)
    rows = (await session.execute(query.order_by(*order))).all()
    skills = await _skills_of(session, [a.id for a, _ in rows])
    today = _today()
    return schemas.AgentsOut(
        items=[_agent_out(a, u, skills[a.id], names, today) for a, u in rows],
        can_edit=can_edit(principal),
        can_see_names=names,
        can_export_names=exports_names(principal, principal.gouvernorat_code),
    )


async def _agent(session: AsyncSession, agent_id: uuid.UUID) -> tuple[Agent, Unit]:
    row = (
        await session.execute(
            select(Agent, Unit)
            .join(Unit, Unit.id == Agent.unit_id)
            .where(Agent.id == agent_id)
            .with_for_update(of=Agent)
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "agent_not_found")
    return row[0], row[1]


async def _taken(session: AsyncSession, matricules: list[str], own: set[uuid.UUID]) -> set[str]:
    """Matricules already given to another member of staff, in any gouvernorat (a regional room cannot see the
    others: the check runs with the system scope and returns the matricules only)."""
    if not matricules:
        return set()
    async with get_system_sessionmaker()() as system:
        query = select(Agent.matricule).where(Agent.matricule.in_(matricules))
        if own:
            query = query.where(Agent.id.not_in(own))
        return set((await system.scalars(query)).all())


async def _check_skills(session: AsyncSession, skills: list[schemas.SkillIn]) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for s in skills:
        category = await _category(session, s.skill_key, "skill")
        level = 0 if category.levels == 0 else s.level
        if category.levels and not 1 <= level <= category.levels:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "skill_level_invalid")
        out[category.key] = {"skill_key": category.key, "level": level, "cert_expires": s.cert_expires}
    return list(out.values())


async def _set_skills(session: AsyncSession, agent: Agent, skills: list[dict[str, Any]]) -> None:
    await session.execute(delete(AgentSkill).where(AgentSkill.agent_id == agent.id))
    for s in skills:
        session.add(AgentSkill(agent_id=agent.id, **s))


async def _agent_response(session: AsyncSession, principal: Principal, agent: Agent, unit: Unit) -> schemas.AgentOut:
    skills = (await _skills_of(session, [agent.id]))[agent.id]
    return _agent_out(agent, unit, skills, sees_names(principal), _today())


@router.post("/agents", response_model=schemas.AgentOut, status_code=status.HTTP_201_CREATED)
async def create_agent(principal: Reader, session: Session, body: schemas.AgentIn) -> schemas.AgentOut:
    unit = await _unit(session, body.unit_id)
    _require_edit(principal, unit.gouvernorat_code)
    matricule = body.matricule.strip()
    if await _taken(session, [matricule], set()):
        raise HTTPException(status.HTTP_409_CONFLICT, "matricule_taken")
    skills = await _check_skills(session, body.skills)
    agent = Agent(
        unit_id=unit.id,
        gouvernorat_code=unit.gouvernorat_code,
        matricule=matricule,
        full_name=body.full_name.strip(),
        rank=body.rank,
        phone=body.phone,
        availability=body.availability,
        notes=body.notes,
        updated_by=audit.actor_of(principal),
    )
    session.add(agent)
    await session.flush()
    await _set_skills(session, agent, skills)
    await session.flush()
    await session.refresh(agent)
    reason = _reason(body.reason, required=False)
    await _revise(
        session, principal, "agent", agent.id, unit.gouvernorat_code, "create", _agent_snapshot(agent, skills), reason
    )
    out = await _agent_response(session, principal, agent, unit)
    await session.commit()
    return out


@router.patch("/agents/{agent_id}", response_model=schemas.AgentOut)
async def update_agent(
    principal: Reader, session: Session, agent_id: uuid.UUID, body: schemas.AgentIn
) -> schemas.AgentOut:
    agent, unit = await _agent(session, agent_id)
    _require_edit(principal, unit.gouvernorat_code)
    if body.version is not None and body.version != agent.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
    reason = _reason(body.reason, required=False) or "تحيين"
    if body.unit_id != agent.unit_id:
        unit = await _unit(session, body.unit_id)
        _require_edit(principal, unit.gouvernorat_code)
    matricule = body.matricule.strip()
    if matricule != agent.matricule and await _taken(session, [matricule], {agent.id}):
        raise HTTPException(status.HTTP_409_CONFLICT, "matricule_taken")
    skills = await _check_skills(session, body.skills)
    agent.unit_id, agent.gouvernorat_code = unit.id, unit.gouvernorat_code
    agent.matricule, agent.full_name = matricule, body.full_name.strip()
    agent.rank, agent.phone, agent.availability, agent.notes = body.rank, body.phone, body.availability, body.notes
    agent.version += 1
    agent.updated_at = _now()
    agent.updated_by = audit.actor_of(principal)
    await _set_skills(session, agent, skills)
    await session.flush()
    await _revise(
        session, principal, "agent", agent.id, unit.gouvernorat_code, "update", _agent_snapshot(agent, skills), reason
    )
    out = await _agent_response(session, principal, agent, unit)
    await session.commit()
    return out


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(principal: Reader, session: Session, agent_id: uuid.UUID, body: schemas.ReasonIn) -> Response:
    """Left the service or moved to another administration; a transfer between gouvernorats is a change of unit."""
    agent, unit = await _agent(session, agent_id)
    _require_edit(principal, unit.gouvernorat_code)
    reason = _reason(body.reason)
    skills = [
        {"skill_key": s.skill_key, "level": s.level, "cert_expires": s.cert_expires}
        for s in (await _skills_of(session, [agent.id]))[agent.id]
    ]
    snapshot = _agent_snapshot(agent, skills)
    await session.delete(agent)
    await _revise(session, principal, "agent", agent.id, unit.gouvernorat_code, "delete", snapshot, reason)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- template, import and export


async def _lookups(
    session: AsyncSession, gouvernorat: int
) -> tuple[list[Unit], dict[str, Any], list[Category], dict[str, domain.CategoryRef]]:
    units = list(
        (await session.scalars(select(Unit).where(Unit.gouvernorat_code == gouvernorat).order_by(Unit.name_ar))).all()
    )
    by_name: dict[str, Any] = {}
    for u in units:
        by_name.setdefault(normalize(u.name_ar), u.id)
        by_name.setdefault(normalize(u.name_fr), u.id)
    categories = await _categories(session)
    refs: dict[str, domain.CategoryRef] = {}
    for c in categories:
        ref = _ref(c)
        for label in (c.key, *c.name.values()):
            refs.setdefault(normalize(label), ref)
    return units, by_name, categories, refs


@router.get("/template")
async def template(
    principal: Reader, session: Session, gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None
) -> Response:
    """The xlsx template of a gouvernorat, with its units and the catalogue in a sheet of accepted values."""
    code = _gouvernorat(principal, gouvernorat)
    units, _, categories, _ = await _lookups(session, code)
    content = domain.template(
        [u.name_ar for u in units],
        [(c.kind, c.name.get("ar", c.key), c.levels) for c in categories if c.active],
    )
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="inventory-{code:02d}.xlsx"'},
    )


async def _read_body(request: Request) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > domain.MAX_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "file_too_large")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/imports", response_model=schemas.ImportOut)
async def import_register(
    principal: Reader,
    session: Session,
    request: Request,
    file_name: Annotated[str, Query(min_length=1, max_length=200)],
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
    entity: Annotated[Entity | None, Query()] = None,
    apply: Annotated[bool, Query()] = False,
    reason: Annotated[str, Query(max_length=500)] = "",
) -> schemas.ImportOut:
    """The register of one gouvernorat from the xlsx template (or a CSV of one sheet, named by ``entity``). Without
    ``apply`` nothing is saved: the answer counts the new and changed rows and lists the errors and warnings. With
    ``apply`` the rows are added or updated (vehicles by unit and label, equipment by unit, type and specifications,
    staff by matricule); nothing absent from the file is deleted. A file with errors is refused."""
    code = _gouvernorat(principal, gouvernorat)
    _require_edit(principal, code)
    data = await _read_body(request)
    _, units, _, refs = await _lookups(session, code)
    try:
        parsed = domain.parse(file_name, data, entity, units, refs)
    except FileError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.code) from exc
    why = _reason(reason) if apply else None
    elsewhere = await _taken(
        session,
        [r["matricule"] for r in parsed.rows["agents"]],
        set(
            (
                await session.scalars(
                    select(Agent.id).where(Agent.matricule.in_([r["matricule"] for r in parsed.rows["agents"]]))
                )
            ).all()
        ),
    )
    for row in list(parsed.rows["agents"]):
        if row["matricule"] in elsewhere:
            parsed.errors.append(domain.Problem("matricule_elsewhere", "agents", row["line"], row["matricule"]))
            parsed.rows["agents"].remove(row)
    if apply and parsed.errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "import_has_errors")
    counts = {e: schemas.ImportCounts() for e in domain.ENTITIES}
    actor = audit.actor_of(principal)
    unit_by_id = {u.id: u for u in (await session.scalars(select(Unit).where(Unit.gouvernorat_code == code))).all()}
    categories = {c.key: c for c in await _categories(session)}

    for row in parsed.rows["vehicles"]:
        existing = await session.scalar(
            select(Resource).where(Resource.unit_id == row["unit_id"], Resource.label == row["label"]).with_for_update()
        )
        unit = unit_by_id[row["unit_id"]]
        if existing is None:
            counts["vehicles"].new += 1
            if apply:
                vehicle = Resource(unit_id=unit.id, status="available", updated_by=actor)
                _apply_vehicle(vehicle, row, categories[row["category_key"]])
                session.add(vehicle)
                await session.flush()
                await session.refresh(vehicle)
                await _revise(
                    session, principal, "vehicle", vehicle.id, code, "import", _vehicle_snapshot(vehicle, unit), why
                )
            continue
        before = _vehicle_snapshot(existing, unit)
        _apply_vehicle(existing, row, categories[row["category_key"]])
        after = _vehicle_snapshot(existing, unit)
        if before == after:
            counts["vehicles"].unchanged += 1
            continue
        counts["vehicles"].changed += 1
        if apply:
            existing.version += 1
            existing.updated_at, existing.updated_by = _now(), actor
            await _revise(
                session, principal, "vehicle", existing.id, code, "import", _vehicle_snapshot(existing, unit), why
            )

    for row in parsed.rows["stock"]:
        line = await session.scalar(
            select(Stock)
            .where(
                Stock.unit_id == row["unit_id"], Stock.category_key == row["category_key"], Stock.specs == row["specs"]
            )
            .with_for_update()
        )
        unit = unit_by_id[row["unit_id"]]
        if line is None:
            counts["stock"].new += 1
            if apply:
                line = Stock(
                    unit_id=unit.id,
                    gouvernorat_code=code,
                    category_key=row["category_key"],
                    specs=row["specs"],
                    qty_ready=row["qty_ready"],
                    qty_broken=row["qty_broken"],
                    notes=row["notes"],
                    updated_by=actor,
                )
                session.add(line)
                await session.flush()
                await session.refresh(line)
                await _revise(session, principal, "stock", line.id, code, "import", _stock_snapshot(line, unit), why)
            continue
        if (line.qty_ready, line.qty_broken, line.notes) == (row["qty_ready"], row["qty_broken"], row["notes"]):
            counts["stock"].unchanged += 1
            continue
        counts["stock"].changed += 1
        if apply:
            line.qty_ready, line.qty_broken, line.notes = row["qty_ready"], row["qty_broken"], row["notes"]
            line.version += 1
            line.updated_at, line.updated_by = _now(), actor
            await _revise(session, principal, "stock", line.id, code, "import", _stock_snapshot(line, unit), why)

    for row in parsed.rows["agents"]:
        agent = await session.scalar(select(Agent).where(Agent.matricule == row["matricule"]).with_for_update())
        unit = unit_by_id[row["unit_id"]]
        fields = {k: row[k] for k in ("full_name", "rank", "phone", "availability", "notes")}
        if agent is None:
            counts["agents"].new += 1
            if apply:
                agent = Agent(
                    unit_id=unit.id, gouvernorat_code=code, matricule=row["matricule"], updated_by=actor, **fields
                )
                session.add(agent)
                await session.flush()
                await _set_skills(session, agent, row["skills"])
                await session.flush()
                await _revise(
                    session, principal, "agent", agent.id, code, "import", _agent_snapshot(agent, row["skills"]), why
                )
            continue
        current = [
            {"skill_key": s.skill_key, "level": s.level, "cert_expires": s.cert_expires}
            for s in sorted((await _skills_of(session, [agent.id]))[agent.id], key=lambda s: s.skill_key)
        ]
        wanted = sorted(row["skills"], key=lambda s: s["skill_key"])
        same = agent.unit_id == unit.id and all(getattr(agent, k) == v for k, v in fields.items()) and current == wanted
        if same:
            counts["agents"].unchanged += 1
            continue
        counts["agents"].changed += 1
        if apply:
            agent.unit_id = unit.id
            for k, v in fields.items():
                setattr(agent, k, v)
            agent.version += 1
            agent.updated_at, agent.updated_by = _now(), actor
            await _set_skills(session, agent, row["skills"])
            await session.flush()
            await _revise(
                session, principal, "agent", agent.id, code, "import", _agent_snapshot(agent, row["skills"]), why
            )

    if apply:
        await audit.record(
            session,
            actor=actor,
            action="inventory.import",
            target=f"gouvernorat:{code}",
            reason=why,
            details={"file": file_name, **{e: c.model_dump() for e, c in counts.items()}},
            gouvernorats=[code],
        )
        await session.commit()
    else:
        await session.rollback()
    return schemas.ImportOut(
        format=parsed.format,
        gouvernorat_code=code,
        applied=apply,
        vehicles=counts["vehicles"],
        stock=counts["stock"],
        agents=counts["agents"],
        errors=[schemas.ProblemOut(**p.out()) for p in parsed.errors],
        warnings=[schemas.ProblemOut(**p.out()) for p in parsed.warnings],
    )


def _csv(rows: list[list[Any]], stem: str) -> Response:
    buffer = io.StringIO()
    csv.writer(buffer).writerows([[neutralize(v) if isinstance(v, str) else v for v in row] for row in rows])
    return Response(
        ("﻿" + buffer.getvalue()).encode(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{stem}.csv"'},
    )


def _skill_text(agent: schemas.AgentOut) -> str:
    return "; ".join(
        f"{s.skill_key}:{s.level}" + (f":{s.cert_expires.isoformat()}" if s.cert_expires else "") for s in agent.skills
    )


def _spec_text(specs: dict[str, Any]) -> str:
    return "; ".join(f"{k}={v}" for k, v in sorted(specs.items()))


@router.get("/export")
async def export_register(
    principal: Reader,
    session: Session,
    entity: Annotated[Entity, Query()],
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
) -> Response:
    """CSV of the register as the caller sees it. The names, matricules and phones of the staff are in the file only
    for the room of their own gouvernorat; every export is audited."""
    if gouvernorat is not None and not principal.can_access_gouvernorat(gouvernorat):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
    names = False
    if entity == "vehicles":
        found = (await list_vehicles(principal, session, gouvernorat)).items
        rows: list[list[Any]] = [["gouvernorat", "unit", "category", "label", "code", "specs", "state", "year"]]
        rows += [
            [
                v.gouvernorat_code,
                v.unit_name,
                v.category_key or "",
                v.label,
                v.code or "",
                _spec_text(v.specs),
                v.state,
                v.year or "",
            ]
            for v in found
        ]
    elif entity == "stock":
        lines = (await list_stock(principal, session, gouvernorat)).items
        rows = [["gouvernorat", "unit", "category", "specs", "ready", "broken"]]
        rows += [
            [s.gouvernorat_code, s.unit_name, s.category_key, _spec_text(s.specs), s.qty_ready, s.qty_broken]
            for s in lines
        ]
    else:
        names = exports_names(principal, gouvernorat if gouvernorat is not None else principal.gouvernorat_code)
        agents = (await list_agents(principal, session, gouvernorat)).items
        if names:
            rows = [["gouvernorat", "unit", "matricule", "full_name", "rank", "phone", "availability", "skills"]]
            rows += [
                [
                    a.gouvernorat_code,
                    a.unit_name,
                    a.matricule,
                    a.full_name,
                    a.rank or "",
                    a.phone or "",
                    a.availability,
                    _skill_text(a),
                ]
                for a in agents
            ]
        else:
            rows = [["gouvernorat", "unit", "rank", "availability", "skills"]]
            rows += [[a.gouvernorat_code, a.unit_name, a.rank or "", a.availability, _skill_text(a)] for a in agents]
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="inventory.export",
        target=f"inventory:{entity}",
        details={"rows": len(rows) - 1, "names": names},
        gouvernorats=[gouvernorat] if gouvernorat is not None else None,
    )
    await session.commit()
    suffix = f"-{gouvernorat:02d}" if gouvernorat is not None else ""
    return _csv(rows, f"inventory-{entity}{suffix}")


# ---------------------------------------------------------------- search (phase R2)


def _search_scope(principal: Principal, wanted: list[int] | None) -> list[int] | None:
    """The gouvernorats of a search: those asked for, never beyond what the caller sees (``None``: all of them)."""
    if wanted and any(not principal.can_access_gouvernorat(g) for g in wanted):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
    if wanted:
        return sorted(set(wanted))
    return None if principal.is_national else [principal.gouvernorat_code or 0]


async def _search_counts(
    session: AsyncSession, principal: Principal, body: schemas.SearchIn, codes: list[int] | None
) -> dict[uuid.UUID, list[int]]:
    """``{unit id: [total, ready]}`` of what meets the question."""
    found: dict[uuid.UUID, list[int]] = defaultdict(lambda: [0, 0])
    if body.what == "vehicles":
        query = select(Resource.unit_id, Resource.status, Resource.out_reason, Resource.specs).join(
            Unit, Unit.id == Resource.unit_id
        )
        query = query.where(_scope(principal, Unit.gouvernorat_code))
        if codes is not None:
            query = query.where(Unit.gouvernorat_code.in_(codes))
        if body.category:
            query = query.where(Resource.category_key == body.category)
        for unit_id, state, out_reason, specs in (await session.execute(query)).all():
            ready = domain.vehicle_state(state, out_reason) == "ready"
            if (body.ready_only and not ready) or not domain.matches(specs or {}, body.specs):
                continue
            found[unit_id][0] += 1
            found[unit_id][1] += int(ready)
    elif body.what == "stock":
        stock = select(Stock.unit_id, Stock.qty_ready, Stock.qty_broken, Stock.specs).where(
            _scope(principal, Stock.gouvernorat_code)
        )
        if codes is not None:
            stock = stock.where(Stock.gouvernorat_code.in_(codes))
        if body.category:
            stock = stock.where(Stock.category_key == body.category)
        for unit_id, ready_qty, broken, specs in (await session.execute(stock)).all():
            if not domain.matches(specs or {}, body.specs):
                continue
            found[unit_id][0] += ready_qty + (0 if body.ready_only else broken)
            found[unit_id][1] += ready_qty
    else:
        today = _today()
        on_duty = Agent.availability == "on_duty"
        agents = select(Agent.unit_id, func.count(), func.count().filter(on_duty)).where(
            _scope(principal, Agent.gouvernorat_code)
        )
        if codes is not None:
            agents = agents.where(Agent.gouvernorat_code.in_(codes))
        if body.category:
            valid = func.coalesce(AgentSkill.cert_expires >= today, True)
            agents = agents.join(
                AgentSkill, and_(AgentSkill.agent_id == Agent.id, AgentSkill.skill_key == body.category)
            )
            agents = agents.with_only_columns(Agent.unit_id, func.count(), func.count().filter(and_(on_duty, valid)))
            if body.min_level is not None:
                agents = agents.where(AgentSkill.level >= body.min_level)
            if body.valid_cert:
                agents = agents.where(valid)
        if body.ready_only:
            agents = agents.where(on_duty)
        for unit_id, n, on_call in (await session.execute(agents.group_by(Agent.unit_id))).all():
            found[unit_id] = [int(n), int(on_call)]
    return {unit_id: counts for unit_id, counts in found.items() if counts[0] > 0}


async def _search(session: AsyncSession, principal: Principal, body: schemas.SearchIn) -> schemas.SearchOut:
    codes = _search_scope(principal, body.gouvernorats)
    counts = await _search_counts(session, principal, body, codes)
    inside = func.ST_PointOnSurface(Gouvernorat.boundary)
    gouvernorats = select(
        Gouvernorat.code,
        Gouvernorat.name_ar,
        Gouvernorat.name_fr,
        Gouvernorat.name_en,
        func.ST_Y(inside),
        func.ST_X(inside),
    ).where(_scope(principal, Gouvernorat.code))
    if codes is not None:
        gouvernorats = gouvernorats.where(Gouvernorat.code.in_(codes))
    rows = {
        code: schemas.SearchGouvernorat(
            code=code, name_ar=ar, name_fr=fr, name_en=en, lat=lat, lon=lon, total=0, ready=0, units=[]
        )
        for code, ar, fr, en, lat, lon in (await session.execute(gouvernorats.order_by(Gouvernorat.code))).all()
    }
    if counts:
        point = cast(Unit.location, Geometry)
        units = (
            await session.execute(
                select(Unit.id, Unit.name_ar, Unit.name_fr, Unit.gouvernorat_code, func.ST_Y(point), func.ST_X(point))
                .where(Unit.id.in_(list(counts)))
                .order_by(Unit.gouvernorat_code, Unit.name_ar)
            )
        ).all()
        for unit_id, ar, fr, code, lat, lon in units:
            if code not in rows:
                continue
            total, ready = counts[unit_id]
            rows[code].units.append(
                schemas.SearchUnit(id=unit_id, name_ar=ar, name_fr=fr, lat=lat, lon=lon, total=total, ready=ready)
            )
            rows[code].total += total
            rows[code].ready += ready
    return schemas.SearchOut(
        what=body.what,
        total=sum(g.total for g in rows.values()),
        ready=sum(g.ready for g in rows.values()),
        gouvernorats=list(rows.values()),
    )


@router.post("/search", response_model=schemas.SearchOut)
async def search(principal: Viewer, session: Session, body: schemas.SearchIn) -> schemas.SearchOut:
    """The same question across every gouvernorat the caller sees, answered with counts by gouvernorat and unit (no
    name): what the central room, the governor and the minister send to the map."""
    return await _search(session, principal, body)


@router.get("/boundaries")
async def boundaries(principal: Viewer, session: Session, response: Response) -> dict[str, object]:
    """The outlines of the gouvernorats the caller sees (simplified), coloured on the map by the count of a search."""
    rows = await session.execute(
        select(
            Gouvernorat.code,
            func.ST_AsGeoJSON(func.ST_SimplifyPreserveTopology(Gouvernorat.boundary, 0.005), 5),
        ).where(Gouvernorat.boundary.isnot(None), _scope(principal, Gouvernorat.code))
    )
    response.headers["Cache-Control"] = "private, max-age=3600"
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "id": code, "properties": {"code": code}, "geometry": json.loads(g)}
            for code, g in rows.all()
        ],
    }


@router.post("/search/export")
async def export_search(principal: Viewer, session: Session, body: schemas.SearchIn) -> Response:
    """The result of a search as CSV (counts by unit, no name); audited like every export of the register."""
    result = await _search(session, principal, body)
    rows: list[list[Any]] = [["gouvernorat", "gouvernorat_name", "unit", "total", "ready"]]
    for g in result.gouvernorats:
        rows += [[g.code, g.name_ar, u.name_ar, u.total, u.ready] for u in g.units]
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="inventory.search_export",
        target=f"inventory:{body.what}",
        details={"rows": len(rows) - 1, "query": body.model_dump(mode="json", exclude_none=True)},
        gouvernorats=body.gouvernorats,
    )
    await session.commit()
    return _csv(rows, f"inventory-search-{body.what}")
