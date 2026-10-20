"""Who may touch an incident and its interventions (phase 9 §1.2, §5): the glue between the operations module and
the policy function ``core.access.authorize``.

Out-of-scope objects answer ``404 not_found``; in-scope but forbidden actions ``403 <code>``. Field actions (orders to
resources, call-outs) stay with the regions: a national caller gets ``403 field_action_regional_only`` before any
other check, and a resource of another gouvernorat ``403 resource_not_owned``.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import FIELD_ACTION_REGIONAL_ONLY, Action, Ctx, authorize, require
from app.core.access import room_of as room_of
from app.core.security import Principal
from app.modules.ops.models import Incident, IncidentGouvernorat
from app.modules.reports.models import Report


def forbidden(code: str) -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, code)


def not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "not_found")


async def gouvernorats_of(session: AsyncSession, incident_id: uuid.UUID) -> tuple[int | None, frozenset[int]]:
    """(lead, participating gouvernorats) of an incident."""
    rows = (
        await session.execute(
            select(IncidentGouvernorat.gouvernorat_code, IncidentGouvernorat.role).where(
                IncidentGouvernorat.incident_id == incident_id
            )
        )
    ).all()
    lead = next((int(code) for code, role in rows if role == "lead"), None)
    return lead, frozenset(int(code) for code, role in rows if role == "participating")


async def incident_ctx(session: AsyncSession, incident: Incident) -> Ctx:
    lead, participants = await gouvernorats_of(session, incident.id)
    return Ctx(
        lead=incident.gouvernorat_code if lead is None else lead,
        participants=participants,
        candidates=frozenset(),
        claimed_room=None,
        critical=False,
        command_level=incident.command_level,
        incident_id=incident.id,
    )


async def report_ctx(session: AsyncSession, report: Report) -> Ctx:
    """Scope of a report: its gouvernorat, the gouvernorats of its incident, its critical geo candidates."""
    participants: frozenset[int] = frozenset()
    command_level = "regional"
    if report.incident_id is not None:
        lead, others = await gouvernorats_of(session, report.incident_id)
        participants = others | ({lead} if lead is not None else frozenset())
        command_level = (
            await session.scalar(select(Incident.command_level).where(Incident.id == report.incident_id))
        ) or "regional"
    return Ctx(
        lead=report.gouvernorat_code,
        participants=participants,
        candidates=frozenset(report.geo_candidates or ()),
        claimed_room=report.claimed_room,
        critical=report.sla_band == "critical" or report.category == "sos",
        command_level=command_level,
        late=report.escalation_state != "none",
        report_id=report.id,
        incident_id=report.incident_id,
    )


async def check(session: AsyncSession, principal: Principal, action: Action, ctx: Ctx) -> None:
    require(await authorize(session, principal, action, ctx))


async def check_incident(session: AsyncSession, principal: Principal, incident: Incident, action: Action) -> None:
    await check(session, principal, action, await incident_ctx(session, incident))


def regional_only(principal: Principal) -> int:
    """Field actions (assignments, call-outs, their follow-up) belong to a regional room; returns its gouvernorat."""
    if principal.is_national or principal.gouvernorat_code is None:
        raise forbidden(FIELD_ACTION_REGIONAL_ONLY)
    return principal.gouvernorat_code
