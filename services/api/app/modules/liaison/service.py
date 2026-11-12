"""Informing the partner bodies by phone, OS20 (docs/phase-os20/design-os20.md).

The level of a report: 1, handled in the room and closed without informing anyone; 2, one or more bodies are informed.
The decision engine suggests the bodies (the services involved by the incident's type and classification, the central
room when the level or the priority calls for regional coordination); each suggestion is matched with the body of the
contact system in the incident's gouvernorat, else the national one, else shown as missing with its public number.

The link with the bodies is the phone only. A call is placed from the room's softphone or dialled by hand; the agent
records its result, what was asked and promised, the expected arrival, a note and a follow-up reminder. The parties
informed stay attached to the report: the history of the reports shows them with the result of their last call.

Scope: the rows are read under row level security (a regional room: its gouvernorat and the national bodies). A body is
kept by the room it belongs to: the regional room of its gouvernorat, the central room for a national body. The central
room may add a missing body of any gouvernorat from a report; the regional room then keeps it.
"""

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from geoalchemy2 import Geometry
from sqlalchemy import Select, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.modules.audit import service as audit
from app.modules.decision import domain, responders
from app.modules.decision.context import NoEnvironment, gather
from app.modules.decision.schemas import Bilingual
from app.modules.liaison import schemas
from app.modules.liaison.models import Body, Call, IncidentLevel, Official, Party
from app.modules.ops.models import Incident, OpLevel
from app.modules.telephony.models import Call as PhoneCall

#: Priority from which the central room is suggested even at the normal level (the committee rule of the engine).
CENTRAL_SEVERITY = 80
HISTORY_LIMIT = 40
USED_BEFORE_LIMIT = 10
_LAT = func.ST_Y(cast(Body.location, Geometry))
_LON = func.ST_X(cast(Body.location, Geometry))

CENTRAL_REASON = Bilingual(ar="مستوى عملياتي أو أولوية عالية: إعلام القاعة المركزية", fr="niveau ou priorité élevés")
DG_REASON = Bilingual(ar="حالة أزمة أو كارثة: إعلام المدير العام", fr="crise ou catastrophe : informer le DG")


def _now() -> datetime:
    return datetime.now(UTC)


def _name(principal: Principal) -> str | None:
    return audit.name_of(principal)


def _not_found(what: str = "not_found") -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, what)


def _point(p: schemas.Point) -> Any:
    return func.ST_SetSRID(func.ST_MakePoint(p.lon, p.lat), 4326)


def editable(principal: Principal, gouvernorat_code: int | None) -> bool:
    """The room that keeps a body: the central room the national ones, a regional room those of its gouvernorat."""
    if principal.is_national:
        return gouvernorat_code is None
    return gouvernorat_code is not None and gouvernorat_code == principal.gouvernorat_code


async def _record(
    session: AsyncSession, principal: Principal, action: str, target: str, gouvernorat: int | None, **details: Any
) -> None:
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action=f"liaison.{action}",
        target=target,
        details=details or None,
        gouvernorats=[gouvernorat] if gouvernorat else None,
    )


# ---------------------------------------------------------------- the contact system


def _official_out(o: Official) -> schemas.OfficialOut:
    return schemas.OfficialOut(
        id=o.id,
        body_id=o.body_id,
        name=o.name,
        role=o.role,
        phones=list(o.phones),
        email=o.email,
        duty=o.duty,
        position=o.position,
        status=o.status,
        updated_at=o.updated_at,
        updated_by_name=o.updated_by_name,
    )


def _body_out(
    principal: Principal, b: Body, lat: float | None, lon: float | None, officials: list[Official]
) -> schemas.BodyOut:
    return schemas.BodyOut(
        id=b.id,
        gouvernorat_code=b.gouvernorat_code,
        category=b.category,
        kind=b.kind,
        agency=b.agency,
        name=b.name,
        domain=b.domain,
        address=b.address,
        location=schemas.Point(lat=float(lat), lon=float(lon)) if lat is not None and lon is not None else None,
        public_phone=b.public_phone,
        status=b.status,
        created_by_name=b.created_by_name,
        updated_at=b.updated_at,
        updated_by_name=b.updated_by_name,
        version=b.version,
        editable=editable(principal, b.gouvernorat_code),
        officials=[_official_out(o) for o in officials],
    )


async def _officials(session: AsyncSession, body_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[Official]]:
    out: dict[uuid.UUID, list[Official]] = defaultdict(list)
    if not body_ids:
        return out
    rows = await session.scalars(
        select(Official)
        .where(Official.body_id.in_(body_ids), Official.status == "active")
        .order_by(Official.position, Official.name)
    )
    for o in rows:
        out[o.body_id].append(o)
    return out


async def _outs(session: AsyncSession, principal: Principal, query: Select[Any]) -> list[schemas.BodyOut]:
    rows = (await session.execute(query)).all()
    officials = await _officials(session, [r[0].id for r in rows])
    return [_body_out(principal, b, lat, lon, officials.get(b.id, [])) for b, lat, lon in rows]


async def list_bodies(
    session: AsyncSession,
    principal: Principal,
    *,
    gouvernorat: int | None = None,
    national: bool = False,
    category: str | None = None,
    q: str | None = None,
    archived: bool = False,
) -> list[schemas.BodyOut]:
    """The bodies the caller reads. ``gouvernorat``: that gouvernorat's bodies and the national ones (the picker of the
    central room once the gouvernorat is chosen); ``national``: the national bodies only."""
    query = select(Body, _LAT, _LON).where(Body.status == ("archived" if archived else "active"))
    if national:
        query = query.where(Body.gouvernorat_code.is_(None))
    elif gouvernorat is not None:
        query = query.where(or_(Body.gouvernorat_code == gouvernorat, Body.gouvernorat_code.is_(None)))
    if category:
        query = query.where(Body.category == category)
    if q and q.strip():
        like = f"%{q.strip()}%"
        matching = select(Official.body_id).where(
            Official.status == "active",
            or_(
                Official.name.ilike(like),
                Official.role.ilike(like),
                func.array_to_string(Official.phones, " ").ilike(like),
            ),
        )
        query = query.where(
            or_(Body.name.ilike(like), Body.domain.ilike(like), Body.address.ilike(like), Body.id.in_(matching))
        )
    query = query.order_by(Body.gouvernorat_code.is_(None).desc(), Body.kind.desc(), Body.category, Body.name)
    return await _outs(session, principal, query)


async def get_body(session: AsyncSession, principal: Principal, body_id: uuid.UUID) -> schemas.BodyOut:
    out = await _outs(session, principal, select(Body, _LAT, _LON).where(Body.id == body_id))
    if not out:
        raise _not_found()
    return out[0]


async def _body(session: AsyncSession, body_id: uuid.UUID) -> Body:
    body = await session.get(Body, body_id)
    if body is None:
        raise _not_found("body_not_found")
    return body


async def _kept_body(session: AsyncSession, principal: Principal, body_id: uuid.UUID) -> Body:
    """A body the caller's room keeps, locked. The check comes first: under row level security a row the caller may
    not update is not even seen by ``FOR UPDATE``."""
    body = await _body(session, body_id)
    _keeper(principal, body)
    await session.refresh(body, with_for_update=True)
    return body


def _keeper(principal: Principal, body: Body) -> None:
    if not editable(principal, body.gouvernorat_code):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_owner")


async def create_body(session: AsyncSession, principal: Principal, data: schemas.BodyIn) -> schemas.BodyOut:
    code = data.gouvernorat_code
    if not principal.is_national:
        code = code or principal.gouvernorat_code
        if code != principal.gouvernorat_code:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "outside_gouvernorat")
    if data.agency is not None:
        taken = await session.scalar(
            select(Body.id).where(
                Body.agency == data.agency,
                Body.status == "active",
                Body.gouvernorat_code.is_(None) if code is None else Body.gouvernorat_code == code,
            )
        )
        if taken is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "agency_exists")
    if data.origin_incident_id is not None:
        from app.modules.ops import service as incidents

        await incidents.get_in_scope(session, principal, data.origin_incident_id)
    name = _name(principal)
    body = Body(
        gouvernorat_code=code,
        category=data.category,
        kind=data.kind,
        agency=data.agency,
        name=data.name,
        domain=data.domain,
        address=data.address,
        location=_point(data.location) if data.location else None,
        public_phone=data.public_phone,
        origin_incident_id=data.origin_incident_id,
        created_by_name=name,
        updated_by_name=name,
    )
    session.add(body)
    await session.flush()
    for o in data.officials:
        session.add(_new_official(body.id, o, name))
    await session.flush()
    await _record(
        session,
        principal,
        "body_create",
        f"liaison_body:{body.id}",
        code,
        name=body.name,
        origin_incident_id=str(data.origin_incident_id) if data.origin_incident_id else None,
    )
    return await get_body(session, principal, body.id)


async def patch_body(
    session: AsyncSession, principal: Principal, body_id: uuid.UUID, data: schemas.BodyPatch
) -> schemas.BodyOut:
    body = await _kept_body(session, principal, body_id)
    if body.version != data.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
    changed = data.model_dump(exclude_unset=True, exclude={"version", "location"})
    for key, value in changed.items():
        setattr(body, key, value)
    if "location" in data.model_fields_set:
        body.location = _point(data.location) if data.location else None
    body.version += 1
    body.updated_at = _now()
    body.updated_by_name = _name(principal)
    await session.flush()
    await _record(
        session, principal, "body_update", f"liaison_body:{body.id}", body.gouvernorat_code, fields=sorted(changed)
    )
    await session.refresh(body)
    return await get_body(session, principal, body.id)


async def archive_body(session: AsyncSession, principal: Principal, body_id: uuid.UUID) -> schemas.BodyOut:
    body = await _kept_body(session, principal, body_id)
    if (
        body.kind == "internal"
        and body.gouvernorat_code is None
        and body.agency in ("central_room", "director_general")
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "internal_body")
    body.status = "archived"
    body.version += 1
    body.updated_at = _now()
    body.updated_by_name = _name(principal)
    await session.flush()
    await _record(session, principal, "body_archive", f"liaison_body:{body.id}", body.gouvernorat_code)
    await session.refresh(body)
    return await get_body(session, principal, body.id)


def _new_official(body_id: uuid.UUID, o: schemas.OfficialIn, by: str | None) -> Official:
    return Official(
        body_id=body_id,
        name=o.name,
        role=o.role,
        phones=list(o.phones),
        email=o.email,
        duty=o.duty,
        position=o.position,
        updated_by_name=by,
    )


async def add_official(
    session: AsyncSession, principal: Principal, body_id: uuid.UUID, data: schemas.OfficialIn
) -> schemas.OfficialOut:
    body = await _body(session, body_id)
    _keeper(principal, body)
    if body.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "body_archived")
    official = _new_official(body.id, data, _name(principal))
    session.add(official)
    await session.flush()
    await session.refresh(official)
    await _record(session, principal, "official_create", f"liaison_body:{body.id}", body.gouvernorat_code)
    return _official_out(official)


async def _official(session: AsyncSession, principal: Principal, official_id: uuid.UUID) -> tuple[Official, Body]:
    official = await session.get(Official, official_id)
    if official is None:
        raise _not_found("official_not_found")
    body = await _body(session, official.body_id)
    _keeper(principal, body)
    await session.refresh(official, with_for_update=True)
    return official, body


async def patch_official(
    session: AsyncSession, principal: Principal, official_id: uuid.UUID, data: schemas.OfficialPatch
) -> schemas.OfficialOut:
    official, body = await _official(session, principal, official_id)
    changed = data.model_dump(exclude_unset=True)
    for key, value in changed.items():
        setattr(official, key, list(value) if key == "phones" else value)
    official.updated_at = _now()
    official.updated_by_name = _name(principal)
    await session.flush()
    await session.refresh(official)
    await _record(
        session,
        principal,
        "official_update",
        f"liaison_body:{body.id}",
        body.gouvernorat_code,
        official_id=str(official.id),
        fields=sorted(changed),
    )
    return _official_out(official)


async def archive_official(session: AsyncSession, principal: Principal, official_id: uuid.UUID) -> None:
    official, body = await _official(session, principal, official_id)
    official.status = "archived"
    official.updated_at = _now()
    official.updated_by_name = _name(principal)
    await session.flush()
    await _record(
        session,
        principal,
        "official_archive",
        f"liaison_body:{body.id}",
        body.gouvernorat_code,
        official_id=str(official.id),
    )


# ---------------------------------------------------------------- suggestions


async def _match(session: AsyncSession, agency: str, code: int | None) -> Body | None:
    """The body of a service in the incident's gouvernorat, else the national one."""
    rows = await session.scalars(
        select(Body)
        .where(
            Body.agency == agency,
            Body.status == "active",
            or_(Body.gouvernorat_code.is_(None), Body.gouvernorat_code == code)
            if code is not None
            else Body.gouvernorat_code.is_(None),
        )
        .order_by(Body.gouvernorat_code.is_(None))
    )
    return rows.first()


async def suggestions(
    session: AsyncSession, incident: Incident, in_report: set[uuid.UUID] | None = None
) -> list[schemas.Suggestion]:
    """The decision engine's bodies for this incident (FR-C-13), matched with the contact system."""
    situation = await gather(session, incident, NoEnvironment())
    wanted: list[tuple[str, schemas.Kind, Bilingual]] = []
    if incident.op_level != OpLevel.NORMAL or (incident.severity or 0) >= CENTRAL_SEVERITY:
        wanted.append(("central_room", "internal", CENTRAL_REASON))
    if incident.op_level != OpLevel.NORMAL:
        wanted.append(("director_general", "internal", DG_REASON))
    wanted.extend((r.role, "external", r.reason) for r in responders.agencies(situation) if r.role)
    out: list[schemas.Suggestion] = []
    in_report = in_report or set()
    for key, kind, reason in wanted:
        body = await _match(session, key, incident.gouvernorat_code)
        agency: dict[str, Any] = domain.AGENCIES.get(key, {})
        name = body.name if body is not None else str((agency.get("name") or {}).get("ar") or key)
        phone = body.public_phone if body is not None and body.public_phone else agency.get("phone")
        out.append(
            schemas.Suggestion(
                agency=key,
                kind=kind,
                body_id=body.id if body is not None else None,
                name=name,
                public_phone=str(phone) if phone else None,
                reason=reason,
                missing=body is None,
                in_report=body is not None and body.id in in_report,
            )
        )
    return out


# ---------------------------------------------------------------- a report


def _call_out(c: Call, body_name: str, now: datetime, incident: Incident | None = None) -> schemas.CallOut:
    return schemas.CallOut(
        id=c.id,
        incident_id=c.incident_id,
        party_id=c.party_id,
        body_name=body_name,
        official_id=c.official_id,
        official_name=c.official_name,
        number=c.number,
        via=c.via,
        telephony_call_id=c.telephony_call_id,
        duration_s=c.duration_s,
        result=c.result,
        asked=c.asked,
        promised=c.promised,
        eta_min=c.eta_min,
        note=c.note,
        follow_up_at=c.follow_up_at,
        follow_up_done_at=c.follow_up_done_at,
        follow_up_due=c.follow_up_at is not None and c.follow_up_done_at is None and c.follow_up_at <= now,
        by_name=c.by_name,
        at=c.at,
        incident_title=incident.title if incident is not None else None,
        incident_category=incident.category if incident is not None else None,
    )


async def _level(session: AsyncSession, incident_id: uuid.UUID) -> IncidentLevel | None:
    return await session.get(IncidentLevel, incident_id)


def _level_out(level: IncidentLevel | None) -> schemas.LevelOut | None:
    if level is None:
        return None
    return schemas.LevelOut(level=level.level, note=level.note, set_by_name=level.set_by_name, set_at=level.set_at)


async def _parties(session: AsyncSession, incident_id: uuid.UUID, *, removed: bool = False) -> list[schemas.PartyOut]:
    query = select(Party, Body).join(Body, Body.id == Party.body_id).where(Party.incident_id == incident_id)
    if not removed:
        query = query.where(Party.removed_at.is_(None))
    rows = (await session.execute(query.order_by(Party.added_at))).all()
    if not rows:
        return []
    official_ids = [p.official_id for p, _ in rows if p.official_id]
    officials = (
        {o.id: o for o in await session.scalars(select(Official).where(Official.id.in_(official_ids)))}
        if official_ids
        else {}
    )
    calls: dict[uuid.UUID, list[Call]] = defaultdict(list)
    for c in await session.scalars(select(Call).where(Call.incident_id == incident_id).order_by(Call.at)):
        calls[c.party_id].append(c)
    now = _now()
    out = []
    for p, b in rows:
        official = officials.get(p.official_id) if p.official_id else None
        mine = calls.get(p.id, [])
        out.append(
            schemas.PartyOut(
                id=p.id,
                body_id=p.body_id,
                official_id=p.official_id,
                body_name=p.body_name,
                official_name=p.official_name,
                official_role=p.official_role,
                phones=list(official.phones) if official is not None else [],
                public_phone=b.public_phone,
                agency=b.agency,
                category=b.category,
                suggested=p.suggested,
                reason=p.reason,
                added_by_name=p.added_by_name,
                added_at=p.added_at,
                removed_at=p.removed_at,
                last_result=mine[-1].result if mine else None,
                calls=[_call_out(c, p.body_name, now) for c in mine],
            )
        )
    return out


async def incident_view(session: AsyncSession, incident: Incident) -> schemas.IncidentLiaison:
    parties = await _parties(session, incident.id)
    return schemas.IncidentLiaison(
        incident_id=incident.id,
        gouvernorat_code=incident.gouvernorat_code,
        level=_level_out(await _level(session, incident.id)),
        parties=parties,
        suggestions=await suggestions(session, incident, {p.body_id for p in parties}),
    )


async def set_level(
    session: AsyncSession, principal: Principal, incident: Incident, data: schemas.LevelIn
) -> schemas.IncidentLiaison:
    if data.level == 1 and (await _parties(session, incident.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "parties_informed")
    level = await _level(session, incident.id)
    before = level.level if level is not None else None
    if level is None:
        level = IncidentLevel(incident_id=incident.id, gouvernorat_code=incident.gouvernorat_code, level=data.level)
        session.add(level)
    level.level = data.level
    level.note = data.note
    level.set_by_name = _name(principal)
    level.set_at = _now()
    await session.flush()
    await _record(
        session,
        principal,
        "level",
        f"incident:{incident.id}",
        incident.gouvernorat_code,
        before=before,
        after=data.level,
    )
    return await incident_view(session, incident)


async def add_parties(
    session: AsyncSession, principal: Principal, incident: Incident, data: schemas.PartiesIn
) -> schemas.IncidentLiaison:
    """The bodies chosen in the picker (several at once). Adding bodies sets the level to 2."""
    level = await _level(session, incident.id)
    if level is not None and level.level == 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "level_room_only")
    name = _name(principal)
    if level is None:
        session.add(
            IncidentLevel(
                incident_id=incident.id, gouvernorat_code=incident.gouvernorat_code, level=2, set_by_name=name
            )
        )
    current = set(
        await session.scalars(select(Party.body_id).where(Party.incident_id == incident.id, Party.removed_at.is_(None)))
    )
    added = []
    for item in data.parties:
        if item.body_id in current:
            continue
        body = await _body(session, item.body_id)
        if body.status != "active":
            raise HTTPException(status.HTTP_409_CONFLICT, "body_archived")
        official = await _body_official(session, body, item.official_id)
        session.add(
            Party(
                incident_id=incident.id,
                gouvernorat_code=incident.gouvernorat_code,
                body_id=body.id,
                official_id=official.id if official else None,
                body_name=body.name,
                official_name=official.name if official else None,
                official_role=official.role if official else None,
                suggested=item.suggested,
                reason=item.reason,
                added_by_name=name,
            )
        )
        current.add(body.id)
        added.append(str(body.id))
    await session.flush()
    if added:
        await _record(
            session, principal, "parties_add", f"incident:{incident.id}", incident.gouvernorat_code, bodies=added
        )
    return await incident_view(session, incident)


async def _body_official(session: AsyncSession, body: Body, official_id: uuid.UUID | None) -> Official | None:
    """The chosen official of a body; none chosen: the first in calling order."""
    if official_id is None:
        return await session.scalar(
            select(Official)
            .where(Official.body_id == body.id, Official.status == "active")
            .order_by(Official.position, Official.name)
            .limit(1)
        )
    official = await session.get(Official, official_id)
    if official is None or official.body_id != body.id or official.status != "active":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "official_not_of_body")
    return official


async def _party(session: AsyncSession, incident: Incident, party_id: uuid.UUID) -> Party:
    party = await session.get(Party, party_id, with_for_update=True)
    if party is None or party.incident_id != incident.id:
        raise _not_found("party_not_found")
    if party.removed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "party_removed")
    return party


async def patch_party(
    session: AsyncSession, principal: Principal, incident: Incident, party_id: uuid.UUID, data: schemas.PartyPatch
) -> schemas.IncidentLiaison:
    party = await _party(session, incident, party_id)
    official = await _body_official(session, await _body(session, party.body_id), data.official_id)
    assert official is not None
    party.official_id = official.id
    party.official_name = official.name
    party.official_role = official.role
    await session.flush()
    await _record(
        session,
        principal,
        "party_official",
        f"incident:{incident.id}",
        incident.gouvernorat_code,
        party_id=str(party.id),
    )
    return await incident_view(session, incident)


async def remove_party(
    session: AsyncSession, principal: Principal, incident: Incident, party_id: uuid.UUID
) -> schemas.IncidentLiaison:
    """A body chosen by mistake. Once called, a party stays in the report's history."""
    party = await _party(session, incident, party_id)
    if await session.scalar(select(func.count()).where(Call.party_id == party.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "party_called")
    party.removed_at = _now()
    party.removed_by_name = _name(principal)
    await session.flush()
    await _record(
        session,
        principal,
        "party_remove",
        f"incident:{incident.id}",
        incident.gouvernorat_code,
        party_id=str(party.id),
    )
    return await incident_view(session, incident)


async def add_call(
    session: AsyncSession, principal: Principal, incident: Incident, party_id: uuid.UUID, data: schemas.CallIn
) -> schemas.CallOut:
    party = await _party(session, incident, party_id)
    official: Official | None = None
    if data.official_id is not None:
        official = await _body_official(session, await _body(session, party.body_id), data.official_id)
    elif party.official_id is not None:
        official = await session.get(Official, party.official_id)
    duration = data.duration_s
    phone_call_id = None
    if data.telephony_call_id is not None:
        phone = await session.get(PhoneCall, data.telephony_call_id)
        if phone is None:
            raise _not_found("telephony_call_not_found")
        phone_call_id = phone.id
        if duration is None and phone.answered_at is not None and phone.ended_at is not None:
            duration = max(0, int((phone.ended_at - phone.answered_at).total_seconds()))
    now = _now()
    call = Call(
        incident_id=incident.id,
        party_id=party.id,
        gouvernorat_code=incident.gouvernorat_code,
        official_id=official.id if official else None,
        official_name=official.name if official else party.official_name,
        number=data.number,
        via=data.via,
        telephony_call_id=phone_call_id,
        duration_s=duration,
        result=data.result,
        asked=data.asked,
        promised=data.promised,
        eta_min=data.eta_min,
        note=data.note,
        follow_up_at=now + timedelta(minutes=data.follow_up_min) if data.follow_up_min else None,
        by_subject=principal.subject,
        by_name=_name(principal),
        at=now,
    )
    session.add(call)
    # A call to another official of the body makes them the party's official.
    if official is not None and official.id != party.official_id:
        party.official_id = official.id
        party.official_name = official.name
        party.official_role = official.role
    await session.flush()
    await _record(
        session,
        principal,
        "call",
        f"incident:{incident.id}",
        incident.gouvernorat_code,
        party_id=str(party.id),
        result=data.result,
        via=data.via,
    )
    return _call_out(call, party.body_name, now)


# ---------------------------------------------------------------- follow-ups, log, history, picker


async def _calls(session: AsyncSession, query: Select[Call, str, Incident]) -> list[schemas.CallOut]:
    now = _now()
    return [_call_out(c, body_name, now, incident) for c, body_name, incident in (await session.execute(query)).all()]


def _call_query() -> Select[Call, str, Incident]:
    return (
        select(Call, Party.body_name, Incident)
        .join(Party, Party.id == Call.party_id)
        .join(Incident, Incident.id == Call.incident_id)
    )


async def follow_ups(session: AsyncSession, incident_id: uuid.UUID | None = None) -> list[schemas.CallOut]:
    query = _call_query().where(Call.follow_up_at.is_not(None), Call.follow_up_done_at.is_(None))
    if incident_id is not None:
        query = query.where(Call.incident_id == incident_id)
    return await _calls(session, query.order_by(Call.follow_up_at).limit(100))


async def follow_up_done(session: AsyncSession, principal: Principal, call_id: uuid.UUID) -> schemas.CallOut:
    call = await session.get(Call, call_id, with_for_update=True)
    if call is None:
        raise _not_found()
    if call.follow_up_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no_follow_up")
    if call.follow_up_done_at is None:
        call.follow_up_done_at = _now()
        call.follow_up_done_by_name = _name(principal)
        await session.flush()
        await _record(
            session,
            principal,
            "follow_up_done",
            f"incident:{call.incident_id}",
            call.gouvernorat_code,
            call_id=str(call.id),
        )
    return (await _calls(session, _call_query().where(Call.id == call.id)))[0]


async def call_log(
    session: AsyncSession, *, incident_id: uuid.UUID | None = None, result: str | None = None, limit: int = 200
) -> list[schemas.CallOut]:
    query = _call_query()
    if incident_id is not None:
        query = query.where(Call.incident_id == incident_id)
    if result is not None:
        query = query.where(Call.result == result)
    return await _calls(session, query.order_by(Call.at.desc()).limit(limit))


async def history(
    session: AsyncSession,
    *,
    category: str | None = None,
    exclude: uuid.UUID | None = None,
    level: int | None = None,
    limit: int = HISTORY_LIMIT,
) -> list[schemas.HistoryRow]:
    """The reports whose level was set or that informed bodies, newest first, with their parties."""
    ids = select(IncidentLevel.incident_id).union(select(Party.incident_id).where(Party.removed_at.is_(None)))
    query = select(Incident, IncidentLevel.level).outerjoin(IncidentLevel, IncidentLevel.incident_id == Incident.id)
    query = query.where(Incident.id.in_(ids))
    if category:
        query = query.where(Incident.category == category)
    if exclude is not None:
        query = query.where(Incident.id != exclude)
    if level is not None:
        query = query.where(IncidentLevel.level == level)
    rows = (await session.execute(query.order_by(Incident.opened_at.desc()).limit(limit))).all()
    if not rows:
        return []
    incident_ids = [i.id for i, _ in rows]
    parties: dict[uuid.UUID, list[schemas.HistoryParty]] = defaultdict(list)
    counts: dict[uuid.UUID, int] = {
        party_id: int(n)
        for party_id, n in (
            await session.execute(
                select(Call.party_id, func.count()).where(Call.incident_id.in_(incident_ids)).group_by(Call.party_id)
            )
        ).all()
    }
    latest = dict(
        (
            await session.execute(
                select(Call.party_id, Call.result)
                .where(Call.incident_id.in_(incident_ids))
                .distinct(Call.party_id)
                .order_by(Call.party_id, Call.at.desc())
            )
        ).all()
    )
    for p in await session.scalars(
        select(Party).where(Party.incident_id.in_(incident_ids), Party.removed_at.is_(None)).order_by(Party.added_at)
    ):
        parties[p.incident_id].append(
            schemas.HistoryParty(
                body_id=p.body_id,
                official_id=p.official_id,
                body_name=p.body_name,
                official_name=p.official_name,
                official_role=p.official_role,
                last_result=latest.get(p.id),
                calls=counts.get(p.id, 0),
            )
        )
    return [
        schemas.HistoryRow(
            incident_id=i.id,
            title=i.title,
            category=i.category,
            gouvernorat_code=i.gouvernorat_code,
            status=i.status,
            opened_at=i.opened_at,
            level=lvl,
            parties=parties.get(i.id, []),
        )
        for i, lvl in rows
    ]


async def picker(session: AsyncSession, incident: Incident) -> schemas.PickerOut:
    """What the picker opens on: the engine's suggestions, the bodies informed in earlier reports of the same kind,
    and the history of the reports to pick from directly."""
    current = {
        p
        for p in await session.scalars(
            select(Party.body_id).where(Party.incident_id == incident.id, Party.removed_at.is_(None))
        )
    }
    used_rows = (
        await session.execute(
            select(
                Party.body_id,
                func.count(),
                func.max(Party.added_at),
            )
            .join(Incident, Incident.id == Party.incident_id)
            .join(Body, Body.id == Party.body_id)
            .where(
                Incident.category == incident.category,
                Incident.id != incident.id,
                Party.removed_at.is_(None),
                Body.status == "active",
            )
            .group_by(Party.body_id)
            .order_by(func.count().desc(), func.max(Party.added_at).desc())
            .limit(USED_BEFORE_LIMIT)
        )
    ).all()
    used: list[schemas.UsedBefore] = []
    for body_id, times, last_at in used_rows:
        last_party = await session.scalar(
            select(Party)
            .join(Incident, Incident.id == Party.incident_id)
            .where(Party.body_id == body_id, Incident.category == incident.category, Party.removed_at.is_(None))
            .where(Incident.id != incident.id)
            .order_by(Party.added_at.desc())
            .limit(1)
        )
        assert last_party is not None
        used.append(
            schemas.UsedBefore(
                body_id=body_id,
                official_id=last_party.official_id,
                body_name=last_party.body_name,
                official_name=last_party.official_name,
                times=int(times),
                last_incident_id=last_party.incident_id,
                last_at=last_at,
            )
        )
    return schemas.PickerOut(
        suggestions=await suggestions(session, incident, current),
        used_before=used,
        history=await history(session, exclude=incident.id),
    )
