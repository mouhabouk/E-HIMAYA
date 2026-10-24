"""Locked medical files (phase C1-b, docs/phase-c/design-medical-axis.md §12).

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
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import as_system
from app.modules.doctors.models import Doctor
from app.modules.medical import schemas
from app.modules.medical.models import FileKey, FileOpening, LockedFile
from app.modules.reports.geo import Assessment
from app.modules.reports.models import MedicalAttachment, Report

log = logging.getLogger(__name__)

MAX_LOCKED_BYTES = 65_536


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
    """Removes the copies locked for a doctor (all of them, or those received for ``vias``)."""
    query = delete(FileKey).where(FileKey.doctor_id == doctor_id)
    if vias is not None:
        query = query.where(FileKey.via.in_(vias))
    async with as_system(session):
        result = await session.execute(query.returning(FileKey.report_id))
        return len(result.all())


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
