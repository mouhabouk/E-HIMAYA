"""Address warnings, OS8 (docs/phase-os8/design-os8.md).

A mark is shown for an incident when the incident's point falls within the circle of the mark's category, the mark is
active and not past its review date. The warnings are ordered: the ones critical with the incident's kind first, then
the nearest. A mark with hours (a nursery) is greyed outside them and never critical then.

The warnings of an incident are read across gouvernorats (an incident near a border meets the marks of the next one):
the incident is checked against the caller's scope first, then the marks are read with the system scope. A personal
mark gives its owner's need and never a name; the name and phone are shown on request, with a reason, and every such
request is kept and shown to the owner.
"""

import asyncio
import calendar
import uuid
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from fastapi import HTTPException, status
from geoalchemy2 import Geography, Geometry
from sqlalchemy import Select, cast, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import events
from app.core.db import as_system
from app.core.security import Principal
from app.modules.address_warnings import schemas
from app.modules.address_warnings.models import Ack, Category, Marker, ReminderDay, Reveal
from app.modules.audit import service as audit
from app.modules.identity.models import Profile
from app.modules.notify import outbox
from app.modules.notify.models import Device, Outbox
from app.modules.ops.models import Incident
from app.modules.orgs.models import Hazmat, Organization
from app.modules.reports.service import locate_gouvernorat

TUNIS = ZoneInfo("Africa/Tunis")
log = structlog.get_logger()
_LAT = func.ST_Y(cast(Marker.location, Geometry))
_LON = func.ST_X(cast(Marker.location, Geometry))
#: Words of a hazardous material that make an institution's mark a gas store rather than hazardous materials.
GAS_WORDS = ("غاز", "gaz", "gas", "propane", "butane", "بروبان", "بوتان")
GAS_UN = {"1011", "1075", "1965", "1978", "1049", "1971"}
#: OS8-3, the morning review reminder (Yamen 2026-11-13): sent at 08:00 to the room of the gouvernorat; a mark shows
#: «soon» 30 days ahead, is raised to the room's manager 7 days past its date and to the central room 30 days past.
REMINDER_HOUR = 8
AHEAD_DAYS = 30
MANAGER_DAYS = 7
CENTRAL_DAYS = 30
#: OS8-2: the SMS to the owner of a personal mark when their account has no phone that receives pushes. Fixed text:
#: no name, no address, no reason (the reason is read in the app, behind the account's login).
REVEAL_SMS = (
    "ء-حماية: اطّلعت فرق الحماية المدنية على اسمك ورقمك بسبب بلاغ قريب من عنوانك. "
    "التفاصيل في التطبيق: الملف الطبي ثم «من اطّلع على بياناتي»."
)
REVEAL_PUSH_TITLE = outbox.localized(
    "اطّلعت فرق الحماية على اسمك", "Les secours ont consulté votre nom", "Rescue teams viewed your name"
)
REVEAL_PUSH_BODY = outbox.localized(
    "بسبب بلاغ قريب من عنوانك. انقر لمعرفة السبب.",
    "Suite à un signalement près de chez vous. Touchez pour voir le motif.",
    "Because of an incident near your address. Tap to see why.",
)


def _now() -> datetime:
    return datetime.now(UTC)


def today() -> date:
    return _now().astimezone(TUNIS).date()


def minutes_now(at: datetime | None = None) -> int:
    local = (at or _now()).astimezone(TUNIS)
    return local.hour * 60 + local.minute


def add_months(day: date, months: int) -> date:
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def in_hours(start: int | None, end: int | None, minute: int) -> bool:
    """Inside the hours of a mark (both empty: always). Hours may cross midnight (22:00 to 06:00)."""
    if start is None or end is None:
        return True
    if start <= end:
        return start <= minute <= end
    return minute >= start or minute <= end


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "not_found")


def _point(lat: float, lon: float) -> Any:
    return func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)


def _name(principal: Principal) -> str | None:
    return audit.name_of(principal)


# ---------------------------------------------------------------- categories


async def categories(session: AsyncSession) -> dict[str, Category]:
    rows = await session.scalars(select(Category).order_by(Category.position))
    return {c.key: c for c in rows}


def category_out(c: Category) -> schemas.CategoryOut:
    return schemas.CategoryOut(
        key=c.key,
        name=c.name,
        icon=c.icon,
        colour=c.colour,
        personal=c.personal,
        radius_m=c.radius_m,
        review_months=c.review_months,
        team=c.team,
        critical_with=list(c.critical_with),
        examples=list(c.examples),
        updated_by_name=c.updated_by_name,
    )


async def save_category(
    session: AsyncSession, principal: Principal, key: str, body: schemas.CategoryIn
) -> schemas.CategoryOut:
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "national_only")
    category = await session.get(Category, key, with_for_update=True)
    if category is None:
        raise _not_found()
    before = category_out(category).model_dump()
    category.radius_m = body.radius_m
    category.review_months = body.review_months
    category.team = body.team
    category.critical_with = sorted(set(body.critical_with))
    category.updated_at = _now()
    category.updated_by_name = _name(principal)
    out = category_out(category)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="address_warnings.category",
        target=f"aw_category:{key}",
        details={"before": before, "after": out.model_dump()},
    )
    return out


async def _category(session: AsyncSession, key: str, *, personal: bool = False) -> Category:
    category = await session.get(Category, key)
    if category is None or category.personal != personal:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "personal_category" if category else "category")
    return category


# ---------------------------------------------------------------- marks


def _hours(m: Marker) -> schemas.Hours | None:
    return None if m.active_from is None or m.active_to is None else schemas.Hours(start=m.active_from, end=m.active_to)


def marker_out(m: Marker, lat: float, lon: float) -> schemas.MarkerOut:
    return schemas.MarkerOut(
        id=m.id,
        category=m.category,
        gouvernorat_code=m.gouvernorat_code,
        location=schemas.Point(lat=lat, lon=lon),
        address=m.address,
        description=m.description,
        source=m.source,
        source_ref=m.source_ref,
        org_id=m.org_id,
        incident_id=m.incident_id,
        team_visible=m.team_visible,
        hours=_hours(m),
        review_on=m.review_on,
        review_due=m.status == "active" and m.review_on < today(),
        status=m.status,
        created_at=m.created_at,
        created_by_name=m.created_by_name,
        decided_at=m.decided_at,
        decided_by_name=m.decided_by_name,
        decision_reason=m.decision_reason,
        confirmed_at=m.confirmed_at,
        check_requested_at=m.check_requested_at,
        check_requested_by_name=m.check_requested_by_name,
    )


def _scoped(query: Select[Any], principal: Principal) -> Select[Any]:
    if principal.gouvernorat_code is not None:
        query = query.where(Marker.gouvernorat_code == principal.gouvernorat_code)
    return query


async def list_markers(
    session: AsyncSession,
    principal: Principal,
    *,
    status_: str | None = None,
    category: str | None = None,
    source: str | None = None,
) -> schemas.MarkerPage:
    """The register of the room's gouvernorat (the central room: every one). Personal marks are never listed: there
    is no browsing nor searching people (only their count)."""
    personal = select(Category.key).where(Category.personal)
    query = _scoped(select(Marker, _LAT, _LON), principal).where(Marker.category.not_in(personal))
    if status_ == "review_due":
        query = query.where(Marker.status == "active", Marker.review_on < today())
    elif status_:
        query = query.where(Marker.status == status_)
    else:
        query = query.where(Marker.status.in_(("pending", "active")))
    if category:
        query = query.where(Marker.category == category)
    if source:
        query = query.where(Marker.source == source)
    rows = (await session.execute(query.order_by(Marker.status.desc(), Marker.created_at.desc()).limit(500))).all()
    base = _scoped(select(func.count()).select_from(Marker), principal)
    live = base.where(Marker.status == "active", Marker.review_on >= today())
    counts = schemas.Counts(
        active=await session.scalar(live.where(Marker.category.not_in(personal))) or 0,
        pending=await session.scalar(base.where(Marker.status == "pending")) or 0,
        review_due=await session.scalar(
            base.where(Marker.status == "active", Marker.review_on < today(), Marker.category.not_in(personal))
        )
        or 0,
        personal=await session.scalar(live.where(Marker.category.in_(personal))) or 0,
    )
    return schemas.MarkerPage(items=[marker_out(m, lat, lon) for m, lat, lon in rows], counts=counts)


async def _located(session: AsyncSession, principal: Principal, location: schemas.LocationIn) -> int | None:
    code = await locate_gouvernorat(session, location.lat, location.lon)
    if principal.gouvernorat_code is not None and code != principal.gouvernorat_code:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "outside_gouvernorat")
    return code


async def load(session: AsyncSession, principal: Principal, marker_id: uuid.UUID) -> tuple[Marker, float, float]:
    row = (
        await session.execute(
            _scoped(select(Marker, _LAT, _LON), principal)
            .where(Marker.id == marker_id, Marker.owner_id.is_(None))
            .with_for_update(of=Marker)
        )
    ).one_or_none()
    if row is None:
        raise _not_found()
    return row[0], row[1], row[2]


async def _record(session: AsyncSession, principal: Principal, action: str, m: Marker, **details: Any) -> None:
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action=f"address_warnings.{action}",
        target=f"aw_marker:{m.id}",
        details={"category": m.category, **details},
        gouvernorats=[m.gouvernorat_code] if m.gouvernorat_code else None,
    )


async def create_marker(session: AsyncSession, principal: Principal, body: schemas.MarkerIn) -> schemas.MarkerOut:
    category = await _category(session, body.category)
    code = await _located(session, principal, body.location)
    m = Marker(
        category=category.key,
        gouvernorat_code=code,
        location=_point(body.location.lat, body.location.lon),
        address=body.address,
        description=body.description,
        source=body.source,
        source_ref=body.source_ref,
        team_visible=body.team_visible,
        active_from=body.hours.start if body.hours else None,
        active_to=body.hours.end if body.hours else None,
        review_on=body.review_on or add_months(today(), category.review_months),
        status="active",
        created_by=audit.actor_of(principal),
        created_by_name=_name(principal),
        decided_at=_now(),
        decided_by_name=_name(principal),
    )
    session.add(m)
    await session.flush()
    await _record(session, principal, "create", m, source=m.source)
    return marker_out(m, body.location.lat, body.location.lon)


async def patch_marker(
    session: AsyncSession, principal: Principal, marker_id: uuid.UUID, body: schemas.MarkerPatch
) -> schemas.MarkerOut:
    m, lat, lon = await load(session, principal, marker_id)
    if m.status not in ("pending", "active"):
        raise HTTPException(status.HTTP_409_CONFLICT, "marker_closed")
    if body.address is not None:
        m.address = body.address
    if body.description is not None:
        m.description = body.description
    if body.team_visible is not None:
        m.team_visible = body.team_visible
    if body.clear_hours:
        m.active_from = m.active_to = None
    elif body.hours is not None:
        m.active_from, m.active_to = body.hours.start, body.hours.end
    if body.location is not None:
        m.gouvernorat_code = await _located(session, principal, body.location)
        m.location = _point(body.location.lat, body.location.lon)
        lat, lon = body.location.lat, body.location.lon
    m.version += 1
    await _record(session, principal, "update", m)
    return marker_out(m, lat, lon)


async def decide(
    session: AsyncSession, principal: Principal, marker_id: uuid.UUID, action: str, reason: str | None
) -> schemas.MarkerOut:
    """approve or reject a pending mark; archive an active one; confirm one whose review date came."""
    m, lat, lon = await load(session, principal, marker_id)
    category = await session.get(Category, m.category)
    assert category is not None
    allowed = {
        "approve": ("pending",),
        "reject": ("pending",),
        "archive": ("pending", "active"),
        "confirm": ("active",),
    }
    if m.status not in allowed[action]:
        raise HTTPException(status.HTTP_409_CONFLICT, "marker_status")
    if action in ("reject", "archive") and not reason:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reason_required")
    now = _now()
    if action == "approve":
        m.status = "active"
        m.review_on = add_months(today(), category.review_months)
    elif action == "reject":
        m.status = "rejected"
    elif action == "archive":
        m.status = "archived"
    else:
        m.review_on = add_months(today(), category.review_months)
        m.confirmed_at = now
    if action != "confirm":
        m.decided_at, m.decided_by_name, m.decision_reason = now, _name(principal), reason
    if action in ("confirm", "archive"):
        # OS8-3: the review is done; a field check asked from the reminder is no longer awaited.
        m.check_requested_at = m.check_requested_by_name = None
    m.version += 1
    await _record(session, principal, action, m, reason=reason)
    return marker_out(m, lat, lon)


def _org_category(materials: list[Hazmat]) -> str:
    for h in materials:
        words = f"{h.name} {h.hazard_class or ''}".lower()
        if (h.un_number or "").strip() in GAS_UN or any(w in words for w in GAS_WORDS):
            return "gas"
    return "chem"


async def import_orgs(session: AsyncSession, principal: Principal) -> schemas.ImportOut:
    """Pending marks from the institutions register: every active institution of the scope that declared hazardous
    materials and has no mark of that category yet. The room approves each one."""
    query = select(
        Organization, func.ST_Y(cast(Organization.location, Geometry)), func.ST_X(cast(Organization.location, Geometry))
    ).where(Organization.status == "active")
    if principal.gouvernorat_code is not None:
        query = query.where(Organization.gouvernorat_code == principal.gouvernorat_code)
    created = 0
    for org, lat, lon in (await session.execute(query.order_by(Organization.name).limit(2000))).all():
        materials = list(await session.scalars(select(Hazmat).where(Hazmat.org_id == org.id)))
        if not materials:
            continue
        key = _org_category(materials)
        taken = await session.scalar(
            select(func.count())
            .select_from(Marker)
            .where(Marker.org_id == org.id, Marker.category == key, Marker.status.in_(("pending", "active")))
        )
        if taken:
            continue
        listed = "، ".join(
            f"{h.name} {h.quantity.normalize():f} {h.unit}" + (f" ({h.storage_location})" if h.storage_location else "")
            for h in materials[:4]
        )
        m = Marker(
            category=key,
            gouvernorat_code=org.gouvernorat_code,
            location=_point(lat, lon),
            address=(org.address or org.name)[:200],
            description=f"{org.name}: {listed}"[:500],
            source="org",
            source_ref=f"{org.name} · {org.kind}"[:200],
            org_id=org.id,
            team_visible=True,
            review_on=add_months(today(), 12),
            status="pending",
            created_by=audit.actor_of(principal),
            created_by_name="استيراد من سجل المؤسسات",
        )
        session.add(m)
        await session.flush()
        await _record(session, principal, "import", m, org_id=str(org.id))
        created += 1
    return schemas.ImportOut(created=created)


# ---------------------------------------------------------------- the warnings of an incident


async def incident_point(session: AsyncSession, incident: Incident) -> tuple[float, float] | None:
    if incident.centroid is None:
        return None
    row = (
        await session.execute(
            select(func.ST_Y(cast(Incident.centroid, Geometry)), func.ST_X(cast(Incident.centroid, Geometry))).where(
                Incident.id == incident.id
            )
        )
    ).one_or_none()
    return None if row is None or row[0] is None else (float(row[0]), float(row[1]))


async def warnings(
    session: AsyncSession, incident: Incident, *, team: bool = False, at: datetime | None = None
) -> schemas.IncidentWarnings:
    """The warnings of an incident, after the caller's check of the incident (the marks are read across borders)."""
    point = await incident_point(session, incident)
    kind = incident.category
    if point is None:
        return schemas.IncidentWarnings(incident_id=incident.id, incident_kind=kind, location=None, items=[], unread=0)
    lat, lon = point
    target = cast(_point(lat, lon), Geography)
    distance = func.ST_Distance(Marker.location, target)
    minute = minutes_now(at)
    async with as_system(session):
        query = (
            select(Marker, Category, _LAT, _LON, distance)
            .join(Category, Category.key == Marker.category)
            .where(
                Marker.status == "active",
                Marker.review_on >= today(),
                func.ST_DWithin(Marker.location, target, Category.radius_m),
            )
        )
        if team:
            query = query.where(Marker.team_visible, Category.team)
        rows = (await session.execute(query)).all()
        acks = {
            (a.marker_id, a.by_kind): a
            for a in await session.scalars(select(Ack).where(Ack.incident_id == incident.id))
        }
        revealed = set(await session.scalars(select(Reveal.marker_id).where(Reveal.incident_id == incident.id)))
    items: list[schemas.Warning] = []
    for m, c, mlat, mlon, dist in rows:
        off = not in_hours(m.active_from, m.active_to, minute)
        room, crew = acks.get((m.id, "room")), acks.get((m.id, "team"))
        items.append(
            schemas.Warning(
                marker_id=m.id,
                category=c.key,
                category_name=c.name,
                personal=c.personal,
                location=schemas.Point(lat=mlat, lon=mlon),
                address=m.address,
                description=m.description,
                source=m.source,
                source_ref=None if c.personal else m.source_ref,
                team_visible=m.team_visible and c.team,
                distance_m=round(dist),
                critical=not off and kind in c.critical_with,
                off_hours=off,
                hours=_hours(m),
                review_on=m.review_on,
                room_ack_at=room.at if room else None,
                room_ack_by=room.by_name if room else None,
                team_ack_at=crew.at if crew else None,
                team_ack_by=crew.by_name if crew else None,
                revealed=m.id in revealed and not team,
            )
        )
    items.sort(key=lambda w: (w.off_hours, not w.critical, w.distance_m))
    ack_kind = "team_ack_at" if team else "room_ack_at"
    unread = sum(1 for w in items if getattr(w, ack_kind) is None)
    return schemas.IncidentWarnings(
        incident_id=incident.id,
        incident_kind=kind,
        location=schemas.Point(lat=lat, lon=lon),
        items=items,
        unread=unread,
    )


async def acknowledge(
    session: AsyncSession,
    principal: Principal,
    incident: Incident,
    by_kind: str,
    marker_ids: list[uuid.UUID],
) -> int:
    shown = await warnings(session, incident, team=by_kind == "team")
    ids = {w.marker_id for w in shown.items}
    wanted = set(marker_ids) or ids
    if not wanted <= ids:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "not_a_warning_of_the_incident")
    done = {w.marker_id for w in shown.items if (w.team_ack_at if by_kind == "team" else w.room_ack_at)}
    new = sorted(wanted - done)
    for marker_id in new:
        session.add(
            Ack(
                marker_id=marker_id,
                incident_id=incident.id,
                gouvernorat_code=incident.gouvernorat_code,
                by_kind=by_kind,
                by_subject=audit.actor_of(principal),
                by_name=_name(principal),
            )
        )
    if new:
        await session.flush()
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action=f"address_warnings.ack_{by_kind}",
            target=f"incident:{incident.id}",
            details={"markers": [str(i) for i in new]},
            gouvernorats=[incident.gouvernorat_code] if incident.gouvernorat_code else None,
        )
    return len(new)


async def reveal(
    session: AsyncSession, principal: Principal, incident: Incident, marker_id: uuid.UUID, reason: str
) -> schemas.RevealOut:
    """The name and phone of the owner of a personal mark shown for this incident, with the reason."""
    shown = await warnings(session, incident)
    if not any(w.marker_id == marker_id and w.personal for w in shown.items):
        raise _not_found()
    async with as_system(session):
        m = await session.get(Marker, marker_id)
        assert m is not None and m.owner_id is not None
        profile = await session.get(Profile, m.owner_id)
        row = Reveal(
            marker_id=m.id,
            owner_id=m.owner_id,
            incident_id=incident.id,
            gouvernorat_code=incident.gouvernorat_code,
            by_subject=audit.actor_of(principal),
            by_name=_name(principal),
            reason=reason,
        )
        session.add(row)
        await session.flush()
        name = " ".join(p for p in (profile.first_name, profile.last_name) if p) if profile else ""
        phone = profile.phone if profile else None
        row.notified_via = await _tell_owner(session, m.owner_id, row.id, phone)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="address_warnings.reveal",
        target=f"aw_marker:{marker_id}",
        reason=reason,
        details={"incident_id": str(incident.id)},
        gouvernorats=[incident.gouvernorat_code] if incident.gouvernorat_code else None,
    )
    return schemas.RevealOut(name=name or None, phone=phone)


async def _tell_owner(session: AsyncSession, owner_id: uuid.UUID, reveal_id: int, phone: str | None) -> str | None:
    """OS8-2: the owner learns at once that a room read their name. A content-free push to their phones (the app
    fetches when and why behind the login); an SMS with a fixed text when the account has no phone for pushes."""
    has_device = await session.scalar(select(func.count()).select_from(Device).where(Device.user_id == owner_id))
    if has_device:
        outbox.push(
            session,
            owner_id,
            "address_warning_viewed",
            {"id": str(reveal_id)},
            alert=True,
            title=REVEAL_PUSH_TITLE,
            body=REVEAL_PUSH_BODY,
        )
        return "push"
    if phone:
        session.add(Outbox(channel="sms", address=phone, payload={"text": REVEAL_SMS}))
        return "sms"
    return None


async def reveals(session: AsyncSession, principal: Principal) -> list[schemas.RevealRow]:
    query = select(Reveal, Marker.category, Marker.address).join(Marker, Marker.id == Reveal.marker_id)
    if principal.gouvernorat_code is not None:
        query = query.where(Reveal.gouvernorat_code == principal.gouvernorat_code)
    rows = (await session.execute(query.order_by(Reveal.at.desc()).limit(200))).all()
    return [
        schemas.RevealRow(
            id=r.id,
            at=r.at,
            by_name=r.by_name,
            category=cat,
            address=address,
            incident_id=r.incident_id,
            reason=r.reason,
            notified_via=r.notified_via,
            disputed_at=r.disputed_at,
            dispute_note=r.dispute_note,
        )
        for r, cat, address in rows
    ]


# ---------------------------------------------------------------- the team's proposal


async def propose(
    session: AsyncSession, principal: Principal, incident: Incident, body: schemas.ProposalIn
) -> schemas.MarkerOut:
    """A mark proposed from the scene: pending until the room approves it."""
    category = await _category(session, body.category)
    if body.location is not None:
        lat, lon = body.location.lat, body.location.lon
    else:
        point = await incident_point(session, incident)
        if point is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "location_required")
        lat, lon = point
    code = await locate_gouvernorat(session, lat, lon)
    m = Marker(
        category=category.key,
        gouvernorat_code=code or incident.gouvernorat_code,
        location=_point(lat, lon),
        address=body.address or (incident.title or "عنوان التدخل")[:200],
        description=body.description,
        source="team",
        source_ref=f"اقتراح من الميدان · {_name(principal) or ''}".strip(" ·")[:200],
        incident_id=incident.id,
        team_visible=True,
        review_on=add_months(today(), category.review_months),
        status="pending",
        created_by=audit.actor_of(principal),
        created_by_name=_name(principal),
    )
    async with as_system(session):
        session.add(m)
        await session.flush()
    await _record(session, principal, "propose", m, incident_id=str(incident.id))
    return marker_out(m, lat, lon)


# ---------------------------------------------------------------- the citizen's own needs


async def my_warnings(session: AsyncSession, user_id: uuid.UUID) -> schemas.MyWarningsOut:
    cats = await categories(session)
    rows = (
        await session.execute(
            select(Marker, _LAT, _LON)
            .where(Marker.owner_id == user_id, Marker.status == "active")
            .order_by(Marker.created_at)
        )
    ).all()
    reveal_rows = (
        await session.execute(
            select(Reveal, Marker.category)
            .join(Marker, Marker.id == Reveal.marker_id)
            .where(Reveal.owner_id == user_id)
            .order_by(Reveal.at.desc())
            .limit(50)
        )
    ).all()
    first = rows[0] if rows else None
    return schemas.MyWarningsOut(
        location=schemas.Point(lat=first[1], lon=first[2]) if first else None,
        address=first[0].address if first else None,
        needs=[
            schemas.MyNeed(id=m.id, category=m.category, description=m.description, review_on=m.review_on)
            for m, _, _ in rows
        ],
        # The owner learns that a room read their name, when and why, never who.
        reveals=[
            schemas.MyReveal(id=r.id, at=r.at, category=cat, reason=r.reason, disputed_at=r.disputed_at)
            for r, cat in reveal_rows
        ],
        categories=[category_out(c) for c in cats.values() if c.personal],
    )


async def save_my_warnings(
    session: AsyncSession, user_id: uuid.UUID, actor: str, body: schemas.MyWarningsIn
) -> schemas.MyWarningsOut:
    """The citizen's consent, from their medical file: one mark per need at their address. A need left out is
    withdrawn at once; saving again renews the consent for a year."""
    cats = await categories(session)
    code = await locate_gouvernorat(session, body.location.lat, body.location.lon)
    current = {
        m.category: m
        for m in await session.scalars(
            select(Marker).where(Marker.owner_id == user_id, Marker.status == "active").with_for_update()
        )
    }
    wanted = {n.category: n for n in body.needs}
    now = _now()
    for key, m in current.items():
        if key not in wanted:
            m.status, m.decided_at, m.decision_reason = "withdrawn", now, "سحب صاحبها موافقته"
            m.version += 1
    for key, need in wanted.items():
        review = add_months(today(), cats[key].review_months)
        held = current.get(key)
        if held is None:
            session.add(
                Marker(
                    category=key,
                    gouvernorat_code=code,
                    location=_point(body.location.lat, body.location.lon),
                    address=body.address,
                    description=need.description,
                    source="citizen",
                    owner_id=user_id,
                    team_visible=True,
                    review_on=review,
                    status="active",
                    created_by=actor,
                    decided_at=now,
                )
            )
        else:
            held.gouvernorat_code = code
            held.location = _point(body.location.lat, body.location.lon)
            held.address, held.description, held.review_on, held.confirmed_at = (
                body.address,
                need.description,
                review,
                now,
            )
            held.version += 1
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action="address_warnings.consent",
        target=f"account:{user_id}",
        details={"needs": sorted(wanted), "withdrawn": sorted(set(current) - set(wanted))},
        gouvernorats=[code] if code else None,
    )
    return await my_warnings(session, user_id)


async def dispute(session: AsyncSession, user_id: uuid.UUID, actor: str, reveal_id: int, note: str | None) -> None:
    """OS8-2: «لا علم لي بأي بلاغ عندي». The owner objects to a reading of their name; kept on the reading, audited
    and followed by the central room (the reveals log and the reminder count)."""
    async with as_system(session):
        row = await session.get(Reveal, reveal_id, with_for_update=True)
        if row is None or row.owner_id != user_id:
            raise _not_found()
        if row.disputed_at is not None:
            return
        row.disputed_at, row.dispute_note = _now(), note or None
        code = row.gouvernorat_code
        incident_id = row.incident_id
        await session.flush()
    await audit.record(
        session,
        actor=actor,
        action="address_warnings.reveal_disputed",
        target=f"aw_reveal:{reveal_id}",
        details={"incident_id": str(incident_id) if incident_id else None},
        gouvernorats=[code] if code else None,
    )


# ---------------------------------------------------------------- the review reminder (OS8-3)


def reminder_level(days: int) -> schemas.ReminderLevel:
    """days: past the review date (1 or more: review_on < today, like the register) or left before it (0 or less)."""
    if days <= 0:
        return "soon"
    if days >= CENTRAL_DAYS:
        return "central"
    if days >= MANAGER_DAYS:
        return "manager"
    return "room"


async def reminders(session: AsyncSession, principal: Principal) -> schemas.Reminders:
    """The marks of the scope past their review date or within the notice, oldest first; personal marks are left out
    (their owner renews their consent in the app)."""
    personal = select(Category.key).where(Category.personal)
    day = today()
    horizon = date.fromordinal(day.toordinal() + AHEAD_DAYS)
    query = _scoped(select(Marker, _LAT, _LON), principal).where(
        Marker.status == "active", Marker.review_on <= horizon, Marker.category.not_in(personal)
    )
    rows = (await session.execute(query.order_by(Marker.review_on).limit(500))).all()
    late: list[schemas.ReminderItem] = []
    soon: list[schemas.ReminderItem] = []
    for m, lat, lon in rows:
        days = (day - m.review_on).days
        item = schemas.ReminderItem(marker=marker_out(m, lat, lon), days=days, level=reminder_level(days))
        (late if days > 0 else soon).append(item)
    disputes = select(func.count()).select_from(Reveal).where(Reveal.disputed_at.is_not(None))
    if principal.gouvernorat_code is not None:
        disputes = disputes.where(Reveal.gouvernorat_code == principal.gouvernorat_code)
    return schemas.Reminders(
        late=late,
        soon=soon,
        disputes=await session.scalar(disputes) or 0,
        settings=schemas.ReminderSettings(
            hour=REMINDER_HOUR, ahead_days=AHEAD_DAYS, manager_days=MANAGER_DAYS, central_days=CENTRAL_DAYS
        ),
    )


async def request_check(session: AsyncSession, principal: Principal, marker_id: uuid.UUID) -> schemas.MarkerOut:
    """A field check of a mark asked from the reminder: kept on the mark until a confirm or an archive."""
    m, lat, lon = await load(session, principal, marker_id)
    if m.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "marker_status")
    m.check_requested_at, m.check_requested_by_name = _now(), _name(principal)
    m.version += 1
    await _record(session, principal, "check_requested", m)
    return marker_out(m, lat, lon)


async def send_reminders(session: AsyncSession, at: datetime | None = None) -> int:
    """Once a day from 08:00 (Tunis), one live reminder per gouvernorat whose room has marks past or near their
    review date. Kept in ``aw.reminder_day`` so that it goes once across processes. Returns the reminders sent."""
    local = (at or _now()).astimezone(TUNIS)
    if local.hour < REMINDER_HOUR:
        return 0
    day = local.date()
    personal = select(Category.key).where(Category.personal)
    horizon = date.fromordinal(day.toordinal() + AHEAD_DAYS)
    late_days = day - Marker.review_on
    rows = (
        await session.execute(
            select(
                Marker.gouvernorat_code,
                func.count().filter(Marker.review_on < day),
                func.count().filter(Marker.review_on >= day),
                func.count().filter(Marker.review_on < day, late_days >= MANAGER_DAYS),
                func.count().filter(Marker.review_on < day, late_days >= CENTRAL_DAYS),
            )
            .where(
                Marker.status == "active",
                Marker.review_on <= horizon,
                Marker.category.not_in(personal),
                Marker.gouvernorat_code.is_not(None),
            )
            .group_by(Marker.gouvernorat_code)
        )
    ).all()
    sent = 0
    for code, late, soon, manager, central in rows:
        done = await session.scalar(
            pg_insert(ReminderDay)
            .values(gouvernorat_code=code, day=day, late=late, soon=soon)
            .on_conflict_do_nothing()
            .returning(ReminderDay.day)
        )
        if done is None:
            continue
        await events.emit(
            session,
            "address_warnings.review_reminder",
            {
                "day": day.isoformat(),
                "gouvernorat_code": code,
                "gouvernorat_codes": [code],
                "late": late,
                "soon": soon,
                "manager": manager,
                "central": central,
            },
        )
        sent += 1
    return sent


async def reminders_forever(sessionmaker: async_sessionmaker[AsyncSession], interval_s: float = 600) -> None:
    """Worker loop: the morning review reminder (checked every ten minutes, sent once a day per gouvernorat)."""
    while True:
        try:
            async with sessionmaker() as session, session.begin():
                sent = await send_reminders(session)
            if sent:
                log.info("address_warnings.reminders_sent", count=sent)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("address_warnings.reminders_failed")
        await asyncio.sleep(interval_s)
