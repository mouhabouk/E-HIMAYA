"""Operational levels per gouvernorat (requirements §6.4, FR-C-24).

``normal`` is the default. ``crisis`` (local or central committee) raises the priority of the zone's
reports; ``disaster`` (central committee only) also applies AI grouping automatically (BR-11) and
suspends informational notifications. Every module reads the level from here.
"""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import emit
from app.core.security import Principal, Role
from app.modules.audit import service as audit
from app.modules.ops import schemas
from app.modules.ops.models import Incident, LevelState, OpLevel, TimelineEvent
from app.modules.reports.domain import Status
from app.modules.reports.models import Report

RESCORE_WINDOW = timedelta(hours=48)
RESCORE_MAX = 2000
_FINAL = (Status.CLOSED.value, Status.REJECTED.value)


def level_out(row: LevelState) -> schemas.LevelOut:
    return schemas.LevelOut(
        gouvernorat_code=row.gouvernorat_code,
        level=row.level,
        since=row.since,
        reason=row.reason,
        set_by=row.set_by_name,
    )


async def all_levels(session: AsyncSession) -> list[LevelState]:
    return list(await session.scalars(select(LevelState).order_by(LevelState.gouvernorat_code)))


async def level_of(session: AsyncSession, gouvernorat_code: int | None) -> OpLevel:
    if gouvernorat_code is None:
        return OpLevel.NORMAL
    level = await session.scalar(select(LevelState.level).where(LevelState.gouvernorat_code == gouvernorat_code))
    return level or OpLevel.NORMAL


async def levels_of(session: AsyncSession, codes: list[int] | None = None) -> dict[int, OpLevel]:
    query = select(LevelState.gouvernorat_code, LevelState.level)
    if codes is not None:
        query = query.where(LevelState.gouvernorat_code.in_(codes))
    return {code: level for code, level in (await session.execute(query)).all()}


def _check_allowed(principal: Principal, codes: list[int], target: OpLevel, current: dict[int, OpLevel]) -> None:
    if Role.CENTRAL_COMMITTEE in principal.roles and principal.is_national:
        return
    # A local committee (or a central committee member with a regional scope) acts on its gouvernorat only,
    # between normal and crisis; a disaster is declared and lifted centrally.
    allowed = (
        principal.gouvernorat_code is not None
        and set(codes) == {principal.gouvernorat_code}
        and target is not OpLevel.DISASTER
        and current.get(principal.gouvernorat_code) is not OpLevel.DISASTER
    )
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "level_not_allowed")


async def set_levels(
    session: AsyncSession, principal: Principal, codes: list[int], target: OpLevel, reason: str
) -> list[LevelState]:
    rows = list(
        await session.scalars(
            select(LevelState)
            .where(LevelState.gouvernorat_code.in_(codes))
            .with_for_update()
            .order_by(LevelState.gouvernorat_code)
        )
    )
    if len(rows) != len(set(codes)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_gouvernorat")
    _check_allowed(principal, codes, target, {r.gouvernorat_code: r.level for r in rows})
    actor, name, now = audit.actor_of(principal), audit.name_of(principal), datetime.now(UTC)
    changed = [r for r in rows if r.level is not target]
    for row in changed:
        previous = row.level
        row.level, row.since, row.reason, row.set_by, row.set_by_name = target, now, reason, actor, name
        await audit.record(
            session,
            actor=actor,
            action="oplevel.change",
            target=f"gouvernorat:{row.gouvernorat_code}",
            reason=reason,
            details={"from": previous.value, "to": target.value},
        )
    if not changed:
        return rows
    changed_codes = [r.gouvernorat_code for r in changed]
    open_incidents = list(
        await session.scalars(
            select(Incident.id).where(Incident.status == "open", Incident.gouvernorat_code.in_(changed_codes))
        )
    )
    await session.execute(
        update(Incident).where(Incident.id.in_(open_incidents)).values(op_level=target, updated_at=now)
    )
    for incident_id in open_incidents:
        session.add(
            TimelineEvent(incident_id=incident_id, kind="level_changed", actor=actor, payload={"level": target.value})
        )
    await session.flush()
    for row in changed:
        await emit(session, "oplevel.changed", {"level": level_out(row).model_dump(mode="json")})
    # The level is a priority component: re-rank the zone's recent open reports.
    from app.modules.ai import pipeline

    recent = list(
        await session.scalars(
            select(Report.id)
            .where(
                Report.gouvernorat_code.in_(changed_codes),
                Report.status.not_in(_FINAL),
                Report.received_at >= now - RESCORE_WINDOW,
            )
            .order_by(Report.received_at.desc())
            .limit(RESCORE_MAX)
        )
    )
    await pipeline.rescore(session, recent)
    return rows
