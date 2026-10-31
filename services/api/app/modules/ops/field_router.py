"""Field agents (phase F, docs/phase-f/design-f.md §1).

``/api/v1/field/*`` is open (no account yet): the phone activates itself with a professional number and a one-time
code, then renews its tokens. ``/api/v1/staff/field-agents`` is the room chief's page. ``/api/v1/crew/charter``
records the charter an activated agent accepted.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import ratelimit
from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.ops import field_agents, schemas

router = APIRouter(prefix="/api/v1/field", tags=["field-agents"])
staff_router = APIRouter(prefix="/api/v1/staff/field-agents", tags=["field-agents"])
crew_router = APIRouter(prefix="/api/v1/crew", tags=["field-agents"])

Manager = Annotated[Principal, Depends(require_roles(*field_agents.MANAGERS))]
Agent = Annotated[Principal, Depends(require_roles(Role.TEAM_LEADER, Role.FIELD_AGENT))]
Session = Annotated[AsyncSession, Depends(get_session)]
#: Activations tried from one address in an hour (the codes themselves lock after a few wrong tries).
ACTIVATIONS_PER_HOUR = 20
REFRESHES_PER_HOUR = 120


@router.post("/activate", response_model=schemas.FieldTokens)
async def activate(request: Request, session: Session, body: schemas.FieldActivateIn) -> schemas.FieldTokens:
    await ratelimit.enforce(f"field-activate:{ratelimit.client_key(request)}", ACTIVATIONS_PER_HOUR, 3600)
    out = await field_agents.activate(session, body)
    await session.commit()
    return out


@router.post("/token", response_model=schemas.FieldTokens)
async def token(request: Request, session: Session, body: schemas.FieldRefreshIn) -> schemas.FieldTokens:
    await ratelimit.enforce(f"field-token:{ratelimit.client_key(request)}", REFRESHES_PER_HOUR, 3600)
    out = await field_agents.refresh(session, body)
    await session.commit()
    return out


@crew_router.post("/charter", status_code=status.HTTP_204_NO_CONTENT)
async def charter(principal: Agent, session: Session, body: schemas.CharterIn) -> None:
    await field_agents.accept_charter(session, principal, body)
    await session.commit()


@staff_router.get("", response_model=list[schemas.FieldAgentOut])
async def list_agents(
    principal: Manager, session: Session, gouvernorat_code: Annotated[int | None, Query(ge=11, le=83)] = None
) -> list[schemas.FieldAgentOut]:
    return await field_agents.list_agents(session, principal, gouvernorat_code)


@staff_router.post("", response_model=schemas.FieldAgentOut, status_code=status.HTTP_201_CREATED)
async def create(principal: Manager, session: Session, body: schemas.FieldAgentIn) -> schemas.FieldAgentOut:
    out = await field_agents.create(session, principal, body)
    await session.commit()
    return out


@staff_router.patch("/{agent_id}", response_model=schemas.FieldAgentOut)
async def update(
    principal: Manager, session: Session, agent_id: uuid.UUID, body: schemas.FieldAgentPatch
) -> schemas.FieldAgentOut:
    out = await field_agents.update(session, principal, agent_id, body)
    await session.commit()
    return out


@staff_router.post("/{agent_id}/code", response_model=schemas.FieldAgentOut)
async def renew_code(principal: Manager, session: Session, agent_id: uuid.UUID) -> schemas.FieldAgentOut:
    out = await field_agents.renew_code(session, principal, agent_id)
    await session.commit()
    return out


@staff_router.post("/{agent_id}/disable", response_model=schemas.FieldAgentOut)
async def disable(
    principal: Manager, session: Session, agent_id: uuid.UUID, body: schemas.FieldAgentAction
) -> schemas.FieldAgentOut:
    out = await field_agents.disable(session, principal, agent_id, body.reason, delete=False)
    await session.commit()
    return out


@staff_router.post("/{agent_id}/delete", response_model=schemas.FieldAgentOut)
async def delete(
    principal: Manager, session: Session, agent_id: uuid.UUID, body: schemas.FieldAgentAction
) -> schemas.FieldAgentOut:
    out = await field_agents.disable(session, principal, agent_id, body.reason, delete=True)
    await session.commit()
    return out
