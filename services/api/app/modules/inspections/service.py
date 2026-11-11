"""Periodic inspections of the units, phase I1 (docs/phase-i/design-i.md).

The general inspectorate (``inspector_general``) keeps the calculation model, the general recommendations of the
mission orders and the disclosure policy; activates the inspectors' app accounts; plans the missions and prints their
orders; reads every report and decides what the rooms read of the rooms' own inspections. The inspectors carry out
their missions from the app. The rooms read only what was disclosed to them of the inspections of the operations
rooms; the inspections of the other units stay here (Yamen, 2026-11-11).
"""

import base64
import binascii
import html
import secrets
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import segno
from fastapi import HTTPException, status
from geoalchemy2 import WKTElement
from sqlalchemy import and_, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import field_tokens, sessions
from app.core.config import get_settings
from app.core.db import system_scoped
from app.core.security import Principal, Role
from app.modules.audit import service as audit
from app.modules.audit.service import actor_of, name_of
from app.modules.geo.models import Gouvernorat
from app.modules.inspections import domain, schemas
from app.modules.inspections.models import (
    Inspection,
    Inspector,
    Mission,
    MissionSite,
    OrderNote,
    Policy,
    Profile,
    Recommendation,
)
from app.modules.inventory.models import Agent
from app.modules.notify.models import Outbox
from app.modules.ops.models import Unit
from app.modules.settings import service as settings_service

TUNIS_TZ = ZoneInfo("Africa/Tunis")
SUBJECT_PREFIX = "insp:"
#: Letters and digits that cannot be mistaken for one another (the field agents' codes, phase F).
ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
REFRESH_TTL = timedelta(days=30)
SIGNATURE_MAX_BYTES = 200_000
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
CONFIRM_WORD = "حذف"
CENTRAL_ROOM = "قاعة العمليات المركزية"


def now() -> datetime:
    return datetime.now(UTC)


def today() -> date:
    return now().astimezone(TUNIS_TZ).date()


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


async def _audit(
    session: AsyncSession,
    principal: Principal | None,
    action: str,
    target: str,
    gouvernorats: Iterable[int | None] = (),
    **details: Any,
) -> None:
    await audit.record(
        session,
        actor=actor_of(principal),
        action=action,
        target=target,
        details=details or None,
        gouvernorats=sorted({g for g in gouvernorats if g is not None}) or None,
    )


# ---------------------------------------------------------------- places


async def gouvernorat_names(session: AsyncSession) -> dict[int, str]:
    return {g.code: g.name_ar for g in await session.scalars(select(Gouvernorat))}


def room_name(room: str | None, gouvernorat_code: int | None, names: dict[int, str]) -> str:
    if room == "central":
        return CENTRAL_ROOM
    return f"القاعة الجهوية للعمليات ب{names.get(gouvernorat_code or 0, '')}".strip()


UNIT_KINDS = {
    "regional_directorate": "إدارة جهوية",
    "brigade": "فرقة",
    "centre": "مركز",
    "advanced_centre": "مركز مقدّم",
    "guard_post": "نقطة حراسة",
    "beach": "شاطئ",
    "other": "وحدة",
}


def unit_place(kind: str | None, name: str | None) -> str:
    """A unit as the planner typed it: its kind, then its name (Yamen 2026-11-11)."""
    label = UNIT_KINDS.get(kind or "", "")
    name = (name or "").strip()
    return name if not label or name.startswith(label) else f"{label} {name}"


async def place_names(session: AsyncSession, rows: Sequence[MissionSite | Inspection]) -> dict[uuid.UUID, str]:
    """Display name of each site or report: the unit as typed by the planner, or the operations room."""
    names = await gouvernorat_names(session) if any(r.target == "room" for r in rows) else {}
    return {
        r.id: unit_place(r.unit_kind, r.unit_name)
        if r.target == "unit"
        else room_name(r.room, r.gouvernorat_code, names)
        for r in rows
    }


# ---------------------------------------------------------------- settings


async def active_profile(session: AsyncSession) -> Profile:
    profile = await session.scalar(select(Profile).where(Profile.active))
    if profile is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no_active_profile")
    return profile


def profile_out(profile: Profile) -> schemas.ProfileOut:
    return schemas.ProfileOut(
        id=profile.id,
        name=profile.name,
        version=profile.version,
        config=schemas.ProfileConfig.model_validate(profile.config),
        created_by_name=profile.created_by_name,
        created_at=profile.created_at,
    )


async def save_profile(session: AsyncSession, principal: Principal, body: schemas.ProfileIn) -> schemas.ProfileOut:
    """A new version of the model becomes the active one; the reports already made keep their own version."""
    config = body.config.model_dump()
    try:
        domain.check_model(config)
    except domain.InvalidModel as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.code) from exc
    current = await session.scalar(select(Profile).where(Profile.active).with_for_update())
    version = (await session.scalar(select(func.max(Profile.version))) or 0) + 1
    if current is not None:
        current.active = False
        await session.flush()
    profile = Profile(name=body.name, version=version, active=True, config=config, created_by_name=name_of(principal))
    session.add(profile)
    await session.flush()
    await _audit(session, principal, "inspection.profile", f"insp_profile:{profile.id}", version=version)
    return profile_out(profile)


async def order_notes(session: AsyncSession) -> list[str]:
    return list(await session.scalars(select(OrderNote.text).order_by(OrderNote.position)))


async def save_order_notes(session: AsyncSession, principal: Principal, notes: list[str]) -> list[str]:
    for row in await session.scalars(select(OrderNote)):
        await session.delete(row)
    await session.flush()
    for i, note in enumerate(notes, start=1):
        session.add(OrderNote(position=i, text=note))
    await session.flush()
    await _audit(session, principal, "inspection.order_notes", "insp_order_notes", count=len(notes))
    return await order_notes(session)


async def policy(session: AsyncSession) -> Policy:
    row = await session.get(Policy, 1)
    if row is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no_policy")
    return row


def policy_out(row: Policy) -> schemas.PolicyOut:
    return schemas.PolicyOut(**row.config, updated_by_name=row.updated_by_name, updated_at=row.updated_at)


async def save_policy(session: AsyncSession, principal: Principal, body: schemas.PolicyIn) -> schemas.PolicyOut:
    row = await session.get(Policy, 1, with_for_update=True)
    if row is None:
        row = Policy(id=1, config={})
        session.add(row)
    row.config = body.model_dump()
    row.updated_by_name = name_of(principal)
    row.updated_at = now()
    await session.flush()
    await _audit(session, principal, "inspection.policy", "insp_policy")
    return policy_out(row)


# ---------------------------------------------------------------- inspectors


def normalise_code(code: str) -> str:
    return "".join(c for c in code.upper() if c.isalnum())


def new_code() -> str:
    raw = "".join(secrets.choice(ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def mask_phone(phone: str) -> str:
    digits = phone.replace(" ", "")
    return f"{digits[:4]} •• ••• {digits[-3:]}" if len(digits) > 7 else "•••"


def mask_email(email: str) -> str:
    local, _, host = email.partition("@")
    return f"{local[:1]}•••@{host.lower()}"


def destination(inspector: Inspector) -> str:
    if inspector.via == "sms":
        return mask_phone(inspector.phone or "")
    return mask_email(inspector.email or "")


def inspector_out(inspector: Inspector) -> schemas.InspectorOut:
    return schemas.InspectorOut(
        id=inspector.id,
        kind=inspector.kind,
        matricule=inspector.matricule,
        name=inspector.name,
        organisation=inspector.organisation,
        phone=inspector.phone,
        email=inspector.email,
        via=inspector.via,
        status=inspector.status,
        expires_on=inspector.expires_on,
        matched_agent=inspector.agent_id is not None,
        requested_device=inspector.requested_device,
        requested_at=inspector.requested_at,
        decided_at=inspector.decided_at,
        decided_by_name=inspector.decided_by_name,
        reject_reason=inspector.reject_reason,
        code_expires_at=inspector.code_expires_at if inspector.code_hash else None,
        activated_at=inspector.activated_at,
        device_model=inspector.device_model,
        last_seen_at=inspector.last_seen_at,
        lost_at=inspector.lost_at,
    )


@system_scoped
async def register(session: AsyncSession, body: schemas.RegisterIn) -> schemas.RegisterOut:
    """A registration from the app (no account yet). Runs as the system: the caller is anonymous."""
    if body.via == "sms" and not body.phone:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "phone_required")
    if body.via == "email" and not body.email:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "email_required")
    if body.kind == "external" and not body.organisation:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "organisation_required")
    taken = await session.scalar(
        select(Inspector.id).where(
            func.lower(Inspector.matricule) == body.matricule.lower(),
            Inspector.status.not_in(("rejected", "closed")),
        )
    )
    if taken is not None:
        # The same answer as a new registration would leak who already has an account; a conflict is enough here
        # because the professional number is not a secret and the inspector general sees every request.
        raise HTTPException(status.HTTP_409_CONFLICT, "already_registered")
    agent_id = await session.scalar(select(Agent.id).where(func.lower(Agent.matricule) == body.matricule.lower()))
    inspector = Inspector(
        kind=body.kind,
        matricule=body.matricule,
        name=body.name,
        organisation=body.organisation if body.kind == "external" else None,
        phone=body.phone,
        email=str(body.email) if body.email else None,
        via=body.via,
        agent_id=agent_id,
        requested_device=body.device_model,
    )
    session.add(inspector)
    await session.flush()
    await audit.record(
        session, actor=f"insp-app:{inspector.id}", action="inspector.register", target=f"inspector:{inspector.id}"
    )
    return schemas.RegisterOut(status="pending", destination=destination(inspector))


async def inspectors(session: AsyncSession, state: str | None) -> list[schemas.InspectorOut]:
    order = {"pending": 0, "code_sent": 1, "active": 2, "blocked": 3, "rejected": 4, "closed": 5}
    query = select(Inspector)
    if state:
        query = query.where(Inspector.status == state)
    rows = sorted(await session.scalars(query), key=lambda i: (order.get(i.status, 9), i.name))
    return [inspector_out(i) for i in rows]


async def _inspector(session: AsyncSession, inspector_id: uuid.UUID) -> Inspector:
    inspector = await session.get(Inspector, inspector_id, with_for_update=True)
    if inspector is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return inspector


async def _send_code(session: AsyncSession, inspector: Inspector) -> None:
    """A fresh one-time code by SMS or e-mail; the platform keeps only its fingerprint. The outbox row is marked
    secret: its text is wiped once sent."""
    hours = await settings_service.threshold(session, "field.code_hours")
    code = new_code()
    inspector.code_hash = field_tokens.fingerprint(normalise_code(code))
    inspector.code_expires_at = now() + timedelta(hours=hours)
    inspector.code_attempts = 0
    message = f"ء-حماية: رمز تفعيل حسابك في تطبيق التفقّد {code}. صالح {hours} ساعة ولمرّة واحدة. لا تشاركه مع أحد."
    if inspector.via == "sms":
        session.add(Outbox(channel="sms", address=inspector.phone, payload={"text": message, "secret": True}))
    else:
        session.add(
            Outbox(
                channel="email",
                address=inspector.email,
                payload={"subject": "ء-حماية: رمز تفعيل تطبيق التفقّد", "text": message, "secret": True},
            )
        )


async def activate_account(
    session: AsyncSession, principal: Principal, inspector_id: uuid.UUID, body: schemas.ActivateIn
) -> schemas.InspectorOut:
    inspector = await _inspector(session, inspector_id)
    if inspector.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "not_pending")
    if inspector.kind == "external":
        if body.expires_on is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "expires_on_required")
        if body.expires_on < today():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "expires_on_past")
        inspector.expires_on = body.expires_on
    inspector.status = "code_sent"
    inspector.decided_at = now()
    inspector.decided_by_name = name_of(principal)
    await _send_code(session, inspector)
    inspector.version += 1
    await _audit(session, principal, "inspector.activate", f"inspector:{inspector.id}", via=inspector.via)
    return inspector_out(inspector)


async def reject_account(
    session: AsyncSession, principal: Principal, inspector_id: uuid.UUID, reason: str
) -> schemas.InspectorOut:
    inspector = await _inspector(session, inspector_id)
    if inspector.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "not_pending")
    inspector.status = "rejected"
    inspector.reject_reason = reason
    inspector.decided_at = now()
    inspector.decided_by_name = name_of(principal)
    await _audit(session, principal, "inspector.reject", f"inspector:{inspector.id}")
    return inspector_out(inspector)


async def renew_code(session: AsyncSession, principal: Principal, inspector_id: uuid.UUID) -> schemas.InspectorOut:
    """A new code: never received, or a new phone (the old phone keeps working until the new one is activated, unless
    it was reported lost)."""
    inspector = await _inspector(session, inspector_id)
    if inspector.status not in ("code_sent", "active", "blocked"):
        raise HTTPException(status.HTTP_409_CONFLICT, "not_renewable")
    await _send_code(session, inspector)
    if inspector.status == "blocked":
        inspector.status = "code_sent"
    await _audit(session, principal, "inspector.code", f"inspector:{inspector.id}", via=inspector.via)
    return inspector_out(inspector)


async def _end_sessions(inspector: Inspector) -> None:
    await sessions.revoke(subject_of(inspector))


async def report_lost(session: AsyncSession, principal: Principal, inspector_id: uuid.UUID) -> schemas.InspectorOut:
    inspector = await _inspector(session, inspector_id)
    if inspector.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "not_active")
    inspector.status = "blocked"
    inspector.lost_at = now()
    inspector.refresh_hash = None
    inspector.refresh_expires_at = None
    inspector.push_token = None
    await _end_sessions(inspector)
    await _audit(session, principal, "inspector.lost", f"inspector:{inspector.id}", device=inspector.device_model)
    return inspector_out(inspector)


async def close_account(session: AsyncSession, principal: Principal, inspector_id: uuid.UUID) -> schemas.InspectorOut:
    inspector = await _inspector(session, inspector_id)
    if inspector.status in ("rejected", "closed"):
        raise HTTPException(status.HTTP_409_CONFLICT, "already_closed")
    _close(inspector)
    await _end_sessions(inspector)
    await _audit(session, principal, "inspector.close", f"inspector:{inspector.id}")
    return inspector_out(inspector)


def _close(inspector: Inspector) -> None:
    inspector.status = "closed"
    inspector.closed_at = now()
    inspector.code_hash = None
    inspector.code_expires_at = None
    inspector.refresh_hash = None
    inspector.refresh_expires_at = None
    inspector.push_token = None


def subject_of(inspector: Inspector) -> str:
    return f"{SUBJECT_PREFIX}{inspector.id}"


def _role_of(inspector: Inspector) -> Role:
    return Role.INSPECTOR_EXTERNAL if inspector.kind == "external" else Role.INSPECTOR


def _tokens(inspector: Inspector) -> schemas.AppTokens:
    refresh = field_tokens.new_refresh()
    inspector.refresh_hash = field_tokens.fingerprint(refresh)
    inspector.refresh_expires_at = now() + REFRESH_TTL
    inspector.last_seen_at = now()
    access, expires = field_tokens.issue(
        subject=subject_of(inspector),
        name=inspector.name,
        username=inspector.matricule,
        roles=[_role_of(inspector).value],
        gouvernorat_code=None,
        device_id=str(inspector.id),
    )
    return schemas.AppTokens(
        access_token=access,
        expires_at=expires,
        refresh_token=refresh,
        name=inspector.name,
        kind=inspector.kind,
        expires_on=inspector.expires_on,
    )


def _expired(inspector: Inspector) -> bool:
    return inspector.kind == "external" and inspector.expires_on is not None and inspector.expires_on < today()


@system_scoped
async def app_activate(session: AsyncSession, body: schemas.AppActivateIn) -> schemas.AppTokens:
    """The phone activates the account with the code and the professional number (runs as the system)."""
    inspector = await session.scalar(
        select(Inspector)
        .where(Inspector.code_hash == field_tokens.fingerprint(normalise_code(body.code)))
        .with_for_update()
    )
    if inspector is None or inspector.matricule.lower() != body.matricule.lower():
        await _refuse(session, inspector, body.matricule)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "activation_refused")
    if inspector.code_expires_at is None or inspector.code_expires_at < now():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "activation_expired")
    if _expired(inspector):
        _close(inspector)
        raise HTTPException(status.HTTP_410_GONE, "account_expired")
    previous = inspector.device_model if inspector.activated_at else None
    inspector.status = "active"
    inspector.code_hash = None
    inspector.code_expires_at = None
    inspector.code_attempts = 0
    inspector.activated_at = now()
    inspector.lost_at = None
    inspector.device_model = body.device.model
    inspector.device_platform = body.device.platform
    inspector.device_ref = body.device.device_ref
    inspector.push_token = body.device.push_token
    if previous is not None:
        # One phone per account: the previous phone's session ends.
        await _end_sessions(inspector)
    out = _tokens(inspector)
    await audit.record(
        session,
        actor=f"staff:{subject_of(inspector)}",
        action="inspector.app_activate",
        target=f"inspector:{inspector.id}",
        details={"platform": body.device.platform, "model": body.device.model},
    )
    return out


async def _refuse(session: AsyncSession, inspector: Inspector | None, matricule: str) -> None:
    """Count a wrong try against the account the professional number names; the code dies at the limit."""
    limit = await settings_service.threshold(session, "field.code_attempts")
    targets = (
        [inspector]
        if inspector is not None
        else list(
            await session.scalars(
                select(Inspector).where(
                    func.lower(Inspector.matricule) == matricule.lower(), Inspector.code_hash.is_not(None)
                )
            )
        )
    )
    for target in targets:
        target.code_attempts += 1
        if target.code_attempts >= limit:
            target.code_hash = None
            target.code_expires_at = None
    await session.commit()


@system_scoped
async def app_refresh(session: AsyncSession, body: schemas.AppRefreshIn) -> schemas.AppTokens:
    inspector = await session.scalar(
        select(Inspector)
        .where(Inspector.refresh_hash == field_tokens.fingerprint(body.refresh_token))
        .with_for_update()
    )
    if inspector is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh_refused")
    if inspector.status != "active":
        raise HTTPException(status.HTTP_410_GONE, "device_revoked")
    if _expired(inspector):
        _close(inspector)
        await session.commit()
        raise HTTPException(status.HTTP_410_GONE, "account_expired")
    if inspector.refresh_expires_at is None or inspector.refresh_expires_at < now():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh_expired")
    return _tokens(inspector)


async def me(session: AsyncSession, principal: Principal) -> Inspector:
    """The inspector behind an app token; refused once the account is no longer active or has expired."""
    if not principal.subject.startswith(SUBJECT_PREFIX):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "inspector_only")
    try:
        inspector_id = uuid.UUID(principal.subject.removeprefix(SUBJECT_PREFIX))
    except ValueError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "inspector_only") from exc
    inspector = await session.get(Inspector, inspector_id)
    if inspector is None or inspector.status != "active" or _expired(inspector):
        raise HTTPException(status.HTTP_410_GONE, "account_inactive")
    return inspector


# ---------------------------------------------------------------- missions


async def _sites_of(session: AsyncSession, mission_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[MissionSite]]:
    out: dict[uuid.UUID, list[MissionSite]] = {m: [] for m in mission_ids}
    if not mission_ids:
        return out
    for site in await session.scalars(
        select(MissionSite).where(MissionSite.mission_id.in_(mission_ids)).order_by(MissionSite.position)
    ):
        out[site.mission_id].append(site)
    return out


async def _reports_of(session: AsyncSession, site_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Inspection]:
    if not site_ids:
        return {}
    rows = await session.scalars(
        select(Inspection).where(Inspection.site_id.in_(site_ids), Inspection.deleted_at.is_(None))
    )
    return {r.site_id: r for r in rows}


def mission_state(mission: Mission, sites: list[MissionSite], reports: dict[uuid.UUID, Inspection]) -> str:
    if mission.status == "cancelled":
        return "cancelled"
    done = [reports.get(s.id) for s in sites]
    if done and all(r is not None and r.status == "submitted" for r in done):
        return "done"
    return "live" if any(r is not None for r in done) else "planned"


async def missions_out(session: AsyncSession, missions: Sequence[Mission]) -> list[schemas.MissionOut]:
    sites = await _sites_of(session, [m.id for m in missions])
    flat = [s for group in sites.values() for s in group]
    reports = await _reports_of(session, [s.id for s in flat])
    names = await place_names(session, flat)
    inspector_names = {
        i.id: i.name
        for i in await session.scalars(select(Inspector).where(Inspector.id.in_({m.inspector_id for m in missions})))
    }
    out = []
    for m in missions:
        group = sites[m.id]
        out.append(
            schemas.MissionOut(
                id=m.id,
                ref=m.ref,
                on_date=m.on_date,
                at_time=m.at_time,
                kind=m.kind,
                inspector_id=m.inspector_id,
                inspector_name=inspector_names.get(m.inspector_id, ""),
                status=mission_state(m, group, reports),
                cancel_reason=m.cancel_reason,
                published=m.published,
                sites=[_site_out(s, names[s.id], reports.get(s.id)) for s in group],
                created_by_name=m.created_by_name,
                created_at=m.created_at,
            )
        )
    return out


def _site_out(site: MissionSite, name: str, report: Inspection | None) -> schemas.SiteOut:
    return schemas.SiteOut(
        id=site.id,
        position=site.position,
        target=site.target,
        unit_kind=site.unit_kind,
        unit_name=site.unit_name,
        unit_id=site.unit_id,
        room=site.room,
        name=name,
        gouvernorat_code=site.gouvernorat_code,
        sections=list(site.sections or []),
        inspection_id=report.id if report else None,
        inspection_status=report.status if report else None,
    )


async def list_missions(
    session: AsyncSession, from_date: date | None, to_date: date | None, inspector_id: uuid.UUID | None
) -> list[schemas.MissionOut]:
    query = select(Mission).order_by(Mission.on_date.desc(), Mission.at_time.desc())
    if from_date:
        query = query.where(Mission.on_date >= from_date)
    if to_date:
        query = query.where(Mission.on_date <= to_date)
    if inspector_id:
        query = query.where(Mission.inspector_id == inspector_id)
    return await missions_out(session, list(await session.scalars(query.limit(500))))


async def create_mission(session: AsyncSession, principal: Principal, body: schemas.MissionIn) -> schemas.MissionOut:
    inspector = await session.get(Inspector, body.inspector_id)
    if inspector is None or inspector.status != "active":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "inspector_not_active")
    if body.on_date < today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "date_past")
    if inspector.kind == "external" and inspector.expires_on is not None and body.on_date > inspector.expires_on:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "after_account_end")
    places: list[MissionSite] = []
    seen: set[str] = set()
    for site in body.sites:
        if site.target == "unit":
            if site.gouvernorat_code is None or await session.get(Gouvernorat, site.gouvernorat_code) is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "gouvernorat_required")
            if site.unit_kind is None or not site.unit_name:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unit_required")
            if site.unit_id is not None:
                unit = await session.get(Unit, site.unit_id)
                if unit is None or unit.gouvernorat_code != site.gouvernorat_code:
                    raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unit_not_found")
            key = f"u:{site.gouvernorat_code}:{site.unit_kind}:{site.unit_name.casefold()}"
            places.append(
                MissionSite(
                    target="unit",
                    unit_kind=site.unit_kind,
                    unit_name=site.unit_name,
                    unit_id=site.unit_id,
                    gouvernorat_code=site.gouvernorat_code,
                    sections=site.sections,
                )
            )
        else:
            if site.room is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "room_required")
            gouvernorat = None
            if site.room == "regional":
                if site.gouvernorat_code is None or await session.get(Gouvernorat, site.gouvernorat_code) is None:
                    raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "gouvernorat_required")
                gouvernorat = site.gouvernorat_code
            key = f"r:{site.room}:{gouvernorat}"
            places.append(
                MissionSite(target="room", room=site.room, gouvernorat_code=gouvernorat, sections=site.sections)
            )
        if key in seen:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "duplicate_site")
        seen.add(key)
    seq = int(await session.scalar(text("SELECT nextval('insp.mission_seq')")) or 0)
    mission = Mission(
        ref=f"OM-{body.on_date.year}-{seq:04d}",
        on_date=body.on_date,
        at_time=body.at_time,
        kind=body.kind,
        inspector_id=inspector.id,
        published=body.publish,
        created_by=actor_of(principal),
        created_by_name=name_of(principal),
    )
    session.add(mission)
    await session.flush()
    for i, place in enumerate(places, start=1):
        place.mission_id = mission.id
        place.position = i
        session.add(place)
    await session.flush()
    await _audit(
        session,
        principal,
        "inspection.mission",
        f"insp_mission:{mission.id}",
        [p.gouvernorat_code for p in places],
        ref=mission.ref,
        places=len(places),
    )
    return (await missions_out(session, [mission]))[0]


async def cancel_mission(
    session: AsyncSession, principal: Principal, mission_id: uuid.UUID, reason: str
) -> schemas.MissionOut:
    mission = await session.get(Mission, mission_id, with_for_update=True)
    if mission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if mission.status == "cancelled":
        raise HTTPException(status.HTTP_409_CONFLICT, "already_cancelled")
    started = await session.scalar(
        select(func.count()).select_from(Inspection).where(Inspection.mission_id == mission.id)
    )
    if started:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_started")
    mission.status = "cancelled"
    mission.cancel_reason = reason
    await _audit(session, principal, "inspection.mission_cancel", f"insp_mission:{mission.id}", ref=mission.ref)
    return (await missions_out(session, [mission]))[0]


def order_verify_url(ref: str) -> str:
    return f"{get_settings().portal_public_url}/verify/om/{ref}"


async def order_html(session: AsyncSession, mission: Mission, signer: str | None) -> str:
    """The mission order, A4 (design-i §5): header, reference, the inspector, the place or places, the general
    recommendations, the inspector general's signature, and the QR code at the foot of the page."""
    sites = (await _sites_of(session, [mission.id]))[mission.id]
    names = await place_names(session, sites)
    gnames = await gouvernorat_names(session)
    inspector = await session.get(Inspector, mission.inspector_id)
    notes = await order_notes(session)
    e = html.escape
    qr = segno.make(order_verify_url(mission.ref), error="m").svg_data_uri(scale=4, border=1)
    kind = "تفقّد دوري" if mission.kind == "periodic" else "تفقّد فجئي"
    rows = "".join(
        f"<tr><td class='n'>{s.position}</td><td><b>{e(names[s.id])}</b></td>"
        f"<td>{e(gnames.get(s.gouvernorat_code or 0, '—') if s.gouvernorat_code else '—')}</td>"
        f"<td>{e('، '.join(s.sections) if s.sections else 'كل الأقسام')}</td></tr>"
        for s in sites
    )
    who = e(inspector.name if inspector else "")
    if inspector is not None and inspector.kind == "external":
        who += f" <span class='muted'>({e(inspector.organisation or '')} · متفقّد خارجي)</span>"
    plural = "المكان" if len(sites) == 1 else f"الأمكنة ({len(sites)})"
    note_items = "".join(f"<li>{e(n)}</li>" for n in notes)
    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><style>
@page {{ size: A4; margin: 18mm 18mm 22mm; }}
body {{ font-family: 'Noto Naskh Arabic', 'Noto Sans Arabic', sans-serif; font-size: 12pt; color: #111; }}
.hd {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #1F3FA0;
       padding-bottom: 8px; }}
.hd .l {{ line-height: 1.6; font-weight: 700; }}
.meta {{ display: flex; justify-content: space-between; margin: 10px 0 4px; font-size: 11pt; }}
h1 {{ text-align: center; font-size: 22pt; margin: 18px 0 14px; letter-spacing: 1px; }}
table {{ width: 100%; border-collapse: collapse; margin: 6px 0 14px; }}
td, th {{ border: 1px solid #999; padding: 6px 8px; vertical-align: top; text-align: right; }}
th {{ background: #EEF1FA; }}
td.k {{ width: 30%; background: #F6F7FB; font-weight: 700; }}
td.n {{ width: 6%; text-align: center; }}
h2 {{ font-size: 13pt; margin: 14px 0 6px; }}
ol {{ margin: 0 0 10px; padding-inline-start: 22px; line-height: 1.7; }}
.sig {{ margin-top: 26px; display: flex; justify-content: space-between; align-items: flex-end; }}
.sig .who {{ text-align: center; width: 55%; line-height: 1.7; }}
.qr {{ text-align: center; font-size: 9pt; color: #444; }}
.qr img {{ width: 34mm; height: 34mm; }}
.muted {{ color: #555; font-weight: 400; }}
</style></head><body>
<div class="hd"><div class="l">الجمهورية التونسية<br>وزارة الداخلية<br>الديوان الوطني للحماية المدنية
<br>التفقّدية العامة</div>
<div class="l" style="text-align:left">République Tunisienne<br>Ministère de l'Intérieur
<br>Office National de la Protection Civile<br>Inspection Générale</div></div>
<div class="meta"><span>المرجع: <b dir="ltr">{e(mission.ref)}</b></span>
<span>تونس في {e(_fd(mission.created_at))}</span></div>
<h1>أمر مهمة</h1>
<table>
<tr><td class="k">التاريخ</td><td>{e(_fd_date(mission.on_date))}</td></tr>
<tr><td class="k">التوقيت</td><td dir="ltr" style="text-align:right">{mission.at_time.strftime("%H:%M")}</td></tr>
<tr><td class="k">نوع المهمة</td><td>{kind}</td></tr>
<tr><td class="k">المكلَّف بالمهمة</td><td>{who}</td></tr>
</table>
<h2>{plural}</h2>
<table><tr><th>#</th><th>المقرّ</th><th>الولاية</th><th>الأقسام</th></tr>{rows}</table>
<h2>توصيات عامة</h2><ol>{note_items}</ol>
<div class="sig"><div class="qr"><img src="{qr}" alt=""><div>للتحقّق من صحّة الأمر</div>
<div dir="ltr">{e(mission.ref)}</div></div>
<div class="who">المتفقّد العام للديوان الوطني للحماية المدنية<br><b>{e(signer or "")}</b><br><br>
<span class="muted">الإمضاء والختم</span></div></div>
<p class="muted" style="font-size:9pt;margin-top:18px">وثيقة صادرة عن منظومة ء-حماية.
يُتحقَّق من صحّتها بمسح الرمز.</p>
</body></html>"""


_MONTHS = ("جانفي", "فيفري", "مارس", "أفريل", "ماي", "جوان", "جويلية", "أوت", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر")


def _fd_date(d: date) -> str:
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"


def _fd(at: datetime) -> str:
    return _fd_date(at.astimezone(TUNIS_TZ).date())


@system_scoped
async def verify_order(session: AsyncSession, ref: str) -> schemas.OrderVerifyOut:
    mission = await session.scalar(select(Mission).where(Mission.ref == ref))
    if mission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    inspector = await session.get(Inspector, mission.inspector_id)
    places = await session.scalar(
        select(func.count()).select_from(MissionSite).where(MissionSite.mission_id == mission.id)
    )
    return schemas.OrderVerifyOut(
        ref=mission.ref,
        on_date=mission.on_date,
        inspector_name=inspector.name if inspector else "",
        places=int(places or 0),
        valid=mission.status != "cancelled",
    )


# ---------------------------------------------------------------- the inspector's app


async def my_missions(session: AsyncSession, inspector: Inspector) -> list[schemas.AppMissionOut]:
    rows = list(
        await session.scalars(
            select(Mission)
            .where(
                Mission.inspector_id == inspector.id,
                Mission.status == "planned",
                Mission.on_date >= today() - timedelta(days=1),
            )
            .order_by(Mission.on_date, Mission.at_time)
        )
    )
    full = await missions_out(session, rows)
    return [
        schemas.AppMissionOut(id=m.id, ref=m.ref, on_date=m.on_date, at_time=m.at_time, kind=m.kind, sites=m.sites)
        for m in full
        if m.status != "done"
    ]


def app_inspection_out(report: Inspection) -> schemas.AppInspectionOut:
    return schemas.AppInspectionOut(
        id=report.id,
        site_id=report.site_id,
        status=report.status,
        profile=schemas.ProfileConfig.model_validate(report.profile),
        answers=report.answers,
        present=report.present,
        expected=report.expected,
        exit_seconds=report.exit_seconds,
        score=report.score,
        verdict=report.verdict,
        receipt=report.receipt,
    )


async def start(session: AsyncSession, inspector: Inspector, body: schemas.StartIn) -> schemas.AppInspectionOut:
    site = await session.get(MissionSite, body.site_id)
    mission = await session.get(Mission, site.mission_id) if site else None
    if site is None or mission is None or mission.inspector_id != inspector.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if mission.status == "cancelled":
        raise HTTPException(status.HTTP_409_CONFLICT, "mission_cancelled")
    existing = await session.scalar(select(Inspection).where(Inspection.site_id == site.id))
    if existing is not None:
        if existing.deleted_at is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "inspection_deleted")
        return app_inspection_out(existing)
    if mission.on_date > today():
        raise HTTPException(status.HTTP_409_CONFLICT, "mission_not_today")
    profile = await active_profile(session)
    report = Inspection(
        mission_id=mission.id,
        site_id=site.id,
        target=site.target,
        unit_kind=site.unit_kind,
        unit_name=site.unit_name,
        unit_id=site.unit_id,
        room=site.room,
        gouvernorat_code=site.gouvernorat_code,
        inspector_id=inspector.id,
        kind=mission.kind,
        profile_id=profile.id,
        profile=profile.config | {"name": profile.name, "version": profile.version},
        started_at=min(body.started_at or now(), now()),
        location=WKTElement(f"POINT({body.lon} {body.lat})", srid=4326)
        if body.lat is not None and body.lon is not None
        else None,
        answers={},
    )
    session.add(report)
    await session.flush()
    await audit.record(
        session,
        actor=f"staff:{subject_of(inspector)}",
        action="inspection.start",
        target=f"inspection:{report.id}",
        details={"mission": mission.ref},
        gouvernorats=[site.gouvernorat_code] if site.gouvernorat_code else None,
    )
    return app_inspection_out(report)


async def _own_report(session: AsyncSession, inspector: Inspector, inspection_id: uuid.UUID) -> Inspection:
    report = await session.get(Inspection, inspection_id, with_for_update=True)
    if report is None or report.inspector_id != inspector.id or report.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return report


def _apply_progress(report: Inspection, body: schemas.ProgressIn) -> None:
    keys = {i["key"] for i in report.profile["items"]}
    unknown = set(body.answers) - keys
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown_item")
    if body.answers:
        report.answers = {**report.answers, **body.answers}
    if body.present is not None:
        report.present = body.present
    if body.expected is not None:
        report.expected = body.expected
    if body.exit_seconds is not None:
        report.exit_seconds = body.exit_seconds
    value = domain.score(report.profile, report.answers, report.present, report.expected, report.exit_seconds)
    report.score = value
    report.verdict = domain.verdict(report.profile, value) if value is not None else None
    report.updated_at = now()


async def progress(
    session: AsyncSession, inspector: Inspector, inspection_id: uuid.UUID, body: schemas.ProgressIn
) -> schemas.AppInspectionOut:
    report = await _own_report(session, inspector, inspection_id)
    if report.status != "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "inspection_sealed")
    _apply_progress(report, body)
    return app_inspection_out(report)


def _png(value: str) -> bytes:
    data = value.split(",", 1)[1] if value.startswith("data:") else value
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "signature_invalid") from exc
    if not raw.startswith(PNG_MAGIC) or len(raw) > SIGNATURE_MAX_BYTES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "signature_invalid")
    return raw


async def submit(
    session: AsyncSession, inspector: Inspector, inspection_id: uuid.UUID, body: schemas.SubmitIn
) -> schemas.ReceiptOut:
    """Seal the report: answers, recommendations, the two signatures, the signing time (the app may send it later,
    from its queue). The same ``client_id`` twice returns the same receipt."""
    report = await _own_report(session, inspector, inspection_id)
    if report.status == "submitted":
        if report.client_id == body.client_id:
            return _receipt(report)
        raise HTTPException(status.HTTP_409_CONFLICT, "inspection_sealed")
    _apply_progress(report, body)
    if not report.answers:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "no_answers")
    signed_at = body.signed_at if body.signed_at.tzinfo else body.signed_at.replace(tzinfo=UTC)
    if signed_at > now() + timedelta(minutes=5) or signed_at < report.started_at - timedelta(minutes=5):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "signed_at_invalid")
    for rec in body.recommendations:
        if rec.kind == "detailed" and rec.priority is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "priority_required")
    rules = (await policy(session)).config
    is_room = report.target == "room"
    for i, rec in enumerate(body.recommendations, start=1):
        priority = rec.priority if rec.kind == "detailed" else None
        to_central, to_regional = (
            domain.audience_flags(domain.recommendation_audience(rules, rec.kind, priority))
            if is_room
            else (False, False)
        )
        session.add(
            Recommendation(
                inspection_id=report.id,
                gouvernorat_code=report.gouvernorat_code,
                position=i,
                kind=rec.kind,
                item_key=rec.item_key,
                text=rec.text,
                priority=priority,
                to_central=to_central,
                to_regional=to_regional,
            )
        )
    seq = int(await session.scalar(text("SELECT nextval('insp.receipt_seq')")) or 0)
    received = now()
    report.summary = body.summary
    report.head_name = body.head_name
    report.inspector_sig = _png(body.inspector_signature)
    report.head_sig = _png(body.head_signature)
    report.signed_at = signed_at
    report.submitted_at = received
    report.client_id = body.client_id
    report.receipt = f"T-{received.astimezone(TUNIS_TZ):%Y%m%d}-{seq:02d}"
    report.disclosure = domain.disclosure_of(rules) if is_room else {}
    if report.score is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "no_answers")
    report.status = "submitted"
    await session.flush()
    await audit.record(
        session,
        actor=f"staff:{subject_of(inspector)}",
        action="inspection.submit",
        target=f"inspection:{report.id}",
        details={"receipt": report.receipt, "score": report.score},
        gouvernorats=[report.gouvernorat_code] if report.gouvernorat_code else None,
    )
    return _receipt(report)


def _receipt(report: Inspection) -> schemas.ReceiptOut:
    assert report.receipt is not None and report.score is not None and report.submitted_at is not None
    return schemas.ReceiptOut(
        inspection_id=report.id,
        receipt=report.receipt,
        score=report.score,
        verdict=report.verdict or "",
        received_at=report.submitted_at,
    )


# ---------------------------------------------------------------- records (inspector general)


async def _previous_scores(session: AsyncSession, reports: Sequence[Inspection]) -> dict[uuid.UUID, int | None]:
    """The score of the previous sent report of the same place, for each report."""
    out: dict[uuid.UUID, int | None] = {}
    for report in reports:
        if report.submitted_at is None:
            out[report.id] = None
            continue
        same = (
            and_(
                Inspection.target == "unit",
                Inspection.gouvernorat_code == report.gouvernorat_code,
                Inspection.unit_kind == report.unit_kind,
                func.lower(func.btrim(Inspection.unit_name)) == (report.unit_name or "").strip().lower(),
            )
            if report.target == "unit"
            else and_(
                Inspection.room == report.room,
                Inspection.gouvernorat_code.is_(None)
                if report.gouvernorat_code is None
                else Inspection.gouvernorat_code == report.gouvernorat_code,
            )
        )
        out[report.id] = await session.scalar(
            select(Inspection.score)
            .where(
                same,
                Inspection.status == "submitted",
                Inspection.deleted_at.is_(None),
                Inspection.submitted_at < report.submitted_at,
            )
            .order_by(Inspection.submitted_at.desc())
            .limit(1)
        )
    return out


async def records(
    session: AsyncSession,
    *,
    gouvernorat_code: int | None,
    target: str | None,
    kind: str | None,
    inspector_id: uuid.UUID | None,
    unit_kind: str | None,
    search: str | None,
    from_date: date | None,
    to_date: date | None,
    verdict: str | None,
) -> list[schemas.RecordRow]:
    query = select(Inspection).where(Inspection.deleted_at.is_(None))
    if gouvernorat_code is not None:
        query = query.where(Inspection.gouvernorat_code == gouvernorat_code)
    if target:
        query = query.where(Inspection.target == target)
    if kind:
        query = query.where(Inspection.kind == kind)
    if inspector_id:
        query = query.where(Inspection.inspector_id == inspector_id)
    if unit_kind:
        query = query.where(Inspection.unit_kind == unit_kind)
    if search:
        pattern = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(Inspection.unit_name.ilike(pattern))
    if from_date:
        query = query.where(Inspection.started_at >= datetime.combine(from_date, datetime.min.time(), TUNIS_TZ))
    if to_date:
        query = query.where(
            Inspection.started_at < datetime.combine(to_date + timedelta(days=1), datetime.min.time(), TUNIS_TZ)
        )
    if verdict:
        query = query.where(Inspection.verdict == verdict)
    rows = list(await session.scalars(query.order_by(Inspection.started_at.desc()).limit(2000)))
    return await _rows(session, rows)


async def _rows(session: AsyncSession, rows: Sequence[Inspection]) -> list[schemas.RecordRow]:
    names = await place_names(session, rows)
    previous = await _previous_scores(session, rows)
    missions = {
        m.id: m.ref for m in await session.scalars(select(Mission).where(Mission.id.in_({r.mission_id for r in rows})))
    }
    inspectors = {
        i.id: i.name
        for i in await session.scalars(select(Inspector).where(Inspector.id.in_({r.inspector_id for r in rows})))
    }
    return [
        schemas.RecordRow(
            id=r.id,
            mission_ref=missions.get(r.mission_id, ""),
            kind=r.kind,
            target=r.target,
            unit_kind=r.unit_kind,
            room=r.room,
            place=names[r.id],
            gouvernorat_code=r.gouvernorat_code,
            inspector_name=inspectors.get(r.inspector_id, ""),
            status=r.status,
            started_at=r.started_at,
            submitted_at=r.submitted_at,
            score=r.score,
            verdict=r.verdict,
            previous_score=previous.get(r.id),
            receipt=r.receipt,
        )
        for r in rows
    ]


def recommendation_out(rec: Recommendation) -> schemas.RecommendationOut:
    return schemas.RecommendationOut(
        id=rec.id,
        kind=rec.kind,
        item_key=rec.item_key,
        text=rec.text,
        priority=rec.priority,
        audience=domain.audience_of(rec.to_central, rec.to_regional),
    )


async def _report(session: AsyncSession, inspection_id: uuid.UUID, *, lock: bool = False) -> Inspection:
    report = await session.get(Inspection, inspection_id, with_for_update=lock)
    if report is None or report.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return report


async def record(session: AsyncSession, inspection_id: uuid.UUID) -> schemas.RecordOut:
    report = await _report(session, inspection_id)
    row = (await _rows(session, [report]))[0]
    recs = await session.scalars(
        select(Recommendation).where(Recommendation.inspection_id == report.id).order_by(Recommendation.position)
    )
    return schemas.RecordOut(
        **row.model_dump(),
        answers=report.answers,
        present=report.present,
        expected=report.expected,
        exit_seconds=report.exit_seconds,
        summary=report.summary,
        head_name=report.head_name,
        signed_at=report.signed_at,
        profile_name=str(report.profile.get("name", "")),
        profile_version=int(report.profile.get("version", 0)),
        disclosure={k: schemas.RoomDisclosure(**v) for k, v in (report.disclosure or {}).items()},
        recommendations=[recommendation_out(r) for r in recs],
    )


async def _room_report(session: AsyncSession, inspection_id: uuid.UUID) -> Inspection:
    report = await _report(session, inspection_id, lock=True)
    if report.target != "room":
        # Yamen 2026-11-11: what the rooms read of the inspections is what was done in the rooms.
        raise HTTPException(status.HTTP_409_CONFLICT, "not_a_room")
    if report.status != "submitted":
        raise HTTPException(status.HTTP_409_CONFLICT, "not_submitted")
    return report


async def set_disclosure(
    session: AsyncSession, principal: Principal, inspection_id: uuid.UUID, body: schemas.DisclosureIn
) -> schemas.RecordOut:
    report = await _room_report(session, inspection_id)
    current = {k: dict(v) for k, v in (report.disclosure or {}).items()}
    room = current.setdefault(body.room, {"inspection": False, "verdict": False, "score": False})
    for field in domain.DISCLOSED_FIELDS:
        value = getattr(body, field)
        if value is not None:
            room[field] = value
    report.disclosure = current
    report.updated_at = now()
    await _audit(
        session,
        principal,
        "inspection.disclosure",
        f"inspection:{report.id}",
        [report.gouvernorat_code],
        room=body.room,
        **{f: room[f] for f in domain.DISCLOSED_FIELDS},
    )
    return await record(session, report.id)


async def set_audience(
    session: AsyncSession, principal: Principal, inspection_id: uuid.UUID, body: schemas.AudienceIn
) -> schemas.RecordOut:
    report = await _room_report(session, inspection_id)
    to_central, to_regional = domain.audience_flags(body.audience)
    result = await session.execute(
        update(Recommendation)
        .where(Recommendation.inspection_id == report.id, Recommendation.id.in_(body.ids))
        .values(to_central=to_central, to_regional=to_regional)
    )
    if result.rowcount != len(set(body.ids)):  # type: ignore[attr-defined]
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await _audit(
        session,
        principal,
        "inspection.recommendations",
        f"inspection:{report.id}",
        [report.gouvernorat_code],
        audience=body.audience,
        count=len(set(body.ids)),
    )
    return await record(session, report.id)


async def apply_policy(session: AsyncSession, principal: Principal) -> int:
    """The current policy again on every sent room report (the inspector general's choice, design-i §4)."""
    rules = (await policy(session)).config
    reports = list(
        await session.scalars(
            select(Inspection).where(
                Inspection.target == "room", Inspection.status == "submitted", Inspection.deleted_at.is_(None)
            )
        )
    )
    for report in reports:
        report.disclosure = domain.disclosure_of(rules)
        report.updated_at = now()
        for rec in await session.scalars(select(Recommendation).where(Recommendation.inspection_id == report.id)):
            rec.to_central, rec.to_regional = domain.audience_flags(
                domain.recommendation_audience(rules, rec.kind, rec.priority)
            )
    await _audit(session, principal, "inspection.policy_apply", "insp_policy", count=len(reports))
    return len(reports)


# ---------------------------------------------------------------- dashboard and status


def place_key(target: str, room: str | None, gouvernorat_code: int | None, kind: str | None, name: str | None) -> str:
    """One key per place: a room, or a unit by its gouvernorat, kind and name as typed."""
    if target == "room":
        return f"room:{room}:{gouvernorat_code or '-'}"
    return f"unit:{gouvernorat_code}:{kind}:{(name or '').strip().casefold()}"


def _key(r: MissionSite | Inspection) -> str:
    return place_key(r.target, r.room, r.gouvernorat_code, r.unit_kind, r.unit_name)


async def dashboard(session: AsyncSession) -> schemas.DashboardOut:
    t = today()
    first = t.replace(day=1)
    nxt = (first + timedelta(days=32)).replace(day=1)
    month = list(
        await session.scalars(
            select(Mission).where(Mission.on_date >= first, Mission.on_date < nxt, Mission.status == "planned")
        )
    )
    sites = await _sites_of(session, [m.id for m in month])
    reports = await _reports_of(session, [s.id for g in sites.values() for s in g])
    states = [mission_state(m, sites[m.id], reports) for m in month]
    planned_rooms = {
        _key(site)
        for site in await session.scalars(
            select(MissionSite)
            .join(Mission, Mission.id == MissionSite.mission_id)
            .where(Mission.status == "planned", Mission.on_date >= t, MissionSite.target == "room")
        )
    }
    all_rooms = 1 + len(await gouvernorat_names(session))
    since = first.replace(year=first.year - 1)
    sent = list(
        await session.execute(
            select(Inspection.submitted_at, Inspection.score, Inspection.verdict).where(
                Inspection.status == "submitted",
                Inspection.deleted_at.is_(None),
                Inspection.submitted_at >= datetime.combine(since, datetime.min.time(), TUNIS_TZ),
            )
        )
    )
    by_month: dict[str, int] = {}
    levels: dict[str, int] = {}
    stamps = [(at.astimezone(TUNIS_TZ), score_, verdict) for at, score_, verdict in sent if at is not None]
    for at, _score, verdict in stamps:
        key = at.strftime("%Y-%m")
        by_month[key] = by_month.get(key, 0) + 1
        levels[verdict or ""] = levels.get(verdict or "", 0) + 1
    in_month = [s for at, s, _ in stamps if first <= at.date() < nxt and s is not None]
    return schemas.DashboardOut(
        month_missions=len(month),
        month_done=states.count("done"),
        month_planned=states.count("planned"),
        rooms_without_plan=max(0, all_rooms - len(planned_rooms)),
        average_score=round(sum(in_month) / len(in_month)) if in_month else None,
        by_month=[{"month": k, "count": v} for k, v in sorted(by_month.items())],
        levels=levels,
    )


async def unit_status(session: AsyncSession, gouvernorat_code: int | None) -> list[schemas.UnitStatusOut]:
    """The operations rooms, then every unit ever planned, each with its last sent report and next planned mission."""
    reports = select(Inspection).where(Inspection.status == "submitted", Inspection.deleted_at.is_(None))
    planned = select(MissionSite, Mission.on_date, Mission.status).join(Mission, Mission.id == MissionSite.mission_id)
    if gouvernorat_code is not None:
        reports = reports.where(Inspection.gouvernorat_code == gouvernorat_code)
        planned = planned.where(MissionSite.gouvernorat_code == gouvernorat_code)
    last: dict[str, Inspection] = {}
    for r in await session.scalars(reports.order_by(Inspection.submitted_at.desc())):
        last.setdefault(_key(r), r)
    upcoming: dict[str, date] = {}
    units: dict[str, MissionSite] = {}
    for site, on, state in await session.execute(planned.order_by(Mission.on_date)):
        key = _key(site)
        if site.target == "unit":
            units.setdefault(key, site)
        if state == "planned" and on >= today():
            upcoming.setdefault(key, on)
    names = await gouvernorat_names(session)
    places: list[tuple[str, str | None, str | None, str | None, int | None]] = []
    if gouvernorat_code is None:
        places.append(("room", "central", None, None, None))
    for g in sorted(names) if gouvernorat_code is None else [gouvernorat_code]:
        places.append(("room", "regional", None, None, g))
    places += sorted(
        (("unit", None, u.unit_kind, u.unit_name, u.gouvernorat_code) for u in units.values()),
        key=lambda p: (p[4] or 0, p[2] or "", (p[3] or "").casefold()),
    )
    out = []
    for target, room, kind, name, code in places:
        key = place_key(target, room, code, kind, name)
        report = last.get(key)
        out.append(
            schemas.UnitStatusOut(
                target=target,
                unit_kind=kind,
                unit_name=name,
                room=room,
                name=room_name(room, code, names) if target == "room" else unit_place(kind, name),
                gouvernorat_code=code,
                last_inspection_id=report.id if report else None,
                last_on=report.submitted_at if report else None,
                last_score=report.score if report else None,
                last_verdict=report.verdict if report else None,
                next_on=upcoming.get(key),
            )
        )
    return out


# ---------------------------------------------------------------- the rooms


def _room_of(principal: Principal) -> str:
    return "central" if principal.is_national else "regional"


def _room_scope(principal: Principal) -> Any:
    """The room reports a room may read: every room's for the central room, its own room's for a regional one."""
    if principal.is_national:
        return Inspection.target == "room"
    return and_(
        Inspection.target == "room",
        Inspection.room == "regional",
        Inspection.gouvernorat_code == principal.gouvernorat_code,
    )


async def room_results(session: AsyncSession, principal: Principal) -> list[schemas.RoomResultOut]:
    room = _room_of(principal)
    rows = list(
        await session.scalars(
            select(Inspection)
            .where(
                _room_scope(principal),
                Inspection.status == "submitted",
                Inspection.deleted_at.is_(None),
                Inspection.disclosure[room]["inspection"].as_boolean(),
            )
            .order_by(Inspection.submitted_at.desc())
            .limit(500)
        )
    )
    names = await place_names(session, rows)
    flag = Recommendation.to_central if room == "central" else Recommendation.to_regional
    recs: dict[uuid.UUID, list[Recommendation]] = {r.id: [] for r in rows}
    if rows:
        for rec in await session.scalars(
            select(Recommendation)
            .where(Recommendation.inspection_id.in_(list(recs)), flag.is_(True))
            .order_by(Recommendation.position)
        ):
            recs[rec.inspection_id].append(rec)
    out = []
    for r in rows:
        view = domain.room_view(r.disclosure, room)  # type: ignore[arg-type]
        assert r.submitted_at is not None
        out.append(
            schemas.RoomResultOut(
                id=r.id,
                room=r.room,
                place=names[r.id],
                gouvernorat_code=r.gouvernorat_code,
                kind=r.kind,
                submitted_at=r.submitted_at,
                verdict=r.verdict if view["verdict"] else None,
                score=r.score if view["score"] else None,
                recommendations=[
                    schemas.RecommendationOut(
                        id=x.id,
                        kind=x.kind,
                        item_key=None,
                        text=x.text,
                        priority=x.priority,
                        audience=room,
                    )
                    for x in recs[r.id]
                ],
            )
        )
    return out


async def room_live(session: AsyncSession, principal: Principal) -> list[schemas.RoomLiveOut]:
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "central_room_only")
    rows = list(
        await session.scalars(
            select(Inspection)
            .where(Inspection.target == "room", Inspection.status == "in_progress", Inspection.deleted_at.is_(None))
            .order_by(Inspection.started_at)
        )
    )
    names = await place_names(session, rows)
    inspectors = {
        i.id: i.name
        for i in await session.scalars(select(Inspector).where(Inspector.id.in_({r.inspector_id for r in rows})))
    }
    return [
        schemas.RoomLiveOut(
            id=r.id,
            room=r.room,
            place=names[r.id],
            gouvernorat_code=r.gouvernorat_code,
            inspector_name=inspectors.get(r.inspector_id, ""),
            started_at=r.started_at,
            answered=len(r.answers),
            items=len(r.profile.get("items", [])),
            score=r.score,
        )
        for r in rows
    ]


async def room_upcoming(session: AsyncSession, principal: Principal) -> list[schemas.RoomUpcomingOut]:
    """The programme of the rooms' inspections, for the central room only, when published (a regional room never
    sees an inspection before it happens)."""
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "central_room_only")
    rows = list(
        await session.execute(
            select(MissionSite, Mission)
            .join(Mission, Mission.id == MissionSite.mission_id)
            .where(
                Mission.status == "planned",
                Mission.published.is_(True),
                Mission.on_date >= today(),
                MissionSite.target == "room",
            )
            .order_by(Mission.on_date)
        )
    )
    names = await place_names(session, [s for s, _ in rows])
    return [
        schemas.RoomUpcomingOut(
            ref=m.ref,
            room=s.room,
            place=names[s.id],
            gouvernorat_code=s.gouvernorat_code,
            on_date=m.on_date,
            kind=m.kind,
        )
        for s, m in rows
    ]


# ---------------------------------------------------------------- the system administrator


async def delete_records(session: AsyncSession, principal: Principal, body: schemas.DeleteIn) -> int:
    if body.confirm.strip() != CONFIRM_WORD:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "confirm_word")
    query = update(Inspection).where(Inspection.deleted_at.is_(None))
    if body.scope == "one":
        if body.inspection_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "inspection_required")
        query = query.where(Inspection.id == body.inspection_id)
    elif body.scope == "period":
        if body.from_date is None or body.to_date is None or body.to_date < body.from_date:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "period_required")
        query = query.where(
            Inspection.started_at >= datetime.combine(body.from_date, datetime.min.time(), TUNIS_TZ),
            Inspection.started_at < datetime.combine(body.to_date + timedelta(days=1), datetime.min.time(), TUNIS_TZ),
        )
    result = await session.execute(
        query.values(deleted_at=now(), deleted_by_name=name_of(principal), delete_reason=body.reason)
    )
    count = int(result.rowcount or 0)  # type: ignore[attr-defined]
    if body.scope == "one" and count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await audit.record(
        session,
        actor=actor_of(principal),
        action="inspection.delete",
        target=f"inspection:{body.inspection_id}" if body.scope == "one" else f"inspections:{body.scope}",
        reason=body.reason,
        details={"count": count, "from": str(body.from_date or ""), "to": str(body.to_date or "")},
    )
    return count


async def bin_rows(session: AsyncSession) -> list[schemas.BinRow]:
    rows = list(
        await session.scalars(
            select(Inspection).where(Inspection.deleted_at.is_not(None)).order_by(Inspection.deleted_at.desc())
        )
    )
    names = await place_names(session, rows)
    return [
        schemas.BinRow(
            id=r.id,
            place=names[r.id],
            submitted_at=r.submitted_at,
            deleted_at=r.deleted_at,
            deleted_by_name=r.deleted_by_name,
            delete_reason=r.delete_reason,
        )
        for r in rows
    ]


async def restore(session: AsyncSession, principal: Principal, inspection_id: uuid.UUID) -> None:
    report = await session.get(Inspection, inspection_id, with_for_update=True)
    if report is None or report.deleted_at is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    report.deleted_at = None
    report.deleted_by_name = None
    report.delete_reason = None
    await audit.record(
        session, actor=actor_of(principal), action="inspection.restore", target=f"inspection:{report.id}"
    )
