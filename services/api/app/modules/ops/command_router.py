"""Command endpoints of the dashboard: operational levels, committees, units and resources (phase 5)."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import REALM_ROLES, Principal, Realm, Role, require_roles
from app.modules.audit import service as audit
from app.modules.ops import committee, levels, resources, schemas
from app.modules.reports.staff_router import READ_ROLES, _bbox

router = APIRouter(prefix="/api/v1/staff", tags=["command"])

Session = Annotated[AsyncSession, Depends(get_session)]
AnyStaff = Annotated[Principal, Depends(require_roles(*REALM_ROLES[Realm.STAFF]))]
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
Committee = Annotated[Principal, Depends(require_roles(Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE))]
Monitor = Annotated[Principal, Depends(require_roles(Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE, Role.OPS_MANAGER))]
LocalCommittee = Annotated[Principal, Depends(require_roles(Role.LOCAL_COMMITTEE))]
Logistics = Annotated[Principal, Depends(require_roles(Role.OPS_MANAGER, Role.SYSADMIN))]
LogisticsReader = Annotated[Principal, Depends(require_roles(*READ_ROLES, Role.SYSADMIN))]


def _csv(raw: str | None, allowed: tuple[str, ...], code: str) -> list[str]:
    values = [v.strip() for v in (raw or "").split(",") if v.strip()]
    if any(v not in allowed for v in values):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, code)
    return values


# ---------------------------------------------------------------- levels (§6.4, FR-C-24)


@router.get("/levels", response_model=list[schemas.LevelOut])
async def get_levels(principal: AnyStaff, session: Session) -> list[schemas.LevelOut]:
    return [levels.level_out(r) for r in await levels.all_levels(session)]


@router.post("/levels", response_model=list[schemas.LevelOut])
async def set_levels(principal: Committee, session: Session, body: schemas.LevelIn) -> list[schemas.LevelOut]:
    rows = await levels.set_levels(session, principal, sorted(set(body.gouvernorat_codes)), body.level, body.reason)
    out = [levels.level_out(r) for r in rows]
    await session.commit()
    return out


# ---------------------------------------------------------------- committees (FR-C-15, FR-C-16)


@router.get("/directives", response_model=schemas.DirectivePage)
async def list_directives(
    principal: Monitor,
    session: Session,
    pending: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    cursor: str | None = None,
) -> schemas.DirectivePage:
    items, next_cursor = await committee.list_directives(session, principal, pending, limit, cursor)
    return schemas.DirectivePage(items=items, next_cursor=next_cursor)


@router.post("/directives", response_model=schemas.DirectiveOut, status_code=status.HTTP_201_CREATED)
async def issue_directive(principal: Committee, session: Session, body: schemas.DirectiveIn) -> schemas.DirectiveOut:
    out = await committee.issue(session, principal, body)
    await session.commit()
    return out


@router.post("/directives/{directive_id}/ack", response_model=schemas.DirectiveOut)
async def ack_directive(
    principal: LocalCommittee, session: Session, directive_id: uuid.UUID, body: schemas.AckIn
) -> schemas.DirectiveOut:
    out = await committee.acknowledge(session, principal, directive_id, body.note)
    await session.commit()
    return out


@router.get("/committee/performance", response_model=schemas.PerformanceOut)
async def performance(principal: Monitor, session: Session, since: datetime | None = None) -> schemas.PerformanceOut:
    since = since or datetime.now(UTC) - timedelta(days=30)
    if since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    return await committee.performance(session, principal, since)


# ---------------------------------------------------------------- units and resources (FR-C-09)


@router.get("/units", response_model=list[schemas.UnitOut])
async def list_units(principal: LogisticsReader, session: Session) -> list[schemas.UnitOut]:
    return await resources.list_units(session, principal)


@router.post("/units", response_model=schemas.UnitOut, status_code=status.HTTP_201_CREATED)
async def create_unit(principal: Logistics, session: Session, body: schemas.UnitIn) -> schemas.UnitOut:
    unit = await resources.save_unit(session, principal, body)
    await audit.record(session, actor=audit.actor_of(principal), action="unit.create", target=f"unit:{unit.id}")
    out = await resources.unit_out(session, unit)
    await session.commit()
    return out


@router.put("/units/{unit_id}", response_model=schemas.UnitOut)
async def update_unit(
    principal: Logistics, session: Session, unit_id: uuid.UUID, body: schemas.UnitIn
) -> schemas.UnitOut:
    unit = await resources.save_unit(session, principal, body, unit_id)
    await audit.record(session, actor=audit.actor_of(principal), action="unit.update", target=f"unit:{unit.id}")
    out = await resources.unit_out(session, unit)
    await session.commit()
    return out


@router.delete("/units/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unit(principal: Logistics, session: Session, unit_id: uuid.UUID) -> Response:
    await resources.delete_unit(session, principal, unit_id)
    await audit.record(session, actor=audit.actor_of(principal), action="unit.delete", target=f"unit:{unit_id}")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


RESOURCE_STATUSES = ("available", "assigned", "out_of_service")
RESOURCE_KINDS = schemas.ResourceKind.__args__  # type: ignore[attr-defined]


@router.get("/resources", response_model=schemas.ResourcePage)
async def list_resources(
    principal: LogisticsReader,
    session: Session,
    status_: Annotated[str | None, Query(alias="status")] = None,
    kind: str | None = None,
    unit_id: uuid.UUID | None = None,
    gouvernorat_code: int | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    cursor: str | None = None,
) -> schemas.ResourcePage:
    items, next_cursor = await resources.list_resources(
        session,
        principal,
        statuses=_csv(status_, RESOURCE_STATUSES, "invalid_status"),
        kinds=_csv(kind, RESOURCE_KINDS, "invalid_kind"),
        unit_id=unit_id,
        gouvernorat_code=gouvernorat_code,
        limit=limit,
        cursor=cursor,
    )
    return schemas.ResourcePage(items=items, next_cursor=next_cursor)


@router.get("/resources/summary", response_model=schemas.ResourceSummary)
async def resources_summary(principal: LogisticsReader, session: Session) -> schemas.ResourceSummary:
    return await resources.summary(session, principal)


@router.get("/resources/map")
async def resources_map(principal: LogisticsReader, session: Session, bbox: str | None = None) -> dict[str, Any]:
    return await resources.map_features(session, principal, _bbox(bbox))


@router.post("/resources", response_model=schemas.ResourceOut, status_code=status.HTTP_201_CREATED)
async def create_resource(principal: Logistics, session: Session, body: schemas.ResourceIn) -> schemas.ResourceOut:
    resource = await resources.save_resource(session, principal, body)
    await audit.record(
        session, actor=audit.actor_of(principal), action="resource.create", target=f"resource:{resource.id}"
    )
    await resources.announce(session, resource.id)
    out = await resources.resource_out(session, resource.id)
    await session.commit()
    return out


@router.put("/resources/{resource_id}", response_model=schemas.ResourceOut)
async def update_resource(
    principal: Logistics, session: Session, resource_id: uuid.UUID, body: schemas.ResourceIn
) -> schemas.ResourceOut:
    resource = await resources.save_resource(session, principal, body, resource_id)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="resource.update",
        target=f"resource:{resource.id}",
        details={"status": resource.status},
    )
    await resources.announce(session, resource.id)
    out = await resources.resource_out(session, resource.id)
    await session.commit()
    return out


@router.delete("/resources/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(principal: Logistics, session: Session, resource_id: uuid.UUID) -> Response:
    await resources.delete_resource(session, principal, resource_id)
    await audit.record(
        session, actor=audit.actor_of(principal), action="resource.delete", target=f"resource:{resource_id}"
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
