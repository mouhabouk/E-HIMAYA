"""Volunteer network (FR-A-020…023, FR-C-04).

A registered citizen declares skills and a period; staff review the application (human decision, e-mail
to the volunteer). An approved volunteer within the period switches «جاهز»: the live position is shared
with the dashboard through ``presence`` (Valkey) until readiness ends, and nowhere else.
"""

import base64
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, any_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import emit
from app.core.security import Principal
from app.modules.audit import service as audit
from app.modules.identity.models import Profile
from app.modules.identity.service import Reporter
from app.modules.notify import outbox, templates
from app.modules.ops.models import Callout, CalloutTarget
from app.modules.volunteers import schemas
from app.modules.volunteers.models import Volunteer, VolunteerReview
from app.modules.volunteers.presence import Fix, get_presence

MAX_PERIOD_DAYS = 730
LOCATION_MIN_INTERVAL_S = 20
TUNISIA_BBOX = (7.4, 30.0, 11.7, 37.6)

_DECISIONS: dict[str, tuple[str, str]] = {
    # decision: (required current status, new status)
    "approve": ("pending", "approved"),
    "reject": ("pending", "rejected"),
    "suspend": ("approved", "suspended"),
    "reinstate": ("suspended", "approved"),
}


def now() -> datetime:
    return datetime.now(UTC)


def require_registered(reporter: Reporter) -> Reporter:
    if reporter.principal is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "registration_required")
    return reporter


def is_ready(volunteer: Volunteer, at: datetime | None = None) -> bool:
    return (
        volunteer.status == "approved" and volunteer.ready_until is not None and volunteer.ready_until > (at or now())
    )


def in_period(volunteer: Volunteer, on: date) -> bool:
    return volunteer.period_from <= on and (volunteer.period_to is None or on <= volunteer.period_to)


def volunteer_out(volunteer: Volunteer) -> schemas.VolunteerOut:
    ready = is_ready(volunteer)
    return schemas.VolunteerOut(
        status=volunteer.status,
        skills=list(volunteer.skills),
        other_skill=volunteer.other_skill,
        availability=volunteer.availability,
        period_from=volunteer.period_from,
        period_to=volunteer.period_to,
        notes=volunteer.notes,
        review_reason=volunteer.review_reason,
        submitted_at=volunteer.submitted_at,
        reviewed_at=volunteer.reviewed_at,
        ready=ready,
        ready_until=volunteer.ready_until if ready else None,
        version=volunteer.version,
    )


def full_name(profile: Profile | None) -> str | None:
    if profile is None:
        return None
    return " ".join(p for p in (profile.first_name, profile.last_name) if p) or None


def staff_item(volunteer: Volunteer, profile: Profile | None) -> schemas.StaffVolunteer:
    ready = is_ready(volunteer)
    return schemas.StaffVolunteer(
        id=volunteer.user_id,
        full_name=full_name(profile),
        phone=profile.phone if profile else None,
        gouvernorat_code=volunteer.gouvernorat_code,
        skills=list(volunteer.skills),
        availability=volunteer.availability,
        period_from=volunteer.period_from,
        period_to=volunteer.period_to,
        status=volunteer.status,
        ready=ready,
        ready_until=volunteer.ready_until if ready else None,
        submitted_at=volunteer.submitted_at,
    )


async def announce(session: AsyncSession, volunteer: Volunteer) -> None:
    profile = await session.get(Profile, volunteer.user_id)
    await emit(session, "volunteer.updated", {"volunteer": staff_item(volunteer, profile).model_dump(mode="json")})


async def _end_readiness(session: AsyncSession, volunteer: Volunteer) -> None:
    volunteer.ready_until = None
    await get_presence().clear(volunteer.user_id)


# ---------------------------------------------------------------- the volunteer (app)


async def get_mine(session: AsyncSession, reporter: Reporter, lock: bool = False) -> Volunteer:
    volunteer = await session.get(Volunteer, require_registered(reporter).user_id, with_for_update=lock)
    if volunteer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_volunteer")
    return volunteer


async def declare(session: AsyncSession, reporter: Reporter, body: schemas.VolunteerIn) -> Volunteer:
    require_registered(reporter)
    profile = await session.get(Profile, reporter.user_id)
    if profile is None or not profile.phone or profile.gouvernorat_code is None:
        # The dashboard calls volunteers by phone and ranks them by gouvernorat.
        raise HTTPException(status.HTTP_409_CONFLICT, "profile_incomplete")
    today = now().date()
    if body.period_to is not None and (
        body.period_to < body.period_from or body.period_to > today + timedelta(days=MAX_PERIOD_DAYS)
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_period")
    if body.period_from > today + timedelta(days=365):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_period")
    skills: list[str] = sorted(set(body.skills))
    volunteer = await session.get(Volunteer, reporter.user_id, with_for_update=True)
    if volunteer is None:
        volunteer = Volunteer(user_id=reporter.user_id, status="pending", version=1)
        session.add(volunteer)
    else:
        if body.version is not None and body.version != volunteer.version:
            raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
        if volunteer.status in ("rejected", "withdrawn"):
            volunteer.status, volunteer.submitted_at, volunteer.review_reason = "pending", now(), None
        elif volunteer.status == "approved" and skills != sorted(volunteer.skills):
            # New skills are checked again before the volunteer is called out for them.
            volunteer.status, volunteer.submitted_at = "pending", now()
            await _end_readiness(session, volunteer)
        volunteer.version += 1
    volunteer.skills = skills
    volunteer.other_skill = body.other_skill if "other" in skills else None
    volunteer.availability = body.availability
    volunteer.period_from, volunteer.period_to = body.period_from, body.period_to
    volunteer.notes = body.notes
    volunteer.gouvernorat_code = profile.gouvernorat_code
    volunteer.updated_at = now()
    if not in_period(volunteer, today) and volunteer.ready_until is not None:
        await _end_readiness(session, volunteer)
    await session.flush()
    await session.refresh(volunteer)
    await announce(session, volunteer)
    return volunteer


async def withdraw(session: AsyncSession, reporter: Reporter) -> Volunteer:
    volunteer = await get_mine(session, reporter, lock=True)
    volunteer.status, volunteer.updated_at = "withdrawn", now()
    volunteer.version += 1
    await _end_readiness(session, volunteer)
    await session.flush()
    await announce(session, volunteer)
    return volunteer


async def set_readiness(session: AsyncSession, reporter: Reporter, body: schemas.ReadinessIn) -> Volunteer:
    volunteer = await get_mine(session, reporter, lock=True)
    if not body.ready:
        await _end_readiness(session, volunteer)
    else:
        if volunteer.status != "approved":
            raise HTTPException(status.HTTP_409_CONFLICT, "volunteer_not_approved")
        if not in_period(volunteer, now().date()):
            raise HTTPException(status.HTTP_409_CONFLICT, "outside_period")
        if body.lat is None or body.lon is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "location_required")
        until = now() + timedelta(hours=body.hours)
        if volunteer.period_to is not None:
            # Readiness never outlasts the declared period.
            until = min(until, datetime.combine(volunteer.period_to + timedelta(days=1), datetime.min.time(), UTC))
        volunteer.ready_until = until
        await get_presence().put(volunteer.user_id, Fix(body.lat, body.lon, body.accuracy_m, now()), until)
    volunteer.updated_at = now()
    await session.flush()
    await announce(session, volunteer)
    return volunteer


async def update_location(session: AsyncSession, reporter: Reporter, body: schemas.LocationIn) -> None:
    volunteer = await get_mine(session, reporter)
    if not is_ready(volunteer) or volunteer.ready_until is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_ready")
    await get_presence().put(volunteer.user_id, Fix(body.lat, body.lon, body.accuracy_m, now()), volunteer.ready_until)


# ---------------------------------------------------------------- staff (dashboard)


def scope_filter(principal: Principal) -> Any:
    return True if principal.is_national else Volunteer.gouvernorat_code == principal.gouvernorat_code


def _encode(rank: int, at: datetime, user_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{rank}|{at.isoformat()}|{user_id}".encode()).decode().rstrip("=")


def _decode(cursor: str) -> tuple[int, datetime, uuid.UUID]:
    try:
        rank, at, uid = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode().split("|", 2)
        return int(rank), datetime.fromisoformat(at), uuid.UUID(uid)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc


async def staff_list(
    session: AsyncSession,
    principal: Principal,
    *,
    statuses: list[str],
    skill: str | None,
    gouvernorat_code: int | None,
    ready: bool | None,
    q: str | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[schemas.StaffVolunteer], str | None]:
    rank = case((Volunteer.status == "pending", 0), else_=1)
    query = (
        select(Volunteer, Profile, rank)
        .outerjoin(Profile, Profile.user_id == Volunteer.user_id)
        .where(scope_filter(principal))
    )
    if statuses:
        query = query.where(Volunteer.status.in_(statuses))
    if skill:
        query = query.where(any_(Volunteer.skills) == skill)
    if gouvernorat_code:
        query = query.where(Volunteer.gouvernorat_code == gouvernorat_code)
    if ready is not None:
        live = and_(Volunteer.status == "approved", Volunteer.ready_until > func.now())
        query = query.where(live if ready else ~live)
    if q:
        pattern = f"%{q.replace('%', '').replace('_', '')}%"
        query = query.where(
            or_(
                Profile.first_name.ilike(pattern),
                Profile.last_name.ilike(pattern),
                Profile.phone.ilike(pattern),
                func.concat(Profile.first_name, " ", Profile.last_name).ilike(pattern),
            )
        )
    if cursor:
        c_rank, c_at, c_id = _decode(cursor)
        query = query.where(
            or_(
                rank > c_rank,
                and_(rank == c_rank, Volunteer.submitted_at < c_at),
                and_(rank == c_rank, Volunteer.submitted_at == c_at, Volunteer.user_id < c_id),
            )
        )
    rows = (
        await session.execute(
            query.order_by(rank, Volunteer.submitted_at.desc(), Volunteer.user_id.desc()).limit(limit)
        )
    ).all()
    items = [staff_item(v, p) for v, p, _ in rows]
    next_cursor = None
    if len(rows) == limit:
        last, _, last_rank = rows[-1]
        next_cursor = _encode(int(last_rank), last.submitted_at, last.user_id)
    return items, next_cursor


async def get_in_scope(
    session: AsyncSession, principal: Principal, volunteer_id: uuid.UUID, lock: bool = False
) -> Volunteer:
    volunteer = await session.get(Volunteer, volunteer_id, with_for_update=lock)
    if volunteer is None or not principal.can_access_gouvernorat(volunteer.gouvernorat_code):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return volunteer


async def staff_detail(session: AsyncSession, volunteer: Volunteer) -> schemas.StaffVolunteerDetail:
    profile = await session.get(Profile, volunteer.user_id)
    reviews = await session.scalars(
        select(VolunteerReview).where(VolunteerReview.user_id == volunteer.user_id).order_by(VolunteerReview.at.desc())
    )
    callouts = (
        await session.execute(
            select(CalloutTarget, Callout)
            .join(Callout, Callout.id == CalloutTarget.callout_id)
            .where(CalloutTarget.volunteer_id == volunteer.user_id)
            .order_by(CalloutTarget.sent_at.desc())
            .limit(20)
        )
    ).all()
    return schemas.StaffVolunteerDetail(
        **staff_item(volunteer, profile).model_dump(),
        email=profile.email if profile else None,
        other_skill=volunteer.other_skill,
        notes=volunteer.notes,
        review_reason=volunteer.review_reason,
        reviews=[schemas.VolunteerReviewOut(decision=r.decision, reason=r.reason, at=r.at) for r in reviews],
        callouts=[
            schemas.VolunteerCalloutRef(
                callout_id=c.id,
                incident_id=c.incident_id,
                skill=c.skill,
                status=t.status,
                sent_at=t.sent_at,
                responded_at=t.responded_at,
            )
            for t, c in callouts
        ],
    )


async def review(
    session: AsyncSession, principal: Principal, volunteer: Volunteer, body: schemas.VolunteerReviewIn
) -> str:
    required, target = _DECISIONS[body.decision]
    if volunteer.status != required:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    if body.decision in ("reject", "suspend") and not body.reason:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reason_required")
    previous = volunteer.status
    actor = audit.actor_of(principal)
    volunteer.status, volunteer.reviewed_at, volunteer.reviewed_by = target, now(), actor
    volunteer.review_reason = body.reason
    volunteer.version += 1
    volunteer.updated_at = now()
    if target != "approved":
        await _end_readiness(session, volunteer)
    session.add(VolunteerReview(user_id=volunteer.user_id, decision=body.decision, reason=body.reason, actor=actor))
    profile = await session.get(Profile, volunteer.user_id)
    if profile is not None and profile.email:
        # FR-A-021: the decision is confirmed by e-mail, in the volunteer's language.
        lang = profile.locale if profile.locale in ("ar", "fr", "en") else "ar"
        body_text = templates.pick(templates.VOLUNTEER_DECISION_BODY[body.decision], lang).format(
            name=full_name(profile) or "", reason=body.reason or ""
        )
        text = f"{body_text}\n\n{templates.pick(templates.SIGNATURE, lang)}"
        outbox.email(
            session, profile.email, templates.pick(templates.VOLUNTEER_DECISION_SUBJECT[body.decision], lang), text
        )
    await session.flush()
    await announce(session, volunteer)
    return previous


async def map_features(
    session: AsyncSession, principal: Principal, bbox: tuple[float, float, float, float] | None, skill: str | None
) -> dict[str, Any]:
    fixes = await get_presence().within(bbox or TUNISIA_BBOX)
    features: list[dict[str, Any]] = []
    if fixes:
        query = (
            select(Volunteer, Profile)
            .outerjoin(Profile, Profile.user_id == Volunteer.user_id)
            .where(
                Volunteer.user_id.in_(list(fixes)),
                Volunteer.status == "approved",
                Volunteer.ready_until > func.now(),
                scope_filter(principal),
            )
        )
        if skill:
            query = query.where(any_(Volunteer.skills) == skill)
        for volunteer, profile in (await session.execute(query)).all():
            fix = fixes[volunteer.user_id]
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [fix.lon, fix.lat]},
                    "properties": {
                        "id": str(volunteer.user_id),
                        "full_name": full_name(profile),
                        "phone": profile.phone if profile else None,
                        "skills": list(volunteer.skills),
                        "ready_until": volunteer.ready_until.isoformat() if volunteer.ready_until else None,
                        "at": fix.at.isoformat(),
                    },
                }
            )
    return {"type": "FeatureCollection", "features": features}


async def expire_readiness(session: AsyncSession) -> int:
    """Readiness ended (time or period): clear the flag. The Valkey position expires on its own."""
    result = await session.execute(
        update(Volunteer)
        .where(Volunteer.ready_until.is_not(None), Volunteer.ready_until <= func.now())
        .values(ready_until=None)
        .returning(Volunteer.user_id)
    )
    return len(result.all())
