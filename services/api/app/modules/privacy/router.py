"""Citizen rights (law 2004-63: access and erasure) for registered citizens and anonymous device identities.

* ``GET /api/v1/me/export``  — every personal datum held on the caller, decrypted, as one JSON document.
* ``POST /api/v1/me/delete`` — erasure: the profile is wiped at once; reports are kept for the legal
  retention period, detached from any identifier (the account keeps only its random id). Live streams still
  running are ended (their publisher disconnected); recordings and the position track stay with the report.
  Calls and emergency SMS lose the person's number; calls and their recordings stay for their retention period.
  Rewards: points and badges are deleted, nominations anonymised, certificates lose their holder and PDF.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from geoalchemy2 import Geometry
from pydantic import BaseModel
from sqlalchemy import cast, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import get_cipher
from app.core.db import as_system, get_session
from app.modules.audit import service as audit
from app.modules.contact import router as contact
from app.modules.doctors import service as doctors
from app.modules.doctors.models import Doctor
from app.modules.doctors.schemas import DoctorOut
from app.modules.identity.models import Account, Consent, ErasureRequest, Profile
from app.modules.identity.router import MedicalInfo
from app.modules.identity.service import CurrentReporter, limit_reporter
from app.modules.notify.models import Device, Message, Outbox
from app.modules.orgs.domain import OrgRole
from app.modules.orgs.models import Member
from app.modules.reports.models import Media, MedicalAttachment, Report, StatusHistory
from app.modules.rewards import privacy as rewards
from app.modules.safety import history as safety_history
from app.modules.safety import service as safety
from app.modules.streams import mediamtx
from app.modules.streams import service as streams
from app.modules.streams.domain import ACTIVE as ACTIVE_STREAMS
from app.modules.streams.domain import EndReason
from app.modules.streams.models import LiveStream, StreamLocation
from app.modules.telephony import privacy as telephony
from app.modules.volunteers import service as volunteers
from app.modules.volunteers.models import Volunteer
from app.modules.volunteers.presence import get_presence
from app.modules.volunteers.schemas import VolunteerOut

router = APIRouter(prefix="/api/v1", tags=["privacy"])
Session = Annotated[AsyncSession, Depends(get_session)]

EXPORT_PER_DAY = 3
DELETE_PER_DAY = 5
# Anonymous identities are free to mint: the client address bounds them too (see limit_reporter).
PER_IP_PER_DAY = 30
DAY_S = 86_400
_CIN_CONTEXT = "identity.profile.cin"


class ExportAccount(BaseModel):
    user_id: uuid.UUID
    kind: str
    status: str
    created_at: datetime


class ExportProfile(BaseModel):
    first_name: str | None
    last_name: str | None
    cin: str | None
    phone: str | None
    phone_verified_at: datetime | None
    email: str | None
    email_verified_at: datetime | None
    gouvernorat_code: int | None
    delegation_id: int | None
    address: str | None
    medical: MedicalInfo | None
    locale: str
    updated_at: datetime


class ExportConsent(BaseModel):
    charter_version: str
    locale: str
    platform: str | None
    accepted_at: datetime
    purpose: str = "charter"
    withdrawn_at: datetime | None = None


class ExportLocation(BaseModel):
    lat: float
    lon: float
    accuracy_m: float | None


class ExportStatus(BaseModel):
    status: str
    at: datetime


class ExportMedia(BaseModel):
    id: uuid.UUID
    kind: str
    content_type: str | None
    bytes: int | None
    sha256: str
    duration_s: float | None
    status: str
    created_at: datetime
    transcript: str | None
    translation_ar: str | None


class ExportReport(BaseModel):
    id: uuid.UUID
    tracking_code: str
    category: str
    status: str
    text: str | None
    lang: str | None
    text_ar: str | None
    location: ExportLocation
    gouvernorat_code: int | None
    created_at: datetime
    received_at: datetime
    updated_at: datetime
    history: list[ExportStatus]
    media: list[ExportMedia]


class ExportTrackPoint(BaseModel):
    at: datetime
    lat: float
    lon: float
    accuracy_m: float | None


class ExportStream(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID | None
    status: str
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    end_reason: str | None
    # Recordings are listed with the report's media (kind "recording").
    recording_media_ids: list[uuid.UUID]
    track: list[ExportTrackPoint]


class ExportDevice(BaseModel):
    platform: str
    locale: str
    # The push token is a device identifier: only its end is shown, enough to recognise it.
    token_suffix: str
    gouvernorat_code: int | None
    has_location: bool
    created_at: datetime
    updated_at: datetime


class ExportMessage(BaseModel):
    id: uuid.UUID
    kind: str
    title: dict[str, str]
    body: dict[str, str]
    published_at: datetime | None


class ExportOut(BaseModel):
    generated_at: datetime
    account: ExportAccount
    profile: ExportProfile | None
    consents: list[ExportConsent]
    reports: list[ExportReport]
    streams: list[ExportStream]
    # Phase 7: calls from or to the verified phone number, emergency SMS sent from it or creating own reports.
    calls: list[telephony.ExportCall]
    sms: list[telephony.ExportSms]
    volunteer: VolunteerOut | None
    # Phase C1-a: the doctor's registration (status, specialties, numbers).
    doctor: DoctorOut | None = None
    # Phase 8: points ledger, badges, certificates and nominations naming the person.
    rewards: rewards.ExportRewards
    devices: list[ExportDevice]
    messages: list[ExportMessage]
    # Phase B1: "contact us" requests, with the contact details given.
    contact: list[contact.ExportContact]


class DeleteIn(BaseModel):
    confirm: Literal["DELETE"]


class DeleteOut(BaseModel):
    status: Literal["deleted"]


def _profile(profile: Profile) -> ExportProfile:
    return ExportProfile(
        first_name=profile.first_name,
        last_name=profile.last_name,
        cin=get_cipher().decrypt(profile.cin_enc, context=_CIN_CONTEXT) if profile.cin_enc else None,
        phone=profile.phone,
        phone_verified_at=profile.phone_verified_at,
        email=profile.email,
        email_verified_at=profile.email_verified_at,
        gouvernorat_code=profile.gouvernorat_code,
        delegation_id=profile.delegation_id,
        address=profile.address,
        medical=MedicalInfo.model_validate(profile.medical) if profile.medical else None,
        locale=profile.locale,
        updated_at=profile.updated_at,
    )


async def _reports(session: AsyncSession, user_id: uuid.UUID) -> list[ExportReport]:
    point = cast(Report.location, Geometry)
    rows = (
        await session.execute(
            select(Report, func.ST_Y(point), func.ST_X(point))
            .where(Report.user_id == user_id)
            .order_by(Report.received_at)
        )
    ).all()
    ids = [r[0].id for r in rows]
    history: dict[uuid.UUID, list[ExportStatus]] = {i: [] for i in ids}
    media: dict[uuid.UUID, list[ExportMedia]] = {i: [] for i in ids}
    if ids:
        for h in await session.scalars(
            select(StatusHistory).where(StatusHistory.report_id.in_(ids)).order_by(StatusHistory.at, StatusHistory.id)
        ):
            history[h.report_id].append(ExportStatus(status=h.status, at=h.at))
        for m in await session.scalars(select(Media).where(Media.report_id.in_(ids)).order_by(Media.created_at)):
            assert m.report_id is not None
            media[m.report_id].append(
                ExportMedia(
                    id=m.id,
                    kind=m.kind,
                    content_type=m.content_type,
                    bytes=m.bytes,
                    sha256=m.sha256,
                    duration_s=m.duration_s,
                    status=m.status,
                    created_at=m.created_at,
                    transcript=m.transcript,
                    translation_ar=m.translation_ar,
                )
            )
    return [
        ExportReport(
            id=r.id,
            tracking_code=r.tracking_code,
            category=r.category,
            status=r.status,
            text=r.text_original,
            lang=r.lang_original,
            text_ar=r.text_ar,
            location=ExportLocation(lat=float(lat), lon=float(lon), accuracy_m=r.location_accuracy_m),
            gouvernorat_code=r.gouvernorat_code,
            created_at=r.created_at,
            received_at=r.received_at,
            updated_at=r.updated_at,
            history=history[r.id],
            media=media[r.id],
        )
        for r, lat, lon in rows
    ]


async def _streams(session: AsyncSession, user_id: uuid.UUID) -> list[ExportStream]:
    rows = list(
        await session.scalars(select(LiveStream).where(LiveStream.user_id == user_id).order_by(LiveStream.created_at))
    )
    ids = [s.id for s in rows]
    tracks: dict[uuid.UUID, list[ExportTrackPoint]] = {i: [] for i in ids}
    recordings: dict[uuid.UUID, list[uuid.UUID]] = {i: [] for i in ids}
    if ids:
        point = cast(StreamLocation.location, Geometry)
        for sid, at, lat, lon, accuracy in (
            await session.execute(
                select(
                    StreamLocation.stream_id,
                    StreamLocation.at,
                    func.ST_Y(point),
                    func.ST_X(point),
                    StreamLocation.accuracy_m,
                )
                .where(StreamLocation.stream_id.in_(ids))
                .order_by(StreamLocation.at, StreamLocation.id)
            )
        ).all():
            tracks[sid].append(ExportTrackPoint(at=at, lat=float(lat), lon=float(lon), accuracy_m=accuracy))
        for sid, media_id in (
            await session.execute(
                select(Media.stream_id, Media.id)
                .where(Media.stream_id.in_(ids), Media.kind == "recording")
                .order_by(Media.created_at)
            )
        ).all():
            if sid is not None:
                recordings[sid].append(media_id)
    return [
        ExportStream(
            id=s.id,
            report_id=s.report_id,
            status=s.status,
            created_at=s.created_at,
            started_at=s.started_at,
            ended_at=s.ended_at,
            end_reason=s.end_reason,
            recording_media_ids=recordings[s.id],
            track=tracks[s.id],
        )
        for s in rows
    ]


@router.get("/me/export", response_model=ExportOut)
async def export_my_data(
    request: Request, response: Response, reporter: CurrentReporter, session: Session
) -> ExportOut:
    """Right of access: all personal data held on the caller (registered citizen or anonymous device)."""
    await limit_reporter(
        request, reporter, "me-export", per_account=EXPORT_PER_DAY, per_ip=PER_IP_PER_DAY, window_s=DAY_S
    )
    user_id = reporter.user_id
    account = await session.get(Account, user_id)
    assert account is not None
    profile = await session.get(Profile, user_id)
    volunteer = await session.get(Volunteer, user_id)
    doctor = await session.get(Doctor, user_id)
    consents = await session.scalars(select(Consent).where(Consent.user_id == user_id).order_by(Consent.accepted_at))
    devices = await session.scalars(select(Device).where(Device.user_id == user_id).order_by(Device.created_at))
    messages = await session.scalars(
        select(Message)
        .where(Message.audience == "user", Message.user_id == user_id, Message.status != "draft")
        .order_by(Message.created_at)
    )
    calls, sms = await telephony.export(session, user_id)
    out = ExportOut(
        generated_at=datetime.now(UTC),
        account=ExportAccount(
            user_id=account.user_id, kind=account.kind.value, status=account.status.value, created_at=account.created_at
        ),
        profile=_profile(profile) if profile is not None else None,
        consents=[
            ExportConsent(
                charter_version=c.charter_version,
                locale=c.locale,
                platform=c.platform,
                accepted_at=c.accepted_at,
                purpose=c.purpose,
                withdrawn_at=c.withdrawn_at,
            )
            for c in consents
        ],
        reports=await _reports(session, user_id),
        streams=await _streams(session, user_id),
        calls=calls,
        sms=sms,
        volunteer=volunteers.volunteer_out(volunteer) if volunteer is not None else None,
        doctor=doctors.doctor_out(doctor) if doctor is not None else None,
        rewards=await rewards.export(session, user_id),
        devices=[
            ExportDevice(
                platform=d.platform,
                locale=d.locale,
                token_suffix=d.token[-8:],
                gouvernorat_code=d.gouvernorat_code,
                has_location=d.location is not None,
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
            for d in devices
        ],
        messages=[
            ExportMessage(id=m.id, kind=m.kind, title=m.title, body=m.body, published_at=m.published_at)
            for m in messages
        ],
        contact=await contact.export(session, user_id),
    )
    await audit.record(
        session,
        actor=reporter.actor,
        action="user.export",
        target=f"account:{user_id}",
        details={"reports": len(out.reports), "streams": len(out.streams)},
    )
    await session.commit()
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Disposition"] = f'attachment; filename="ehimaya-export-{date.today().isoformat()}.json"'
    return out


async def _leave_organizations(session: AsyncSession, user_id: uuid.UUID) -> int:
    """Memberships end with the account; the last administrator of an institution must hand over first."""
    memberships = list(await session.scalars(select(Member).where(Member.user_id == user_id).with_for_update()))
    for m in memberships:
        if m.role != OrgRole.ADMIN.value:
            continue
        others = await session.scalar(
            select(func.count())
            .select_from(Member)
            .where(Member.org_id == m.org_id, Member.role == OrgRole.ADMIN.value, Member.user_id != user_id)
        )
        if not others:
            raise HTTPException(status.HTTP_409_CONFLICT, "last_admin")
    await session.execute(delete(Member).where(Member.user_id == user_id))
    return len(memberships)


@router.post("/me/delete", response_model=DeleteOut, status_code=status.HTTP_202_ACCEPTED)
async def delete_my_account(request: Request, body: DeleteIn, reporter: CurrentReporter, session: Session) -> DeleteOut:
    """Right to erasure. Reports stay (legal retention) without any link to a person."""
    await limit_reporter(
        request, reporter, "me-delete", per_account=DELETE_PER_DAY, per_ip=PER_IP_PER_DAY, window_s=DAY_S
    )
    user_id = reporter.user_id
    account = await session.get(Account, user_id, with_for_update=True)
    assert account is not None
    now = datetime.now(UTC)
    details: dict[str, Any] = {"kind": account.kind.value}

    details["organizations_left"] = await _leave_organizations(session, user_id)
    # Before the profile goes: the verified phone number is what links calls and SMS to the person.
    details.update(await telephony.forget(session, user_id))
    # Phase 8: ledger and badges deleted, nominations anonymised, certificates detached (PDF removed).
    details.update(await rewards.forget(session, user_id))
    details["contact_requests_detached"] = await contact.forget(session, user_id)
    # Phase B2: personal safety rows (system scope: the alerts received and the links have other owners too) and the
    # medical files attached to the person's reports.
    async with as_system(session) as system:
        details.update(await safety.forget(system, user_id))
        details["location_points"] = await safety_history.forget(system, user_id)
        details["medical_files"] = (
            await system.execute(
                delete(MedicalAttachment).where(
                    MedicalAttachment.report_id.in_(select(Report.id).where(Report.user_id == user_id))
                )
            )
        ).rowcount  # type: ignore[attr-defined]
    details["profile"] = (await session.execute(delete(Profile).where(Profile.user_id == user_id))).rowcount > 0  # type: ignore[attr-defined]
    details["devices"] = (await session.execute(delete(Device).where(Device.user_id == user_id))).rowcount  # type: ignore[attr-defined]
    await session.execute(delete(Outbox).where(Outbox.user_id == user_id, Outbox.status == "pending"))
    volunteer = await session.get(Volunteer, user_id, with_for_update=True)
    if volunteer is not None:
        volunteer.status = "withdrawn"
        volunteer.other_skill = volunteer.notes = None
        volunteer.ready_until = None
        volunteer.version += 1
        volunteer.updated_at = now
        await get_presence().clear(user_id)
        await session.flush()
        await volunteers.announce(session, volunteer)
        details["volunteer"] = "withdrawn"
    doctor = await session.get(Doctor, user_id, with_for_update=True)
    if doctor is not None and doctor.status != "withdrawn":
        doctors.clear(doctor)
        doctor.workplace = "--"  # the row stays as a tombstone: nothing left to tell who it was
        details["doctor"] = "withdrawn"
    if account.keycloak_sub is not None:
        # No identity-provider admin credentials in the API: the account is disabled from this queue.
        session.add(ErasureRequest(keycloak_sub=account.keycloak_sub))
    details["reports_kept"] = await session.scalar(select(func.count()).where(Report.user_id == user_id))
    active = list(
        await session.scalars(
            select(LiveStream)
            .where(LiveStream.user_id == user_id, LiveStream.status.in_(ACTIVE_STREAMS))
            .with_for_update()
        )
    )
    for stream in active:
        await streams.end(session, stream, EndReason.PUBLISHER_STOPPED, now)
    details["streams_ended"] = len(active)
    await session.execute(
        update(Account)
        .where(Account.user_id == user_id)
        .values(keycloak_sub=None, anon_pseudonym=None, deleted_at=now, updated_at=now)
    )
    await audit.record(
        session, actor=reporter.actor, action="user.delete", target=f"account:{user_id}", details=details
    )
    await session.commit()
    for stream in active:
        await mediamtx.kick(stream.path)
    return DeleteOut(status="deleted")
