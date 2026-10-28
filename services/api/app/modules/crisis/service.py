"""Disaster and crisis axes with the database (phase L3, docs/phase-l/design-l3.md).

Numbering, the figures of an axis (computed from the attached interventions, never typed), the interventions an axis
suggests, the timeline, signed recommendations and decisions, situation reports and the closing record. Callers
check the role (domain.py) and commit; row-level security keeps every axis in its gouvernorats (migration 0056).
"""

import base64
import json
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from geoalchemy2 import Geography, Geometry
from sqlalchemy import cast, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import emit
from app.core.security import Principal
from app.modules.audit import service as audit
from app.modules.crisis import domain, schemas
from app.modules.crisis.models import (
    Axis,
    AxisEvent,
    AxisIncident,
    DeclarationRequest,
    Directive,
    DirectiveEvent,
    Dismissal,
    Evacuation,
    Need,
    Shelter,
    Sitrep,
)
from app.modules.evidence.service import signing_key
from app.modules.geo.models import Gouvernorat
from app.modules.ops.models import Assignment, CasualtyCount, Incident, Resource
from app.modules.orgs.certificate import key_id_of
from app.modules.settings import service as settings
from app.modules.settings.domain import CRISIS_SITREP_HOURS

SYSTEM = "system"
OPEN_INCIDENT = "open"
LIVE_ASSIGNMENT = (Assignment.released_at.is_(None), Assignment.cancelled_at.is_(None))
SUGGESTIONS_LIMIT = 50


def now() -> datetime:
    return datetime.now(UTC)


def error(code: int, detail: str) -> HTTPException:
    return HTTPException(code, detail)


def not_found(detail: str) -> HTTPException:
    return error(status.HTTP_404_NOT_FOUND, detail)


def conflict(detail: str) -> HTTPException:
    return error(status.HTTP_409_CONFLICT, detail)


def forbidden(detail: str = "insufficient_role") -> HTTPException:
    return error(status.HTTP_403_FORBIDDEN, detail)


# --- Geometry -------------------------------------------------------------------------------------------------------


def area_value(area: schemas.Area | None) -> Any:
    """A drawn polygon as a geography(MULTIPOLYGON) expression, or None."""
    if area is None:
        return None
    geojson = json.dumps(area.model_dump())
    return cast(func.ST_Multi(func.ST_SetSRID(func.ST_GeomFromGeoJSON(geojson), 4326)), Geography)


async def check_area(session: AsyncSession, area: schemas.Area | None) -> None:
    if area is None:
        return
    valid = await session.scalar(
        text("SELECT ST_IsValid(ST_SetSRID(ST_GeomFromGeoJSON(:g), 4326))"), {"g": json.dumps(area.model_dump())}
    )
    if not valid:
        raise error(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_area")


def geojson_of(column: Any) -> Any:
    return func.ST_AsGeoJSON(cast(column, Geometry), 6)


async def geojson(session: AsyncSession, model: Any, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, dict[str, Any]]:
    ids = list(ids)
    if not ids:
        return {}
    rows = await session.execute(
        select(model.id, geojson_of(model.area)).where(model.id.in_(ids), model.area.isnot(None))
    )
    return {row[0]: json.loads(row[1]) for row in rows.all()}


# --- Numbering, loading, timeline -----------------------------------------------------------------------------------


async def next_number(session: AsyncSession, year: int) -> str:
    n = await session.scalar(
        text(
            "INSERT INTO crisis.counter (year, last) VALUES (:y, 1) "
            "ON CONFLICT (year) DO UPDATE SET last = crisis.counter.last + 1 RETURNING last"
        ),
        {"y": year},
    )
    return domain.axis_number(year, int(n))


async def get_axis(session: AsyncSession, axis_id: uuid.UUID, *, lock: bool = False) -> Axis:
    query = select(Axis).where(Axis.id == axis_id)
    found = await session.scalar(query.with_for_update() if lock else query)
    if found is None:
        raise not_found("axis_not_found")
    return found


async def family(session: AsyncSession, axis: Axis) -> list[Axis]:
    """The axis and, for a national root, its sub-axes the caller sees."""
    children = list(
        await session.scalars(select(Axis).where(Axis.parent_id == axis.id).order_by(Axis.gouvernorat_code))
    )
    return [axis, *children]


async def codes_of(session: AsyncSession, axis: Axis) -> list[int]:
    if axis.gouvernorat_code is not None:
        return [axis.gouvernorat_code]
    rows = await session.scalars(text("SELECT unnest(crisis.axis_gouvernorats(:id))"), {"id": axis.id})
    return sorted(int(c) for c in rows)


def unit_gouvernorat(axis: Axis) -> int | None:
    """The gouvernorat whose room and governor act on the axis (None: a national root, the commander's)."""
    return axis.gouvernorat_code


async def add_event(
    session: AsyncSession,
    axis_id: uuid.UUID,
    principal: Principal | None,
    kind: str,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        AxisEvent(
            axis_id=axis_id,
            actor=audit.actor_of(principal),
            actor_name=audit.name_of(principal),
            kind=kind,
            payload=payload or {},
            at=now(),
        )
    )


async def notify(session: AsyncSession, subject: str, axis: Axis, codes: list[int], **payload: Any) -> None:
    """A live event to the rooms, governors of ``codes`` and the national command (reports/live.py routes it)."""
    await emit(
        session,
        f"axis.{subject}",
        {
            "axis": {"id": str(axis.id), "number": axis.number, "name": axis.name, "level": axis.level},
            "gouvernorat_codes": codes,
            **payload,
        },
    )


async def sitrep_hours(session: AsyncSession) -> dict[str, int]:
    value = await settings.get(session, CRISIS_SITREP_HOURS)
    return value if isinstance(value, dict) else dict(domain.DEFAULT_SITREP_HOURS)


async def gouvernorat_names(session: AsyncSession) -> dict[int, str]:
    rows = await session.execute(select(Gouvernorat.code, Gouvernorat.name_ar))
    return dict(rows.all())


# --- Interventions and figures --------------------------------------------------------------------------------------


async def attached_ids(session: AsyncSession, axis_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    rows = await session.scalars(
        select(AxisIncident.incident_id).where(AxisIncident.axis_id.in_(axis_ids), AxisIncident.detached_at.is_(None))
    )
    return list(dict.fromkeys(rows))


async def figures(session: AsyncSession, axis_ids: list[uuid.UUID]) -> schemas.Figures:
    """The live figures of one axis or a family of axes (design §2.5): computed, never typed."""
    out = schemas.Figures()
    if not axis_ids:
        return out
    incident_ids = await attached_ids(session, axis_ids)
    if incident_ids:
        row = (
            await session.execute(
                select(func.count(), func.count().filter(Incident.status == OPEN_INCIDENT)).where(
                    Incident.id.in_(incident_ids)
                )
            )
        ).one()
        out.incidents, out.incidents_open = int(row[0]), int(row[1])
        c = (
            await session.execute(
                select(
                    func.coalesce(func.sum(CasualtyCount.deceased), 0),
                    func.coalesce(func.sum(CasualtyCount.injured_light), 0),
                    func.coalesce(func.sum(CasualtyCount.injured_serious), 0),
                    func.coalesce(func.sum(CasualtyCount.rescued), 0),
                    func.coalesce(func.sum(CasualtyCount.trapped), 0),
                ).where(CasualtyCount.incident_id.in_(incident_ids))
            )
        ).one()
        out.deceased, light, out.injured_serious, out.rescued, out.trapped = (int(v) for v in c)
        out.injured = light + out.injured_serious
        kinds = await session.execute(
            select(Resource.kind, func.count(func.distinct(Assignment.resource_id)))
            .join(Resource, Resource.id == Assignment.resource_id)
            .where(Assignment.incident_id.in_(incident_ids), *LIVE_ASSIGNMENT)
            .group_by(Resource.kind)
        )
        out.resources_by_kind = {k: int(n) for k, n in kinds.all()}
        out.resources = sum(out.resources_by_kind.values())
        out.volunteers = int(
            await session.scalar(
                select(func.count(func.distinct(Assignment.volunteer_id))).where(
                    Assignment.incident_id.in_(incident_ids), Assignment.volunteer_id.isnot(None), *LIVE_ASSIGNMENT
                )
            )
            or 0
        )
    s = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(Shelter.capacity), 0),
                func.coalesce(func.sum(Shelter.occupants), 0),
            ).where(Shelter.axis_id.in_(axis_ids))
        )
    ).one()
    out.shelters, out.shelter_capacity, out.sheltered = (int(v) for v in s)
    out.evacuated = int(
        await session.scalar(
            select(func.coalesce(func.sum(Evacuation.evacuated), 0)).where(Evacuation.axis_id.in_(axis_ids))
        )
        or 0
    )
    out.needs_open = int(
        await session.scalar(select(func.count()).where(Need.axis_id.in_(axis_ids), Need.status == "raised")) or 0
    )
    rows = await session.execute(
        select(Directive.kind, Directive.status, Directive.overridden_by, Directive.issued_at, Directive.done_at).where(
            Directive.axis_id.in_(axis_ids)
        )
    )
    execution = domain.execution_figures(dict(r._mapping) for r in rows.all())
    for key, value in execution.items():
        setattr(out, key, value)
    return out


async def incidents_out(
    session: AsyncSession, axis_ids: list[uuid.UUID], principal: Principal, *, ids: list[uuid.UUID] | None = None
) -> list[schemas.IncidentOut]:
    """The attached interventions (or the given ones) with their counts; the room's title for the rooms only."""
    links: dict[uuid.UUID, AxisIncident] = {}
    if ids is None:
        for link in await session.scalars(
            select(AxisIncident).where(AxisIncident.axis_id.in_(axis_ids), AxisIncident.detached_at.is_(None))
        ):
            links.setdefault(link.incident_id, link)
        ids = list(links)
    if not ids:
        return []
    lat = func.ST_Y(cast(Incident.centroid, Geometry))
    lon = func.ST_X(cast(Incident.centroid, Geometry))
    rows = (
        await session.execute(
            select(Incident, lat, lon, CasualtyCount)
            .outerjoin(CasualtyCount, CasualtyCount.incident_id == Incident.id)
            .where(Incident.id.in_(ids))
            .order_by(Incident.severity.desc().nulls_last(), Incident.opened_at.desc())
        )
    ).all()
    engaged = dict(
        (
            await session.execute(
                select(Assignment.incident_id, func.count(func.distinct(Assignment.resource_id)))
                .where(Assignment.incident_id.in_(ids), Assignment.resource_id.isnot(None), *LIVE_ASSIGNMENT)
                .group_by(Assignment.incident_id)
            )
        ).all()
    )
    room = domain.is_room(principal)
    out = []
    for incident, y, x, counts in rows:
        found = links.get(incident.id)
        out.append(
            schemas.IncidentOut(
                id=str(incident.id),
                axis_id=str(found.axis_id) if found else None,
                category=incident.category,
                severity=incident.severity,
                status=incident.status,
                gouvernorat_code=incident.gouvernorat_code,
                lat=y,
                lon=x,
                opened_at=incident.opened_at,
                title=incident.title if room else None,
                deceased=counts.deceased if counts else 0,
                injured=(counts.injured_light + counts.injured_serious) if counts else 0,
                rescued=counts.rescued if counts else 0,
                resources=int(engaged.get(incident.id, 0)),
                attached_by_name=found.attached_by_name if found and room else None,
                attached_at=found.attached_at if found else None,
            )
        )
    return out


async def suggestions(session: AsyncSession, axis: Axis, principal: Principal) -> list[schemas.IncidentOut]:
    """Open interventions inside the area (or the gouvernorat when no area is drawn), of a category that fits the kind,
    attached to no open axis and not dismissed for this one (design §2, step 3). Nothing is attached automatically."""
    if axis.status != "open" or axis.gouvernorat_code is None:
        return []
    taken = (
        select(AxisIncident.incident_id)
        .join(Axis, Axis.id == AxisIncident.axis_id)
        .where(AxisIncident.detached_at.is_(None), Axis.status == "open")
    )
    dismissed = select(Dismissal.incident_id).where(Dismissal.axis_id == axis.id)
    categories = sorted(domain.COMPATIBLE.get(axis.kind, domain.COMPATIBLE["other"]))
    query = select(Incident.id).where(
        Incident.status == OPEN_INCIDENT,
        Incident.category.in_(categories),
        Incident.id.not_in(taken),
        Incident.id.not_in(dismissed),
    )
    if axis.area is not None:
        query = query.where(
            or_(
                func.ST_Intersects(Incident.centroid, select(Axis.area).where(Axis.id == axis.id).scalar_subquery()),
                func.ST_Intersects(Incident.area, select(Axis.area).where(Axis.id == axis.id).scalar_subquery()),
            )
        )
    else:
        query = query.where(Incident.gouvernorat_code == axis.gouvernorat_code)
    ids = list(await session.scalars(query.order_by(Incident.opened_at.desc()).limit(SUGGESTIONS_LIMIT)))
    return await incidents_out(session, [axis.id], principal, ids=ids)


async def attach(session: AsyncSession, principal: Principal | None, axis: Axis, incident_id: uuid.UUID) -> bool:
    """Attach an intervention; False when already attached to this axis."""
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise not_found("incident_not_found")
    if incident.status in ("merged", "dissolved"):
        raise conflict("incident_not_attachable")
    if axis.gouvernorat_code is not None and incident.gouvernorat_code not in (None, axis.gouvernorat_code):
        raise conflict("incident_out_of_axis")
    elsewhere = await session.scalar(
        select(Axis.number)
        .join(AxisIncident, AxisIncident.axis_id == Axis.id)
        .where(
            AxisIncident.incident_id == incident_id,
            AxisIncident.detached_at.is_(None),
            Axis.status == "open",
            Axis.id != axis.id,
        )
    )
    if elsewhere:
        raise conflict("incident_in_other_axis")
    link = await session.get(AxisIncident, (axis.id, incident_id))
    actor, name = audit.actor_of(principal), audit.name_of(principal)
    if link is not None and link.detached_at is None:
        return False
    if link is None:
        session.add(AxisIncident(axis_id=axis.id, incident_id=incident_id, attached_by=actor, attached_by_name=name))
    else:
        link.attached_by, link.attached_by_name, link.attached_at = actor, name, now()
        link.detached_by = link.detached_by_name = link.detach_reason = None
        link.detached_at = None
    await add_event(
        session,
        axis.id,
        principal,
        "incident_attached",
        {"incident_id": str(incident_id), "category": incident.category},
    )
    return True


async def detach(session: AsyncSession, principal: Principal, axis: Axis, incident_id: uuid.UUID, reason: str) -> None:
    link = await session.get(AxisIncident, (axis.id, incident_id))
    if link is None or link.detached_at is not None:
        raise not_found("incident_not_attached")
    link.detached_by, link.detached_by_name = audit.actor_of(principal), audit.name_of(principal)
    link.detached_at, link.detach_reason = now(), reason
    await add_event(
        session, axis.id, principal, "incident_detached", {"incident_id": str(incident_id), "reason": reason}
    )


async def dismiss(session: AsyncSession, principal: Principal, axis: Axis, incident_id: uuid.UUID) -> None:
    if await session.get(Dismissal, (axis.id, incident_id)) is None:
        session.add(Dismissal(axis_id=axis.id, incident_id=incident_id, dismissed_by=audit.actor_of(principal)))


# --- Opening, escalation, closing -----------------------------------------------------------------------------------


async def create_axis(
    session: AsyncSession,
    principal: Principal,
    *,
    name: str,
    kind: str,
    level: int,
    gouvernorat_code: int | None,
    area: schemas.Area | None = None,
    plan: str = "",
    parent: Axis | None = None,
    request_id: uuid.UUID | None = None,
) -> Axis:
    opened = now()
    period = domain.sitrep_period(await sitrep_hours(session), level)
    axis = Axis(
        number=await next_number(session, opened.year),
        name=name,
        kind=kind,
        scope="national" if gouvernorat_code is None else "gouvernorat",
        parent_id=parent.id if parent else None,
        gouvernorat_code=gouvernorat_code,
        area=area_value(area),
        level=level,
        plan=plan,
        status="open",
        request_id=request_id,
        opened_by=audit.actor_of(principal),
        opened_by_name=audit.name_of(principal),
        opened_at=opened,
        next_sitrep_at=opened + period,
        version=1,
        updated_at=opened,
    )
    session.add(axis)
    await session.flush()
    await add_event(
        session, axis.id, principal, "opened", {"level": level, "parent": parent.number if parent else None}
    )
    return axis


async def open_axis(
    session: AsyncSession, principal: Principal, body: schemas.AxisIn, request: DeclarationRequest | None = None
) -> Axis:
    """The commander opens an axis: regional, or national with one sub-axis per gouvernorat (design §2)."""
    await check_area(session, body.area)
    common: dict[str, Any] = {"name": body.name, "kind": body.kind, "level": body.level, "plan": body.plan}
    if body.national:
        codes = sorted(set(body.gouvernorats) | ({body.gouvernorat_code} if body.gouvernorat_code else set()))
        if not codes:
            raise error(status.HTTP_422_UNPROCESSABLE_CONTENT, "gouvernorats_required")
        root = await create_axis(
            session,
            principal,
            gouvernorat_code=None,
            area=body.area,
            request_id=request.id if request else None,
            **common,
        )
        for code in codes:
            await create_axis(session, principal, gouvernorat_code=code, parent=root, **common)
        axis = root
    else:
        if body.gouvernorat_code is None:
            raise error(status.HTTP_422_UNPROCESSABLE_CONTENT, "gouvernorat_required")
        axis = await create_axis(
            session,
            principal,
            gouvernorat_code=body.gouvernorat_code,
            area=body.area,
            request_id=request.id if request else None,
            **common,
        )
        codes = [body.gouvernorat_code]
    for incident_id in body.incident_ids:
        target = axis
        if axis.scope == "national":
            incident = await session.get(Incident, incident_id)
            sub = await session.scalar(
                select(Axis).where(
                    Axis.parent_id == axis.id,
                    Axis.gouvernorat_code == (incident.gouvernorat_code if incident else None),
                )
            )
            if sub is None:
                continue
            target = sub
        await attach(session, principal, target, incident_id)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="crisis.axis_opened",
        target=str(axis.id),
        details={"number": axis.number, "kind": axis.kind, "level": axis.level, "scope": axis.scope},
        gouvernorats=codes,
    )
    await notify(session, "opened", axis, codes)
    return axis


async def escalate(session: AsyncSession, principal: Principal, axis: Axis, extra: list[int], reason: str) -> Axis:
    """A regional axis becomes the first sub-axis of a new national root; other gouvernorats become sub-axes too.
    Nothing is copied or lost: the regional axis keeps its interventions, components and decisions."""
    if axis.status != "open":
        raise conflict("axis_closed")
    if axis.parent_id is not None:
        axis = await get_axis(session, axis.parent_id, lock=True)
    if axis.scope == "national":
        root = axis
    else:
        root = await create_axis(
            session, principal, name=axis.name, kind=axis.kind, level=axis.level, gouvernorat_code=None, plan=axis.plan
        )
        if axis.area is not None:
            await session.execute(
                text("UPDATE crisis.axis SET area = (SELECT area FROM crisis.axis WHERE id = :src) WHERE id = :id"),
                {"src": axis.id, "id": root.id},
            )
        axis.parent_id = root.id
        axis.version += 1
        axis.updated_at = now()
        await add_event(session, axis.id, principal, "escalated", {"root": root.number, "reason": reason})
    existing = set(await session.scalars(select(Axis.gouvernorat_code).where(Axis.parent_id == root.id)))
    for code in sorted(set(extra) - existing):
        await create_axis(
            session,
            principal,
            name=root.name,
            kind=root.kind,
            level=root.level,
            gouvernorat_code=code,
            plan=root.plan,
            parent=root,
        )
    await session.flush()
    codes = await codes_of(session, root)
    await add_event(session, root.id, principal, "escalated", {"gouvernorats": codes, "reason": reason})
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="crisis.axis_escalated",
        target=str(root.id),
        reason=reason,
        details={"number": root.number, "gouvernorats": codes},
        gouvernorats=codes,
    )
    await notify(session, "escalated", root, codes)
    return root


async def close_axis(session: AsyncSession, principal: Principal, axis: Axis, summary: str) -> Axis:
    """The closing record (design §2.6) and a draft of the national memory with the timeline."""
    if axis.status != "open":
        raise conflict("axis_closed")
    if axis.parent_id is not None:
        raise conflict("close_the_national_axis")
    members = await family(session, axis)
    ids = [a.id for a in members]
    totals = await figures(session, ids)
    closed = now()
    hours = round((closed - axis.opened_at).total_seconds() / 3600, 1)
    closing = {**totals.model_dump(), "hours": hours, "summary": summary}
    for member in members:
        member.status = "closed"
        member.closed_by, member.closed_by_name, member.closed_at = (
            audit.actor_of(principal),
            audit.name_of(principal),
            closed,
        )
        member.closing = (
            closing if member.id == axis.id else {**(await figures(session, [member.id])).model_dump(), "hours": hours}
        )
        member.next_sitrep_at = None
        member.version += 1
        member.updated_at = closed
        await add_event(session, member.id, principal, "closed", {"hours": hours})
    codes = await codes_of(session, axis)
    axis.memory_id = await memory_draft(session, principal, axis, ids, totals, hours, summary, codes)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="crisis.axis_closed",
        target=str(axis.id),
        details={"number": axis.number, "closing": closing},
        gouvernorats=codes,
    )
    await notify(session, "closed", axis, codes)
    return axis


MEMORY_TYPE = {
    "flood": "flood",
    "forest_fire": "fire",
    "storm": "flood",
    "earthquake": "landslide",
    "technological": "chemical_leak",
    "health": "medical",
    "other": "other",
}


async def memory_draft(
    session: AsyncSession,
    principal: Principal,
    axis: Axis,
    ids: list[uuid.UUID],
    totals: schemas.Figures,
    hours: float,
    summary: str,
    codes: list[int],
) -> uuid.UUID | None:
    """A draft of the national memory (item 11): figures and timeline, no personal data; reviewed as usual."""
    from app.modules.knowledge import memory
    from app.modules.knowledge import schemas as ks

    events = list(await session.scalars(select(AxisEvent).where(AxisEvent.axis_id.in_(ids)).order_by(AxisEvent.at)))
    rows = [
        ("التدخلات الملحقة", totals.incidents),
        ("الوفيات", totals.deceased),
        ("الإصابات", totals.injured),
        ("المُنقَذون", totals.rescued),
        ("المُجلَون", totals.evacuated),
        ("طاقة الإيواء", totals.shelter_capacity),
        ("الموارد المسخّرة", totals.resources),
        ("القرارات المنفّذة", f"{totals.decisions_done} / {totals.decisions}"),
        ("متوسط زمن التنفيذ (ساعة)", totals.mean_hours_to_done if totals.mean_hours_to_done is not None else "—"),
        ("المدة (ساعة)", hours),
    ]
    table = "| المؤشر | القيمة |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k, v in rows)
    timeline = "| الوقت | الحدث |\n|---|---|\n" + "\n".join(f"| {e.at:%Y-%m-%d %H:%M} | {e.kind} |" for e in events)
    incident_ids = (await attached_ids(session, ids))[:50]
    area = await session.scalar(select(geojson_of(Axis.area)).where(Axis.id == axis.id, Axis.area.isnot(None)))
    try:
        fields = ks.EntryIn.model_validate(
            {
                "title": {"ar": f"{axis.name} ({axis.number})", "fr": f"{axis.name} ({axis.number})"},
                "event_type": MEMORY_TYPE.get(axis.kind, "other"),
                "started_at": axis.opened_at,
                "ended_at": axis.closed_at,
                "gouvernorats": codes,
                "geometry": json.loads(area) if area else None,
                "incident_ids": incident_ids,
                "summary": {
                    "ar": f"{summary}\n\n### الحصيلة\n\n{table}\n\n### الخط الزمني\n\n{timeline}",
                    "fr": "",
                },
                "access": "national",
            }
        )
        entry = await memory.create(session, principal, fields)
    except HTTPException:
        return None
    await session.flush()
    return entry.id


# --- Requests -------------------------------------------------------------------------------------------------------


async def create_request(session: AsyncSession, principal: Principal, body: schemas.RequestIn) -> DeclarationRequest:
    await check_area(session, body.area)
    code = principal.gouvernorat_code
    assert code is not None
    request = DeclarationRequest(
        gouvernorat_code=code,
        name=body.name,
        kind=body.kind,
        level=body.level,
        facts=body.facts,
        incident_ids=list(dict.fromkeys(body.incident_ids)),
        area=area_value(body.area),
        status="pending",
        created_by=audit.actor_of(principal),
        created_by_name=audit.name_of(principal),
    )
    session.add(request)
    await session.flush()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="crisis.request_created",
        target=str(request.id),
        details={"name": body.name, "kind": body.kind, "level": body.level},
        gouvernorats=[code],
    )
    await emit(
        session, "axis.requested", {"request": {"id": str(request.id), "name": request.name}, "gouvernorat_codes": []}
    )
    return request


async def decide_request(
    session: AsyncSession, principal: Principal, request: DeclarationRequest, accept: bool, reason: str
) -> DeclarationRequest:
    if request.status != "pending":
        raise conflict("request_decided")
    request.decided_by, request.decided_by_name, request.decided_at = (
        audit.actor_of(principal),
        audit.name_of(principal),
        now(),
    )
    request.decision_reason = reason or None
    if accept:
        area = await session.scalar(
            select(geojson_of(DeclarationRequest.area)).where(DeclarationRequest.id == request.id)
        )
        body = schemas.AxisIn(
            name=request.name,
            kind=request.kind,
            level=request.level,
            gouvernorat_code=request.gouvernorat_code,
            area=schemas.Area.model_validate(json.loads(area)) if area else None,
            incident_ids=list(request.incident_ids),
        )
        axis = await open_axis(session, principal, body, request)
        request.status, request.axis_id = "accepted", axis.id
    else:
        request.status = "rejected"
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="crisis.request_" + request.status,
        target=str(request.id),
        reason=reason or None,
        gouvernorats=[request.gouvernorat_code],
    )
    await emit(
        session,
        "axis.request_decided",
        {"request": {"id": str(request.id), "status": request.status}, "gouvernorat_codes": [request.gouvernorat_code]},
    )
    return request


# --- Recommendations and decisions ----------------------------------------------------------------------------------


def sign(payload: bytes) -> tuple[str | None, str | None]:
    key = signing_key()
    if key is None:
        return None, None
    return base64.b64encode(key.sign(payload)).decode(), key_id_of(key.public_key())


async def issue(session: AsyncSession, principal: Principal, axis: Axis, body: schemas.DirectiveIn) -> Directive:
    """A signed recommendation or decision (design §4); a minister's decision overrides the governor's pending ones
    of the same category on the same axis."""
    if axis.status != "open":
        raise conflict("axis_closed")
    role = domain.issuer_role(principal)
    assert role is not None
    if body.executor == "partner" and not body.executor_name:
        raise error(status.HTTP_422_UNPROCESSABLE_CONTENT, "executor_name_required")
    if body.due_at is not None and body.due_at <= now():
        raise error(status.HTTP_422_UNPROCESSABLE_CONTENT, "due_in_past")
    await check_area(session, body.area)
    number = (
        int(
            await session.scalar(
                select(func.coalesce(func.max(Directive.number), 0)).where(Directive.axis_id == axis.id)
            )
            or 0
        )
        + 1
    )
    issued = now()
    directive_id = uuid.uuid4()
    issued_by = audit.actor_of(principal)
    payload = domain.signed_payload(
        directive_id=str(directive_id),
        axis_number=axis.number,
        number=number,
        kind=body.kind,
        category=body.category,
        body=body.body,
        executor=body.executor,
        executor_name=body.executor_name,
        due_at=body.due_at,
        issuer_role=role,
        issued_by=issued_by,
        issued_at=issued,
    )
    signature, key_id = sign(payload)
    directive = Directive(
        id=directive_id,
        axis_id=axis.id,
        number=number,
        kind=body.kind,
        category=body.category,
        body=body.body,
        area=area_value(body.area),
        executor=body.executor,
        executor_name=body.executor_name,
        due_at=body.due_at,
        status="issued",
        issuer_role=role,
        issued_by=issued_by,
        issued_by_name=audit.name_of(principal),
        issued_at=issued,
        signature=signature,
        key_id=key_id,
        updated_at=issued,
    )
    session.add(directive)
    await session.flush()
    session.add(
        DirectiveEvent(
            directive_id=directive.id,
            axis_id=axis.id,
            status="issued",
            by_actor=issued_by,
            by_name=directive.issued_by_name,
            at=issued,
        )
    )
    earlier = [
        domain.Issued(str(d.id), d.kind, d.category, d.issuer_role, d.status, d.overridden_by is not None)
        for d in await session.scalars(
            select(Directive).where(Directive.axis_id == axis.id, Directive.id != directive.id)
        )
    ]
    overridden = domain.overridden_by_minister(body.kind, body.category, role, earlier)
    if overridden:
        await session.execute(
            update(Directive)
            .where(Directive.id.in_([uuid.UUID(i) for i in overridden]))
            .values(overridden_by=directive.id, updated_at=issued)
        )
    codes = await codes_of(session, axis)
    await add_event(
        session,
        axis.id,
        principal,
        "directive_issued",
        {"number": number, "kind": body.kind, "category": body.category, "role": role, "overrides": overridden},
    )
    await audit.record(
        session,
        actor=issued_by,
        action="crisis.directive_issued",
        target=str(directive.id),
        details={
            "axis": axis.number,
            "number": number,
            "kind": body.kind,
            "category": body.category,
            "role": role,
            "digest": domain.digest(payload),
            "key_id": key_id,
            "overrides": overridden,
        },
        gouvernorats=codes,
    )
    await notify(
        session,
        "directive",
        axis,
        codes,
        directive={
            "id": str(directive.id),
            "number": number,
            "kind": body.kind,
            "category": body.category,
            "executor": body.executor,
            "status": "issued",
            "overrides": overridden,
        },
    )
    return directive


async def set_directive_status(
    session: AsyncSession, principal: Principal | None, axis: Axis, directive: Directive, new: str, reason: str
) -> Directive:
    if directive.overridden_by is not None:
        raise conflict("directive_overridden")
    if new not in domain.NEXT_STATUS.get(directive.status, frozenset()):
        raise conflict("invalid_transition")
    if new == "failed" and len(reason.strip()) < 5:
        raise error(status.HTTP_422_UNPROCESSABLE_CONTENT, "reason_required")
    at = now()
    directive.status, directive.status_reason, directive.updated_at = new, reason or None, at
    if new == "done":
        directive.done_at = at
    actor, name = audit.actor_of(principal), audit.name_of(principal)
    session.add(
        DirectiveEvent(
            directive_id=directive.id,
            axis_id=axis.id,
            status=new,
            reason=reason or None,
            by_actor=actor,
            by_name=name,
            at=at,
        )
    )
    codes = await codes_of(session, axis)
    await add_event(
        session, axis.id, principal, "directive_" + new, {"number": directive.number, "reason": reason or None}
    )
    await audit.record(
        session,
        actor=actor,
        action="crisis.directive_status",
        target=str(directive.id),
        reason=reason or None,
        details={"axis": axis.number, "number": directive.number, "status": new},
        gouvernorats=codes,
    )
    await notify(
        session,
        "directive",
        axis,
        codes,
        directive={"id": str(directive.id), "number": directive.number, "status": new, "reason": reason or None},
    )
    return directive


async def directives_out(
    session: AsyncSession, directives: list[Directive], principal: Principal, axes: dict[uuid.UUID, Axis]
) -> list[schemas.DirectiveOut]:
    if not directives:
        return []
    areas = await geojson(session, Directive, [d.id for d in directives])
    history: dict[uuid.UUID, list[schemas.DirectiveEventOut]] = {}
    for e in await session.scalars(
        select(DirectiveEvent)
        .where(DirectiveEvent.directive_id.in_([d.id for d in directives]))
        .order_by(DirectiveEvent.at, DirectiveEvent.id)
    ):
        history.setdefault(e.directive_id, []).append(
            schemas.DirectiveEventOut(status=e.status, reason=e.reason, by_name=e.by_name, at=e.at)
        )
    at = now()
    out = []
    for d in directives:
        axis = axes.get(d.axis_id)
        gouvernorat = axis.gouvernorat_code if axis else None
        out.append(
            schemas.DirectiveOut(
                id=str(d.id),
                axis_id=str(d.axis_id),
                axis_number=axis.number if axis else "",
                number=d.number,
                kind=d.kind,
                category=d.category,
                body=d.body,
                area=areas.get(d.id),
                executor=d.executor,
                executor_name=d.executor_name,
                due_at=d.due_at,
                status=d.status,
                status_reason=d.status_reason,
                issuer_role=d.issuer_role,
                issued_by_name=d.issued_by_name,
                issued_at=d.issued_at,
                signature=d.signature,
                key_id=d.key_id,
                overridden_by=str(d.overridden_by) if d.overridden_by else None,
                overdue=bool(d.due_at and d.due_at < at and d.status not in domain.FINAL_STATUSES),
                done_at=d.done_at,
                events=history.get(d.id, []),
                can_update=(
                    d.overridden_by is None
                    and d.status not in domain.FINAL_STATUSES
                    and axis is not None
                    and axis.status == "open"
                    and domain.can_update_directive(principal, d.executor, gouvernorat)
                ),
            )
        )
    return out


# --- Situation reports ----------------------------------------------------------------------------------------------


async def draft_sitrep(session: AsyncSession, principal: Principal | None, axis: Axis) -> Sitrep:
    """A draft from the figures; the room adds its assessment and sends it."""
    members = await family(session, axis)
    totals = await figures(session, [a.id for a in members])
    number = (
        int(
            await session.scalar(select(func.coalesce(func.max(Sitrep.number), 0)).where(Sitrep.axis_id == axis.id))
            or 0
        )
        + 1
    )
    sitrep = Sitrep(
        axis_id=axis.id,
        number=number,
        figures={**totals.model_dump(), "level": axis.level},
        assessment="",
        status="draft",
        created_by=audit.actor_of(principal),
        created_at=now(),
    )
    session.add(sitrep)
    await session.flush()
    await add_event(session, axis.id, principal, "sitrep_drafted", {"number": number})
    return sitrep


async def send_sitrep(
    session: AsyncSession, principal: Principal, axis: Axis, sitrep: Sitrep, assessment: str
) -> Sitrep:
    if sitrep.status != "draft":
        raise conflict("sitrep_sent")
    members = await family(session, axis)
    totals = await figures(session, [a.id for a in members])
    sitrep.figures = {**totals.model_dump(), "level": axis.level}
    sitrep.assessment = assessment
    sitrep.status = "sent"
    sitrep.sent_by, sitrep.sent_by_name, sitrep.sent_at = audit.actor_of(principal), audit.name_of(principal), now()
    axis.next_sitrep_at = sitrep.sent_at + domain.sitrep_period(await sitrep_hours(session), axis.level)
    codes = await codes_of(session, axis)
    await add_event(session, axis.id, principal, "sitrep_sent", {"number": sitrep.number})
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="crisis.sitrep_sent",
        target=str(sitrep.id),
        details={"axis": axis.number, "number": sitrep.number},
        gouvernorats=codes,
    )
    await notify(session, "sitrep", axis, codes, sitrep={"id": str(sitrep.id), "number": sitrep.number})
    return sitrep


def sitrep_out(s: Sitrep) -> schemas.SitrepOut:
    return schemas.SitrepOut(
        id=str(s.id),
        axis_id=str(s.axis_id),
        number=s.number,
        figures=s.figures,
        assessment=s.assessment,
        status=s.status,
        created_at=s.created_at,
        sent_by_name=s.sent_by_name,
        sent_at=s.sent_at,
    )


# --- Worker ---------------------------------------------------------------------------------------------------------


async def tick(session: AsyncSession) -> dict[str, int]:
    """Situation report drafts when due, reminders an hour before a deadline, alerts when it passes (design §5).
    Runs with the system scope (every axis)."""
    at = now()
    result = {"sitreps": 0, "reminders": 0, "overdue": 0}
    due = list(
        await session.scalars(
            select(Axis).where(Axis.status == "open", Axis.next_sitrep_at <= at).with_for_update(skip_locked=True)
        )
    )
    hours = await sitrep_hours(session)
    for axis in due:
        pending = await session.scalar(select(func.count()).where(Sitrep.axis_id == axis.id, Sitrep.status == "draft"))
        if not pending:
            await draft_sitrep(session, None, axis)
            await notify(session, "sitrep_due", axis, await codes_of(session, axis))
            result["sitreps"] += 1
        axis.next_sitrep_at = at + domain.sitrep_period(hours, axis.level)
    live = (
        Directive.status.not_in(tuple(domain.FINAL_STATUSES)),
        Directive.overridden_by.is_(None),
        Directive.due_at.isnot(None),
    )
    for directive in await session.scalars(
        select(Directive).where(
            *live, Directive.reminded_at.is_(None), Directive.due_at <= at + domain.REMIND_BEFORE, Directive.due_at > at
        )
    ):
        directive.reminded_at = at
        owner = await session.get(Axis, directive.axis_id)
        if owner is not None:
            deadline = directive.due_at.isoformat() if directive.due_at else None
            ref = {"id": str(directive.id), "number": directive.number, "due_at": deadline}
            await notify(session, "directive_reminder", owner, await codes_of(session, owner), directive=ref)
        result["reminders"] += 1
    for directive in await session.scalars(
        select(Directive).where(*live, Directive.overdue_at.is_(None), Directive.due_at <= at)
    ):
        directive.overdue_at = at
        owner = await session.get(Axis, directive.axis_id)
        if owner is not None:
            await add_event(session, owner.id, None, "directive_overdue", {"number": directive.number})
            ref = {"id": str(directive.id), "number": directive.number, "issuer_role": directive.issuer_role}
            await notify(session, "directive_overdue", owner, await codes_of(session, owner), directive=ref)
        result["overdue"] += 1
    return result
