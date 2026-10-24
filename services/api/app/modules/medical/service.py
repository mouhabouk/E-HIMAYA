"""Locked medical files (phase C1-b, docs/phase-c/design-medical-axis.md §12; referrals and opinions, C1-c §13).

The reporter's phone locks the part of their medical file that is not on the emergency card for the Civil Protection
doctors of the place's gouvernorat and for the medical committee; the server keeps the locked file and one locked key
per doctor, and never opens either. Doctors fetch their copy and open it on their own phone.

The ``medical`` schema is written with the system scope after the API's own checks; a doctor reads their own keys.
"""

import base64
import binascii
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import as_system
from app.modules.doctors.models import Doctor
from app.modules.identity.models import Profile
from app.modules.identity.service import Reporter
from app.modules.medical import schemas
from app.modules.medical.models import FileKey, FileOpening, LockedFile, Opinion, OpinionKey, Referral
from app.modules.notify import outbox
from app.modules.reports.geo import Assessment
from app.modules.reports.models import MedicalAttachment, Report

log = logging.getLogger(__name__)

MAX_LOCKED_BYTES = 65_536
MAX_OPINION_BYTES = 32_768
MAX_REFERRALS = 5
MAX_OPINIONS = 5  # by one specialist on one file


def b64(value: bytes) -> str:
    return base64.b64encode(value).decode()


def unb64(value: str, *, size: int | None = None, max_size: int | None = None, error: str = "invalid_key") -> bytes:
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error) from exc
    if (size is not None and len(raw) != size) or (max_size is not None and len(raw) > max_size):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error)
    return raw


def _committee_member(at: Any = None) -> Any:
    return (Doctor.committee_until.is_not(None)) & (Doctor.committee_until > (at if at is not None else func.now()))


def groups_of(place: Assessment) -> list[int]:
    """The gouvernorats whose doctors receive the file: the place's, or its candidates while it is uncertain."""
    return [place.gouvernorat_code] if place.gouvernorat_code is not None else list(place.candidates)


async def allowed(session: AsyncSession, gouvernorat_codes: list[int]) -> dict[uuid.UUID, tuple[bytes, str]]:
    """Doctors a file may be locked for, with their public key and why (their gouvernorat first)."""
    ready = (Doctor.status == "approved") & Doctor.public_key.is_not(None)
    rows = (
        await session.execute(
            select(Doctor.user_id, Doctor.public_key, Doctor.gouvernorat_code, Doctor.kind, Doctor.committee_until)
            .where(
                ready,
                ((Doctor.kind == "civil_protection") & Doctor.gouvernorat_code.in_(gouvernorat_codes or [-1]))
                | _committee_member(),
            )
            .order_by(Doctor.user_id)
        )
    ).all()
    out: dict[uuid.UUID, tuple[bytes, str]] = {}
    for user_id, key, code, kind, _ in rows:
        if key is None:
            continue
        local = kind == "civil_protection" and code in gouvernorat_codes
        out[user_id] = (key, "gouvernorat" if local else "committee")
    return out


async def recipients(session: AsyncSession, place: Assessment) -> schemas.RecipientsOut:
    codes = groups_of(place)
    found = await allowed(session, codes)
    items = [schemas.Recipient(doctor_id=d, public_key=b64(k), via=v) for d, (k, v) in found.items()]
    items.sort(key=lambda r: (r.via != "gouvernorat", str(r.doctor_id)))
    return schemas.RecipientsOut(gouvernorat_codes=codes, recipients=items)


async def store(session: AsyncSession, report: Report, place: Assessment, body: schemas.LockedFileIn) -> int:
    """Stores the locked file with the keys of the doctors allowed for this place. A key for anyone else is dropped,
    never the report: the emergency comes first. Returns how many keys were kept (0: no locked file is kept)."""
    nonce = unb64(body.nonce, size=12, error="invalid_locked_file")
    ciphertext = unb64(body.ciphertext, max_size=MAX_LOCKED_BYTES, error="invalid_locked_file")
    if len(ciphertext) < 17:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_locked_file")
    keys = [
        (k.doctor_id, unb64(k.eph_public, size=32), unb64(k.nonce, size=12), unb64(k.wrapped, size=48))
        for k in body.keys
    ]
    async with as_system(session):
        ok = await allowed(session, groups_of(place))
        kept = {doctor_id: rest for doctor_id, *rest in keys if doctor_id in ok}
        if len(kept) < len(keys):
            log.info(
                "locked file of report %s: %d key(s) for doctors not allowed dropped", report.id, len(keys) - len(kept)
            )
        if not kept:
            return 0
        session.add(LockedFile(report_id=report.id, nonce=nonce, ciphertext=ciphertext))
        await session.flush()
        for doctor_id, (eph, key_nonce, wrapped) in kept.items():
            session.add(
                FileKey(
                    report_id=report.id,
                    doctor_id=doctor_id,
                    via=ok[doctor_id][1],
                    eph_public=eph,
                    nonce=key_nonce,
                    wrapped=wrapped,
                )
            )
        await session.flush()
    return len(kept)


async def has_locked(session: AsyncSession, report_id: uuid.UUID) -> bool:
    async with as_system(session):
        return await session.get(LockedFile, report_id) is not None


# ---------------------------------------------------------------- the doctor


def require_ready(doctor: Doctor) -> None:
    if doctor.status != "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, "doctor_not_approved")
    if doctor.public_key is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "doctor_key_missing")


async def set_key(session: AsyncSession, doctor: Doctor, body: schemas.DoctorKeyIn) -> bool:
    """Sets (or replaces, after a forgotten code) the doctor's key. Returns True when an older key was replaced: the
    copies locked for it can no longer be opened and are dropped."""
    if doctor.status != "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, "doctor_not_approved")
    public_key = unb64(body.public_key, size=32)
    backup = body.backup
    unb64(backup.salt, size=16)
    unb64(backup.nonce, size=12)
    unb64(backup.ciphertext, size=48)
    replaced = doctor.public_key is not None and doctor.public_key != public_key
    if replaced:
        await drop_keys(session, doctor.user_id)
    doctor.public_key, doctor.key_backup = public_key, backup.model_dump()
    doctor.key_set_at = datetime.now(UTC)
    doctor.version += 1
    await session.flush()
    return replaced


def key_out(doctor: Doctor) -> schemas.DoctorKeyOut:
    if doctor.public_key is None or doctor.key_backup is None or doctor.key_set_at is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "doctor_key_missing")
    return schemas.DoctorKeyOut(
        public_key=b64(doctor.public_key),
        backup=schemas.KeyBackup.model_validate(doctor.key_backup),
        set_at=doctor.key_set_at,
    )


async def drop_keys(session: AsyncSession, doctor_id: uuid.UUID, vias: tuple[str, ...] | None = None) -> int:
    """Removes the copies locked for a doctor (all of them, or those received for ``vias``), with their copies of the
    opinions on those files. An opinion they wrote stays for its other readers."""
    query = delete(FileKey).where(FileKey.doctor_id == doctor_id)
    if vias is not None:
        query = query.where(FileKey.via.in_(vias))
    async with as_system(session):
        dropped = [r for (r,) in (await session.execute(query.returning(FileKey.report_id))).all()]
        opinions = delete(OpinionKey).where(OpinionKey.doctor_id == doctor_id)
        if vias is not None:
            opinions = opinions.where(
                OpinionKey.opinion_id.in_(
                    select(Opinion.id).where(Opinion.report_id.in_(dropped or [uuid.UUID(int=0)]))
                )
            )
        await session.execute(opinions)
        return len(dropped)


async def inbox(session: AsyncSession, doctor: Doctor, limit: int) -> list[schemas.InboxItem]:
    require_ready(doctor)
    last_open = (
        select(func.max(FileOpening.at))
        .where(FileOpening.report_id == FileKey.report_id, FileOpening.doctor_id == doctor.user_id)
        .scalar_subquery()
    )
    async with as_system(session):
        rows = (
            await session.execute(
                select(FileKey.via, Report, last_open)
                .join(Report, Report.id == FileKey.report_id)
                .where(FileKey.doctor_id == doctor.user_id)
                .order_by(FileKey.created_at.desc())
                .limit(limit)
            )
        ).all()
    return [
        schemas.InboxItem(
            report_id=r.id,
            tracking_code=r.tracking_code,
            category=r.category,
            gouvernorat_code=r.gouvernorat_code,
            received_at=r.received_at,
            report_status=r.status,
            via=via,
            opened_at=opened,
        )
        for via, r, opened in rows
    ]


async def open_file(
    session: AsyncSession, doctor: Doctor, report_id: uuid.UUID, reason: str | None
) -> tuple[schemas.OpenedFile, int | None]:
    """The doctor's copy of a file, recorded. A committee copy needs an active membership and a reason. Returns the file
    and the report's gouvernorat (for the audit log)."""
    require_ready(doctor)
    async with as_system(session):
        key = await session.get(FileKey, (report_id, doctor.user_id))
        if key is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        committee = key.via == "committee"
        if committee:
            until = doctor.committee_until
            if until is None or until <= datetime.now(UTC):
                raise HTTPException(status.HTTP_403_FORBIDDEN, "not_committee_member")
            if not reason:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reason_required")
        locked = await session.get(LockedFile, report_id)
        attachment = await session.get(MedicalAttachment, report_id)
        report = await session.get(Report, report_id)
        if locked is None or report is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        session.add(FileOpening(report_id=report_id, doctor_id=doctor.user_id, as_committee=committee, reason=reason))
        out = schemas.OpenedFile(
            report_id=report_id,
            via=key.via,
            nonce=b64(locked.nonce),
            ciphertext=b64(locked.ciphertext),
            eph_public=b64(key.eph_public),
            key_nonce=b64(key.nonce),
            wrapped=b64(key.wrapped),
            card=(attachment.data or None) if attachment is not None else None,
        )
        gouvernorat = report.gouvernorat_code
        await session.flush()
    return out, gouvernorat


# ---------------------------------------------------------------- referrals and opinions (phase C1-c)


def _name(profile: Profile | None) -> str | None:
    if profile is None:
        return None
    return " ".join(p for p in (profile.first_name, profile.last_name) if p) or None


def _active(doctor: Doctor) -> bool:
    return doctor.committee_until is not None and doctor.committee_until > datetime.now(UTC)


def _wrapped(keys: list[schemas.WrappedKeyIn]) -> dict[uuid.UUID, tuple[bytes, bytes, bytes]]:
    out = {
        k.doctor_id: (unb64(k.eph_public, size=32), unb64(k.nonce, size=12), unb64(k.wrapped, size=48)) for k in keys
    }
    if len(out) < len(keys):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "duplicate_recipient")
    return out


async def _holding(session: AsyncSession, doctor: Doctor, report_id: uuid.UUID) -> FileKey:
    """The caller's copy of the file (inside ``as_system``); a committee copy needs an active membership."""
    key = await session.get(FileKey, (report_id, doctor.user_id))
    if key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if key.via == "committee" and not _active(doctor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_committee_member")
    return key


async def _targets(
    session: AsyncSession, me: Doctor, ids: list[uuid.UUID], *, committee: bool
) -> dict[uuid.UUID, Doctor]:
    found = {d.user_id: d for d in (await session.scalars(select(Doctor).where(Doctor.user_id.in_(ids)))).all()}
    for doctor_id in ids:
        d = found.get(doctor_id)
        if d is None or d.user_id == me.user_id or d.status != "approved" or d.public_key is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_recipient")
        if committee and not _active(d):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_recipient")
    return found


async def _no_copy_yet(session: AsyncSession, report_id: uuid.UUID, ids: list[uuid.UUID]) -> None:
    held = await session.scalar(
        select(func.count()).select_from(FileKey).where(FileKey.report_id == report_id, FileKey.doctor_id.in_(ids))
    )
    if held:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_holds_file")


async def refer(
    session: AsyncSession, doctor: Doctor, report_id: uuid.UUID, body: schemas.ReferralIn
) -> tuple[list[uuid.UUID], int | None]:
    """A doctor of the gouvernorat group or of the committee sends the file to specialists (at most 5 per file); a
    specialist does not refer it on. Returns the specialists and the report's gouvernorat (for the audit log)."""
    require_ready(doctor)
    wrapped = _wrapped(body.keys)
    ids = list(wrapped)
    async with as_system(session):
        mine = await _holding(session, doctor, report_id)
        if mine.via == "referral":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "referral_not_allowed")
        # One referral at a time per file, so the cap holds.
        await session.get(LockedFile, report_id, with_for_update=True)
        count = await session.scalar(select(func.count()).select_from(Referral).where(Referral.report_id == report_id))
        if (count or 0) + len(ids) > MAX_REFERRALS:
            raise HTTPException(status.HTTP_409_CONFLICT, "too_many_referrals")
        await _targets(session, doctor, ids, committee=False)
        await _no_copy_yet(session, report_id, ids)
        for doctor_id, (eph, nonce, key) in wrapped.items():
            session.add(
                FileKey(
                    report_id=report_id, doctor_id=doctor_id, via="referral", eph_public=eph, nonce=nonce, wrapped=key
                )
            )
            session.add(
                Referral(report_id=report_id, doctor_id=doctor_id, referred_by=doctor.user_id, reason=body.reason)
            )
            # Content-free (A8): the specialist sees the file in their inbox.
            outbox.push(session, doctor_id, "medical_referral", {"report_id": str(report_id)}, alert=True)
        report = await session.get(Report, report_id)
        await session.flush()
        return ids, report.gouvernorat_code if report is not None else None


async def referrals(session: AsyncSession, doctor: Doctor, report_id: uuid.UUID) -> list[schemas.ReferralOut]:
    """Who the file was referred to, for the gouvernorat group and the committee (not for the specialists)."""
    require_ready(doctor)
    async with as_system(session):
        mine = await _holding(session, doctor, report_id)
        if mine.via == "referral":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "referral_not_allowed")
        rows = (
            await session.execute(
                select(Referral, Doctor, Profile)
                .join(Doctor, Doctor.user_id == Referral.doctor_id)
                .outerjoin(Profile, Profile.user_id == Doctor.user_id)
                .where(Referral.report_id == report_id)
                .order_by(Referral.at)
            )
        ).all()
        return [
            schemas.ReferralOut(
                doctor_id=d.user_id,
                full_name=_name(p),
                specialties=list(d.specialties),
                workplace=d.workplace,
                at=r.at,
                mine=r.referred_by == doctor.user_id,
            )
            for r, d, p in rows
        ]


async def _readers(session: AsyncSession, doctor: Doctor, report_id: uuid.UUID) -> dict[uuid.UUID, tuple[bytes, str]]:
    """Who a specialist's opinion is locked for (inside ``as_system``): the gouvernorat group and the committee members
    holding the file, the doctor who referred it, and the author."""
    mine = await _holding(session, doctor, report_id)
    if mine.via != "referral":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_referred")
    rows = (
        await session.execute(
            select(Doctor, FileKey.via)
            .join(FileKey, FileKey.doctor_id == Doctor.user_id)
            .where(FileKey.report_id == report_id, FileKey.via.in_(("gouvernorat", "committee")))
        )
    ).all()
    out: dict[uuid.UUID, tuple[bytes, str]] = {}
    for d, via in rows:
        if d.status == "approved" and d.public_key is not None and (via != "committee" or _active(d)):
            out[d.user_id] = (d.public_key, via)
    referral = await session.get(Referral, (report_id, doctor.user_id))
    if referral is not None and referral.referred_by is not None:
        by = await session.get(Doctor, referral.referred_by)
        if by is not None and by.status == "approved" and by.public_key is not None:
            out[by.user_id] = (by.public_key, "referrer")
    if doctor.public_key is not None:
        out[doctor.user_id] = (doctor.public_key, "author")
    return out


async def opinion_recipients(
    session: AsyncSession, doctor: Doctor, report_id: uuid.UUID
) -> list[schemas.OpinionRecipient]:
    require_ready(doctor)
    async with as_system(session):
        found = await _readers(session, doctor, report_id)
    return [
        schemas.OpinionRecipient(doctor_id=d, public_key=b64(k), role=role)
        for d, (k, role) in sorted(found.items(), key=lambda i: str(i[0]))
    ]


async def add_opinion(
    session: AsyncSession, doctor: Doctor, report_id: uuid.UUID, body: schemas.OpinionIn
) -> tuple[uuid.UUID, int | None]:
    """Stores a referred specialist's locked opinion. A key for anyone outside its readers is refused (the phone asks
    for the list again). Returns the opinion and the report's gouvernorat (for the audit log)."""
    require_ready(doctor)
    nonce = unb64(body.nonce, size=12, error="invalid_opinion")
    ciphertext = unb64(body.ciphertext, max_size=MAX_OPINION_BYTES, error="invalid_opinion")
    if len(ciphertext) < 17:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_opinion")
    if body.specialty is not None and body.specialty not in doctor.specialties:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_specialty")
    specialty = body.specialty or (doctor.specialties[0] if doctor.specialties else None)
    wrapped = _wrapped(body.keys)
    async with as_system(session):
        readers = await _readers(session, doctor, report_id)
        if set(wrapped) - set(readers):
            raise HTTPException(status.HTTP_409_CONFLICT, "recipients_changed")
        if doctor.user_id not in wrapped:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "author_key_missing")
        written = await session.scalar(
            select(func.count())
            .select_from(Opinion)
            .where(Opinion.report_id == report_id, Opinion.author_id == doctor.user_id)
        )
        if (written or 0) >= MAX_OPINIONS:
            raise HTTPException(status.HTTP_409_CONFLICT, "too_many_opinions")
        opinion = Opinion(
            report_id=report_id, author_id=doctor.user_id, specialty=specialty, nonce=nonce, ciphertext=ciphertext
        )
        session.add(opinion)
        await session.flush()
        for doctor_id, (eph, key_nonce, key) in wrapped.items():
            session.add(
                OpinionKey(opinion_id=opinion.id, doctor_id=doctor_id, eph_public=eph, nonce=key_nonce, wrapped=key)
            )
            if doctor_id != doctor.user_id:
                outbox.push(session, doctor_id, "medical_opinion", {"report_id": str(report_id)})
        report = await session.get(Report, report_id)
        await session.flush()
        return opinion.id, report.gouvernorat_code if report is not None else None


async def opinions(session: AsyncSession, doctor: Doctor, report_id: uuid.UUID) -> list[schemas.OpinionOut]:
    """The opinions on a file that were locked for the caller."""
    require_ready(doctor)
    async with as_system(session):
        rows = (
            await session.execute(
                select(Opinion, OpinionKey)
                .join(OpinionKey, OpinionKey.opinion_id == Opinion.id)
                .where(Opinion.report_id == report_id, OpinionKey.doctor_id == doctor.user_id)
                .order_by(Opinion.created_at)
            )
        ).all()
        return [
            schemas.OpinionOut(
                id=o.id,
                report_id=o.report_id,
                specialty=o.specialty,
                mine=o.author_id == doctor.user_id,
                created_at=o.created_at,
                nonce=b64(o.nonce),
                ciphertext=b64(o.ciphertext),
                eph_public=b64(k.eph_public),
                key_nonce=b64(k.nonce),
                wrapped=b64(k.wrapped),
            )
            for o, k in rows
        ]


# ---------------------------------------------------------------- a new committee member (phase C1-c)


def _require_member(doctor: Doctor) -> None:
    require_ready(doctor)
    if not _active(doctor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_committee_member")


async def pending_members(session: AsyncSession, doctor: Doctor, limit: int = 200) -> list[schemas.PendingMember]:
    """Committee members who joined after files (or opinions) the caller holds were locked: the caller's phone can lock
    those keys for them."""
    _require_member(doctor)
    out: list[schemas.PendingMember] = []
    async with as_system(session):
        members = (
            await session.execute(
                select(Doctor, Profile)
                .outerjoin(Profile, Profile.user_id == Doctor.user_id)
                .where(
                    Doctor.status == "approved",
                    Doctor.public_key.is_not(None),
                    _committee_member(),
                    Doctor.user_id != doctor.user_id,
                )
                .order_by(Doctor.committee_since, Doctor.user_id)
            )
        ).all()
        for member, profile in members:
            theirs = FileKey.__table__.alias("theirs")
            files = (
                await session.scalars(
                    select(FileKey.report_id)
                    .where(
                        FileKey.doctor_id == doctor.user_id,
                        ~exists().where(theirs.c.report_id == FileKey.report_id, theirs.c.doctor_id == member.user_id),
                    )
                    .order_by(FileKey.created_at)
                    .limit(limit)
                )
            ).all()
            other = OpinionKey.__table__.alias("other")
            ops = (
                await session.execute(
                    select(OpinionKey.opinion_id, Opinion.report_id)
                    .join(Opinion, Opinion.id == OpinionKey.opinion_id)
                    .where(
                        OpinionKey.doctor_id == doctor.user_id,
                        ~exists().where(
                            other.c.opinion_id == OpinionKey.opinion_id, other.c.doctor_id == member.user_id
                        ),
                    )
                    .order_by(OpinionKey.created_at)
                    .limit(limit)
                )
            ).all()
            if files or ops:
                assert member.public_key is not None
                out.append(
                    schemas.PendingMember(
                        doctor_id=member.user_id,
                        full_name=_name(profile),
                        public_key=b64(member.public_key),
                        files=list(files),
                        opinions=[schemas.PendingOpinion(id=i, report_id=r) for i, r in ops],
                    )
                )
    return out


async def share_file(
    session: AsyncSession, doctor: Doctor, report_id: uuid.UUID, body: schemas.ShareIn
) -> tuple[list[uuid.UUID], int | None]:
    """An active committee member locks the file key for newly appointed members (``via = 'committee'``)."""
    _require_member(doctor)
    wrapped = _wrapped(body.keys)
    ids = list(wrapped)
    async with as_system(session):
        await _holding(session, doctor, report_id)
        await _targets(session, doctor, ids, committee=True)
        await _no_copy_yet(session, report_id, ids)
        for doctor_id, (eph, nonce, key) in wrapped.items():
            session.add(
                FileKey(
                    report_id=report_id, doctor_id=doctor_id, via="committee", eph_public=eph, nonce=nonce, wrapped=key
                )
            )
        report = await session.get(Report, report_id)
        await session.flush()
        return ids, report.gouvernorat_code if report is not None else None


async def share_opinion(
    session: AsyncSession, doctor: Doctor, opinion_id: uuid.UUID, body: schemas.ShareIn
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """The same for an opinion: only to members who already hold the file. Returns the file and the members."""
    _require_member(doctor)
    wrapped = _wrapped(body.keys)
    ids = list(wrapped)
    async with as_system(session):
        if await session.get(OpinionKey, (opinion_id, doctor.user_id)) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        opinion = await session.get(Opinion, opinion_id)
        if opinion is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        await _targets(session, doctor, ids, committee=True)
        holders = set(
            (
                await session.scalars(
                    select(FileKey.doctor_id).where(FileKey.report_id == opinion.report_id, FileKey.doctor_id.in_(ids))
                )
            ).all()
        )
        if holders != set(ids):
            raise HTTPException(status.HTTP_409_CONFLICT, "file_not_shared")
        held = await session.scalar(
            select(func.count())
            .select_from(OpinionKey)
            .where(OpinionKey.opinion_id == opinion_id, OpinionKey.doctor_id.in_(ids))
        )
        if held:
            raise HTTPException(status.HTTP_409_CONFLICT, "already_holds_opinion")
        for doctor_id, (eph, nonce, key) in wrapped.items():
            session.add(
                OpinionKey(opinion_id=opinion_id, doctor_id=doctor_id, eph_public=eph, nonce=nonce, wrapped=key)
            )
        report_id = opinion.report_id
        await session.flush()
    return report_id, ids


# ---------------------------------------------------------------- the reporter (phase C1-c)


def _role(as_committee: bool, d: Doctor) -> dict[str, Any]:
    if as_committee:
        return {"role": "committee", "gouvernorat_code": None, "specialties": [], "workplace": None}
    if d.kind == "civil_protection":
        return {
            "role": "civil_protection",
            "gouvernorat_code": d.gouvernorat_code,
            "specialties": [],
            "workplace": None,
        }
    return {
        "role": "specialist",
        "gouvernorat_code": None,
        "specialties": list(d.specialties),
        "workplace": d.workplace,
    }


async def my_openings(
    session: AsyncSession, reporter: Reporter, report_id: uuid.UUID | None, limit: int
) -> list[schemas.Opening]:
    """Every opening and referral of the reporter's locked files, by role: never a doctor's name, and the committee
    only as "the medical committee"."""
    own = Report.user_id == reporter.user_id
    if report_id is not None:
        own = own & (Report.id == report_id)
    async with as_system(session):
        opened = (
            await session.execute(
                select(FileOpening, Doctor, Report.tracking_code)
                .join(Report, Report.id == FileOpening.report_id)
                .join(Doctor, Doctor.user_id == FileOpening.doctor_id)
                .where(own)
                .order_by(FileOpening.at.desc())
                .limit(limit)
            )
        ).all()
        referred = (
            await session.execute(
                select(Referral, Doctor, Report.tracking_code)
                .join(Report, Report.id == Referral.report_id)
                .join(Doctor, Doctor.user_id == Referral.doctor_id)
                .where(own)
                .order_by(Referral.at.desc())
                .limit(limit)
            )
        ).all()
    items = [
        schemas.Opening(report_id=o.report_id, tracking_code=code, kind="open", at=o.at, **_role(o.as_committee, d))
        for o, d, code in opened
    ] + [
        schemas.Opening(report_id=r.report_id, tracking_code=code, kind="referral", at=r.at, **_role(False, d))
        for r, d, code in referred
    ]
    items.sort(key=lambda i: i.at, reverse=True)
    return items[:limit]


async def counts(session: AsyncSession, report_id: uuid.UUID) -> tuple[int, int]:
    """How many referrals and opinions a file has (the dashboard shows counts, never content)."""
    async with as_system(session):
        refs = await session.scalar(select(func.count()).select_from(Referral).where(Referral.report_id == report_id))
        ops = await session.scalar(select(func.count()).select_from(Opinion).where(Opinion.report_id == report_id))
    return refs or 0, ops or 0
