"""Doctors (phase C1-a, docs/phase-c/design-medical-axis.md §2).

A registered citizen declares themselves a **volunteer doctor** (a specialist who accepts medical files to give an
opinion) or a **Civil Protection doctor** (who will receive the medical files of their gouvernorat), with their
specialties, registration number and workplace. Staff (a regional medical coordinator, or the volunteer reviewers)
check the registration before the doctor receives anything; the decision is e-mailed like a volunteer's.

The system administrator appoints approved Civil Protection doctors to the national **medical committee** for a fixed
term (§11): at most ``doctors.committee_max`` members (a setting), never themselves; the membership ends on its own
when the doctor stops being an approved Civil Protection doctor.

The workplace's gouvernorat is the doctor's group. Approved doctors find one another by specialty and gouvernorat for
referrals (``directory``): name, workplace and availability only, never the phone or the registration number.
"""

import base64
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, any_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.modules.audit import service as audit
from app.modules.availability import service as availability
from app.modules.doctors import schemas
from app.modules.doctors.models import Doctor, DoctorReview
from app.modules.geo.models import Gouvernorat
from app.modules.identity.models import Profile
from app.modules.identity.service import Reporter
from app.modules.medical import service as medical
from app.modules.notify import outbox, templates
from app.modules.settings import service as settings

# Version of the doctor's terms the app shows before the registration (texts in the app's translations).
TERMS_VERSION = "1"

_DECISIONS: dict[str, tuple[str, str]] = {
    # decision: (required current status, new status)
    "approve": ("pending", "approved"),
    "reject": ("pending", "rejected"),
    "suspend": ("approved", "suspended"),
    "reinstate": ("suspended", "approved"),
}


def now() -> datetime:
    return datetime.now(UTC)


def is_available(doctor: Doctor, at: datetime | None = None) -> bool:
    return doctor.status == "approved" and doctor.available_until is not None and doctor.available_until > (at or now())


def committee_until(doctor: Doctor, at: datetime | None = None) -> datetime | None:
    """End of the current term, or None when the doctor is not (or no longer) on the medical committee."""
    if doctor.status != "approved" or doctor.committee_until is None or doctor.committee_until <= (at or now()):
        return None
    return doctor.committee_until


def leave_committee(doctor: Doctor) -> bool:
    """Ends the membership (status or kind changed, term ended, revoked). True when the doctor was a member."""
    # Not ``committee_until(doctor)``: the status may already have changed in this transaction.
    was = doctor.committee_until is not None and doctor.committee_until > now()
    doctor.committee_since = doctor.committee_until = doctor.committee_by = None
    return was


def full_name(profile: Profile | None) -> str | None:
    if profile is None:
        return None
    return " ".join(p for p in (profile.first_name, profile.last_name) if p) or None


def doctor_out(doctor: Doctor) -> schemas.DoctorOut:
    available = is_available(doctor)
    return schemas.DoctorOut(
        kind=doctor.kind,
        status=doctor.status,
        specialties=list(doctor.specialties),
        licence_no=doctor.licence_no,
        workplace=doctor.workplace,
        gouvernorat_code=doctor.gouvernorat_code,
        cp_unit=doctor.cp_unit,
        cp_staff_no=doctor.cp_staff_no,
        review_reason=doctor.review_reason,
        submitted_at=doctor.submitted_at,
        reviewed_at=doctor.reviewed_at,
        available=available,
        available_until=doctor.available_until if available else None,
        committee_until=committee_until(doctor),
        has_key=doctor.public_key is not None,
        version=doctor.version,
    )


def staff_item(doctor: Doctor, profile: Profile | None) -> schemas.StaffDoctor:
    return schemas.StaffDoctor(
        id=doctor.user_id,
        full_name=full_name(profile),
        kind=doctor.kind,
        specialties=list(doctor.specialties),
        workplace=doctor.workplace,
        gouvernorat_code=doctor.gouvernorat_code,
        cp_unit=doctor.cp_unit,
        status=doctor.status,
        available=is_available(doctor),
        submitted_at=doctor.submitted_at,
        committee_until=committee_until(doctor),
    )


# ---------------------------------------------------------------- the doctor (app)


def require_registered(reporter: Reporter) -> Reporter:
    if reporter.principal is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "registration_required")
    return reporter


async def get_mine(session: AsyncSession, reporter: Reporter, lock: bool = False) -> Doctor:
    doctor = await session.get(Doctor, require_registered(reporter).user_id, with_for_update=lock)
    if doctor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_doctor")
    return doctor


async def declare(session: AsyncSession, reporter: Reporter, body: schemas.DoctorIn) -> Doctor:
    require_registered(reporter)
    if body.terms_version != TERMS_VERSION:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown_terms_version")
    if body.kind == "civil_protection" and (body.cp_unit is None or body.cp_staff_no is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "cp_details_required")
    if await session.get(Gouvernorat, body.gouvernorat_code) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_gouvernorat")
    profile = await session.get(Profile, reporter.user_id)
    if profile is None or not profile.phone or not (profile.first_name or profile.last_name):
        # Staff call the doctor to check the registration, and colleagues pick them by name.
        raise HTTPException(status.HTTP_409_CONFLICT, "profile_incomplete")
    specialties: list[str] = sorted(set(body.specialties))
    doctor = await session.get(Doctor, reporter.user_id, with_for_update=True)
    if doctor is None:
        doctor = Doctor(user_id=reporter.user_id, status="pending", version=1)
        session.add(doctor)
    else:
        if body.version is not None and body.version != doctor.version:
            raise HTTPException(status.HTTP_409_CONFLICT, "version_conflict")
        checked = (
            doctor.kind,
            doctor.licence_no,
            doctor.cp_staff_no,
            doctor.gouvernorat_code,
            sorted(doctor.specialties),
        )
        declared = (
            body.kind,
            body.licence_no,
            body.cp_staff_no if body.kind == "civil_protection" else None,
            body.gouvernorat_code,
            specialties,
        )
        if doctor.status in ("rejected", "withdrawn") or (doctor.status == "approved" and checked != declared):
            # What staff checked changed: the doctor is reviewed again before receiving anything.
            doctor.status, doctor.submitted_at, doctor.review_reason = "pending", now(), None
            doctor.available_until = None
            leave_committee(doctor)
            # Files reached them as a checked doctor of a gouvernorat: they stop until the new review.
            await medical.drop_keys(session, doctor.user_id)
        doctor.version += 1
    doctor.kind = body.kind
    doctor.specialties = specialties
    doctor.licence_no = body.licence_no
    doctor.workplace = body.workplace
    doctor.gouvernorat_code = body.gouvernorat_code
    civil = body.kind == "civil_protection"
    doctor.cp_unit = body.cp_unit if civil else None
    doctor.cp_staff_no = body.cp_staff_no if civil else None
    doctor.terms_version = body.terms_version
    doctor.updated_at = now()
    await session.flush()
    await session.refresh(doctor)
    return doctor


async def clear(session: AsyncSession, doctor: Doctor) -> None:
    """Withdrawn (by the doctor or on erasure): the professional numbers, the key and every copy of a medical file
    locked for it go; the history of decisions stays."""
    doctor.status, doctor.available_until = "withdrawn", None
    leave_committee(doctor)
    doctor.public_key = doctor.key_backup = doctor.key_set_at = None
    await medical.drop_keys(session, doctor.user_id)
    doctor.licence_no = doctor.cp_staff_no = None
    doctor.version += 1
    doctor.updated_at = now()


async def withdraw(session: AsyncSession, reporter: Reporter) -> Doctor:
    doctor = await get_mine(session, reporter, lock=True)
    await clear(session, doctor)
    await session.flush()
    return doctor


async def set_availability(session: AsyncSession, reporter: Reporter, body: schemas.AvailabilityIn) -> Doctor:
    doctor = await get_mine(session, reporter, lock=True)
    if body.available:
        if doctor.status != "approved":
            raise HTTPException(status.HTTP_409_CONFLICT, "doctor_not_approved")
        doctor.available_until = now() + timedelta(hours=body.hours)
    else:
        doctor.available_until = None
    doctor.updated_at = now()
    await session.flush()
    return doctor


async def directory(
    session: AsyncSession, *, specialty: str | None, gouvernorat_code: int | None, near: int | None, limit: int
) -> list[schemas.DirectoryDoctor]:
    """Approved doctors for a referral: available first, then the caller's gouvernorat (``near``), then by name."""
    available = and_(Doctor.available_until.is_not(None), Doctor.available_until > func.now())
    query = (
        select(Doctor, Profile).outerjoin(Profile, Profile.user_id == Doctor.user_id).where(Doctor.status == "approved")
    )
    if specialty:
        query = query.where(any_(Doctor.specialties) == specialty)
    if gouvernorat_code:
        query = query.where(Doctor.gouvernorat_code == gouvernorat_code)
    order: list[Any] = [case((available, 0), else_=1)]
    if near is not None:
        order.append(case((Doctor.gouvernorat_code == near, 0), else_=1))
    order += [Doctor.gouvernorat_code, Profile.last_name, Profile.first_name, Doctor.user_id]
    rows = (await session.execute(query.order_by(*order).limit(limit))).all()
    return [
        schemas.DirectoryDoctor(
            id=d.user_id,
            full_name=full_name(p),
            kind=d.kind,
            specialties=list(d.specialties),
            workplace=d.workplace,
            gouvernorat_code=d.gouvernorat_code,
            available=is_available(d),
            public_key=medical.b64(d.public_key) if d.public_key is not None else None,
        )
        for d, p in rows
    ]


# ---------------------------------------------------------------- staff (dashboard)


def scope_filter(principal: Principal) -> Any:
    return True if principal.is_national else Doctor.gouvernorat_code == principal.gouvernorat_code


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
    kind: str | None,
    specialty: str | None,
    gouvernorat_code: int | None,
    q: str | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[schemas.StaffDoctor], str | None]:
    """Pending registrations first (they wait for a decision), then the newest."""
    rank = case((Doctor.status == "pending", 0), else_=1)
    query = (
        select(Doctor, Profile, rank)
        .outerjoin(Profile, Profile.user_id == Doctor.user_id)
        .where(scope_filter(principal))
    )
    if statuses:
        query = query.where(Doctor.status.in_(statuses))
    if kind:
        query = query.where(Doctor.kind == kind)
    if specialty:
        query = query.where(any_(Doctor.specialties) == specialty)
    if gouvernorat_code:
        query = query.where(Doctor.gouvernorat_code == gouvernorat_code)
    if q:
        pattern = f"%{q.replace('%', '').replace('_', '')}%"
        query = query.where(
            or_(
                Profile.first_name.ilike(pattern),
                Profile.last_name.ilike(pattern),
                func.concat(Profile.first_name, " ", Profile.last_name).ilike(pattern),
                Doctor.workplace.ilike(pattern),
            )
        )
    if cursor:
        c_rank, c_at, c_id = _decode(cursor)
        query = query.where(
            or_(
                rank > c_rank,
                and_(rank == c_rank, Doctor.submitted_at < c_at),
                and_(rank == c_rank, Doctor.submitted_at == c_at, Doctor.user_id < c_id),
            )
        )
    rows = (
        await session.execute(query.order_by(rank, Doctor.submitted_at.desc(), Doctor.user_id.desc()).limit(limit))
    ).all()
    items = [staff_item(d, p) for d, p, _ in rows]
    next_cursor = None
    if len(rows) == limit:
        last, _, last_rank = rows[-1]
        next_cursor = _encode(int(last_rank), last.submitted_at, last.user_id)
    return items, next_cursor


async def get_in_scope(session: AsyncSession, principal: Principal, doctor_id: uuid.UUID, lock: bool = False) -> Doctor:
    doctor = await session.get(Doctor, doctor_id, with_for_update=lock)
    if doctor is None or not principal.can_access_gouvernorat(doctor.gouvernorat_code):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return doctor


async def staff_detail(session: AsyncSession, doctor: Doctor) -> schemas.StaffDoctorDetail:
    profile = await session.get(Profile, doctor.user_id)
    reviews = await session.scalars(
        select(DoctorReview).where(DoctorReview.user_id == doctor.user_id).order_by(DoctorReview.at.desc())
    )
    return schemas.StaffDoctorDetail(
        **staff_item(doctor, profile).model_dump(),
        phone=profile.phone if profile else None,
        email=profile.email if profile else None,
        licence_no=doctor.licence_no,
        cp_staff_no=doctor.cp_staff_no,
        review_reason=doctor.review_reason,
        reviews=[schemas.DoctorReviewOut(decision=r.decision, reason=r.reason, at=r.at) for r in reviews],
        calendar=availability.out("doctor", await availability.slots_of(session, doctor.user_id, "doctor")),
    )


async def review(session: AsyncSession, principal: Principal, doctor: Doctor, body: schemas.DoctorReviewIn) -> str:
    required, target = _DECISIONS[body.decision]
    if doctor.status != required:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    if body.decision in ("reject", "suspend") and not body.reason:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reason_required")
    previous = doctor.status
    actor = audit.actor_of(principal)
    doctor.status, doctor.reviewed_at, doctor.reviewed_by = target, now(), actor
    doctor.review_reason = body.reason
    doctor.version += 1
    doctor.updated_at = now()
    if target != "approved":
        doctor.available_until = None
        if leave_committee(doctor):
            await medical.drop_keys(session, doctor.user_id, ("committee",))
    session.add(DoctorReview(user_id=doctor.user_id, decision=body.decision, reason=body.reason, actor=actor))
    profile = await session.get(Profile, doctor.user_id)
    if profile is not None and profile.email:
        lang = profile.locale if profile.locale in ("ar", "fr", "en") else "ar"
        body_text = templates.pick(templates.DOCTOR_DECISION_BODY[body.decision], lang).format(
            name=full_name(profile) or "", reason=body.reason or ""
        )
        text = f"{body_text}\n\n{templates.pick(templates.SIGNATURE, lang)}"
        outbox.email(
            session, profile.email, templates.pick(templates.DOCTOR_DECISION_SUBJECT[body.decision], lang), text
        )
    await session.flush()
    return previous


async def expire_availability(session: AsyncSession) -> int:
    """Availability ended: clear the flag (the worker runs it with the volunteers' readiness)."""
    result = await session.execute(
        update(Doctor)
        .where(Doctor.available_until.is_not(None), Doctor.available_until <= func.now())
        .values(available_until=None)
        .returning(Doctor.user_id)
    )
    return len(result.all())


# ---------------------------------------------------------------- the medical committee (system administrator)


async def committee(session: AsyncSession) -> list[schemas.CommitteeMember]:
    rows = (
        await session.execute(
            select(Doctor, Profile)
            .outerjoin(Profile, Profile.user_id == Doctor.user_id)
            .where(Doctor.status == "approved", Doctor.committee_until > func.now())
            .order_by(Doctor.committee_since, Doctor.user_id)
        )
    ).all()
    return [
        schemas.CommitteeMember(**staff_item(d, p).model_dump(), committee_since=d.committee_since)
        for d, p in rows
        if d.committee_since is not None
    ]


async def committee_candidates(session: AsyncSession, q: str | None, limit: int) -> list[schemas.StaffDoctor]:
    """Approved Civil Protection doctors who are not members (name and workplace only)."""
    query = (
        select(Doctor, Profile)
        .outerjoin(Profile, Profile.user_id == Doctor.user_id)
        .where(
            Doctor.status == "approved",
            Doctor.kind == "civil_protection",
            or_(Doctor.committee_until.is_(None), Doctor.committee_until <= func.now()),
        )
    )
    if q:
        pattern = f"%{q.replace('%', '').replace('_', '')}%"
        query = query.where(
            or_(
                func.concat(Profile.first_name, " ", Profile.last_name).ilike(pattern),
                Doctor.workplace.ilike(pattern),
                Doctor.cp_unit.ilike(pattern),
            )
        )
    order = (Doctor.gouvernorat_code, Profile.last_name, Profile.first_name, Doctor.user_id)
    rows = (await session.execute(query.order_by(*order).limit(limit))).all()
    return [staff_item(d, p) for d, p in rows]


def _notify_committee(session: AsyncSession, profile: Profile | None, event: str, **values: str) -> None:
    if profile is None or not profile.email:
        return
    lang = profile.locale if profile.locale in ("ar", "fr", "en") else "ar"
    body = templates.pick(templates.COMMITTEE_BODY[event], lang).format(name=full_name(profile) or "", **values)
    text = f"{body}\n\n{templates.pick(templates.SIGNATURE, lang)}"
    outbox.email(session, profile.email, templates.pick(templates.COMMITTEE_SUBJECT[event], lang), text)


async def appoint(
    session: AsyncSession, principal: Principal, doctor_id: uuid.UUID, body: schemas.AppointmentIn
) -> tuple[Doctor, bool]:
    """Appoints (or renews) a member until ``months`` from now. Returns the doctor and whether it was a renewal."""
    # One appointment at a time, so two administrators cannot both take the last seat.
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtext("identity.medical_committee"))))
    doctor = await session.get(Doctor, doctor_id, with_for_update=True)
    if doctor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if doctor.status != "approved" or doctor.kind != "civil_protection":
        raise HTTPException(status.HTTP_409_CONFLICT, "not_civil_protection_doctor")
    profile = await session.get(Profile, doctor.user_id)
    own = str(principal.claims.get("email") or "").strip().lower()
    if own and profile is not None and profile.email and profile.email.strip().lower() == own:
        # The administrator appoints, never themselves: the access to every file needs a second person.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "self_appointment")
    renewal = committee_until(doctor) is not None
    if not renewal:
        members = await session.scalar(
            select(func.count())
            .select_from(Doctor)
            .where(Doctor.status == "approved", Doctor.committee_until > func.now())
        )
        if (members or 0) >= await settings.threshold(session, "doctors.committee_max"):
            raise HTTPException(status.HTTP_409_CONFLICT, "committee_full")
        doctor.committee_since = now()
    until = now() + timedelta(days=30 * body.months)
    doctor.committee_until, doctor.committee_by = until, audit.actor_of(principal)
    doctor.version += 1
    doctor.updated_at = now()
    _notify_committee(session, profile, "renew" if renewal else "appoint", until=until.date().isoformat())
    await session.flush()
    return doctor, renewal


async def revoke(session: AsyncSession, doctor_id: uuid.UUID, reason: str) -> Doctor:
    doctor = await session.get(Doctor, doctor_id, with_for_update=True)
    if doctor is None or not leave_committee(doctor):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_committee_member")
    await medical.drop_keys(session, doctor.user_id, ("committee",))
    doctor.version += 1
    doctor.updated_at = now()
    _notify_committee(session, await session.get(Profile, doctor.user_id), "revoke", reason=reason)
    await session.flush()
    return doctor


async def expire_committee(session: AsyncSession) -> int:
    """Terms that ended: clear them (the worker runs it with the availability)."""
    result = await session.execute(
        update(Doctor)
        .where(Doctor.committee_until.is_not(None), Doctor.committee_until <= func.now())
        .values(committee_since=None, committee_until=None, committee_by=None)
        .returning(Doctor.user_id)
    )
    ended = list(result.scalars())
    for doctor_id in ended:
        await medical.drop_keys(session, doctor_id, ("committee",))
    return len(ended)
