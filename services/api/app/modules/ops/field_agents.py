"""Field agents and their phones (phase F, docs/phase-f/design-f.md §1).

The room chief adds the agents of their gouvernorat and hands each one a code that works once. The agent types it on
the staff app with their professional number; the phone is then registered to them and receives the platform's own
tokens (``app.core.field_tokens``). A lost phone is disabled from the room: its session ends at once, its refresh
token is refused and the app erases itself at the next call. A deleted account is hidden but its phones stay on record.
"""

import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy import update as sql_update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import field_tokens, sessions
from app.core.db import system_scoped
from app.core.security import Principal, Role
from app.modules.audit import service as audit
from app.modules.ops import schemas
from app.modules.ops.models import Assignment, CrewPosition, FieldAgent, Shift, StaffDevice
from app.modules.settings import service as settings_service

#: Letters and digits that cannot be mistaken for one another when read aloud or typed (no 0/O, 1/I/L).
ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_LENGTH = 8
REFRESH_TTL = timedelta(days=30)
ACTIVATION_REFUSED = "activation_refused"
#: Who manages the agents: the room chief of the gouvernorat, and the regional account administrator.
MANAGERS = (Role.OPS_MANAGER, Role.REGIONAL_ACCOUNT_ADMIN)
SUBJECT_PREFIX = "field:"


def _now() -> datetime:
    return datetime.now(UTC)


def subject_of(agent: FieldAgent) -> str:
    return f"{SUBJECT_PREFIX}{agent.id}"


def roles_of(agent: FieldAgent) -> list[str]:
    return [Role.TEAM_LEADER.value if agent.function == "leader" else Role.FIELD_AGENT.value]


def normalise_code(code: str) -> str:
    return "".join(c for c in code.upper() if c.isalnum())


def new_code() -> str:
    raw = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
    return f"{raw[:4]}-{raw[4:]}"


def _scope(principal: Principal, gouvernorat_code: int | None) -> int:
    """The gouvernorat the manager acts on: their own, or the one a national account names."""
    if principal.gouvernorat_code is not None:
        if gouvernorat_code not in (None, principal.gouvernorat_code):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
        return principal.gouvernorat_code
    if gouvernorat_code is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "gouvernorat_required")
    return gouvernorat_code


async def _agent(session: AsyncSession, principal: Principal, agent_id: uuid.UUID) -> FieldAgent:
    agent = await session.get(FieldAgent, agent_id, with_for_update=True)
    if agent is None or agent.status == "deleted":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if principal.gouvernorat_code not in (None, agent.gouvernorat_code):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return agent


async def _give_code(session: AsyncSession, agent: FieldAgent) -> str:
    """A fresh code for the agent (the previous one stops working); the platform keeps only its fingerprint."""
    hours = await settings_service.threshold(session, "field.code_hours")
    code = new_code()
    agent.code_hash = field_tokens.fingerprint(normalise_code(code))
    agent.code_expires_at = _now() + timedelta(hours=hours)
    agent.code_attempts = 0
    return code


# ---------------------------------------------------------------- the room chief


async def _devices(session: AsyncSession, agent_ids: list[uuid.UUID]) -> dict[uuid.UUID, StaffDevice]:
    """The latest phone of each agent."""
    if not agent_ids:
        return {}
    rows = await session.scalars(
        select(StaffDevice).where(StaffDevice.agent_id.in_(agent_ids)).order_by(StaffDevice.created_at)
    )
    return {d.agent_id: d for d in rows if d.agent_id is not None}


async def _last_positions(session: AsyncSession, subjects: list[str]) -> dict[str, tuple[float, float, datetime]]:
    if not subjects:
        return {}
    latest = (
        select(
            Shift.subject,
            func.ST_Y(cast(CrewPosition.location, Geometry)).label("lat"),
            func.ST_X(cast(CrewPosition.location, Geometry)).label("lon"),
            CrewPosition.at,
        )
        .join(Assignment, Assignment.id == CrewPosition.assignment_id)
        .join(Shift, Shift.id == Assignment.shift_id)
        .where(Shift.subject.in_(subjects))
        .order_by(Shift.subject, CrewPosition.at.desc())
        .ext(distinct_on(Shift.subject))
    )
    return {r.subject: (r.lat, r.lon, r.at) for r in await session.execute(latest)}


def _out(
    agent: FieldAgent, device: StaffDevice | None, position: tuple[float, float, datetime] | None, code: str | None
) -> schemas.FieldAgentOut:
    return schemas.FieldAgentOut(
        id=agent.id,
        gouvernorat_code=agent.gouvernorat_code,
        matricule=agent.matricule,
        name=agent.name,
        function=agent.function,
        shift_label=agent.shift_label,
        phone=agent.phone,
        status=agent.status,
        code_expires_at=agent.code_expires_at if agent.code_hash else None,
        code=code,
        charter_accepted_at=agent.charter_accepted_at,
        activated_at=agent.activated_at,
        disabled_at=agent.disabled_at,
        disabled_reason=agent.disabled_reason,
        device=schemas.FieldDeviceOut(
            id=device.id,
            model=device.model,
            platform=device.platform,
            device_ref=device.device_ref,
            sim_number=device.sim_number,
            imei=device.imei,
            created_at=device.created_at,
            last_seen_at=device.last_seen_at,
            revoked_at=device.revoked_at,
        )
        if device is not None
        else None,
        last_position=schemas.FieldPosition(lat=position[0], lon=position[1], at=position[2])
        if position is not None
        else None,
    )


async def list_agents(
    session: AsyncSession, principal: Principal, gouvernorat_code: int | None
) -> list[schemas.FieldAgentOut]:
    code = _scope(principal, gouvernorat_code)
    agents = list(
        await session.scalars(
            select(FieldAgent)
            .where(FieldAgent.gouvernorat_code == code, FieldAgent.status != "deleted")
            .order_by(FieldAgent.shift_label.nulls_last(), FieldAgent.function, FieldAgent.matricule)
        )
    )
    devices = await _devices(session, [a.id for a in agents])
    positions = await _last_positions(session, [subject_of(a) for a in agents])
    return [_out(a, devices.get(a.id), positions.get(subject_of(a)), None) for a in agents]


async def create(session: AsyncSession, principal: Principal, body: schemas.FieldAgentIn) -> schemas.FieldAgentOut:
    code_of = _scope(principal, body.gouvernorat_code)
    taken = await session.scalar(
        select(FieldAgent.id).where(
            FieldAgent.gouvernorat_code == code_of,
            FieldAgent.matricule == body.matricule,
            FieldAgent.status != "deleted",
        )
    )
    if taken is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "matricule_taken")
    agent = FieldAgent(
        gouvernorat_code=code_of,
        matricule=body.matricule,
        name=body.name,
        function=body.function,
        shift_label=body.shift_label,
        phone=body.phone,
        created_by=audit.actor_of(principal),
    )
    session.add(agent)
    code = await _give_code(session, agent)
    await session.flush()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="field_agent.create",
        target=f"field_agent:{agent.id}",
        details={"function": agent.function},
        gouvernorats=[code_of],
    )
    return _out(agent, None, None, code)


async def update(
    session: AsyncSession, principal: Principal, agent_id: uuid.UUID, body: schemas.FieldAgentPatch
) -> schemas.FieldAgentOut:
    agent = await _agent(session, principal, agent_id)
    changed = body.model_dump(exclude_unset=True)
    for name in ("name", "function", "shift_label", "phone"):
        if name in changed:
            setattr(agent, name, changed[name])
    if "function" in changed:
        # The new role reaches the phone with its next token; end the current one now.
        await sessions.revoke(subject_of(agent))
    devices = await _devices(session, [agent.id])
    device = devices.get(agent.id)
    if "imei" in changed:
        if device is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "no_device")
        device.imei = changed["imei"]
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="field_agent.update",
        target=f"field_agent:{agent.id}",
        details={"fields": sorted(changed)},
        gouvernorats=[agent.gouvernorat_code],
    )
    return _out(agent, device, None, None)


async def renew_code(session: AsyncSession, principal: Principal, agent_id: uuid.UUID) -> schemas.FieldAgentOut:
    """A new code: for an agent who lost theirs, or to activate a new phone (the old one is revoked when it does)."""
    agent = await _agent(session, principal, agent_id)
    code = await _give_code(session, agent)
    if agent.status == "disabled":
        agent.status = "pending"
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="field_agent.code",
        target=f"field_agent:{agent.id}",
        gouvernorats=[agent.gouvernorat_code],
    )
    return _out(agent, (await _devices(session, [agent.id])).get(agent.id), None, code)


async def _revoke_devices(session: AsyncSession, agent: FieldAgent, by: str, *, end_sessions: bool = True) -> None:
    """Retire the agent's phones. Their access tokens end too, unless a new phone takes over at once (activation):
    then the old phone is refused by its revoked device id, and the new phone's tokens of this very second stay
    valid. The refresh token stays known so that the phone hears ``410 device_revoked`` and erases itself."""
    await session.execute(
        sql_update(StaffDevice)
        .where(StaffDevice.agent_id == agent.id, StaffDevice.revoked_at.is_(None))
        .values(revoked_at=_now(), revoked_by=by)
    )
    if end_sessions:
        await sessions.revoke(subject_of(agent))


async def disable(
    session: AsyncSession, principal: Principal, agent_id: uuid.UUID, reason: str | None, delete: bool
) -> schemas.FieldAgentOut:
    """Disable the agent (lost phone, leave) or delete the account: the phone stops at once and erases itself."""
    agent = await _agent(session, principal, agent_id)
    by = audit.actor_of(principal)
    await _revoke_devices(session, agent, by)
    agent.status = "deleted" if delete else "disabled"
    agent.code_hash = None
    agent.code_expires_at = None
    agent.disabled_at = _now()
    agent.disabled_by = by
    agent.disabled_reason = reason
    await audit.record(
        session,
        actor=by,
        action="field_agent.delete" if delete else "field_agent.disable",
        target=f"field_agent:{agent.id}",
        reason=reason,
        gouvernorats=[agent.gouvernorat_code],
    )
    return _out(agent, (await _devices(session, [agent.id])).get(agent.id), None, None)


# ---------------------------------------------------------------- the phone


def _tokens(agent: FieldAgent, device: StaffDevice) -> schemas.FieldTokens:
    refresh = field_tokens.new_refresh()
    device.refresh_hash = field_tokens.fingerprint(refresh)
    device.refresh_expires_at = _now() + REFRESH_TTL
    access, expires = field_tokens.issue(
        subject=subject_of(agent),
        name=agent.name,
        username=agent.matricule,
        roles=roles_of(agent),
        gouvernorat_code=agent.gouvernorat_code,
        device_id=str(device.id),
    )
    return schemas.FieldTokens(
        access_token=access,
        expires_at=expires,
        refresh_token=refresh,
        device_id=device.id,
        name=agent.name,
        function=agent.function,
        gouvernorat_code=agent.gouvernorat_code,
        charter_accepted=agent.charter_accepted_at is not None,
    )


async def _refuse(session: AsyncSession, agent: FieldAgent | None, matricule: str) -> HTTPException:
    """Count a wrong try against the agent the professional number names; the code dies at the limit."""
    limit = await settings_service.threshold(session, "field.code_attempts")
    targets = (
        [agent]
        if agent is not None
        else list(
            await session.scalars(
                select(FieldAgent).where(FieldAgent.matricule == matricule, FieldAgent.code_hash.is_not(None))
            )
        )
    )
    for target in targets:
        target.code_attempts += 1
        if target.code_attempts >= limit:
            target.code_hash = None
            target.code_expires_at = None
    await session.commit()
    return HTTPException(status.HTTP_401_UNAUTHORIZED, ACTIVATION_REFUSED)


@system_scoped
async def activate(session: AsyncSession, body: schemas.FieldActivateIn) -> schemas.FieldTokens:
    agent = await session.scalar(
        select(FieldAgent)
        .where(FieldAgent.code_hash == field_tokens.fingerprint(normalise_code(body.code)))
        .with_for_update()
    )
    if agent is None or agent.status == "deleted":
        raise await _refuse(session, None, body.matricule)
    if not hmac.compare_digest(agent.matricule, body.matricule):
        raise await _refuse(session, agent, body.matricule)
    if agent.code_expires_at is None or agent.code_expires_at < _now():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "activation_expired")
    # One phone per agent: a new activation retires the previous phone.
    await _revoke_devices(session, agent, subject_of(agent), end_sessions=False)
    device = StaffDevice(
        subject=subject_of(agent),
        holder_name=agent.name,
        gouvernorat_code=agent.gouvernorat_code,
        label=body.device.model,
        platform=body.device.platform,
        app_build=body.device.app_build,
        push_token=body.device.push_token,
        agent_id=agent.id,
        model=body.device.model,
        device_ref=body.device.device_ref,
        sim_number=body.device.sim_number,
    )
    session.add(device)
    agent.status = "active"
    agent.code_hash = None
    agent.code_expires_at = None
    agent.code_attempts = 0
    agent.activated_at = _now()
    await session.flush()
    out = _tokens(agent, device)
    await audit.record(
        session,
        actor=f"staff:{subject_of(agent)}",
        action="field_agent.activate",
        target=f"staff_device:{device.id}",
        details={"platform": device.platform, "model": device.model},
        gouvernorats=[agent.gouvernorat_code],
    )
    return out


@system_scoped
async def refresh(session: AsyncSession, body: schemas.FieldRefreshIn) -> schemas.FieldTokens:
    device = await session.scalar(
        select(StaffDevice)
        .where(StaffDevice.refresh_hash == field_tokens.fingerprint(body.refresh_token))
        .with_for_update()
    )
    if device is None or device.agent_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh_refused")
    if device.revoked_at is not None:
        raise HTTPException(status.HTTP_410_GONE, "device_revoked")
    agent = await session.get(FieldAgent, device.agent_id)
    if agent is None or agent.status != "active":
        raise HTTPException(status.HTTP_410_GONE, "device_revoked")
    if device.refresh_expires_at is None or device.refresh_expires_at < _now():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh_expired")
    device.last_seen_at = _now()
    return _tokens(agent, device)


async def agent_of(session: AsyncSession, principal: Principal) -> FieldAgent | None:
    if not principal.subject.startswith(SUBJECT_PREFIX):
        return None
    try:
        agent_id = uuid.UUID(principal.subject.removeprefix(SUBJECT_PREFIX))
    except ValueError:
        return None
    return await session.get(FieldAgent, agent_id)


async def accept_charter(session: AsyncSession, principal: Principal, body: schemas.CharterIn) -> None:
    agent = await agent_of(session, principal)
    if agent is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "field_agent_only")
    agent.charter_version = body.version
    agent.charter_accepted_at = _now()
    agent.consents = {"sms": body.sms, "location": body.location}
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="field_agent.charter",
        target=f"field_agent:{agent.id}",
        details={"version": body.version, "sms": body.sms, "location": body.location},
        gouvernorats=[agent.gouvernorat_code],
    )
